"""
バッチマッチングスクリプト — 全 ship_profiles × 未マッチ regulations を判定
==============================================================================
GHA から定期実行し、新規規制 × 登録船舶のマッチングを自動実行する。

使い方:
    python run_matching.py                 # 通常実行
    python run_matching.py --dry-run       # DB 書き込みなし
    python run_matching.py --limit 10      # 最大 10 規制のみ処理
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Optional

# scripts/ 内の utils/ を import 可能にする
sys.path.insert(0, os.path.dirname(__file__))

import requests

from utils.matching import match_regulation_to_ship

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger("run_matching")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[Matching] %(levelname)s: %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Supabase REST API ヘルパー
# ---------------------------------------------------------------------------

SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _headers() -> dict[str, str]:
    """Supabase REST API 共通ヘッダー"""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def fetch_all_paginated(table: str, select: str = "*", extra_params: Optional[dict] = None) -> list[dict]:
    """
    Supabase REST API からページネーション付きで全行を取得する。
    1000 行ずつ取得し、結果が空になるまで繰り返す。
    """
    all_rows: list[dict] = []
    offset = 0
    page_size = 1000

    while True:
        params: dict = {
            "select": select,
            "limit": str(page_size),
            "offset": str(offset),
        }
        if extra_params:
            params.update(extra_params)

        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            params=params,
            headers=_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.json()

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < page_size:
            break

        offset += page_size

    return all_rows


def fetch_ship_profiles() -> list[dict]:
    """ship_profiles テーブルから全行を取得"""
    logger.info("ship_profiles を取得中...")
    profiles = fetch_all_paginated("ship_profiles")
    logger.info(f"ship_profiles: {len(profiles)} 件取得")
    return profiles


def fetch_regulations(limit: Optional[int] = None) -> list[dict]:
    """regulations テーブルから全行を取得（limit 指定時は最新 N 件）"""
    logger.info("regulations を取得中...")
    params: dict = {"order": "created_at.desc"}
    if limit:
        params["limit"] = str(limit)
    regulations = fetch_all_paginated("regulations", extra_params=params)
    logger.info(f"regulations: {len(regulations)} 件取得")
    return regulations


def fetch_existing_matches() -> set[tuple[str, str]]:
    """
    user_matches テーブルから、正常に完了した (regulation_id, ship_profile_id) ペアを取得。
    confidence=0 のレコード（429 等で失敗した判定）は再処理対象とするためスキップしない。
    """
    logger.info("既存の user_matches を取得中...")
    rows = fetch_all_paginated(
        "user_matches",
        select="regulation_id,ship_profile_id,confidence",
    )
    # confidence > 0 のもののみ「完了済み」として扱う
    existing = {
        (row["regulation_id"], row["ship_profile_id"])
        for row in rows
        if row.get("confidence") is not None and row["confidence"] > 0
    }
    total = len(rows)
    retry = total - len(existing)
    logger.info(f"既存 user_matches: {total} ペア（完了={len(existing)}, 再処理対象={retry}）")
    return existing


def upsert_match(
    regulation_id: str,
    ship_profile_id: str,
    result: dict,
) -> bool:
    """
    user_matches テーブルに upsert する。
    UNIQUE 制約: (regulation_id, ship_profile_id)
    """
    row = {
        "regulation_id": regulation_id,
        "ship_profile_id": ship_profile_id,
        "is_applicable": result.get("is_applicable"),
        "match_method": result.get("match_method", ""),
        "confidence": result.get("confidence", 0.0),
        "reason": result.get("reason", ""),
        "citations": json.dumps(result.get("citations") or [], ensure_ascii=False),
        "notified": False,
    }

    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/user_matches?on_conflict=regulation_id,ship_profile_id",
            json=row,
            headers={
                **_headers(),
                "Prefer": "resolution=merge-duplicates",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return True
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        logger.error(f"user_matches upsert 失敗 (HTTP {status}): {e}")
        return False
    except requests.RequestException as e:
        logger.error(f"user_matches upsert 失敗: {e}")
        return False


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def run_matching(dry_run: bool = False, limit: Optional[int] = None, force: bool = False) -> None:
    """バッチマッチングのメインロジック"""

    if not _supabase_configured():
        logger.error("SUPABASE_URL または SUPABASE_SERVICE_ROLE_KEY が未設定です。終了します。")
        sys.exit(1)

    # 1. ship_profiles 取得
    ship_profiles = fetch_ship_profiles()
    if not ship_profiles:
        logger.warning("ship_profiles が 0 件です。マッチング対象がないため終了します。")
        return

    # 2. regulations 取得
    regulations = fetch_regulations(limit=limit)
    if not regulations:
        logger.warning("regulations が 0 件です。マッチング対象がないため終了します。")
        return

    # 3. 既存マッチを取得してスキップ対象を特定
    if force:
        existing_matches: set[tuple[str, str]] = set()
        logger.info("FORCE モード: 既存マッチを全て無視し、全ペアを再処理します")
    else:
        existing_matches = fetch_existing_matches()

    # 4. 未マッチペアを計算
    pairs_to_process: list[tuple[dict, dict]] = []
    for reg in regulations:
        reg_id = reg.get("id")
        if not reg_id:
            continue
        for ship in ship_profiles:
            ship_id = ship.get("id")
            if not ship_id:
                continue
            if (reg_id, ship_id) not in existing_matches:
                pairs_to_process.append((reg, ship))

    logger.info(
        f"マッチング対象: {len(pairs_to_process)} ペア "
        f"(regulations={len(regulations)} × ships={len(ship_profiles)} "
        f"- 既存={len(existing_matches)})"
    )

    if not pairs_to_process:
        logger.info("未マッチのペアがありません。終了します。")
        return

    if dry_run:
        logger.info("=== DRY RUN モード: DB 書き込みをスキップします ===")

    # 5. マッチング実行
    stats = {"processed": 0, "applicable": 0, "not_applicable": 0, "error": 0, "skipped_429": 0}

    for i, (reg, ship) in enumerate(pairs_to_process, 1):
        reg_id = reg["id"]
        ship_id = ship["id"]
        source_label = f"{reg.get('source', '?')}/{reg.get('source_id', '?')}"
        ship_label = f"{ship.get('ship_name', '?')}"

        logger.info(f"[{i}/{len(pairs_to_process)}] {source_label} × {ship_label}")

        try:
            result = match_regulation_to_ship(reg, ship)
        except Exception as e:
            error_msg = str(e)
            # Gemini 429 レート制限を検出して graceful に処理
            if "429" in error_msg:
                logger.warning(f"Gemini レート制限 (429) を検出。このペアをスキップします: {source_label} × {ship_label}")
                stats["skipped_429"] += 1
                # 少し待ってから次へ
                time.sleep(5)
                continue
            logger.error(f"マッチングエラー: {e}")
            stats["error"] += 1
            continue

        is_applicable = result.get("is_applicable")
        confidence = result.get("confidence", 0.0)
        method = result.get("match_method", "?")

        logger.info(
            f"  結果: is_applicable={is_applicable}, "
            f"confidence={confidence:.2f}, method={method}"
        )

        if dry_run:
            logger.info(f"  [DRY RUN] upsert スキップ")
        else:
            success = upsert_match(reg_id, ship_id, result)
            if not success:
                stats["error"] += 1
                continue

        stats["processed"] += 1
        if is_applicable is True:
            stats["applicable"] += 1
        elif is_applicable is False:
            stats["not_applicable"] += 1

    # 6. サマリー出力
    logger.info("=" * 60)
    logger.info("マッチング完了 サマリー:")
    logger.info(f"  処理済み:      {stats['processed']}")
    logger.info(f"  適用:          {stats['applicable']}")
    logger.info(f"  非適用:        {stats['not_applicable']}")
    logger.info(f"  エラー:        {stats['error']}")
    logger.info(f"  429 スキップ:  {stats['skipped_429']}")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI エントリポイント
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="バッチマッチング: 全 ship_profiles × 未マッチ regulations を判定"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 書き込みなし（マッチング結果をログ出力のみ）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="処理する regulations の最大件数（最新 N 件）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="既存の全マッチング結果を無視し、全ペアを再処理する",
    )
    args = parser.parse_args()

    logger.info("バッチマッチング開始")
    if args.dry_run:
        logger.info("モード: DRY RUN")
    if args.force:
        logger.info("モード: FORCE（全件再処理）")
    if args.limit:
        logger.info(f"規制取得上限: {args.limit} 件")

    run_matching(dry_run=args.dry_run, limit=args.limit, force=args.force)

    logger.info("バッチマッチング終了")


if __name__ == "__main__":
    main()
