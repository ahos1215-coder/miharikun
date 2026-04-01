"""
既存ノイズデータの一括清掃
===========================
旅客船事故関連など、マッチング精度を下げるノイズレコードを
regulations テーブルから削除するワンショットスクリプト。

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

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cleanup_noise")

# ---------------------------------------------------------------------------
# ノイズパターン（タイトルまたは要約に含まれる文字列）
# ---------------------------------------------------------------------------

NOISE_PATTERNS: list[str] = [
    "旅客船の安全",
    "旅客船安全対策",
    "知床遊覧船",
    "遊覧船事故",
    "小型旅客船の安全",
    "検討委員会",
    "造船業の再生",
    "造船・舶用工業",
    "海事産業の現状",
    "海事観光",
]


# ---------------------------------------------------------------------------
# ノイズレコード検索
# ---------------------------------------------------------------------------

def find_noise_records(client: SupabaseClient) -> list[dict]:
    """
    source='MLIT' かつ タイトルに NOISE_PATTERNS を含むレコードを全取得。
    Supabase REST API の or フィルタを使用。
    """
    if not client._configured:
        logger.warning("Supabase 未設定: ノイズレコードを検索できません。")
        return []

    all_noise: list[dict] = []

    for pattern in NOISE_PATTERNS:
        try:
            resp = requests.get(
                f"{client.url}/rest/v1/regulations",
                params={
                    "source": "eq.MLIT",
                    "title": f"like.*{pattern}*",
                    "select": "id,source_id,title,url,pdf_url",
                    "limit": "1000",
                },
                headers=client._headers,
                timeout=30,
            )
            resp.raise_for_status()
            records = resp.json()
            if records:
                all_noise.extend(records)
                logger.info("パターン '%s' — %d 件ヒット", pattern, len(records))
        except Exception as e:
            logger.error("検索エラー (パターン='%s'): %s", pattern, e)

    # 重複排除（id ベース）
    seen_ids: set[str] = set()
    unique_noise: list[dict] = []
    for record in all_noise:
        record_id = str(record.get("id", ""))
        if record_id and record_id not in seen_ids:
            seen_ids.add(record_id)
            unique_noise.append(record)

    return unique_noise


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
    logger.info("ノイズレコード検索開始（%d パターン）", len(NOISE_PATTERNS))
    noise_records = find_noise_records(client)

    if not noise_records:
        logger.info("ノイズレコードは見つかりませんでした。")
        return

    logger.info("ノイズレコード検出: %d 件", len(noise_records))

    # 削除
    deleted = delete_noise_records(client, noise_records, args.dry_run)

    if args.dry_run:
        logger.info("=== DRY RUN 完了: %d 件が削除対象 ===", deleted)
    else:
        logger.info("=== 清掃完了: %d 件を削除 ===", deleted)


if __name__ == "__main__":
    main()
