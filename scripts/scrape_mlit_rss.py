"""
国交省（MLIT）海事局 RSS スクレイパー — 第 1 層
=================================================
RSS フィードを監視して海事関連の新着情報を検出し、
Gemini で分類して Supabase に保存する。

処理フロー:
  1) MLIT_RSS_URLS の各 RSS フィードを feedparser で取得
  2) 海事関連キーワードでフィルタリング（20語以上）
  3) Supabase の regulations テーブルから既知 URL を取得 → 新着のみ抽出
  4) 新着エントリの URL にアクセス → PDF リンクを取得
  5) PDF を Gemini で分類 → Supabase に保存
  6) PDF なし（HTML のみ）の場合もタイトル・要約を保存

使い方:
  python scrape_mlit_rss.py
  python scrape_mlit_rss.py --dry-run
  python scrape_mlit_rss.py --limit 10
  python scrape_mlit_rss.py --since 2026-01-01
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser  # type: ignore
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# パス設定（スクリプト直下から utils を import）
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(__file__))

from utils.supabase_client import SupabaseClient  # type: ignore
from utils.gemini_client import classify_pdf  # type: ignore
from utils.gdrive_client import upload_json  # type: ignore
from utils.line_notify import send_alert, send_scraper_error  # type: ignore
from utils.pdf_preprocess import preprocess_pdf, check_pdf_url  # type: ignore

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scrape_mlit_rss")

# ---------------------------------------------------------------------------
# 定数・設定
# ---------------------------------------------------------------------------

# デフォルト RSS URL（環境変数 MLIT_RSS_URLS でカンマ区切り指定可能）
DEFAULT_RSS_URLS = [
    # 国交省プレスリリース RDF（海事局記事を kaiji キーワードでフィルタ）
    "https://www.mlit.go.jp/pressrelease.rdf",
]

# 海事関連キーワード（フィルタリング用・20語以上）
MARITIME_KEYWORDS = [
    "船舶", "海事", "船員", "港湾", "安全", "環境", "条約",
    "IMO", "SOLAS", "MARPOL", "検査", "証書",
    "海上", "航行", "漁船", "旅客船", "貨物船",
    "船級", "船籍", "STCW", "ISM", "ISPS", "MLC",
    "海洋", "沿岸", "運輸局", "海事局",
]

SOURCE_PREFIX = "MLIT"
USER_AGENT = "MaritimeRegsMonitor/0.1 (+https://github.com/ahos1215-coder)"

# リクエスト間隔（秒）
REQUEST_INTERVAL_SEC = 2

# Gemini 分類プロンプト
GEMINI_PROMPT = """
あなたは海事規制の専門家です。添付の PDF ドキュメントを解析し、以下の JSON 形式で分類結果を返してください。
過去の学習知識は使わず、添付 PDF のテキストのみから判断してください。

分類対象: 国土交通省（MLIT）発行の海事関連文書
"""

# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def get_rss_urls() -> list[str]:
    """環境変数またはデフォルトから RSS URL リストを返す。"""
    env_urls = os.getenv("MLIT_RSS_URLS", "")
    if env_urls.strip():
        urls = [u.strip() for u in env_urls.split(",") if u.strip()]
        logger.info("環境変数から RSS URL を取得: %d 件", len(urls))
        return urls
    logger.info("デフォルト RSS URL を使用: %d 件", len(DEFAULT_RSS_URLS))
    return DEFAULT_RSS_URLS.copy()


def is_maritime_related(title: str, summary: str, link: str = "") -> bool:
    """タイトル・要約・URL が海事関連キーワードを含むか判定する。"""
    # 海事局 URL パスを含む場合は即マッチ
    if link and "/kaiji" in link.lower():
        return True
    text = f"{title} {summary}".lower()
    for keyword in MARITIME_KEYWORDS:
        if keyword.lower() in text:
            return True
    return False


def generate_source_id(published_date: Optional[datetime], counter: int) -> str:
    """
    source_id を生成する。
    形式: MLIT-{YYYYMMDD}-{連番3桁}
    例: MLIT-20260329-001
    """
    if published_date:
        date_str = published_date.strftime("%Y%m%d")
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{SOURCE_PREFIX}-{date_str}-{counter:03d}"


def parse_published_date(entry: feedparser.FeedParserDict) -> Optional[datetime]:
    """feedparser エントリから公開日時を解析する。"""
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            import calendar
            ts = calendar.timegm(entry.published_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            import calendar
            ts = calendar.timegm(entry.updated_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception as e:
        logger.debug("日時解析エラー: %s", e)
    return None


def fetch_pdf_links(page_url: str, session: requests.Session) -> list[str]:
    """
    ページ URL にアクセスして PDF リンクを抽出する。

    Returns:
        PDF の URL リスト（絶対 URL）
    """
    try:
        resp = session.get(page_url, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding  # 文字コード自動検出

        soup = BeautifulSoup(resp.text, "html.parser")
        pdf_links: list[str] = []

        for a_tag in soup.find_all("a", href=True):
            href: str = a_tag["href"]
            # .pdf リンクを収集
            if href.lower().endswith(".pdf") or "pdf" in href.lower():
                absolute_url = urljoin(page_url, href)
                pdf_links.append(absolute_url)

        logger.debug("%d 件の PDF リンクを検出: %s", len(pdf_links), page_url)
        return pdf_links

    except requests.exceptions.RequestException as e:
        logger.warning("ページ取得エラー: %s — %s", page_url, e)
        return []


def download_pdf(pdf_url: str, session: requests.Session) -> Optional[bytes]:
    """PDF をダウンロードしてバイト列を返す。失敗時は None。"""
    try:
        resp = session.get(pdf_url, timeout=30)
        resp.raise_for_status()
        return resp.content
    except requests.exceptions.RequestException as e:
        logger.warning("PDF ダウンロードエラー: %s — %s", pdf_url, e)
        return None


def get_known_urls(client: SupabaseClient) -> set[str]:
    """
    Supabase から MLIT ソースの既知 URL を取得する。
    SupabaseClient の REST API を直接使い source=MLIT のレコードを取得する。
    """
    if not client._configured:
        logger.warning("Supabase 未設定: 既知 URL を取得できません。")
        return set()

    try:
        resp = requests.get(
            f"{client.url}/rest/v1/regulations",
            params={
                "source": "eq.MLIT",
                "select": "url",
                "limit": "10000",
            },
            headers=client._headers,
            timeout=30,
        )
        resp.raise_for_status()
        records = resp.json()
        known: set[str] = {r["url"] for r in records if r.get("url")}
        logger.info("既知 URL 取得完了: %d 件", len(known))
        return known
    except Exception as e:
        logger.error("既知 URL 取得エラー: %s", e)
        return set()


def build_regulation_record(
    source_id: str,
    title: str,
    page_url: str,
    published_date: Optional[datetime],
    classification: Optional[dict],
    pdf_url: Optional[str] = None,
    pdf_preprocess_result: Optional[dict] = None,
) -> dict:
    """Supabase に保存するレコードを構築する。"""
    now_iso = datetime.now(timezone.utc).isoformat()

    record: dict = {
        "source_id": source_id,
        "source": "MLIT",
        "title": title,
        "url": page_url,
        "published_at": published_date.isoformat() if published_date else None,
        "scraped_at": now_iso,
        "pdf_url": pdf_url,
    }

    # Gemini 分類結果をマージ
    if classification and classification.get("status") == "ok":
        record.update({
            "category": classification.get("category"),
            "severity": classification.get("severity"),
            "summary_ja": classification.get("summary"),
            "confidence": classification.get("confidence"),
            "citations": classification.get("citations"),
            "applicable_ship_types": classification.get("applicable_vessel_types"),
            "effective_date": classification.get("effective_date"),
            "raw_gemini_response": classification,
        })

    # PDF 前処理の警告
    if pdf_preprocess_result and pdf_preprocess_result.get("warning"):
        record["processing_notes"] = pdf_preprocess_result["warning"]

    return record


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def fetch_rss_entries(
    rss_urls: list[str],
    since: Optional[datetime] = None,
) -> list[dict]:
    """
    RSS フィードを取得し、海事関連エントリをフィルタリングして返す。

    Returns:
        海事関連エントリのリスト（各エントリは feedparser の dict）
    """
    all_entries: list[dict] = []

    for url in rss_urls:
        logger.info("RSS フィード取得中: %s", url)
        try:
            feed = feedparser.parse(
                url,
                agent=USER_AGENT,
                request_headers={"User-Agent": USER_AGENT},
            )

            if feed.bozo and not feed.entries:
                logger.warning("RSS パースエラー: %s — %s", url, feed.bozo_exception)
                continue

            logger.info(
                "フィード取得完了: %s — %d エントリ",
                feed.feed.get("title", url),
                len(feed.entries),
            )

            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                link = entry.get("link", "")

                if not link:
                    continue

                # --since フィルタ
                if since:
                    pub_date = parse_published_date(entry)
                    if pub_date and pub_date < since:
                        continue

                # 海事キーワードフィルタ（URL パスの kaiji も判定）
                if is_maritime_related(title, summary, link):
                    all_entries.append(entry)
                    logger.debug("海事エントリ検出: %s", title[:60])

        except Exception as e:
            logger.error("RSS フィード取得エラー: %s — %s", url, e)
            continue

    logger.info("海事関連エントリ合計: %d 件", len(all_entries))
    return all_entries


def process_entries(
    entries: list[dict],
    known_urls: set[str],
    client: SupabaseClient,
    session: requests.Session,
    dry_run: bool,
    limit: int,
) -> int:
    """
    新着エントリを処理して Supabase に保存する。

    Returns:
        処理済みエントリ数
    """
    processed = 0
    # 日付ごとのカウンターを管理
    date_counter: dict[str, int] = {}

    for entry in entries:
        if processed >= limit:
            logger.info("処理件数上限 (%d 件) に達しました。", limit)
            break

        link = entry.get("link", "")
        title = entry.get("title", "（タイトルなし）")

        # 既知 URL はスキップ
        if link in known_urls:
            logger.debug("既知 URL をスキップ: %s", link)
            continue

        logger.info("新着エントリ処理中: %s", title[:60])
        pub_date = parse_published_date(entry)

        # source_id 生成
        date_key = pub_date.strftime("%Y%m%d") if pub_date else datetime.now(timezone.utc).strftime("%Y%m%d")
        date_counter[date_key] = date_counter.get(date_key, 0) + 1
        source_id = generate_source_id(pub_date, date_counter[date_key])

        # PDF リンク取得
        pdf_links: list[str] = []
        if not dry_run:
            time.sleep(REQUEST_INTERVAL_SEC)
            pdf_links = fetch_pdf_links(link, session)
        else:
            logger.info("[dry-run] PDF リンク取得をスキップ: %s", link)

        # PDF 処理
        classification: Optional[dict] = None
        primary_pdf_url: Optional[str] = None
        pdf_preprocess_result: Optional[dict] = None

        if pdf_links and not dry_run:
            primary_pdf_url = pdf_links[0]
            logger.info("PDF 処理中: %s", primary_pdf_url)

            # HEAD チェック
            head_check = check_pdf_url(primary_pdf_url)
            if not head_check["accessible"]:
                logger.warning("PDF にアクセスできません: %s", primary_pdf_url)
                primary_pdf_url = None
            else:
                # PDF ダウンロード
                pdf_bytes = download_pdf(primary_pdf_url, session)
                if pdf_bytes:
                    # 前処理チェック
                    pdf_preprocess_result = preprocess_pdf(primary_pdf_url, pdf_bytes)

                    if pdf_preprocess_result["status"] == "skipped":
                        logger.warning(
                            "PDF をスキップ: %s — %s",
                            primary_pdf_url,
                            pdf_preprocess_result["skip_reason"],
                        )
                        primary_pdf_url = None
                        # pending_queue に登録
                        client.queue_pending(
                            source="MLIT",
                            source_id=source_id,
                            pdf_url=primary_pdf_url or "",
                            reason="pdf_skipped",
                            error_detail=pdf_preprocess_result.get("skip_reason", ""),
                        )
                    else:
                        # Gemini 分類
                        try:
                            classification = classify_pdf(
                                pdf_bytes=pdf_bytes,
                                prompt=GEMINI_PROMPT,
                                source_id=source_id,
                            )
                            logger.info(
                                "Gemini 分類完了: カテゴリ=%s, 信頼度=%s",
                                classification.get("category"),
                                classification.get("confidence"),
                            )
                            # classify_pdf は失敗時に例外ではなく status=pending を返す
                            if classification.get("status") == "pending":
                                logger.warning("Gemini 分類失敗（pending）: %s — %s", source_id, classification.get("error"))
                                client.queue_pending(
                                    source="MLIT",
                                    source_id=source_id,
                                    pdf_url=primary_pdf_url or "",
                                    reason="gemini_pending",
                                    error_detail=classification.get("error", ""),
                                )
                        except Exception as e:
                            logger.error("Gemini 分類エラー: %s — %s", primary_pdf_url, e)
                            client.queue_pending(
                                source="MLIT",
                                source_id=source_id,
                                pdf_url=primary_pdf_url or "",
                                reason="gemini_error",
                                error_detail=str(e),
                            )

        # Supabase に保存
        record = build_regulation_record(
            source_id=source_id,
            title=title,
            page_url=link,
            published_date=pub_date,
            classification=classification,
            pdf_url=primary_pdf_url,
            pdf_preprocess_result=pdf_preprocess_result,
        )

        if not dry_run:
            success = client.upsert_regulation(record)
            if success:
                logger.info("Supabase 保存完了: %s", source_id)

                # Google Drive に分類結果を保存
                if classification and classification.get("status") == "ok":
                    try:
                        upload_json(
                            data=record,
                            filename=f"{source_id}.json",
                        )
                    except Exception as e:
                        logger.warning("Google Drive 保存エラー: %s", e)
            else:
                logger.error("Supabase 保存失敗: %s", source_id)
                try:
                    send_scraper_error(
                        scraper_name="scrape_mlit_rss",
                        error=Exception(f"Supabase upsert failed for {source_id}"),
                        context={"url": link, "source_id": source_id},
                    )
                except Exception:
                    pass
        else:
            logger.info(
                "[dry-run] レコード（保存スキップ）: source_id=%s, title=%s",
                source_id,
                title[:40],
            )

        processed += 1

    return processed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="国交省（MLIT）海事局 RSS スクレイパー — 第 1 層"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="PDF ダウンロード・Gemini 分類・DB 書き込みをスキップ",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        metavar="N",
        help="処理件数の上限（デフォルト: 20）",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        metavar="DATE",
        help="指定日以降のエントリのみ処理（YYYY-MM-DD 形式）",
    )
    args = parser.parse_args()

    # --since の解析
    since_date: Optional[datetime] = None
    if args.since:
        try:
            since_date = datetime.strptime(args.since, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            logger.error("--since の日付形式が正しくありません: %s (YYYY-MM-DD が必要)", args.since)
            sys.exit(1)

    if args.dry_run:
        logger.info("=== DRY RUN モード ===")

    logger.info("MLIT RSS スクレイパー開始 (limit=%d)", args.limit)

    # RSS URL リスト取得
    rss_urls = get_rss_urls()

    # HTTP セッション初期化
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    # Supabase クライアント初期化
    client = SupabaseClient()

    try:
        # RSS エントリ取得・フィルタリング
        entries = fetch_rss_entries(rss_urls, since=since_date)

        if not entries:
            logger.info("新着海事エントリなし。終了します。")
            return

        # 既知 URL 取得
        known_urls = get_known_urls(client)
        logger.info("既知 URL: %d 件", len(known_urls))

        # 新着エントリ処理
        processed_count = process_entries(
            entries=entries,
            known_urls=known_urls,
            client=client,
            session=session,
            dry_run=args.dry_run,
            limit=args.limit,
        )

        logger.info("処理完了: %d 件", processed_count)

        # 新着があれば LINE 通知
        if processed_count > 0 and not args.dry_run:
            try:
                send_alert(
                    title="MLIT RSS 新着",
                    message=f"国交省 RSS から新着海事規制 {processed_count} 件を検出・保存しました。",
                    severity="info",
                )
            except Exception as e:
                logger.warning("LINE 通知エラー: %s", e)

    except Exception as e:
        logger.error("予期しないエラー: %s", e, exc_info=True)
        try:
            send_scraper_error(
                scraper_name="scrape_mlit_rss",
                error=e,
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
