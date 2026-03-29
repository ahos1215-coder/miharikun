"""
LINE Notify ラッパーモジュール。
GitHub Actions からエラー通知・ヘルスチェック報告を送信する。
スロットリング機能付き（同一 severity は 5 分間に 1 回まで）。
"""

import os
import time
from typing import Optional

import requests


# ---------- 定数 ----------

_LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"
_THROTTLE_INTERVAL = 300  # 5 分 = 300 秒

# severity ごとの最終送信時刻キャッシュ
_last_sent: dict[str, float] = {}

# severity ごとの絵文字プレフィックス
_SEVERITY_PREFIX: dict[str, str] = {
    "critical": "[CRITICAL]",
    "warning": "[WARNING]",
    "info": "[INFO]",
}


# ---------- 内部ユーティリティ ----------

def _get_token() -> Optional[str]:
    """環境変数から LINE Notify トークンを取得する。"""
    return os.environ.get("LINE_NOTIFY_TOKEN") or None


def _is_throttled(severity: str) -> bool:
    """同一 severity が 5 分以内に送信済みかチェックする。"""
    last = _last_sent.get(severity, 0.0)
    return (time.time() - last) < _THROTTLE_INTERVAL


def _mark_sent(severity: str) -> None:
    """送信時刻を記録する。"""
    _last_sent[severity] = time.time()


def _post_line(message: str) -> bool:
    """
    LINE Notify API に POST する。
    トークン未設定時は print のみで True を返す。
    Returns: 送信成功なら True
    """
    token = _get_token()
    if not token:
        print(f"[LineNotify] TOKEN未設定のためコンソール出力のみ: {message}")
        return True

    try:
        resp = requests.post(
            _LINE_NOTIFY_URL,
            headers={"Authorization": f"Bearer {token}"},
            data={"message": message},
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        else:
            print(f"[LineNotify] 送信失敗 status={resp.status_code} body={resp.text[:100]}")
            return False
    except requests.RequestException as e:
        print(f"[LineNotify] 送信例外: {e}")
        return False


def _build_message(title: str, body: str, severity: str) -> str:
    """通知メッセージを組み立てる。"""
    prefix = _SEVERITY_PREFIX.get(severity.lower(), "[INFO]")
    return f"\n{prefix} {title}\n{body}"


# ---------- パブリック API ----------

def send_alert(title: str, message: str, severity: str = "info") -> bool:
    """
    汎用アラートを LINE Notify で送信する。

    Args:
        title:    通知タイトル
        message:  本文
        severity: "critical" | "warning" | "info"

    Returns:
        送信成功または throttle スキップなら True
    """
    severity = severity.lower()
    if severity not in ("critical", "warning", "info"):
        severity = "info"

    if _is_throttled(severity):
        print(f"[LineNotify] スロットリング中 severity={severity!r} title={title!r}")
        return True

    msg = _build_message(title, message, severity)
    success = _post_line(msg)
    if success:
        _mark_sent(severity)
    return success


def send_scraper_error(
    scraper_name: str,
    error: Exception,
    context: Optional[dict] = None,
) -> bool:
    """
    スクレイパーエラーを LINE Notify で送信する。

    Args:
        scraper_name: スクレイパー名（例: "scrape_nk"）
        error:        発生した例外
        context:      追加コンテキスト情報（URL, page_count 等）

    Returns:
        送信成功なら True
    """
    title = f"スクレイパーエラー: {scraper_name}"
    lines = [f"エラー: {type(error).__name__}: {error}"]
    if context:
        for k, v in context.items():
            lines.append(f"{k}: {v}")
    message = "\n".join(lines)

    print(f"[LineNotify] {title} {message}")
    return send_alert(title, message, severity="warning")


def send_health_check_report(report: dict) -> bool:
    """
    ヘルスチェック結果サマリーを LINE Notify で送信する。

    Args:
        report: ヘルスチェック結果 dict。
                期待するキー:
                  - status: "ok" | "warning" | "critical"
                  - sources: list[dict] (name, last_scraped, error_count 等)
                  - db_size_mb: float (任意)
                  - pending_count: int (任意)

    Returns:
        送信成功なら True
    """
    status = report.get("status", "info").lower()
    severity = status if status in ("critical", "warning", "info") else "info"

    title = f"ヘルスチェック: {status.upper()}"
    lines: list[str] = []

    # ソース別サマリー
    sources = report.get("sources", [])
    if sources:
        lines.append("--- ソース状況 ---")
        for src in sources:
            name = src.get("name", "unknown")
            last = src.get("last_scraped", "不明")
            err = src.get("error_count", 0)
            lines.append(f"{name}: 最終取得={last} エラー={err}")

    # DB 容量
    db_mb = report.get("db_size_mb")
    if db_mb is not None:
        lines.append(f"DB容量: {db_mb:.1f} MB")

    # 未処理件数
    pending = report.get("pending_count")
    if pending is not None:
        lines.append(f"未処理キュー: {pending} 件")

    message = "\n".join(lines) if lines else "詳細なし"
    print(f"[LineNotify] ヘルスチェック報告 status={status}")
    return send_alert(title, message, severity=severity)
