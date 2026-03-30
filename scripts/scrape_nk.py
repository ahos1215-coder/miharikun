"""
ClassNK テクニカルインフォメーション スクレイパー（本番版）
================================================================
GitHub Actions の日次 cron で実行する想定。

処理フロー:
  1) 一覧ページ (tech_ichiran.aspx) を取得 → 最新エントリをパース
  2) Supabase に保存済みの最新番号と比較 → 新着のみ抽出
  3) 新着 PDF をダウンロード → Gemini API で全文分類
  4) 分類結果を Supabase に保存 + 全文テキストを Google Drive にアップロード

使い方:
  # ローカル検証（.env に GEMINI_API_KEY 等を設定）
  python scripts/scrape_nk.py

  # dry-run（PDF ダウンロード + Gemini 分類をスキップ）
  python scripts/scrape_nk.py --dry-run

  # 特定の TEC 番号だけ処理
  python scripts/scrape_nk.py --tec 1373

  # 結果を stdout に JSON 出力（GHA artifact 用）
  python scripts/scrape_nk.py --json-output

exit codes:
  0: 成功（新着あり or 新着なし）
  1: エラー（例外・DB接続失敗等）
  2: サイト構造変更（エントリ 0 件）
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# パス設定（scripts/ から utils を import できるようにする）
sys.path.insert(0, os.path.dirname(__file__))

# 共通ユーティリティ
from utils.gemini_client import classify_pdf
from utils.gdrive_client import upload_json
from utils.line_notify import send_alert
from utils.stealth_fetcher import stealth_get, stealth_download_bytes
from utils.supabase_client import SupabaseClient

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

NK_LIST_URL = "https://www.classnk.or.jp/hp/ja/tech_info/tech_ichiran.aspx"
NK_PDF_BASE = "https://www.classnk.or.jp/hp/pdf/tech_info/tech_img"
NK_DETAIL_URL_BASE = "https://www.classnk.or.jp/hp/ja/tech_info/tech_ichiran.aspx"

# HTTP — ClassNK はシンプルな bot UA を 403 で拒否するため、ブラウザライクなヘッダーを送る
HEADERS = {
    "User-Agent": os.getenv(
        "SCRAPE_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
REQUEST_INTERVAL = 2  # リクエスト間隔（秒）: 礼儀正しいボット


# ---------------------------------------------------------------------------
# Data model（v4: confidence / citations / needs_review / applicable_crew_roles 追加）
# ---------------------------------------------------------------------------

@dataclass
class NKEntry:
    """一覧ページから取得した 1 件分のメタデータ"""
    tec_number: int
    title_ja: str
    title_en: str
    published_date: str       # YYYY-MM-DD
    contact_dept: str
    pdf_url_ja: str
    pdf_url_en: str


@dataclass
class ClassifiedRegulation:
    """Gemini 分類後の完全なレコード（v4 拡張版）"""
    # 識別子
    source: str               # 'nk'
    source_id: str            # 'TEC-1373'

    # 基本情報
    title: str
    title_en: str
    summary_ja: str
    url: str
    pdf_url: str
    published_at: str
    contact_dept: str

    # 適用範囲
    applicable_ship_types: list[str]
    applicable_gt_min: Optional[int]
    applicable_gt_max: Optional[int]
    applicable_built_after: Optional[int]
    applicable_routes: list[str]
    applicable_flags: list[str]
    applicable_crew_roles: list[str]  # v4: ['master', 'chief_engineer', ...]

    # 分類
    category: str
    severity: str

    # v4: AI 信頼性
    confidence: float         # 0.0-1.0
    citations: list[dict]     # [{"text": str, "page": int, "source": str}]
    needs_review: bool        # confidence < 0.7 の場合 True

    # ストレージ
    full_text: str            # Google Drive 保存用
    gdrive_text_file_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Gemini 分類プロンプト（v4 拡張: confidence / citations / applicable_crew_roles 追加）
# ---------------------------------------------------------------------------

CLASSIFICATION_PROMPT = """\
あなたは海事規制の専門家です。以下の ClassNK テクニカルインフォメーション PDF の全文を読み、
船舶管理者・乗組員が「自分の船・自分の職種に関係あるか」を判断するための分類情報を JSON で返してください。

【重要】
- 過去の知識を使わず、添付 PDF のテキストのみから判断してください。
- 不確実な場合は正直に confidence を低く設定し、その根拠を citations に記載してください。

必ず以下の JSON 形式で返してください（```json ブロックで囲む）:

```json
{
  "summary_ja": "この通達の要点を200字以内で日本語要約",
  "applicable_ship_types": ["bulk_carrier", "container", "general_cargo", "roro", "pcc", "tanker_product", "tanker_crude", "lng", "lpg", "passenger", "all"],
  "applicable_gt_min": null,
  "applicable_gt_max": null,
  "applicable_built_after": null,
  "applicable_routes": ["international", "domestic_ocean", "domestic_coastal", "eca_north_europe", "eca_north_america", "arctic", "antarctic", "all"],
  "applicable_flags": ["all", "japan", "panama", "liberia", "marshall_islands", "cyprus", "malta", "bahamas", "singapore", "hong_kong"],
  "applicable_crew_roles": ["master", "chief_officer", "officer", "chief_engineer", "engineer", "electrician", "rating", "all"],
  "category": "safety | environment | equipment | survey | crew | navigation | cargo | recycling | other",
  "severity": "critical | important | informational",
  "confidence": 0.85,
  "citations": [
    {
      "text": "根拠となる原文をここに引用（50〜150字程度）",
      "page": 2,
      "source": "TEC-1373"
    }
  ]
}
```

分類ルール:
- applicable_ship_types: 通達が特定の船種にのみ適用される場合はその船種を列挙。全船種に適用なら ["all"]
- applicable_gt_min / gt_max: 総トン数の適用範囲。制限なしなら null
- applicable_built_after: 建造年の条件（例: 2020年以降建造船 → 2020）。条件なしなら null
- applicable_flags: 特定の船旗国にのみ適用される場合は列挙。全旗国なら ["all"]
- applicable_crew_roles: 職種による適用区分（例: 機関士向けのみ → ["chief_engineer", "engineer"]）。全職種なら ["all"]
- severity: 法的義務・検査要件の変更は "critical"、推奨事項・情報提供は "informational"、その中間は "important"
- confidence: 分類全体の確信度（0.0〜1.0）。PDF から明確に読み取れる場合は高く、曖昧な場合は低く設定
- citations: 分類の根拠となった PDF 内の原文を 1〜3 件引用。page は 1 始まりのページ番号
- 判断に迷った場合は、より広い適用範囲（all）を選択し、confidence を低めに設定してください
"""

# confidence 閾値（これ以下は needs_review = True）
CONFIDENCE_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# Step 1: 一覧ページのスクレイピング
# ---------------------------------------------------------------------------

def fetch_nk_list(max_pages: int = 1) -> list[NKEntry]:
    """
    NK テクニカルインフォメーション一覧ページをスクレイプ。
    日次運用では max_pages=1（最新 50 件）で十分。
    初回の全量取得時は max_pages=14 に設定。

    NOTE: ページネーションは ASP.NET の __VIEWSTATE を使った PostBack。
    max_pages > 1 の場合は PostBack を模擬する（現在は最新ページのみ対応）。
    """
    entries: list[NKEntry] = []

    logger.info(f"Fetching NK list page: {NK_LIST_URL}")
    try:
        resp = stealth_get(NK_LIST_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch NK list page: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to fetch NK list page (stealth): {e}")
        raise

    soup = BeautifulSoup(resp.text, "html.parser")
    entries.extend(_parse_list_page(soup))

    logger.info(f"Parsed {len(entries)} entries from page 1")

    # TODO: max_pages > 1 の場合は PostBack で 2 ページ目以降を取得
    # 初回全量取得時に実装する（__VIEWSTATE + __EVENTARGUMENT を模擬）

    return entries


def _parse_list_page(soup: BeautifulSoup) -> list[NKEntry]:
    """
    一覧テーブルの各行をパースして NKEntry を返す。
    テーブル構造:
      <table> の各 <tr> に <td> × 4:
        [0] 発行番号
        [1] 標題（日本語 + --- + 英語、各リンク付き）
        [2] 発行日 (YYYY/MM/DD)
        [3] 連絡先
    """
    entries: list[NKEntry] = []

    rows = soup.select("table tr")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        # 発行番号
        tec_text = cells[0].get_text(strip=True)
        if not tec_text.isdigit():
            continue
        tec_number = int(tec_text)

        # 標題（日本語 / 英語）と PDF URL
        links = cells[1].find_all("a")
        title_ja = ""
        title_en = ""
        pdf_url_ja = ""
        pdf_url_en = ""

        for link in links:
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if href.lower().endswith("j.pdf"):
                title_ja = text
                pdf_url_ja = _normalize_url(href)
            elif href.lower().endswith("e.pdf"):
                title_en = text
                pdf_url_en = _normalize_url(href)

        # タイトルが取れなかった場合のフォールバック
        if not title_ja:
            full_text = cells[1].get_text(separator="\n", strip=True)
            parts = full_text.split("---")
            title_ja = parts[0].strip() if parts else full_text
            title_en = parts[1].strip() if len(parts) > 1 else ""

        # PDF URL をパターンから生成（リンクが取れなかった場合）
        if not pdf_url_ja:
            pdf_url_ja = f"{NK_PDF_BASE}/T{tec_number}j.pdf"
        if not pdf_url_en:
            pdf_url_en = f"{NK_PDF_BASE}/T{tec_number}e.pdf"

        # 発行日
        date_text = cells[2].get_text(strip=True)
        try:
            published_date = datetime.strptime(date_text, "%Y/%m/%d").strftime("%Y-%m-%d")
        except ValueError:
            # フォーマットが異なる場合はそのまま保持
            published_date = date_text

        # 連絡先
        contact_dept = cells[3].get_text(strip=True)

        entries.append(NKEntry(
            tec_number=tec_number,
            title_ja=title_ja,
            title_en=title_en,
            published_date=published_date,
            contact_dept=contact_dept,
            pdf_url_ja=pdf_url_ja,
            pdf_url_en=pdf_url_en,
        ))

    return entries


def _normalize_url(href: str) -> str:
    """相対 URL を絶対 URL に変換"""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return f"https:{href}"
    if href.startswith("/"):
        return f"https://www.classnk.or.jp{href}"
    # 相対パス（ドットなし）
    return f"https://www.classnk.or.jp/{href}"


# ---------------------------------------------------------------------------
# Step 2: 新着判定
# ---------------------------------------------------------------------------

def filter_new_entries(
    entries: list[NKEntry],
    known_max_tec: int = 0,
) -> list[NKEntry]:
    """
    既知の最新 TEC 番号より新しいエントリのみ返す。
    known_max_tec は Supabase の regulations テーブルから取得する想定。
    """
    new = [e for e in entries if e.tec_number > known_max_tec]
    logger.info(f"New entries: {len(new)} (known max: TEC-{known_max_tec})")
    return sorted(new, key=lambda e: e.tec_number)


def get_known_max_tec(db: SupabaseClient) -> int:
    """
    Supabase から保存済みの最大 TEC 番号を取得。
    未設定時は 0（全件を新着扱い）。
    """
    source_id = db.get_max_source_id("nk")
    if source_id is None:
        return 0

    try:
        # "TEC-1373" → 1373
        num = int(source_id.replace("TEC-", ""))
        logger.info(f"Known max TEC from Supabase: {num}")
        return num
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse source_id '{source_id}': {e}")
        return 0


# ---------------------------------------------------------------------------
# Step 3: PDF ダウンロード + Gemini 分類
# ---------------------------------------------------------------------------

def download_pdf(url: str) -> bytes:
    """PDF をダウンロードしてバイト列を返す（Stealth フェッチャー経由）"""
    logger.info(f"Downloading PDF: {url}")
    return stealth_download_bytes(url, headers=HEADERS, timeout=60)


def _build_regulation_from_classification(
    entry: NKEntry,
    classification: dict,
    full_text: str,
) -> ClassifiedRegulation:
    """
    NKEntry + Gemini 分類結果 → ClassifiedRegulation を組み立てる。
    """
    confidence: float = float(classification.get("confidence", 0.5))
    # 0.0-1.0 の範囲に clamp
    confidence = max(0.0, min(1.0, confidence))
    needs_review = confidence < CONFIDENCE_THRESHOLD

    return ClassifiedRegulation(
        source="nk",
        source_id=f"TEC-{entry.tec_number}",
        title=entry.title_ja,
        title_en=entry.title_en,
        summary_ja=classification.get("summary_ja", ""),
        url=NK_DETAIL_URL_BASE,
        pdf_url=entry.pdf_url_ja,
        published_at=entry.published_date,
        contact_dept=entry.contact_dept,
        applicable_ship_types=classification.get("applicable_ship_types", ["all"]),
        applicable_gt_min=classification.get("applicable_gt_min"),
        applicable_gt_max=classification.get("applicable_gt_max"),
        applicable_built_after=classification.get("applicable_built_after"),
        applicable_routes=classification.get("applicable_routes", ["all"]),
        applicable_flags=classification.get("applicable_flags", ["all"]),
        applicable_crew_roles=classification.get("applicable_crew_roles", ["all"]),
        category=classification.get("category", "other"),
        severity=classification.get("severity", "informational"),
        confidence=confidence,
        citations=classification.get("citations", []),
        needs_review=needs_review,
        full_text=full_text,
        gdrive_text_file_id=None,
    )


def _mock_classification(tec_number: int) -> dict:
    """dry-run や Gemini API キーなしの場合のモック分類"""
    return {
        "summary_ja": f"TEC-{tec_number} のモック分類（dry-run または GEMINI_API_KEY 未設定）",
        "applicable_ship_types": ["all"],
        "applicable_gt_min": None,
        "applicable_gt_max": None,
        "applicable_built_after": None,
        "applicable_routes": ["all"],
        "applicable_flags": ["all"],
        "applicable_crew_roles": ["all"],
        "category": "other",
        "severity": "informational",
        "confidence": 0.5,
        "citations": [],
    }


# ---------------------------------------------------------------------------
# Step 4: PDF テキスト抽出（Google Drive 保存用）
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    PDF からテキストを抽出（Google Drive バックアップ用）。
    PyMuPDF (fitz) を使用。インストール: pip install PyMuPDF
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        return text.strip()
    except ImportError:
        logger.warning("PyMuPDF not installed. Text extraction skipped. pip install PyMuPDF")
        return "(text extraction skipped - PyMuPDF not installed)"
    except Exception as e:
        logger.warning(f"Text extraction failed: {e}")
        return f"(text extraction failed: {e})"


# ---------------------------------------------------------------------------
# Step 5: 保存（Supabase + Google Drive）
# ---------------------------------------------------------------------------

def save_to_supabase(db: SupabaseClient, regulation: ClassifiedRegulation) -> bool:
    """Supabase の regulations テーブルに upsert"""
    row = {
        "source": regulation.source,
        "source_id": regulation.source_id,
        "title": regulation.title,
        "title_en": regulation.title_en,
        "summary_ja": regulation.summary_ja,
        "url": regulation.url,
        "pdf_url": regulation.pdf_url,
        "published_at": regulation.published_at,
        "applicable_ship_types": regulation.applicable_ship_types,
        "applicable_gt_min": regulation.applicable_gt_min,
        "applicable_gt_max": regulation.applicable_gt_max,
        "applicable_built_after": regulation.applicable_built_after,
        "applicable_routes": regulation.applicable_routes,
        "applicable_flags": regulation.applicable_flags,
        "applicable_crew_roles": regulation.applicable_crew_roles,
        "category": regulation.category,
        "severity": regulation.severity,
        "confidence": regulation.confidence,
        "citations": regulation.citations,
        "needs_review": regulation.needs_review,
        "contact_dept": regulation.contact_dept,
        "gdrive_text_file_id": regulation.gdrive_text_file_id,
    }
    return db.upsert_regulation(row)


def save_text_to_gdrive(regulation: ClassifiedRegulation) -> Optional[str]:
    """
    Google Drive に全文テキストを JSON 形式で保存。
    utils.gdrive_client.upload_json（Agent C が実装）を使用。

    Returns: Google Drive ファイル ID or None
    """
    payload = {
        "source_id": regulation.source_id,
        "title": regulation.title,
        "full_text": regulation.full_text,
        "classified_at": datetime.now(timezone.utc).isoformat(),
    }
    filename = f"{regulation.source_id}.json"

    try:
        file_id = upload_json(
            data=payload,
            filename=filename,
        )
        if file_id:
            logger.info(f"Uploaded to Google Drive: {filename} (id={file_id})")
        else:
            # upload_json が None を返した場合はローカルにフォールバック
            _save_text_locally(regulation.source_id, payload)
        return file_id
    except Exception as e:
        logger.warning(f"Google Drive upload failed for {filename}: {e}. Saving locally.")
        _save_text_locally(regulation.source_id, payload)
        return None


def _save_text_locally(source_id: str, payload: dict) -> None:
    """Google Drive 失敗時のローカルフォールバック"""
    output_dir = Path("output/texts")
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{source_id}.json"
    filepath.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Saved text locally (fallback): {filepath}")


# ---------------------------------------------------------------------------
# Main pipeline: 1 件処理
# ---------------------------------------------------------------------------

def process_entry(
    entry: NKEntry,
    db: SupabaseClient,
    dry_run: bool = False,
) -> Optional[ClassifiedRegulation]:
    """
    1 件のエントリを完全に処理する（PDF ダウンロード → 分類 → 保存）。

    dry_run=True: PDF ダウンロード・Gemini 分類・Supabase 保存をスキップ。
    失敗時は pending_queue に登録し None を返す。
    """
    logger.info(f"{'='*60}")
    logger.info(f"Processing TEC-{entry.tec_number}: {entry.title_ja[:50]}")
    logger.info(f"{'='*60}")

    if dry_run:
        logger.info("[DRY-RUN] Skipping PDF download, Gemini classification, and DB save")
        # dry-run でもモックで ClassifiedRegulation を組み立てて返す
        mock_cls = _mock_classification(entry.tec_number)
        return _build_regulation_from_classification(entry, mock_cls, full_text="")

    # ---- PDF ダウンロード ----
    pdf_bytes: Optional[bytes] = None
    try:
        pdf_bytes = download_pdf(entry.pdf_url_ja)
        logger.info(f"PDF downloaded: {len(pdf_bytes):,} bytes")
    except requests.HTTPError as e:
        logger.error(f"PDF download HTTP error for TEC-{entry.tec_number}: {e}")
        db.queue_pending(
            source="nk",
            source_id=f"TEC-{entry.tec_number}",
            pdf_url=entry.pdf_url_ja,
            reason="pdf_download_http_error",
            error_detail=str(e),
        )
        return None
    except requests.RequestException as e:
        logger.error(f"PDF download failed for TEC-{entry.tec_number}: {e}")
        db.queue_pending(
            source="nk",
            source_id=f"TEC-{entry.tec_number}",
            pdf_url=entry.pdf_url_ja,
            reason="pdf_download_failed",
            error_detail=str(e),
        )
        return None
    except Exception as e:
        logger.error(f"Unexpected error during PDF download for TEC-{entry.tec_number}: {e}")
        db.queue_pending(
            source="nk",
            source_id=f"TEC-{entry.tec_number}",
            pdf_url=entry.pdf_url_ja,
            reason="pdf_download_unexpected_error",
            error_detail=str(e),
        )
        return None

    time.sleep(REQUEST_INTERVAL)

    # ---- Gemini 分類（共通ユーティリティ経由）----
    classification: Optional[dict] = None
    try:
        # classify_pdf は Agent C が実装する共通ユーティリティ
        # インターフェース: classify_pdf(pdf_bytes: bytes, prompt: str, source_id: str) -> dict
        classification = classify_pdf(
            pdf_bytes=pdf_bytes,
            prompt=CLASSIFICATION_PROMPT,
            source_id=f"TEC-{entry.tec_number}",
        )
        if classification is None:
            raise ValueError("classify_pdf returned None")
        if classification.get("status") == "pending":
            raise ValueError(f"classify_pdf returned pending: {classification.get('error', '')}")
    except Exception as e:
        logger.error(f"Gemini classification failed for TEC-{entry.tec_number}: {e}")
        # Gemini 失敗 → pending_queue に登録（翌日のバッチで自動リトライ）
        db.queue_pending(
            source="nk",
            source_id=f"TEC-{entry.tec_number}",
            pdf_url=entry.pdf_url_ja,
            reason="gemini_classification_failed",
            error_detail=str(e),
        )
        return None

    # ---- テキスト抽出（Google Drive 保存用）----
    full_text = extract_text_from_pdf(pdf_bytes)

    # ---- ClassifiedRegulation を組み立て ----
    regulation = _build_regulation_from_classification(entry, classification, full_text)

    # ---- Google Drive にテキスト保存 ----
    file_id = save_text_to_gdrive(regulation)
    if file_id:
        regulation.gdrive_text_file_id = file_id

    # ---- Supabase 保存 ----
    saved = save_to_supabase(db, regulation)
    if not saved:
        logger.error(f"Failed to save TEC-{entry.tec_number} to Supabase")
        # Supabase 失敗もキューに入れる
        db.queue_pending(
            source="nk",
            source_id=f"TEC-{entry.tec_number}",
            pdf_url=entry.pdf_url_ja,
            reason="supabase_save_failed",
            error_detail="upsert_regulation returned False",
        )
        # regulation 自体は返す（JSON サマリーには含める）

    logger.info(
        f"TEC-{entry.tec_number} done: "
        f"category={regulation.category}, "
        f"severity={regulation.severity}, "
        f"confidence={regulation.confidence:.2f}, "
        f"needs_review={regulation.needs_review}"
    )
    return regulation


# ---------------------------------------------------------------------------
# LINE 通知ヘルパー
# ---------------------------------------------------------------------------

def _notify_site_structure_change() -> None:
    """NK サイト構造変更疑い（エントリ 0 件）を LINE で通知"""
    message = (
        "\n[MIHARIKUN ALERT] NK スクレイパー異常\n"
        "ClassNK 一覧ページからエントリが取得できませんでした。\n"
        "サイト構造が変更された可能性があります。\n"
        f"URL: {NK_LIST_URL}\n"
        f"Time: {datetime.now(timezone.utc).isoformat()}Z"
    )
    logger.error(f"ALERT: {message}")

    try:
        send_alert(
            title="NK スクレイパー異常",
            message=message,
            severity="critical",
        )
    except Exception as e:
        logger.error(f"Failed to send LINE notification: {e}")


# ---------------------------------------------------------------------------
# サマリー JSON 出力
# ---------------------------------------------------------------------------

def _build_summary(
    entries: list[NKEntry],
    results: list[ClassifiedRegulation],
    start_time: datetime,
) -> dict:
    """実行サマリーを dict で返す（GHA artifact + --json-output 用）"""
    return {
        "scraped_at": start_time.isoformat(),
        "source": "nk",
        "total_new_entries": len(entries),
        "processed": len(results),
        "severity_breakdown": {
            sev: sum(1 for r in results if r.severity == sev)
            for sev in ["critical", "important", "informational"]
        },
        "needs_review_count": sum(1 for r in results if r.needs_review),
        "entries": [
            {
                "source_id": r.source_id,
                "title": r.title,
                "category": r.category,
                "severity": r.severity,
                "confidence": r.confidence,
                "needs_review": r.needs_review,
                "summary": r.summary_ja,
            }
            for r in results
        ],
    }


def _save_summary_json(summary: dict) -> Path:
    """サマリーを output/scrape_summary_nk.json に保存"""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    summary_path = output_dir / "scrape_summary_nk.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Summary saved to: {summary_path}")
    return summary_path


# ---------------------------------------------------------------------------
# メインエントリポイント
# ---------------------------------------------------------------------------

def main() -> int:
    """
    Returns:
        0: 成功（新着あり or 新着なし）
        1: エラー
        2: サイト構造変更疑い（エントリ 0 件）
    """
    parser = argparse.ArgumentParser(
        description="ClassNK Tech Info Scraper (Production)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip PDF download, Gemini classification, and DB write",
    )
    parser.add_argument(
        "--tec",
        type=int,
        help="Process a specific TEC number only (overrides new-entry filter)",
    )
    parser.add_argument(
        "--all-pages",
        action="store_true",
        help="Fetch all pages (for initial full load)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max entries to process per run (default: 10)",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print result summary JSON to stdout (for GHA artifact use)",
    )
    args = parser.parse_args()

    start_time = datetime.now(timezone.utc)

    logger.info("=" * 60)
    logger.info("ClassNK Technical Information Scraper (Production)")
    logger.info(f"Time: {start_time.isoformat()}Z")
    logger.info(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    logger.info("=" * 60)

    # Supabase クライアント初期化
    db = SupabaseClient()

    # ---- Step 1: 一覧ページ取得 ----
    try:
        entries = fetch_nk_list(max_pages=14 if args.all_pages else 1)
    except Exception as e:
        logger.error(f"Fatal: Failed to fetch NK list page: {e}")
        return 1

    if not entries:
        logger.error("No entries found. Site structure may have changed.")
        _notify_site_structure_change()
        return 2  # サイト構造変更疑い

    # ---- 特定 TEC 番号のみ処理 ----
    if args.tec:
        entries = [e for e in entries if e.tec_number == args.tec]
        if not entries:
            logger.error(f"TEC-{args.tec} not found in the list page")
            return 1
    else:
        # ---- Step 2: 新着フィルタ ----
        known_max = get_known_max_tec(db)
        entries = filter_new_entries(entries, known_max)

    # 件数制限
    if len(entries) > args.limit:
        logger.info(f"Limiting to {args.limit} entries (of {len(entries)} new)")
        entries = entries[: args.limit]

    if not entries:
        logger.info("No new entries. Done.")
        summary = _build_summary([], [], start_time)
        _save_summary_json(summary)
        if args.json_output:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    # ---- Step 3-5: 各エントリを処理 ----
    results: list[ClassifiedRegulation] = []
    for i, entry in enumerate(entries):
        if i > 0:
            time.sleep(REQUEST_INTERVAL)

        result = process_entry(entry, db, dry_run=args.dry_run)
        if result is not None:
            results.append(result)

    # ---- サマリー ----
    logger.info(f"\n{'='*60}")
    logger.info(f"Completed: {len(results)} / {len(entries)} entries processed")
    if results:
        logger.info("Severity breakdown:")
        for sev in ["critical", "important", "informational"]:
            count = sum(1 for r in results if r.severity == sev)
            if count:
                logger.info(f"  {sev}: {count}")
        needs_review_count = sum(1 for r in results if r.needs_review)
        if needs_review_count:
            logger.info(f"  needs_review: {needs_review_count} (confidence < {CONFIDENCE_THRESHOLD})")
    logger.info("=" * 60)

    # ---- サマリー JSON を保存 ----
    summary = _build_summary(entries, results, start_time)
    _save_summary_json(summary)

    # --json-output オプション: stdout にも出力
    if args.json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
