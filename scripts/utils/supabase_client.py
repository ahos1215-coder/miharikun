"""
Supabase クライアント — 全スクレイパー共通ユーティリティ
=========================================================
SERVICE_ROLE_KEY で RLS をバイパスし、GHA バッチ処理から DB に書き込む。

使い方:
    from utils.supabase_client import SupabaseClient

    client = SupabaseClient()
    client.upsert_regulation(regulation_dict)
"""

import logging
import os
import time
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[Supabase] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# リトライ設定（指数バックオフ）
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # 秒
BACKOFF_MULTIPLIER = 2.0

# HTTP ステータスコード: transient error（リトライ対象）
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _is_transient_error(status_code: int) -> bool:
    """一時的なエラー（リトライ可能）か判定"""
    return status_code in TRANSIENT_STATUS_CODES


def _with_retry(func, *args, **kwargs):
    """
    指数バックオフ付きリトライラッパー。
    transient error の場合のみリトライし、それ以外は即座に諦める。
    成功した場合は (True, result)、最終失敗時は (False, None) を返す。
    """
    last_error: Optional[Exception] = None
    backoff = INITIAL_BACKOFF

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = func(*args, **kwargs)
            return True, result
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 0
            if not _is_transient_error(status_code):
                logger.error(f"Non-transient HTTP error {status_code}: {e}")
                return False, None
            last_error = e
            logger.warning(
                f"Transient error {status_code} on attempt {attempt}/{MAX_RETRIES}. "
                f"Retrying in {backoff:.1f}s..."
            )
        except requests.RequestException as e:
            last_error = e
            logger.warning(
                f"Request error on attempt {attempt}/{MAX_RETRIES}: {e}. "
                f"Retrying in {backoff:.1f}s..."
            )

        if attempt < MAX_RETRIES:
            time.sleep(backoff)
            backoff *= BACKOFF_MULTIPLIER

    logger.error(f"All {MAX_RETRIES} retries exhausted. Last error: {last_error}")
    return False, None


# ---------------------------------------------------------------------------
# SupabaseClient
# ---------------------------------------------------------------------------

class SupabaseClient:
    """
    Supabase REST API クライアント。
    SERVICE_ROLE_KEY を使い、RLS をバイパスして直接書き込む。
    接続失敗時は None/False を返す fail-safe 設計。
    """

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """
        url: Supabase プロジェクト URL（省略時は環境変数 SUPABASE_URL）
        key: SERVICE_ROLE_KEY（省略時は環境変数 SUPABASE_SERVICE_ROLE_KEY）
        """
        self.url = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

        if not self.url or not self.key:
            logger.warning(
                "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set. "
                "DB operations will be no-ops."
            )

    @property
    def _configured(self) -> bool:
        """接続情報が設定されているか"""
        return bool(self.url and self.key)

    @property
    def _headers(self) -> dict[str, str]:
        """共通リクエストヘッダー"""
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # regulations テーブル
    # ------------------------------------------------------------------

    def upsert_regulation(self, regulation: dict) -> bool:
        """
        regulations テーブルに upsert（INSERT or UPDATE）。
        UNIQUE 制約: (source, source_id)
        重複時は全フィールドを上書きする（merge-duplicates）。

        Returns: True on success, False on failure
        """
        if not self._configured:
            logger.warning(
                f"[SKIP] Supabase not configured. Would upsert: "
                f"{regulation.get('source_id', '?')}"
            )
            return False

        def _do_upsert():
            resp = requests.post(
                f"{self.url}/rest/v1/regulations?on_conflict=source,source_id",
                json=regulation,
                headers={
                    **self._headers,
                    "Prefer": "resolution=merge-duplicates",
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp

        success, resp = _with_retry(_do_upsert)

        if success:
            logger.info(f"Upserted regulation: {regulation.get('source_id')}")
            return True
        else:
            logger.error(
                f"Failed to upsert regulation: {regulation.get('source_id')}"
            )
            return False

    def get_max_source_id(self, source: str) -> Optional[str]:
        """
        指定ソースの最新 source_id を取得。
        NK の場合: "TEC-1373" 形式の文字列を返す。
        データがない場合または失敗時は None を返す。
        """
        if not self._configured:
            logger.warning(f"[SKIP] Supabase not configured. Cannot get max source_id for {source}")
            return None

        def _do_get():
            resp = requests.get(
                f"{self.url}/rest/v1/regulations",
                params={
                    "source": f"eq.{source}",
                    "select": "source_id",
                    "order": "source_id.desc",
                    "limit": "1",
                },
                headers=self._headers,
                timeout=15,
            )
            resp.raise_for_status()
            return resp

        success, resp = _with_retry(_do_get)

        if not success:
            logger.error(f"Failed to get max source_id for source={source}")
            return None

        rows = resp.json()
        if rows:
            source_id = rows[0].get("source_id")
            logger.info(f"Max source_id for {source}: {source_id}")
            return source_id

        logger.info(f"No regulations found for source={source}")
        return None

    # ------------------------------------------------------------------
    # pending_queue テーブル
    # ------------------------------------------------------------------

    def queue_pending(
        self,
        source: str,
        source_id: str,
        pdf_url: str,
        reason: str,
        error_detail: str = "",
    ) -> bool:
        """
        pending_queue に未処理エントリを登録する。
        PDF ダウンロード失敗・Gemini 分類失敗時に呼び出す。

        Returns: True on success, False on failure
        """
        if not self._configured:
            logger.warning(
                f"[SKIP] Supabase not configured. Would queue: {source_id} ({reason})"
            )
            return False

        row = {
            "source": source,
            "source_id": source_id,
            "pdf_url": pdf_url,
            "reason": reason,
            "error_detail": error_detail,
            "retry_count": 0,
        }

        def _do_insert():
            resp = requests.post(
                f"{self.url}/rest/v1/pending_queue",
                json=row,
                headers={
                    **self._headers,
                    # 同一エントリが既にある場合は何もしない（冪等性）
                    "Prefer": "resolution=ignore-duplicates",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp

        success, _ = _with_retry(_do_insert)

        if success:
            logger.info(f"Queued pending: {source_id} (reason={reason})")
            return True
        else:
            logger.error(f"Failed to queue pending: {source_id}")
            return False

    def get_pending_queue(self, source: Optional[str] = None) -> list[dict]:
        """
        pending_queue からリトライ対象を取得（retry_count < 3）。

        source: 指定した場合そのソースのみ返す。省略時は全ソース。
        Returns: list of dict（失敗時は空リスト）
        """
        if not self._configured:
            logger.warning("[SKIP] Supabase not configured. Returning empty pending queue.")
            return []

        params: dict = {
            "retry_count": "lt.3",
            "order": "created_at.asc",
        }
        if source:
            params["source"] = f"eq.{source}"

        def _do_get():
            resp = requests.get(
                f"{self.url}/rest/v1/pending_queue",
                params=params,
                headers=self._headers,
                timeout=15,
            )
            resp.raise_for_status()
            return resp

        success, resp = _with_retry(_do_get)

        if not success:
            logger.error("Failed to get pending queue")
            return []

        rows = resp.json()
        logger.info(f"Pending queue: {len(rows)} items (source={source or 'all'})")
        return rows

    def delete_from_pending_queue(self, queue_id: str) -> bool:
        """
        pending_queue から指定 ID のエントリを削除（処理成功後に呼び出す）。

        Returns: True on success, False on failure
        """
        if not self._configured:
            logger.warning(f"[SKIP] Supabase not configured. Would delete queue_id={queue_id}")
            return False

        def _do_delete():
            resp = requests.delete(
                f"{self.url}/rest/v1/pending_queue",
                params={"id": f"eq.{queue_id}"},
                headers=self._headers,
                timeout=15,
            )
            resp.raise_for_status()
            return resp

        success, _ = _with_retry(_do_delete)

        if success:
            logger.info(f"Deleted from pending queue: id={queue_id}")
            return True
        else:
            logger.error(f"Failed to delete from pending queue: id={queue_id}")
            return False

    def increment_retry_count(self, queue_id: str, error: str = "") -> bool:
        """
        pending_queue の retry_count を +1 し、last_error を更新する。
        リトライ失敗時に呼び出す。

        Returns: True on success, False on failure
        """
        if not self._configured:
            logger.warning(
                f"[SKIP] Supabase not configured. Would increment retry for id={queue_id}"
            )
            return False

        def _do_update():
            # Supabase REST API でのインクリメント: rpc か raw SQL が必要だが、
            # 単純化のため現在値+1 をセットする方式で対応。
            # まず現在値を取得
            resp_get = requests.get(
                f"{self.url}/rest/v1/pending_queue",
                params={"id": f"eq.{queue_id}", "select": "retry_count"},
                headers=self._headers,
                timeout=15,
            )
            resp_get.raise_for_status()
            rows = resp_get.json()
            if not rows:
                raise ValueError(f"pending_queue entry not found: id={queue_id}")

            current_count = rows[0].get("retry_count", 0)
            new_count = current_count + 1

            resp_update = requests.patch(
                f"{self.url}/rest/v1/pending_queue",
                params={"id": f"eq.{queue_id}"},
                json={
                    "retry_count": new_count,
                    "last_error": error[:1000] if error else "",  # カラム長制限
                },
                headers=self._headers,
                timeout=15,
            )
            resp_update.raise_for_status()
            return resp_update

        success, _ = _with_retry(_do_update)

        if success:
            logger.info(f"Incremented retry count for id={queue_id}")
            return True
        else:
            logger.error(f"Failed to increment retry count for id={queue_id}")
            return False

    # ------------------------------------------------------------------
    # ヘルスチェック
    # ------------------------------------------------------------------

    def check_source_health(self, source: str, days: int = 30) -> dict:
        """
        指定ソースの最終スクレイピング日時と経過日数を返す。

        Returns:
            {
                "last_scraped": "2026-03-29T...",  # ISO 8601 or None
                "days_since": 0,                    # 経過日数（取得失敗時は -1）
                "status": "healthy" | "stale" | "unknown"
            }
        """
        if not self._configured:
            logger.warning(
                f"[SKIP] Supabase not configured. Cannot check health for {source}"
            )
            return {"last_scraped": None, "days_since": -1, "status": "unknown"}

        def _do_get():
            resp = requests.get(
                f"{self.url}/rest/v1/regulations",
                params={
                    "source": f"eq.{source}",
                    "select": "scraped_at",
                    "order": "scraped_at.desc",
                    "limit": "1",
                },
                headers=self._headers,
                timeout=15,
            )
            resp.raise_for_status()
            return resp

        success, resp = _with_retry(_do_get)

        if not success:
            return {"last_scraped": None, "days_since": -1, "status": "unknown"}

        rows = resp.json()
        if not rows or not rows[0].get("scraped_at"):
            return {"last_scraped": None, "days_since": -1, "status": "unknown"}

        last_scraped_str = rows[0]["scraped_at"]

        # 経過日数の計算
        try:
            from datetime import datetime, timezone

            # Supabase は ISO 8601 with timezone を返す
            last_scraped_dt = datetime.fromisoformat(
                last_scraped_str.replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            days_since = (now - last_scraped_dt).days

            status = "healthy" if days_since <= days else "stale"

            logger.info(
                f"Health check for {source}: last_scraped={last_scraped_str}, "
                f"days_since={days_since}, status={status}"
            )
            return {
                "last_scraped": last_scraped_str,
                "days_since": days_since,
                "status": status,
            }
        except Exception as e:
            logger.error(f"Failed to calculate days_since for {source}: {e}")
            return {
                "last_scraped": last_scraped_str,
                "days_since": -1,
                "status": "unknown",
            }
