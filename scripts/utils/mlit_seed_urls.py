"""
国交省海事局 シードURL + ノイズフィルタ定義
==========================================
BFS に頼らず、重要なインデックスページを直接巡回する。
"""

# ---------------------------------------------------------------------------
# シードURL（インデックスページ、6件固定）
# ---------------------------------------------------------------------------

SEED_URLS: list[str] = [
    "https://www.mlit.go.jp/maritime/maritime_mn4_000005.html",   # 運航労務監理
    "https://www.mlit.go.jp/maritime/maritime_tk8_000003.html",   # 船舶の安全・環境
    "https://www.mlit.go.jp/maritime/maritime_fr4_000030.html",   # 船員安全衛生
    "https://www.mlit.go.jp/maritime/maritime_tk4_000016.html",   # 船員の現状
    "https://www.mlit.go.jp/maritime/maritime_tk10_000017.html",  # 船員養成
    "https://www.mlit.go.jp/maritime/maritime_fr1_000027.html",   # 法律
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
