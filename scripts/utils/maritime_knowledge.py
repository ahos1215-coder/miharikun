"""
maritime_knowledge.py — 海事条約ナレッジベース
================================================
マッチングエンジンの「頭脳」。
各条約がどの船舶に適用されるかのルール、キーワード、
典型的なアクション、関連証書、日本国内法マッピングを定義。

使い方:
    from utils.maritime_knowledge import CONVENTION_RULES, ACTION_TYPES, SHIP_TYPE_GROUPS

純粋データファイル — API 呼び出し・DB 接続は一切なし。
条約ルールデータは maritime_convention_rules.py に分離。
"""

from __future__ import annotations

from utils.maritime_convention_rules import CONVENTION_RULES  # noqa: F401 — re-export

# ---------------------------------------------------------------------------
# 船種グループ定数
# ---------------------------------------------------------------------------

CARGO_SHIPS: list[str] = ["bulk_carrier", "tanker", "container", "general_cargo", "roro"]
PASSENGER_SHIPS: list[str] = ["passenger"]
GAS_CARRIERS: list[str] = ["lpg", "lng"]
CHEMICAL_CARRIERS: list[str] = ["chemical"]

ALL_MERCHANT_SHIPS: list[str] = CARGO_SHIPS + PASSENGER_SHIPS + GAS_CARRIERS + CHEMICAL_CARRIERS
TANKER_TYPES: list[str] = ["tanker", "chemical", "lpg", "lng"]
HIGH_SPEED_CRAFT: list[str] = ["hsc"]

SHIP_TYPE_GROUPS: dict[str, list[str]] = {
    "cargo": CARGO_SHIPS,
    "passenger": PASSENGER_SHIPS,
    "gas": GAS_CARRIERS,
    "chemical": CHEMICAL_CARRIERS,
    "all_merchant": ALL_MERCHANT_SHIPS,
    "tanker_types": TANKER_TYPES,
    "hsc": HIGH_SPEED_CRAFT,
}


# ---------------------------------------------------------------------------
# アクション種別定義
# ---------------------------------------------------------------------------

ACTION_TYPES: dict[str, dict[str, str]] = {
    "sms_revision": {
        "label": "SMS改訂",
        "description": "安全管理マニュアル（SMS）の改訂",
    },
    "equipment_modification": {
        "label": "設備工事",
        "description": "設備の設置・改修工事",
    },
    "crew_training": {
        "label": "乗組員訓練",
        "description": "教育・訓練の実施・記録",
    },
    "certificate_update": {
        "label": "証書更新",
        "description": "船舶証書の書き換え・追記",
    },
    "documentation": {
        "label": "書類整備",
        "description": "計画書・記録簿等の整備",
    },
    "psc_preparation": {
        "label": "PSC対策",
        "description": "ポートステートコントロール検査対策",
    },
}


# ---------------------------------------------------------------------------
# ISM Code SMS (Safety Management System) 章番号マッピング
# 規制がSMSのどのセクションに関連するかを推論するために使用
# ---------------------------------------------------------------------------

SMS_CHAPTER_MAP: dict[str, dict] = {
    "1": {"title": "一般", "keywords": ["方針", "安全管理方針", "目標"]},
    "2": {"title": "安全及び環境保護に関する方針", "keywords": ["安全方針", "環境方針"]},
    "3": {"title": "会社の責任と権限", "keywords": ["責任", "権限", "指定者", "DPA"]},
    "4": {"title": "管理責任者の指定", "keywords": ["管理責任者", "DPA", "designated person"]},
    "5": {"title": "船長の責任と権限", "keywords": ["船長", "master", "override"]},
    "6": {"title": "資源及び人員", "keywords": ["資格", "訓練", "能力", "manning", "STCW"]},
    "7": {"title": "船上作業の計画の策定", "keywords": ["作業手順", "操作", "荷役", "係船", "閉囲区画", "立入", "enclosed space", "作業計画"]},
    "8": {"title": "緊急事態への準備", "keywords": ["緊急", "非常", "emergency", "火災", "浸水", "abandon", "退船", "救助"]},
    "9": {"title": "不適合、事故及び危険な状態の報告及び分析", "keywords": ["不適合", "事故", "インシデント", "是正", "CAR", "near miss"]},
    "10": {"title": "船舶及び設備の保守整備", "keywords": ["保守", "整備", "maintenance", "検査", "点検", "survey"]},
    "11": {"title": "文書管理", "keywords": ["文書", "記録", "文書管理", "document"]},
    "12": {"title": "会社による検証、見直し及び評価", "keywords": ["内部監査", "audit", "見直し", "review", "評価"]},
}


# ---------------------------------------------------------------------------
# 船側/会社側アクション分類
# ---------------------------------------------------------------------------

ONBOARD_ACTIONS: dict[str, dict[str, str]] = {
    "crew_training": {"label": "乗組員訓練", "side": "onboard", "description": "訓練実施・記録"},
    "onboard_drill": {"label": "船上ドリル", "side": "onboard", "description": "非常訓練・操練の実施"},
    "inspection_record": {"label": "点検記録", "side": "onboard", "description": "点検チェックリスト・記録簿の更新"},
    "poster_display": {"label": "掲示・周知", "side": "onboard", "description": "ポスター掲示・乗組員への周知"},
    "logbook_entry": {"label": "航海日誌記入", "side": "onboard", "description": "航海日誌・作業記録の追記"},
}

SHORESIDE_ACTIONS: dict[str, dict[str, str]] = {
    "sms_revision": {"label": "SMS改訂", "side": "shore", "description": "安全管理マニュアルの改訂"},
    "equipment_procurement": {"label": "機材調達", "side": "shore", "description": "設備・部品の調達・手配"},
    "drawing_approval": {"label": "図面承認", "side": "shore", "description": "改造図面の船級承認"},
    "certificate_update": {"label": "証書更新", "side": "shore", "description": "船舶証書の書き換え・追記"},
    "class_survey": {"label": "船級検査", "side": "shore", "description": "船級協会の臨時検査手配"},
}


# ---------------------------------------------------------------------------
# 条約ルール一覧 → maritime_convention_rules.py に分離済み
# CONVENTION_RULES は上記 import で re-export
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# 条約間キーワード排他ルール — cross-contamination 防止
# ---------------------------------------------------------------------------
# 単一キーワードだけでは条約を判定しないルール。
# min_keyword_matches: 最低何個のキーワードがマッチする必要があるか（AND寄りの判定）
# required_any: これらのうち少なくとも1つが含まれていなければマッチしない（アンカーキーワード）
# single_keyword_insufficient: これらのキーワード単独ではマッチと判定しない

KEYWORD_EXCLUSIONS: dict[str, dict] = {
    # "訓練" 単独では STCW とは判定しない — SOLAS 訓練操練と混同防止
    "STCW": {
        "min_keyword_matches": 2,
        "required_any": ["STCW", "船員資格", "海技免状", "海技士", "資格証明",
                         "当直基準", "CoC", "GoC", "Manila"],
        "single_keyword_insufficient": ["訓練", "教育", "training", "休息時間",
                                        "rest hours", "fatigue", "MSC"],
    },
    # "設備" "機器" 単独では SOLAS 構造とは判定しない
    "SOLAS_CH_II1_STRUCTURE": {
        "min_keyword_matches": 2,
        "required_any": ["SOLAS", "SOLAS II-1", "Chapter II-1", "構造", "復原性",
                         "区画", "stability", "subdivision", "CSR", "GBS"],
        "single_keyword_insufficient": ["設備", "機器", "MSC"],
    },
    # "消火" 単独は OK だが "設備" 単独では SOLAS 防火とは判定しない
    "SOLAS_CH_II2_FIRE": {
        "min_keyword_matches": 2,
        "required_any": ["SOLAS", "SOLAS II-2", "Chapter II-2", "防火", "消火",
                         "fire", "FSS Code", "FTP Code"],
        "single_keyword_insufficient": ["設備", "機器", "MSC"],
    },
    # "労働" 単独では MLC とは判定しない — 一般的な労働ニュースと混同防止
    "MLC_2006": {
        "min_keyword_matches": 2,
        "required_any": ["MLC", "海上労働", "Maritime Labour", "DMLC",
                         "Maritime Labour Certificate", "海上労働証書"],
        "single_keyword_insufficient": ["労働", "労働条件", "労働時間", "休息時間",
                                        "食料", "medical", "健康"],
    },
    # "環境" 単独では MARPOL とは判定しない — 一般環境ニュースと混同防止
    "MARPOL_I_OIL": {
        "min_keyword_matches": 2,
        "required_any": ["MARPOL", "MARPOL I", "Annex I", "油濁", "IOPP",
                         "油排出", "SOPEP", "ORB"],
        "single_keyword_insufficient": ["環境", "汚染", "排出", "MEPC"],
    },
    "MARPOL_VI_AIR": {
        "min_keyword_matches": 2,
        "required_any": ["MARPOL", "MARPOL VI", "Annex VI", "SOx", "NOx",
                         "GHG", "EEDI", "EEXI", "CII", "硫黄", "DCS"],
        "single_keyword_insufficient": ["環境", "排出", "MEPC", "温室"],
    },
    # "安全" 単独では ISM とは判定しない
    "ISM_CODE": {
        "min_keyword_matches": 2,
        "required_any": ["ISM", "ISM Code", "安全管理", "SMS", "DOC",
                         "SMC", "Safety Management"],
        "single_keyword_insufficient": ["安全", "管理", "MSC"],
    },
}


# ---------------------------------------------------------------------------
# ユーティリティ関数
# ---------------------------------------------------------------------------

def get_rule_by_id(rule_id: str) -> dict | None:
    """ID で条約ルールを検索"""
    for rule in CONVENTION_RULES:
        if rule["id"] == rule_id:
            return rule
    return None


def get_rules_by_convention(convention: str) -> list[dict]:
    """条約名で条約ルールを検索（部分一致）"""
    convention_lower = convention.lower()
    return [
        rule for rule in CONVENTION_RULES
        if convention_lower in rule["convention"].lower()
    ]


def get_rules_for_ship(
    ship_type: str,
    gross_tonnage: int | None = None,
    navigation: str = "international",
    flag_state: str = "JPN",
    build_year: int | None = None,
) -> list[dict]:
    """
    基本5入力から適用可能性のある条約ルールを返す。
    明確に非適用のものを除外し、「適用」または「要確認（Potential Match）」を返す。

    Returns:
        list of dicts with added key "match_status":
            "applicable" — 基本条件を全て満たす
            "potential"  — detail_conditions が存在し、追加情報が必要
    """
    results: list[dict] = []

    for rule in CONVENTION_RULES:
        cond = rule["conditions"]

        # --- GT 下限チェック ---
        if cond["gt_min"] is not None and gross_tonnage is not None:
            if gross_tonnage < cond["gt_min"]:
                continue

        # --- GT 上限チェック ---
        if cond["gt_max"] is not None and gross_tonnage is not None:
            if gross_tonnage > cond["gt_max"]:
                continue

        # --- 船種チェック ---
        allowed = cond["ship_types"]
        excluded = cond["excluded_types"]
        if allowed and ship_type not in allowed:
            continue
        if excluded and ship_type in excluded:
            continue

        # --- 航行区域チェック ---
        nav_req = cond["navigation"]
        if nav_req and navigation not in nav_req:
            continue

        # --- 建造年チェック（keel_after） ---
        if cond["keel_after"] is not None and build_year is not None:
            keel_year = int(cond["keel_after"][:4])
            if build_year < keel_year:
                if not cond.get("retroactive", False):
                    continue

        # --- 旗国特有ルールのチェック ---
        # National Law ルールで flag_state が条件に含まれる場合
        if rule["convention"] == "National Law (JPN)" and flag_state != "JPN":
            continue

        # --- 適用判定 ---
        match_status = "applicable"
        if rule.get("detail_conditions") is not None:
            match_status = "potential"

        results.append({**rule, "match_status": match_status})

    return results


def search_rules_by_keyword(keyword: str) -> list[dict]:
    """キーワードで条約ルールを検索（部分一致、大文字小文字無視）"""
    keyword_lower = keyword.lower()
    return [
        rule for rule in CONVENTION_RULES
        if any(keyword_lower in kw.lower() for kw in rule["keywords"])
    ]
