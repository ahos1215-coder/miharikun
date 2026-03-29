"""
ClassNK テクニカルインフォメーション スクレイパー（プロトタイプ）
==================================================================
GitHub Actions の日次 cron で実行する想定。

処理フロー:
  1) 一覧ページ (tech_ichiran.aspx) を取得 → 最新エントリをパース
  2) Supabase に保存済みの最新番号と比較 → 新着のみ抽出
  3) 新着 PDF をダウンロード → Gemini API で全文分類
  4) 分類結果を Supabase に保存 + 全文テキストを Google Drive にアップロード

使い方:
  # ローカル検証（.env に GEMINI_API_KEY 等を設定）
  python scrape_nk.py

  # dry-run（PDF ダウンロード + Gemini 分類をスキップ）
  python scrape_nk.py --dry-run

  # 特定の TEC 番号だけ処理
  python scrape_nk.py --tec 1373
"""

import argparse
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

NK_LIST_URL = "https://www.classnk.or.jp/hp/ja/tech_info/tech_ichiran.aspx"
NK_PDF_BASE = "https://www.classnk.or.jp/hp/pdf/tech_info/tech_img"

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Google Drive (optional, Phase 1 では手動でも OK)
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "")

# HTTP
HEADERS = {
    "User-Agent": "MaritimeRegsMonitor/0.1 (+https://github.com/ahos1215-coder)"
}
REQUEST_INTERVAL = 2  # seconds between requests (be polite)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class NKEntry:
    """一覧ページから取得した 1 件分のメタデータ"""
    tec_number: int
    title_ja: str
    title_en: str
    published_date: str  # YYYY-MM-DD
    contact_dept: str
    pdf_url_ja: str
    pdf_url_en: str


@dataclass
class ClassifiedRegulation:
    """Gemini 分類後の完全なレコード"""
    source: str  # 'nk'
    source_id: str  # 'TEC-1373'
    title: str
    title_en: str
    summary_ja: str
    url: str
    pdf_url: str
    published_at: str
    applicable_ship_types: list[str]
    applicable_gt_min: Optional[int]
    applicable_gt_max: Optional[int]
    applicable_built_after: Optional[int]
    applicable_routes: list[str]
    applicable_flags: list[str]
    category: str
    severity: str
    full_text: str  # Google Drive 保存用
    contact_dept: str


# ---------------------------------------------------------------------------
# Step 1: 一覧ページのスクレイピング
# ---------------------------------------------------------------------------

def fetch_nk_list(max_pages: int = 1) -> list[NKEntry]:
    """
    NK テクニカルインフォメーション一覧ページをスクレイプ。
    日次運用では max_pages=1（最新 50 件）で十分。
    初回の全量取得時は max_pages=14 に設定。
    
    NOTE: ページネーションは ASP.NET の __VIEWSTATE を使った PostBack。
    max_pages > 1 の場合は PostBack を模擬する必要がある（将来実装）。
    MVP では最新 50 件（1ページ目）のみ対応。
    """
    entries: list[NKEntry] = []

    print(f"[NK] Fetching list page: {NK_LIST_URL}")
    resp = requests.get(NK_LIST_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding

    soup = BeautifulSoup(resp.text, "html.parser")
    entries.extend(_parse_list_page(soup))

    print(f"[NK] Parsed {len(entries)} entries from page 1")

    # TODO: max_pages > 1 の場合は PostBack で 2 ページ目以降を取得
    # 初回全量取得時に実装する

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
    entries = []

    # テーブルの行を探す
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

        # 標題（日本語 / 英語）
        links = cells[1].find_all("a")
        title_ja = ""
        title_en = ""
        pdf_url_ja = ""
        pdf_url_en = ""

        for link in links:
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if href.endswith("j.pdf"):
                title_ja = text
                pdf_url_ja = _normalize_url(href)
            elif href.endswith("e.pdf"):
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
    return f"https://www.classnk.or.jp{href}"


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
    print(f"[NK] New entries: {len(new)} (known max: TEC-{known_max_tec})")
    return sorted(new, key=lambda e: e.tec_number)


# ---------------------------------------------------------------------------
# Step 3: PDF ダウンロード + Gemini 分類
# ---------------------------------------------------------------------------

CLASSIFICATION_PROMPT = """\
あなたは海事規制の専門家です。以下の ClassNK テクニカルインフォメーション PDF の全文を読み、
船舶管理者が「自分の船に関係あるか」を判断するための分類情報を JSON で返してください。

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
  "category": "safety | environment | equipment | survey | crew | navigation | cargo | recycling | other",
  "severity": "critical | important | informational"
}
```

分類ルール:
- applicable_ship_types: 通達が特定の船種にのみ適用される場合はその船種を列挙。全船種に適用なら ["all"]
- applicable_gt_min / gt_max: 総トン数の適用範囲。制限なしなら null
- applicable_built_after: 建造年の条件（例: 2020年以降建造船 → 2020）。条件なしなら null
- applicable_flags: 特定の船旗国にのみ適用される場合は列挙。全旗国なら ["all"]
- severity: 法的義務・検査要件の変更は "critical"、推奨事項・情報提供は "informational"、その中間は "important"
- 判断に迷った場合は、より広い適用範囲（all）を選択してください
"""


def download_pdf(url: str) -> bytes:
    """PDF をダウンロードしてバイト列を返す"""
    print(f"[NK] Downloading PDF: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.content


def classify_with_gemini(pdf_bytes: bytes, tec_number: int) -> dict:
    """
    Gemini API に PDF を送信し、構造化された分類結果を返す。
    Gemini は PDF を直接入力として受け取れる（base64 エンコード）。
    """
    import base64

    if not GEMINI_API_KEY:
        print("[WARN] GEMINI_API_KEY not set, returning mock classification")
        return _mock_classification(tec_number)

    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "application/pdf",
                            "data": pdf_b64,
                        }
                    },
                    {
                        "text": CLASSIFICATION_PROMPT,
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,  # 分類タスクなので低温
            "maxOutputTokens": 1024,
        },
    }

    print(f"[NK] Sending TEC-{tec_number} to Gemini for classification...")
    resp = requests.post(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    # Gemini のレスポンスからテキスト部分を抽出
    text = ""
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            text += part.get("text", "")

    return _parse_gemini_json(text, tec_number)


def _parse_gemini_json(text: str, tec_number: int) -> dict:
    """Gemini の出力から JSON ブロックを抽出してパース"""
    # ```json ... ``` ブロックを探す
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # ブロックなしの場合、全体を JSON として試す
        json_str = text.strip()

    try:
        result = json.loads(json_str)
        print(f"[NK] TEC-{tec_number} classified: category={result.get('category')}, severity={result.get('severity')}")
        return result
    except json.JSONDecodeError as e:
        print(f"[WARN] Failed to parse Gemini response for TEC-{tec_number}: {e}")
        print(f"[WARN] Raw response: {text[:500]}")
        return _mock_classification(tec_number)


def _mock_classification(tec_number: int) -> dict:
    """Gemini API キーがない場合のモック"""
    return {
        "summary_ja": f"TEC-{tec_number} のモック分類（GEMINI_API_KEY 未設定）",
        "applicable_ship_types": ["all"],
        "applicable_gt_min": None,
        "applicable_gt_max": None,
        "applicable_built_after": None,
        "applicable_routes": ["all"],
        "applicable_flags": ["all"],
        "category": "other",
        "severity": "informational",
    }


# ---------------------------------------------------------------------------
# Step 4: PDF からテキスト抽出（Google Drive 保存用）
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
        print("[WARN] PyMuPDF not installed. pip install PyMuPDF")
        return "(text extraction skipped - install PyMuPDF)"


# ---------------------------------------------------------------------------
# Step 5: 保存（Supabase + Google Drive）
# ---------------------------------------------------------------------------

def save_to_supabase(regulation: ClassifiedRegulation) -> bool:
    """Supabase の regulations テーブルに upsert"""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print(f"[SKIP] Supabase not configured. Would save: {regulation.source_id}")
        return False

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
        "category": regulation.category,
        "severity": regulation.severity,
        "contact_dept": regulation.contact_dept,
    }

    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/regulations",
        json=row,
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        },
        timeout=30,
    )

    if resp.status_code in (200, 201):
        print(f"[OK] Saved to Supabase: {regulation.source_id}")
        return True
    else:
        print(f"[ERROR] Supabase save failed: {resp.status_code} {resp.text[:200]}")
        return False


def get_known_max_tec() -> int:
    """Supabase から保存済みの最大 TEC 番号を取得"""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        # 未設定時は 0（全件を新着扱い）
        return 0

    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/regulations",
            params={
                "source": "eq.nk",
                "select": "source_id",
                "order": "source_id.desc",
                "limit": "1",
            },
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            rows = resp.json()
            if rows:
                # source_id は "TEC-1373" 形式
                num = int(rows[0]["source_id"].replace("TEC-", ""))
                print(f"[NK] Known max TEC from Supabase: {num}")
                return num
    except Exception as e:
        print(f"[WARN] Failed to query Supabase: {e}")

    return 0


def save_text_to_gdrive(text: str, filename: str) -> Optional[str]:
    """
    Google Drive に全文テキストを保存（JSON 形式）。
    MVP では手動アップロードでも OK。
    本格運用時は Google Drive API + Service Account を使用。

    Returns: file_id or None
    """
    # TODO: Google Drive API 実装
    # 現時点ではローカルファイル出力で代替
    output_dir = Path("output/texts")
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    filepath.write_text(text, encoding="utf-8")
    print(f"[OK] Saved text to: {filepath}")
    return None  # file_id は Drive API 実装後


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_entry(entry: NKEntry, dry_run: bool = False) -> Optional[ClassifiedRegulation]:
    """1 件のエントリを完全に処理する"""
    print(f"\n{'='*60}")
    print(f"Processing TEC-{entry.tec_number}: {entry.title_ja[:50]}")
    print(f"{'='*60}")

    if dry_run:
        print("[DRY-RUN] Skipping PDF download and classification")
        return None

    # PDF ダウンロード
    try:
        pdf_bytes = download_pdf(entry.pdf_url_ja)
        print(f"[OK] PDF downloaded: {len(pdf_bytes):,} bytes")
    except Exception as e:
        print(f"[ERROR] PDF download failed: {e}")
        return None

    time.sleep(REQUEST_INTERVAL)

    # Gemini 分類
    try:
        classification = classify_with_gemini(pdf_bytes, entry.tec_number)
    except Exception as e:
        print(f"[ERROR] Gemini classification failed: {e}")
        return None

    # テキスト抽出（Drive 保存用）
    full_text = extract_text_from_pdf(pdf_bytes)

    # ClassifiedRegulation を組み立て
    regulation = ClassifiedRegulation(
        source="nk",
        source_id=f"TEC-{entry.tec_number}",
        title=entry.title_ja,
        title_en=entry.title_en,
        summary_ja=classification.get("summary_ja", ""),
        url=f"https://www.classnk.or.jp/hp/ja/tech_info/tech_ichiran.aspx",
        pdf_url=entry.pdf_url_ja,
        published_at=entry.published_date,
        applicable_ship_types=classification.get("applicable_ship_types", ["all"]),
        applicable_gt_min=classification.get("applicable_gt_min"),
        applicable_gt_max=classification.get("applicable_gt_max"),
        applicable_built_after=classification.get("applicable_built_after"),
        applicable_routes=classification.get("applicable_routes", ["all"]),
        applicable_flags=classification.get("applicable_flags", ["all"]),
        category=classification.get("category", "other"),
        severity=classification.get("severity", "informational"),
        full_text=full_text,
        contact_dept=entry.contact_dept,
    )

    # Supabase 保存
    save_to_supabase(regulation)

    # Google Drive テキスト保存
    save_text_to_gdrive(
        json.dumps({
            "source_id": regulation.source_id,
            "title": regulation.title,
            "full_text": regulation.full_text,
            "classified_at": datetime.utcnow().isoformat(),
        }, ensure_ascii=False, indent=2),
        f"TEC-{entry.tec_number}.json",
    )

    return regulation


def main():
    parser = argparse.ArgumentParser(description="ClassNK Tech Info Scraper")
    parser.add_argument("--dry-run", action="store_true", help="Skip PDF download and Gemini")
    parser.add_argument("--tec", type=int, help="Process a specific TEC number only")
    parser.add_argument("--all-pages", action="store_true", help="Fetch all pages (initial load)")
    parser.add_argument("--limit", type=int, default=10, help="Max entries to process per run")
    args = parser.parse_args()

    print("=" * 60)
    print("ClassNK Technical Information Scraper")
    print(f"Time: {datetime.utcnow().isoformat()}Z")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print("=" * 60)

    # Step 1: 一覧ページ取得
    entries = fetch_nk_list(max_pages=14 if args.all_pages else 1)

    if not entries:
        print("[WARN] No entries found. Site structure may have changed.")
        sys.exit(1)

    # 特定 TEC 番号のみ処理
    if args.tec:
        entries = [e for e in entries if e.tec_number == args.tec]
        if not entries:
            print(f"[ERROR] TEC-{args.tec} not found in list page")
            sys.exit(1)
    else:
        # Step 2: 新着フィルタ
        known_max = get_known_max_tec()
        entries = filter_new_entries(entries, known_max)

    # 件数制限
    if len(entries) > args.limit:
        print(f"[NK] Limiting to {args.limit} entries (of {len(entries)})")
        entries = entries[:args.limit]

    if not entries:
        print("[NK] No new entries. Done.")
        return

    # Step 3-5: 各エントリを処理
    results = []
    for i, entry in enumerate(entries):
        if i > 0:
            time.sleep(REQUEST_INTERVAL)

        result = process_entry(entry, dry_run=args.dry_run)
        if result:
            results.append(result)

    # サマリー
    print(f"\n{'='*60}")
    print(f"Completed: {len(results)} / {len(entries)} entries processed")
    if results:
        print(f"Severity breakdown:")
        for sev in ["critical", "important", "informational"]:
            count = sum(1 for r in results if r.severity == sev)
            if count:
                print(f"  {sev}: {count}")
    print("=" * 60)

    # 結果を JSON 出力（GHA の Artifact 用）
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    summary_path = output_dir / "scrape_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "scraped_at": datetime.utcnow().isoformat(),
                "total_entries": len(entries),
                "processed": len(results),
                "entries": [
                    {
                        "source_id": r.source_id,
                        "title": r.title,
                        "category": r.category,
                        "severity": r.severity,
                        "summary": r.summary_ja,
                    }
                    for r in results
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
