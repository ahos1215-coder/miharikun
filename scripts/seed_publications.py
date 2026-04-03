"""
seed_publications.py — 書籍マスターデータの初期投入
====================================================
publication_requirements.py の全書籍データを publications テーブルに upsert する。

使い方:
    python scripts/seed_publications.py          # 本番投入
    python scripts/seed_publications.py --dry-run # ドライラン（DB書き込みなし）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import argparse
import logging
from typing import Optional

import requests

from utils.publication_requirements import (
    CATEGORY_A_PUBLICATIONS,
    CATEGORY_D_PUBLICATIONS,
    JHO_PUBLICATIONS,
    UKHO_PUBLICATIONS,
    NGA_PUBLICATIONS,
    JPN_FLAG_PUBLICATIONS,
    CLASS_SOCIETY_PUBLICATIONS,
    ITU_PUBLICATIONS,
    NAVIGATION_REFERENCE_PUBLICATIONS,
    NK_SPECIALIZED_PUBLICATIONS,
    ISM_REFERENCE_PUBLICATIONS,
)
from utils.supabase_client import get_supabase_url, get_supabase_headers

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[SeedPub] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

STATIC_FIELDS = [
    "publication_id",
    "title",
    "title_ja",
    "category",
    "publisher",
    "current_edition",
    "current_edition_date",
    "legal_basis",
    "update_cycle",
    "applicability_rules",
]


# ---------------------------------------------------------------------------
# 全書籍データの収集
# ---------------------------------------------------------------------------

def collect_all_publications() -> list[dict]:
    """
    全カテゴリの書籍マスターデータを収集し、静的フィールドのみ抽出して返す。
    lambda (condition) など非シリアライズ可能なフィールドは除外。
    """
    all_pubs: list[dict] = []
    seen_ids: set[str] = set()

    def _add(pub_list: list[dict]) -> None:
        for pub in pub_list:
            pid = pub.get("publication_id", "")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            row = {"id": pid}
            for field in STATIC_FIELDS:
                if field == "publication_id":
                    continue  # id として既に追加済み
                val = pub.get(field)
                # None はそのまま渡す（Supabase 側で nullable）
                row[field] = val
            all_pubs.append(row)

    # カテゴリA: 条約書籍
    _add(CATEGORY_A_PUBLICATIONS)

    # カテゴリB: 航海用刊行物
    _add(JHO_PUBLICATIONS)
    _add(UKHO_PUBLICATIONS)
    _add(NGA_PUBLICATIONS)
    _add(ITU_PUBLICATIONS)
    _add(NAVIGATION_REFERENCE_PUBLICATIONS)

    # カテゴリC: 旗国・船級
    _add(JPN_FLAG_PUBLICATIONS)
    for class_pubs in CLASS_SOCIETY_PUBLICATIONS.values():
        _add(class_pubs)
    _add(NK_SPECIALIZED_PUBLICATIONS)
    _add(ISM_REFERENCE_PUBLICATIONS)

    # カテゴリD: 船上マニュアル
    _add(CATEGORY_D_PUBLICATIONS)

    return all_pubs


# ---------------------------------------------------------------------------
# Supabase upsert
# ---------------------------------------------------------------------------

def upsert_publications(
    publications: list[dict],
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    publications テーブルに upsert する。
    Supabase接続は supabase_client.py のSSoTを使用。

    Returns:
        (success_count, fail_count)
    """
    base_url = get_supabase_url()
    headers = {**get_supabase_headers(), "Prefer": "resolution=merge-duplicates"}

    success = 0
    failed = 0

    for pub in publications:
        pub_id = pub.get("id", "???")

        if dry_run:
            logger.info(f"[DRY-RUN] upsert: {pub_id} — {pub.get('title', '')}")
            success += 1
            continue

        try:
            resp = requests.post(
                f"{base_url}/rest/v1/publications?on_conflict=id",
                json=pub,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Upserted: {pub_id} — {pub.get('title', '')}")
            success += 1
        except requests.RequestException as e:
            status = getattr(getattr(e, "response", None), "status_code", "N/A")
            body = ""
            if hasattr(e, "response") and e.response is not None:
                body = e.response.text[:200]
            logger.error(f"Failed to upsert {pub_id}: HTTP {status} — {body}")
            failed += 1

    return success, failed


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="書籍マスターデータ初期投入")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB に書き込まずログ出力のみ",
    )
    args = parser.parse_args()

    # 環境変数チェック（supabase_client.py が読み込み時に取得済み）
    if not args.dry_run:
        try:
            url = get_supabase_url()
            if not url:
                raise ValueError("empty")
        except Exception:
            logger.error(
                "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY が未設定です。"
                "--dry-run で実行するか環境変数を設定してください。"
            )
            sys.exit(1)

    # 全書籍データ収集
    publications = collect_all_publications()
    logger.info(f"収集した書籍数: {len(publications)}")

    if not publications:
        logger.warning("投入する書籍データがありません。終了します。")
        return

    # カテゴリ別サマリー
    from collections import Counter
    cat_count = Counter(p.get("category", "?") for p in publications)
    for cat, count in sorted(cat_count.items()):
        logger.info(f"  カテゴリ {cat}: {count} 件")

    # upsert 実行
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    logger.info(f"=== {mode} モードで upsert 開始 ===")

    success, failed = upsert_publications(
        publications,
        dry_run=args.dry_run,
    )

    logger.info(f"=== 完了: 成功={success}, 失敗={failed} ===")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
