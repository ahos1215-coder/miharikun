"""
Stealth HTTP フェッチャー — Scrapling ラッパー
================================================================
Scrapling の StealthyFetcher が利用可能な場合はそちらを使い、
利用不可 or 失敗時は通常の requests にフォールバックする。

使い方:
    from utils.stealth_fetcher import stealth_get, stealth_download

    resp = stealth_get("https://example.com")
    print(resp.status_code, len(resp.text))

    ok = stealth_download("https://example.com/file.pdf", "/tmp/file.pdf")
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scrapling 利用可能チェック
# ---------------------------------------------------------------------------

_scrapling_available = False
_StealthyFetcher = None

try:
    from scrapling import StealthyFetcher as _SF
    _StealthyFetcher = _SF
    _scrapling_available = True
    logger.info("[Stealth] Scrapling StealthyFetcher is available")
except ImportError:
    logger.info("[Fallback] Scrapling not installed — using requests")
except Exception as e:
    logger.warning(f"[Fallback] Scrapling import failed: {e} — using requests")


# ---------------------------------------------------------------------------
# デフォルトヘッダー（requests フォールバック用）
# ---------------------------------------------------------------------------

_DEFAULT_HEADERS = {
    "User-Agent": os.getenv(
        "SCRAPE_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


# ---------------------------------------------------------------------------
# 統一レスポンスオブジェクト
# ---------------------------------------------------------------------------

@dataclass
class Response:
    """stealth_get が返す統一レスポンス（requests.Response 互換の最小セット）"""
    status_code: int
    text: str
    content: bytes
    url: str
    encoding: Optional[str] = None

    def raise_for_status(self) -> None:
        """4xx/5xx の場合に例外を発生"""
        if 400 <= self.status_code < 600:
            raise requests.HTTPError(
                f"HTTP {self.status_code} for url: {self.url}",
                response=self,  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# stealth_get — HTML ページ取得
# ---------------------------------------------------------------------------

def stealth_get(url: str, headers: Optional[dict] = None, timeout: int = 30) -> Response:
    """
    URL から HTML ページを取得する。
    Scrapling StealthyFetcher → requests の順にフォールバック。

    Args:
        url: 取得先 URL
        headers: 追加ヘッダー（requests フォールバック用。Scrapling 時は無視される）
        timeout: タイムアウト秒数

    Returns:
        Response オブジェクト
    """
    # Scrapling で試行
    if _scrapling_available and _StealthyFetcher is not None:
        try:
            logger.info(f"[Stealth] Fetching: {url}")
            fetcher = _StealthyFetcher()
            page = fetcher.fetch(url)

            # Scrapling のレスポンスから統一 Response を構築
            status = getattr(page, 'status', 200)
            html = str(page.html) if hasattr(page, 'html') else getattr(page, 'text', '')
            content = html.encode('utf-8') if isinstance(html, str) else html

            resp = Response(
                status_code=status,
                text=html,
                content=content,
                url=url,
                encoding='utf-8',
            )
            logger.info(f"[Stealth] Success: {url} (status={status}, {len(content):,} bytes)")
            return resp
        except Exception as e:
            logger.warning(f"[Stealth] Failed for {url}: {e} — falling back to requests")

    # requests フォールバック
    merged_headers = {**_DEFAULT_HEADERS, **(headers or {})}
    logger.info(f"[Fallback] Fetching: {url}")
    r = requests.get(url, headers=merged_headers, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding

    resp = Response(
        status_code=r.status_code,
        text=r.text,
        content=r.content,
        url=str(r.url),
        encoding=r.encoding,
    )
    logger.info(f"[Fallback] Success: {url} (status={r.status_code}, {len(r.content):,} bytes)")
    return resp


# ---------------------------------------------------------------------------
# stealth_download — PDF 等のバイナリダウンロード
# ---------------------------------------------------------------------------

def stealth_download(url: str, dest_path: str, headers: Optional[dict] = None, timeout: int = 60) -> bool:
    """
    URL からファイルをダウンロードして dest_path に保存する。

    Args:
        url: ダウンロード URL
        dest_path: 保存先パス
        headers: 追加ヘッダー（requests フォールバック用）
        timeout: タイムアウト秒数

    Returns:
        True: 成功、False: 失敗
    """
    try:
        content = stealth_download_bytes(url, headers=headers, timeout=timeout)
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(content)
        logger.info(f"Downloaded {len(content):,} bytes → {dest_path}")
        return True
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return False


def stealth_download_bytes(url: str, headers: Optional[dict] = None, timeout: int = 60) -> bytes:
    """
    URL からバイナリコンテンツをダウンロードしてバイト列を返す。
    stealth_get と同じフォールバック戦略を使う。

    Args:
        url: ダウンロード URL
        headers: 追加ヘッダー（requests フォールバック用）
        timeout: タイムアウト秒数

    Returns:
        ダウンロードしたバイト列

    Raises:
        requests.RequestException: ダウンロード失敗時
    """
    # Scrapling で試行（PDF ダウンロードはヘッドレスブラウザ不要な場合が多いが、
    # WAF バイパスのために Scrapling 経由で取得を試みる）
    if _scrapling_available and _StealthyFetcher is not None:
        try:
            logger.info(f"[Stealth] Downloading: {url}")
            fetcher = _StealthyFetcher()
            page = fetcher.fetch(url)

            # バイナリコンテンツを取得
            content = getattr(page, 'content', None)
            if content is None:
                html = str(page.html) if hasattr(page, 'html') else getattr(page, 'text', '')
                content = html.encode('utf-8') if isinstance(html, str) else html

            if content and len(content) > 0:
                logger.info(f"[Stealth] Downloaded: {url} ({len(content):,} bytes)")
                return content
            else:
                logger.warning(f"[Stealth] Empty content for {url} — falling back to requests")
        except Exception as e:
            logger.warning(f"[Stealth] Download failed for {url}: {e} — falling back to requests")

    # requests フォールバック
    merged_headers = {**_DEFAULT_HEADERS, **(headers or {})}
    logger.info(f"[Fallback] Downloading: {url}")
    r = requests.get(url, headers=merged_headers, timeout=timeout)
    r.raise_for_status()
    logger.info(f"[Fallback] Downloaded: {url} ({len(r.content):,} bytes)")
    return r.content
