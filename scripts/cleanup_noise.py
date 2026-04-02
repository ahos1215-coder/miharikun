"""
既存ノイズデータの一括清掃
===========================
「航海士が読んでも、設備を変える必要も、マニュアルを改訂する必要も、
免状の手続きが変わることもない情報」を regulations テーブルから削除する。

ノイズの定義:
  - 旅客船・遊覧船の事故対策検討会
  - 造船・舶用工業の産業政策
  - 港湾施設・インフラ整備
  - 審議会・検討会・議事録
  - 統計・調査報告
  - 一般啓発・広報（海の日等）
  - 漁船・プレジャーボート専用の規制

使い方:
  python cleanup_noise.py --dry-run   # 削除対象の確認のみ
  python cleanup_noise.py             # 実際に削除
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import argparse
import logging
from typing import Optional

import requests

from utils.supabase_client import SupabaseClient  # type: ignore
from utils.filters import is_noise, NOISE_KEYWORDS_SINGLE, NOISE_KEYWORD_PAIRS  # type: ignore

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cleanup_noise")


def find_noise_records(client: SupabaseClient) -> list[dict]:
    """
    全ソースの regulations から、ノイズ判定されるレコードを全取得。
    全件取得してローカルで判定（Supabase の or フィルタの複雑さを回避）。
    """
    if not client._configured:
        logger.warning("Supabase 未設定: ノイズレコードを検索できません。")
        return []

    # 全件取得（ページネーション付き）
    all_records: list[dict] = []
    offset = 0
    page_size = 1000

    while True:
        try:
            resp = requests.get(
                f"{client.url}/rest/v1/regulations",
                params={
                    "select": "id,source_id,source,title,summary_ja,url,pdf_url",
                    "limit": str(page_size),
                    "offset": str(offset),
                },
                headers=client._headers,
                timeout=30,
            )
            resp.raise_for_status()
            records = resp.json()
            if not records:
                break
            all_records.extend(records)
            offset += page_size
            if len(records) < page_size:
                break
        except Exception as e:
            logger.error("全件取得エラー (offset=%d): %s", offset, e)
            break

    logger.info("全規制レコード取得: %d 件", len(all_records))

    # ローカルでノイズ判定
    noise_records: list[dict] = []
    for record in all_records:
        # NK はすべて実務情報のため、ノイズ判定をスキップ
        if (record.get("source") or "").lower() == "nk":
            continue
        title = record.get("title") or ""
        summary = record.get("summary_ja") or ""
        noise, reason = is_noise(title, summary)
        if noise:
            record["_noise_reason"] = reason
            noise_records.append(record)
            logger.debug("ノイズ: [%s] %s — %s", record.get("source", "?"), title[:60], reason)

    return noise_records


# ---------------------------------------------------------------------------
# ノイズレコード削除
# ---------------------------------------------------------------------------

def delete_noise_records(
    client: SupabaseClient,
    records: list[dict],
    dry_run: bool,
) -> int:
    """
    ノイズレコードを regulations テーブルから削除する。
    関連する pending_queue エントリも削除する。

    Returns:
        削除件数
    """
    deleted = 0

    for record in records:
        record_id = record.get("id")
        source_id = record.get("source_id", "?")
        title = record.get("title", "?")

        if dry_run:
            logger.info("[dry-run] 削除対象: %s — %s", source_id, title)
            deleted += 1
            continue

        try:
            # regulations から削除
            resp = requests.delete(
                f"{client.url}/rest/v1/regulations",
                params={"id": f"eq.{record_id}"},
                headers=client._headers,
                timeout=15,
            )
            resp.raise_for_status()

            # pending_queue からも削除（source_id で紐付け）
            if source_id and source_id != "?":
                try:
                    resp_pq = requests.delete(
                        f"{client.url}/rest/v1/pending_queue",
                        params={"source_id": f"eq.{source_id}"},
                        headers=client._headers,
                        timeout=15,
                    )
                    resp_pq.raise_for_status()
                except Exception:
                    pass  # pending_queue になくてもエラーにしない

            deleted += 1
            logger.info("削除完了: %s — %s", source_id, title)

        except Exception as e:
            logger.error("削除エラー: %s — %s", source_id, e)

    return deleted


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="既存ノイズデータの一括清掃"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="削除対象の確認のみ（実際には削除しない）",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=== DRY RUN モード ===")

    client = SupabaseClient()

    # ノイズレコード検索
    total_keywords = len(NOISE_KEYWORDS_SINGLE) + len(NOISE_KEYWORD_PAIRS)
    logger.info("ノイズレコード検索開始（単独%d + AND%d = %d パターン）",
                len(NOISE_KEYWORDS_SINGLE), len(NOISE_KEYWORD_PAIRS), total_keywords)
    noise_records = find_noise_records(client)

    if not noise_records:
        logger.info("ノイズレコードは見つかりませんでした。")
        return

    # ソース別カウント
    source_counts: dict[str, int] = {}
    for r in noise_records:
        src = r.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    logger.info("ノイズレコード検出: %d 件", len(noise_records))
    for src, cnt in sorted(source_counts.items()):
        logger.info("  %s: %d 件", src, cnt)

    # 削除対象のタイトル一覧（dry-run でも表示）
    for r in noise_records:
        logger.info("  [%s] %s — 理由: %s",
                    r.get("source", "?"),
                    (r.get("title") or "?")[:60],
                    r.get("_noise_reason", "?"))

    # 削除
    deleted = delete_noise_records(client, noise_records, args.dry_run)

    if args.dry_run:
        logger.info("=== DRY RUN 完了: %d 件が削除対象 ===", deleted)
    else:
        logger.info("=== 清掃完了: %d 件を削除 ===", deleted)


if __name__ == "__main__":
    main()
