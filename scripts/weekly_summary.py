"""
週次サマリー生成スクリプト — ユーザーごとの該当規制レポートを生成
=================================================================
GHA から毎週月曜に実行し、各ユーザーの登録船舶に対する
直近 7 日間の該当規制をまとめたサマリーを生成する。

サマリーは Resend API（Next.js API Route 経由）でメール送信可能。
SUMMARY_API_KEY が設定されていない場合はログ出力のみ（従来動作）。

使い方:
    python weekly_summary.py             # 通常実行（サマリー生成＋メール送信）
    python weekly_summary.py --dry-run   # DB アクセスのみ、送信処理なし
"""

import argparse
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# scripts/ 内の utils/ を import 可能にする
sys.path.insert(0, os.path.dirname(__file__))

import requests

try:
    from utils.supabase_client import get_supabase_url, get_supabase_headers
except ImportError:
    from supabase_client import get_supabase_url, get_supabase_headers

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger("weekly_summary")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[Summary] %(levelname)s: %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Supabase REST API ヘルパー
# ---------------------------------------------------------------------------

SUPABASE_URL: str = get_supabase_url()
_BASE_URL: str = os.environ.get("MIHARIKUN_BASE_URL", "https://miharikun2.vercel.app")

# メール送信設定
RESEND_API_URL: str = os.environ.get(
    "RESEND_API_URL",
    f"{_BASE_URL}/api/send-summary",
)
SUMMARY_API_KEY: str = os.environ.get("SUMMARY_API_KEY", "")
# TODO: auth.users から取得する仕組みに置き換える
NOTIFY_EMAIL: str = os.environ.get("NOTIFY_EMAIL", "")


def _supabase_configured() -> bool:
    return bool(SUPABASE_URL and get_supabase_headers().get("apikey"))


def fetch_all_paginated(
    table: str,
    select: str = "*",
    extra_params: Optional[dict] = None,
) -> list[dict]:
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
            headers=get_supabase_headers(),
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


# ---------------------------------------------------------------------------
# データ取得
# ---------------------------------------------------------------------------

def fetch_ship_profiles() -> list[dict]:
    """ship_profiles テーブルから全行を取得"""
    logger.info("ship_profiles を取得中...")
    profiles = fetch_all_paginated("ship_profiles")
    logger.info(f"ship_profiles: {len(profiles)} 件取得")
    return profiles


def fetch_recent_matches(since_iso: str) -> list[dict]:
    """
    user_matches テーブルから、指定日時以降の is_applicable=true のレコードを取得。
    regulation の情報も結合して取得する。
    """
    logger.info(f"直近の該当マッチを取得中 (since={since_iso})...")
    rows = fetch_all_paginated(
        "user_matches",
        select="*,regulations(*)",
        extra_params={
            "is_applicable": "eq.true",
            "created_at": f"gte.{since_iso}",
            "order": "created_at.desc",
        },
    )
    logger.info(f"該当マッチ: {len(rows)} 件取得")
    return rows


# ---------------------------------------------------------------------------
# メール送信
# ---------------------------------------------------------------------------

MIHARIKUN_BASE_URL: str = _BASE_URL


def _email_configured() -> bool:
    """メール送信に必要な設定が揃っているか判定"""
    return bool(SUMMARY_API_KEY and NOTIFY_EMAIL)


def build_email_payload(
    to: str,
    ships: list[dict],
    matches: list[dict],
    date_from: datetime,
    date_to: datetime,
) -> dict[str, Any]:
    """
    API Route `/api/send-summary` が期待する JSON ペイロードを組み立てる。

    Args:
        to: 送信先メールアドレス
        ships: ユーザーの ship_profiles リスト
        matches: ユーザーの user_matches リスト（regulations 結合済み）
        date_from: 集計開始日
        date_to: 集計終了日

    Returns:
        API に POST する dict
    """
    date_range = f"{date_from.strftime('%Y-%m-%d')} 〜 {date_to.strftime('%Y-%m-%d')}"

    # ship_profile_id ごとにマッチをグループ化
    matches_by_ship: dict[str, list[dict]] = defaultdict(list)
    for m in matches:
        ship_id = m.get("ship_profile_id", "")
        matches_by_ship[ship_id].append(m)

    ship_summaries: list[dict[str, Any]] = []
    for ship in ships:
        ship_id = ship["id"]
        ship_matches = matches_by_ship.get(ship_id, [])

        regulations: list[dict[str, Any]] = []
        for m in ship_matches:
            reg = m.get("regulations") or {}
            reg_id = reg.get("id", "")
            regulations.append({
                "title": reg.get("title", "タイトル不明"),
                "severity": reg.get("severity", "info"),
                "confidence": float(m.get("confidence", 0.0)),
                "reason": m.get("reason", ""),
                "url": f"{MIHARIKUN_BASE_URL}/news/{reg_id}" if reg_id else "",
            })

        ship_summaries.append({
            "shipName": ship.get("ship_name", "不明"),
            "shipType": ship.get("ship_type", "unknown"),
            "grossTonnage": ship.get("gross_tonnage", 0),
            "regulations": regulations,
        })

    return {
        "to": to,
        "dateRange": date_range,
        "ships": ship_summaries,
    }


def send_summary_email(payload: dict[str, Any]) -> bool:
    """
    Next.js API Route にサマリーメール送信リクエストを POST する。

    Returns:
        True: 送信成功, False: 送信失敗
    """
    try:
        resp = requests.post(
            RESEND_API_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": SUMMARY_API_KEY,
            },
            timeout=30,
        )
        if resp.ok:
            data = resp.json()
            logger.info(f"メール送信成功: {data}")
            return True
        else:
            logger.error(
                f"メール送信失敗: HTTP {resp.status_code} — {resp.text}"
            )
            return False
    except requests.RequestException as e:
        logger.error(f"メール送信リクエストエラー: {e}")
        return False


# ---------------------------------------------------------------------------
# サマリー生成
# ---------------------------------------------------------------------------

def generate_user_summary(
    user_id: str,
    ships: list[dict],
    matches: list[dict],
    date_from: datetime,
    date_to: datetime,
) -> str:
    """
    1 ユーザー分のプレーンテキストサマリーを生成する。

    Args:
        user_id: ユーザー ID
        ships: そのユーザーの ship_profiles リスト
        matches: そのユーザーの user_matches リスト（regulations 結合済み）
        date_from: 集計開始日
        date_to: 集計終了日

    Returns:
        プレーンテキストのサマリー文字列
    """
    date_from_str = date_from.strftime("%Y/%m/%d")
    date_to_str = date_to.strftime("%Y/%m/%d")

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(f"MIHARIKUN 週次サマリー ({date_from_str} - {date_to_str})")
    lines.append("=" * 60)
    lines.append("")

    # ship_profile_id -> ship 情報のマッピング
    ship_map: dict[str, dict] = {s["id"]: s for s in ships}

    # ship_profile_id ごとにマッチをグループ化
    matches_by_ship: dict[str, list[dict]] = defaultdict(list)
    for m in matches:
        ship_id = m.get("ship_profile_id", "")
        matches_by_ship[ship_id].append(m)

    total_count = 0

    for ship in ships:
        ship_id = ship["id"]
        ship_name = ship.get("ship_name", "不明")
        ship_matches = matches_by_ship.get(ship_id, [])

        lines.append(f"--- {ship_name} ---")

        if not ship_matches:
            lines.append("  該当する新規規制はありませんでした。")
            lines.append("")
            continue

        for idx, m in enumerate(ship_matches, 1):
            reg = m.get("regulations") or {}
            title = reg.get("title", "タイトル不明")
            severity = reg.get("severity", "-")
            confidence = m.get("confidence", 0.0)
            reason = m.get("reason", "")
            source = reg.get("source", "")
            source_id = reg.get("source_id", "")

            lines.append(f"  [{idx}] {title}")
            lines.append(f"      出典: {source} / {source_id}")
            lines.append(f"      重要度: {severity}  |  確信度: {confidence:.0%}")
            if reason:
                lines.append(f"      理由: {reason}")
            lines.append("")
            total_count += 1

    lines.append("-" * 60)
    lines.append(f"合計: {total_count} 件の該当規制")
    lines.append("")
    lines.append(
        "※ 本サービスはAIによる参考情報の提供を目的としており、"
        "法的助言を構成するものではありません。"
        "規制の正確な内容については、必ず原文をご確認ください。"
    )
    lines.append("=" * 60)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def run_weekly_summary(dry_run: bool = False) -> None:
    """週次サマリーのメインロジック"""

    if not _supabase_configured():
        logger.error("SUPABASE_URL または SUPABASE_SERVICE_ROLE_KEY が未設定です。終了します。")
        sys.exit(1)

    # 1. 集計期間を計算（直近 7 日間）
    now = datetime.now(timezone.utc)
    date_from = now - timedelta(days=7)
    since_iso = date_from.isoformat()

    logger.info(f"集計期間: {date_from.strftime('%Y/%m/%d')} - {now.strftime('%Y/%m/%d')}")

    # 2. ship_profiles を取得してユーザーごとにグループ化
    ship_profiles = fetch_ship_profiles()
    if not ship_profiles:
        logger.warning("ship_profiles が 0 件です。サマリー対象がないため終了します。")
        return

    ships_by_user: dict[str, list[dict]] = defaultdict(list)
    for ship in ship_profiles:
        user_id = ship.get("user_id")
        if user_id:
            ships_by_user[user_id].append(ship)

    logger.info(f"対象ユーザー: {len(ships_by_user)} 名")

    # 3. 直近 7 日間の該当マッチを取得
    recent_matches = fetch_recent_matches(since_iso)

    # user_id ごとにマッチをグループ化
    # user_matches には user_id がないため、ship_profile_id 経由で紐付ける
    ship_to_user: dict[str, str] = {}
    for ship in ship_profiles:
        ship_id = ship.get("id")
        user_id = ship.get("user_id")
        if ship_id and user_id:
            ship_to_user[ship_id] = user_id

    matches_by_user: dict[str, list[dict]] = defaultdict(list)
    for m in recent_matches:
        ship_id = m.get("ship_profile_id", "")
        user_id = ship_to_user.get(ship_id)
        if user_id:
            matches_by_user[user_id].append(m)

    # 4. ユーザーごとにサマリーを生成・送信
    summary_count = 0
    email_sent_count = 0
    can_send_email = _email_configured() and not dry_run

    if not _email_configured():
        logger.info(
            "SUMMARY_API_KEY または NOTIFY_EMAIL が未設定のため、"
            "メール送信はスキップします（ログ出力のみ）"
        )

    for user_id, ships in ships_by_user.items():
        user_matches = matches_by_user.get(user_id, [])

        # テキストサマリー生成（ログ出力用）
        summary = generate_user_summary(
            user_id=user_id,
            ships=ships,
            matches=user_matches,
            date_from=date_from,
            date_to=now,
        )

        match_count = len(user_matches)
        logger.info(
            f"ユーザー {user_id}: 船舶 {len(ships)} 隻, "
            f"該当規制 {match_count} 件"
        )

        # テキストサマリーを常にログ出力
        print(summary)
        print()

        if dry_run:
            logger.info("[DRY RUN] サマリー生成のみ（送信なし）")
        elif can_send_email:
            # メールペイロードを構築して送信
            payload = build_email_payload(
                to=NOTIFY_EMAIL,
                ships=ships,
                matches=user_matches,
                date_from=date_from,
                date_to=now,
            )
            logger.info(
                f"メール送信中: {NOTIFY_EMAIL} "
                f"(ships={len(payload['ships'])})"
            )
            if send_summary_email(payload):
                email_sent_count += 1

        summary_count += 1

    # 5. 完了サマリー
    logger.info("=" * 60)
    logger.info("週次サマリー生成完了:")
    logger.info(f"  対象ユーザー数: {summary_count}")
    logger.info(f"  該当マッチ総数: {len(recent_matches)}")
    logger.info(f"  メール送信数: {email_sent_count}")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI エントリポイント
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="週次サマリー: ユーザーごとの該当規制レポートを生成"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="サマリー生成のみ（送信処理なし）",
    )
    args = parser.parse_args()

    logger.info("週次サマリー生成開始")
    if args.dry_run:
        logger.info("モード: DRY RUN")

    run_weekly_summary(dry_run=args.dry_run)

    logger.info("週次サマリー生成終了")


if __name__ == "__main__":
    main()
