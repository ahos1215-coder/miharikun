"""
engine.py — 備付書籍判定ロジック
================================
船舶スペックと条約適用結果から、必要な備付書籍リストを自動判定する。
マスターデータは data_category_*.py に分離。
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    from utils.ship_compliance import determine_compliance
except ImportError:
    try:
        from ship_compliance import determine_compliance
    except ImportError:
        determine_compliance = None  # type: ignore[assignment]

from .constants import CAT_A, CAT_B, CAT_C, CAT_D, MANDATORY, RECOMMENDED
from .data_category_a import (
    CATEGORY_A_PUBLICATIONS,
    _any_solas,
    _is_international,
    _is_solas_ship,
)
from .data_category_b import (
    JHO_PUBLICATIONS,
    ITU_PUBLICATIONS,
    NAVIGATION_REFERENCE_PUBLICATIONS,
    NGA_PUBLICATIONS,
    UKHO_PUBLICATIONS,
)
from .data_category_c import (
    CLASS_SOCIETY_PUBLICATIONS,
    ISM_REFERENCE_PUBLICATIONS,
    JPN_FLAG_PUBLICATIONS,
    NK_SPECIALIZED_PUBLICATIONS,
)
from .data_category_d import CATEGORY_D_PUBLICATIONS

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
# ヘルパー関数
# ---------------------------------------------------------------------------

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

    # ITU無線刊行物（GMDSS船 = 国際航行300GT以上）
    if is_intl and ship.get("gross_tonnage", 0) >= 300:
        for pub in ITU_PUBLICATIONS:
            _add_pub(pub)

    # 日本旗船の無線局名録
    if is_jpn:
        for pub in ITU_PUBLICATIONS:
            if pub.get("applicability_rules", {}).get("flag_state") == "JPN":
                _add_pub(pub)

    # SMS管理図書（航海実務参考書 — 法定義務なし）
    if is_jpn:
        for pub in NAVIGATION_REFERENCE_PUBLICATIONS:
            _add_pub(pub)
    elif is_intl:
        for pub in NAVIGATION_REFERENCE_PUBLICATIONS:
            if not pub.get("applicability_rules", {}).get("flag_state"):
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

    # NK専門規則（NK船級のみ）
    if class_soc in ("NK", "ClassNK"):
        for pub in NK_SPECIALIZED_PUBLICATIONS:
            _add_pub(pub)

    # ISM実務参考書（SMS管理図書 — 法定義務なし）
    if is_intl and is_jpn:
        for pub in ISM_REFERENCE_PUBLICATIONS:
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
