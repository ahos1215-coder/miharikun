"""
pending_queue リトライスクリプト
================================
pending_queue に溜まった失敗エントリを再処理する。
retry_count < 3 のエントリを取得し、PDF ダウンロード → Gemini 分類 → DB upsert を試みる。

Usage:
    python process_queue.py [--source nk|mlit] [--limit 20] [--dry-run]
"""

import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import requests
from utils.gemini_client import classify_pdf
from utils.supabase_client import SupabaseClient
from utils.line_notify import send_alert

# レートリミット: アイテム間の最小待機秒数
_GEMINI_MIN_INTERVAL = float(os.environ.get("GEMINI_MIN_INTERVAL", "4"))
_MAX_CONSECUTIVE_429 = 2

# ---------------------------------------------------------------------------
# ロガー
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="[ProcessQueue] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PDF ダウンロード
# ---------------------------------------------------------------------------
USER_AGENT = os.environ.get(
    "SCRAPE_USER_AGENT",
    "MaritimeRegsMonitor/1.0 (process-queue)"
)


def download_pdf(url: str, timeout: int = 60) -> bytes | None:
    """PDF をダウンロードしてバイト列を返す。失敗時は None。"""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
        if len(resp.content) < 100:
            logger.warning(f"PDF が小さすぎます ({len(resp.content)} bytes): {url}")
            return None
        return resp.content
    except requests.RequestException as e:
        logger.error(f"PDF ダウンロード失敗: {url} — {e}")
        return None


# ---------------------------------------------------------------------------
# 分類プロンプト（汎用）
# ---------------------------------------------------------------------------
CLASSIFICATION_PROMPT = """
あなたは海事規制の専門家です。添付された PDF を読み、以下の情報を JSON で返してください。

- category: 規制のカテゴリ（SOLAS, MARPOL, 船員, PSC, その他）
- summary: 日本語の要約（200字以内）
- severity: critical / warning / info / upcoming
- applicable_vessel_types: 適用船種のリスト
- effective_date: 施行日（不明なら null）
"""


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------
def process_queue(
    source: str | None = None,
    limit: int = 20,
    batch_size: int = 5,
    dry_run: bool = False,
) -> dict:
    """
    pending_queue を処理する。

    Args:
        source: 処理するソース（None=全ソース）
        limit: キューから取得する最大件数
        batch_size: 1回の実行で実際に処理する最大件数（レートリミット対策）
        dry_run: True の場合は実際の処理をスキップ

    Returns:
        {"processed": int, "succeeded": int, "failed": int, "skipped": int}
    """
    client = SupabaseClient()
    queue = client.get_pending_queue(source=source)

    if not queue:
        logger.info("処理対象なし")
        return {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0}

    if len(queue) > limit:
        logger.info(f"キュー {len(queue)} 件中 {limit} 件のみ取得")
        queue = queue[:limit]

    # batch_size でさらに絞る
    effective_count = min(len(queue), batch_size)
    if effective_count < len(queue):
        logger.info(f"バッチサイズ制限: {len(queue)} 件中 {effective_count} 件のみ処理")
        queue = queue[:effective_count]

    stats = {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0}
    consecutive_429: int = 0

    for idx, item in enumerate(queue):
        queue_id = item["id"]
        source_id = item.get("source_id", "?")
        pdf_url = item.get("pdf_url", "")
        item_source = item.get("source", "unknown")

        # 連続 429 エラーチェック
        if consecutive_429 >= _MAX_CONSECUTIVE_429:
            logger.warning(
                f"[Queue] Stopping early: {_MAX_CONSECUTIVE_429} consecutive 429 errors. "
                "Will retry next hour."
            )
            break

        # アイテム間の待機（最初のアイテムはスキップ）
        if idx > 0 and not dry_run:
            logger.info(f"アイテム間待機: {_GEMINI_MIN_INTERVAL:.0f}s")
            time.sleep(_GEMINI_MIN_INTERVAL)

        logger.info(f"処理中: {source_id} ({item_source}) retry={item.get('retry_count', 0)}")
        stats["processed"] += 1

        if dry_run:
            logger.info(f"[DRY-RUN] スキップ: {source_id}")
            stats["skipped"] += 1
            continue

        if not pdf_url:
            logger.warning(f"PDF URL なし: {source_id}")
            client.increment_retry_count(queue_id, "PDF URL が空")
            stats["failed"] += 1
            continue

        # 1. PDF ダウンロード
        pdf_bytes = download_pdf(pdf_url)
        if pdf_bytes is None:
            client.increment_retry_count(queue_id, f"PDF ダウンロード失敗: {pdf_url}")
            stats["failed"] += 1
            continue

        # 2. Gemini 分類
        result = classify_pdf(pdf_bytes, CLASSIFICATION_PROMPT, source_id=source_id)

        if result.get("status") != "ok":
            error_msg = result.get("error", "分類失敗")
            # 429 エラーの連続回数をトラッキング
            if "429" in error_msg:
                consecutive_429 += 1
                logger.warning(f"429 エラー検出 ({consecutive_429}/{_MAX_CONSECUTIVE_429}): {source_id}")
            else:
                consecutive_429 = 0
            client.increment_retry_count(queue_id, error_msg)
            stats["failed"] += 1
            continue

        # 3. regulations に upsert
        regulation = {
            "source": item_source,
            "source_id": source_id,
            "pdf_url": pdf_url,
            "category": result.get("category"),
            "summary_ja": result.get("summary"),
            "severity": result.get("severity", "informational"),
            "confidence": result.get("confidence", 0.0),
            "citations": result.get("citations", []),
            "needs_review": result.get("confidence", 0.0) < 0.7,
            "applicable_ship_types": result.get("applicable_vessel_types", []),
            "effective_date": result.get("effective_date"),
            "raw_gemini_response": result,
        }

        success = client.upsert_regulation(regulation)
        if success:
            client.delete_from_pending_queue(queue_id)
            stats["succeeded"] += 1
            consecutive_429 = 0
            logger.info(f"成功: {source_id}")
        else:
            client.increment_retry_count(queue_id, "DB upsert 失敗")
            stats["failed"] += 1

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="pending_queue リトライ処理")
    parser.add_argument("--source", choices=["nk", "mlit"], default=None,
                        help="処理するソース（省略時は全ソース）")
    parser.add_argument("--limit", type=int, default=20,
                        help="キューから取得する最大件数")
    parser.add_argument("--batch-size", type=int, default=5,
                        help="1回の実行で実際に処理する件数（レートリミット対策）")
    parser.add_argument("--dry-run", action="store_true",
                        help="実際の処理をスキップ")
    args = parser.parse_args()

    logger.info(
        f"開始: source={args.source or 'all'}, limit={args.limit}, "
        f"batch_size={args.batch_size}, dry_run={args.dry_run}"
    )

    stats = process_queue(
        source=args.source,
        limit=args.limit,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    logger.info(
        f"完了: 処理={stats['processed']} 成功={stats['succeeded']} "
        f"失敗={stats['failed']} スキップ={stats['skipped']}"
    )

    # 失敗が多い場合は LINE 通知
    if stats["failed"] > 0:
        send_alert(
            "Queue リトライ結果",
            f"処理={stats['processed']} 成功={stats['succeeded']} 失敗={stats['failed']}",
            severity="warning" if stats["failed"] > 3 else "info",
        )

    # CI 用: 全件失敗なら exit code 1
    if stats["processed"] > 0 and stats["succeeded"] == 0 and not args.dry_run:
        sys.exit(1)


if __name__ == "__main__":
    main()
