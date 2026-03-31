"""
国交省（MLIT）海事局 ウェブクロール — 第 2 層
==============================================
`mlit.go.jp/maritime/` 配下を BFS（幅優先探索）でクロールし、
ページハッシュの差分から新規・更新コンテンツを検出する。

処理フロー:
  1) 起点 URL から BFS でリンクをたどる（深さ・ページ数制限あり）
  2) 各ページの SHA256 ハッシュを Supabase mlit_crawl_state と比較
  3) 変更ページから PDF リンクを抽出
  4) 新規 PDF を Gemini で分類 → Supabase に保存
  5) クロール状態を mlit_crawl_state テーブルに更新

安全機構:
  - 1 回のクロールで 100+ 新規 URL を検出した場合 → 異常として LINE アラート＆中断
  - リクエスト間隔: 3 秒（サーバー負荷軽減）
  - robots.txt 遵守（urllib.robotparser）
  - HTTP Content-Length / Last-Modified ヘッダーでスキップ判定

使い方:
  python scrape_mlit_crawl.py
  python scrape_mlit_crawl.py --dry-run
  python scrape_mlit_crawl.py --max-pages 50 --depth 2
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# パス設定（スクリプト直下から utils を import）
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(__file__))

from utils.supabase_client import SupabaseClient  # type: ignore
from utils.line_notify import send_alert, send_scraper_error  # type: ignore
from utils.pdf_preprocess import check_pdf_url  # type: ignore
from utils.stealth_fetcher import stealth_get  # type: ignore

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scrape_mlit_crawl")

# ---------------------------------------------------------------------------
# 定数・設定
# ---------------------------------------------------------------------------

# クロール起点
CRAWL_START_URL = "https://www.mlit.go.jp/maritime/"

# URL フィルタ（この文字列を含む URL のみフォロー）
MARITIME_URL_PATTERN = "/maritime/"

# 異常検知：1 回のクロールで新規 URL がこの数を超えたら中断
ANOMALY_NEW_URL_THRESHOLD = 100

# リクエスト間隔（秒）
REQUEST_INTERVAL_SEC = 3

# デフォルト設定
DEFAULT_MAX_PAGES = 100
DEFAULT_CRAWL_DEPTH = 3

USER_AGENT = "MaritimeRegsMonitor/0.1 (+https://github.com/ahos1215-coder)"

SOURCE_PREFIX = "MLIT"

# ---------------------------------------------------------------------------
# robots.txt チェッカー
# ---------------------------------------------------------------------------

class RobotsChecker:
    """robots.txt を尊重するためのヘルパークラス。"""

    def __init__(self, user_agent: str = USER_AGENT):
        self._cache: dict[str, RobotFileParser] = {}
        self._user_agent = user_agent

    def _get_robots_url(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def is_allowed(self, url: str) -> bool:
        """指定 URL のクロールが robots.txt で許可されているか確認する。"""
        robots_url = self._get_robots_url(url)
        if robots_url not in self._cache:
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                parser.read()
                self._cache[robots_url] = parser
                logger.debug("robots.txt 取得完了: %s", robots_url)
            except Exception as e:
                logger.warning("robots.txt 取得エラー: %s — %s", robots_url, e)
                # 取得できない場合はクロール許可と扱う
                return True
        return self._cache[robots_url].can_fetch(self._user_agent, url)


# ---------------------------------------------------------------------------
# ページハッシュ計算
# ---------------------------------------------------------------------------

def compute_page_hash(content: str) -> str:
    """ページコンテンツの SHA256 ハッシュを計算する。"""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


# ---------------------------------------------------------------------------
# Supabase — mlit_crawl_state テーブル操作（直接 REST API を使用）
# ---------------------------------------------------------------------------

def get_crawl_state(client: SupabaseClient, url: str) -> Optional[dict]:
    """
    Supabase から指定 URL のクロール状態を取得する。
    直接 REST API を叩く（SupabaseClient の汎用メソッドを使用）。

    Returns:
        クロール状態の dict（存在しない場合は None）
    """
    if not client._configured:
        return None

    try:
        resp = requests.get(
            f"{client.url}/rest/v1/mlit_crawl_state",
            params={"url": f"eq.{url}", "select": "*", "limit": "1"},
            headers=client._headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else None
    except Exception as e:
        logger.error("クロール状態取得エラー: %s — %s", url, e)
        return None


def upsert_crawl_state(
    client: SupabaseClient,
    url: str,
    page_hash: str,
    content_length: int,
    last_modified: str,
    pdf_links: list[str],
) -> None:
    """
    Supabase の mlit_crawl_state テーブルを更新する（直接 REST API）。

    Args:
        client: Supabase クライアント
        url: クロールした URL
        page_hash: ページ内容の SHA256 ハッシュ
        content_length: ページのバイト数
        last_modified: Last-Modified ヘッダーの値
        pdf_links: 検出された PDF リンクのリスト
    """
    if not client._configured:
        logger.warning("Supabase 未設定: クロール状態を更新できません。")
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "url": url,
        "page_hash": page_hash,
        "content_length": content_length,
        "last_modified": last_modified,
        "pdf_links": pdf_links,
        "last_crawled_at": now_iso,
    }
    try:
        resp = requests.post(
            f"{client.url}/rest/v1/mlit_crawl_state?on_conflict=url",
            json=record,
            headers={
                **client._headers,
                "Prefer": "resolution=merge-duplicates",
            },
            timeout=15,
        )
        resp.raise_for_status()
        logger.debug("クロール状態を更新: %s", url)
    except Exception as e:
        logger.error("クロール状態更新エラー: %s — %s", url, e)


# ---------------------------------------------------------------------------
# リンク抽出
# ---------------------------------------------------------------------------

def extract_links(base_url: str, html: str) -> list[str]:
    """
    HTML から絶対 URL リンクを抽出する。
    MARITIME_URL_PATTERN を含む URL のみを返す。

    Returns:
        フィルタ済み絶対 URL のリスト（重複なし）
    """
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()
    base_domain = urlparse(base_url).netloc

    for a_tag in soup.find_all("a", href=True):
        href: str = a_tag["href"]
        # フラグメントや JavaScript リンクを除外
        if href.startswith("#") or href.startswith("javascript:"):
            continue

        absolute_url = urljoin(base_url, href)
        parsed = urlparse(absolute_url)

        # 同一ドメインかつ /maritime/ パターンを含む URL のみ
        if (
            parsed.netloc == base_domain
            and MARITIME_URL_PATTERN in parsed.path
            and parsed.scheme in ("http", "https")
        ):
            # フラグメントを除去して正規化
            clean_url = absolute_url.split("#")[0]
            links.add(clean_url)

    return list(links)


def extract_pdf_links(base_url: str, html: str) -> list[str]:
    """
    HTML から PDF リンクを抽出する。

    Returns:
        PDF の絶対 URL リスト
    """
    soup = BeautifulSoup(html, "html.parser")
    pdf_links: list[str] = []

    for a_tag in soup.find_all("a", href=True):
        href: str = a_tag["href"]
        if href.lower().endswith(".pdf") or "pdf" in href.lower():
            absolute_url = urljoin(base_url, href)
            pdf_links.append(absolute_url)

    return pdf_links


# ---------------------------------------------------------------------------
# 既知 PDF URL 取得
# ---------------------------------------------------------------------------

def get_known_pdf_urls(client: SupabaseClient) -> set[str]:
    """
    Supabase から MLIT ソースの既知 PDF URL を取得する。
    直接 REST API を叩く。
    """
    if not client._configured:
        logger.warning("Supabase 未設定: 既知 PDF URL を取得できません。")
        return set()

    try:
        resp = requests.get(
            f"{client.url}/rest/v1/regulations",
            params={
                "source": "eq.MLIT",
                "select": "pdf_url",
                "limit": "10000",
            },
            headers=client._headers,
            timeout=30,
        )
        resp.raise_for_status()
        records = resp.json()
        known: set[str] = {r["pdf_url"] for r in records if r.get("pdf_url")}
        logger.info("既知 PDF URL 取得完了: %d 件", len(known))
        return known
    except Exception as e:
        logger.warning("既知 PDF URL 取得エラー: %s", e)
        return set()


# ---------------------------------------------------------------------------
# PDF 処理
# ---------------------------------------------------------------------------

def generate_source_id(counter: int) -> str:
    """
    source_id を生成する。
    形式: MLIT-{YYYYMMDD}-{連番3桁}
    """
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{SOURCE_PREFIX}-{date_str}-{counter:03d}"


def process_pdf(
    pdf_url: str,
    page_url: str,
    client: SupabaseClient,
    known_pdf_urls: set[str],
    source_id: str,
    dry_run: bool,
) -> bool:
    """
    新規 PDF を検出し、pending_queue に登録する。
    Gemini 分類は process-queue ジョブに委任（API コスト最適化）。

    Returns:
        登録に成功した場合は True
    """
    # 既知 PDF はスキップ
    if pdf_url in known_pdf_urls:
        logger.debug("既知 PDF をスキップ: %s", pdf_url)
        return False

    logger.info("新規 PDF 検出: %s", pdf_url)

    # HEAD チェック（アクセス可能か確認のみ）
    head_check = check_pdf_url(pdf_url)
    if not head_check["accessible"]:
        logger.warning("PDF にアクセスできません: %s", pdf_url)
        return False

    if dry_run:
        logger.info("[dry-run] PDF キューイングをスキップ: %s", pdf_url)
        return False

    # regulations テーブルに仮レコードを挿入（タイトルはファイル名、分類は後で）
    now_iso = datetime.now(timezone.utc).isoformat()
    pdf_filename = pdf_url.split("/")[-1]

    record: dict = {
        "source_id": source_id,
        "source": "MLIT",
        "title": pdf_filename,
        "url": page_url,
        "pdf_url": pdf_url,
        "scraped_at": now_iso,
        "severity": "informational",
    }
    client.upsert_regulation(record)

    # pending_queue に登録 → process-queue ジョブが Gemini 分類を実行
    client.queue_pending(
        source="MLIT",
        source_id=source_id,
        pdf_url=pdf_url,
        reason="awaiting_classification",
        error_detail="クロールで検出。Gemini 分類は process-queue で実行予定。",
    )
    logger.info("pending_queue に登録: %s → process-queue で分類予定", source_id)

    return True


# ---------------------------------------------------------------------------
# BFS クロール
# ---------------------------------------------------------------------------

def crawl(
    start_url: str,
    client: SupabaseClient,
    robots_checker: RobotsChecker,
    max_pages: int,
    max_depth: int,
    dry_run: bool,
) -> dict:
    """
    BFS（幅優先探索）で maritime/ 配下をクロールする。

    Returns:
        クロール結果サマリー:
        {
            "pages_crawled": int,
            "pages_changed": int,
            "pages_new": int,
            "pdfs_processed": int,
            "anomaly_detected": bool,
        }
    """
    stats = {
        "pages_crawled": 0,
        "pages_changed": 0,
        "pages_new": 0,
        "pdfs_processed": 0,
        "anomaly_detected": False,
    }

    # BFS キュー: (url, depth)
    queue: deque[tuple[str, int]] = deque()
    queue.append((start_url, 0))

    visited_urls: set[str] = {start_url}
    new_url_count = 0

    # Supabase から既知 PDF URL を取得
    known_pdf_urls = get_known_pdf_urls(client)

    pdf_counter = 0  # Supabase 保存用カウンター

    while queue and stats["pages_crawled"] < max_pages:
        current_url, depth = queue.popleft()

        # robots.txt チェック
        if not robots_checker.is_allowed(current_url):
            logger.info("robots.txt によりスキップ: %s", current_url)
            continue

        logger.info(
            "[%d/%d] クロール中 (深さ=%d): %s",
            stats["pages_crawled"] + 1,
            max_pages,
            depth,
            current_url,
        )

        # ページ取得（stealth_get を使用）
        try:
            time.sleep(REQUEST_INTERVAL_SEC)
            resp = stealth_get(current_url, timeout=15)
            resp.raise_for_status()

            html_content = resp.text
            content_bytes = resp.content
            last_modified = ""  # stealth_get の Response にはヘッダーがないため空文字
            content_length = len(content_bytes)

        except (requests.exceptions.RequestException, Exception) as e:
            logger.warning("ページ取得エラー: %s — %s", current_url, e)
            continue

        stats["pages_crawled"] += 1

        # ハッシュ計算
        page_hash = compute_page_hash(html_content)

        # 既存のクロール状態と比較
        existing_state = get_crawl_state(client, current_url)
        is_new_page = existing_state is None
        is_changed = not is_new_page and existing_state.get("page_hash") != page_hash

        if is_new_page:
            stats["pages_new"] += 1
            new_url_count += 1
            logger.info("新規ページ検出: %s", current_url)

            # 異常検知チェック
            if new_url_count >= ANOMALY_NEW_URL_THRESHOLD:
                logger.error(
                    "異常検知: 新規 URL が %d 件を超えました。クロールを中断します。",
                    ANOMALY_NEW_URL_THRESHOLD,
                )
                stats["anomaly_detected"] = True
                try:
                    send_alert(
                        title="MLIT クロール異常",
                        message=(
                            f"新規 URL が {new_url_count} 件検出されました。"
                            "サイト構造の大幅な変更の可能性があります。クロールを中断しました。"
                        ),
                        severity="critical",
                    )
                except Exception:
                    pass
                break

        elif is_changed:
            stats["pages_changed"] += 1
            logger.info("ページ変更検出: %s", current_url)
        else:
            logger.debug("変更なし: %s", current_url)

        # PDF リンク抽出（新規または変更ページのみ）
        pdf_links: list[str] = []
        if is_new_page or is_changed:
            pdf_links = extract_pdf_links(current_url, html_content)
            if pdf_links:
                logger.info(
                    "%d 件の PDF リンクを検出: %s", len(pdf_links), current_url
                )

            # 各 PDF を処理
            for pdf_url in pdf_links:
                pdf_counter += 1
                source_id = generate_source_id(pdf_counter)
                success = process_pdf(
                    pdf_url=pdf_url,
                    page_url=current_url,
                    client=client,
                    known_pdf_urls=known_pdf_urls,
                    source_id=source_id,
                    dry_run=dry_run,
                )
                if success:
                    stats["pdfs_processed"] += 1
                    known_pdf_urls.add(pdf_url)  # 二重処理防止

        # クロール状態を更新
        if not dry_run:
            upsert_crawl_state(
                client=client,
                url=current_url,
                page_hash=page_hash,
                content_length=content_length,
                last_modified=last_modified,
                pdf_links=pdf_links,
            )

        # 次の深さの URL をキューに追加
        if depth < max_depth:
            child_links = extract_links(current_url, html_content)
            for child_url in child_links:
                if child_url not in visited_urls:
                    visited_urls.add(child_url)
                    queue.append((child_url, depth + 1))

    return stats


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="国交省（MLIT）海事局 ウェブクロール — 第 2 層"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 書き込みをスキップ（クロールのみ実行）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        metavar="N",
        help=f"クロール最大ページ数（デフォルト: {DEFAULT_MAX_PAGES}）",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=DEFAULT_CRAWL_DEPTH,
        metavar="N",
        help=f"クロール深さ（デフォルト: {DEFAULT_CRAWL_DEPTH}）",
    )
    args = parser.parse_args()

    # 環境変数からクロール設定を上書き可能
    env_depth = os.getenv("MLIT_CRAWL_DEPTH")
    if env_depth and env_depth.isdigit():
        effective_depth = int(env_depth)
        logger.info("クロール深さを環境変数から設定: %d", effective_depth)
    else:
        effective_depth = args.depth

    if args.dry_run:
        logger.info("=== DRY RUN モード ===")

    logger.info(
        "MLIT クロール開始 (max_pages=%d, depth=%d)",
        args.max_pages,
        effective_depth,
    )

    # robots.txt チェッカー初期化
    robots_checker = RobotsChecker(user_agent=USER_AGENT)

    # Supabase クライアント初期化
    client = SupabaseClient()

    try:
        stats = crawl(
            start_url=CRAWL_START_URL,
            client=client,
            robots_checker=robots_checker,
            max_pages=args.max_pages,
            max_depth=effective_depth,
            dry_run=args.dry_run,
        )

        logger.info(
            "クロール完了: ページ=%d (新規=%d, 変更=%d), PDF=%d件処理",
            stats["pages_crawled"],
            stats["pages_new"],
            stats["pages_changed"],
            stats["pdfs_processed"],
        )

        if stats["anomaly_detected"]:
            logger.warning("異常を検知したため、クロールを途中で中断しました。")
            sys.exit(1)

        # サマリー通知
        if (stats["pages_new"] > 0 or stats["pdfs_processed"] > 0) and not args.dry_run:
            try:
                send_alert(
                    title="MLIT クロール完了",
                    message=(
                        f"新規ページ: {stats['pages_new']} 件、"
                        f"変更ページ: {stats['pages_changed']} 件、"
                        f"PDF 処理: {stats['pdfs_processed']} 件"
                    ),
                    severity="info",
                )
            except Exception as e:
                logger.warning("LINE 通知エラー: %s", e)

    except Exception as e:
        logger.error("予期しないエラー: %s", e, exc_info=True)
        try:
            send_scraper_error(
                scraper_name="scrape_mlit_crawl",
                error=e,
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
