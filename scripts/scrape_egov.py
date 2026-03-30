"""
e-Gov パブリックコメント スクレイパー
=====================================
e-Gov（意見公募手続）サイトから海事関連のパブコメ情報を取得し、
Supabase に保存する。パブコメは省令施行前の情報であり、
事前準備のために severity="upcoming" として扱う。

処理フロー:
  1) e-Gov パブコメ一覧ページを取得（募集中 + 結果公示の両方）
  2) 海事関連キーワードでフィルタリング
  3) 各パブコメの詳細ページからメタデータを抽出
  4) Supabase の regulations テーブルに upsert
  5) 新着があれば LINE 通知

対象サイト:
  https://public-comment.e-gov.go.jp/

使い方:
  python scrape_egov.py
  python scrape_egov.py --dry-run
  python scrape_egov.py --limit 10
"""

import argparse
import hashlib
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlencode

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# パス設定（スクリプト直下から utils を import）
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(__file__))

from utils.supabase_client import SupabaseClient  # type: ignore
from utils.line_notify import send_alert, send_scraper_error  # type: ignore
from utils.stealth_fetcher import stealth_get  # type: ignore

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scrape_egov")

# ---------------------------------------------------------------------------
# 定数・設定
# ---------------------------------------------------------------------------

# e-Gov パブコメ一覧 URL
# CLASSNAME=PCMMSTLIST: 一覧表示
# Mode=0: 募集中、Mode=1: 結果公示
EGOV_BASE_URL = "https://public-comment.e-gov.go.jp/servlet/Public"

# 一覧ページ URL（募集中）
EGOV_LIST_URLS = [
    # 募集中のパブコメ一覧
    f"{EGOV_BASE_URL}?CLASSNAME=PCMMSTLIST&id=&Mode=0",
    # 結果公示（直近のもの）
    f"{EGOV_BASE_URL}?CLASSNAME=PCMMSTLIST&id=&Mode=1",
]

# 海事関連キーワード（フィルタリング用）
MARITIME_KEYWORDS = [
    "海事", "船舶", "船員", "海上", "港湾",
    "SOLAS", "MARPOL", "海洋",
    "国土交通省海事局", "海事局",
    "船舶安全法", "船員法", "海上運送法",
    "船舶職員", "小型船舶", "海上交通",
    "港則", "水先", "海難審判",
    "造船", "船級", "船籍",
    "IMO", "STCW", "バラスト水",
]

SOURCE_PREFIX = "EGOV"
REQUEST_INTERVAL_SEC = 3  # リクエスト間隔（秒）


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def is_maritime_related(title: str, department: str = "") -> bool:
    """タイトルまたは担当省庁が海事関連キーワードを含むか判定する。"""
    text = f"{title} {department}".lower()
    for keyword in MARITIME_KEYWORDS:
        if keyword.lower() in text:
            return True
    return False


def generate_source_id(published_date: Optional[datetime], counter: int) -> str:
    """
    source_id を生成する。
    形式: EGOV-{YYYYMMDD}-{連番3桁}
    例: EGOV-20260329-001
    """
    if published_date:
        date_str = published_date.strftime("%Y%m%d")
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{SOURCE_PREFIX}-{date_str}-{counter:03d}"


def generate_source_id_from_url(url: str) -> str:
    """
    URL からハッシュベースの安定した source_id を生成する。
    同じ URL は常に同じ source_id を返す（冪等性）。
    形式: EGOV-{URLハッシュ先頭8文字}
    """
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{SOURCE_PREFIX}-{url_hash}"


def parse_japanese_date(date_str: str) -> Optional[datetime]:
    """
    日本語の日付文字列を datetime に変換する。
    対応形式:
      - 令和6年3月29日
      - 2026年3月29日
      - 2026/03/29
      - 2026-03-29
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # 令和→西暦変換
    reiwa_match = re.search(r"令和(\d+)年(\d+)月(\d+)日", date_str)
    if reiwa_match:
        year = int(reiwa_match.group(1)) + 2018
        month = int(reiwa_match.group(2))
        day = int(reiwa_match.group(3))
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None

    # 西暦（漢字区切り）
    kanji_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_str)
    if kanji_match:
        try:
            return datetime(
                int(kanji_match.group(1)),
                int(kanji_match.group(2)),
                int(kanji_match.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None

    # スラッシュ or ハイフン区切り
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


# ---------------------------------------------------------------------------
# e-Gov ページ解析
# ---------------------------------------------------------------------------

def fetch_listing_page(url: str) -> Optional[str]:
    """
    e-Gov 一覧ページの HTML を取得する。
    stealth_get を使用してアクセス制限を回避する。

    Returns:
        HTML 文字列（失敗時は None）
    """
    try:
        resp = stealth_get(url, timeout=30)
        resp.raise_for_status()
        logger.info("一覧ページ取得完了: %s (%d bytes)", url, len(resp.content))
        return resp.text
    except Exception as e:
        logger.error("一覧ページ取得エラー: %s — %s", url, e)
        return None


def parse_listing_page(html: str, mode: int = 0) -> list[dict]:
    """
    e-Gov パブコメ一覧ページの HTML を解析し、個別案件情報を抽出する。

    e-Gov の一覧ページは table ベースのレイアウト。
    各案件は table 行として表示され、以下の情報を含む:
      - 案件名（title）+ 詳細ページへのリンク
      - 担当省庁（department）
      - 受付期間 / 意見提出期限（comment_deadline）

    Args:
        html: 一覧ページの HTML
        mode: 0=募集中、1=結果公示

    Returns:
        案件情報の辞書リスト
    """
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []

    # e-Gov のパブコメ一覧は table 要素で構成される
    # 複数のパターンに対応（サイト構造変更への耐性）

    # パターン 1: table 内の行を探索
    # class 名やID はサイト構造に依存するため、複数戦略で探索
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            # リンクを含むセルを探す
            link_tag = row.find("a", href=True)
            if not link_tag:
                continue

            href = link_tag.get("href", "")
            title = link_tag.get_text(strip=True)

            # パブコメ詳細ページへのリンクかチェック
            # 典型的なパターン: PCMMSTDETAIL を含む URL
            if not title or len(title) < 5:
                continue

            # 詳細ページの URL を構築
            if "CLASSNAME" in href or "servlet" in href:
                detail_url = urljoin(EGOV_BASE_URL, href)
            elif href.startswith("http"):
                detail_url = href
            else:
                detail_url = urljoin(EGOV_BASE_URL, href)

            # セルからメタデータを抽出
            cell_texts = [c.get_text(strip=True) for c in cells]
            department = ""
            deadline_str = ""

            for text in cell_texts:
                # 省庁名の検出（「省」「庁」「局」「委員会」を含むテキスト）
                if re.search(r"(省|庁|局|委員会)$", text) and len(text) < 30:
                    department = text
                # 日付の検出
                if re.search(r"\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2}", text):
                    if not deadline_str:
                        deadline_str = text

            item: dict = {
                "title": title,
                "url": detail_url,
                "department": department,
                "deadline_str": deadline_str,
                "status": "募集中" if mode == 0 else "終了",
            }
            items.append(item)

    # パターン 2: div/dl ベースのリスト構造
    if not items:
        # 案件リストが div や dl で構成されている場合
        for dl in soup.find_all("dl"):
            dt = dl.find("dt")
            dd = dl.find("dd")
            if not dt:
                continue

            link_tag = dt.find("a", href=True)
            if link_tag:
                title = link_tag.get_text(strip=True)
                href = link_tag.get("href", "")
                detail_url = urljoin(EGOV_BASE_URL, href)
            else:
                title = dt.get_text(strip=True)
                detail_url = ""

            if not title or len(title) < 5:
                continue

            department = ""
            deadline_str = ""
            if dd:
                dd_text = dd.get_text(strip=True)
                dept_match = re.search(r"([\w]+(?:省|庁|局|委員会))", dd_text)
                if dept_match:
                    department = dept_match.group(1)
                date_match = re.search(
                    r"(\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2}日?)", dd_text
                )
                if date_match:
                    deadline_str = date_match.group(1)

            item = {
                "title": title,
                "url": detail_url,
                "department": department,
                "deadline_str": deadline_str,
                "status": "募集中" if mode == 0 else "終了",
            }
            items.append(item)

    # パターン 3: リンクテキストからの直接抽出（フォールバック）
    if not items:
        logger.info("table/dl パターンで案件が見つからず。リンク直接抽出を試行。")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            title = a_tag.get_text(strip=True)

            # パブコメ詳細っぽいリンクをフィルタ
            if (
                title
                and len(title) > 10
                and ("PCMMSTDETAIL" in href or "detail" in href.lower())
            ):
                detail_url = urljoin(EGOV_BASE_URL, href)
                items.append({
                    "title": title,
                    "url": detail_url,
                    "department": "",
                    "deadline_str": "",
                    "status": "募集中" if mode == 0 else "終了",
                })

    logger.info("一覧ページから %d 件の案件を抽出 (mode=%d)", len(items), mode)
    return items


def fetch_detail_page(url: str) -> Optional[dict]:
    """
    パブコメ詳細ページから追加メタデータを抽出する。

    Returns:
        {
            "department": str,       # 担当省庁
            "comment_deadline": str,  # 意見提出期限（文字列）
            "published_at": str,      # 公示日（文字列）
            "summary": str,           # 要約/概要
        }
        失敗時は None
    """
    try:
        time.sleep(REQUEST_INTERVAL_SEC)
        resp = stealth_get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("詳細ページ取得エラー: %s — %s", url, e)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    detail: dict = {
        "department": "",
        "comment_deadline": "",
        "published_at": "",
        "summary": "",
    }

    # テーブルベースの詳細情報を解析
    # e-Gov の詳細ページは「項目名: 値」形式のテーブルが多い
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            header = row.find("th")
            value = row.find("td")
            if not header or not value:
                continue

            header_text = header.get_text(strip=True)
            value_text = value.get_text(strip=True)

            if "案件番号" in header_text or "受付番号" in header_text:
                pass  # 案件番号は source_id に使わない（独自体系を使用）
            elif "所管" in header_text or "省庁" in header_text or "担当" in header_text:
                detail["department"] = value_text
            elif "意見提出期限" in header_text or "締切" in header_text or "受付終了" in header_text:
                detail["comment_deadline"] = value_text
            elif "公示日" in header_text or "掲載日" in header_text or "開始日" in header_text:
                detail["published_at"] = value_text
            elif "概要" in header_text or "趣旨" in header_text or "内容" in header_text:
                # 概要は長くなりすぎないよう 500 文字に制限
                detail["summary"] = value_text[:500]

    # dl ベースの詳細情報も探索
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            dt_text = dt.get_text(strip=True)
            dd_text = dd.get_text(strip=True)

            if "所管" in dt_text or "省庁" in dt_text or "担当" in dt_text:
                detail["department"] = dd_text
            elif "意見提出期限" in dt_text or "締切" in dt_text:
                detail["comment_deadline"] = dd_text
            elif "公示日" in dt_text or "掲載日" in dt_text:
                detail["published_at"] = dd_text
            elif "概要" in dt_text or "趣旨" in dt_text:
                detail["summary"] = dd_text[:500]

    return detail


# ---------------------------------------------------------------------------
# Supabase 操作
# ---------------------------------------------------------------------------

def get_known_urls(client: SupabaseClient) -> set[str]:
    """
    Supabase から EGOV ソースの既知 URL を取得する。
    """
    if not client._configured:
        logger.warning("Supabase 未設定: 既知 URL を取得できません。")
        return set()

    try:
        import requests as req
        resp = req.get(
            f"{client.url}/rest/v1/regulations",
            params={
                "source": "eq.EGOV",
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
    url: str,
    department: str,
    comment_deadline: Optional[datetime],
    published_at: Optional[datetime],
    status: str,
    summary: str = "",
) -> dict:
    """Supabase に保存するレコードを構築する。"""
    now_iso = datetime.now(timezone.utc).isoformat()

    record: dict = {
        "source_id": source_id,
        "source": "EGOV",
        "title": title,
        "url": url,
        "published_at": published_at.isoformat() if published_at else None,
        "scraped_at": now_iso,
        # パブコメは施行前の情報 → severity="upcoming"
        "severity": "upcoming",
        "category": "パブリックコメント",
        "summary_ja": summary if summary else f"【{status}】{department} — {title}",
        # パブコメ固有メタデータを processing_notes に格納
        "processing_notes": (
            f"担当省庁: {department}\n"
            f"意見提出期限: {comment_deadline.strftime('%Y-%m-%d') if comment_deadline else '不明'}\n"
            f"ステータス: {status}"
        ),
    }

    # effective_date にパブコメ期限を設定（期限後に施行される可能性が高い）
    if comment_deadline:
        record["effective_date"] = comment_deadline.isoformat()

    return record


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def scrape_egov(dry_run: bool = False, limit: int = 20) -> int:
    """
    e-Gov パブコメスクレイピングのメイン処理。

    Returns:
        処理済み件数
    """
    client = SupabaseClient()

    # 既知 URL 取得
    known_urls = get_known_urls(client)
    logger.info("既知 URL: %d 件", len(known_urls))

    all_items: list[dict] = []

    # 各一覧ページを取得
    for i, list_url in enumerate(EGOV_LIST_URLS):
        mode = i  # 0=募集中、1=結果公示
        logger.info("一覧ページ取得中 (mode=%d): %s", mode, list_url)

        html = fetch_listing_page(list_url)
        if not html:
            logger.warning("一覧ページの取得に失敗: %s", list_url)
            continue

        items = parse_listing_page(html, mode=mode)
        all_items.extend(items)

        # リクエスト間隔
        if i < len(EGOV_LIST_URLS) - 1:
            time.sleep(REQUEST_INTERVAL_SEC)

    logger.info("全一覧ページから %d 件の案件を抽出", len(all_items))

    # 海事関連フィルタリング
    maritime_items = [
        item for item in all_items
        if is_maritime_related(item["title"], item.get("department", ""))
    ]
    logger.info("海事関連案件: %d 件", len(maritime_items))

    if not maritime_items:
        logger.info("海事関連のパブコメなし。終了します。")
        return 0

    # 処理
    processed = 0
    date_counter: dict[str, int] = {}

    for item in maritime_items:
        if processed >= limit:
            logger.info("処理件数上限 (%d 件) に達しました。", limit)
            break

        url = item["url"]
        title = item["title"]

        # 既知 URL はスキップ
        if url in known_urls:
            logger.debug("既知 URL をスキップ: %s", url)
            continue

        logger.info("新着パブコメ処理中: %s", title[:60])

        # 詳細ページからメタデータを取得
        detail: Optional[dict] = None
        if not dry_run and url:
            detail = fetch_detail_page(url)

        # メタデータをマージ
        department = item.get("department", "")
        deadline_str = item.get("deadline_str", "")
        published_at_str = ""
        summary = ""

        if detail:
            if detail.get("department"):
                department = detail["department"]
            if detail.get("comment_deadline"):
                deadline_str = detail["comment_deadline"]
            if detail.get("published_at"):
                published_at_str = detail["published_at"]
            if detail.get("summary"):
                summary = detail["summary"]

        # 日付パース
        comment_deadline = parse_japanese_date(deadline_str)
        published_at = parse_japanese_date(published_at_str)

        # source_id 生成（URL ベースで冪等性を確保）
        source_id = generate_source_id_from_url(url) if url else generate_source_id(
            published_at, processed + 1
        )

        # レコード構築
        record = build_regulation_record(
            source_id=source_id,
            title=title,
            url=url,
            department=department,
            comment_deadline=comment_deadline,
            published_at=published_at,
            status=item.get("status", "不明"),
            summary=summary,
        )

        if not dry_run:
            success = client.upsert_regulation(record)
            if success:
                logger.info("Supabase 保存完了: %s", source_id)
            else:
                logger.error("Supabase 保存失敗: %s", source_id)
                try:
                    send_scraper_error(
                        scraper_name="scrape_egov",
                        error=Exception(f"Supabase upsert failed for {source_id}"),
                        context={"url": url, "source_id": source_id},
                    )
                except Exception:
                    pass
        else:
            logger.info(
                "[dry-run] レコード（保存スキップ）: source_id=%s, title=%s, dept=%s",
                source_id,
                title[:40],
                department,
            )

        processed += 1

    return processed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="e-Gov パブリックコメント スクレイパー — 海事関連パブコメ収集"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="詳細ページ取得・DB 書き込みをスキップ",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        metavar="N",
        help="処理件数の上限（デフォルト: 20）",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=== DRY RUN モード ===")

    logger.info("e-Gov パブコメスクレイパー開始 (limit=%d)", args.limit)

    try:
        processed_count = scrape_egov(
            dry_run=args.dry_run,
            limit=args.limit,
        )

        logger.info("処理完了: %d 件", processed_count)

        # 新着があれば LINE 通知
        if processed_count > 0 and not args.dry_run:
            try:
                send_alert(
                    title="e-Gov パブコメ新着",
                    message=(
                        f"e-Gov パブリックコメントから海事関連 "
                        f"{processed_count} 件を検出・保存しました。"
                    ),
                    severity="info",
                )
            except Exception as e:
                logger.warning("LINE 通知エラー: %s", e)

    except Exception as e:
        logger.error("予期しないエラー: %s", e, exc_info=True)
        try:
            send_scraper_error(
                scraper_name="scrape_egov",
                error=e,
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
