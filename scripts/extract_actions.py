"""
アクション極限抽出 — 44件の金脈から具体的な対応事項を搾り出す
=================================================================
Gemini API を使い、各規制について
「一級海技士が明日、何を変えるべきか」を具体化する。

処理フロー:
  1. regulations テーブルから MLIT ソースの記事を取得
  2. 各記事に対して Gemini で船側/会社側アクションを抽出
  3. アクションが空の記事は hidden フラグを立てる
  4. 最終レポートを標準出力に出力
"""

import sys
import os
import logging
import time
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

import requests

try:
    from utils.gemini_client import call_gemini_text
except ImportError:
    from gemini_client import call_gemini_text

try:
    from utils.supabase_client import get_supabase_url, get_supabase_headers
except ImportError:
    from supabase_client import get_supabase_url, get_supabase_headers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("extract_actions")

SUPABASE_URL = get_supabase_url()

MIN_INTERVAL = 4.0  # Tier 1: 15 RPM


# ---------------------------------------------------------------------------
# Gemini 呼び出し
# ---------------------------------------------------------------------------

ACTION_PROMPT = """あなたは一級海技士の資格を持つ海事コンサルタントです。
以下の規制情報を読み、**航海士・機関士が明日から具体的に何を変えるべきか**を箇条書きで抽出してください。

## 規制情報
タイトル: {title}
要約: {summary}
カテゴリ: {category}
適用日: {effective_date}

## 抽出ルール
- **抽象的な表現は禁止**。「確認する」「注意する」ではなく、「〇〇チェックリストの△△項目を追加」「□□設備を××年△月までに換装」のように具体化せよ。
- アクションが本当にない場合（情報提供のみ、法的義務変更なし）は、正直に空配列を返せ。
- 「案」「検討中」「将来の予定」のものはアクションなしとせよ。

## 出力（JSON）
```json
{{
  "onboard_actions": [
    "具体的な船側アクション1",
    "具体的な船側アクション2"
  ],
  "shore_actions": [
    "具体的な会社側アクション1（SMS第何章の改訂等）",
    "具体的な会社側アクション2"
  ],
  "sms_chapters": ["該当するISM SMS章番号"],
  "is_actionable": true
}}
```

`is_actionable` は、船側・会社側のいずれかに1つでも具体的アクションがある場合のみ true。

## ★ F-D-H ルール（絶対基準）
アクションは以下の3つのいずれかの実務的変化を伴うものに限定:
- Form（様式）: 第○号様式の変更、記録簿備置義務、証書書換
- Deadline（期限）: ○年○月○日までの完了義務
- Hardware/Budget（金と物）: 設備換装、検査受検、SMS改訂

「理解する」「認識する」「注意する」はアクションではない。除外せよ。
"""


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------


def fetch_articles() -> list[dict]:
    all_rows = []
    offset = 0
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/regulations",
            params={
                "source": "eq.MLIT",
                "select": "id,source_id,title,headline,summary_ja,category,severity,"
                          "effective_date,confidence",
                "order": "published_at.desc.nullslast",
                "limit": "1000",
                "offset": str(offset),
            },
            headers=get_supabase_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            break
        all_rows.extend(rows)
        offset += 1000
        if len(rows) < 1000:
            break
    return all_rows


def update_actions(reg_id: str, actions: dict) -> bool:
    try:
        resp = requests.patch(
            f"{SUPABASE_URL}/rest/v1/regulations",
            params={"id": f"eq.{reg_id}"},
            json={
                "onboard_actions": actions.get("onboard_actions") or [],
                "shore_actions": actions.get("shore_actions") or [],
                "sms_chapters": actions.get("sms_chapters") or [],
            },
            headers={**get_supabase_headers(), "Prefer": "return=minimal"},
            timeout=15,
        )
        return resp.status_code < 300
    except Exception as e:
        logger.error(f"Update failed for {reg_id}: {e}")
        return False


def hide_article(reg_id: str) -> bool:
    """アクションなしの記事を needs_review=true にマーク"""
    try:
        resp = requests.patch(
            f"{SUPABASE_URL}/rest/v1/regulations",
            params={"id": f"eq.{reg_id}"},
            json={"needs_review": True},
            headers={**get_supabase_headers(), "Prefer": "return=minimal"},
            timeout=15,
        )
        return resp.status_code < 300
    except Exception as e:
        logger.error(f"Hide failed for {reg_id}: {e}")
        return False


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    articles = fetch_articles()
    logger.info(f"取得記事数: {len(articles)}")

    if args.limit:
        articles = articles[:args.limit]
        logger.info(f"制限適用: {args.limit}件")

    actionable = []
    non_actionable = []
    errors = []

    for i, art in enumerate(articles, 1):
        title = art.get("headline") or art.get("title") or "(タイトルなし)"
        summary = art.get("summary_ja") or "(要約なし)"
        category = art.get("category") or ""
        effective = art.get("effective_date") or "不明"
        reg_id = art.get("id")

        logger.info(f"[{i}/{len(articles)}] {title[:50]}")

        prompt = ACTION_PROMPT.format(
            title=title,
            summary=summary[:500],
            category=category,
            effective_date=effective,
        )

        result = call_gemini_text(prompt)
        time.sleep(MIN_INTERVAL)

        if result is None:
            errors.append(art)
            logger.warning(f"  Gemini抽出失敗")
            continue

        onboard = result.get("onboard_actions") or []
        shore = result.get("shore_actions") or []
        is_actionable = result.get("is_actionable", bool(onboard or shore))

        if is_actionable and (onboard or shore):
            actionable.append({
                "id": reg_id,
                "title": title,
                "summary": summary[:200],
                "onboard_actions": onboard,
                "shore_actions": shore,
                "sms_chapters": result.get("sms_chapters") or [],
                "severity": art.get("severity"),
                "effective_date": effective,
            })
            logger.info(f"  ✅ アクションあり: 船側={len(onboard)}, 会社側={len(shore)}")
            if not args.dry_run:
                update_actions(reg_id, result)
        else:
            non_actionable.append(art)
            logger.info(f"  ❌ アクションなし → hidden")
            if not args.dry_run:
                hide_article(reg_id)

    # サマリー
    logger.info("=" * 60)
    logger.info(f"処理完了:")
    logger.info(f"  アクションあり: {len(actionable)}")
    logger.info(f"  アクションなし: {len(non_actionable)} (hidden)")
    logger.info(f"  エラー: {len(errors)}")

    # レポート出力
    print(f"# MIHARIKUN 蒸留レポート — Phase 1 最終着岸")
    print(f"> 生成日: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"> 元データ: 453件 → 蒸留後: {len(actionable)}件（アクションあり）")
    print()
    print(f"## サマリー")
    print(f"- アクションあり: **{len(actionable)}件**")
    print(f"- アクションなし（hidden）: {len(non_actionable)}件")
    print(f"- エラー: {len(errors)}件")
    print()
    print("---")
    print()

    for i, a in enumerate(actionable, 1):
        print(f"## {i}. [{a['severity']}] {a['title']}")
        if a['effective_date'] and a['effective_date'] != '不明':
            print(f"適用日: {a['effective_date']}")
        print()
        print(f"**要約**: {a['summary']}")
        print()
        if a['onboard_actions']:
            print("**船側対応（Ship-side）:**")
            for act in a['onboard_actions']:
                print(f"- {act}")
            print()
        if a['shore_actions']:
            print("**会社側対応（Company-side）:**")
            for act in a['shore_actions']:
                print(f"- {act}")
            print()
        if a['sms_chapters']:
            print(f"**SMS章**: {', '.join(a['sms_chapters'])}")
            print()
        print("---")
        print()


if __name__ == "__main__":
    main()
