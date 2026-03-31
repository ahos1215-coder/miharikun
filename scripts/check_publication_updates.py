"""
check_publication_updates.py — 書籍最新版自動チェッカー
========================================================
各書籍の発行元サイトから最新版情報をフェッチし、publications テーブルの
edition と比較して差分があれば更新する。

初版ではスクレイピングは未実装。チェッカーのフレームワークのみ提供。

使い方:
    python scripts/check_publication_updates.py          # 本番実行
    python scripts/check_publication_updates.py --dry-run # ドライラン
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import argparse
import logging
from typing import Optional

import requests

from utils.line_notify import send_alert

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[PubCheck] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ===========================================================================
# Publisher ごとのチェッカー（将来スクレイピング実装用フレームワーク）
# ===========================================================================

def check_imo_publications() -> list[dict]:
    """
    IMO Publishing の最新版をチェック。
    Returns: [{"publication_id": "SOLAS_CONSOLIDATED", "latest_edition": "2025 Edition", "latest_date": "2025-01-01"}]
    """
    # TODO: 将来 IMO Publishing のスクレイピングを実装
    logger.info("[IMO] スクレイパー未実装 — スキップ")
    return []


def check_jho_publications() -> list[dict]:
    """
    海上保安庁 水路部（日本水路協会）の最新版をチェック。
    Returns: [{"publication_id": "JHO_CHART_CATALOG", "latest_edition": "...", "latest_date": "..."}]
    """
    # TODO: 将来 日本水路協会サイトのスクレイピングを実装
    logger.info("[JHO] スクレイパー未実装 — スキップ")
    return []


def check_nk_publications() -> list[dict]:
    """
    ClassNK の最新版をチェック。
    Returns: [{"publication_id": "NK_TECHNICAL_INFO", "latest_edition": "...", "latest_date": "..."}]
    """
    # TODO: 将来 ClassNK サイトのスクレイピングを実装
    logger.info("[ClassNK] スクレイパー未実装 — スキップ")
    return []


def check_ukho_publications() -> list[dict]:
    """
    UKHO (UK Hydrographic Office) の最新版をチェック。
    Returns: [{"publication_id": "ADMIRALTY_MARINERS_HANDBOOK", "latest_edition": "...", "latest_date": "..."}]
    """
    # TODO: 将来 UKHO サイトのスクレイピングを実装
    logger.info("[UKHO] スクレイパー未実装 — スキップ")
    return []


def check_ilo_publications() -> list[dict]:
    """
    ILO (MLC 2006) の最新版をチェック。
    Returns: [{"publication_id": "MLC_2006", "latest_edition": "...", "latest_date": "..."}]
    """
    # TODO: 将来 ILO サイトのスクレイピングを実装
    logger.info("[ILO] スクレイパー未実装 — スキップ")
    return []


# ---------------------------------------------------------------------------
# チェッカーレジストリ
# ---------------------------------------------------------------------------

CHECKERS: dict[str, callable] = {
    "IMO": check_imo_publications,
    "海上保安庁 水路部": check_jho_publications,
    "日本水路協会": check_jho_publications,
    "ClassNK": check_nk_publications,
    "NK": check_nk_publications,
    "UKHO": check_ukho_publications,
    "ILO": check_ilo_publications,
}


# ===========================================================================
# Supabase 連携
# ===========================================================================

class PublicationDBClient:
    """publications / ship_publications テーブル操作クライアント"""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def get_all_publications(self) -> list[dict]:
        """publications テーブルの全レコードを取得"""
        try:
            resp = requests.get(
                f"{self.url}/rest/v1/publications",
                params={"select": "id,title,publisher,current_edition,current_edition_date"},
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"publications テーブル取得失敗: {e}")
            return []

    def update_publication_edition(
        self,
        publication_id: str,
        latest_edition: str,
        latest_date: Optional[str],
    ) -> bool:
        """publications テーブルの edition を更新"""
        payload: dict = {"current_edition": latest_edition}
        if latest_date:
            payload["current_edition_date"] = latest_date

        try:
            resp = requests.patch(
                f"{self.url}/rest/v1/publications",
                params={"id": f"eq.{publication_id}"},
                json=payload,
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Updated edition: {publication_id} -> {latest_edition}")
            return True
        except requests.RequestException as e:
            logger.error(f"edition 更新失敗 ({publication_id}): {e}")
            return False

    def flag_needs_update(self, publication_id: str) -> bool:
        """ship_publications テーブルの該当レコードを needs_update=true に更新"""
        try:
            resp = requests.patch(
                f"{self.url}/rest/v1/ship_publications",
                params={"publication_id": f"eq.{publication_id}"},
                json={"needs_update": True},
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Flagged needs_update: publication_id={publication_id}")
            return True
        except requests.RequestException as e:
            logger.error(f"needs_update フラグ設定失敗 ({publication_id}): {e}")
            return False


# ===========================================================================
# メインロジック
# ===========================================================================

def run_checkers() -> list[dict]:
    """
    全チェッカーを実行し、最新版情報を収集する。
    Returns: [{"publication_id": ..., "latest_edition": ..., "latest_date": ...}]
    """
    all_updates: list[dict] = []
    executed: set[int] = set()  # 同一関数の重複実行防止

    for publisher, checker_fn in CHECKERS.items():
        fn_id = id(checker_fn)
        if fn_id in executed:
            continue
        executed.add(fn_id)

        logger.info(f"--- チェッカー実行: {publisher} ---")
        try:
            updates = checker_fn()
            if updates:
                all_updates.extend(updates)
                logger.info(f"  {publisher}: {len(updates)} 件の更新情報を検出")
        except Exception as e:
            logger.error(f"  {publisher} チェッカーでエラー: {e}")

    return all_updates


def compare_and_update(
    db: PublicationDBClient,
    latest_updates: list[dict],
    dry_run: bool = False,
) -> list[dict]:
    """
    DB の現在版と最新版を比較し、差分があれば更新する。

    Returns: 更新された書籍のリスト
    """
    if not latest_updates:
        logger.info("チェッカーからの更新情報なし。比較スキップ。")
        return []

    # DB から現在の edition を取得
    current_pubs = db.get_all_publications()
    current_map: dict[str, dict] = {p["id"]: p for p in current_pubs}

    updated: list[dict] = []

    for update in latest_updates:
        pub_id = update["publication_id"]
        latest_edition = update.get("latest_edition", "")
        latest_date = update.get("latest_date")

        current = current_map.get(pub_id)
        if not current:
            logger.warning(f"DB に存在しない publication_id: {pub_id} — スキップ")
            continue

        current_edition = current.get("current_edition", "")

        if current_edition == latest_edition:
            logger.info(f"  {pub_id}: 変更なし (edition={current_edition})")
            continue

        logger.info(
            f"  {pub_id}: 更新検出! "
            f"'{current_edition}' -> '{latest_edition}'"
        )

        if dry_run:
            logger.info(f"  [DRY-RUN] 更新スキップ: {pub_id}")
        else:
            db.update_publication_edition(pub_id, latest_edition, latest_date)
            db.flag_needs_update(pub_id)

        updated.append({
            "publication_id": pub_id,
            "title": current.get("title", ""),
            "old_edition": current_edition,
            "new_edition": latest_edition,
        })

    return updated


def notify_updates(updated: list[dict]) -> None:
    """更新があった書籍をLINE通知する"""
    if not updated:
        return

    lines = [f"- {u['title']}: {u['old_edition']} → {u['new_edition']}" for u in updated]
    body = "\n".join(lines)

    send_alert(
        title=f"書籍更新検出: {len(updated)} 件",
        message=body,
        severity="warning",
    )


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="書籍最新版自動チェッカー")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 更新せずログ出力のみ",
    )
    args = parser.parse_args()

    # 環境変数
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not args.dry_run and (not supabase_url or not supabase_key):
        logger.error(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY が未設定です。"
            "--dry-run で実行するか環境変数を設定してください。"
        )
        sys.exit(1)

    # チェッカー実行
    logger.info("=== 書籍最新版チェック開始 ===")
    latest_updates = run_checkers()

    if not latest_updates:
        logger.info("全チェッカーからの更新情報なし。正常終了。")
        return

    # DB 比較・更新
    db = PublicationDBClient(supabase_url, supabase_key)
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    logger.info(f"=== {mode} モードで比較・更新開始 ===")

    updated = compare_and_update(db, latest_updates, dry_run=args.dry_run)

    # 通知
    if updated and not args.dry_run:
        notify_updates(updated)

    logger.info(f"=== 完了: 更新={len(updated)} 件 ===")


if __name__ == "__main__":
    main()
