"""
MLIT データの「知能化」— テンプレ推論禁止、100% 事実ベース再解析
================================================================
既存の regulations テーブルの MLIT 記事に対し、
PDF 本文テキストを Gemini に渡して「具体的な事実のみ」を抽出し直す。

処理:
  1. regulations テーブルから MLIT ソースの記事を取得
  2. 各記事の pdf_url から PDF をダウンロード → テキスト抽出
  3. Gemini に PDF 本文を渡して事実ベースの再解析
  4. DB を更新（タイトル/要約/アクション/適用条約）
  5. 最終レポートを出力
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
    from utils.gemini_client import call_gemini_text, download_and_extract_pdf_text, SELF_CRITIQUE_PROMPT
except ImportError:
    from gemini_client import call_gemini_text, download_and_extract_pdf_text, SELF_CRITIQUE_PROMPT

try:
    from utils.supabase_client import get_supabase_url, get_supabase_headers
except ImportError:
    from supabase_client import get_supabase_url, get_supabase_headers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("deep_reanalyze")

SUPABASE_URL = get_supabase_url()

MIN_INTERVAL = 4.0


def fetch_articles() -> list[dict]:
    all_rows = []
    offset = 0
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/regulations",
            params={
                "source": "eq.MLIT",
                "needs_review": "eq.false",
                "select": "id,source_id,title,headline,summary_ja,category,severity,"
                          "effective_date,confidence,pdf_url,url",
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


def update_article(reg_id: str, data: dict) -> bool:
    update_fields: dict = {}
    if data.get("title_ja"):
        update_fields["headline"] = data["title_ja"]
    if data.get("summary_ja"):
        update_fields["summary_ja"] = data["summary_ja"]
    if data.get("onboard_actions"):
        update_fields["onboard_actions"] = data["onboard_actions"]
    if data.get("shore_actions"):
        update_fields["shore_actions"] = data["shore_actions"]
    if data.get("sms_chapters"):
        update_fields["sms_chapters"] = data["sms_chapters"]
    if data.get("effective_date"):
        update_fields["effective_date"] = data["effective_date"]

    if not update_fields:
        return False

    try:
        resp = requests.patch(
            f"{SUPABASE_URL}/rest/v1/regulations",
            params={"id": f"eq.{reg_id}"},
            json=update_fields,
            headers={**get_supabase_headers(), "Prefer": "return=minimal"},
            timeout=15,
        )
        return resp.status_code < 300
    except Exception as e:
        logger.error(f"Update failed for {reg_id}: {e}")
        return False


def hide_article(reg_id: str) -> bool:
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
    logger.info(f"対象記事数: {len(articles)}")

    if args.limit:
        articles = articles[:args.limit]

    actionable = []
    non_actionable = []
    errors = []

    for i, art in enumerate(articles, 1):
        title = art.get("headline") or art.get("title") or "(タイトルなし)"
        summary = art.get("summary_ja") or ""
        pdf_url = art.get("pdf_url") or ""
        reg_id = art.get("id")

        logger.info(f"[{i}/{len(articles)}] {title[:50]}")

        # PDF テキスト取得を試みる
        pdf_text = None
        if pdf_url:
            pdf_text = download_and_extract_pdf_text(pdf_url)
            if pdf_text:
                logger.info(f"  PDF テキスト取得成功: {len(pdf_text)}文字")

        # プロンプト構築（SELF_CRITIQUE_PROMPT に統一）
        if pdf_text:
            prompt = SELF_CRITIQUE_PROMPT.format(
                pdf_text=pdf_text,
                page_title=title,
            )
        else:
            prompt = SELF_CRITIQUE_PROMPT.format(
                pdf_text=f"(PDF取得不可。以下は既存要約)\n{summary[:500]}",
                page_title=title,
            )

        result = call_gemini_text(prompt)
        time.sleep(MIN_INTERVAL)

        if result is None:
            errors.append(art)
            logger.warning(f"  Gemini 解析失敗")
            continue

        # Self-Critique 構造対応: final_* を優先
        onboard = result.get("final_onboard_actions") or result.get("onboard_actions") or []
        shore = result.get("final_shore_actions") or result.get("shore_actions") or []
        is_actionable = result.get("is_actionable", bool(onboard or shore))

        new_title = result.get("title_ja", title)
        new_summary = result.get("summary_ja", summary)

        if is_actionable and (onboard or shore):
            actionable.append({
                "id": reg_id,
                "title": new_title,
                "summary": new_summary[:300],
                "legal_basis": result.get("legal_basis"),
                "onboard_actions": onboard,
                "shore_actions": shore,
                "sms_chapters": result.get("sms_chapters") or [],
                "severity": art.get("severity"),
                "effective_date": result.get("effective_date") or art.get("effective_date"),
                "confidence_note": result.get("confidence_note", ""),
                "had_pdf": bool(pdf_text),
            })
            logger.info(f"  ✅ {new_title[:40]} — 船側={len(onboard)}, 会社側={len(shore)}")
            if not args.dry_run:
                update_article(reg_id, result)
        else:
            non_actionable.append({"title": new_title, "reason": "アクションなし"})
            logger.info(f"  ❌ アクションなし → hidden")
            if not args.dry_run:
                hide_article(reg_id)

    # レポート出力
    print(f"# MIHARIKUN 蒸留レポート — 事実ベース再解析版")
    print(f"> 生成日: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"> 対象: {len(articles)}件 → アクションあり: {len(actionable)}件")
    print(f"> PDF本文取得: {sum(1 for a in actionable if a['had_pdf'])}件")
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
        if a.get('effective_date'):
            print(f"適用日: {a['effective_date']}")
        if a.get('legal_basis'):
            print(f"法的根拠: {a['legal_basis']}")
        if a.get('confidence_note'):
            print(f"解析注記: {a['confidence_note']}")
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
            print(f"**SMS章**: {', '.join(str(c) for c in a['sms_chapters'])}")
            print()
        print("---")
        print()


if __name__ == "__main__":
    main()
