"""
常設ページの強制取り込み + 深層再解析
=====================================
RSS に出ない「制度の深層ページ」を URL 指定で直接取り込む。
PDF をダウンロードし、Gemini で事実ベースの解析を行い、DB に保存する。

使い方:
  python force_ingest.py --url https://www.mlit.go.jp/maritime/maritime_fr4_000055.html
  python force_ingest.py --dry-run
"""

import sys
import os
import json
import logging
import time
import argparse
from datetime import datetime, timezone
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(__file__))

import requests
from bs4 import BeautifulSoup

try:
    from utils.gemini_client import call_gemini_text, download_and_extract_pdf_text, SELF_CRITIQUE_PROMPT
except ImportError:
    from gemini_client import call_gemini_text, download_and_extract_pdf_text, SELF_CRITIQUE_PROMPT

try:
    from utils.supabase_client import get_supabase_url, get_supabase_headers
except ImportError:
    from supabase_client import get_supabase_url, get_supabase_headers

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("force_ingest")

SUPABASE_URL = get_supabase_url()
USER_AGENT = "MaritimeRegsMonitor/0.3"

# デフォルト: 基本訓練 + 主要施策ページ
DEFAULT_URLS = [
    "https://www.mlit.go.jp/maritime/maritime_fr4_000055.html",  # 基本訓練
]


def fetch_page(url: str) -> str | None:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.error(f"ページ取得失敗: {url} — {e}")
        return None


def extract_pdfs(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    pdfs = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            full_url = urljoin(base_url, href)
            if full_url not in seen:
                seen.add(full_url)
                pdfs.append({"url": full_url, "text": a.get_text(strip=True)})
    return pdfs


def extract_page_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    title = soup.find("title")
    if title:
        return title.get_text(strip=True)
    return ""


# プロンプトとGemini呼び出し、PDF抽出は utils/gemini_client.py に統合済み
# SELF_CRITIQUE_PROMPT + call_gemini_text + download_and_extract_pdf_text を使用


def upsert_regulation(record: dict) -> bool:
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/regulations",
            json=record,
            headers={**get_supabase_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            timeout=15,
        )
        if resp.status_code >= 300:
            logger.error(f"DB upsert HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.status_code < 300
    except Exception as e:
        logger.error(f"DB upsert 例外: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", nargs="*", default=DEFAULT_URLS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    results = []
    counter = 0

    for page_url in args.url:
        logger.info(f"=== ページ取り込み: {page_url} ===")
        html = fetch_page(page_url)
        if not html:
            continue

        page_title = extract_page_title(html)
        pdfs = extract_pdfs(html, page_url)
        logger.info(f"  タイトル: {page_title}")
        logger.info(f"  PDF リンク: {len(pdfs)}件")

        for pdf in pdfs:
            counter += 1
            pdf_text = download_and_extract_pdf_text(pdf["url"])
            if not pdf_text or len(pdf_text.strip()) < 50:
                logger.info(f"  [{counter}] スキップ（テキスト不足）: {pdf['text'][:40]}")
                continue

            logger.info(f"  [{counter}] 解析中: {pdf['text'][:40]} ({len(pdf_text)}文字)")

            prompt = SELF_CRITIQUE_PROMPT.format(
                pdf_text=pdf_text,
                page_title=f"{page_title} / {pdf['text']}",
            )
            result = call_gemini_text(prompt)
            time.sleep(4)

            if not result:
                logger.warning(f"  [{counter}] Gemini 解析失敗")
                continue

            # Self-Critique 構造対応: final_* を優先
            onboard = result.get("final_onboard_actions") or result.get("onboard_actions") or []
            shore = result.get("final_shore_actions") or result.get("shore_actions") or []

            critique = result.get("self_critique_log", "")
            if critique:
                logger.info(f"  [Self-Critique] {critique[:120]}")

            if not result.get("is_actionable") and not onboard and not shore:
                logger.info(f"  [{counter}] アクションなし → スキップ")
                continue

            source_id = f"MLIT-INGEST-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{counter:03d}"
            record = {
                "source_id": source_id,
                "source": "MLIT",
                "title": pdf["text"] or pdf["url"].split("/")[-1],
                "headline": result.get("title_ja", ""),
                "summary_ja": result.get("summary_ja", ""),
                "url": page_url,
                "pdf_url": pdf["url"],
                "category": result.get("category", ""),
                "severity": result.get("severity", "informational"),
                "effective_date": result.get("effective_date"),
                "onboard_actions": onboard,
                "shore_actions": shore,
                "sms_chapters": result.get("sms_chapters") or [],
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }

            if not args.dry_run:
                success = upsert_regulation(record)
                logger.info(f"  [{counter}] {'✅ DB保存成功' if success else '❌ DB保存失敗'}: {result.get('title_ja', '')[:40]}")
            else:
                logger.info(f"  [{counter}] [dry-run] {result.get('title_ja', '')[:40]}")

            results.append({
                "title": result.get("title_ja", ""),
                "legal_basis": result.get("legal_basis"),
                "effective_date": result.get("effective_date"),
                "onboard_actions": onboard,
                "shore_actions": shore,
                "severity": result.get("severity"),
                "summary": result.get("summary_ja", "")[:200],
            })

    # レポート出力
    print(f"# 常設ページ強制取り込みレポート")
    print(f"> 生成日: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"> 取り込み: {len(results)}件")
    print()
    for i, r in enumerate(results, 1):
        print(f"## {i}. [{r['severity']}] {r['title']}")
        if r.get("legal_basis"):
            print(f"法的根拠: {r['legal_basis']}")
        if r.get("effective_date"):
            print(f"適用日: {r['effective_date']}")
        print(f"\n**要約**: {r['summary']}\n")
        if r["onboard_actions"]:
            print("**船側対応:**")
            for a in r["onboard_actions"]:
                print(f"- {a}")
            print()
        if r["shore_actions"]:
            print("**会社側対応:**")
            for a in r["shore_actions"]:
                print(f"- {a}")
            print()
        print("---\n")


if __name__ == "__main__":
    main()
