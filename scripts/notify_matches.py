"""
LINE 通知スクリプト — 新規該当規制をユーザーに通知する
==============================================================================
マッチングエンジン実行後に呼び出し、is_applicable=true かつ未通知の
user_matches を LINE Notify で送信する。

使い方:
    python notify_matches.py              # 通常実行
    python notify_matches.py --dry-run    # 送信・DB更新なし（ログ出力のみ）
"""

import argparse
import logging
import os
import sys
from typing import Optional

# scripts/ 内の utils/ を import 可能にする
sys.path.insert(0, os.path.dirname(__file__))

import requests

from utils.line_notify import send_alert

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger("notify_matches")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[Notify] %(levelname)s: %(message)s"))
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


# ---------------------------------------------------------------------------
# データ取得
# ---------------------------------------------------------------------------

def fetch_unnotified_matches() -> list[dict]:
    """
    user_matches テーブルから未通知かつ該当 (is_applicable=true) のレコードを取得する。
    """
    logger.info("未通知の該当マッチを取得中...")
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/user_matches",
        params={
            "select": "*",
            "notified": "eq.false",
            "is_applicable": "eq.true",
            "limit": "1000",
        },
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    matches = resp.json()
    logger.info(f"未通知の該当マッチ: {len(matches)} 件")
    return matches


def fetch_regulation(regulation_id: str) -> Optional[dict]:
    """regulations テーブルから 1 件取得する。"""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/regulations",
        params={
            "select": "*",
            "id": f"eq.{regulation_id}",
            "limit": "1",
        },
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def fetch_ship_profile(ship_profile_id: str) -> Optional[dict]:
    """ship_profiles テーブルから 1 件取得する。"""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/ship_profiles",
        params={
            "select": "id,ship_name",
            "id": f"eq.{ship_profile_id}",
            "limit": "1",
        },
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def mark_notified(match_id: str) -> bool:
    """user_matches の notified フラグを true に更新する。"""
    try:
        resp = requests.patch(
            f"{SUPABASE_URL}/rest/v1/user_matches",
            params={"id": f"eq.{match_id}"},
            json={"notified": True},
            headers=_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"notified 更新失敗 (match_id={match_id}): {e}")
        return False


# ---------------------------------------------------------------------------
# 通知メッセージ組み立て
# ---------------------------------------------------------------------------

def build_message(
    ship_name: str,
    regulation: dict,
    confidence: float,
) -> str:
    """LINE 通知用の本文を組み立てる。"""
    title = regulation.get("title", "（タイトル不明）")
    severity = regulation.get("severity", "不明")
    reg_id = regulation.get("id", "")

    body = (
        f"{ship_name} に該当する規制が見つかりました\n\n"
        f"{title}\n"
        f"重要度: {severity}\n"
        f"確度: {confidence:.0f}%\n\n"
        f"詳細: https://miharikun.vercel.app/news/{reg_id}"
    )
    return body


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def run_notify(dry_run: bool = False) -> None:
    """未通知の該当マッチを LINE Notify で送信する。"""

    if not _supabase_configured():
        logger.error("SUPABASE_URL または SUPABASE_SERVICE_ROLE_KEY が未設定です。終了します。")
        sys.exit(1)

    matches = fetch_unnotified_matches()
    if not matches:
        logger.info("未通知の該当マッチはありません。終了します。")
        return

    if dry_run:
        logger.info("=== DRY RUN モード: 送信・DB更新をスキップします ===")

    stats = {"sent": 0, "failed": 0, "skipped": 0}

    # regulation / ship_profile のキャッシュ（同一 ID の再取得を防ぐ）
    reg_cache: dict[str, Optional[dict]] = {}
    ship_cache: dict[str, Optional[dict]] = {}

    for i, match in enumerate(matches, 1):
        match_id = match.get("id", "")
        regulation_id = match.get("regulation_id", "")
        ship_profile_id = match.get("ship_profile_id", "")
        confidence = match.get("confidence", 0.0)

        # regulation を取得（キャッシュ有り）
        if regulation_id not in reg_cache:
            reg_cache[regulation_id] = fetch_regulation(regulation_id)
        regulation = reg_cache[regulation_id]

        if not regulation:
            logger.warning(f"[{i}] regulation が見つかりません (id={regulation_id})。スキップ。")
            stats["skipped"] += 1
            continue

        # ship_profile を取得（キャッシュ有り）
        if ship_profile_id not in ship_cache:
            ship_cache[ship_profile_id] = fetch_ship_profile(ship_profile_id)
        ship = ship_cache[ship_profile_id]

        ship_name = ship.get("ship_name", "不明な船舶") if ship else "不明な船舶"

        # メッセージ組み立て
        body = build_message(ship_name, regulation, confidence)
        title = "[MIHARIKUN] 新規該当規制"

        logger.info(f"[{i}/{len(matches)}] {ship_name} × {regulation.get('title', '?')[:40]}")

        if dry_run:
            logger.info(f"  [DRY RUN] タイトル: {title}")
            logger.info(f"  [DRY RUN] 本文:\n{body}")
            stats["sent"] += 1
            continue

        # LINE Notify 送信
        success = send_alert(title=title, message=body, severity="critical")

        if success:
            # notified フラグ更新
            if mark_notified(match_id):
                stats["sent"] += 1
                logger.info(f"  送信成功・notified=true に更新")
            else:
                stats["failed"] += 1
                logger.warning(f"  送信成功だが notified 更新失敗")
        else:
            stats["failed"] += 1
            logger.error(f"  LINE 送信失敗")

    # サマリー
    logger.info("=" * 60)
    logger.info("通知処理完了 サマリー:")
    logger.info(f"  送信成功:  {stats['sent']}")
    logger.info(f"  送信失敗:  {stats['failed']}")
    logger.info(f"  スキップ:  {stats['skipped']}")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI エントリポイント
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="未通知の該当規制マッチを LINE Notify で送信する"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="送信・DB更新なし（メッセージをログ出力のみ）",
    )
    args = parser.parse_args()

    logger.info("LINE 通知処理開始")
    if args.dry_run:
        logger.info("モード: DRY RUN")

    run_notify(dry_run=args.dry_run)

    logger.info("LINE 通知処理終了")


if __name__ == "__main__":
    main()
