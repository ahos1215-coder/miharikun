"""
publication_requirements.py — 備付書籍自動判定エンジン
=====================================================
船舶スペックと条約適用結果から、必要な備付書籍リストを自動判定する。

使い方:
    from utils.publication_requirements import determine_required_publications

    ship = {
        "ship_type": "bulk_carrier",
        "gross_tonnage": 5000,
        "navigation_area": ["international"],
        "flag_state": "JPN",
        "build_year": 2015,
        "classification_society": "NK",
    }
    publications = determine_required_publications(ship)

純粋データ＋ロジックファイル — API呼び出し・DB接続は一切なし。
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

try:
    from utils.ship_compliance import determine_compliance
except ImportError:
    try:
        from ship_compliance import determine_compliance
    except ImportError:
        determine_compliance = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[Publications] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# 船種定数（maritime_knowledge.py と同期）
# ---------------------------------------------------------------------------

CARGO_SHIPS = ["bulk_carrier", "tanker", "container", "general_cargo", "roro"]
GAS_CARRIERS = ["lpg", "lng"]
CHEMICAL_CARRIERS = ["chemical"]
TANKER_TYPES = ["tanker", "chemical", "lpg", "lng"]
PASSENGER_SHIPS = ["passenger"]

# ---------------------------------------------------------------------------
# カテゴリ定数
# ---------------------------------------------------------------------------

CAT_A = "A"  # 条約書籍
CAT_B = "B"  # 航海用刊行物
CAT_C = "C"  # 旗国・船級
CAT_D = "D"  # 船上マニュアル

MANDATORY = "mandatory"
RECOMMENDED = "recommended"


# ===========================================================================
# カテゴリA: 条約書籍マスターデータ
# ===========================================================================

CATEGORY_A_PUBLICATIONS: list[dict] = [
    # 1. SOLAS
    {
        "publication_id": "SOLAS_CONSOLIDATED",
        "title": "SOLAS Consolidated Edition 2024",
        "title_ja": "SOLAS統合版 2024",
        "category": CAT_A,
        "legal_basis": "SOLAS 1974 as amended",
        "publisher": "IMO",
        "current_edition": "2024 Edition",
        "current_edition_date": "2024-01-01",
        "update_cycle": "約2〜3年ごとに統合版刊行",
        "priority": MANDATORY,
        "convention_trigger": "SOLAS",
        "condition": lambda ship, conv_ids: _any_solas(conv_ids, ship),
        "applicability_rules": {
            "conventions": ["SOLAS"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "SOLAS適用船舶として全SOLAS章に基づく規則の備付義務",
    },
    # 2. MARPOL
    {
        "publication_id": "MARPOL_CONSOLIDATED",
        "title": "MARPOL Consolidated Edition (Annex I-VI)",
        "title_ja": "MARPOL統合版 (附属書I〜VI)",
        "category": CAT_A,
        "legal_basis": "MARPOL 73/78",
        "publisher": "IMO",
        "current_edition": "2022 Edition",
        "current_edition_date": "2022-01-01",
        "update_cycle": "約3年ごとに統合版刊行",
        "priority": MANDATORY,
        "convention_trigger": "MARPOL",
        "condition": lambda ship, conv_ids: _any_marpol(conv_ids),
        "applicability_rules": {
            "conventions": ["MARPOL"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "MARPOL適用船舶として海洋汚染防止条約の備付義務",
    },
    # 3. IMDG Code
    {
        "publication_id": "IMDG_CODE",
        "title": "IMDG Code (Amendment 42-24)",
        "title_ja": "国際海上危険物規程 (改正42-24)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter VII",
        "publisher": "IMO",
        "current_edition": "Amendment 42-24",
        "current_edition_date": "2024-01-01",
        "update_cycle": "2年ごと改正",
        "priority": MANDATORY,
        "convention_trigger": "SOLAS_CH_VII_DG",
        "condition": lambda ship, conv_ids: (
            "SOLAS_CH_VII_DG" in conv_ids
            and ship.get("ship_type") in CARGO_SHIPS
            and _is_solas_ship(ship)
        ),
        "applicability_rules": {
            "conventions": ["SOLAS_CH_VII_DG"],
            "ship_types": CARGO_SHIPS[:],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "SOLAS VII章適用貨物船として危険物運送規程の備付義務",
    },
    # 4. IBC Code
    {
        "publication_id": "IBC_CODE",
        "title": "IBC Code (International Code for the Construction and Equipment of Ships Carrying Dangerous Chemicals in Bulk)",
        "title_ja": "国際バルクケミカルコード (IBC Code)",
        "category": CAT_A,
        "legal_basis": "SOLAS VII / MARPOL Annex II",
        "publisher": "IMO",
        "current_edition": "2022 Edition",
        "current_edition_date": "2022-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "IBC_CODE",
        "condition": lambda ship, conv_ids: (
            ship.get("ship_type") in CHEMICAL_CARRIERS
        ),
        "applicability_rules": {
            "conventions": [],
            "ship_types": CHEMICAL_CARRIERS[:],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "ケミカルタンカーとしてIBCコードに基づく備付義務",
    },
    # 5. IGC Code
    {
        "publication_id": "IGC_CODE",
        "title": "IGC Code (International Code for the Construction and Equipment of Ships Carrying Liquefied Gases in Bulk)",
        "title_ja": "国際ガスキャリアコード (IGC Code)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter VII",
        "publisher": "IMO",
        "current_edition": "2016 Edition",
        "current_edition_date": "2016-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "IGC_CODE",
        "condition": lambda ship, conv_ids: (
            ship.get("ship_type") in GAS_CARRIERS
        ),
        "applicability_rules": {
            "conventions": [],
            "ship_types": GAS_CARRIERS[:],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "LPG/LNG船としてIGCコードに基づく備付義務",
    },
    # 6. BCH Code
    {
        "publication_id": "BCH_CODE",
        "title": "BCH Code (Code for the Construction and Equipment of Ships Carrying Dangerous Chemicals in Bulk)",
        "title_ja": "BCHコード (旧船ケミカル)",
        "category": CAT_A,
        "legal_basis": "MARPOL Annex II / SOLAS VII",
        "publisher": "IMO",
        "current_edition": "2008 Edition",
        "current_edition_date": "2008-01-01",
        "update_cycle": "不定期",
        "priority": MANDATORY,
        "convention_trigger": "IBC_CODE",
        "condition": lambda ship, conv_ids: (
            ship.get("ship_type") in CHEMICAL_CARRIERS
            and (ship.get("build_year") or 2000) < 1986
        ),
        "applicability_rules": {
            "conventions": [],
            "ship_types": CHEMICAL_CARRIERS[:],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": 1986,
            "build_year_after": None,
        },
        "reason_template": "1986年以前建造のケミカルタンカーとしてBCHコードに基づく備付義務",
    },
    # 7. ISM Code
    {
        "publication_id": "ISM_CODE",
        "title": "ISM Code (International Safety Management Code)",
        "title_ja": "国際安全管理コード (ISM Code)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter IX",
        "publisher": "IMO",
        "current_edition": "2018 Edition",
        "current_edition_date": "2018-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "SOLAS_CH_IX_ISM",
        "condition": lambda ship, conv_ids: (
            "SOLAS_CH_IX_ISM" in conv_ids and _is_solas_ship(ship)
        ),
        "applicability_rules": {
            "conventions": ["SOLAS_CH_IX_ISM"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "500GT以上の国際航行船舶にSOLAS IX章に基づくISMコードの備付義務",
    },
    # 8. ISPS Code
    {
        "publication_id": "ISPS_CODE",
        "title": "ISPS Code (International Ship and Port Facility Security Code)",
        "title_ja": "国際船舶・港湾施設保安コード (ISPS Code)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter XI-2",
        "publisher": "IMO",
        "current_edition": "2003 Edition (with amendments)",
        "current_edition_date": "2003-12-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "SOLAS_CH_XI2_ISPS",
        "condition": lambda ship, conv_ids: (
            "SOLAS_CH_XI2_ISPS" in conv_ids and _is_solas_ship(ship)
        ),
        "applicability_rules": {
            "conventions": ["SOLAS_CH_XI2_ISPS"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "500GT以上の国際航行船舶にSOLAS XI-2章に基づくISPSコードの備付義務",
    },
    # 9. STCW Convention & Code
    {
        "publication_id": "STCW_CODE",
        "title": "STCW Convention and STCW Code",
        "title_ja": "船員の訓練・資格証明・当直基準条約及びコード (STCW)",
        "category": CAT_A,
        "legal_basis": "STCW 1978 as amended (Manila 2010)",
        "publisher": "IMO",
        "current_edition": "2017 Edition",
        "current_edition_date": "2017-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "STCW",
        "condition": lambda ship, conv_ids: True,  # 全条約船
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "全ての条約適用船舶にSTCW条約・コードの備付義務",
    },
    # 10. MLC 2006
    {
        "publication_id": "MLC_2006",
        "title": "Maritime Labour Convention, 2006 (MLC)",
        "title_ja": "海上労働条約 2006 (MLC)",
        "category": CAT_A,
        "legal_basis": "MLC 2006 as amended",
        "publisher": "ILO",
        "current_edition": "2022 Consolidated Edition",
        "current_edition_date": "2022-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "MLC_2006",
        "condition": lambda ship, conv_ids: True,  # 全船
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "全ての船舶に海上労働条約の備付義務",
    },
    # 11. COLREG
    {
        "publication_id": "COLREG_1972",
        "title": "COLREG 1972 (Convention on the International Regulations for Preventing Collisions at Sea)",
        "title_ja": "1972年海上衝突予防規則条約 (COLREG)",
        "category": CAT_A,
        "legal_basis": "COLREG 1972",
        "publisher": "IMO",
        "current_edition": "2003 Consolidated Edition",
        "current_edition_date": "2003-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "COLREG",
        "condition": lambda ship, conv_ids: True,  # 全船
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "全ての船舶に海上衝突予防規則の備付義務",
    },
    # 12. Load Lines Convention
    {
        "publication_id": "LOAD_LINES",
        "title": "International Convention on Load Lines, 1966 / Protocol 1988",
        "title_ja": "国際満載喫水線条約 1966 / 1988年議定書",
        "category": CAT_A,
        "legal_basis": "Load Lines 1966/1988",
        "publisher": "IMO",
        "current_edition": "2021 Edition",
        "current_edition_date": "2021-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "LOAD_LINE",
        "condition": lambda ship, conv_ids: _is_international(ship),
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "国際航行船舶に満載喫水線条約に基づく備付義務",
    },
    # 13. Tonnage Convention
    {
        "publication_id": "TONNAGE_1969",
        "title": "International Convention on Tonnage Measurement of Ships, 1969",
        "title_ja": "1969年船舶トン数測度条約",
        "category": CAT_A,
        "legal_basis": "Tonnage Convention 1969",
        "publisher": "IMO",
        "current_edition": "1982 Edition",
        "current_edition_date": "1982-01-01",
        "update_cycle": "改正頻度低",
        "priority": MANDATORY,
        "convention_trigger": "TONNAGE_CONVENTION",
        "condition": lambda ship, conv_ids: _is_international(ship),
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "国際航行船舶にトン数測度条約に基づく備付義務",
    },
    # 14. IAMSAR Manual Vol.III
    {
        "publication_id": "IAMSAR_VOL3",
        "title": "IAMSAR Manual Volume III (Mobile Facilities)",
        "title_ja": "国際航空海上捜索救助マニュアル 第III巻 (船上用)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter V, Reg. 21",
        "publisher": "IMO / ICAO",
        "current_edition": "2022 Edition",
        "current_edition_date": "2022-01-01",
        "update_cycle": "約3年ごと",
        "priority": MANDATORY,
        "convention_trigger": "SOLAS_CH_V_NAVIGATION",
        "condition": lambda ship, conv_ids: (
            "SOLAS_CH_V_NAVIGATION" in conv_ids and _is_solas_ship(ship)
        ),
        "applicability_rules": {
            "conventions": ["SOLAS_CH_V_NAVIGATION"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "SOLAS V章適用船舶にIAMSARマニュアルの備付義務（Reg. V/21）",
    },
    # 15. LSA Code
    {
        "publication_id": "LSA_CODE",
        "title": "LSA Code (International Life-Saving Appliance Code)",
        "title_ja": "国際救命設備コード (LSA Code)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter III",
        "publisher": "IMO",
        "current_edition": "2023 Edition",
        "current_edition_date": "2023-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "SOLAS_CH_III_LSA",
        "condition": lambda ship, conv_ids: _any_solas(conv_ids, ship),
        "applicability_rules": {
            "conventions": ["SOLAS"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "SOLAS適用船舶にLSAコードの備付義務",
    },
    # 16. FSS Code
    {
        "publication_id": "FSS_CODE",
        "title": "FSS Code (International Code for Fire Safety Systems)",
        "title_ja": "国際火災安全システムコード (FSS Code)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter II-2",
        "publisher": "IMO",
        "current_edition": "2015 Edition",
        "current_edition_date": "2015-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "SOLAS_CH_II2_FIRE",
        "condition": lambda ship, conv_ids: _any_solas(conv_ids, ship),
        "applicability_rules": {
            "conventions": ["SOLAS"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "SOLAS適用船舶にFSSコードの備付義務",
    },
    # 17. FTP Code
    {
        "publication_id": "FTP_CODE",
        "title": "FTP Code (International Code for Application of Fire Test Procedures)",
        "title_ja": "国際耐火試験手順コード (FTP Code)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter II-2",
        "publisher": "IMO",
        "current_edition": "2010 Edition (2012 FTP Code)",
        "current_edition_date": "2012-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "SOLAS_CH_II2_FIRE",
        "condition": lambda ship, conv_ids: _any_solas(conv_ids, ship),
        "applicability_rules": {
            "conventions": ["SOLAS"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "SOLAS適用船舶にFTPコードの備付義務",
    },
    # 18. CSS Code
    {
        "publication_id": "CSS_CODE",
        "title": "CSS Code (Code of Safe Practice for Cargo Stowage and Securing)",
        "title_ja": "貨物積付・固定安全実施要綱 (CSS Code)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter VI",
        "publisher": "IMO",
        "current_edition": "2021 Edition",
        "current_edition_date": "2021-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "SOLAS_CH_VI_CARGO",
        "condition": lambda ship, conv_ids: ship.get("ship_type") in CARGO_SHIPS,
        "applicability_rules": {
            "conventions": [],
            "ship_types": CARGO_SHIPS[:],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "貨物船としてCSSコードに基づく備付義務",
    },
    # 19. Grain Code
    {
        "publication_id": "GRAIN_CODE",
        "title": "International Code for the Safe Carriage of Grain in Bulk (International Grain Code)",
        "title_ja": "穀類運送国際コード (Grain Code)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter VI, Part C",
        "publisher": "IMO",
        "current_edition": "1991 Edition",
        "current_edition_date": "1991-01-01",
        "update_cycle": "改正頻度低",
        "priority": MANDATORY,
        "convention_trigger": "SOLAS_CH_VI_CARGO",
        "condition": lambda ship, conv_ids: ship.get("ship_type") in ["bulk_carrier", "general_cargo"],
        "applicability_rules": {
            "conventions": [],
            "ship_types": ["bulk_carrier", "general_cargo"],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "穀類運送可能船舶としてGrain Codeの備付義務",
    },
    # 20. ESP Code
    {
        "publication_id": "ESP_CODE",
        "title": "ESP Code (Enhanced Survey Programme)",
        "title_ja": "強化検査プログラムコード (ESP Code)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter XI-1, Reg. 2",
        "publisher": "IMO",
        "current_edition": "2022 Edition",
        "current_edition_date": "2022-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "SOLAS_CH_XI1_ESP",
        "condition": lambda ship, conv_ids: (
            ship.get("ship_type") in ["bulk_carrier", "tanker"]
            and _is_solas_ship(ship)
        ),
        "applicability_rules": {
            "conventions": [],
            "ship_types": ["bulk_carrier", "tanker"],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "バルカー・タンカーとしてESPコードに基づく強化検査の備付義務",
    },
    # 21. BWM Convention
    {
        "publication_id": "BWM_CONVENTION",
        "title": "International Convention for the Control and Management of Ships' Ballast Water and Sediments (BWM Convention)",
        "title_ja": "バラスト水管理条約 (BWM Convention)",
        "category": CAT_A,
        "legal_basis": "BWM Convention 2004",
        "publisher": "IMO",
        "current_edition": "2004 Edition (with 2024 amendments)",
        "current_edition_date": "2024-01-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "BWM_CONVENTION",
        "condition": lambda ship, conv_ids: "BWM_CONVENTION" in conv_ids,
        "applicability_rules": {
            "conventions": ["BWM_CONVENTION"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "バラスト水管理条約適用船舶としてBWM条約の備付義務",
    },
    # 22. AFS Convention
    {
        "publication_id": "AFS_CONVENTION",
        "title": "AFS Convention (International Convention on the Control of Harmful Anti-Fouling Systems on Ships)",
        "title_ja": "船舶有害防汚方法規制条約 (AFS Convention)",
        "category": CAT_A,
        "legal_basis": "AFS Convention 2001",
        "publisher": "IMO",
        "current_edition": "2001 Edition (with amendments)",
        "current_edition_date": "2001-10-05",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "AFS_CONVENTION",
        "condition": lambda ship, conv_ids: True,  # 全船
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "全ての船舶にAFS条約に基づく備付義務",
    },
    # 23. Hong Kong Convention
    {
        "publication_id": "HONG_KONG_CONVENTION",
        "title": "Hong Kong International Convention for the Safe and Environmentally Sound Recycling of Ships, 2009",
        "title_ja": "シップリサイクル条約 (香港条約)",
        "category": CAT_A,
        "legal_basis": "Hong Kong Convention 2009",
        "publisher": "IMO",
        "current_edition": "2009 Edition",
        "current_edition_date": "2009-05-15",
        "update_cycle": "発効後改正予定",
        "priority": MANDATORY,
        "convention_trigger": "SHIP_RECYCLING_HKC",
        "condition": lambda ship, conv_ids: True,  # 全船
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "全ての船舶に香港条約に基づく備付義務",
    },
    # 24. Nairobi WRC
    {
        "publication_id": "NAIROBI_WRC",
        "title": "Nairobi International Convention on the Removal of Wrecks, 2007",
        "title_ja": "ナイロビ残骸物除去条約 (Nairobi WRC 2007)",
        "category": CAT_A,
        "legal_basis": "Nairobi WRC 2007",
        "publisher": "IMO",
        "current_edition": "2007 Edition",
        "current_edition_date": "2007-05-18",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "NAIROBI_WRC",
        "condition": lambda ship, conv_ids: True,  # 全船
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "全ての船舶にナイロビ残骸物除去条約の備付義務",
    },
    # 25. CTU Code
    {
        "publication_id": "CTU_CODE",
        "title": "CTU Code (IMO/ILO/UNECE Code of Practice for Packing of Cargo Transport Units)",
        "title_ja": "貨物輸送ユニット積載コード (CTU Code)",
        "category": CAT_A,
        "legal_basis": "MSC.1/Circ.1497",
        "publisher": "IMO / ILO / UNECE",
        "current_edition": "2014 Edition",
        "current_edition_date": "2014-01-01",
        "update_cycle": "不定期改正",
        "priority": RECOMMENDED,
        "convention_trigger": "SOLAS_CH_VII_DG",
        "condition": lambda ship, conv_ids: ship.get("ship_type") == "container",
        "applicability_rules": {
            "conventions": [],
            "ship_types": ["container"],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "コンテナ船としてCTUコードの備付推奨",
    },
    # 26. NOx Technical Code
    {
        "publication_id": "NOX_TECHNICAL_CODE",
        "title": "NOx Technical Code 2008",
        "title_ja": "NOx技術コード 2008",
        "category": CAT_A,
        "legal_basis": "MARPOL Annex VI, Reg. 13",
        "publisher": "IMO",
        "current_edition": "2008 Edition (with amendments)",
        "current_edition_date": "2008-10-01",
        "update_cycle": "不定期改正",
        "priority": MANDATORY,
        "convention_trigger": "NOX_TECHNICAL_CODE",
        "condition": lambda ship, conv_ids: (
            "NOX_TECHNICAL_CODE" in conv_ids
            or "MARPOL_ANNEX_VI_AIR" in conv_ids
        ),
        "applicability_rules": {
            "conventions": ["NOX_TECHNICAL_CODE", "MARPOL_ANNEX_VI_AIR"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "MARPOL Annex VI適用船舶にNOx技術コードの備付義務",
    },
    # 27. IMSBC Code
    {
        "publication_id": "IMSBC_CODE",
        "title": "IMSBC Code (International Maritime Solid Bulk Cargoes Code)",
        "title_ja": "国際海上固体ばら積貨物コード (IMSBC Code)",
        "category": CAT_A,
        "legal_basis": "SOLAS Chapter VI, Part B",
        "publisher": "IMO",
        "current_edition": "2023 Edition (Amendment 07-23)",
        "current_edition_date": "2023-12-01",
        "update_cycle": "2年ごと改正",
        "priority": MANDATORY,
        "convention_trigger": "IMSBC_CODE",
        "condition": lambda ship, conv_ids: (
            "IMSBC_CODE" in conv_ids
            or ship.get("ship_type") in ["bulk_carrier", "general_cargo"]
        ),
        "applicability_rules": {
            "conventions": ["IMSBC_CODE"],
            "ship_types": ["bulk_carrier", "general_cargo"],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "ばら積貨物運送船としてIMSBCコードの備付義務",
    },
]


# ===========================================================================
# カテゴリB: 航海用刊行物マスターデータ
# ===========================================================================

# --- 日本水路部 ---
JHO_PUBLICATIONS: list[dict] = [
    {
        "publication_id": "JHO_CHART_CATALOG",
        "title": "Chart Catalogue (Japan Hydrographic Office)",
        "title_ja": "海図総目録",
        "category": CAT_B,
        "legal_basis": "海上保安庁法 / 水路業務法",
        "publisher": "日本水路協会",
        "current_edition": "2026年版",
        "current_edition_date": "2026-04-01",
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として海図総目録の備付義務",
    },
    {
        "publication_id": "JHO_SAILING_DIRECTIONS",
        "title": "Sailing Directions (Japan)",
        "title_ja": "水路誌",
        "category": CAT_B,
        "legal_basis": "船舶安全法 / 船舶設備規程",
        "publisher": "日本水路協会",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "不定期改訂",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として水路誌の備付義務",
    },
    {
        "publication_id": "JHO_LIST_OF_LIGHTS",
        "title": "List of Lights (Japan)",
        "title_ja": "灯台表",
        "category": CAT_B,
        "legal_basis": "船舶安全法 / 船舶設備規程",
        "publisher": "日本水路協会",
        "current_edition": "2026年版",
        "current_edition_date": "2026-01-01",
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として灯台表の備付義務",
    },
    {
        "publication_id": "JHO_TIDE_TABLES",
        "title": "Tide Tables (Japan)",
        "title_ja": "潮汐表",
        "category": CAT_B,
        "legal_basis": "船舶安全法 / 船舶設備規程",
        "publisher": "日本水路協会",
        "current_edition": "2026年版",
        "current_edition_date": "2026-01-01",
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として潮汐表の備付義務",
    },
    {
        "publication_id": "JHO_NAUTICAL_ALMANAC",
        "title": "Nautical Almanac",
        "title_ja": "天測暦",
        "category": CAT_B,
        "legal_basis": "船舶安全法 / 船舶設備規程",
        "publisher": "日本水路協会",
        "current_edition": "2026年版",
        "current_edition_date": "2026-01-01",
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として天測暦の備付義務",
    },
    {
        "publication_id": "JHO_NAUTICAL_ALMANAC_ABRIDGED",
        "title": "Abridged Nautical Almanac",
        "title_ja": "天測略暦",
        "category": CAT_B,
        "legal_basis": "船舶安全法 / 船舶設備規程",
        "publisher": "日本水路協会",
        "current_edition": "2026年版",
        "current_edition_date": "2026-01-01",
        "update_cycle": "年1回",
        "priority": RECOMMENDED,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として天測略暦の備付推奨",
    },
    {
        "publication_id": "JHO_DISTANCE_TABLES",
        "title": "Table of Distances",
        "title_ja": "距離表",
        "category": CAT_B,
        "legal_basis": "船舶安全法 / 船舶設備規程",
        "publisher": "日本水路協会",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "不定期改訂",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として距離表の備付義務",
    },
    {
        "publication_id": "JHO_NOTICES_TO_MARINERS",
        "title": "Notices to Mariners (Weekly)",
        "title_ja": "水路通報",
        "category": CAT_B,
        "legal_basis": "船舶安全法 / 水路業務法",
        "publisher": "海上保安庁",
        "current_edition": "最新号",
        "current_edition_date": None,
        "update_cycle": "週1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として水路通報の備付義務",
    },
]

# --- UKHO (Admiralty) ---
UKHO_PUBLICATIONS: list[dict] = [
    {
        "publication_id": "ADMIRALTY_MARINERS_HANDBOOK",
        "title": "NP100 The Mariner's Handbook",
        "title_ja": "NP100 マリナーズハンドブック",
        "category": CAT_B,
        "legal_basis": "SOLAS Chapter V",
        "publisher": "UKHO (Admiralty)",
        "current_edition": "12th Edition (2020)",
        "current_edition_date": "2020-01-01",
        "update_cycle": "不定期改訂",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "国際航行船舶にSOLAS V章に基づくNP100の備付義務",
    },
    {
        "publication_id": "ADMIRALTY_OCEAN_PASSAGES",
        "title": "NP136 Ocean Passages for the World",
        "title_ja": "NP136 世界の海上航路",
        "category": CAT_B,
        "legal_basis": "SOLAS Chapter V",
        "publisher": "UKHO (Admiralty)",
        "current_edition": "2021 Edition",
        "current_edition_date": "2021-01-01",
        "update_cycle": "不定期改訂",
        "priority": RECOMMENDED,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "国際航行船舶にNP136の備付推奨",
    },
    {
        "publication_id": "ADMIRALTY_LIST_OF_LIGHTS",
        "title": "Admiralty List of Lights and Fog Signals (NP74-84)",
        "title_ja": "英国水路部灯台表 (NP74-84)",
        "category": CAT_B,
        "legal_basis": "SOLAS Chapter V",
        "publisher": "UKHO (Admiralty)",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "国際航行船舶にAdmiralty灯台表の備付義務",
    },
    {
        "publication_id": "ADMIRALTY_TIDE_TABLES",
        "title": "Admiralty Tide Tables (NP201-204)",
        "title_ja": "英国水路部潮汐表 (NP201-204)",
        "category": CAT_B,
        "legal_basis": "SOLAS Chapter V",
        "publisher": "UKHO (Admiralty)",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "国際航行船舶にAdmiralty潮汐表の備付義務",
    },
    {
        "publication_id": "ADMIRALTY_SAILING_DIRECTIONS",
        "title": "Admiralty Sailing Directions (Pilots)",
        "title_ja": "英国水路部水路誌 (Pilots)",
        "category": CAT_B,
        "legal_basis": "SOLAS Chapter V",
        "publisher": "UKHO (Admiralty)",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "不定期改訂",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "国際航行船舶にAdmiralty水路誌の備付義務",
    },
]

# --- NGA (米国) ---
NGA_PUBLICATIONS: list[dict] = [
    {
        "publication_id": "NGA_AMERICAN_PRACTICAL_NAV",
        "title": "Pub. 9 The American Practical Navigator (Bowditch)",
        "title_ja": "Pub.9 米国実用航海書 (Bowditch)",
        "category": CAT_B,
        "legal_basis": "SOLAS Chapter V",
        "publisher": "NGA (National Geospatial-Intelligence Agency)",
        "current_edition": "2019 Edition",
        "current_edition_date": "2019-01-01",
        "update_cycle": "不定期改訂",
        "priority": RECOMMENDED,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "国際航行船舶にBowditchの備付推奨",
    },
    {
        "publication_id": "NGA_INT_CODE_OF_SIGNALS",
        "title": "Pub. 102 International Code of Signals (ICS)",
        "title_ja": "Pub.102 国際信号書",
        "category": CAT_B,
        "legal_basis": "SOLAS Chapter V, Reg. 21",
        "publisher": "NGA / IMO",
        "current_edition": "2005 Edition",
        "current_edition_date": "2005-01-01",
        "update_cycle": "不定期改訂",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "SOLAS V章に基づく国際信号書の備付義務",
    },
    {
        "publication_id": "NGA_RADIO_NAV_AIDS",
        "title": "Pub. 117 Radio Navigational Aids",
        "title_ja": "Pub.117 無線航行援助書",
        "category": CAT_B,
        "legal_basis": "SOLAS Chapter V",
        "publisher": "NGA",
        "current_edition": "2017 Edition",
        "current_edition_date": "2017-01-01",
        "update_cycle": "不定期改訂",
        "priority": RECOMMENDED,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "国際航行船舶にPub.117の備付推奨",
    },
]


# ===========================================================================
# カテゴリC: 旗国・船級マスターデータ
# ===========================================================================

# --- 日本旗国書籍 ---
JPN_FLAG_PUBLICATIONS: list[dict] = [
    {
        "publication_id": "JPN_SHIP_SAFETY_ACT",
        "title": "Ship Safety Act and Related Regulations",
        "title_ja": "船舶安全法関連法令集",
        "category": CAT_C,
        "legal_basis": "船舶安全法",
        "publisher": "海文堂 / 成山堂",
        "current_edition": "2025年版",
        "current_edition_date": "2025-04-01",
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として船舶安全法関連法令集の備付義務",
    },
    {
        "publication_id": "JPN_SEAFARERS_ACT",
        "title": "Seafarers Act and Related Regulations",
        "title_ja": "船員法関連法令集",
        "category": CAT_C,
        "legal_basis": "船員法",
        "publisher": "海文堂 / 成山堂",
        "current_edition": "2025年版",
        "current_edition_date": "2025-04-01",
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として船員法関連法令集の備付義務",
    },
    {
        "publication_id": "JPN_COLREG_COMMENTARY",
        "title": "Commentary on COLREG (Japanese Edition)",
        "title_ja": "海上衝突予防法解説",
        "category": CAT_C,
        "legal_basis": "海上衝突予防法",
        "publisher": "海文堂",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "不定期改訂",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として海上衝突予防法解説の備付義務",
    },
    {
        "publication_id": "JPN_PORT_REGULATIONS",
        "title": "Port Regulations Act",
        "title_ja": "港則法",
        "category": CAT_C,
        "legal_basis": "港則法",
        "publisher": "海文堂 / 成山堂",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "不定期改訂",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として港則法の備付義務",
    },
    {
        "publication_id": "JPN_MARITIME_TRAFFIC_SAFETY",
        "title": "Maritime Traffic Safety Act",
        "title_ja": "海上交通安全法",
        "category": CAT_C,
        "legal_basis": "海上交通安全法",
        "publisher": "海文堂 / 成山堂",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "不定期改訂",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": "JPN",
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "日本旗船として海上交通安全法の備付義務",
    },
]

# --- ClassNK ---
NK_PUBLICATIONS: list[dict] = [
    {
        "publication_id": "NK_STEEL_SHIP_RULES",
        "title": "ClassNK Rules and Guidance for the Survey and Construction of Steel Ships",
        "title_ja": "NK鋼船規則",
        "category": CAT_C,
        "legal_basis": "ClassNK Rules",
        "publisher": "日本海事協会 (ClassNK)",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": "NK",
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "ClassNK船級船として鋼船規則の備付義務",
    },
    {
        "publication_id": "NK_TECHNICAL_INFO",
        "title": "ClassNK Technical Information",
        "title_ja": "NK技術情報",
        "category": CAT_C,
        "legal_basis": "ClassNK Guidance",
        "publisher": "日本海事協会 (ClassNK)",
        "current_edition": "最新号",
        "current_edition_date": None,
        "update_cycle": "随時",
        "priority": RECOMMENDED,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": "NK",
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "ClassNK船級船としてNK技術情報の参照推奨",
    },
    {
        "publication_id": "NK_RULES_GUIDANCE",
        "title": "ClassNK Rules & Guidance (Full Set)",
        "title_ja": "NK規則・ガイダンス全集",
        "category": CAT_C,
        "legal_basis": "ClassNK Rules",
        "publisher": "日本海事協会 (ClassNK)",
        "current_edition": "2026 Edition",
        "current_edition_date": "2026-01-01",
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": "NK",
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "ClassNK船級船として規則・ガイダンスの備付義務",
    },
    {
        "publication_id": "NK_SURVEY_GUIDELINES",
        "title": "ClassNK Survey Procedure Manual",
        "title_ja": "NK検査要領",
        "category": CAT_C,
        "legal_basis": "ClassNK Guidance",
        "publisher": "日本海事協会 (ClassNK)",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "不定期改訂",
        "priority": RECOMMENDED,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": "NK",
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "ClassNK船級船としてNK検査要領の参照推奨",
    },
]

# --- DNV ---
DNV_PUBLICATIONS: list[dict] = [
    {
        "publication_id": "DNV_RULES",
        "title": "DNV Rules for Classification of Ships",
        "title_ja": "DNV船級規則",
        "category": CAT_C,
        "legal_basis": "DNV Rules",
        "publisher": "DNV",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "年2回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": "DNV",
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "DNV船級船としてDNV規則の備付義務",
    },
]

# --- LR ---
LR_PUBLICATIONS: list[dict] = [
    {
        "publication_id": "LR_RULES",
        "title": "Lloyd's Register Rules and Regulations for the Classification of Ships",
        "title_ja": "LR船級規則",
        "category": CAT_C,
        "legal_basis": "LR Rules",
        "publisher": "Lloyd's Register",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": "LR",
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "LR船級船としてLR規則の備付義務",
    },
]

# --- ABS ---
ABS_PUBLICATIONS: list[dict] = [
    {
        "publication_id": "ABS_RULES",
        "title": "ABS Rules for Building and Classing Marine Vessels",
        "title_ja": "ABS船級規則",
        "category": CAT_C,
        "legal_basis": "ABS Rules",
        "publisher": "American Bureau of Shipping (ABS)",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "年1回",
        "priority": MANDATORY,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": "ABS",
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "ABS船級船としてABS規則の備付義務",
    },
]

# 船級社マッピング
CLASS_SOCIETY_PUBLICATIONS: dict[str, list[dict]] = {
    "NK": NK_PUBLICATIONS,
    "ClassNK": NK_PUBLICATIONS,
    "DNV": DNV_PUBLICATIONS,
    "DNV-GL": DNV_PUBLICATIONS,
    "LR": LR_PUBLICATIONS,
    "ABS": ABS_PUBLICATIONS,
}


# ===========================================================================
# カテゴリD: 船上マニュアルマスターデータ
# ===========================================================================

CATEGORY_D_PUBLICATIONS: list[dict] = [
    # 56. SMS
    {
        "publication_id": "SMS_MANUAL",
        "title": "Safety Management Manual (SMS)",
        "title_ja": "安全管理マニュアル (SMS)",
        "category": CAT_D,
        "legal_basis": "ISM Code, Section 11",
        "publisher": "管理会社作成",
        "current_edition": "自社版最新",
        "current_edition_date": None,
        "update_cycle": "随時改訂",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: "SOLAS_CH_IX_ISM" in conv_ids and _is_solas_ship(ship),
        "applicability_rules": {
            "conventions": ["SOLAS_CH_IX_ISM"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "ISM Code適用船舶としてSMSマニュアルの備付義務",
        "related_conventions_static": ["SOLAS_CH_IX_ISM"],
    },
    # 57. DOC
    {
        "publication_id": "DOC_CERTIFICATE",
        "title": "Document of Compliance (DOC) — Copy on board",
        "title_ja": "適合証書 (DOC) — 船上コピー",
        "category": CAT_D,
        "legal_basis": "ISM Code, Section 13",
        "publisher": "旗国/船級協会",
        "current_edition": "最新発行",
        "current_edition_date": None,
        "update_cycle": "5年ごと更新",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: "SOLAS_CH_IX_ISM" in conv_ids and _is_solas_ship(ship),
        "applicability_rules": {
            "conventions": ["SOLAS_CH_IX_ISM"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "ISM Code適用船舶としてDOCコピーの船上備付義務",
        "related_conventions_static": ["SOLAS_CH_IX_ISM"],
    },
    # 58. CSM
    {
        "publication_id": "CARGO_SECURING_MANUAL",
        "title": "Cargo Securing Manual (CSM)",
        "title_ja": "貨物固縛マニュアル (CSM)",
        "category": CAT_D,
        "legal_basis": "SOLAS Chapter VI / CSS Code",
        "publisher": "船主・管理会社作成（船級承認）",
        "current_edition": "自船版最新",
        "current_edition_date": None,
        "update_cycle": "随時改訂",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: ship.get("ship_type") in CARGO_SHIPS,
        "applicability_rules": {
            "conventions": [],
            "ship_types": CARGO_SHIPS[:],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "貨物船として貨物固縛マニュアルの備付義務",
        "related_conventions_static": ["SOLAS_CH_VI_CARGO"],
    },
    # 59. SOPEP
    {
        "publication_id": "SOPEP",
        "title": "Shipboard Oil Pollution Emergency Plan (SOPEP)",
        "title_ja": "船舶油濁防止緊急措置手引書 (SOPEP)",
        "category": CAT_D,
        "legal_basis": "MARPOL Annex I, Reg. 37",
        "publisher": "管理会社作成（旗国承認）",
        "current_edition": "自船版最新",
        "current_edition_date": None,
        "update_cycle": "随時改訂",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: (ship.get("gross_tonnage") or 0) >= 400,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 400,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "400GT以上の船舶にMARPOL Annex I Reg.37に基づくSOPEPの備付義務",
        "related_conventions_static": ["MARPOL_ANNEX_I"],
    },
    # 60. SMPEP
    {
        "publication_id": "SMPEP",
        "title": "Shipboard Marine Pollution Emergency Plan (SMPEP)",
        "title_ja": "船舶海洋汚染防止緊急措置手引書 (SMPEP)",
        "category": CAT_D,
        "legal_basis": "MARPOL Annex II / Protocol I",
        "publisher": "管理会社作成（旗国承認）",
        "current_edition": "自船版最新",
        "current_edition_date": None,
        "update_cycle": "随時改訂",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: (
            ship.get("ship_type") in CHEMICAL_CARRIERS + GAS_CARRIERS
        ),
        "applicability_rules": {
            "conventions": [],
            "ship_types": CHEMICAL_CARRIERS + GAS_CARRIERS,
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "ケミカル/ガスキャリアとしてSMPEPの備付義務",
        "related_conventions_static": ["MARPOL_ANNEX_II"],
    },
    # 61. BWM Plan
    {
        "publication_id": "BWMP",
        "title": "Ballast Water Management Plan (BWMP)",
        "title_ja": "バラスト水管理計画書 (BWMP)",
        "category": CAT_D,
        "legal_basis": "BWM Convention, Reg. B-1",
        "publisher": "管理会社作成（旗国承認）",
        "current_edition": "自船版最新",
        "current_edition_date": None,
        "update_cycle": "随時改訂",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: "BWM_CONVENTION" in conv_ids,
        "applicability_rules": {
            "conventions": ["BWM_CONVENTION"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "BWM条約適用船舶としてバラスト水管理計画書の備付義務",
        "related_conventions_static": ["BWM_CONVENTION"],
    },
    # 62. SSP
    {
        "publication_id": "SHIP_SECURITY_PLAN",
        "title": "Ship Security Plan (SSP)",
        "title_ja": "船舶保安計画書 (SSP)",
        "category": CAT_D,
        "legal_basis": "ISPS Code, Part A, Section 9",
        "publisher": "管理会社作成（旗国承認）",
        "current_edition": "自船版最新",
        "current_edition_date": None,
        "update_cycle": "随時改訂",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: "SOLAS_CH_XI2_ISPS" in conv_ids and _is_solas_ship(ship),
        "applicability_rules": {
            "conventions": ["SOLAS_CH_XI2_ISPS"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "ISPS Code適用船舶として船舶保安計画書の備付義務",
        "related_conventions_static": ["SOLAS_CH_XI2_ISPS"],
    },
    # 63. Garbage Management Plan
    {
        "publication_id": "GARBAGE_MANAGEMENT_PLAN",
        "title": "Garbage Management Plan",
        "title_ja": "廃棄物管理計画書",
        "category": CAT_D,
        "legal_basis": "MARPOL Annex V, Reg. 10.2",
        "publisher": "管理会社作成",
        "current_edition": "自船版最新",
        "current_edition_date": None,
        "update_cycle": "随時改訂",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: True,  # 全船（MARPOL V）
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "全ての船舶にMARPOL Annex V Reg.10.2に基づく廃棄物管理計画書の備付義務",
        "related_conventions_static": ["MARPOL_ANNEX_V"],
    },
    # 64. SEEMP
    {
        "publication_id": "SEEMP",
        "title": "Ship Energy Efficiency Management Plan (SEEMP)",
        "title_ja": "船舶エネルギー効率管理計画書 (SEEMP)",
        "category": CAT_D,
        "legal_basis": "MARPOL Annex VI, Reg. 26",
        "publisher": "管理会社作成（旗国承認）",
        "current_edition": "Part I & Part II (CII)",
        "current_edition_date": None,
        "update_cycle": "随時改訂",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: (ship.get("gross_tonnage") or 0) >= 400,
        "applicability_rules": {
            "conventions": [],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 400,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "400GT以上の船舶にMARPOL Annex VI Reg.26に基づくSEEMPの備付義務",
        "related_conventions_static": ["MARPOL_ANNEX_VI_AIR", "MARPOL_ANNEX_VI_GHG"],
    },
    # 65. VOC Management Plan
    {
        "publication_id": "VOC_MANAGEMENT_PLAN",
        "title": "VOC Management Plan",
        "title_ja": "揮発性有機化合物管理計画書 (VOC)",
        "category": CAT_D,
        "legal_basis": "MARPOL Annex VI, Reg. 15",
        "publisher": "管理会社作成",
        "current_edition": "自船版最新",
        "current_edition_date": None,
        "update_cycle": "随時改訂",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: ship.get("ship_type") in TANKER_TYPES,
        "applicability_rules": {
            "conventions": [],
            "ship_types": TANKER_TYPES[:],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "タンカーとしてMARPOL Annex VI Reg.15に基づくVOC管理計画の備付義務",
        "related_conventions_static": ["MARPOL_ANNEX_VI_AIR"],
    },
    # 66. CAS Record
    {
        "publication_id": "CAS_RECORD",
        "title": "Condition Assessment Scheme Record (CAS)",
        "title_ja": "船体状態評価記録 (CAS)",
        "category": CAT_D,
        "legal_basis": "MARPOL Annex I, Reg. 20 / 21",
        "publisher": "船級協会",
        "current_edition": "自船版最新",
        "current_edition_date": None,
        "update_cycle": "中間検査時",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: (
            ship.get("ship_type") in TANKER_TYPES
            and (ship.get("build_year") or 2020) <= (date.today().year - 15)
        ),
        "applicability_rules": {
            "conventions": [],
            "ship_types": TANKER_TYPES[:],
            "excluded_types": [],
            "gt_min": None,
            "gt_max": None,
            "navigation": [],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "船齢15年超のタンカーとしてCAS記録の備付義務",
        "related_conventions_static": ["MARPOL_ANNEX_I", "MARPOL_I_TANKER"],
    },
    # 67. CSR (Continuous Synopsis Record)
    {
        "publication_id": "CONTINUOUS_SYNOPSIS_RECORD",
        "title": "Continuous Synopsis Record (CSR)",
        "title_ja": "継続概要記録簿 (CSR)",
        "category": CAT_D,
        "legal_basis": "SOLAS Chapter XI-1, Reg. 5",
        "publisher": "旗国発行",
        "current_edition": "最新版",
        "current_edition_date": None,
        "update_cycle": "変更の都度",
        "priority": MANDATORY,
        "condition": lambda ship, conv_ids: _any_solas(conv_ids, ship),
        "applicability_rules": {
            "conventions": ["SOLAS"],
            "ship_types": [],
            "excluded_types": [],
            "gt_min": 500,
            "gt_max": None,
            "navigation": ["international"],
            "flag_state": None,
            "class_society": None,
            "radio_equipment": [],
            "build_year_before": None,
            "build_year_after": None,
        },
        "reason_template": "全ての条約適用船舶にSOLAS XI-1 Reg.5に基づくCSRの備付義務",
        "related_conventions_static": ["SOLAS_CH_XI1_ESP"],
    },
]


# ===========================================================================
# ヘルパー関数
# ===========================================================================

def _is_solas_ship(ship: dict) -> bool:
    """SOLAS条約船かどうか（500GT以上かつ国際航行）"""
    gt = ship.get("gross_tonnage") or 0
    return gt >= 500 and _is_international(ship)


def _any_solas(conv_ids: set[str], ship: Optional[dict] = None) -> bool:
    """適用条約にいずれかのSOLAS章が含まれるか（ship指定時はGT/航行区域も確認）"""
    has_solas = any(cid.startswith("SOLAS") for cid in conv_ids)
    if ship is not None:
        return has_solas and _is_solas_ship(ship)
    return has_solas


def _any_marpol(conv_ids: set[str]) -> bool:
    """適用条約にいずれかのMARPOL附属書が含まれるか"""
    return any(cid.startswith("MARPOL") for cid in conv_ids)


def _is_international(ship: dict) -> bool:
    """国際航行船舶かどうか"""
    nav = ship.get("navigation_area") or []
    if isinstance(nav, str):
        nav = [nav]
    return "international" in nav


def _is_jpn_flag(ship: dict) -> bool:
    """日本旗船かどうか"""
    return ship.get("flag_state", "").upper() in ("JPN", "JP", "JAPAN")


def _get_applicable_conv_ids(compliance_results: list[dict]) -> set[str]:
    """compliance_results から applicable/potential の convention_id を集合で返す"""
    return {
        r["convention_id"]
        for r in compliance_results
        if r.get("status") in ("applicable", "potential")
    }


def _build_related_conventions(pub: dict, conv_ids: set[str]) -> list[str]:
    """書籍に関連する条約IDリストを構築"""
    # static な関連条約がある場合はそれを使用
    static = pub.get("related_conventions_static")
    if static:
        return list(static)

    # convention_trigger からマッチするものを返す
    trigger = pub.get("convention_trigger", "")
    if not trigger:
        return []

    related = []
    for cid in conv_ids:
        if trigger in cid or cid.startswith(trigger.split("_")[0]):
            related.append(cid)
    if not related and trigger:
        related = [trigger]
    return related


# ===========================================================================
# メイン判定関数
# ===========================================================================

def determine_required_publications(
    ship: dict,
    compliance_results: Optional[list[dict]] = None,
) -> list[dict]:
    """
    船舶スペックと条約適用結果から、必要な備付書籍リストを自動判定する。

    Args:
        ship: {
            "ship_type": "bulk_carrier",
            "gross_tonnage": 5000,
            "navigation_area": ["international"],
            "flag_state": "JPN",
            "build_year": 2015,
            "classification_society": "NK",  # optional
        }
        compliance_results: ship_compliance.determine_compliance() の出力。
                            None の場合は内部で呼ぶ。

    Returns: list of {
        "publication_id": str,
        "title": str,
        "title_ja": str,
        "category": "A" | "B" | "C" | "D",
        "legal_basis": str,
        "publisher": str,
        "current_edition": str,
        "current_edition_date": str | None,
        "update_cycle": str,
        "priority": "mandatory" | "recommended",
        "reason": str,
        "related_conventions": list[str],
    }
    """
    # ----- compliance_results の取得 -----
    if compliance_results is None:
        if determine_compliance is not None:
            compliance_results = determine_compliance(ship)
        else:
            logger.warning("ship_compliance が import できないため空のcompliance_resultsで判定")
            compliance_results = []

    conv_ids: set[str] = _get_applicable_conv_ids(compliance_results)
    logger.info(f"適用条約数: {len(conv_ids)}, 条約ID: {sorted(conv_ids)[:10]}...")

    publications: list[dict] = []
    seen_ids: set[str] = set()

    def _add_pub(pub: dict, reason_override: Optional[str] = None) -> None:
        """書籍を結果リストに追加（重複排除）"""
        pid = pub["publication_id"]
        if pid in seen_ids:
            return
        seen_ids.add(pid)

        reason = reason_override or pub.get("reason_template", "備付義務")
        related = _build_related_conventions(pub, conv_ids)

        publications.append({
            "publication_id": pid,
            "title": pub["title"],
            "title_ja": pub["title_ja"],
            "category": pub["category"],
            "legal_basis": pub["legal_basis"],
            "publisher": pub["publisher"],
            "current_edition": pub["current_edition"],
            "current_edition_date": pub.get("current_edition_date"),
            "update_cycle": pub["update_cycle"],
            "priority": pub["priority"],
            "reason": reason,
            "related_conventions": related,
        })

    # ===== カテゴリA: 条約書籍 =====
    for pub in CATEGORY_A_PUBLICATIONS:
        cond = pub.get("condition")
        if cond and cond(ship, conv_ids):
            _add_pub(pub)

    # ===== カテゴリB: 航海用刊行物 =====
    is_intl = _is_international(ship)
    is_jpn = _is_jpn_flag(ship)

    # 日本旗船なら日本水路部刊行物を追加
    if is_jpn:
        for pub in JHO_PUBLICATIONS:
            _add_pub(pub)

    # 国際航行船には UKHO, NGA を追加
    if is_intl:
        for pub in UKHO_PUBLICATIONS:
            _add_pub(pub)
        for pub in NGA_PUBLICATIONS:
            _add_pub(pub)

    # ===== カテゴリC: 旗国・船級 =====
    # 日本旗国書籍
    if is_jpn:
        for pub in JPN_FLAG_PUBLICATIONS:
            _add_pub(pub)

    # 船級社書籍
    class_soc = ship.get("classification_society", "")
    class_pubs = CLASS_SOCIETY_PUBLICATIONS.get(class_soc, [])
    for pub in class_pubs:
        _add_pub(pub)

    # ===== カテゴリD: 船上マニュアル =====
    for pub in CATEGORY_D_PUBLICATIONS:
        cond = pub.get("condition")
        if cond and cond(ship, conv_ids):
            _add_pub(pub)

    logger.info(
        f"備付書籍判定完了: 全{len(publications)}件 "
        f"(A={sum(1 for p in publications if p['category'] == CAT_A)}, "
        f"B={sum(1 for p in publications if p['category'] == CAT_B)}, "
        f"C={sum(1 for p in publications if p['category'] == CAT_C)}, "
        f"D={sum(1 for p in publications if p['category'] == CAT_D)})"
    )

    return publications


# ===========================================================================
# ユーティリティ関数
# ===========================================================================

def get_mandatory_publications(ship: dict, compliance_results: Optional[list[dict]] = None) -> list[dict]:
    """mandatory（義務）の書籍のみ返す"""
    all_pubs = determine_required_publications(ship, compliance_results)
    return [p for p in all_pubs if p["priority"] == MANDATORY]


def get_publications_by_category(
    ship: dict,
    category: str,
    compliance_results: Optional[list[dict]] = None,
) -> list[dict]:
    """指定カテゴリの書籍のみ返す"""
    all_pubs = determine_required_publications(ship, compliance_results)
    return [p for p in all_pubs if p["category"] == category]


def get_publication_summary(ship: dict, compliance_results: Optional[list[dict]] = None) -> dict:
    """カテゴリ別の集計サマリーを返す"""
    all_pubs = determine_required_publications(ship, compliance_results)
    summary: dict = {
        "total": len(all_pubs),
        "mandatory": sum(1 for p in all_pubs if p["priority"] == MANDATORY),
        "recommended": sum(1 for p in all_pubs if p["priority"] == RECOMMENDED),
        "by_category": {},
    }
    for cat in [CAT_A, CAT_B, CAT_C, CAT_D]:
        cat_pubs = [p for p in all_pubs if p["category"] == cat]
        summary["by_category"][cat] = {
            "count": len(cat_pubs),
            "mandatory": sum(1 for p in cat_pubs if p["priority"] == MANDATORY),
            "recommended": sum(1 for p in cat_pubs if p["priority"] == RECOMMENDED),
        }
    return summary
