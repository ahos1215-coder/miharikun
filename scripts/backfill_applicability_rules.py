"""
backfill_applicability_rules.py — 既存規制の applicability_rules 一括生成
==========================================================================
既存 regulations の個別フィールド (applicable_ship_types, applicable_gt_min 等)
から applicability_rules JSONB を自動構築して更新する。

使い方:
    python scripts/backfill_applicability_rules.py          # 本番
    python scripts/backfill_applicability_rules.py --dry-run # ドライラン
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

import argparse
import logging

import requests

from utils.supabase_client import (
    get_supabase_url,
    get_supabase_headers,
    build_applicability_rules,
)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[Backfill] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def fetch_all_regulations() -> list[dict]:
    """applicability_rules が null の全規制を取得"""
    url = get_supabase_url()
    headers = get_supabase_headers()

    fields = (
        "id,source,source_id,applicable_ship_types,"
        "applicable_gt_min,applicable_gt_max,"
        "applicability_rules"
    )
    resp = requests.get(
        f"{url}/rest/v1/regulations",
        params={
            "select": fields,
            "applicability_rules": "is.null",
            "limit": "1000",
        },
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def update_applicability_rules(reg_id: str, rules: dict) -> bool:
    """regulations テーブルの applicability_rules を更新"""
    url = get_supabase_url()
    headers = get_supabase_headers()

    resp = requests.patch(
        f"{url}/rest/v1/regulations",
        params={"id": f"eq.{reg_id}"},
        json={"applicability_rules": rules},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="既存規制の applicability_rules 一括生成")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    regulations = fetch_all_regulations()
    logger.info(f"applicability_rules が null の規制: {len(regulations)} 件")

    updated = 0
    skipped = 0

    for reg in regulations:
        rules = build_applicability_rules(reg)
        if not rules:
            skipped += 1
            continue

        if args.dry_run:
            logger.info(f"[DRY-RUN] {reg['source_id']}: {json.dumps(rules, ensure_ascii=False)[:80]}")
            updated += 1
        else:
            try:
                update_applicability_rules(reg["id"], rules)
                updated += 1
                logger.info(f"Updated: {reg['source_id']}")
            except Exception as e:
                logger.error(f"Failed: {reg['source_id']} — {e}")

    logger.info(f"完了: 更新={updated}, スキップ={skipped}, 合計={len(regulations)}")


if __name__ == "__main__":
    main()
