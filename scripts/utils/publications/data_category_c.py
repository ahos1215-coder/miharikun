"""
data_category_c.py — カテゴリC: 旗国・船級マスターデータ (12件)
=============================================================
日本旗国法令集および各船級協会(NK/DNV/LR/ABS)規則のデータ定義。
"""

from __future__ import annotations

from .constants import CAT_C, MANDATORY, RECOMMENDED


# ---------------------------------------------------------------------------
# 日本旗国書籍
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# ClassNK
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# DNV
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# LR
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# ABS
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# 船級社マッピング
# ---------------------------------------------------------------------------

CLASS_SOCIETY_PUBLICATIONS: dict[str, list[dict]] = {
    "NK": NK_PUBLICATIONS,
    "ClassNK": NK_PUBLICATIONS,
    "DNV": DNV_PUBLICATIONS,
    "DNV-GL": DNV_PUBLICATIONS,
    "LR": LR_PUBLICATIONS,
    "ABS": ABS_PUBLICATIONS,
}
