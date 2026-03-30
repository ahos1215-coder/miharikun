"""
マッチングエンジン ゴールデンセット テスト
==========================================
規制 x 船舶の組み合わせに対する既知の正解（ゴールデンセット）を用いて、
ルールベースフィルタの品質を検証する。

リファクタリングによるマッチング精度の劣化を防ぐためのリグレッションテスト。
Gemini API 不要 — ルールベースロジックのみをテストする。
"""

import os
import sys

import pytest

# scripts/utils/ を import パスに追加
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "utils"
))

from matching import match_regulation_to_ship, rule_based_filter


# ---------------------------------------------------------------------------
# ゴールデン船舶プロファイル
# ---------------------------------------------------------------------------

GOLDEN_SHIP = {
    "id": "test-ship-001",
    "ship_name": "テスト丸",
    "ship_type": "bulk_carrier",
    "gross_tonnage": 5000,
    "dwt": 8000,
    "build_year": 2015,
    "classification_society": "NK",
    "flag_state": "JPN",
    "navigation_area": ["international"],
    "routes": ["Tokyo Bay → Singapore"],
    "imo_number": "1234567",
}


# ---------------------------------------------------------------------------
# ゴールデン規制データ — NOT APPLICABLE (ルールベース除外)
# ---------------------------------------------------------------------------

def _base_regulation(**overrides) -> dict:
    """規制 dict のテンプレート。overrides で個別フィールドを上書きする。"""
    reg = {
        "id": "test-reg-000",
        "source": "IMO",
        "source_id": "TEST-000",
        "title": "テスト規制",
        "summary_ja": "テスト用の規制要約。",
        "category": "safety",
        "severity": "important",
        "applicable_ship_types": None,
        "applicable_gt_min": None,
        "applicable_gt_max": None,
        "applicable_built_after": None,
        "applicable_routes": None,
        "applicable_flags": None,
        "navigation_area": None,
        "domain": "maritime",
    }
    reg.update(overrides)
    return reg


# --- 1. 船種不一致: passenger 限定 → bulk_carrier は非適用 ---
REG_SHIP_TYPE_MISMATCH = _base_regulation(
    id="test-reg-001",
    source="IMO",
    source_id="MEPC.400",
    title="Ship Recycling Requirements for Passenger Ships",
    summary_ja="旅客船のリサイクル規制に関する要件。すべての旅客船に適用。",
    applicable_ship_types=["passenger"],
    category="environment",
)

# --- 2. GT 下限不一致: GT > 10000 → GT 5000 は非適用 ---
REG_GT_MIN_MISMATCH = _base_regulation(
    id="test-reg-002",
    source="IMO",
    source_id="MSC.520",
    title="Enhanced Safety Measures for Large Vessels",
    summary_ja="GT 10,000 以上の大型船舶に対する追加安全要件。",
    applicable_gt_min=10000,
    category="safety",
)

# --- 3. 建造年不一致: 2020年以降建造 → 2015年建造は非適用 ---
REG_BUILD_YEAR_MISMATCH = _base_regulation(
    id="test-reg-003",
    source="NK",
    source_id="TEC-1400",
    title="New Construction Standards for Modern Vessels",
    summary_ja="2020年以降に建造される船舶の新しい構造基準。",
    applicable_built_after=2020,
    category="construction",
)

# --- 4. 航行区域不一致: smooth_water 限定 → international は非適用 ---
REG_NAV_AREA_MISMATCH = _base_regulation(
    id="test-reg-004",
    source="MLIT",
    source_id="KOKU-2026-01",
    title="平水区域限定の追加基準",
    summary_ja="平水区域のみを航行する船舶に対する基準改定。",
    applicable_routes=["smooth_water"],
    category="navigation",
)


# ---------------------------------------------------------------------------
# ゴールデン規制データ — NOT APPLICABLE (キーワードフィルタ)
# ---------------------------------------------------------------------------

# --- 5. 港湾施設ガイドライン → 船舶オペレーターには非適用 ---
REG_INFRASTRUCTURE = _base_regulation(
    id="test-reg-005",
    source="MLIT",
    source_id="PORT-2026-05",
    title="港湾施設における水素燃料供給設備の安全ガイドライン",
    summary_ja="港湾施設内に設置される水素燃料供給設備の設計・運用基準を定める。",
    category="infrastructure",
)

# --- 6. 審議会開催案内 → 行政手続き、船舶に直接影響なし ---
REG_ADMIN_MEETING = _base_regulation(
    id="test-reg-006",
    source="MLIT",
    source_id="SHINGI-2026-03",
    title="第45回海上安全審議会の開催について",
    summary_ja="審議会の開催案内。議題は海上交通安全に関する検討。",
    category="administrative",
)

# --- 7. 空港保安規制 → 海事と無関係（キーワード「空港保安」は未登録だが
#         航空系は category で除外されないため、ここではタイトルにインフラKWを入れる）---
REG_NON_MARITIME = _base_regulation(
    id="test-reg-007",
    source="MLIT",
    source_id="AIR-2026-01",
    title="ターミナル保安検査基準の改定について",
    summary_ja="ターミナルにおける保安検査の新基準。空港・港湾ターミナル共通。",
    category="security",
)


# ---------------------------------------------------------------------------
# ゴールデン規制データ — APPLICABLE / NEEDS_AI (除外されてはいけない)
# ---------------------------------------------------------------------------

# --- 8. SOLAS 改正: GT > 500 国際航行 → GT 5000 国際 = 除外されない ---
REG_SOLAS_APPLICABLE = _base_regulation(
    id="test-reg-008",
    source="IMO",
    source_id="MSC.530",
    title="SOLAS Chapter II-1 Amendment: Stability Requirements",
    summary_ja="SOLAS 第II-1章の改正。GT 500 以上の国際航行船舶の復原性要件を強化。",
    applicable_gt_min=500,
    applicable_routes=["international"],
    category="safety",
    severity="critical",
)

# --- 9. MARPOL Annex VI バルクキャリア対象 → 除外されない ---
REG_MARPOL_APPLICABLE = _base_regulation(
    id="test-reg-009",
    source="IMO",
    source_id="MEPC.350",
    title="MARPOL Annex VI: CII Rating for Bulk Carriers",
    summary_ja="バルクキャリアの CII 格付け計算方法の改定。2027年より適用。",
    applicable_ship_types=["bulk_carrier", "tanker", "container"],
    category="environment",
    severity="important",
)

# --- 10. NK 船級規則変更（制限未指定） → 判断できない = needs_ai ---
REG_NK_AMBIGUOUS = _base_regulation(
    id="test-reg-010",
    source="NK",
    source_id="TEC-1450",
    title="鋼船規則 C編の一部改正について",
    summary_ja="鋼船規則C編（電気設備）の一部を改正。適用範囲は改正内容による。",
    category="class_rules",
    severity="important",
)

# --- 11. (追加) 旗国不一致: パナマ船籍限定 → JPN は非適用 ---
REG_FLAG_MISMATCH = _base_regulation(
    id="test-reg-011",
    source="Panama",
    source_id="PAN-MMN-2026-01",
    title="Panama Flag Vessels: Annual Survey Extension",
    summary_ja="パナマ船籍船の年次検査期限延長に関する通達。",
    applicable_flags=["PAN"],
    category="survey",
)

# --- 12. (追加) GT 上限不一致: GT < 3000 限定 → GT 5000 は非適用 ---
REG_GT_MAX_MISMATCH = _base_regulation(
    id="test-reg-012",
    source="MLIT",
    source_id="KAIJI-2026-02",
    title="小型船舶の安全設備基準",
    summary_ja="GT 3,000 未満の小型船舶に適用される安全設備の新基準。",
    applicable_gt_max=3000,
    category="safety",
)


# ===========================================================================
# テストケース — NOT APPLICABLE (ルールベースフィールド比較)
# ===========================================================================

class TestGoldenNotApplicableRuleBased:
    """ルールベースのフィールド比較で NOT APPLICABLE と判定されるべきケース"""

    def test_01_ship_type_mismatch(self):
        """#1 船種不一致: passenger 限定 → bulk_carrier は非適用"""
        result = match_regulation_to_ship(REG_SHIP_TYPE_MISMATCH, GOLDEN_SHIP)
        assert result["is_applicable"] is False
        assert result["match_method"] == "rule_based"
        assert result["confidence"] == 1.0

    def test_02_gt_min_too_high(self):
        """#2 GT 下限不一致: GT >= 10000 → GT 5000 は非適用"""
        result = match_regulation_to_ship(REG_GT_MIN_MISMATCH, GOLDEN_SHIP)
        assert result["is_applicable"] is False
        assert result["match_method"] == "rule_based"

    def test_03_build_year_too_old(self):
        """#3 建造年不一致: 2020年以降建造限定 → 2015年建造は非適用"""
        result = match_regulation_to_ship(REG_BUILD_YEAR_MISMATCH, GOLDEN_SHIP)
        assert result["is_applicable"] is False
        assert result["match_method"] == "rule_based"

    def test_04_navigation_area_mismatch(self):
        """#4 航行区域不一致: smooth_water 限定 → international は非適用"""
        result = match_regulation_to_ship(REG_NAV_AREA_MISMATCH, GOLDEN_SHIP)
        assert result["is_applicable"] is False
        assert result["match_method"] == "rule_based"

    def test_11_flag_state_mismatch(self):
        """#11 旗国不一致: パナマ限定 → JPN は非適用"""
        result = match_regulation_to_ship(REG_FLAG_MISMATCH, GOLDEN_SHIP)
        assert result["is_applicable"] is False
        assert result["match_method"] == "rule_based"

    def test_12_gt_max_exceeded(self):
        """#12 GT 上限超過: GT < 3000 限定 → GT 5000 は非適用"""
        result = match_regulation_to_ship(REG_GT_MAX_MISMATCH, GOLDEN_SHIP)
        assert result["is_applicable"] is False
        assert result["match_method"] == "rule_based"


# ===========================================================================
# テストケース — NOT APPLICABLE (キーワードフィルタ)
# ===========================================================================

class TestGoldenNotApplicableKeyword:
    """キーワードフィルタで NOT APPLICABLE と判定されるべきケース"""

    def test_05_infrastructure_guideline(self):
        """#5 港湾施設ガイドライン → 船舶オペレーターには非適用"""
        result = match_regulation_to_ship(REG_INFRASTRUCTURE, GOLDEN_SHIP)
        assert result["is_applicable"] is False
        assert result["match_method"] == "rule_based"

    def test_06_admin_meeting(self):
        """#6 審議会開催案内 → 行政手続きで非適用"""
        result = match_regulation_to_ship(REG_ADMIN_MEETING, GOLDEN_SHIP)
        assert result["is_applicable"] is False
        assert result["match_method"] == "rule_based"

    def test_07_non_maritime_terminal(self):
        """#7 ターミナル保安規制 → インフラキーワードで非適用"""
        result = match_regulation_to_ship(REG_NON_MARITIME, GOLDEN_SHIP)
        assert result["is_applicable"] is False
        assert result["match_method"] == "rule_based"


# ===========================================================================
# テストケース — APPLICABLE / NEEDS_AI (除外されてはいけない)
# ===========================================================================

class TestGoldenPassThroughToAI:
    """
    ルールベースフィルタを通過すべきケース。
    rule_based_filter の戻り値が "applicable" または "needs_ai" であることを検証。
    match_regulation_to_ship は Gemini を呼ぶため、ここでは rule_based_filter を直接テスト。
    """

    def test_08_solas_applicable(self):
        """#8 SOLAS 改正: GT>500 国際航行 → GT 5000 国際 = 除外されない"""
        result = rule_based_filter(REG_SOLAS_APPLICABLE, GOLDEN_SHIP)
        assert result in ("applicable", "needs_ai"), (
            f"SOLAS 規制が誤って除外された: {result}"
        )

    def test_09_marpol_bulk_carrier(self):
        """#9 MARPOL Annex VI バルクキャリア → 除外されない"""
        result = rule_based_filter(REG_MARPOL_APPLICABLE, GOLDEN_SHIP)
        assert result in ("applicable", "needs_ai"), (
            f"MARPOL 規制が誤って除外された: {result}"
        )

    def test_10_nk_ambiguous(self):
        """#10 NK 船級規則（制限未指定） → needs_ai（AI に委譲すべき）"""
        result = rule_based_filter(REG_NK_AMBIGUOUS, GOLDEN_SHIP)
        assert result == "needs_ai", (
            f"制限未指定の NK 規則が AI に委譲されなかった: {result}"
        )


# ===========================================================================
# テストケース — エッジケース
# ===========================================================================

class TestGoldenEdgeCases:
    """境界値・特殊ケースのテスト"""

    def test_gt_exactly_at_minimum(self):
        """GT がちょうど下限と一致 → 除外されない"""
        reg = _base_regulation(
            id="test-edge-01",
            applicable_gt_min=5000,  # ちょうど船の GT と同じ
        )
        result = rule_based_filter(reg, GOLDEN_SHIP)
        assert result != "not_applicable", (
            "GT が下限と一致する場合は除外してはいけない"
        )

    def test_gt_exactly_at_maximum(self):
        """GT がちょうど上限と一致 → 除外されない"""
        reg = _base_regulation(
            id="test-edge-02",
            applicable_gt_max=5000,  # ちょうど船の GT と同じ
        )
        result = rule_based_filter(reg, GOLDEN_SHIP)
        assert result != "not_applicable", (
            "GT が上限と一致する場合は除外してはいけない"
        )

    def test_build_year_exactly_at_threshold(self):
        """建造年がちょうど閾値と一致 → 除外されない"""
        reg = _base_regulation(
            id="test-edge-03",
            applicable_built_after=2015,  # ちょうど船の建造年と同じ
        )
        result = rule_based_filter(reg, GOLDEN_SHIP)
        assert result != "not_applicable", (
            "建造年が閾値と一致する場合は除外してはいけない"
        )

    def test_empty_regulation_fields(self):
        """全フィールドが None/空 → needs_ai（除外されない）"""
        reg = _base_regulation(
            id="test-edge-04",
            title="General Maritime Notice",
            summary_ja="一般的な海事通知。",
        )
        result = rule_based_filter(reg, GOLDEN_SHIP)
        assert result == "needs_ai"

    def test_infrastructure_keyword_with_ship_override(self):
        """港湾施設キーワードがあるが船舶関連キーワードも含む → AI に委譲"""
        reg = _base_regulation(
            id="test-edge-05",
            title="港湾施設における船舶への陸上電力供給基準",
            summary_ja="港湾施設の陸上電力供給設備と船舶搭載受電設備の両方に関する基準。",
        )
        result = rule_based_filter(reg, GOLDEN_SHIP)
        # 「港湾施設」キーワードがヒットするが「船舶」もあるので AI に委譲
        assert result == "needs_ai", (
            "船舶関連キーワードが含まれる場合は AI に委譲すべき"
        )


# ===========================================================================
# テストケース — match_regulation_to_ship 出力形式の検証
# ===========================================================================

class TestMatchOutputSchema:
    """match_regulation_to_ship の戻り値が期待するスキーマを持つか検証"""

    def test_output_has_required_keys(self):
        """戻り値に必須キーが含まれる"""
        result = match_regulation_to_ship(REG_SHIP_TYPE_MISMATCH, GOLDEN_SHIP)
        required_keys = {
            "is_applicable", "match_method", "confidence",
            "reason", "citations", "needs_review",
        }
        assert required_keys <= set(result.keys()), (
            f"欠落キー: {required_keys - set(result.keys())}"
        )

    def test_rule_based_not_applicable_has_correct_types(self):
        """ルールベース非適用の結果が正しい型を持つ"""
        result = match_regulation_to_ship(REG_GT_MIN_MISMATCH, GOLDEN_SHIP)
        assert isinstance(result["is_applicable"], bool)
        assert isinstance(result["match_method"], str)
        assert isinstance(result["confidence"], (int, float))
        assert isinstance(result["reason"], str)
        assert isinstance(result["citations"], list)
        assert isinstance(result["needs_review"], bool)


# ===========================================================================
# テストケース — 条約ベースマッチング (Stage 0)
# ===========================================================================

class TestGoldenConventionBased:
    """
    条約ベースマッチング（Stage 0）のゴールデンセットテスト。
    Gemini API 不要 — determine_compliance + キーワード照合のみ。
    """

    def test_msc581_enclosed_space(self):
        """#C1 MSC.581 閉囲区画 → SOLAS Ch.III キーワードマッチ → 適用"""
        reg = _base_regulation(
            id="test-conv-001",
            source="IMO",
            source_id="MSC.581",
            title="閉囲区画への進入に関する改正 MSC.581",
            summary_ja="閉囲区画への進入に係る安全要件の改正。SOLAS Chapter III 関連。救命設備の点検手順を見直し。",
            category="safety",
            severity="important",
        )
        result = match_regulation_to_ship(reg, GOLDEN_SHIP)
        assert result["is_applicable"] is True
        assert result["match_method"] == "convention_based"
        assert result["confidence"] == 0.95
        assert len(result["conventions"]) > 0
        assert result["needs_review"] is False

    def test_ism_code_safety_management(self):
        """#C2 ISM + 安全管理 → SOLAS Ch.IX キーワードマッチ → 適用"""
        reg = _base_regulation(
            id="test-conv-002",
            source="IMO",
            source_id="MSC.600",
            title="ISMコードに基づく安全管理体制の強化について",
            summary_ja="ISM Code の安全管理要件改正。SMS 文書管理と内部監査の手順を見直し。",
            category="safety",
            severity="important",
        )
        result = match_regulation_to_ship(reg, GOLDEN_SHIP)
        assert result["is_applicable"] is True
        assert result["match_method"] == "convention_based"
        assert result["confidence"] == 0.95
        assert len(result["conventions"]) > 0
        assert result["needs_review"] is False

    def test_marpol_annex_vi_sox(self):
        """#C3 大気汚染 + SOx → MARPOL Annex VI キーワードマッチ → 適用"""
        reg = _base_regulation(
            id="test-conv-003",
            source="IMO",
            source_id="MEPC.400",
            title="大気汚染防止に関する MARPOL Annex VI 改正: SOx排出規制強化",
            summary_ja="MARPOL Annex VI の SOx 排出規制を強化。2027年以降 GT 400 以上の国際航行船舶に適用。",
            category="environment",
            severity="critical",
        )
        result = match_regulation_to_ship(reg, GOLDEN_SHIP)
        assert result["is_applicable"] is True
        assert result["match_method"] == "convention_based"
        assert result["confidence"] == 0.95
        assert len(result["conventions"]) > 0
        assert result["needs_review"] is False

    def test_stcw_crew_training(self):
        """#C4 STCW + 訓練 → STCW 条約キーワードマッチ → 適用"""
        reg = _base_regulation(
            id="test-conv-004",
            source="IMO",
            source_id="MSC.700",
            title="STCW条約に基づく船員訓練要件の改正",
            summary_ja="STCW Code 改正による乗組員の訓練基準の見直し。当直体制要件を更新。",
            category="safety",
            severity="important",
        )
        result = match_regulation_to_ship(reg, GOLDEN_SHIP)
        assert result["is_applicable"] is True
        assert result["match_method"] == "convention_based"
        assert result["confidence"] == 0.95
        assert len(result["conventions"]) > 0
        assert result["needs_review"] is False

    def test_ship_recycling_ihm(self):
        """#C5 リサイクル + IHM → Hong Kong Convention キーワードマッチ → 適用"""
        reg = _base_regulation(
            id="test-conv-005",
            source="IMO",
            source_id="MEPC.450",
            title="シップリサイクル条約に基づく IHM 有害物質一覧表の更新要件",
            summary_ja="Hong Kong Convention（HKC）に基づく IHM の更新手順改正。リサイクル関連。",
            category="environment",
            severity="important",
        )
        result = match_regulation_to_ship(reg, GOLDEN_SHIP)
        assert result["is_applicable"] is True
        assert result["match_method"] == "convention_based"
        assert result["confidence"] == 0.95
        assert len(result["conventions"]) > 0
        assert result["needs_review"] is False

    def test_bwm_convention_ballast_water(self):
        """#C6 バラスト水 → BWM Convention キーワードマッチ → 適用
        BWM Convention は detail_conditions=None のため applicable 判定。
        他の applicable 条約キーワードも同時マッチするため convention_based (True)。
        """
        reg = _base_regulation(
            id="test-conv-006",
            source="IMO",
            source_id="MEPC.500",
            title="バラスト水管理条約の改正について",
            summary_ja="バラスト水処理装置の型式承認基準改定。BWMS の性能要件を見直し。",
            category="environment",
            severity="important",
        )
        result = match_regulation_to_ship(reg, GOLDEN_SHIP)
        assert result["is_applicable"] is True
        assert result["match_method"] == "convention_based"
        assert result["confidence"] == 0.95
        assert len(result["conventions"]) > 0
        assert result["needs_review"] is False

    def test_passenger_only_for_bulk_carrier(self):
        """#C7 旅客船限定規制 → Stage 1 (rule_based) で除外 → not_applicable
        applicable_ship_types=["passenger"] のため、bulk_carrier は Stage 0 到達前に除外。
        """
        reg = _base_regulation(
            id="test-conv-007",
            source="IMO",
            source_id="MSC.800",
            title="旅客船の避難設備に関する安全基準の改正",
            summary_ja="旅客船における救命設備および避難経路の追加要件。SOLAS 旅客船規定の改正。",
            applicable_ship_types=["passenger"],
            category="safety",
            severity="critical",
        )
        result = match_regulation_to_ship(reg, GOLDEN_SHIP)
        assert result["is_applicable"] is False
        assert result["match_method"] == "rule_based"
        assert result["confidence"] == 1.0
        assert result["conventions"] == []
