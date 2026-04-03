"""
check_publication_updates.py — 書籍最新版自動チェッカー
========================================================
各書籍の発行元サイトから最新版情報をフェッチし、publications テーブルの
edition と比較して差分があれば更新する。

実装済みチェッカー:
  - IMO Just Published
  - 日本水路協会 (JHA) ショップ検索
  - 海文堂出版 (Kaibundo) 法規・条約カテゴリ

使い方:
    python scripts/check_publication_updates.py          # 本番実行
    python scripts/check_publication_updates.py --dry-run # ドライラン
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import argparse
import logging
import re
import time
import urllib.parse
from typing import Optional

import requests
from bs4 import BeautifulSoup

from utils.line_notify import send_alert

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[PubCheck] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ===========================================================================
# 共通ヘルパー
# ===========================================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}


def reiwa_to_year(reiwa_year: int) -> int:
    """和暦（令和）を西暦に変換。令和1年=2019"""
    return 2018 + reiwa_year


def _extract_japanese_date(text: str) -> Optional[str]:
    """
    日本語テキストから刊行日を推定して YYYY-MM-DD を返す。
    例: "2026年2月刊" → "2026-02-01", "2025年3月下旬刊" → "2025-03-15"
    """
    # 西暦パターン: "2026年3月" or "2026年3月下旬"
    m = re.search(r'(\d{4})年(\d{1,2})月', text)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        return f"{year:04d}-{month:02d}-01"

    # 令和パターン: "令和8年" → 2026
    m = re.search(r'令和(\d{1,2})年', text)
    if m:
        year = reiwa_to_year(int(m.group(1)))
        return f"{year:04d}-01-01"

    return None


# ===========================================================================
# IMO Just Published チェッカー — publication_id マッピング
# ===========================================================================

# IMO タイトルに含まれるキーワード → DB の publication_id
IMO_TITLE_MAP: dict[str, str] = {
    "SOLAS": "SOLAS_CONSOLIDATED",
    "MARPOL": "MARPOL_CONSOLIDATED",
    "COLREG": "IMO_COLREG",
    "STCW": "STCW_CONVENTION",
    "ISM Code": "ISM_CODE",
    "ISPS Code": "ISPS_CODE",
    "IMDG Code": "IMDG_CODE",
    "IMSBC Code": "IMSBC_CODE",
    "IGF Code": "IGF_CODE",
    "IGC Code": "IGC_CODE",
    "IBC Code": "IBC_CODE",
    "BCH Code": "BCH_CODE",
    "LSA Code": "LSA_CODE",
    "FSS Code": "FSS_CODE",
    "FTP Code": "FTP_CODE",
    "CSS Code": "CSS_CODE",
    "IAMSAR": "IAMSAR_MANUAL",
    "MLC": "MLC_2006",
    "BWM Convention": "BWM_CONVENTION",
    "Load Lines": "LOAD_LINES_CONVENTION",
    "Grain Code": "GRAIN_CODE",
    "Polar Code": "POLAR_CODE",
    "GBS": "GBS_STANDARDS",
}


def _match_imo_publication_id(title: str) -> Optional[str]:
    """IMO タイトルから DB の publication_id を推定"""
    for keyword, pub_id in IMO_TITLE_MAP.items():
        if keyword.lower() in title.lower():
            return pub_id
    return None


# ===========================================================================
# Publisher チェッカー実装
# ===========================================================================

def check_imo_publications() -> list[dict]:
    """
    IMO の Just Published ページをスクレイプし、最新刊行物を返す。
    URL: https://www.imo.org/en/publications/Pages/JustPublished.aspx
    """
    url = "https://www.imo.org/en/publications/Pages/JustPublished.aspx"
    results: list[dict] = []

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"[IMO] ページ取得失敗: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # IMO Just Published ページは書籍をリスト/カード形式で掲載
    # 一般的なパターン: テーブル行または div 要素に書籍情報
    items_found = 0

    # パターン1: テーブル行から抽出
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        title_text = cells[0].get_text(strip=True)
        if not title_text:
            continue
        items_found += 1

        # Edition 情報を抽出 (例: "COLREG 2026 Edition")
        edition_match = re.search(r'(\d{4})\s*Edition', title_text, re.IGNORECASE)
        edition_str = edition_match.group(0) if edition_match else ""

        # 日付を抽出（あれば）
        date_str = None
        for cell in cells:
            cell_text = cell.get_text(strip=True)
            # ISO 形式 or "24 March 2026" 等
            dm = re.search(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', cell_text, re.IGNORECASE)
            if dm:
                from datetime import datetime
                try:
                    parsed = datetime.strptime(dm.group(0), "%d %B %Y")
                    date_str = parsed.strftime("%Y-%m-%d")
                except ValueError:
                    pass

        pub_id = _match_imo_publication_id(title_text)
        if pub_id:
            results.append({
                "publication_id": pub_id,
                "latest_edition": edition_str or title_text,
                "latest_date": date_str,
            })
        else:
            logger.info(f"[IMO] DB未登録の書籍を検出（スキップ）: {title_text}")

    # パターン2: div/article ベースのレイアウト（テーブルが無い場合）
    if items_found == 0:
        for item in soup.select(".dfwp-item, .slm-layout-main .item, article, .publication-item"):
            title_el = item.find(["h2", "h3", "h4", "a", "strong"])
            if not title_el:
                continue
            title_text = title_el.get_text(strip=True)
            if not title_text:
                continue
            items_found += 1

            edition_match = re.search(r'(\d{4})\s*Edition', title_text, re.IGNORECASE)
            edition_str = edition_match.group(0) if edition_match else ""

            # 日付を本文から抽出
            date_str = None
            full_text = item.get_text(" ", strip=True)
            dm = re.search(
                r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
                full_text, re.IGNORECASE,
            )
            if dm:
                from datetime import datetime
                try:
                    parsed = datetime.strptime(dm.group(0), "%d %B %Y")
                    date_str = parsed.strftime("%Y-%m-%d")
                except ValueError:
                    pass

            pub_id = _match_imo_publication_id(title_text)
            if pub_id:
                results.append({
                    "publication_id": pub_id,
                    "latest_edition": edition_str or title_text,
                    "latest_date": date_str,
                })
            else:
                logger.info(f"[IMO] DB未登録の書籍を検出（スキップ）: {title_text}")

    logger.info(f"[IMO] ページから {items_found} 件を検出、{len(results)} 件が DB マッチ")
    return results


# ---------------------------------------------------------------------------
# JHA (日本水路協会) チェッカー
# ---------------------------------------------------------------------------

JHA_SEARCH_KEYWORDS: list[str] = ["潮汐表", "灯台表", "水路誌", "天測暦", "海図総目録"]

# JHA タイトルキーワード → DB の publication_id
JHA_TITLE_MAP: dict[str, str] = {
    "潮汐表": "JHA_TIDE_TABLE",
    "灯台表": "JHA_LIGHT_LIST",
    "水路誌": "JHA_SAILING_DIRECTIONS",
    "天測暦": "JHA_NAUTICAL_ALMANAC",
    "海図総目録": "JHO_CHART_CATALOG",
    "距離表": "JHA_DISTANCE_TABLE",
}


def _match_jha_publication_id(title: str) -> Optional[str]:
    """JHA タイトルから DB の publication_id を推定"""
    for keyword, pub_id in JHA_TITLE_MAP.items():
        if keyword in title:
            return pub_id
    return None


def check_jho_publications() -> list[dict]:
    """
    日本水路協会のショップ検索をスクレイプし、各カテゴリの最新版を返す。
    URL: https://www.jha.or.jp/shop/index.php?main_page=advanced_search_result&keyword={keyword}&language=jp
    """
    results: list[dict] = []
    seen_pub_ids: set[str] = set()

    for keyword in JHA_SEARCH_KEYWORDS:
        encoded_kw = urllib.parse.quote(keyword)
        url = (
            f"https://www.jha.or.jp/shop/index.php?"
            f"main_page=advanced_search_result&keyword={encoded_kw}&language=jp"
        )

        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[JHA] '{keyword}' 検索失敗: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # JHA ショップの検索結果は商品リスト形式
        items_found = 0
        for item in soup.select(".productListing-data, .product-listing tr, .itemTitle, .product_name, li.product"):
            title_el = item.find(["a", "h3", "h4", "strong"])
            if not title_el:
                # テーブル行の場合、最初のリンクを探す
                title_el = item.find("a")
            if not title_el:
                continue

            title_text = title_el.get_text(strip=True)
            if not title_text or keyword not in title_text:
                continue

            items_found += 1
            full_text = item.get_text(" ", strip=True)

            # 和暦から年を抽出: "令和9年" → 2027
            edition_str = title_text
            reiwa_match = re.search(r'令和(\d{1,2})年', title_text)
            if reiwa_match:
                western_year = reiwa_to_year(int(reiwa_match.group(1)))
                edition_str = f"{western_year}年版 ({title_text})"

            # 西暦パターン
            year_match = re.search(r'(\d{4})年版', title_text)
            if year_match:
                edition_str = title_text

            # 刊行日を推定
            date_str = _extract_japanese_date(full_text)

            pub_id = _match_jha_publication_id(title_text)
            if pub_id and pub_id not in seen_pub_ids:
                seen_pub_ids.add(pub_id)
                results.append({
                    "publication_id": pub_id,
                    "latest_edition": edition_str,
                    "latest_date": date_str,
                })
            elif not pub_id:
                logger.info(f"[JHA] DB未登録の書籍を検出（スキップ）: {title_text}")

        logger.info(f"[JHA] '{keyword}' 検索: {items_found} 件ヒット")

        # サーバー負荷軽減
        time.sleep(3)

    logger.info(f"[JHA] 合計 {len(results)} 件の更新情報を取得")
    return results


# ---------------------------------------------------------------------------
# 海文堂出版 (Kaibundo) チェッカー
# ---------------------------------------------------------------------------

# 海文堂タイトルキーワード → DB の publication_id
KAIBUNDO_TITLE_MAP: dict[str, str] = {
    "海上衝突予防法": "JPN_COLREG_COMMENTARY",
    "海事法令集": "JPN_SHIP_SAFETY_ACT",
    "船員法": "JPN_SEAFARERS_ACT",
    "港則法": "JPN_PORT_REGULATIONS",
    "海上交通安全法": "JPN_MARITIME_TRAFFIC_SAFETY",
    "航海便覧": "NAVIGATION_HANDBOOK",
    "緊急入域ハンドブック": "EMERGENCY_ENTRY_HANDBOOK",
    "ISMコード": "ISM_GUIDE_KAIBUNDO",
    "訓練手引書": "SOLAS_TRAINING_MANUAL",
    "防火訓練": "FIRE_SAFETY_TRAINING_MANUAL",
    "油濁防止緊急措置手引書": "SOPEP",
    "廃棄物汚染防止規程": "GARBAGE_MANAGEMENT_PLAN",
}


def _match_kaibundo_publication_id(title: str) -> Optional[str]:
    """海文堂タイトルから DB の publication_id を推定。マッチしない場合は None"""
    for keyword, pub_id in KAIBUNDO_TITLE_MAP.items():
        if keyword in title:
            return pub_id
    return None


def check_kaibundo_publications() -> list[dict]:
    """
    海文堂出版の法規・条約カテゴリページをスクレイプし、書籍情報を返す。
    URL: https://www.kaibundo.jp/category/kaiji/kaiji-houki/

    DB の publications テーブルに存在しない書籍を検出した場合は、
    ログに記録するだけで DB には書き込まない（手動で追加判断するため）。
    """
    url = "https://www.kaibundo.jp/category/kaiji/kaiji-houki/"
    results: list[dict] = []

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"[海文堂] ページ取得失敗: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # 海文堂は WordPress ベースの EC サイト — 商品カード/リストから抽出
    items_found = 0
    for item in soup.select(
        "article, .product, .post, .entry, "
        ".woocommerce-loop-product, li.product, "
        ".product-item, .book-item"
    ):
        title_el = item.find(["h2", "h3", "h4", "a.woocommerce-LoopProduct-link"])
        if not title_el:
            title_el = item.find("a")
        if not title_el:
            continue

        title_text = title_el.get_text(strip=True)
        if not title_text:
            continue

        items_found += 1
        full_text = item.get_text(" ", strip=True)

        # 版情報を抽出: "第25版", "2026年版", "22訂版" 等
        edition_str = title_text
        ver_match = re.search(r'第\s*(\d+)\s*版', title_text)
        rev_match = re.search(r'(\d+)\s*訂版', title_text)
        year_match = re.search(r'(\d{4})年版', title_text)

        if ver_match:
            edition_str = f"第{ver_match.group(1)}版"
        elif rev_match:
            edition_str = f"{rev_match.group(1)}訂版"
        elif year_match:
            edition_str = f"{year_match.group(1)}年版"

        # 刊行日を推定
        date_str = _extract_japanese_date(full_text)

        # 価格を抽出（ログ用）
        price_match = re.search(r'[¥￥][\s,]*([0-9,]+)', full_text)
        price_str = price_match.group(0) if price_match else "不明"

        pub_id = _match_kaibundo_publication_id(title_text)
        if pub_id:
            results.append({
                "publication_id": pub_id,
                "latest_edition": edition_str,
                "latest_date": date_str,
            })
            logger.info(f"[海文堂] DBマッチ: {title_text} → {pub_id} (価格: {price_str})")
        else:
            # DB に存在しない書籍はログ記録のみ
            logger.info(
                f"[海文堂] DB未登録の書籍を検出（手動追加要検討）: "
                f"{title_text} / 版: {edition_str} / 刊行: {date_str or '不明'} / 価格: {price_str}"
            )

    logger.info(f"[海文堂] ページから {items_found} 件を検出、{len(results)} 件が DB マッチ")
    return results


# ---------------------------------------------------------------------------
# Stub チェッカー（未実装 — 既存スクレイパーがカバーまたは将来実装）
# ---------------------------------------------------------------------------

def check_nk_publications() -> list[dict]:
    """
    ClassNK の最新版をチェック。
    既存の scrape_nk.py がカバーしているため stub 維持。
    """
    logger.info("[ClassNK] 既存 scrape_nk.py がカバー — スキップ")
    return []


# ---------------------------------------------------------------------------
# 成山堂書店 (Seizando) チェッカー
# ---------------------------------------------------------------------------

# 成山堂タイトルキーワード → DB の publication_id
SEIZANDO_TITLE_MAP: dict[str, str] = {
    "海事法令集": "JPN_SHIP_SAFETY_ACT",
    "船員法": "JPN_SEAFARERS_ACT",
    "海上衝突予防法": "JPN_COLREG_COMMENTARY",
    "港則法": "JPN_PORT_REGULATIONS",
    "海上交通安全法": "JPN_MARITIME_TRAFFIC_SAFETY",
    "ISMコード": "ISM_GUIDE_KAIBUNDO",
    "訓練手引書": "SOLAS_TRAINING_MANUAL",
    "防火訓練": "FIRE_SAFETY_TRAINING_MANUAL",
    "航海便覧": "NAVIGATION_HANDBOOK",
    "国際信号書": "NGA_INT_CODE_OF_SIGNALS",
    "STCW": "STCW_CODE",
    "船舶安全法": "JPN_SHIP_SAFETY_ACT",
}


def _match_seizando_publication_id(title: str) -> Optional[str]:
    """成山堂タイトルから DB の publication_id を推定"""
    for keyword, pub_id in SEIZANDO_TITLE_MAP.items():
        if keyword in title:
            return pub_id
    return None


# 成山堂の検索カテゴリURL
SEIZANDO_URLS = [
    # 海事法規
    "https://www.seizando.co.jp/book/genre/1-1/",
    # 航海・運用
    "https://www.seizando.co.jp/book/genre/1-2/",
    # 船舶・海洋工学
    "https://www.seizando.co.jp/book/genre/1-3/",
]


def check_seizando_publications() -> list[dict]:
    """
    成山堂書店の海事カテゴリページをスクレイプし、書籍情報を返す。
    海文堂にない書籍を成山堂でカバーする。
    """
    results: list[dict] = []
    seen_ids: set[str] = set()

    for url in SEIZANDO_URLS:
        try:
            time.sleep(3)  # 礼儀正しく
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[成山堂] ページ取得失敗 ({url}): {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        items_found = 0
        for item in soup.select(
            "article, .book-item, .product, .post, .entry, "
            "li.book, .book-list-item, .item, div.book"
        ):
            title_el = item.find(["h2", "h3", "h4", "a"])
            if not title_el:
                continue

            title_text = title_el.get_text(strip=True)
            if not title_text:
                continue

            items_found += 1
            full_text = item.get_text(" ", strip=True)

            # 版情報を抽出
            edition_str = title_text
            ver_match = re.search(r'第\s*(\d+)\s*版', title_text)
            rev_match = re.search(r'(\d+)\s*訂版', title_text)
            year_match = re.search(r'(\d{4})年版', title_text)

            if ver_match:
                edition_str = f"第{ver_match.group(1)}版"
            elif rev_match:
                edition_str = f"{rev_match.group(1)}訂版"
            elif year_match:
                edition_str = f"{year_match.group(1)}年版"

            date_str = _extract_japanese_date(full_text)

            pub_id = _match_seizando_publication_id(title_text)
            if pub_id and pub_id not in seen_ids:
                seen_ids.add(pub_id)
                results.append({
                    "publication_id": pub_id,
                    "latest_edition": edition_str,
                    "latest_date": date_str,
                })
                logger.info(f"[成山堂] DBマッチ: {title_text} → {pub_id}")
            elif not pub_id:
                logger.debug(
                    f"[成山堂] DB未登録: {title_text} / 版: {edition_str}"
                )

        logger.info(f"[成山堂] {url} から {items_found} 件検出、{len(results)} 件累計マッチ")

    return results


def check_ukho_publications() -> list[dict]:
    """
    UKHO (UK Hydrographic Office) の最新版をチェック。
    Returns: [{"publication_id": "ADMIRALTY_MARINERS_HANDBOOK", "latest_edition": "...", "latest_date": "..."}]
    """
    # TODO: 将来 UKHO サイトのスクレイピングを実装
    logger.info("[UKHO] スクレイパー未実装 — スキップ")
    return []


def check_ilo_publications() -> list[dict]:
    """
    ILO (MLC 2006) の最新版をチェック。
    Returns: [{"publication_id": "MLC_2006", "latest_edition": "...", "latest_date": "..."}]
    """
    # TODO: 将来 ILO サイトのスクレイピングを実装
    logger.info("[ILO] スクレイパー未実装 — スキップ")
    return []


# ---------------------------------------------------------------------------
# チェッカーレジストリ
# ---------------------------------------------------------------------------

CHECKERS: dict[str, callable] = {
    "IMO": check_imo_publications,
    "海上保安庁 水路部": check_jho_publications,
    "日本水路協会": check_jho_publications,
    "海文堂": check_kaibundo_publications,
    "成山堂": check_seizando_publications,
    "海文堂 / 成山堂": check_seizando_publications,  # 両方扱う出版社
    "ClassNK": check_nk_publications,
    "NK": check_nk_publications,
    "UKHO": check_ukho_publications,
    "ILO": check_ilo_publications,
    "情報通信振興会": check_seizando_publications,  # フォールバック
}


# ===========================================================================
# Supabase 連携
# ===========================================================================

class PublicationDBClient:
    """publications / ship_publications テーブル操作クライアント"""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def get_all_publications(self) -> list[dict]:
        """publications テーブルの全レコードを取得"""
        try:
            resp = requests.get(
                f"{self.url}/rest/v1/publications",
                params={"select": "id,title,publisher,current_edition,current_edition_date"},
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"publications テーブル取得失敗: {e}")
            return []

    def update_publication_edition(
        self,
        publication_id: str,
        latest_edition: str,
        latest_date: Optional[str],
    ) -> bool:
        """publications テーブルの edition を更新"""
        payload: dict = {"current_edition": latest_edition}
        if latest_date:
            payload["current_edition_date"] = latest_date

        try:
            resp = requests.patch(
                f"{self.url}/rest/v1/publications",
                params={"id": f"eq.{publication_id}"},
                json=payload,
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Updated edition: {publication_id} -> {latest_edition}")
            return True
        except requests.RequestException as e:
            logger.error(f"edition 更新失敗 ({publication_id}): {e}")
            return False

    def flag_needs_update(self, publication_id: str) -> bool:
        """ship_publications テーブルの該当レコードを needs_update=true に更新"""
        try:
            resp = requests.patch(
                f"{self.url}/rest/v1/ship_publications",
                params={"publication_id": f"eq.{publication_id}"},
                json={"needs_update": True},
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Flagged needs_update: publication_id={publication_id}")
            return True
        except requests.RequestException as e:
            logger.error(f"needs_update フラグ設定失敗 ({publication_id}): {e}")
            return False


# ===========================================================================
# メインロジック
# ===========================================================================

def run_checkers() -> list[dict]:
    """
    全チェッカーを実行し、最新版情報を収集する。
    Returns: [{"publication_id": ..., "latest_edition": ..., "latest_date": ...}]
    """
    all_updates: list[dict] = []
    executed: set[int] = set()  # 同一関数の重複実行防止

    for publisher, checker_fn in CHECKERS.items():
        fn_id = id(checker_fn)
        if fn_id in executed:
            continue
        executed.add(fn_id)

        logger.info(f"--- チェッカー実行: {publisher} ---")
        try:
            updates = checker_fn()
            if updates:
                all_updates.extend(updates)
                logger.info(f"  {publisher}: {len(updates)} 件の更新情報を検出")
        except Exception as e:
            logger.error(f"  {publisher} チェッカーでエラー: {e}")

    return all_updates


def compare_and_update(
    db: PublicationDBClient,
    latest_updates: list[dict],
    dry_run: bool = False,
) -> list[dict]:
    """
    DB の現在版と最新版を比較し、差分があれば更新する。

    Returns: 更新された書籍のリスト
    """
    if not latest_updates:
        logger.info("チェッカーからの更新情報なし。比較スキップ。")
        return []

    # DB から現在の edition を取得
    current_pubs = db.get_all_publications()
    current_map: dict[str, dict] = {p["id"]: p for p in current_pubs}

    updated: list[dict] = []

    for update in latest_updates:
        pub_id = update["publication_id"]
        latest_edition = update.get("latest_edition", "")
        latest_date = update.get("latest_date")

        current = current_map.get(pub_id)
        if not current:
            logger.warning(f"DB に存在しない publication_id: {pub_id} — スキップ")
            continue

        current_edition = current.get("current_edition", "")

        if current_edition == latest_edition:
            logger.info(f"  {pub_id}: 変更なし (edition={current_edition})")
            continue

        logger.info(
            f"  {pub_id}: 更新検出! "
            f"'{current_edition}' -> '{latest_edition}'"
        )

        if dry_run:
            logger.info(f"  [DRY-RUN] 更新スキップ: {pub_id}")
        else:
            db.update_publication_edition(pub_id, latest_edition, latest_date)
            db.flag_needs_update(pub_id)

        updated.append({
            "publication_id": pub_id,
            "title": current.get("title", ""),
            "old_edition": current_edition,
            "new_edition": latest_edition,
        })

    return updated


def notify_updates(updated: list[dict]) -> None:
    """更新があった書籍をLINE通知する"""
    if not updated:
        return

    lines = [f"- {u['title']}: {u['old_edition']} → {u['new_edition']}" for u in updated]
    body = "\n".join(lines)

    send_alert(
        title=f"書籍更新検出: {len(updated)} 件",
        message=body,
        severity="warning",
    )


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="書籍最新版自動チェッカー")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 更新せずログ出力のみ",
    )
    args = parser.parse_args()

    # 環境変数
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not args.dry_run and (not supabase_url or not supabase_key):
        logger.error(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY が未設定です。"
            "--dry-run で実行するか環境変数を設定してください。"
        )
        sys.exit(1)

    # チェッカー実行
    logger.info("=== 書籍最新版チェック開始 ===")
    latest_updates = run_checkers()

    if not latest_updates:
        logger.info("全チェッカーからの更新情報なし。正常終了。")
        return

    # DB 比較・更新
    db = PublicationDBClient(supabase_url, supabase_key)
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    logger.info(f"=== {mode} モードで比較・更新開始 ===")

    updated = compare_and_update(db, latest_updates, dry_run=args.dry_run)

    # 通知
    if updated and not args.dry_run:
        notify_updates(updated)

    logger.info(f"=== 完了: 更新={len(updated)} 件 ===")


if __name__ == "__main__":
    main()
