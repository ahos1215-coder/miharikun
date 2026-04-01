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
import json
import logging
import time
import re
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

import requests

try:
    from utils.gemini_config import (
        DEFAULT_PRIMARY_MODEL,
        GEMINI_API_BASE,
        GEMINI_API_KEY,
        MAX_RETRIES,
        BASE_WAIT,
        MAX_WAIT,
    )
except ImportError:
    DEFAULT_PRIMARY_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    MAX_RETRIES = 6
    BASE_WAIT = 1.0
    MAX_WAIT = 32.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("deep_reanalyze")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
API_KEY = os.environ.get("GEMINI_API_KEY", "") or GEMINI_API_KEY
MODEL = os.environ.get("GEMINI_MODEL", DEFAULT_PRIMARY_MODEL)

MIN_INTERVAL = 4.0
USER_AGENT = "MaritimeRegsMonitor/0.3 (+https://github.com/ahos1215-coder)"


# ---------------------------------------------------------------------------
# PDF テキスト抽出（PyMuPDF 使用）
# ---------------------------------------------------------------------------

def download_pdf_text(pdf_url: str) -> str | None:
    """PDF をダウンロードしてテキストを抽出する。"""
    try:
        resp = requests.get(
            pdf_url,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        pdf_bytes = resp.content

        # PyMuPDF でテキスト抽出
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            full_text = "\n".join(text_parts)
            # 最大 8000 文字（Gemini のコンテキスト節約）
            return full_text[:8000] if full_text.strip() else None
        except ImportError:
            logger.warning("PyMuPDF (fitz) がインストールされていません。要約のみで再解析します。")
            return None
        except Exception as e:
            logger.warning(f"PDF テキスト抽出エラー: {pdf_url} — {e}")
            return None
    except Exception as e:
        logger.warning(f"PDF ダウンロードエラー: {pdf_url} — {e}")
        return None


# ---------------------------------------------------------------------------
# Gemini 呼び出し
# ---------------------------------------------------------------------------

REANALYZE_PROMPT = """あなたは一級海技士の資格を持つ海事規制の専門家です。
以下の「PDF本文テキスト」を読み、**本文に書いてある事実のみに基づいて**情報を構造化してください。

## ★ 最重要ルール（違反したら即失格）
1. **テンプレ推論は絶対禁止**。PDF に書いていないことは一切推測しない。
2. アクションは **PDF 本文に具体的な手順や義務が記載されている場合のみ** 記載する。
3. 記載がない場合は「（該当文書に具体的な手順の記載なし）」と正直に書く。
4. 「油記録簿」「SOPEP」等、**本文に一切登場しないキーワード** を勝手に追加しない。

## PDF 本文テキスト
{pdf_text}

## 既存の要約（参考のみ、PDF本文が優先）
{existing_summary}

## 出力（JSON、コードブロックで囲む）
```json
{{
  "title_ja": "この文書の内容を1行で表す日本語タイトル（例: EEXI規制に伴う機関出力制限の認証手続き）",
  "summary_ja": "背景・目的・具体的数値を含む要約（200-400字）。PDF本文の事実のみ記載。",
  "legal_basis": "適用条約・法令（MARPOL附属書VI第X規則 等、可能な限り条文レベルで特定）。PDF本文に記載がなければ null",
  "effective_date": "施行日・適用日（YYYY-MM-DD形式）。PDF本文に記載がなければ null",
  "onboard_actions": [
    "PDF本文に記載された船側の具体的アクション（チェックリスト・設備・記録簿等）",
    "記載がなければ空配列"
  ],
  "shore_actions": [
    "PDF本文に記載された会社側の具体的アクション（SMS・証書・申請等）",
    "記載がなければ空配列"
  ],
  "sms_chapters": ["該当するISM SMS章番号。記載がなければ空配列"],
  "is_actionable": true,
  "confidence_note": "この解析の確信度に関する注記（テキスト抽出が不完全だった場合等）"
}}
```
"""

REANALYZE_PROMPT_NO_PDF = """あなたは一級海技士の資格を持つ海事規制の専門家です。
以下の「既存の要約」を読み、**要約に書いてある事実のみに基づいて**情報を再構造化してください。

## ★ 最重要ルール
1. **テンプレ推論は絶対禁止**。要約に書いていないことは一切推測しない。
2. アクションは **要約に具体的な手順や義務が記載されている場合のみ** 記載。
3. 記載がない場合は空配列を返す。適当なテンプレを埋めない。

## 既存の要約
{existing_summary}

## タイトル
{title}

## 出力（JSON、コードブロックで囲む）
```json
{{
  "title_ja": "内容を1行で表す日本語タイトル",
  "summary_ja": "背景・目的・具体的数値を含む要約（200-400字）",
  "legal_basis": "適用条約・法令。記載がなければ null",
  "effective_date": "施行日。記載がなければ null",
  "onboard_actions": ["具体的な船側アクション。なければ空配列"],
  "shore_actions": ["具体的な会社側アクション。なければ空配列"],
  "sms_chapters": [],
  "is_actionable": true,
  "confidence_note": "PDF本文を取得できなかったため、既存要約からの再構造化"
}}
```
"""


def call_gemini(prompt: str) -> dict | None:
    url = f"{GEMINI_API_BASE}/{MODEL}:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1},
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, timeout=90)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
                if match:
                    return json.loads(match.group(1))
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                logger.warning("JSON not found in response")
                return None
            elif resp.status_code == 429:
                wait = min(BASE_WAIT * (2 ** attempt), MAX_WAIT)
                logger.warning(f"429 Rate limit. Waiting {wait}s...")
                time.sleep(wait)
                continue
            else:
                logger.error(f"Gemini HTTP {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return None
    return None


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

def _headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


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
            headers=_headers(),
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
            headers={**_headers(), "Prefer": "return=minimal"},
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
            headers={**_headers(), "Prefer": "return=minimal"},
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
            pdf_text = download_pdf_text(pdf_url)
            if pdf_text:
                logger.info(f"  PDF テキスト取得成功: {len(pdf_text)}文字")

        # プロンプト構築
        if pdf_text:
            prompt = REANALYZE_PROMPT.format(
                pdf_text=pdf_text,
                existing_summary=summary[:500],
            )
        else:
            prompt = REANALYZE_PROMPT_NO_PDF.format(
                existing_summary=summary[:500],
                title=title,
            )

        result = call_gemini(prompt)
        time.sleep(MIN_INTERVAL)

        if result is None:
            errors.append(art)
            logger.warning(f"  Gemini 解析失敗")
            continue

        onboard = result.get("onboard_actions") or []
        shore = result.get("shore_actions") or []
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
