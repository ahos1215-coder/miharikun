"""
regulations 完全初期化（グランドゼロ）
====================================
regulations テーブルの全レコード（MLIT + NK 含む全ソース）を削除する。
--mlit-only で MLIT のみ削除も可能。

使い方:
  python reset_mlit_data.py --dry-run        # 件数確認のみ
  python reset_mlit_data.py                  # 全件削除
  python reset_mlit_data.py --mlit-only      # MLIT のみ削除
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


def count_all() -> int:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/regulations",
        params={"select": "id", "limit": "10000"},
        headers={**_headers(), "Prefer": "count=exact"},
        timeout=30,
    )
    resp.raise_for_status()
    count = resp.headers.get("content-range", "")
    if "/" in count:
        return int(count.split("/")[1])
    return len(resp.json())


def delete_all(dry_run: bool) -> None:
    """全ソースの regulations + pending_queue + user_matches を削除"""
    if dry_run:
        return

    # user_matches を先に削除（FK 制約）
    try:
        resp = requests.delete(
            f"{SUPABASE_URL}/rest/v1/user_matches",
            params={"id": "neq.00000000-0000-0000-0000-000000000000"},  # 全件
            headers=_headers(),
            timeout=60,
        )
        logger.info(f"  user_matches 削除: HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"  user_matches 削除エラー: {e}")

    # pending_queue を削除
    try:
        resp = requests.delete(
            f"{SUPABASE_URL}/rest/v1/pending_queue",
            params={"id": "neq.00000000-0000-0000-0000-000000000000"},
            headers=_headers(),
            timeout=60,
        )
        logger.info(f"  pending_queue 削除: HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"  pending_queue 削除エラー: {e}")

    # regulations を削除
    resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/regulations",
        params={"id": "neq.00000000-0000-0000-0000-000000000000"},
        headers=_headers(),
        timeout=60,
    )
    logger.info(f"  regulations 削除: HTTP {resp.status_code}")
    resp.raise_for_status()


def delete_mlit_only(dry_run: bool) -> None:
    """MLIT のみ削除"""
    if dry_run:
        return

    resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/regulations",
        params={"source": "eq.MLIT"},
        headers=_headers(),
        timeout=60,
    )
    resp.raise_for_status()

    try:
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/pending_queue",
            params={"source": "eq.MLIT"},
            headers=_headers(),
            timeout=30,
        )
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mlit-only", action="store_true", help="MLIT のみ削除（NK は保持）")
    args = parser.parse_args()

    mlit_count = count_mlit()
    nk_count = count_nk()
    total = count_all()

    logger.info(f"=== グランドゼロ: データ初期化 ===")
    logger.info(f"  全レコード: {total}件")
    logger.info(f"  MLIT: {mlit_count}件")
    logger.info(f"  NK: {nk_count}件")

    if args.mlit_only:
        logger.info(f"  モード: MLIT のみ削除（NK 保持）")
        if args.dry_run:
            logger.info(f"[DRY RUN] MLIT {mlit_count}件が削除対象")
            return
        delete_mlit_only(dry_run=False)
        logger.info(f"=== 完了: MLIT {mlit_count}件削除, NK {nk_count}件保持 ===")
    else:
        logger.info(f"  モード: 全件削除（NK 含む）")
        if args.dry_run:
            logger.info(f"[DRY RUN] 全{total}件が削除対象")
            return
        delete_all(dry_run=False)
        remaining = count_all()
        logger.info(f"=== 完了: {total}件削除 → 残り{remaining}件 ===")


if __name__ == "__main__":
    main()
