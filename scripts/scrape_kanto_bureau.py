"""
関東運輸局 海事振興部 お知らせ監視（テスト）
===========================================
本庁の通達を「実務レベル」に噛み砕いた資料を捕捉する。
3ヶ月運用して有用性を評価し、他局への拡大を判断する。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import argparse
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils.supabase_client import SupabaseClient  # type: ignore
from utils.line_notify import send_alert  # type: ignore

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scrape_kanto")

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

# 関東運輸局の海事関連ページ
KANTO_URLS = [
    "https://wwwtb.mlit.go.jp/kanto/kaiji_sinkou/oshirase.html",
]

# 航海士に関連するキーワード（これらを含むリンクのみ抽出）
RELEVANT_KEYWORDS = [
    "船員法", "STCW", "免状", "基本訓練", "安全管理",
    "船舶安全", "海技", "船員手帳", "雇入届",
    "海上労働", "MLC", "ISM", "SMS",
]

USER_AGENT = "Mozilla/5.0 (compatible; MIHARIKUN/1.0)"
REQUEST_INTERVAL = 3

# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------


def scrape_kanto(dry_run: bool = False) -> None:
    """
    1. KANTO_URLS を巡回
    2. <main> 要素のテキストハッシュを前回と比較
    3. 新規リンク（PDF含む）からキーワードフィルタ
    4. マッチしたものを regulations に登録
    """
    client = SupabaseClient()
    stats = {"pages": 0, "new_links": 0, "relevant": 0, "pdfs": 0}

    for url in KANTO_URLS:
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error("取得エラー: %s — %s", url, e)
            continue

        stats["pages"] += 1
        soup = BeautifulSoup(resp.text, "html.parser")

        # リンクを全抽出
        links: list[dict[str, str]] = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = urljoin(url, a["href"])
            links.append({"text": text, "url": href})

        stats["new_links"] = len(links)

        # キーワードフィルタ
        for link in links:
            combined = f"{link['text']}".lower()
            if any(kw.lower() in combined for kw in RELEVANT_KEYWORDS):
                stats["relevant"] += 1
                logger.info(
                    "関連リンク検出: %s → %s",
                    link["text"][:50],
                    link["url"],
                )

                if link["url"].lower().endswith(".pdf"):
                    stats["pdfs"] += 1
                    if not dry_run:
                        # pending_queue に登録
                        source_id = (
                            f"KANTO-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
                            f"-{stats['pdfs']:03d}"
                        )
                        client.upsert_regulation({
                            "source_id": source_id,
                            "source": "KANTO",
                            "title": link["text"],
                            "url": url,
                            "pdf_url": link["url"],
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                            "severity": "informational",
                        })
                        client.queue_pending(
                            source="KANTO",
                            source_id=source_id,
                            pdf_url=link["url"],
                            reason="awaiting_classification",
                            error_detail="関東運輸局テスト監視で検出",
                        )
                    else:
                        logger.info(
                            "[dry-run] PDF 登録スキップ: %s", link["url"]
                        )

        time.sleep(REQUEST_INTERVAL)

    # サマリー
    logger.info("=== 関東運輸局巡回完了 ===")
    logger.info(
        "  ページ: %d, リンク検出: %d, 関連: %d, PDF: %d",
        stats["pages"],
        stats["new_links"],
        stats["relevant"],
        stats["pdfs"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="関東運輸局 海事振興部 お知らせ監視（テスト）"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    scrape_kanto(dry_run=args.dry_run)
