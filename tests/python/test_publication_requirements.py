"""
test_publication_requirements.py — 備付書籍自動判定のテスト
============================================================
"""

import sys
import os

# scripts/ を PYTHONPATH に追加して utils を import 可能にする
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import pytest
from utils.publication_requirements import (
    determine_required_publications,
    get_mandatory_publications,
    get_publication_summary,
)


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _pub_ids(pubs: list[dict]) -> set[str]:
    """publication_id の集合を返す"""
    return {p["publication_id"] for p in pubs}


def _pub_titles(pubs: list[dict]) -> list[str]:
    """title_ja のリストを返す"""
    return [p["title_ja"] for p in pubs]


def _has_pub_containing(pubs: list[dict], keyword: str) -> bool:
    """title または title_ja に keyword を含む書籍があるか"""
    return any(
        keyword.lower() in p["title"].lower() or keyword in p.get("title_ja", "")
        for p in pubs
    )


def _pubs_by_category(pubs: list[dict], category: str) -> list[dict]:
    return [p for p in pubs if p["category"] == category]


# ---------------------------------------------------------------------------
# テストデータ
# ---------------------------------------------------------------------------

SHIP_5000GT_BULKER_INTL_JPN = {
    "ship_type": "bulk_carrier",
    "gross_tonnage": 5000,
    "navigation_area": ["international"],
    "flag_state": "JPN",
    "build_year": 2015,
    "classification_society": "NK",
}

SHIP_300GT_COASTAL_JPN = {
    "ship_type": "general_cargo",
    "gross_tonnage": 300,
    "navigation_area": ["coastal"],
    "flag_state": "JPN",
    "build_year": 2010,
    "classification_society": "NK",
}

SHIP_LNG = {
    "ship_type": "lng",
    "gross_tonnage": 80000,
    "navigation_area": ["international"],
    "flag_state": "JPN",
    "build_year": 2020,
    "classification_society": "NK",
}

SHIP_CHEMICAL = {
    "ship_type": "chemical",
    "gross_tonnage": 10000,
    "navigation_area": ["international"],
    "flag_state": "JPN",
    "build_year": 2018,
    "classification_society": "NK",
}

SHIP_TANKER_OLD = {
    "ship_type": "tanker",
    "gross_tonnage": 50000,
    "navigation_area": ["international"],
    "flag_state": "JPN",
    "build_year": 2005,
    "classification_society": "NK",
}


# ===========================================================================
# テスト1: 5000GT バルカー/国際航行/日本旗/NK
# ===========================================================================

class TestBulkCarrier5000GT:
    """5000GTバルカー、国際航行、日本旗、NK船級"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pubs = determine_required_publications(SHIP_5000GT_BULKER_INTL_JPN)

    def test_solas_included(self):
        """SOLAS統合版が含まれること"""
        assert _has_pub_containing(self.pubs, "SOLAS"), "SOLAS Consolidated Edition が含まれるべき"

    def test_marpol_included(self):
        """MARPOL統合版が含まれること"""
        assert _has_pub_containing(self.pubs, "MARPOL"), "MARPOL Consolidated Edition が含まれるべき"

    def test_ism_included(self):
        """ISM Codeが含まれること（500GT以上・国際航行）"""
        assert _has_pub_containing(self.pubs, "ISM"), "ISM Code が含まれるべき"

    def test_csm_included(self):
        """貨物固縛マニュアルが含まれること（貨物船）"""
        assert _has_pub_containing(self.pubs, "Cargo Securing"), "CSM が含まれるべき"

    def test_isps_included(self):
        """ISPSコードが含まれること（500GT以上・国際航行）"""
        assert _has_pub_containing(self.pubs, "ISPS"), "ISPS Code が含まれるべき"

    def test_esp_included(self):
        """ESPコードが含まれること（バルカー）"""
        assert _has_pub_containing(self.pubs, "ESP"), "ESP Code が含まれるべき"

    def test_imsbc_included(self):
        """IMSBCコードが含まれること（バルカー）"""
        assert _has_pub_containing(self.pubs, "IMSBC"), "IMSBC Code が含まれるべき"

    def test_jpn_flag_publications(self):
        """日本旗国書籍が含まれること"""
        assert _has_pub_containing(self.pubs, "船舶安全法"), "船舶安全法関連法令集が含まれるべき"
        assert _has_pub_containing(self.pubs, "船員法"), "船員法関連法令集が含まれるべき"

    def test_jho_publications(self):
        """日本水路部刊行物が含まれること（日本旗）"""
        assert _has_pub_containing(self.pubs, "灯台表"), "灯台表が含まれるべき"
        assert _has_pub_containing(self.pubs, "水路通報"), "水路通報が含まれるべき"

    def test_nk_publications(self):
        """NK船級書籍が含まれること"""
        assert _has_pub_containing(self.pubs, "NK鋼船規則"), "NK鋼船規則が含まれるべき"

    def test_ukho_publications(self):
        """国際航行なのでUKHO刊行物が含まれること"""
        assert _has_pub_containing(self.pubs, "NP100"), "NP100 Mariner's Handbook が含まれるべき"

    def test_sopep_included(self):
        """400GT以上なのでSOPEPが含まれること"""
        assert _has_pub_containing(self.pubs, "SOPEP"), "SOPEP が含まれるべき"

    def test_seemp_included(self):
        """400GT以上なのでSEEMPが含まれること"""
        assert _has_pub_containing(self.pubs, "SEEMP"), "SEEMP が含まれるべき"

    def test_category_counts(self):
        """全カテゴリにわたって書籍が存在すること"""
        for cat in ["A", "B", "C", "D"]:
            cat_pubs = _pubs_by_category(self.pubs, cat)
            assert len(cat_pubs) > 0, f"カテゴリ{cat}に書籍が存在すべき"

    def test_minimum_total(self):
        """最低限の書籍数（バルカー国際JPN/NK なら相当数出るはず）"""
        assert len(self.pubs) >= 40, f"総数{len(self.pubs)}は少なすぎる"


# ===========================================================================
# テスト2: 300GT 沿海貨物船/日本旗/NK
# ===========================================================================

class TestCoastalCargoSmall:
    """300GT沿海貨物船、日本旗、NK船級"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pubs = determine_required_publications(SHIP_300GT_COASTAL_JPN)

    def test_solas_not_applicable(self):
        """SOLAS統合版が含まれないこと（300GT・沿海はSOLAS非適用想定）"""
        solas_pubs = [
            p for p in self.pubs
            if p["publication_id"] == "SOLAS_CONSOLIDATED"
        ]
        assert len(solas_pubs) == 0, "300GT沿海船にSOLAS統合版は不要のはず"

    def test_domestic_law_included(self):
        """国内法書籍が含まれること"""
        assert _has_pub_containing(self.pubs, "船舶安全法"), "船舶安全法関連法令集が含まれるべき"
        assert _has_pub_containing(self.pubs, "港則法"), "港則法が含まれるべき"

    def test_colreg_included(self):
        """COLREGは全船に必要"""
        assert _has_pub_containing(self.pubs, "COLREG"), "COLREG は全船に必要"

    def test_mlc_included(self):
        """MLCは全船に必要"""
        assert _has_pub_containing(self.pubs, "MLC"), "MLC は全船に必要"

    def test_no_ukho_publications(self):
        """沿海なのでUKHO刊行物は含まれないこと"""
        assert not _has_pub_containing(self.pubs, "NP100"), "沿海船にNP100は不要"

    def test_nk_publications(self):
        """NK船級書籍は含まれること"""
        assert _has_pub_containing(self.pubs, "NK鋼船規則"), "NK鋼船規則が含まれるべき"


# ===========================================================================
# テスト3: LNG船 → IGC Code が含まれ、IBC Code が含まれないこと
# ===========================================================================

class TestLNGShip:
    """LNG船の書籍判定"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pubs = determine_required_publications(SHIP_LNG)

    def test_igc_code_included(self):
        """IGC Code が含まれること"""
        assert _has_pub_containing(self.pubs, "IGC"), "LNG船にIGC Code が含まれるべき"

    def test_ibc_code_not_included(self):
        """IBC Code が含まれないこと"""
        ibc_pubs = [p for p in self.pubs if p["publication_id"] == "IBC_CODE"]
        assert len(ibc_pubs) == 0, "LNG船にIBC Code は不要"

    def test_smpep_included(self):
        """ガスキャリアなのでSMPEPが含まれること"""
        assert _has_pub_containing(self.pubs, "SMPEP"), "ガスキャリアにSMPEPが含まれるべき"


# ===========================================================================
# テスト4: ケミカルタンカー → IBC Code が含まれること
# ===========================================================================

class TestChemicalTanker:
    """ケミカルタンカーの書籍判定"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pubs = determine_required_publications(SHIP_CHEMICAL)

    def test_ibc_code_included(self):
        """IBC Code が含まれること"""
        assert _has_pub_containing(self.pubs, "IBC"), "ケミカルタンカーにIBC Code が含まれるべき"

    def test_igc_code_not_included(self):
        """IGC Code が含まれないこと"""
        igc_pubs = [p for p in self.pubs if p["publication_id"] == "IGC_CODE"]
        assert len(igc_pubs) == 0, "ケミカルタンカーにIGC Code は不要"

    def test_smpep_included(self):
        """ケミカルキャリアなのでSMPEPが含まれること"""
        assert _has_pub_containing(self.pubs, "SMPEP"), "ケミカルキャリアにSMPEPが含まれるべき"

    def test_voc_plan_included(self):
        """タンカー型なのでVOC管理計画が含まれること"""
        assert _has_pub_containing(self.pubs, "VOC"), "タンカーにVOC管理計画が含まれるべき"


# ===========================================================================
# テスト5: 全船に共通する書籍（COLREG, MLC等）
# ===========================================================================

class TestUniversalPublications:
    """全船に共通する書籍のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        # 最小構成の船でテスト
        self.pubs = determine_required_publications({
            "ship_type": "general_cargo",
            "gross_tonnage": 100,
            "navigation_area": ["coastal"],
            "flag_state": "PAN",
            "build_year": 2020,
        })

    def test_colreg_included(self):
        """COLREGは全船に必要"""
        assert _has_pub_containing(self.pubs, "COLREG"), "COLREG は全船に必要"

    def test_mlc_included(self):
        """MLCは全船に必要"""
        assert _has_pub_containing(self.pubs, "MLC"), "MLC は全船に必要"

    def test_stcw_included(self):
        """STCWは全条約船に必要"""
        assert _has_pub_containing(self.pubs, "STCW"), "STCW は全条約船に必要"

    def test_afs_included(self):
        """AFS条約は全船に必要"""
        assert _has_pub_containing(self.pubs, "AFS"), "AFS は全船に必要"

    def test_garbage_management_plan(self):
        """廃棄物管理計画書は全船に必要"""
        assert _has_pub_containing(self.pubs, "Garbage"), "廃棄物管理計画書は全船に必要"


# ===========================================================================
# テスト6: カテゴリD — ISM適用船にSMS、400GT以上にSOPEP
# ===========================================================================

class TestCategoryDManuals:
    """カテゴリD: 船上マニュアルのテスト"""

    def test_sms_for_ism_ship(self):
        """ISM適用船にSMSが含まれること"""
        pubs = determine_required_publications(SHIP_5000GT_BULKER_INTL_JPN)
        assert _has_pub_containing(pubs, "SMS"), "ISM適用船にSMS が含まれるべき"

    def test_doc_for_ism_ship(self):
        """ISM適用船にDOCが含まれること"""
        pubs = determine_required_publications(SHIP_5000GT_BULKER_INTL_JPN)
        assert _has_pub_containing(pubs, "DOC"), "ISM適用船にDOC が含まれるべき"

    def test_sopep_for_400gt_plus(self):
        """400GT以上にSOPEPが含まれること"""
        pubs = determine_required_publications(SHIP_5000GT_BULKER_INTL_JPN)
        assert _has_pub_containing(pubs, "SOPEP"), "400GT以上にSOPEPが含まれるべき"

    def test_no_sopep_for_small_ship(self):
        """400GT未満にSOPEPが含まれないこと"""
        ship = {
            "ship_type": "general_cargo",
            "gross_tonnage": 200,
            "navigation_area": ["coastal"],
            "flag_state": "JPN",
            "build_year": 2020,
        }
        pubs = determine_required_publications(ship)
        sopep_pubs = [p for p in pubs if p["publication_id"] == "SOPEP"]
        assert len(sopep_pubs) == 0, "400GT未満にSOPEPは不要"

    def test_ssp_for_isps_ship(self):
        """ISPS適用船にSSPが含まれること"""
        pubs = determine_required_publications(SHIP_5000GT_BULKER_INTL_JPN)
        assert _has_pub_containing(pubs, "Security Plan"), "ISPS適用船にSSPが含まれるべき"

    def test_bwm_plan_for_bwm_ship(self):
        """BWM適用船にバラスト水管理計画書が含まれること"""
        pubs = determine_required_publications(SHIP_5000GT_BULKER_INTL_JPN)
        assert _has_pub_containing(pubs, "Ballast Water"), "BWM適用船にBWMPが含まれるべき"

    def test_csr_for_convention_ship(self):
        """条約適用船にCSR (Continuous Synopsis Record) が含まれること"""
        pubs = determine_required_publications(SHIP_5000GT_BULKER_INTL_JPN)
        assert _has_pub_containing(pubs, "Continuous Synopsis"), "条約船にCSRが含まれるべき"

    def test_cas_for_old_tanker(self):
        """船齢15年超のタンカーにCAS記録が含まれること"""
        pubs = determine_required_publications(SHIP_TANKER_OLD)
        assert _has_pub_containing(pubs, "CAS"), "15年超タンカーにCASが含まれるべき"


# ===========================================================================
# テスト7: 出力フォーマット
# ===========================================================================

class TestOutputFormat:
    """出力形式の検証"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pubs = determine_required_publications(SHIP_5000GT_BULKER_INTL_JPN)

    def test_required_fields(self):
        """全書籍に必須フィールドが存在すること"""
        required_fields = [
            "publication_id", "title", "title_ja", "category",
            "legal_basis", "publisher", "current_edition",
            "update_cycle", "priority", "reason", "related_conventions",
        ]
        for pub in self.pubs:
            for field in required_fields:
                assert field in pub, f"{pub['publication_id']} に {field} フィールドがない"

    def test_category_values(self):
        """categoryがA/B/C/Dのいずれかであること"""
        for pub in self.pubs:
            assert pub["category"] in ("A", "B", "C", "D"), (
                f"{pub['publication_id']} のcategoryが不正: {pub['category']}"
            )

    def test_priority_values(self):
        """priorityがmandatory/recommendedのいずれかであること"""
        for pub in self.pubs:
            assert pub["priority"] in ("mandatory", "recommended"), (
                f"{pub['publication_id']} のpriorityが不正: {pub['priority']}"
            )

    def test_no_duplicate_ids(self):
        """publication_idに重複がないこと"""
        ids = [p["publication_id"] for p in self.pubs]
        assert len(ids) == len(set(ids)), "publication_idに重複がある"

    def test_related_conventions_is_list(self):
        """related_conventionsがリストであること"""
        for pub in self.pubs:
            assert isinstance(pub["related_conventions"], list), (
                f"{pub['publication_id']} のrelated_conventionsがリストでない"
            )


# ===========================================================================
# テスト8: ユーティリティ関数
# ===========================================================================

class TestUtilityFunctions:
    """ユーティリティ関数のテスト"""

    def test_get_mandatory_only(self):
        """get_mandatory_publications が mandatory のみ返すこと"""
        pubs = get_mandatory_publications(SHIP_5000GT_BULKER_INTL_JPN)
        for p in pubs:
            assert p["priority"] == "mandatory"

    def test_summary(self):
        """get_publication_summary の構造が正しいこと"""
        summary = get_publication_summary(SHIP_5000GT_BULKER_INTL_JPN)
        assert "total" in summary
        assert "mandatory" in summary
        assert "recommended" in summary
        assert "by_category" in summary
        assert summary["total"] > 0
        assert summary["total"] == summary["mandatory"] + summary["recommended"]


# ===========================================================================
# テスト9: 船級社による分岐
# ===========================================================================

class TestClassSociety:
    """船級社による書籍分岐テスト"""

    def test_dnv_ship(self):
        """DNV船にDNV規則が含まれ、NK規則が含まれないこと"""
        ship = {**SHIP_5000GT_BULKER_INTL_JPN, "classification_society": "DNV"}
        pubs = determine_required_publications(ship)
        assert _has_pub_containing(pubs, "DNV"), "DNV船にDNV規則が含まれるべき"
        assert not _has_pub_containing(pubs, "NK鋼船規則"), "DNV船にNK鋼船規則は不要"

    def test_lr_ship(self):
        """LR船にLR規則が含まれること"""
        ship = {**SHIP_5000GT_BULKER_INTL_JPN, "classification_society": "LR"}
        pubs = determine_required_publications(ship)
        assert _has_pub_containing(pubs, "LR"), "LR船にLR規則が含まれるべき"

    def test_abs_ship(self):
        """ABS船にABS規則が含まれること"""
        ship = {**SHIP_5000GT_BULKER_INTL_JPN, "classification_society": "ABS"}
        pubs = determine_required_publications(ship)
        assert _has_pub_containing(pubs, "ABS"), "ABS船にABS規則が含まれるべき"
