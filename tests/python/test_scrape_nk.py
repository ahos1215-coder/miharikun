"""
NK スクレイパー pytest テストスイート
======================================
外部 API 呼び出しは unittest.mock.patch でモックし、
実際のネットワーク・DB アクセスは一切行わない。

実行方法:
    # リポジトリルートから
    cd scripts && python -m pytest ../tests/python/test_scrape_nk.py -v

    # または conftest.py の PYTHONPATH 設定後
    pytest tests/python/test_scrape_nk.py -v
"""

import json
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

# scrape_nk.py が scripts/ 配下にあるため、scripts/ を PYTHONPATH に追加
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# テスト対象のモジュールをインポート
# NOTE: utils.gemini_client / utils.gdrive_client / utils.line_notify は
#       Agent C が実装するため、import 時にモックで差し替える
with (
    patch("utils.gemini_client.classify_pdf", MagicMock(return_value={})),
    patch("utils.gdrive_client.upload_json", MagicMock(return_value=None)),
    patch("utils.line_notify.send_alert", MagicMock()),
    patch("utils.supabase_client.SupabaseClient", MagicMock()),
):
    import scrape_nk as nk


# ---------------------------------------------------------------------------
# テスト 1: 一覧ページのパース
# ---------------------------------------------------------------------------

class TestParseListPage:
    """_parse_list_page() のユニットテスト"""

    def test_parse_list_page_returns_correct_count(self, mock_nk_html: str):
        """通常の HTML から 3 エントリが取得できること"""
        soup = BeautifulSoup(mock_nk_html, "html.parser")
        entries = nk._parse_list_page(soup)
        assert len(entries) == 3

    def test_parse_list_page_tec_numbers(self, mock_nk_html: str):
        """TEC 番号が正しくパースされること"""
        soup = BeautifulSoup(mock_nk_html, "html.parser")
        entries = nk._parse_list_page(soup)
        tec_numbers = [e.tec_number for e in entries]
        assert 1373 in tec_numbers
        assert 1372 in tec_numbers
        assert 1371 in tec_numbers

    def test_parse_list_page_titles(self, mock_nk_html: str):
        """タイトルが正しくパースされること"""
        soup = BeautifulSoup(mock_nk_html, "html.parser")
        entries = nk._parse_list_page(soup)
        entry_1373 = next(e for e in entries if e.tec_number == 1373)
        assert "揚貨装置" in entry_1373.title_ja
        assert "Cargo Gear" in entry_1373.title_en

    def test_parse_list_page_dates(self, mock_nk_html: str):
        """発行日が YYYY-MM-DD 形式に変換されること"""
        soup = BeautifulSoup(mock_nk_html, "html.parser")
        entries = nk._parse_list_page(soup)
        entry_1373 = next(e for e in entries if e.tec_number == 1373)
        assert entry_1373.published_date == "2026-03-25"

    def test_parse_list_page_pdf_urls(self, mock_nk_html: str):
        """PDF URL が絶対 URL に変換されること"""
        soup = BeautifulSoup(mock_nk_html, "html.parser")
        entries = nk._parse_list_page(soup)
        entry_1373 = next(e for e in entries if e.tec_number == 1373)
        assert entry_1373.pdf_url_ja.startswith("https://")
        assert "T1373j.pdf" in entry_1373.pdf_url_ja
        assert entry_1373.pdf_url_en.startswith("https://")
        assert "T1373e.pdf" in entry_1373.pdf_url_en

    def test_parse_list_page_contact_dept(self, mock_nk_html: str):
        """連絡先部門が正しくパースされること"""
        soup = BeautifulSoup(mock_nk_html, "html.parser")
        entries = nk._parse_list_page(soup)
        entry_1373 = next(e for e in entries if e.tec_number == 1373)
        assert entry_1373.contact_dept == "船舶安全部"

    def test_parse_list_page_empty_html(self, mock_nk_html_empty: str):
        """エントリなしの HTML で空リストが返ること"""
        soup = BeautifulSoup(mock_nk_html_empty, "html.parser")
        entries = nk._parse_list_page(soup)
        assert len(entries) == 0

    def test_parse_list_page_malformed_skips_invalid_rows(self, mock_nk_html_malformed: str):
        """不正な行（数字でない発行番号・列数不足）はスキップされること"""
        soup = BeautifulSoup(mock_nk_html_malformed, "html.parser")
        entries = nk._parse_list_page(soup)
        # 有効な行（tec_number=1370）のみ取得
        assert len(entries) == 1
        assert entries[0].tec_number == 1370

    def test_parse_list_page_pdf_url_fallback(self):
        """PDF リンクがない場合にパターンから URL が生成されること"""
        # PDF リンクなしの HTML
        html = """
        <html><body><table>
          <tr>
            <td>1374</td>
            <td>リンクなし通達（テキストのみ）--- No Links Notice</td>
            <td>2026/04/01</td>
            <td>技術部</td>
          </tr>
        </table></body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        entries = nk._parse_list_page(soup)
        assert len(entries) == 1
        assert "T1374j.pdf" in entries[0].pdf_url_ja
        assert "T1374e.pdf" in entries[0].pdf_url_en


# ---------------------------------------------------------------------------
# テスト 2: 新着フィルタ
# ---------------------------------------------------------------------------

class TestFilterNewEntries:
    """filter_new_entries() のユニットテスト"""

    def _make_entries(self, tec_numbers: list[int]) -> list[nk.NKEntry]:
        """テスト用 NKEntry を一括生成"""
        return [
            nk.NKEntry(
                tec_number=n,
                title_ja=f"テスト通達 {n}",
                title_en=f"Test Notice {n}",
                published_date="2026-03-01",
                contact_dept="テスト部",
                pdf_url_ja=f"https://example.com/T{n}j.pdf",
                pdf_url_en=f"https://example.com/T{n}e.pdf",
            )
            for n in tec_numbers
        ]

    def test_filter_returns_only_new_entries(self):
        """known_max_tec より大きい番号のみ返ること"""
        entries = self._make_entries([1370, 1371, 1372, 1373])
        new = nk.filter_new_entries(entries, known_max_tec=1371)
        assert len(new) == 2
        assert all(e.tec_number > 1371 for e in new)

    def test_filter_returns_all_when_known_max_is_zero(self):
        """known_max_tec=0（初回）の場合は全件返ること"""
        entries = self._make_entries([1370, 1371, 1372])
        new = nk.filter_new_entries(entries, known_max_tec=0)
        assert len(new) == 3

    def test_filter_returns_empty_when_no_new(self):
        """新着なしの場合は空リストを返ること"""
        entries = self._make_entries([1370, 1371])
        new = nk.filter_new_entries(entries, known_max_tec=1371)
        assert len(new) == 0

    def test_filter_returns_sorted_ascending(self):
        """結果が TEC 番号の昇順で返ること"""
        entries = self._make_entries([1373, 1372, 1371])  # 逆順で作成
        new = nk.filter_new_entries(entries, known_max_tec=1370)
        tec_numbers = [e.tec_number for e in new]
        assert tec_numbers == sorted(tec_numbers)

    def test_filter_excludes_equal_to_known_max(self):
        """known_max_tec と同じ番号は含まれないこと（> であること）"""
        entries = self._make_entries([1371, 1372])
        new = nk.filter_new_entries(entries, known_max_tec=1372)
        assert len(new) == 0


# ---------------------------------------------------------------------------
# テスト 3: URL 正規化
# ---------------------------------------------------------------------------

class TestNormalizeUrl:
    """_normalize_url() のユニットテスト"""

    def test_absolute_url_unchanged(self):
        """絶対 URL はそのまま返ること"""
        url = "https://www.classnk.or.jp/hp/pdf/T1373j.pdf"
        assert nk._normalize_url(url) == url

    def test_root_relative_url(self):
        """/ 始まりの相対 URL に https://www.classnk.or.jp が付くこと"""
        url = "/hp/pdf/T1373j.pdf"
        result = nk._normalize_url(url)
        assert result == "https://www.classnk.or.jp/hp/pdf/T1373j.pdf"

    def test_protocol_relative_url(self):
        """// 始まりの相対 URL に https: が付くこと"""
        url = "//www.classnk.or.jp/hp/pdf/T1373j.pdf"
        result = nk._normalize_url(url)
        assert result == "https://www.classnk.or.jp/hp/pdf/T1373j.pdf"

    def test_relative_path_without_slash(self):
        """/ なし相対パスにも https://www.classnk.or.jp/ が付くこと"""
        url = "hp/pdf/T1373j.pdf"
        result = nk._normalize_url(url)
        assert result.startswith("https://www.classnk.or.jp/")

    def test_http_url_unchanged(self):
        """http:// で始まる URL もそのまま返ること"""
        url = "http://www.classnk.or.jp/hp/pdf/T1373j.pdf"
        assert nk._normalize_url(url) == url


# ---------------------------------------------------------------------------
# テスト 4: 分類結果の構造検証
# ---------------------------------------------------------------------------

class TestMockClassification:
    """モック分類結果の構造検証"""

    def test_mock_classification_has_required_fields(self, mock_gemini_response: dict):
        """モック Gemini レスポンスに必須フィールドが揃っていること"""
        required_fields = [
            "summary_ja",
            "applicable_ship_types",
            "applicable_gt_min",
            "applicable_gt_max",
            "applicable_built_after",
            "applicable_routes",
            "applicable_flags",
            "applicable_crew_roles",   # v4
            "category",
            "severity",
            "confidence",              # v4
            "citations",               # v4
        ]
        for field in required_fields:
            assert field in mock_gemini_response, f"Missing field: {field}"

    def test_mock_classification_confidence_range(self, mock_gemini_response: dict):
        """confidence が 0.0〜1.0 の範囲にあること"""
        confidence = mock_gemini_response["confidence"]
        assert 0.0 <= confidence <= 1.0

    def test_mock_classification_citations_structure(self, mock_gemini_response: dict):
        """citations が正しい構造を持つこと（text / page / source）"""
        citations = mock_gemini_response["citations"]
        assert isinstance(citations, list)
        for citation in citations:
            assert "text" in citation
            assert "page" in citation
            assert "source" in citation
            assert isinstance(citation["page"], int)
            assert citation["page"] >= 1

    def test_mock_classification_applicable_crew_roles(self, mock_gemini_response: dict):
        """applicable_crew_roles が有効な職種リストを含むこと"""
        valid_roles = {
            "master", "chief_officer", "officer",
            "chief_engineer", "engineer", "electrician", "rating", "all"
        }
        roles = mock_gemini_response["applicable_crew_roles"]
        assert isinstance(roles, list)
        assert len(roles) > 0
        for role in roles:
            assert role in valid_roles, f"Invalid role: {role}"

    def test_build_regulation_from_classification(
        self, mock_gemini_response: dict
    ):
        """_build_regulation_from_classification が正しく ClassifiedRegulation を生成すること"""
        entry = nk.NKEntry(
            tec_number=1373,
            title_ja="揚貨装置の新要件について",
            title_en="New Requirements for Cargo Gear",
            published_date="2026-03-25",
            contact_dept="船舶安全部",
            pdf_url_ja="https://www.classnk.or.jp/hp/pdf/tech_info/tech_img/T1373j.pdf",
            pdf_url_en="https://www.classnk.or.jp/hp/pdf/tech_info/tech_img/T1373e.pdf",
        )

        regulation = nk._build_regulation_from_classification(
            entry=entry,
            classification=mock_gemini_response,
            full_text="サンプル全文テキスト",
        )

        assert regulation.source == "nk"
        assert regulation.source_id == "TEC-1373"
        assert regulation.confidence == mock_gemini_response["confidence"]
        assert regulation.citations == mock_gemini_response["citations"]
        assert regulation.applicable_crew_roles == mock_gemini_response["applicable_crew_roles"]
        # confidence=0.87 > 0.7 → needs_review=False
        assert regulation.needs_review is False

    def test_build_regulation_needs_review_always_false_for_nk(
        self, mock_gemini_response_low_confidence: dict
    ):
        """NK は完全無審査パス: confidence に関わらず needs_review=False"""
        entry = nk.NKEntry(
            tec_number=9999,
            title_ja="低確信度テスト通達",
            title_en="Low Confidence Test Notice",
            published_date="2026-03-29",
            contact_dept="テスト部",
            pdf_url_ja="https://example.com/T9999j.pdf",
            pdf_url_en="https://example.com/T9999e.pdf",
        )

        regulation = nk._build_regulation_from_classification(
            entry=entry,
            classification=mock_gemini_response_low_confidence,
            full_text="",
        )

        assert regulation.needs_review is False  # NK は常に False

    def test_build_regulation_confidence_clamped_to_range(self):
        """confidence が範囲外の値でも 0.0〜1.0 にクランプされること"""
        entry = nk.NKEntry(
            tec_number=1000,
            title_ja="クランプテスト",
            title_en="Clamp Test",
            published_date="2026-01-01",
            contact_dept="テスト部",
            pdf_url_ja="https://example.com/T1000j.pdf",
            pdf_url_en="https://example.com/T1000e.pdf",
        )

        # confidence が 1.5 （上限超過）のケース
        classification_over = {"confidence": 1.5, "citations": [], "applicable_crew_roles": ["all"],
                               "summary_ja": "", "applicable_ship_types": ["all"],
                               "applicable_gt_min": None, "applicable_gt_max": None,
                               "applicable_built_after": None, "applicable_routes": ["all"],
                               "applicable_flags": ["all"], "category": "other", "severity": "informational"}
        reg_over = nk._build_regulation_from_classification(entry, classification_over, "")
        assert reg_over.confidence == 1.0

        # confidence が -0.1 （下限超過）のケース
        classification_under = dict(classification_over)
        classification_under["confidence"] = -0.1
        reg_under = nk._build_regulation_from_classification(entry, classification_under, "")
        assert reg_under.confidence == 0.0


# ---------------------------------------------------------------------------
# テスト 5: CLASSIFICATION_PROMPT の内容検証
# ---------------------------------------------------------------------------

class TestClassificationPrompt:
    """CLASSIFICATION_PROMPT に必要なフィールドが記述されていることを確認"""

    def test_prompt_has_confidence_field(self):
        """プロンプトに confidence フィールドの説明が含まれること"""
        assert "confidence" in nk.CLASSIFICATION_PROMPT

    def test_prompt_has_citations_field(self):
        """プロンプトに citations フィールドの説明が含まれること"""
        assert "citations" in nk.CLASSIFICATION_PROMPT

    def test_prompt_has_applicable_crew_roles_field(self):
        """プロンプトに applicable_crew_roles フィールドの説明が含まれること"""
        assert "applicable_crew_roles" in nk.CLASSIFICATION_PROMPT

    def test_prompt_instructs_pdf_only(self):
        """プロンプトに「PDFのテキストのみから判断」の指示が含まれること"""
        assert "PDF" in nk.CLASSIFICATION_PROMPT
        assert "添付" in nk.CLASSIFICATION_PROMPT

    def test_prompt_has_temperature_note(self):
        """プロンプトに信頼性・確信度に関する指示が含まれること"""
        assert "不確実" in nk.CLASSIFICATION_PROMPT or "確信" in nk.CLASSIFICATION_PROMPT

    def test_prompt_contains_valid_json_schema(self):
        """プロンプト内の JSON サンプルが有効な構造を持つこと"""
        # プロンプトから ```json ... ``` ブロックを抽出
        import re

        # ```json\n で始まるコードブロックを検索（説明文中の "```json ブロック" を除外）
        match = re.search(
            r"```json\n(.*?)\n```",
            nk.CLASSIFICATION_PROMPT,
            re.DOTALL,
        )
        assert match is not None, "JSON コードブロックがプロンプトに見つかりません"

        json_str = match.group(1)
        # プロンプト内の JSON はサンプルであり、"safety | environment | ..."
        # のような列挙表記を含むため、厳密な JSON パースではなく
        # 必須フィールド名の存在を文字列検査で確認する
        assert "confidence" in json_str, "JSON ブロックに confidence フィールドがありません"
        assert "citations" in json_str, "JSON ブロックに citations フィールドがありません"
        assert "applicable_crew_roles" in json_str, "JSON ブロックに applicable_crew_roles フィールドがありません"


# ---------------------------------------------------------------------------
# テスト 6: process_entry の dry-run 動作
# ---------------------------------------------------------------------------

class TestProcessEntryDryRun:
    """process_entry() のdry-run モード検証"""

    def _make_entry(self, tec_number: int = 1373) -> nk.NKEntry:
        return nk.NKEntry(
            tec_number=tec_number,
            title_ja="揚貨装置の新要件について",
            title_en="New Requirements for Cargo Gear",
            published_date="2026-03-25",
            contact_dept="船舶安全部",
            pdf_url_ja="https://www.classnk.or.jp/hp/pdf/tech_info/tech_img/T1373j.pdf",
            pdf_url_en="https://www.classnk.or.jp/hp/pdf/tech_info/tech_img/T1373e.pdf",
        )

    @patch("scrape_nk.download_pdf")
    @patch("scrape_nk.classify_pdf")
    @patch("scrape_nk.save_to_supabase")
    def test_dry_run_skips_pdf_download(
        self,
        mock_save: MagicMock,
        mock_classify: MagicMock,
        mock_download: MagicMock,
    ):
        """dry_run=True の場合、PDF ダウンロードが呼ばれないこと"""
        mock_db = MagicMock()
        entry = self._make_entry()

        result = nk.process_entry(entry, mock_db, dry_run=True)

        mock_download.assert_not_called()

    @patch("scrape_nk.download_pdf")
    @patch("scrape_nk.classify_pdf")
    @patch("scrape_nk.save_to_supabase")
    def test_dry_run_skips_gemini_classification(
        self,
        mock_save: MagicMock,
        mock_classify: MagicMock,
        mock_download: MagicMock,
    ):
        """dry_run=True の場合、Gemini 分類が呼ばれないこと"""
        mock_db = MagicMock()
        entry = self._make_entry()

        result = nk.process_entry(entry, mock_db, dry_run=True)

        mock_classify.assert_not_called()

    @patch("scrape_nk.download_pdf")
    @patch("scrape_nk.classify_pdf")
    @patch("scrape_nk.save_to_supabase")
    def test_dry_run_skips_supabase_save(
        self,
        mock_save: MagicMock,
        mock_classify: MagicMock,
        mock_download: MagicMock,
    ):
        """dry_run=True の場合、Supabase への保存が呼ばれないこと"""
        mock_db = MagicMock()
        entry = self._make_entry()

        result = nk.process_entry(entry, mock_db, dry_run=True)

        mock_save.assert_not_called()

    @patch("scrape_nk.download_pdf")
    @patch("scrape_nk.classify_pdf")
    @patch("scrape_nk.save_to_supabase")
    def test_dry_run_returns_regulation_with_mock_classification(
        self,
        mock_save: MagicMock,
        mock_classify: MagicMock,
        mock_download: MagicMock,
    ):
        """dry_run=True でも ClassifiedRegulation（モック）を返すこと"""
        mock_db = MagicMock()
        entry = self._make_entry()

        result = nk.process_entry(entry, mock_db, dry_run=True)

        assert result is not None
        assert result.source == "nk"
        assert result.source_id == "TEC-1373"

    @patch("scrape_nk.download_pdf")
    @patch("scrape_nk.classify_pdf")
    @patch("scrape_nk.save_to_supabase")
    def test_pdf_download_failure_queues_pending(
        self,
        mock_save: MagicMock,
        mock_classify: MagicMock,
        mock_download: MagicMock,
    ):
        """PDF ダウンロード失敗時に pending_queue に登録されること"""
        import requests as req

        mock_download.side_effect = req.RequestException("Connection timeout")
        mock_db = MagicMock()
        entry = self._make_entry()

        result = nk.process_entry(entry, mock_db, dry_run=False)

        assert result is None
        mock_db.queue_pending.assert_called_once()
        call_kwargs = mock_db.queue_pending.call_args
        # source="nk", source_id="TEC-1373" が渡されること
        args_or_kwargs = call_kwargs[1] if call_kwargs[1] else {}
        positional = call_kwargs[0] if call_kwargs[0] else ()
        # キーワード引数または位置引数で "nk" が含まれること
        all_args = list(positional) + list(args_or_kwargs.values())
        assert "nk" in all_args

    @patch("scrape_nk.download_pdf")
    @patch("scrape_nk.classify_pdf")
    @patch("scrape_nk.save_to_supabase")
    def test_gemini_failure_queues_pending(
        self,
        mock_save: MagicMock,
        mock_classify: MagicMock,
        mock_download: MagicMock,
        mock_pdf_bytes: bytes,
    ):
        """Gemini 分類失敗時に pending_queue に登録されること"""
        mock_download.return_value = mock_pdf_bytes
        mock_classify.side_effect = Exception("Gemini API 503 Service Unavailable")
        mock_db = MagicMock()
        entry = self._make_entry()

        # classify_pdf はモジュールレベルでインポートされているため、
        # scrape_nk モジュール内の参照を patch する
        with patch("scrape_nk.classify_pdf", side_effect=Exception("Gemini API 503")):
            result = nk.process_entry(entry, mock_db, dry_run=False)

        assert result is None
        mock_db.queue_pending.assert_called_once()


# ---------------------------------------------------------------------------
# テスト 7: get_known_max_tec
# ---------------------------------------------------------------------------

class TestGetKnownMaxTec:
    """get_known_max_tec() のユニットテスト"""

    def test_returns_tec_number_from_supabase(self):
        """Supabase から 'TEC-1373' が返った場合に 1373 を返すこと"""
        mock_db = MagicMock()
        mock_db.get_max_source_id.return_value = "TEC-1373"

        result = nk.get_known_max_tec(mock_db)

        assert result == 1373

    def test_returns_zero_when_no_data(self):
        """Supabase にデータがない場合（None）は 0 を返すこと"""
        mock_db = MagicMock()
        mock_db.get_max_source_id.return_value = None

        result = nk.get_known_max_tec(mock_db)

        assert result == 0

    def test_returns_zero_on_parse_error(self):
        """source_id が想定外のフォーマットでも 0 を返すこと（クラッシュしない）"""
        mock_db = MagicMock()
        mock_db.get_max_source_id.return_value = "INVALID_FORMAT"

        result = nk.get_known_max_tec(mock_db)

        assert result == 0
