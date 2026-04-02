"""
国交省海事局 シードURL + 金脈キーワード + 深層哨戒定義
======================================================
BFS に頼らず、重要なインデックスページを直接巡回する。
金脈キーワードに合致するページはノイズフィルタをバイパスして強制抽出。
"""

# ---------------------------------------------------------------------------
# シードURL（インデックスページ）
# Step 1: これらのページ自体を巡回
# Step 2: 各ページから施策ページリンクを抽出（1階層下）
# ---------------------------------------------------------------------------

SEED_URLS: list[str] = [
    # === 主要施策インデックス ===
    "https://www.mlit.go.jp/maritime/maritime_mn4_000005.html",   # 運航労務監理
    "https://www.mlit.go.jp/maritime/maritime_tk8_000003.html",   # 船舶の安全・環境
    "https://www.mlit.go.jp/maritime/maritime_fr4_000030.html",   # 船員安全衛生
    "https://www.mlit.go.jp/maritime/maritime_tk4_000016.html",   # 船員の現状
    "https://www.mlit.go.jp/maritime/maritime_tk10_000017.html",  # 船員養成
    "https://www.mlit.go.jp/maritime/maritime_fr1_000027.html",   # 法律

    # === 追加インデックス（Gemini 監査で指摘）===
    "https://www.mlit.go.jp/maritime/maritime_tk1_000004.html",   # 海事局・主要施策一覧
    "https://www.mlit.go.jp/maritime/maritime_tk7_000002.html",   # 船舶安全
    "https://www.mlit.go.jp/maritime/maritime_tk10_000003.html",  # 海技資格
    "https://www.mlit.go.jp/maritime/maritime_tk7_000005.html",   # 環境対策
    "https://www.mlit.go.jp/maritime/maritime_tk4_000009.html",   # 船員の確保・雇用
    "https://www.mlit.go.jp/maritime/maritime_tk10_000006.html",  # 海技資格・免許

    # === 重要施策ページ（直接監視）===
    "https://www.mlit.go.jp/maritime/maritime_fr4_000055.html",   # 基本訓練（令和8年2月14日適用）
    "https://www.mlit.go.jp/maritime/maritime_fr4_000043.html",   # 船員の安全教育
    "https://www.mlit.go.jp/maritime/maritime_tk4_000029.html",   # 船員の健康確保
    "https://www.mlit.go.jp/maritime/maritime_tk4_000026.html",   # 船員の働き方改革
    "https://www.mlit.go.jp/maritime/maritime_fr7_000019.html",   # SOx規制への対応
    "https://www.mlit.go.jp/maritime/maritime_fr4_000040.html",   # SOLAS条約改正(係船設備)
    "https://www.mlit.go.jp/maritime/maritime_fr8_000061.html",   # 救命いかだ搭載義務化
    "https://www.mlit.go.jp/maritime/maritime_fr8_000012.html",   # 危険物運送安全対策
]

# ---------------------------------------------------------------------------
# 施策ページ URL パターン（これにマッチするリンクのみ巡回）
# ---------------------------------------------------------------------------

POLICY_URL_PATTERNS: list[str] = [
    "/maritime/maritime_fr",
    "/maritime/maritime_tk",
    "/maritime/maritime_mn",
]

# ---------------------------------------------------------------------------
# 金脈キーワード（Gold Mine）
# これらを含むページはノイズフィルタをバイパスして強制抽出する
# ---------------------------------------------------------------------------

GOLD_MINE_KEYWORDS: list[str] = [
    # 船員法・免状
    "基本訓練",
    "免状",
    "更新",
    "講習",
    "STCW",
    "義務化",
    "船員法改正",
    "省令改正",
    # 設備要件
    "搭載義務",
    "設置義務",
    "SOLAS改正",
    "MARPOL改正",
    # 安全管理
    "閉囲区画",
    "フルハーネス",
    "安全管理規程",
    # 環境規制
    "硫黄分規制",
    "バラスト水",
    "EEXI",
    "CII",
]

# ---------------------------------------------------------------------------
# ノイズ除外パターン（URL）
# ---------------------------------------------------------------------------

NOISE_URL_PATTERNS: list[str] = [
    "/budget/",
    "/statistics/",
    "/bidding/",
    "/event/",
    "/personnel/",
    "/report/press/",
    "/common/header",
    "/common/footer",
    "javascript:",
    "mailto:",
    "#",
]

# ---------------------------------------------------------------------------
# ノイズ除外パターン（タイトル・テキスト）
# ---------------------------------------------------------------------------

NOISE_TITLE_KEYWORDS: list[str] = [
    "入札", "統計", "予算", "人事", "イベント", "説明会開催案内",
    "決算", "組織改編", "採用情報", "インターン",
    "モーターボート競走", "海事観光", "帆船模型",
]

# ---------------------------------------------------------------------------
# <main> 要素のフォールバックセレクタ
# ---------------------------------------------------------------------------

MAIN_CONTENT_SELECTORS: list[dict] = [
    {"name": "main"},
    {"name": "article"},
    {"name": "div", "attrs": {"id": "content"}},
    {"name": "div", "attrs": {"id": "main"}},
    {"name": "div", "attrs": {"id": "main-content"}},
    {"name": "div", "attrs": {"class_": "content"}},
    {"name": "div", "attrs": {"class_": "container"}},
]
