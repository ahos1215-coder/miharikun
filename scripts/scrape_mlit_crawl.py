"""
国交省（MLIT）海事局 シードURL方式クローラー
=============================================
BFS を廃止し、重要インデックスページ（シードURL）を直接巡回する。
Gemini 不要 — PDF 分類は pending_queue 経由で process-queue に委任。

処理フロー:
  1) シードURL 6 ページを巡回
  2) 各ページから POLICY_URL_PATTERNS にマッチするリンクを全抽出
  3) NOISE_URL_PATTERNS / NOISE_TITLE_KEYWORDS で除外
  4) 抽出した施策ページURL（推定40-60件）を巡回
  5) 各ページの <main> 要素のテキストハッシュを計算
  6) mlit_crawl_state の前回ハッシュと比較
  7) 差分あり → 新規 PDF リンクを抽出 → pending_queue に登録
  8) 差分なし → スキップ
  9) 全ページの巡回状態を mlit_crawl_state に更新
  10) 404 エラーのシードURL があれば LINE 通知

Discovery Mode:
  - mlit_crawl_state に存在しない maritime_fr* URL を発見 → ログに記録

使い方:
  python scrape_mlit_crawl.py
  python scrape_mlit_crawl.py --dry-run
  python scrape_mlit_crawl.py --dry-run --verbose
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import argparse
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from utils.supabase_client import SupabaseClient  # type: ignore
from utils.line_notify import send_alert, send_scraper_error  # type: ignore
from utils.mlit_seed_urls import (  # type: ignore
    SEED_URLS,
    POLICY_URL_PATTERNS,
    NOISE_URL_PATTERNS,
    NOISE_TITLE_KEYWORDS,
    MAIN_CONTENT_SELECTORS,
)

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("MLIT Crawl")

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

USER_AGENT = "MaritimeRegsMonitor/0.2 (+https://github.com/ahos1215-coder)"
REQUEST_INTERVAL_SEC = 3
SOURCE_PREFIX = "MLIT"

# シードURL の日本語ラベル（ログ用）
SEED_LABELS: dict[str, str] = {
    "maritime_mn4_000005": "運航労務監理",
    "maritime_tk8_000003": "船舶の安全・環境",
    "maritime_fr4_000030": "船員安全衛生",
    "maritime_tk4_000016": "船員の現状",
    "maritime_tk10_000017": "船員養成",
    "maritime_fr1_000027": "法律",
}


# ---------------------------------------------------------------------------
# ユーティリティ: ラベル取得
# ---------------------------------------------------------------------------

def _get_seed_label(url: str) -> str:
    """シードURL から日本語ラベルを返す。"""
    for key, label in SEED_LABELS.items():
        if key in url:
            return label
    return url.split("/")[-1]


# ---------------------------------------------------------------------------
# コンテンツ抽出・ハッシュ
# ---------------------------------------------------------------------------

def extract_main_content(html: str) -> str:
    """
    <main> 要素のテキストを抽出。フォールバック対応。
    main -> article -> div#content -> div#main -> div.container
    """
    soup = BeautifulSoup(html, "html.parser")

    for selector in MAIN_CONTENT_SELECTORS:
        name = selector["name"]
        attrs = dict(selector.get("attrs", {}))
        # class_ を class に変換（BeautifulSoup の仕様）
        if "class_" in attrs:
            attrs["class"] = attrs.pop("class_")
        element = soup.find(name, attrs=attrs if attrs else None)
        if element:
            for tag in element.find_all(["script", "style", "noscript"]):
                tag.decompose()
            return element.get_text(strip=True)

    # 最終手段: body からヘッダー/フッターを除去
    body = soup.find("body")
    if body:
        for tag in body.find_all(["header", "footer", "nav", "script", "style", "noscript"]):
            tag.decompose()
        return body.get_text(strip=True)

    return ""


def compute_content_hash(text: str) -> str:
    """テキストの SHA256 ハッシュを返す。"""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


# ---------------------------------------------------------------------------
# URL フィルタリング
# ---------------------------------------------------------------------------

def is_policy_url(url: str) -> bool:
    """POLICY_URL_PATTERNS にマッチするか判定。"""
    parsed = urlparse(url)
    return any(pat in parsed.path for pat in POLICY_URL_PATTERNS)


def is_noise_url(url: str) -> bool:
    """NOISE_URL_PATTERNS にマッチするか判定。"""
    return any(pat in url for pat in NOISE_URL_PATTERNS)


def is_noise_title(text: str) -> bool:
    """NOISE_TITLE_KEYWORDS にマッチするか判定。"""
    return any(kw in text for kw in NOISE_TITLE_KEYWORDS)


# ---------------------------------------------------------------------------
# リンク抽出
# ---------------------------------------------------------------------------

def extract_policy_links(html: str, base_url: str) -> list[dict[str, str]]:
    """
    HTML から施策ページリンクを抽出する。
    POLICY_URL_PATTERNS にマッチし、NOISE パターンに該当しないもののみ返す。

    Returns:
        [{"url": str, "text": str}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc
    links: dict[str, str] = {}  # url -> text（重複排除）

    for a_tag in soup.find_all("a", href=True):
        href: str = a_tag["href"]
        text: str = a_tag.get_text(strip=True)

        # フラグメント・JavaScript・mailto を除外
        if href.startswith(("#", "javascript:", "mailto:")):
            continue

        absolute_url = urljoin(base_url, href).split("#")[0]
        parsed = urlparse(absolute_url)

        # 同一ドメインのみ
        if parsed.netloc != base_domain:
            continue

        # 施策ページパターンにマッチするか
        if not is_policy_url(absolute_url):
            continue

        # ノイズ URL を除外
        if is_noise_url(absolute_url):
            continue

        # ノイズタイトルを除外
        if is_noise_title(text):
            continue

        # PDF リンクはここでは除外（PDF は別途抽出する）
        if href.lower().endswith(".pdf"):
            continue

        if absolute_url not in links:
            links[absolute_url] = text

    return [{"url": url, "text": text} for url, text in links.items()]


def extract_pdf_links(html: str, base_url: str) -> list[dict[str, str]]:
    """
    ページ内の PDF リンクを抽出。
    各 PDF の Content-Length と Last-Modified も HEAD リクエストで取得。
    """
    soup = BeautifulSoup(html, "html.parser")
    pdfs: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href: str = a_tag["href"]
        if not href.lower().endswith(".pdf"):
            continue

        full_url = urljoin(base_url, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        text = a_tag.get_text(strip=True)

        # HEAD リクエストで Content-Length を確認
        content_length = ""
        last_modified = ""
        try:
            head = requests.head(
                full_url,
                timeout=10,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            content_length = head.headers.get("Content-Length", "")
            last_modified = head.headers.get("Last-Modified", "")
        except Exception:
            pass

        pdfs.append({
            "url": full_url,
            "text": text,
            "content_length": content_length,
            "last_modified": last_modified,
        })

    return pdfs


# ---------------------------------------------------------------------------
# シードURL ヘルスチェック
# ---------------------------------------------------------------------------

def check_seed_url_health(url: str) -> bool:
    """シードURL が生きているか確認。404 なら LINE 通知。"""
    try:
        resp = requests.head(
            url,
            timeout=15,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        if resp.status_code == 404:
            send_alert(
                title="MLIT シードURL 404",
                message=f"シードURL が 404 を返しました: {url}\nサイト構造が変更された可能性があります。",
                severity="critical",
            )
            return False
        return resp.status_code < 400
    except Exception as e:
        logger.warning("シードURL ヘルスチェック失敗: %s — %s", url, e)
        return False


# ---------------------------------------------------------------------------
# Supabase — mlit_crawl_state テーブル操作
# ---------------------------------------------------------------------------

def get_crawl_state(client: SupabaseClient, url: str) -> Optional[dict]:
    """指定 URL のクロール状態を取得する。"""
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


def get_all_crawl_state_urls(client: SupabaseClient) -> set[str]:
    """mlit_crawl_state に登録済みの全 URL を取得する（Discovery 判定用）。"""
    if not client._configured:
        return set()

    try:
        resp = requests.get(
            f"{client.url}/rest/v1/mlit_crawl_state",
            params={"select": "url", "limit": "10000"},
            headers=client._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return {r["url"] for r in data if r.get("url")}
    except Exception as e:
        logger.warning("クロール状態一覧取得エラー: %s", e)
        return set()


def upsert_crawl_state(
    client: SupabaseClient,
    url: str,
    page_hash: str,
    pdf_links: list[dict[str, str]],
    content_length: int,
) -> None:
    """mlit_crawl_state テーブルを更新する。"""
    if not client._configured:
        logger.warning("Supabase 未設定: クロール状態を更新できません。")
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "url": url,
        "page_hash": page_hash,
        "pdf_links": [p["url"] for p in pdf_links],
        "last_crawled_at": now_iso,
        "content_length": content_length,
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
# 既知 PDF URL 取得
# ---------------------------------------------------------------------------

def get_known_pdf_urls(client: SupabaseClient) -> set[str]:
    """Supabase から MLIT ソースの既知 PDF URL を取得する。"""
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
# 新規 PDF 登録
# ---------------------------------------------------------------------------

def register_new_pdfs(
    client: SupabaseClient,
    page_url: str,
    new_pdfs: list[dict[str, str]],
    source_counter: int,
    dry_run: bool,
) -> int:
    """
    新規 PDF を regulations + pending_queue に登録する。

    Returns:
        更新後の source_counter
    """
    for pdf in new_pdfs:
        source_counter += 1
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        source_id = f"{SOURCE_PREFIX}-{date_str}-{source_counter:03d}"

        # regulations に仮レコード
        record = {
            "source_id": source_id,
            "source": "MLIT",
            "title": pdf["text"] or pdf["url"].split("/")[-1],
            "url": page_url,
            "pdf_url": pdf["url"],
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "severity": "informational",
        }
        if not dry_run:
            client.upsert_regulation(record)

        # pending_queue に登録
        if not dry_run:
            client.queue_pending(
                source="MLIT",
                source_id=source_id,
                pdf_url=pdf["url"],
                reason="awaiting_classification",
                error_detail="シードURL方式で検出。Gemini分類は process-queue で実行予定。",
            )
        logger.info("新規PDF登録: %s -> %s", source_id, pdf["url"])

    return source_counter


# ---------------------------------------------------------------------------
# フェッチ
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> Optional[str]:
    """
    ページ HTML を取得する。エラー時は None を返す。
    リクエスト間隔は呼び出し側で管理する。
    """
    try:
        resp = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if status == 404:
            logger.warning("404 Not Found: %s", url)
        else:
            logger.warning("HTTP エラー %d: %s", status, url)
        return None
    except Exception as e:
        logger.warning("ページ取得エラー: %s — %s", url, e)
        return None


# ---------------------------------------------------------------------------
# メイン巡回ロジック
# ---------------------------------------------------------------------------

def crawl_seeds(client: SupabaseClient, dry_run: bool, verbose: bool) -> dict:
    """
    シードURL 方式で巡回する。

    Returns:
        {
            "seed_count": int,
            "policy_pages": int,
            "pages_changed": int,
            "new_pdfs": int,
            "discoveries": int,
            "seed_errors": list[str],
        }
    """
    stats = {
        "seed_count": len(SEED_URLS),
        "policy_pages": 0,
        "pages_changed": 0,
        "new_pdfs": 0,
        "discoveries": 0,
        "seed_errors": [],
    }

    # 既知 URL セットを取得（Discovery 判定用）
    known_crawl_urls = get_all_crawl_state_urls(client)
    known_pdf_urls = get_known_pdf_urls(client)

    source_counter = 0

    # ---------------------------------------------------------------
    # Phase 1: シードURL からポリシーリンクを収集
    # ---------------------------------------------------------------
    logger.info("シードURL巡回開始 (%d ページ)", len(SEED_URLS))

    all_policy_links: dict[str, str] = {}  # url -> text（重複排除）

    for idx, seed_url in enumerate(SEED_URLS, start=1):
        label = _get_seed_label(seed_url)

        # ヘルスチェック
        if not check_seed_url_health(seed_url):
            logger.error("[%d/%d] %s — シードURL 無効", idx, len(SEED_URLS), label)
            stats["seed_errors"].append(seed_url)
            continue

        time.sleep(REQUEST_INTERVAL_SEC)
        html = fetch_page(seed_url)
        if html is None:
            logger.error("[%d/%d] %s — ページ取得失敗", idx, len(SEED_URLS), label)
            stats["seed_errors"].append(seed_url)
            continue

        links = extract_policy_links(html, seed_url)
        for link in links:
            if link["url"] not in all_policy_links:
                all_policy_links[link["url"]] = link["text"]

        logger.info(
            "[%d/%d] %s -> %d 施策リンク検出",
            idx, len(SEED_URLS), label, len(links),
        )

    # 重複除外後の施策ページ数
    policy_urls = list(all_policy_links.keys())
    stats["policy_pages"] = len(policy_urls)

    logger.info(
        "施策ページ巡回開始 (%d ページ, 重複除外済み)",
        len(policy_urls),
    )

    # ---------------------------------------------------------------
    # Phase 2: 施策ページを巡回
    # ---------------------------------------------------------------
    for idx, page_url in enumerate(policy_urls, start=1):
        page_name = page_url.split("/")[-1]
        time.sleep(REQUEST_INTERVAL_SEC)

        html = fetch_page(page_url)
        if html is None:
            logger.warning("[%d/%d] %s — 取得失敗", idx, len(policy_urls), page_name)
            continue

        # <main> 要素のハッシュを計算
        main_text = extract_main_content(html)
        content_hash = compute_content_hash(main_text)

        # 前回のクロール状態と比較
        existing = get_crawl_state(client, page_url)
        is_new = existing is None
        is_changed = not is_new and existing.get("page_hash") != content_hash

        # Discovery: mlit_crawl_state に未登録の URL を検出
        if is_new and page_url not in known_crawl_urls:
            stats["discoveries"] += 1
            logger.info("[Discovery] 新規ポータル発見: %s", page_name)

        if is_changed:
            # 変更あり — PDF リンクを抽出
            pdf_links = extract_pdf_links(html, page_url)

            # 既知 PDF を除外
            new_pdfs = [p for p in pdf_links if p["url"] not in known_pdf_urls]

            if new_pdfs:
                stats["new_pdfs"] += len(new_pdfs)
                source_counter = register_new_pdfs(
                    client, page_url, new_pdfs, source_counter, dry_run,
                )
                # 二重登録防止
                for p in new_pdfs:
                    known_pdf_urls.add(p["url"])

            stats["pages_changed"] += 1
            logger.info(
                "[%d/%d] %s -> 変更あり! 新規PDF %d件",
                idx, len(policy_urls), page_name, len(new_pdfs),
            )
        elif is_new:
            # 新規ページ — PDF も抽出
            pdf_links = extract_pdf_links(html, page_url)
            new_pdfs = [p for p in pdf_links if p["url"] not in known_pdf_urls]

            if new_pdfs:
                stats["new_pdfs"] += len(new_pdfs)
                source_counter = register_new_pdfs(
                    client, page_url, new_pdfs, source_counter, dry_run,
                )
                for p in new_pdfs:
                    known_pdf_urls.add(p["url"])

            stats["pages_changed"] += 1
            if verbose:
                logger.info(
                    "[%d/%d] %s -> 新規ページ! PDF %d件",
                    idx, len(policy_urls), page_name, len(new_pdfs),
                )
        else:
            if verbose:
                logger.info("[%d/%d] %s -> 変更なし", idx, len(policy_urls), page_name)

        # クロール状態を更新
        if not dry_run:
            all_pdf_links = extract_pdf_links(html, page_url) if (is_new or is_changed) else []
            upsert_crawl_state(
                client=client,
                url=page_url,
                page_hash=content_hash,
                pdf_links=all_pdf_links if (is_new or is_changed) else [],
                content_length=len(html),
            )

    return stats


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="国交省（MLIT）海事局 シードURL方式クローラー"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 書き込みをスキップ（巡回のみ実行）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細ログを出力する",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.dry_run:
        logger.info("=== DRY RUN モード ===")

    # Supabase クライアント初期化
    client = SupabaseClient()

    try:
        stats = crawl_seeds(
            client=client,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        # サマリー出力
        logger.info("=== 巡回完了 ===")
        logger.info("  シードURL: %d, 施策ページ: %d", stats["seed_count"], stats["policy_pages"])
        logger.info(
            "  変更あり: %d, 新規PDF: %d, 新規ポータル: %d",
            stats["pages_changed"], stats["new_pdfs"], stats["discoveries"],
        )

        if stats["seed_errors"]:
            logger.warning("  シードURL エラー: %s", ", ".join(stats["seed_errors"]))

        # LINE 通知（新規 PDF がある場合のみ）
        if stats["new_pdfs"] > 0 and not args.dry_run:
            try:
                send_alert(
                    title="MLIT クロール完了",
                    message=(
                        f"施策ページ: {stats['policy_pages']} 件巡回、"
                        f"変更: {stats['pages_changed']} 件、"
                        f"新規PDF: {stats['new_pdfs']} 件"
                    ),
                    severity="info",
                )
            except Exception as e:
                logger.warning("LINE 通知エラー: %s", e)

    except Exception as e:
        logger.error("予期しないエラー: %s", e, exc_info=True)
        try:
            send_scraper_error(scraper_name="scrape_mlit_crawl", error=e)
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
