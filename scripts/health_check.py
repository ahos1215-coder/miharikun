"""
ヘルスチェックスクリプト
========================
各データソースの鮮度、pending_queue の滞留状況を検査し、
問題があれば LINE Notify で通知する。

Usage:
    python health_check.py [--stale-days 7] [--pending-threshold 10]
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from utils.supabase_client import SupabaseClient
from utils.line_notify import send_alert, send_health_check_report

# ---------------------------------------------------------------------------
# ロガー
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="[HealthCheck] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 検査対象ソース
# ---------------------------------------------------------------------------
SOURCES = [
    {"name": "nk", "expected_interval_days": 7},
    {"name": "mlit", "expected_interval_days": 14},
]


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------
def run_health_check(
    stale_days: int = 7,
    pending_threshold: int = 10,
) -> dict:
    """
    ヘルスチェックを実行する。

    Returns:
        {
            "status": "ok" | "warning" | "critical",
            "sources": [...],
            "pending_count": int,
            "issues": [str],
        }
    """
    client = SupabaseClient()
    issues: list[str] = []
    source_reports: list[dict] = []

    # 1. ソース別鮮度チェック
    for src in SOURCES:
        name = src["name"]
        expected = src["expected_interval_days"]
        health = client.check_source_health(name, days=expected)

        report = {
            "name": name,
            "last_scraped": health.get("last_scraped", "なし"),
            "days_since": health.get("days_since", -1),
            "status": health.get("status", "unknown"),
        }
        source_reports.append(report)

        if health["status"] == "stale":
            days = health.get("days_since", "?")
            issues.append(f"{name}: {days}日間更新なし（閾値: {expected}日）")
            logger.warning(f"STALE: {name} — {days}日間更新なし")
        elif health["status"] == "unknown":
            issues.append(f"{name}: データなしまたは接続失敗")
            logger.warning(f"UNKNOWN: {name} — データなしまたは接続失敗")
        else:
            logger.info(f"OK: {name} — {health.get('days_since', 0)}日前に最終取得")

    # 2. pending_queue 滞留チェック
    pending = client.get_pending_queue()
    pending_count = len(pending)
    logger.info(f"pending_queue: {pending_count} 件")

    if pending_count >= pending_threshold:
        issues.append(f"pending_queue: {pending_count} 件滞留（閾値: {pending_threshold}件）")

    # リトライ上限に達したアイテムをカウント
    max_retry_items = [p for p in pending if p.get("retry_count", 0) >= 2]
    if max_retry_items:
        issues.append(f"リトライ上限間近: {len(max_retry_items)} 件")

    # 3. 総合判定
    if any("CRITICAL" in issue.upper() for issue in issues):
        overall_status = "critical"
    elif issues:
        overall_status = "warning"
    else:
        overall_status = "ok"

    return {
        "status": overall_status,
        "sources": source_reports,
        "pending_count": pending_count,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="データソースヘルスチェック")
    parser.add_argument("--stale-days", type=int, default=7,
                        help="データが古いと判定する日数")
    parser.add_argument("--pending-threshold", type=int, default=10,
                        help="pending_queue 警告の閾値")
    parser.add_argument("--json-output", action="store_true",
                        help="結果を JSON で標準出力")
    args = parser.parse_args()

    logger.info(f"開始: stale_days={args.stale_days}, pending_threshold={args.pending_threshold}")

    result = run_health_check(
        stale_days=args.stale_days,
        pending_threshold=args.pending_threshold,
    )

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    logger.info(f"結果: status={result['status']}, issues={len(result['issues'])}")

    # LINE 通知
    if result["status"] != "ok":
        send_health_check_report(result)
        for issue in result["issues"]:
            logger.warning(f"ISSUE: {issue}")
    else:
        logger.info("全ソース正常")
        # 正常時も週次で報告（GHA cron が週次なので毎回送信）
        send_health_check_report(result)

    # CI 用: critical なら exit code 1
    if result["status"] == "critical":
        sys.exit(1)


if __name__ == "__main__":
    main()
