"""
船舶コンプライアンス判定エンジン — Ship Compliance Determination Engine
=====================================================================
船舶の5つの基本属性（船種・GT・航行区域・旗国・建造年）から
適用される国際条約・国内法を自動推論する。

使い方:
    from utils.ship_compliance import determine_compliance

    ship = {
        "ship_type": "bulk_carrier",
        "gross_tonnage": 5000,
        "navigation_area": ["international"],
        "flag_state": "JPN",
        "build_year": 2015,
    }
    results = determine_compliance(ship)
"""

import logging
from typing import Optional

try:
    from utils.maritime_knowledge import CONVENTION_RULES, ACTION_TYPES
except ImportError:
    from maritime_knowledge import CONVENTION_RULES, ACTION_TYPES

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[Compliance] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# ステータス定数
# ---------------------------------------------------------------------------

STATUS_APPLICABLE = "applicable"
STATUS_POTENTIAL = "potential"
STATUS_NOT_APPLICABLE = "not_applicable"

# ソート優先順位（小さいほど上位）
_STATUS_ORDER = {
    STATUS_APPLICABLE: 0,
    STATUS_POTENTIAL: 1,
    STATUS_NOT_APPLICABLE: 2,
}


# ---------------------------------------------------------------------------
# 内部ヘルパー関数
# ---------------------------------------------------------------------------

def _check_ship_type(rule: dict, ship_type: str) -> Optional[bool]:
    """
    船種条件をチェックする。

    Returns:
        True  — 条件を満たす（適用対象）
        False — 条件を満たさない（非適用）
        None  — 船種条件なし（他の条件で判断）
    """
    # 除外船種チェック（excluded_types が指定されている場合）
    excluded_types: list[str] = rule.get("excluded_types") or []
    if excluded_types and ship_type in excluded_types:
        logger.debug(f"船種 {ship_type!r} は excluded_types に含まれる")
        return False

    # 適用船種チェック
    applicable_types: list[str] = rule.get("ship_types") or []
    if not applicable_types:
        # 船種制限なし → 条件パス
        return None

    # "all" は全船種適用
    if "all" in applicable_types:
        return True

    if ship_type in applicable_types:
        return True

    logger.debug(f"船種 {ship_type!r} は ship_types {applicable_types} に含まれない")
    return False


def _check_gross_tonnage(rule: dict, gross_tonnage: Optional[int]) -> Optional[bool]:
    """
    GT条件をチェックする。

    Returns:
        True  — 条件を満たす
        False — 条件を満たさない
        None  — GT条件なしまたはGT情報なし
    """
    gt_min: Optional[int] = rule.get("gt_min")
    gt_max: Optional[int] = rule.get("gt_max")

    if gt_min is None and gt_max is None:
        return None

    if gross_tonnage is None:
        # GT情報がないが条件がある場合は判断不能
        logger.debug("GT情報なし、GT条件あり → 判断不能")
        return None

    if gt_min is not None and gross_tonnage < gt_min:
        logger.debug(f"GT {gross_tonnage} < gt_min {gt_min}")
        return False

    if gt_max is not None and gross_tonnage > gt_max:
        logger.debug(f"GT {gross_tonnage} > gt_max {gt_max}")
        return False

    return True


def _check_navigation_area(rule: dict, ship_areas: list[str]) -> Optional[bool]:
    """
    航行区域条件をチェックする。

    Returns:
        True  — 条件を満たす
        False — 条件を満たさない
        None  — 航行区域条件なし
    """
    required_areas: list[str] = rule.get("navigation_areas") or []
    if not required_areas:
        return None

    if "all" in required_areas:
        return True

    if not ship_areas:
        logger.debug("船の航行区域情報なし、条件あり → 判断不能")
        return None

    # 共通要素があれば適用
    if set(required_areas) & set(ship_areas):
        return True

    logger.debug(f"航行区域 {ship_areas} と {required_areas} に共通要素なし")
    return False


def _check_build_year(rule: dict, build_year: Optional[int]) -> Optional[bool]:
    """
    建造年条件をチェックする（非遡及適用の場合のみ）。

    Returns:
        True  — 条件を満たす
        False — 条件を満たさない
        None  — 建造年条件なしまたは遡及適用
    """
    # 遡及適用（retroactive=True）の場合は建造年に関係なく適用
    if rule.get("retroactive", True):
        return None

    keel_after: Optional[int] = rule.get("keel_after")
    if keel_after is None:
        return None

    if build_year is None:
        logger.debug("建造年情報なし、keel_after条件あり → 判断不能")
        return None

    if build_year >= keel_after:
        return True

    logger.debug(f"建造年 {build_year} < keel_after {keel_after}")
    return False


def _check_flag_state(rule: dict, flag_state: str) -> Optional[bool]:
    """
    旗国条件をチェックする。

    Returns:
        True  — 条件を満たす
        False — 条件を満たさない
        None  — 旗国条件なし
    """
    applicable_flags: list[str] = rule.get("flag_states") or []
    if not applicable_flags:
        return None

    if "all" in applicable_flags:
        return True

    if flag_state in applicable_flags:
        return True

    logger.debug(f"旗国 {flag_state!r} は flag_states {applicable_flags} に含まれない")
    return False


def _build_reason(rule: dict, ship: dict) -> str:
    """適用理由の文字列を構築する。"""
    parts: list[str] = []

    gt = ship.get("gross_tonnage")
    gt_min = rule.get("gt_min")
    gt_max = rule.get("gt_max")
    if gt is not None and gt_min is not None:
        parts.append(f"GT {gt} ≥ {gt_min}")
    if gt is not None and gt_max is not None:
        parts.append(f"GT {gt} ≤ {gt_max}")

    nav_areas = ship.get("navigation_area") or []
    req_areas = rule.get("navigation_areas") or []
    if nav_areas and req_areas:
        matched = set(nav_areas) & set(req_areas)
        if matched or "all" in req_areas:
            areas_str = ", ".join(nav_areas)
            parts.append(f"航行区域: {areas_str}")

    ship_type = ship.get("ship_type", "")
    if ship_type:
        parts.append(ship_type)

    flag = ship.get("flag_state", "")
    flag_states = rule.get("flag_states") or []
    if flag and flag_states and "all" not in flag_states:
        parts.append(f"旗国: {flag}")

    build_year = ship.get("build_year")
    keel_after = rule.get("keel_after")
    if build_year and keel_after and not rule.get("retroactive", True):
        parts.append(f"建造年 {build_year} ≥ {keel_after}")

    return ", ".join(parts) if parts else "条件該当"


def _resolve_actions(action_refs: list[dict]) -> list[dict]:
    """
    ルールの typical_actions 参照を解決する。
    action_ref に type キーがあれば ACTION_TYPES から詳細を補完する。
    """
    resolved: list[dict] = []
    for ref in action_refs:
        action_type = ref.get("type", "")
        if action_type in ACTION_TYPES:
            merged = {**ACTION_TYPES[action_type], **ref}
            resolved.append(merged)
        else:
            resolved.append(ref)
    return resolved


# ---------------------------------------------------------------------------
# メイン判定関数
# ---------------------------------------------------------------------------

def determine_compliance(ship: dict) -> list[dict]:
    """
    5つの基本情報から適用条約を自動推論する。

    Args:
        ship: {
            "ship_type": "bulk_carrier",
            "gross_tonnage": 5000,
            "navigation_area": ["international"],
            "flag_state": "JPN",
            "build_year": 2015,
        }

    Returns: [
        {
            "convention_id": "SOLAS_CH_IX_ISM",
            "convention": "SOLAS",
            "chapter": "Chapter IX",
            "description": "国際安全管理コード",
            "status": "applicable",
            "reason": "GT 5000 ≥ 500, 国際航海, ばら積み貨物船",
            "keywords": [...],
            "national_laws": ["船舶安全法（ISM告示）"],
            "typical_actions": [{"type": "sms_revision", "detail": "SMS改訂"}],
            "certificates": ["DOC", "SMC"],
            "user_prompt": None,
        },
        ...
    ]
    """
    ship_type: str = ship.get("ship_type", "")
    gross_tonnage: Optional[int] = ship.get("gross_tonnage")
    navigation_area: list[str] = ship.get("navigation_area") or []
    flag_state: str = ship.get("flag_state", "")
    build_year: Optional[int] = ship.get("build_year")

    logger.info(
        f"判定開始: ship_type={ship_type!r}, GT={gross_tonnage}, "
        f"nav={navigation_area}, flag={flag_state!r}, build={build_year}"
    )

    results: list[dict] = []

    for rule in CONVENTION_RULES:
        rule_id: str = rule.get("convention_id", "UNKNOWN")
        logger.debug(f"ルール評価中: {rule_id}")

        # --- 各条件を評価 ---
        type_result = _check_ship_type(rule, ship_type)
        gt_result = _check_gross_tonnage(rule, gross_tonnage)
        nav_result = _check_navigation_area(rule, navigation_area)
        build_result = _check_build_year(rule, build_year)
        flag_result = _check_flag_state(rule, flag_state)

        # いずれかの条件が明確に False → not_applicable
        basic_checks = [type_result, gt_result, nav_result, build_result, flag_result]
        if any(c is False for c in basic_checks):
            status = STATUS_NOT_APPLICABLE
            reason = f"基本条件不適合: {rule_id}"
            user_prompt = None
        else:
            # 全基本条件パス → detail_conditions をチェック
            detail_conditions: list[str] = rule.get("detail_conditions") or []
            if detail_conditions:
                # 詳細条件がある場合は "potential"（ユーザー確認が必要）
                status = STATUS_POTENTIAL
                reason = _build_reason(rule, ship)
                user_prompt = detail_conditions
                logger.info(f"{rule_id}: potential（詳細条件あり: {detail_conditions}）")
            else:
                status = STATUS_APPLICABLE
                reason = _build_reason(rule, ship)
                user_prompt = None
                logger.info(f"{rule_id}: applicable")

        # --- 結果を構築 ---
        raw_actions: list[dict] = rule.get("typical_actions") or []
        resolved_actions = _resolve_actions(raw_actions)

        # 旗国に対応する国内法をフィルタ
        national_laws_map: dict = rule.get("national_laws") or {}
        if isinstance(national_laws_map, dict):
            # 旗国固有の法令 + 共通法令（"all" キー）
            national_laws = list(national_laws_map.get(flag_state, []))
            national_laws.extend(national_laws_map.get("all", []))
        elif isinstance(national_laws_map, list):
            # リスト形式の場合はそのまま使用
            national_laws = list(national_laws_map)
        else:
            national_laws = []

        result_entry = {
            "convention_id": rule_id,
            "convention": rule.get("convention", ""),
            "chapter": rule.get("chapter", ""),
            "description": rule.get("description", ""),
            "status": status,
            "reason": reason,
            "keywords": list(rule.get("keywords") or []),
            "national_laws": national_laws,
            "typical_actions": resolved_actions,
            "certificates": list(rule.get("certificates") or []),
            "user_prompt": user_prompt,
        }
        results.append(result_entry)

    # ソート: applicable → potential → not_applicable
    results.sort(key=lambda r: _STATUS_ORDER.get(r["status"], 99))

    applicable_count = sum(1 for r in results if r["status"] == STATUS_APPLICABLE)
    potential_count = sum(1 for r in results if r["status"] == STATUS_POTENTIAL)
    logger.info(
        f"判定完了: 全{len(results)}件 "
        f"(applicable={applicable_count}, potential={potential_count})"
    )

    return results


# ---------------------------------------------------------------------------
# ユーティリティ関数
# ---------------------------------------------------------------------------

def get_applicable_keywords(ship: dict) -> set[str]:
    """
    船に適用される全条約のキーワードを統合して返す（マッチング用）。
    "applicable" と "potential" の両方からキーワードを収集する。
    """
    results = determine_compliance(ship)
    keywords: set[str] = set()
    for r in results:
        if r["status"] in (STATUS_APPLICABLE, STATUS_POTENTIAL):
            keywords.update(r.get("keywords") or [])
    logger.info(f"適用キーワード数: {len(keywords)}")
    return keywords


def get_applicable_conventions(ship: dict) -> list[str]:
    """
    船に適用される条約IDのリストのみ返す（簡易版）。
    "applicable" ステータスの条約のみ。
    """
    results = determine_compliance(ship)
    convention_ids = [
        r["convention_id"]
        for r in results
        if r["status"] == STATUS_APPLICABLE
    ]
    logger.info(f"適用条約数: {len(convention_ids)}")
    return convention_ids


def get_national_laws(ship: dict) -> list[str]:
    """
    船の旗国に基づく国内法のリストを返す。
    "applicable" と "potential" の両方から収集し、重複を排除。
    """
    results = determine_compliance(ship)
    laws: list[str] = []
    seen: set[str] = set()
    for r in results:
        if r["status"] in (STATUS_APPLICABLE, STATUS_POTENTIAL):
            for law in r.get("national_laws") or []:
                if law not in seen:
                    seen.add(law)
                    laws.append(law)
    logger.info(f"適用国内法数: {len(laws)}")
    return laws
