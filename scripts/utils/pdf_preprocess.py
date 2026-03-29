"""
PDF 前処理ユーティリティ
========================
Gemini に送る前に PDF の品質チェックを行う。
- サイズチェック（< 1KB → broken link）
- テキスト抽出（PyMuPDF）
- スキャン画像 PDF の検出
- HEAD リクエストによる事前確認

使い方:
    from utils.pdf_preprocess import preprocess_pdf, check_pdf_url, extract_text
"""

import logging
from typing import Optional

import requests

# PyMuPDF（fitz）は実行環境に依存するためインポートエラーを柔軟に処理
try:
    import fitz  # type: ignore
    _FITZ_AVAILABLE = True
except ImportError:
    _FITZ_AVAILABLE = False

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ログに [PDF] プレフィックスを付けるカスタムフォーマッタ
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("[PDF] %(levelname)s %(message)s"))
logger.addHandler(_handler)
logger.propagate = False  # 親ロガーへの伝播を抑制

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# ファイルサイズ閾値
MIN_PDF_SIZE_BYTES = 1024        # 1KB 未満はリンク切れ疑い
TEXT_SCAN_THRESHOLD = 50         # テキスト文字数がこれ未満 → suspicious
TEXT_EMPTY_THRESHOLD = 0         # テキスト文字数が 0 → scan_image

USER_AGENT = "MaritimeRegsMonitor/0.1 (+https://github.com/ahos1215-coder)"


# ---------------------------------------------------------------------------
# パブリック API
# ---------------------------------------------------------------------------

def check_pdf_url(url: str, headers: Optional[dict] = None) -> dict:
    """
    PDF URL の事前チェック（HEAD リクエスト）。
    Content-Length, Last-Modified, Content-Type を確認する。

    Args:
        url: チェック対象の URL
        headers: 追加リクエストヘッダー（省略可）

    Returns:
        {
            "accessible": bool,
            "content_length": Optional[int],
            "last_modified": Optional[str],
            "content_type": Optional[str],
            "warning": Optional[str],
        }
    """
    result: dict = {
        "accessible": False,
        "content_length": None,
        "last_modified": None,
        "content_type": None,
        "warning": None,
    }

    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)

    try:
        resp = requests.head(url, headers=req_headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()

        result["accessible"] = True

        # Content-Length
        raw_length = resp.headers.get("Content-Length")
        if raw_length and raw_length.isdigit():
            result["content_length"] = int(raw_length)
            if result["content_length"] < MIN_PDF_SIZE_BYTES:
                result["warning"] = (
                    f"Content-Length が異常に小さい ({result['content_length']} bytes)。"
                    "リンク切れの可能性あり。"
                )
                logger.warning(
                    "小さいファイルサイズを検出: %s (%d bytes)",
                    url,
                    result["content_length"],
                )

        # Last-Modified
        result["last_modified"] = resp.headers.get("Last-Modified")

        # Content-Type
        result["content_type"] = resp.headers.get("Content-Type")
        if result["content_type"] and "pdf" not in result["content_type"].lower():
            existing_warning = result["warning"] or ""
            result["warning"] = (
                existing_warning
                + f" Content-Type が PDF ではない: {result['content_type']}"
            ).strip()
            logger.warning("想定外の Content-Type: %s (%s)", url, result["content_type"])

    except requests.exceptions.HTTPError as e:
        result["warning"] = f"HTTP エラー: {e.response.status_code}"
        logger.warning("HEAD リクエスト失敗: %s — %s", url, e)
    except requests.exceptions.RequestException as e:
        result["warning"] = f"接続エラー: {e}"
        logger.warning("接続エラー: %s — %s", url, e)

    return result


def extract_text(pdf_bytes: bytes) -> tuple[str, int]:
    """
    PyMuPDF でテキスト抽出。

    Args:
        pdf_bytes: PDF のバイナリデータ

    Returns:
        (text, page_count) のタプル。
        text が空または 50 文字未満の場合はスキャン画像の可能性がある。
        PyMuPDF が利用できない場合は ("", 0) を返す。
    """
    if not _FITZ_AVAILABLE:
        logger.warning("PyMuPDF (fitz) が利用できません。テキスト抽出をスキップ。")
        return ("", 0)

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore
        page_count = len(doc)
        text_parts: list[str] = []

        for page in doc:
            text_parts.append(page.get_text())  # type: ignore

        doc.close()
        full_text = "\n".join(text_parts).strip()
        logger.debug(
            "テキスト抽出完了: %d ページ、%d 文字", page_count, len(full_text)
        )
        return (full_text, page_count)

    except Exception as e:
        logger.error("テキスト抽出エラー: %s", e)
        return ("", 0)


def preprocess_pdf(url: str, pdf_bytes: bytes) -> dict:
    """
    PDF の品質チェック。Gemini に送る前に問題を検出する。

    Args:
        url: PDF の元 URL（ログ・レポート用）
        pdf_bytes: PDF のバイナリデータ

    Returns:
        {
            "status": "ok" | "skipped" | "scan_image" | "suspicious",
            "size_bytes": int,
            "text_length": int,
            "page_count": int,
            "last_modified": Optional[str],  # 常に None（bytes からは取得不可）
            "warning": Optional[str],
            "skip_reason": Optional[str],
        }
    """
    size_bytes = len(pdf_bytes)
    logger.info("PDF チェック開始: %s (%d bytes)", url, size_bytes)

    result: dict = {
        "status": "ok",
        "size_bytes": size_bytes,
        "text_length": 0,
        "page_count": 0,
        "last_modified": None,  # バイナリからは取得できない。check_pdf_url を使うこと
        "warning": None,
        "skip_reason": None,
    }

    # ── 1. サイズチェック ────────────────────────────────────────────────
    if size_bytes < MIN_PDF_SIZE_BYTES:
        result["status"] = "skipped"
        result["skip_reason"] = (
            f"ファイルサイズが小さすぎる ({size_bytes} bytes < {MIN_PDF_SIZE_BYTES} bytes)。"
            "リンク切れの可能性。"
        )
        logger.warning("スキップ（サイズ不足）: %s", url)
        return result

    # ── 2. テキスト抽出 ────────────────────────────────────────────────
    text, page_count = extract_text(pdf_bytes)
    text_length = len(text)
    result["text_length"] = text_length
    result["page_count"] = page_count

    # ── 3. テキスト品質判定 ────────────────────────────────────────────
    if text_length == TEXT_EMPTY_THRESHOLD:
        result["status"] = "scan_image"
        result["warning"] = (
            "テキストが抽出できません。スキャン画像 PDF の可能性があります。"
            "Gemini の精度が低下する場合があります。"
        )
        logger.warning("スキャン画像 PDF の可能性: %s", url)
    elif text_length < TEXT_SCAN_THRESHOLD:
        result["status"] = "suspicious"
        result["warning"] = (
            f"テキストが極端に少ない ({text_length} 文字)。"
            "スキャン画像 PDF またはフォームのみの可能性があります。"
        )
        logger.warning(
            "テキスト不足 PDF の可能性 (%d 文字): %s", text_length, url
        )
    else:
        logger.info(
            "PDF チェック OK: %d ページ、%d 文字 (%s)",
            page_count,
            text_length,
            url,
        )

    return result
