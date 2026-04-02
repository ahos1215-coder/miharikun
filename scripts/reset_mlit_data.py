"""
MLIT データ完全初期化（グランドゼロ）
====================================
regulations テーブルから source='MLIT' のレコードを全削除する。
NK データは保持する。

使い方:
  python reset_mlit_data.py --dry-run   # 件数確認のみ
  python reset_mlit_data.py             # 実際に削除
"""

import sys
import os
import logging
import argparse

sys.path.insert(0, os.path.dirname(__file__))

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reset_mlit")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def count_mlit() -> int:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/regulations",
        params={"source": "eq.MLIT", "select": "id", "limit": "10000"},
        headers={**_headers(), "Prefer": "count=exact"},
        timeout=30,
    )
    resp.raise_for_status()
    count = resp.headers.get("content-range", "")
    if "/" in count:
        return int(count.split("/")[1])
    return len(resp.json())


def count_nk() -> int:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/regulations",
        params={"source": "eq.nk", "select": "id", "limit": "10000"},
        headers={**_headers(), "Prefer": "count=exact"},
        timeout=30,
    )
    resp.raise_for_status()
    count = resp.headers.get("content-range", "")
    if "/" in count:
        return int(count.split("/")[1])
    return len(resp.json())


def delete_mlit(dry_run: bool) -> int:
    if dry_run:
        return count_mlit()

    # 全 MLIT レコードを削除
    resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/regulations",
        params={"source": "eq.MLIT"},
        headers=_headers(),
        timeout=60,
    )
    resp.raise_for_status()

    # pending_queue の MLIT も削除
    try:
        resp2 = requests.delete(
            f"{SUPABASE_URL}/rest/v1/pending_queue",
            params={"source": "eq.MLIT"},
            headers=_headers(),
            timeout=30,
        )
        resp2.raise_for_status()
    except Exception:
        pass

    # user_matches の orphaned レコードも考慮（CASCADE で自動削除されるはず）
    return count_mlit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mlit_count = count_mlit()
    nk_count = count_nk()

    logger.info(f"=== グランドゼロ: MLIT データ初期化 ===")
    logger.info(f"  MLIT レコード: {mlit_count}件 → 全削除対象")
    logger.info(f"  NK レコード: {nk_count}件 → 保持")

    if args.dry_run:
        logger.info(f"[DRY RUN] {mlit_count}件が削除対象です。NK {nk_count}件は保持されます。")
        return

    logger.info(f"削除実行中...")
    delete_mlit(dry_run=False)
    remaining = count_mlit()
    logger.info(f"=== 完了: MLIT {mlit_count}件削除 → 残り{remaining}件, NK {nk_count}件保持 ===")


if __name__ == "__main__":
    main()
