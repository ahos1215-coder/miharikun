"""
pytest fixtures — NK スクレイパーテスト共通
"""

import json
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# モック HTML（ClassNK 一覧ページ）
# ---------------------------------------------------------------------------

MOCK_NK_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"><title>テクニカルインフォメーション</title></head>
<body>
<table>
  <thead>
    <tr>
      <th>発行番号</th>
      <th>標題</th>
      <th>発行日</th>
      <th>連絡先</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1373</td>
      <td>
        <a href="/hp/pdf/tech_info/tech_img/T1373j.pdf">揚貨装置の新要件について</a>
        ---
        <a href="/hp/pdf/tech_info/tech_img/T1373e.pdf">New Requirements for Cargo Gear</a>
      </td>
      <td>2026/03/25</td>
      <td>船舶安全部</td>
    </tr>
    <tr>
      <td>1372</td>
      <td>
        <a href="/hp/pdf/tech_info/tech_img/T1372j.pdf">CII/EEXI 計算方法の改定</a>
        ---
        <a href="/hp/pdf/tech_info/tech_img/T1372e.pdf">Revision of CII/EEXI Calculation</a>
      </td>
      <td>2026/03/10</td>
      <td>環境部</td>
    </tr>
    <tr>
      <td>1371</td>
      <td>
        <a href="/hp/pdf/tech_info/tech_img/T1371j.pdf">乗組員配乗要件の改正</a>
        ---
        <a href="/hp/pdf/tech_info/tech_img/T1371e.pdf">Amendment of Crew Manning Requirements</a>
      </td>
      <td>2026/02/20</td>
      <td>船員部</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""

# ヘッダー行のみ（エントリ 0 件 → サイト構造変更を模擬）
MOCK_NK_HTML_EMPTY = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"></head>
<body>
<table>
  <thead>
    <tr>
      <th>発行番号</th><th>標題</th><th>発行日</th><th>連絡先</th>
    </tr>
  </thead>
  <tbody></tbody>
</table>
</body>
</html>
"""

# td が 3 列しかない壊れたテーブル行を含む HTML
MOCK_NK_HTML_MALFORMED = """
<html><body>
<table>
  <tr>
    <td>1370</td>
    <td><a href="/hp/pdf/tech_info/tech_img/T1370j.pdf">テスト通達</a></td>
    <td>2026/01/15</td>
    <td>安全部</td>
  </tr>
  <tr>
    <td>not_a_number</td>
    <td>無効な行</td>
    <td>2026/01/01</td>
    <td>部門不明</td>
  </tr>
  <tr>
    <td colspan="2">結合セル（列数不足）</td>
    <td>2026/01/01</td>
  </tr>
</table>
</body></html>
"""


@pytest.fixture
def mock_nk_html() -> str:
    """通常の NK 一覧ページ HTML（3エントリ）"""
    return MOCK_NK_HTML


@pytest.fixture
def mock_nk_html_empty() -> str:
    """エントリが 0 件の NK 一覧ページ HTML"""
    return MOCK_NK_HTML_EMPTY


@pytest.fixture
def mock_nk_html_malformed() -> str:
    """不正な行を含む NK 一覧ページ HTML"""
    return MOCK_NK_HTML_MALFORMED


# ---------------------------------------------------------------------------
# モック PDF バイト列
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_pdf_bytes() -> bytes:
    """
    最小限の有効な PDF バイト列（テスト用）。
    実際のダウンロード処理をモックする際に使用する。
    """
    # 最小 PDF（テキストなし）
    minimal_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
    )
    return minimal_pdf


# ---------------------------------------------------------------------------
# モック Gemini レスポンス（v4 フィールド完備）
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_gemini_response() -> dict:
    """
    Gemini 分類 API のモックレスポンス。
    v4 必須フィールド（confidence / citations / applicable_crew_roles）を含む。
    """
    return {
        "summary_ja": "揚貨装置に関する新しい検査要件が2027年1月1日以降の建造船に適用される。"
                      "定期検査時に追加書類の提出が必要となる。",
        "applicable_ship_types": ["bulk_carrier", "general_cargo", "roro"],
        "applicable_gt_min": 500,
        "applicable_gt_max": None,
        "applicable_built_after": 2024,
        "applicable_routes": ["international"],
        "applicable_flags": ["all"],
        "applicable_crew_roles": ["chief_officer", "officer"],
        "category": "equipment",
        "severity": "important",
        "confidence": 0.87,
        "citations": [
            {
                "text": "本規則は、総トン数500トン以上の貨物船に適用する",
                "page": 2,
                "source": "TEC-1373",
            },
            {
                "text": "2027年1月1日以降に建造される船舶については定期検査時に揚貨装置試験成績書を提出すること",
                "page": 4,
                "source": "TEC-1373",
            },
        ],
    }


@pytest.fixture
def mock_gemini_response_low_confidence() -> dict:
    """低確信度（needs_review=True になる）のモック Gemini レスポンス"""
    return {
        "summary_ja": "内容が不明瞭な通達。適用範囲の判断が困難。",
        "applicable_ship_types": ["all"],
        "applicable_gt_min": None,
        "applicable_gt_max": None,
        "applicable_built_after": None,
        "applicable_routes": ["all"],
        "applicable_flags": ["all"],
        "applicable_crew_roles": ["all"],
        "category": "other",
        "severity": "informational",
        "confidence": 0.45,
        "citations": [
            {
                "text": "（根拠となる記述が見当たらない）",
                "page": 1,
                "source": "TEC-9999",
            }
        ],
    }
