"""
maritime_knowledge.py — 海事条約ナレッジベース
================================================
マッチングエンジンの「頭脳」。
各条約がどの船舶に適用されるかのルール、キーワード、
典型的なアクション、関連証書、日本国内法マッピングを定義。

使い方:
    from utils.maritime_knowledge import CONVENTION_RULES, ACTION_TYPES, SHIP_TYPE_GROUPS

純粋データファイル — API 呼び出し・DB 接続は一切なし。
"""

from __future__ import annotations

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
# 条約ルール一覧 (30+ rules)
# ---------------------------------------------------------------------------

CONVENTION_RULES: list[dict] = [

    # ===================================================================
    # SOLAS 関連
    # ===================================================================

    # --- SOLAS Chapter II-1: 構造（復原性、区画、機関） ---
    {
        "id": "SOLAS_CH_II1_STRUCTURE",
        "convention": "SOLAS",
        "chapter": "Chapter II-1",
        "code": None,
        "description": "船体構造・復原性・区画・機関設備基準",
        "conditions": {
            "gt_min": 500,
            "gt_max": None,
            "ship_types": [],  # 全船
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "SOLAS", "SOLAS II-1", "Chapter II-1", "構造", "復原性", "区画",
            "watertight", "subdivision", "stability", "damage stability",
            "機関設備", "舵取機", "steering gear", "bilge pumping",
            "船殻構造", "船体強度", "intact stability", "損傷時復原性",
            "MSC", "船舶構造規則", "Goal-Based Standards", "GBS",
            "CSR", "Common Structural Rules", "共通構造規則",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "船舶構造規則", "船舶区画規程", "船舶復原性規則"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "構造・復原性に関する改修"},
            {"type": "certificate_update", "detail": "船舶安全証書（構造）の更新"},
            {"type": "documentation", "detail": "復原性計算書の更新"},
            {"type": "drawing_approval", "detail": "改造図面の船級承認"},
            {"type": "class_survey", "detail": "船級協会の臨時検査手配"},
        ],
        "certificates": ["Safety Construction Certificate", "安全構造証書"],
    },

    # --- SOLAS Chapter II-2: 防火 ---
    {
        "id": "SOLAS_CH_II2_FIRE",
        "convention": "SOLAS",
        "chapter": "Chapter II-2",
        "code": "FSS Code / FTP Code",
        "description": "防火構造・火災検知・消火設備",
        "conditions": {
            "gt_min": 500,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "SOLAS", "SOLAS II-2", "Chapter II-2", "防火", "消火", "火災検知",
            "fire safety", "fire detection", "fire protection",
            "FSS Code", "FTP Code", "fixed fire", "CO2 system",
            "sprinkler", "smoke detection", "fire door", "fire damper",
            "MSC.1/Circ", "防火構造", "消火設備", "火災探知",
            "A-60", "B-15", "耐火等級", "fire rating",
            "脱出設備", "escape route", "避難経路",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "船舶防火構造規則", "船舶消防設備規則"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "消火設備・火災検知器の改修"},
            {"type": "certificate_update", "detail": "船舶安全証書（設備）の更新"},
            {"type": "crew_training", "detail": "消火訓練・避難訓練の実施"},
            {"type": "sms_revision", "detail": "防火手順のSMS反映"},
            {"type": "onboard_drill", "detail": "消火操練・避難操練の実施"},
            {"type": "inspection_record", "detail": "消火設備点検チェックリストの更新"},
        ],
        "certificates": ["Safety Equipment Certificate", "安全設備証書"],
    },

    # --- SOLAS Chapter III: 救命設備 ---
    {
        "id": "SOLAS_CH_III_LSA",
        "convention": "SOLAS",
        "chapter": "Chapter III",
        "code": "LSA Code",
        "description": "救命設備・救命艇・救命胴衣・非常信号",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "SOLAS", "SOLAS III", "Chapter III", "救命設備", "救命艇", "救命胴衣",
            "LSA Code", "life-saving", "lifeboat", "liferaft", "life jacket",
            "EPIRB", "SART", "immersion suit", "rescue boat",
            "muster station", "abandon ship", "MSC.1/Circ",
            "船舶救命設備", "自由降下式", "free-fall lifeboat",
            "退船操練", "総員配置表",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "船舶救命設備規則"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "救命設備の交換・追加搭載"},
            {"type": "certificate_update", "detail": "船舶安全証書（設備）の更新"},
            {"type": "crew_training", "detail": "退船・救命操練の実施"},
            {"type": "psc_preparation", "detail": "救命設備の整備状態確認"},
            {"type": "onboard_drill", "detail": "退船操練・救命艇降下操練の実施"},
            {"type": "inspection_record", "detail": "救命設備週次/月次点検記録の更新"},
            {"type": "equipment_procurement", "detail": "救命設備の調達・手配"},
        ],
        "certificates": ["Safety Equipment Certificate", "安全設備証書"],
    },

    # --- SOLAS Chapter IV: 無線通信 (GMDSS) ---
    {
        "id": "SOLAS_CH_IV_GMDSS",
        "convention": "SOLAS",
        "chapter": "Chapter IV",
        "code": "GMDSS",
        "description": "海上遭難安全システム（GMDSS）無線設備",
        "conditions": {
            "gt_min": 300,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "SOLAS", "SOLAS IV", "Chapter IV", "GMDSS", "無線通信", "無線設備",
            "radio communication", "VHF", "MF/HF", "Inmarsat",
            "DSC", "NAVTEX", "SafetyNET", "EPIRB", "SART", "AIS-SART",
            "GMDSS modernization", "MSC", "無線検査",
            "海上通信", "遭難通信", "航行警報",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "船舶設備規程", "電波法"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "GMDSS無線設備の更新・追加"},
            {"type": "certificate_update", "detail": "無線証書（Safety Radio Certificate）の更新"},
            {"type": "crew_training", "detail": "GMDSS操作訓練"},
        ],
        "certificates": ["Safety Radio Certificate", "無線証書"],
    },

    # --- SOLAS Chapter V: 航行安全 ---
    {
        "id": "SOLAS_CH_V_NAVIGATION",
        "convention": "SOLAS",
        "chapter": "Chapter V",
        "code": None,
        "description": "航行安全・航海計器・ECDIS・VDR・AIS",
        "conditions": {
            "gt_min": 300,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "SOLAS", "SOLAS V", "Chapter V", "航行安全", "航海計器",
            "ECDIS", "VDR", "AIS", "LRIT", "navigation safety",
            "voyage planning", "航海計画", "BRM", "bridge resource management",
            "pilot ladder", "水先人用梯", "radar", "レーダー",
            "echo sounder", "測深儀", "speed log", "GPS",
            "MSC.1/Circ", "航海用具", "航海設備",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "船舶設備規程", "海上衝突予防法"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "ECDIS/VDR/AIS等航海計器の更新"},
            {"type": "crew_training", "detail": "ECDIS操作訓練・BRM訓練"},
            {"type": "documentation", "detail": "航海計画手順の見直し"},
            {"type": "psc_preparation", "detail": "航海計器の整備・テスト記録"},
            {"type": "logbook_entry", "detail": "航海日誌への航海計器テスト記録"},
            {"type": "inspection_record", "detail": "航海計器の定期点検記録"},
        ],
        "certificates": ["Safety Equipment Certificate", "安全設備証書"],
    },

    # --- SOLAS Chapter VI: 貨物運送 ---
    {
        "id": "SOLAS_CH_VI_CARGO",
        "convention": "SOLAS",
        "chapter": "Chapter VI",
        "code": "CSS Code",
        "description": "貨物の積付・固縛・穀類運送",
        "conditions": {
            "gt_min": 500,
            "gt_max": None,
            "ship_types": CARGO_SHIPS,
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "SOLAS", "SOLAS VI", "Chapter VI", "貨物運送", "cargo transport",
            "CSS Code", "cargo securing", "固縛", "積付", "lashing",
            "grain", "穀類", "Cargo Securing Manual", "CSM",
            "MSC.1/Circ.1353", "container weighing", "VGM",
            "verified gross mass", "SOLAS VGM",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "危険物船舶運送及び貯蔵規則"],
        },
        "typical_actions": [
            {"type": "documentation", "detail": "Cargo Securing Manual (CSM) の更新"},
            {"type": "crew_training", "detail": "貨物固縛訓練"},
            {"type": "psc_preparation", "detail": "固縛設備の点検"},
        ],
        "certificates": ["Document of Compliance (Cargo)"],
    },

    # --- SOLAS Chapter VII: 危険物運送 ---
    {
        "id": "SOLAS_CH_VII_DG",
        "convention": "SOLAS",
        "chapter": "Chapter VII",
        "code": "IMDG Code",
        "description": "危険物の海上運送",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": CARGO_SHIPS,
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": {
            "field": "carries_dangerous_goods",
            "prompt": "危険物（IMDG Code 対象貨物）を運送しますか？",
        },
        "keywords": [
            "SOLAS", "SOLAS VII", "Chapter VII", "危険物", "dangerous goods",
            "IMDG Code", "IMDG", "DG", "hazardous cargo",
            "UN number", "国連番号", "危険物申告書",
            "MSC.1/Circ", "segregation", "隔離", "stowage",
            "EmS", "MFAG", "危険物船舶運送",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "危険物船舶運送及び貯蔵規則"],
        },
        "typical_actions": [
            {"type": "documentation", "detail": "危険物積載マニフェストの整備"},
            {"type": "crew_training", "detail": "危険物取扱訓練"},
            {"type": "sms_revision", "detail": "危険物運送手順のSMS反映"},
            {"type": "psc_preparation", "detail": "危険物関連書類の確認"},
        ],
        "certificates": ["Document of Compliance (DG)"],
    },

    # --- SOLAS Chapter IX: ISM Code ---
    {
        "id": "SOLAS_CH_IX_ISM",
        "convention": "SOLAS",
        "chapter": "Chapter IX",
        "code": "ISM Code",
        "description": "国際安全管理コード（ISM Code）",
        "conditions": {
            "gt_min": 500,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "SOLAS", "SOLAS IX", "Chapter IX", "ISM", "ISM Code",
            "安全管理", "Safety Management", "SMS", "安全管理マニュアル",
            "DOC", "SMC", "Document of Compliance", "Safety Management Certificate",
            "適合証書", "安全管理証書", "DPA", "Designated Person Ashore",
            "internal audit", "内部監査", "management review",
            "MSC", "nonconformity", "不適合", "corrective action", "是正処置",
            "ISM audit", "ISM review",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "船舶安全法施行規則"],
        },
        "typical_actions": [
            {"type": "sms_revision", "detail": "SMS（安全管理マニュアル）の改訂"},
            {"type": "certificate_update", "detail": "DOC/SMC の更新"},
            {"type": "crew_training", "detail": "ISM関連教育・内部監査"},
            {"type": "documentation", "detail": "内部監査記録・マネジメントレビュー記録"},
            {"type": "poster_display", "detail": "安全管理方針の掲示・乗組員への周知"},
            {"type": "inspection_record", "detail": "安全点検チェックリストの記録"},
            {"type": "logbook_entry", "detail": "不適合・是正措置の記録"},
        ],
        "certificates": ["DOC", "SMC"],
    },

    # --- SOLAS Chapter XI-1: 船舶強化 (ESP / CSR) ---
    {
        "id": "SOLAS_CH_XI1_ESP",
        "convention": "SOLAS",
        "chapter": "Chapter XI-1",
        "code": "ESP Code",
        "description": "強化検査プログラム（ESP）・船体識別番号（IMO番号）",
        "conditions": {
            "gt_min": 500,
            "gt_max": None,
            "ship_types": ["bulk_carrier", "tanker"],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "SOLAS", "SOLAS XI-1", "Chapter XI-1", "ESP", "Enhanced Survey Programme",
            "強化検査", "CAS", "Condition Assessment Scheme",
            "船体識別番号", "IMO number", "continuous synopsis record", "CSR",
            "船歴記録", "thickness measurement", "板厚計測",
            "close-up survey", "近接検査",
        ],
        "national_laws": {
            "JPN": ["船舶安全法"],
        },
        "typical_actions": [
            {"type": "documentation", "detail": "ESP検査記録の整備"},
            {"type": "equipment_modification", "detail": "板厚計測に基づく鋼板交換"},
            {"type": "certificate_update", "detail": "船級証書の更新"},
            {"type": "class_survey", "detail": "船級協会の定期・臨時検査手配"},
            {"type": "inspection_record", "detail": "板厚計測・腐食状況の記録"},
        ],
        "certificates": ["Class Certificate", "船級証書"],
    },

    # --- SOLAS Chapter XI-2: ISPS Code ---
    {
        "id": "SOLAS_CH_XI2_ISPS",
        "convention": "SOLAS",
        "chapter": "Chapter XI-2",
        "code": "ISPS Code",
        "description": "国際船舶港湾保安コード（ISPS Code）",
        "conditions": {
            "gt_min": 500,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "SOLAS", "SOLAS XI-2", "Chapter XI-2", "ISPS", "ISPS Code",
            "船舶保安", "maritime security", "ship security",
            "ISSC", "International Ship Security Certificate",
            "SSP", "Ship Security Plan", "船舶保安計画書",
            "SSO", "Ship Security Officer", "船舶保安職員",
            "CSO", "Company Security Officer", "会社保安職員",
            "security level", "保安レベル", "PFSO",
            "MSC", "DoS", "Declaration of Security", "保安申告書",
            "maritime cyber", "サイバーセキュリティ",
        ],
        "national_laws": {
            "JPN": ["国際船舶・港湾保安法", "国際船舶・港湾保安法施行規則"],
        },
        "typical_actions": [
            {"type": "sms_revision", "detail": "SSP（船舶保安計画書）の改訂"},
            {"type": "certificate_update", "detail": "ISSC の更新"},
            {"type": "crew_training", "detail": "船舶保安訓練・演習"},
            {"type": "documentation", "detail": "保安記録の整備"},
            {"type": "psc_preparation", "detail": "ISPS関連書類・訓練記録の確認"},
            {"type": "onboard_drill", "detail": "船舶保安操練の実施"},
            {"type": "logbook_entry", "detail": "保安レベル変更・保安事象の記録"},
        ],
        "certificates": ["ISSC"],
    },

    # --- SOLAS Chapter XIV: Polar Code ---
    {
        "id": "SOLAS_CH_XIV_POLAR",
        "convention": "SOLAS",
        "chapter": "Chapter XIV",
        "code": "Polar Code",
        "description": "極海コード（極海域を航行する船舶の安全要件）",
        "conditions": {
            "gt_min": 500,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": {
            "field": "operates_in_polar",
            "prompt": "北極海域または南極海域を航行しますか？",
        },
        "keywords": [
            "Polar Code", "極海コード", "極海", "Arctic", "Antarctic",
            "北極", "南極", "polar waters", "ice class",
            "PWOM", "Polar Water Operational Manual",
            "極域航行船舶", "Polar Ship Certificate",
            "MSC.385(94)", "MEPC.264(68)",
            "氷海", "ice navigation", "ice strengthening",
        ],
        "national_laws": {
            "JPN": ["船舶安全法"],
        },
        "typical_actions": [
            {"type": "documentation", "detail": "PWOM（極海域運航マニュアル）の作成"},
            {"type": "certificate_update", "detail": "Polar Ship Certificate の取得"},
            {"type": "equipment_modification", "detail": "極海域対応設備の搭載"},
            {"type": "crew_training", "detail": "極海域航行訓練"},
        ],
        "certificates": ["Polar Ship Certificate"],
    },

    # ===================================================================
    # MARPOL 関連
    # ===================================================================

    # --- MARPOL Annex I: 油濁防止 ---
    {
        "id": "MARPOL_ANNEX_I",
        "convention": "MARPOL",
        "chapter": "Annex I",
        "code": None,
        "description": "油による汚染の防止（IOPP・SOPEP・油水分離器）",
        "conditions": {
            "gt_min": 400,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "MARPOL", "MARPOL I", "Annex I", "油濁防止", "oil pollution",
            "IOPP", "International Oil Pollution Prevention",
            "SOPEP", "Shipboard Oil Pollution Emergency Plan",
            "油濁防止証書", "油水分離器", "oily water separator", "OWS",
            "oil discharge monitor", "ODM", "油排出監視装置",
            "油記録簿", "Oil Record Book", "ORB",
            "MEPC", "15 ppm", "bilge water", "ビルジ",
            "STS", "ship-to-ship transfer", "洋上移送",
            "crude oil washing", "COW", "原油洗浄",
        ],
        "national_laws": {
            "JPN": ["海洋汚染等及び海上災害の防止に関する法律", "海洋汚染等及び海上災害の防止に関する法律施行規則"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "IOPP証書の更新"},
            {"type": "equipment_modification", "detail": "油水分離器・ODMの整備"},
            {"type": "documentation", "detail": "SOPEP・油記録簿の整備"},
            {"type": "crew_training", "detail": "油流出対応訓練"},
            {"type": "psc_preparation", "detail": "IOPP関連設備・書類の確認"},
            {"type": "logbook_entry", "detail": "油記録簿（Oil Record Book）の記入"},
            {"type": "onboard_drill", "detail": "油流出緊急対応操練"},
            {"type": "inspection_record", "detail": "油水分離器・ODMの定期点検記録"},
        ],
        "certificates": ["IOPP Certificate", "IOPP証書"],
    },

    # --- MARPOL Annex II: ばら積み有害液体物質 ---
    {
        "id": "MARPOL_ANNEX_II",
        "convention": "MARPOL",
        "chapter": "Annex II",
        "code": "IBC Code",
        "description": "ばら積み有害液体物質による汚染防止",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": ["chemical", "tanker"],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "MARPOL", "MARPOL II", "Annex II", "有害液体物質", "NLS",
            "noxious liquid substances", "IBC Code",
            "International Bulk Chemical Code",
            "P&A Manual", "Procedures and Arrangements Manual",
            "NLS certificate", "Cargo Record Book",
            "貨物記録簿", "化学品タンカー", "chemical tanker",
            "MEPC", "prewash", "tank washing",
        ],
        "national_laws": {
            "JPN": ["海洋汚染等及び海上災害の防止に関する法律"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "NLS証書/適合証書の更新"},
            {"type": "documentation", "detail": "P&Aマニュアル・貨物記録簿の整備"},
            {"type": "crew_training", "detail": "有害液体物質取扱訓練"},
        ],
        "certificates": ["NLS Certificate", "Certificate of Fitness (IBC)"],
    },

    # --- MARPOL Annex III: 有害物質の容器運送 ---
    {
        "id": "MARPOL_ANNEX_III",
        "convention": "MARPOL",
        "chapter": "Annex III",
        "code": "IMDG Code (汚染関連)",
        "description": "容器入り有害物質の海上運送による汚染防止",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": CARGO_SHIPS,
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": {
            "field": "carries_harmful_packaged",
            "prompt": "容器入り有害物質（Marine Pollutant 表示貨物）を運送しますか？",
        },
        "keywords": [
            "MARPOL", "MARPOL III", "Annex III", "有害物質容器",
            "harmful substances in packaged form",
            "marine pollutant", "海洋汚染物質", "MP mark",
            "IMDG Code", "marking", "labelling", "表示",
        ],
        "national_laws": {
            "JPN": ["海洋汚染等及び海上災害の防止に関する法律", "危険物船舶運送及び貯蔵規則"],
        },
        "typical_actions": [
            {"type": "documentation", "detail": "有害物質積載記録の整備"},
            {"type": "crew_training", "detail": "有害物質取扱訓練"},
        ],
        "certificates": [],
    },

    # --- MARPOL Annex IV: 汚水 ---
    {
        "id": "MARPOL_ANNEX_IV",
        "convention": "MARPOL",
        "chapter": "Annex IV",
        "code": None,
        "description": "汚水による汚染の防止",
        "conditions": {
            "gt_min": 400,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "MARPOL", "MARPOL IV", "Annex IV", "汚水", "sewage",
            "sewage treatment plant", "汚水処理装置",
            "International Sewage Pollution Prevention Certificate",
            "ISPPC", "comminuting", "disinfecting",
            "MEPC", "Baltic Sea", "special area",
        ],
        "national_laws": {
            "JPN": ["海洋汚染等及び海上災害の防止に関する法律"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "汚水処理装置の設置・更新"},
            {"type": "certificate_update", "detail": "ISPPC（汚水汚染防止証書）の更新"},
        ],
        "certificates": ["ISPPC", "汚水汚染防止証書"],
    },

    # --- MARPOL Annex V: 廃物 ---
    {
        "id": "MARPOL_ANNEX_V",
        "convention": "MARPOL",
        "chapter": "Annex V",
        "code": None,
        "description": "船舶からの廃物による汚染の防止",
        "conditions": {
            "gt_min": 100,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "MARPOL", "MARPOL V", "Annex V", "廃物", "garbage",
            "garbage management plan", "ごみ管理計画", "GMP",
            "Garbage Record Book", "ごみ記録簿", "GRB",
            "placard", "掲示板", "food waste", "食物くず",
            "MEPC", "special area", "特別海域",
            "plastic", "プラスチック", "cargo residues",
        ],
        "national_laws": {
            "JPN": ["海洋汚染等及び海上災害の防止に関する法律"],
        },
        "typical_actions": [
            {"type": "documentation", "detail": "ごみ管理計画書（GMP）・ごみ記録簿の整備"},
            {"type": "crew_training", "detail": "廃物管理に関する乗組員教育"},
            {"type": "psc_preparation", "detail": "ごみ管理関連書類・掲示の確認"},
        ],
        "certificates": [],
    },

    # --- MARPOL Annex VI: 大気汚染防止 (SOx/NOx/GHG) ---
    {
        "id": "MARPOL_ANNEX_VI_AIR",
        "convention": "MARPOL",
        "chapter": "Annex VI",
        "code": "NOx Technical Code",
        "description": "大気汚染防止（SOx/NOx規制・燃料油品質・ECA）",
        "conditions": {
            "gt_min": 400,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "MARPOL", "MARPOL VI", "Annex VI", "大気汚染", "air pollution",
            "IAPP", "International Air Pollution Prevention Certificate",
            "大気汚染防止証書", "SOx", "NOx", "sulphur", "硫黄",
            "fuel oil quality", "燃料油品質", "0.50%", "0.10%",
            "ECA", "Emission Control Area", "排出規制海域",
            "SECA", "NECA", "NOx Tier", "Tier III",
            "NOx Technical Code", "EIAPP", "scrubber", "スクラバー",
            "exhaust gas cleaning", "EGCS",
            "MEPC", "fuel oil sampling", "燃料油サンプリング",
            "BDN", "Bunker Delivery Note", "燃料油供給証明書",
        ],
        "national_laws": {
            "JPN": ["海洋汚染等及び海上災害の防止に関する法律"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "IAPP証書の更新"},
            {"type": "equipment_modification", "detail": "スクラバー/SCR等排ガス処理装置の設置"},
            {"type": "documentation", "detail": "燃料油供給証明書(BDN)・サンプル管理"},
            {"type": "psc_preparation", "detail": "燃料油品質・排ガス関連書類の確認"},
        ],
        "certificates": ["IAPP Certificate", "IAPP証書", "EIAPP Certificate"],
    },

    # --- MARPOL Annex VI: EEXI/CII/SEEMP ---
    {
        "id": "MARPOL_ANNEX_VI_GHG",
        "convention": "MARPOL",
        "chapter": "Annex VI (GHG)",
        "code": "EEXI / CII / SEEMP",
        "description": "GHG排出削減（EEXI技術要件・CII運航格付け・SEEMP）",
        "conditions": {
            "gt_min": 400,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,  # EEXI は既存船にも適用
        },
        "detail_conditions": None,
        "keywords": [
            "EEXI", "Energy Efficiency Existing Ship Index",
            "CII", "Carbon Intensity Indicator", "炭素集約度指標",
            "SEEMP", "Ship Energy Efficiency Management Plan",
            "エネルギー効率", "GHG", "greenhouse gas", "温室効果ガス",
            "EEDI", "Energy Efficiency Design Index",
            "attained EEXI", "required EEXI",
            "CII rating", "CII格付け", "A/B/C/D/E",
            "correction factor", "voyage adjustment",
            "MEPC.328(76)", "MEPC.352(78)", "MEPC.355(78)",
            "shaft power limitation", "EPL", "ShaPoLi",
            "overridable power limitation",
            "fuel oil data collection", "DCS", "IMO DCS",
            "EU MRV", "EU ETS", "FuelEU Maritime",
        ],
        "national_laws": {
            "JPN": ["海洋汚染等及び海上災害の防止に関する法律"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "IAPP証書・EEXI技術ファイルの更新"},
            {"type": "documentation", "detail": "SEEMP Part III（CII管理計画）の整備"},
            {"type": "equipment_modification", "detail": "EPL/ShaPoLi等の出力制限装置設置"},
            {"type": "sms_revision", "detail": "CII改善計画のSMS反映"},
        ],
        "certificates": ["IAPP Certificate", "EEXI Technical File", "IEE Certificate"],
    },

    # ===================================================================
    # STCW 関連
    # ===================================================================

    {
        "id": "STCW",
        "convention": "STCW",
        "chapter": None,
        "code": "STCW Code",
        "description": "船員の訓練・資格証明・当直基準",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "STCW", "STCW Code", "STCW Convention",
            "船員資格", "船員訓練", "当直基準",
            "training", "certification", "watchkeeping",
            "competency", "CoC", "Certificate of Competency",
            "GoC", "Certificate of Proficiency",
            "familiarization", "Basic Safety Training",
            "ECDIS training", "GMDSS operator",
            "rest hours", "休息時間", "fatigue",
            "Manila Amendments", "マニラ改正",
            "MSC", "STW", "海技免状", "海技士",
        ],
        "national_laws": {
            "JPN": ["船舶職員及び小型船舶操縦者法", "船員法", "船員法施行規則"],
        },
        "typical_actions": [
            {"type": "crew_training", "detail": "STCW要件に基づく訓練の実施・更新"},
            {"type": "documentation", "detail": "訓練記録・資格証明の管理"},
            {"type": "sms_revision", "detail": "当直体制・訓練計画のSMS反映"},
        ],
        "certificates": ["STCW Certificates", "海技免状"],
    },

    # ===================================================================
    # MLC 関連
    # ===================================================================

    {
        "id": "MLC_2006",
        "convention": "MLC",
        "chapter": None,
        "code": "MLC, 2006",
        "description": "海上労働条約（乗組員の労働条件・居住設備・食料）",
        "conditions": {
            "gt_min": 500,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "MLC", "MLC 2006", "Maritime Labour Convention", "海上労働条約",
            "seafarers", "船員の労働", "労働条件",
            "DMLC", "Declaration of Maritime Labour Compliance",
            "Maritime Labour Certificate", "海上労働証書",
            "working hours", "労働時間", "rest hours", "休息時間",
            "accommodation", "居住設備", "food and catering", "食料",
            "medical care", "medical certificate", "健康証明書",
            "repatriation", "送還", "complaint procedure",
            "P&I", "社会保障", "shore leave",
            "manning", "配乗", "recruitment",
            "ILO", "国際労働機関",
        ],
        "national_laws": {
            "JPN": ["船員法", "船員労働安全衛生規則", "船員保険法"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "海上労働証書(MLC Certificate)/DMLC の更新"},
            {"type": "documentation", "detail": "労働時間記録・苦情処理手続の整備"},
            {"type": "sms_revision", "detail": "労働条件に関するSMS改訂"},
            {"type": "crew_training", "detail": "船員の権利・苦情手続に関する教育"},
        ],
        "certificates": ["Maritime Labour Certificate", "DMLC", "海上労働証書"],
    },

    # ===================================================================
    # BWM Convention（バラスト水管理条約）
    # ===================================================================

    {
        "id": "BWM_CONVENTION",
        "convention": "BWM Convention",
        "chapter": None,
        "code": "BWM Convention",
        "description": "バラスト水管理条約（BWMS搭載義務）",
        "conditions": {
            "gt_min": 400,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,  # 既存船にもIORSS更新時に適用
        },
        "detail_conditions": None,
        "keywords": [
            "BWM", "Ballast Water Management", "バラスト水", "バラスト水管理",
            "BWMS", "Ballast Water Management System", "バラスト水処理装置",
            "D-1 standard", "D-2 standard", "D-1基準", "D-2基準",
            "ballast water exchange", "バラスト水交換",
            "ballast water treatment", "type approval",
            "BWM Certificate", "バラスト水管理証書",
            "BWMP", "Ballast Water Management Plan",
            "Ballast Water Record Book", "バラスト水記録簿",
            "MEPC", "sediment management",
            "commissioning testing", "IOPP renewal survey",
        ],
        "national_laws": {
            "JPN": ["海洋汚染等及び海上災害の防止に関する法律"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "BWMS（バラスト水処理装置）の設置"},
            {"type": "certificate_update", "detail": "BWM証書の取得・更新"},
            {"type": "documentation", "detail": "BWM計画書・バラスト水記録簿の整備"},
            {"type": "crew_training", "detail": "BWMS操作訓練"},
        ],
        "certificates": ["BWM Certificate", "バラスト水管理証書"],
    },

    # ===================================================================
    # AFS Convention（船底防汚方法規制条約）
    # ===================================================================

    {
        "id": "AFS_CONVENTION",
        "convention": "AFS Convention",
        "chapter": None,
        "code": "AFS Convention",
        "description": "船底防汚方法規制条約（有害防汚塗料の禁止・Cybutryne）",
        "conditions": {
            "gt_min": 400,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "AFS", "Anti-Fouling Systems", "防汚", "船底塗料",
            "TBT", "tributyltin", "有機スズ", "organotin",
            "cybutryne", "シブトリン",
            "AFS Certificate", "AFS Statement",
            "International Anti-Fouling System Certificate",
            "MEPC.331(76)", "anti-fouling",
            "biocide", "防汚方法証書",
        ],
        "national_laws": {
            "JPN": ["海洋汚染等及び海上災害の防止に関する法律"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "AFS証書/AFS声明書の更新"},
            {"type": "equipment_modification", "detail": "船底塗料の塗替え（規制物質除去）"},
            {"type": "documentation", "detail": "AFS声明書の整備"},
        ],
        "certificates": ["AFS Certificate", "AFS声明書"],
    },

    # ===================================================================
    # Hong Kong Convention（シップリサイクル条約）
    # ===================================================================

    {
        "id": "SHIP_RECYCLING_HKC",
        "convention": "Hong Kong Convention",
        "chapter": None,
        "code": "Ship Recycling Convention",
        "description": "シップリサイクル条約（IHM — 有害物質一覧表）",
        "conditions": {
            "gt_min": 500,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,  # EU SRR は既存船にも適用済み
        },
        "detail_conditions": None,
        "keywords": [
            "Hong Kong Convention", "HKC", "シップリサイクル",
            "ship recycling", "IHM", "Inventory of Hazardous Materials",
            "有害物質一覧表", "EU SRR", "Ship Recycling Regulation",
            "asbestos", "アスベスト", "PCB", "hazardous materials",
            "MEPC.269(68)", "Statement of Compliance",
            "Ready for Recycling Certificate",
            "有害物質", "解撤",
        ],
        "national_laws": {
            "JPN": ["船舶安全法"],  # 日本は HKC 締約国
        },
        "typical_actions": [
            {"type": "documentation", "detail": "IHM（有害物質一覧表）Part I/II/III の作成・更新"},
            {"type": "certificate_update", "detail": "IHM証書（Statement of Compliance）の取得"},
            {"type": "psc_preparation", "detail": "IHM関連書類の確認"},
        ],
        "certificates": ["IHM Certificate", "Statement of Compliance (IHM)"],
    },

    # ===================================================================
    # IBC Code（国際バルクケミカルコード）
    # ===================================================================

    {
        "id": "IBC_CODE",
        "convention": "SOLAS / MARPOL",
        "chapter": "SOLAS VII / MARPOL II",
        "code": "IBC Code",
        "description": "国際ばら積み危険化学品コード",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": CHEMICAL_CARRIERS,
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "IBC Code", "International Bulk Chemical Code",
            "化学品コード", "ケミカルタンカー", "chemical tanker",
            "Certificate of Fitness", "適合証書",
            "cargo compatibility", "tank type", "cargo containment",
            "MEPC", "MSC", "BCH Code",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "危険物船舶運送及び貯蔵規則"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "Certificate of Fitness (IBC) の更新"},
            {"type": "documentation", "detail": "P&Aマニュアルの更新"},
            {"type": "crew_training", "detail": "化学品取扱訓練"},
        ],
        "certificates": ["Certificate of Fitness (IBC)"],
    },

    # ===================================================================
    # IGC Code（国際ガスキャリアコード）
    # ===================================================================

    {
        "id": "IGC_CODE",
        "convention": "SOLAS",
        "chapter": "SOLAS VII",
        "code": "IGC Code",
        "description": "国際ガスキャリアコード（液化ガスばら積み運送船）",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": GAS_CARRIERS,
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "IGC Code", "International Gas Carrier Code",
            "ガスキャリア", "LNG船", "LPG船", "gas carrier",
            "Certificate of Fitness (IGC)", "International Certificate of Fitness",
            "cargo containment", "tank type", "membrane",
            "Moss type", "SPB", "独立球形タンク",
            "boil-off gas", "BOG", "reliquefaction",
            "GCU", "Gas Combustion Unit",
            "MSC", "IGF Code",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "液化ガスばら積船の構造及び設備に関する基準"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "Certificate of Fitness (IGC) の更新"},
            {"type": "equipment_modification", "detail": "貨物格納設備の改修"},
            {"type": "crew_training", "detail": "ガス安全訓練・貨物操作訓練"},
        ],
        "certificates": ["Certificate of Fitness (IGC)"],
    },

    # ===================================================================
    # IMSBC Code（国際海上固体ばら積み貨物コード）
    # ===================================================================

    {
        "id": "IMSBC_CODE",
        "convention": "SOLAS",
        "chapter": "SOLAS VI / SOLAS XII",
        "code": "IMSBC Code",
        "description": "国際海上固体ばら積み貨物コード（液状化・化学的危険性）",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": ["bulk_carrier", "general_cargo"],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "IMSBC Code", "International Maritime Solid Bulk Cargoes Code",
            "固体ばら積み", "solid bulk cargo", "液状化", "liquefaction",
            "transportable moisture limit", "TML", "flow moisture point", "FMP",
            "Group A cargo", "Group B cargo", "Group C cargo",
            "cargo declaration", "shipper's declaration",
            "MSC.1/Circ", "bauxite", "nickel ore", "ニッケル鉱石",
            "鉄鉱石", "石炭", "coal", "iron ore",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "危険物船舶運送及び貯蔵規則"],
        },
        "typical_actions": [
            {"type": "documentation", "detail": "貨物申告書・積載マニュアルの確認"},
            {"type": "crew_training", "detail": "固体ばら積み貨物の安全取扱訓練"},
            {"type": "psc_preparation", "detail": "貨物関連書類の確認"},
        ],
        "certificates": ["Document of Authorization (Solid Bulk Cargo)"],
    },

    # ===================================================================
    # SOLAS Chapter XII: ばら積み船の追加安全措置
    # ===================================================================

    {
        "id": "SOLAS_CH_XII_BULK",
        "convention": "SOLAS",
        "chapter": "Chapter XII",
        "code": None,
        "description": "ばら積み船の追加安全措置（水密隔壁・水位検知器）",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": ["bulk_carrier"],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "SOLAS", "SOLAS XII", "Chapter XII", "ばら積み船",
            "bulk carrier", "bulk carrier safety",
            "water ingress", "浸水検知", "water level detector",
            "hold flooding", "double bottom", "二重底",
            "MSC", "single side skin", "single hull bulk carrier",
            "bulk carrier strength", "ばら積み船構造強度",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "船舶構造規則"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "浸水検知装置の設置・整備"},
            {"type": "certificate_update", "detail": "船舶安全証書の更新"},
            {"type": "documentation", "detail": "積付マニュアルの更新"},
        ],
        "certificates": ["Safety Construction Certificate"],
    },

    # ===================================================================
    # NOx Technical Code 2008
    # ===================================================================

    {
        "id": "NOX_TECHNICAL_CODE",
        "convention": "MARPOL",
        "chapter": "Annex VI",
        "code": "NOx Technical Code 2008",
        "description": "NOx技術コード（ディーゼル機関からのNOx排出規制）",
        "conditions": {
            "gt_min": 400,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,  # Tier I/II は既存船にも適用
        },
        "detail_conditions": None,
        "keywords": [
            "NOx Technical Code", "NOx", "窒素酸化物",
            "Tier I", "Tier II", "Tier III",
            "EIAPP", "Engine International Air Pollution Prevention",
            "diesel engine", "ディーゼル機関",
            "SCR", "Selective Catalytic Reduction", "選択触媒還元",
            "EGR", "Exhaust Gas Recirculation", "排ガス再循環",
            "NECA", "NOx Emission Control Area",
            "MEPC", "130 kW", "出力130kW以上",
        ],
        "national_laws": {
            "JPN": ["海洋汚染等及び海上災害の防止に関する法律"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "EIAPP証書の更新"},
            {"type": "equipment_modification", "detail": "SCR/EGR等NOx低減装置の設置"},
            {"type": "documentation", "detail": "NOx技術ファイルの整備"},
        ],
        "certificates": ["EIAPP Certificate"],
    },

    # ===================================================================
    # IGF Code（ガス/低引火点燃料使用船）
    # ===================================================================

    {
        "id": "IGF_CODE",
        "convention": "SOLAS",
        "chapter": "SOLAS II-1",
        "code": "IGF Code",
        "description": "ガス燃料・低引火点燃料使用船の安全基準",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": False,  # 基本的に新造船向け
        },
        "detail_conditions": {
            "field": "uses_gas_fuel",
            "prompt": "LNG/LPG/メタノール等のガス燃料・低引火点燃料を使用しますか？",
        },
        "keywords": [
            "IGF Code", "International Code of Safety for Ships using Gases",
            "ガス燃料", "低引火点燃料", "gas fuel", "low flashpoint fuel",
            "LNG fuelled", "LNG燃料", "methanol fuelled", "メタノール燃料",
            "ammonia fuel", "アンモニア燃料", "hydrogen fuel", "水素燃料",
            "dual fuel", "デュアルフューエル",
            "MSC.391(95)", "bunkering safety",
        ],
        "national_laws": {
            "JPN": ["船舶安全法"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "ガス燃料供給・安全システムの設置"},
            {"type": "certificate_update", "detail": "安全証書への追記"},
            {"type": "crew_training", "detail": "ガス燃料取扱訓練（IGF Code基礎訓練）"},
            {"type": "documentation", "detail": "ガス燃料運用マニュアルの整備"},
        ],
        "certificates": ["Safety Construction Certificate (IGF endorsement)"],
    },

    # ===================================================================
    # Intact Stability Code (2008 IS Code)
    # ===================================================================

    {
        "id": "IS_CODE_2008",
        "convention": "SOLAS / Load Lines",
        "chapter": None,
        "code": "2008 IS Code",
        "description": "非損傷時復原性コード",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "IS Code", "Intact Stability Code", "2008 IS Code",
            "復原性", "intact stability", "stability criteria",
            "GZ curve", "GM", "righting lever",
            "weather criterion", "MSC.267(85)",
            "stability booklet", "復原性資料",
            "loading condition", "積付状態",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "船舶復原性規則"],
        },
        "typical_actions": [
            {"type": "documentation", "detail": "復原性資料（Stability Booklet）の更新"},
            {"type": "certificate_update", "detail": "安全証書の更新"},
        ],
        "certificates": ["Stability Booklet Approval"],
    },

    # ===================================================================
    # International Load Line Convention（満載喫水線条約）
    # ===================================================================

    {
        "id": "LOAD_LINE",
        "convention": "Load Line Convention",
        "chapter": None,
        "code": "LL Convention 1966/1988 Protocol",
        "description": "国際満載喫水線条約（フリーボード・風雨密性）",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "Load Line", "満載喫水線", "freeboard", "フリーボード",
            "LL Convention", "International Load Line Certificate",
            "国際満載喫水線証書", "weathertight", "風雨密",
            "hatch cover", "ハッチカバー", "scupper", "排水口",
            "LL Protocol 1988", "conditions of assignment",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "満載喫水線規則"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "国際満載喫水線証書の更新"},
            {"type": "equipment_modification", "detail": "ハッチカバー・風雨密装置の整備"},
            {"type": "psc_preparation", "detail": "フリーボード・ハッチカバー密閉性確認"},
        ],
        "certificates": ["International Load Line Certificate", "国際満載喫水線証書"],
    },

    # ===================================================================
    # Tonnage Convention（トン数条約）
    # ===================================================================

    {
        "id": "TONNAGE_CONVENTION",
        "convention": "Tonnage Convention 1969",
        "chapter": None,
        "code": None,
        "description": "国際トン数測度条約（GT/NT算定）",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "Tonnage Convention", "トン数", "総トン数", "純トン数",
            "GT", "NT", "gross tonnage", "net tonnage",
            "International Tonnage Certificate",
            "国際トン数証書", "tonnage measurement",
        ],
        "national_laws": {
            "JPN": ["船舶のトン数の測度に関する法律"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "国際トン数証書の更新"},
        ],
        "certificates": ["International Tonnage Certificate (1969)", "国際トン数証書"],
    },

    # ===================================================================
    # COLREG（海上衝突予防規則）
    # ===================================================================

    {
        "id": "COLREG",
        "convention": "COLREG 1972",
        "chapter": None,
        "code": None,
        "description": "国際海上衝突予防規則（航行灯・形象物・操船規則）",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": [],  # 全航行区域
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "COLREG", "海上衝突予防規則", "collision regulations",
            "航行灯", "navigation lights", "形象物", "day shapes",
            "sound signal", "音響信号", "steering and sailing rules",
            "TSS", "Traffic Separation Scheme", "分離通航帯",
            "narrow channel", "狭水道", "overtaking", "追越し",
            "MASS", "maritime autonomous", "自律運航船",
        ],
        "national_laws": {
            "JPN": ["海上衝突予防法", "海上交通安全法", "港則法"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "航行灯・形象物の整備"},
            {"type": "crew_training", "detail": "航法・操船訓練"},
            {"type": "psc_preparation", "detail": "航行灯・音響信号装置の確認"},
        ],
        "certificates": [],
    },

    # ===================================================================
    # 旅客船追加要件（SOLASの旅客船特有規定統合）
    # ===================================================================

    {
        "id": "SOLAS_PASSENGER",
        "convention": "SOLAS",
        "chapter": "Chapter II-1 / II-2 / III (Passenger)",
        "code": "Safe Return to Port / SRtP",
        "description": "旅客船の追加安全要件（SRtP・避難解析・損傷時復原性強化）",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": PASSENGER_SHIPS,
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "passenger ship", "旅客船", "Safe Return to Port", "SRtP",
            "evacuation analysis", "避難解析",
            "alternative design", "SOLAS II-2/17",
            "passenger ship safety", "ro-ro passenger",
            "Stockholm Agreement", "damage stability passenger",
            "MSC", "旅客船安全", "cruise ship",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "船舶防火構造規則", "船舶救命設備規則"],
        },
        "typical_actions": [
            {"type": "documentation", "detail": "避難解析報告書の更新"},
            {"type": "equipment_modification", "detail": "旅客向け安全設備の改修"},
            {"type": "crew_training", "detail": "旅客避難誘導訓練"},
            {"type": "certificate_update", "detail": "旅客船安全証書の更新"},
        ],
        "certificates": ["Passenger Ship Safety Certificate", "旅客船安全証書"],
    },

    # ===================================================================
    # SOLAS Chapter XIII: IMSAS（IMO加盟国監査スキーム）
    # ===================================================================

    {
        "id": "SOLAS_CH_XIII_IMSAS",
        "convention": "SOLAS",
        "chapter": "Chapter XIII",
        "code": "III Code / IMSAS",
        "description": "IMO加盟国監査スキーム（旗国・寄港国の義務）",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "IMSAS", "IMO Member State Audit Scheme",
            "III Code", "flag State", "旗国", "port State",
            "PSC", "port State control", "ポートステートコントロール",
            "concentrated inspection campaign", "CIC",
            "Tokyo MOU", "Paris MOU", "detention", "拘留",
            "deficiency", "指摘事項",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "海上運送法"],
        },
        "typical_actions": [
            {"type": "psc_preparation", "detail": "PSC検査重点項目の事前確認"},
            {"type": "documentation", "detail": "全証書・書類の有効期限確認"},
        ],
        "certificates": [],
    },

    # ===================================================================
    # Nairobi WRC（ナイロビ難破物除去条約）
    # ===================================================================

    {
        "id": "NAIROBI_WRC",
        "convention": "Nairobi WRC 2007",
        "chapter": None,
        "code": None,
        "description": "ナイロビ難破物除去条約（難破物除去費用の強制保険）",
        "conditions": {
            "gt_min": 300,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "Nairobi WRC", "Wreck Removal Convention", "難破物除去",
            "wreck removal", "wreck removal insurance",
            "compulsory insurance", "強制保険",
            "certificate of insurance", "保険証書",
        ],
        "national_laws": {
            "JPN": ["船舶油濁等損害賠償保障法"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "難破物除去保険証書の取得・更新"},
            {"type": "documentation", "detail": "保険証書の船内備置"},
        ],
        "certificates": ["Certificate of Insurance (WRC)"],
    },

    # ===================================================================
    # CLC / Bunker Convention（油濁・燃料油汚染損害賠償保障）
    # ===================================================================

    {
        "id": "CLC_BUNKER",
        "convention": "CLC 1992 / Bunker Convention 2001",
        "chapter": None,
        "code": None,
        "description": "油濁損害賠償保障・燃料油汚染損害賠償保障（強制保険）",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "CLC", "Civil Liability Convention", "油濁損害賠償",
            "Bunker Convention", "燃料油汚染", "BUNKERS",
            "compulsory insurance", "強制保険", "P&I",
            "Blue Card", "ブルーカード",
            "CLC Certificate", "Bunker Certificate",
            "IOPC Fund", "国際油濁補償基金",
        ],
        "national_laws": {
            "JPN": ["船舶油濁等損害賠償保障法"],
        },
        "typical_actions": [
            {"type": "certificate_update", "detail": "CLC/Bunker 保険証書の更新"},
            {"type": "documentation", "detail": "保険証書の船内備置"},
        ],
        "certificates": ["CLC Certificate", "Bunker Convention Certificate"],
    },

    # ===================================================================
    # SOLAS II-2 Reg.4: Fixed fire-extinguishing systems for machinery spaces
    # (tanker 特有の追加要件)
    # ===================================================================

    {
        "id": "MARPOL_I_TANKER",
        "convention": "MARPOL / SOLAS",
        "chapter": "Annex I (Tanker specific)",
        "code": None,
        "description": "タンカー特有の構造・設備要件（ダブルハル・COW・IGS）",
        "conditions": {
            "gt_min": 150,
            "gt_max": None,
            "ship_types": ["tanker"],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "oil tanker", "タンカー", "double hull", "ダブルハル",
            "二重船殻", "crude oil washing", "COW", "原油洗浄",
            "inert gas system", "IGS", "不活性ガス装置",
            "SBT", "segregated ballast tank", "分離バラストタンク",
            "CBT", "clean ballast tank",
            "oil discharge", "oil record book",
            "ODME", "oil discharge monitoring equipment",
            "tank cleaning", "タンク洗浄",
        ],
        "national_laws": {
            "JPN": ["海洋汚染等及び海上災害の防止に関する法律", "船舶安全法"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "IGS/COW/ODME等の整備"},
            {"type": "certificate_update", "detail": "IOPP証書の更新"},
            {"type": "documentation", "detail": "油記録簿の適正記載"},
            {"type": "psc_preparation", "detail": "タンカー特有設備の検査準備"},
        ],
        "certificates": ["IOPP Certificate", "Certificate of Fitness (tanker)"],
    },

    # ===================================================================
    # 日本国内法特有: 船員法関連
    # ===================================================================

    {
        "id": "JPN_SEAFARERS_ACT",
        "convention": "National Law (JPN)",
        "chapter": None,
        "code": "船員法",
        "description": "船員法（労働時間・安全衛生・災害補償）— 日本籍船",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": [],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": {
            "field": "flag_state_jpn",
            "prompt": "日本籍船（日本旗国）ですか？",
        },
        "keywords": [
            "船員法", "船員労働", "労働時間", "休息時間",
            "海員", "船長", "航海士", "機関士",
            "船員災害", "労働安全衛生", "船員手帳",
            "船員労働安全衛生規則", "船内作業",
            "荒天準備", "係船作業", "甲板作業",
            "労使協定", "船内規律",
        ],
        "national_laws": {
            "JPN": ["船員法", "船員法施行規則", "船員労働安全衛生規則"],
        },
        "typical_actions": [
            {"type": "documentation", "detail": "労働時間記録表の整備"},
            {"type": "crew_training", "detail": "安全衛生教育の実施"},
            {"type": "sms_revision", "detail": "労働時間管理手順のSMS反映"},
        ],
        "certificates": [],
    },

    # ===================================================================
    # 日本国内法特有: 海洋汚染防止法の国内追加要件
    # ===================================================================

    {
        "id": "JPN_MARINE_POLLUTION",
        "convention": "National Law (JPN)",
        "chapter": None,
        "code": "海防法",
        "description": "海洋汚染等及び海上災害の防止に関する法律 — 国内追加要件",
        "conditions": {
            "gt_min": None,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": [],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": {
            "field": "flag_state_jpn",
            "prompt": "日本籍船（日本旗国）ですか？",
        },
        "keywords": [
            "海防法", "海洋汚染防止", "海洋汚染等及び海上災害の防止",
            "油防除", "排出油防除", "廃油処理",
            "有害水バラスト", "大気汚染物質",
            "焼却炉", "揮発性有機化合物", "VOC",
            "海上保安庁", "環境省", "国土交通省",
        ],
        "national_laws": {
            "JPN": [
                "海洋汚染等及び海上災害の防止に関する法律",
                "海洋汚染等及び海上災害の防止に関する法律施行令",
                "海洋汚染等及び海上災害の防止に関する法律施行規則",
            ],
        },
        "typical_actions": [
            {"type": "documentation", "detail": "国内法に基づく記録簿・計画書の整備"},
            {"type": "equipment_modification", "detail": "国内基準に基づく設備改修"},
        ],
        "certificates": [],
    },

    # ===================================================================
    # Cyber Security (MSC-FAL.1/Circ.3)
    # ===================================================================

    {
        "id": "CYBER_SECURITY",
        "convention": "SOLAS (ISM Code interpretation)",
        "chapter": "Chapter IX (ISM)",
        "code": "MSC-FAL.1/Circ.3",
        "description": "海事サイバーリスク管理（ISM Code のリスク管理に統合）",
        "conditions": {
            "gt_min": 500,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": None,
        "keywords": [
            "cyber security", "サイバーセキュリティ", "cyber risk",
            "サイバーリスク", "MSC-FAL.1/Circ.3",
            "MSC.428(98)", "cyber risk management",
            "IT security", "OT security", "ECDIS security",
            "network security", "サイバー攻撃",
            "maritime cyber", "ISM cyber",
            "BIMCO cyber", "UR E26", "UR E27",
            "IACS UR", "unified requirements",
        ],
        "national_laws": {
            "JPN": ["船舶安全法（ISM Code経由）"],
        },
        "typical_actions": [
            {"type": "sms_revision", "detail": "SMSにサイバーリスク管理手順を追加"},
            {"type": "crew_training", "detail": "サイバーセキュリティ意識向上訓練"},
            {"type": "documentation", "detail": "サイバーリスクアセスメント文書の作成"},
        ],
        "certificates": ["DOC", "SMC"],
    },

    # ===================================================================
    # ECDIS Carriage Requirements (SOLAS V)
    # ===================================================================

    {
        "id": "ECDIS_MANDATE",
        "convention": "SOLAS",
        "chapter": "Chapter V Reg.19",
        "code": None,
        "description": "ECDIS搭載義務（電子海図情報表示装置）",
        "conditions": {
            "gt_min": 500,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,  # 段階的に既存船にも適用済み
        },
        "detail_conditions": None,
        "keywords": [
            "ECDIS", "Electronic Chart Display",
            "電子海図", "ENC", "electronic navigational chart",
            "RCDS", "raster chart", "backup ECDIS",
            "type-specific training", "ECDIS訓練",
            "IHO", "S-57", "S-100", "S-101",
            "chart update", "海図更新",
        ],
        "national_laws": {
            "JPN": ["船舶安全法", "船舶設備規程"],
        },
        "typical_actions": [
            {"type": "equipment_modification", "detail": "ECDIS機器の更新・バックアップ整備"},
            {"type": "crew_training", "detail": "ECDIS型式別訓練の実施"},
            {"type": "documentation", "detail": "ECDIS関連手順書の整備"},
        ],
        "certificates": ["Safety Equipment Certificate"],
    },

    # ===================================================================
    # EU MRV / EU ETS / FuelEU Maritime（EU域規制）
    # ===================================================================

    {
        "id": "EU_EMISSIONS",
        "convention": "EU Regulation",
        "chapter": None,
        "code": "EU MRV / EU ETS / FuelEU Maritime",
        "description": "EU排出規制（MRV報告・排出枠取引・FuelEU Maritime）",
        "conditions": {
            "gt_min": 5000,
            "gt_max": None,
            "ship_types": [],
            "excluded_types": [],
            "navigation": ["international"],
            "keel_after": None,
            "retroactive": True,
        },
        "detail_conditions": {
            "field": "calls_eu_ports",
            "prompt": "EU/EEA域内の港に寄港しますか？",
        },
        "keywords": [
            "EU MRV", "EU ETS", "FuelEU Maritime",
            "Monitoring Reporting Verification",
            "emission trading", "排出枠", "排出権取引",
            "carbon allowance", "CO2 emission",
            "Document of Compliance (EU MRV)",
            "well-to-wake", "GHG intensity",
            "shore power", "onshore power supply",
            "Regulation 2015/757", "EU Green Deal",
            "Fit for 55", "penalty", "罰則",
        ],
        "national_laws": {
            "JPN": [],  # EU法のため日本法は直接関係なし
        },
        "typical_actions": [
            {"type": "documentation", "detail": "EU MRV監視計画・年次報告の整備"},
            {"type": "certificate_update", "detail": "EU MRV適合証書の取得"},
            {"type": "sms_revision", "detail": "EU ETS対応手順のSMS反映"},
        ],
        "certificates": ["Document of Compliance (EU MRV)"],
    },

]


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
