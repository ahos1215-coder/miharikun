"""
Gemini API ラッパーモジュール。
PDF バイト列を受け取り、海事規制の分類・要約を行う。
プライマリモデル失敗時のフォールバック、指数バックオフ付きリトライを実装。
"""

import base64
import json
import os
import re
import time
from typing import Optional

import requests


# ---------- 定数 ----------

_DEFAULT_PRIMARY_MODEL = "gemini-2.5-flash"
_DEFAULT_FALLBACK_MODEL = "gemini-2.0-flash"
_MAX_RETRIES = 6
_BASE_WAIT = 1.0
_MAX_WAIT = 32.0
_TEMPERATURE = 0.1

_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


# ---------- 内部ユーティリティ ----------

def _exponential_backoff(attempt: int, base: float = _BASE_WAIT, max_wait: float = _MAX_WAIT) -> float:
    """
    指数バックオフの待機秒数を計算する。
    attempt は 0 始まり。
    """
    wait = base * (2 ** attempt)
    return min(wait, max_wait)


def _parse_gemini_json(text: str, source_id: str = "") -> dict:
    """
    Gemini のレスポンステキストから JSON ブロックを抽出して dict を返す。
    コードブロック (```json ... ```) も通常テキストの JSON もどちらも対応。
    """
    # ```json ... ``` ブロックを優先検索
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # コードブロックがない場合、最初の {...} を探す
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            print(f"[Gemini] JSON ブロックが見つかりません source_id={source_id!r}")
            return {"status": "error", "error": "JSON ブロックが見つかりません", "raw": text}

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"[Gemini] JSON パースエラー source_id={source_id!r}: {e}")
        return {"status": "error", "error": f"JSON パースエラー: {e}", "raw": json_str}


def _call_gemini_api(
    model: str,
    api_key: str,
    pdf_bytes: bytes,
    prompt: str,
) -> tuple[bool, dict | str]:
    """
    Gemini API を一度呼び出す。
    Returns: (success: bool, result: dict or error_str)
    """
    # PDF を base64 エンコード
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    url = f"{_GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "application/pdf",
                            "data": pdf_b64,
                        }
                    },
                    {
                        "text": prompt,
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": _TEMPERATURE,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=120)
    except requests.RequestException as e:
        return False, f"HTTPリクエスト例外: {e}"

    if resp.status_code == 200:
        try:
            data = resp.json()
            # レスポンスからテキストを取り出す
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return True, text
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            return False, f"レスポンスパースエラー: {e} / body={resp.text[:200]}"
    else:
        # 429, 500+ はリトライ対象
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"


def _should_retry(error_str: str) -> bool:
    """
    エラー文字列からリトライ可否を判定する。
    """
    return ("429" in error_str or
            "500" in error_str or
            "502" in error_str or
            "503" in error_str or
            "504" in error_str or
            "HTTPリクエスト例外" in error_str)


# ---------- パブリック API ----------

def classify_pdf(pdf_bytes: bytes, prompt: str, source_id: str = "") -> dict:
    """
    PDF バイト列を Gemini に送信して分類・要約結果を返す。

    Args:
        pdf_bytes: PDF ファイルのバイト列
        prompt:    Gemini に送るプロンプト（JSON 出力を指示すること）
        source_id: ログ用の識別子（例: "TEC-1361"）

    Returns:
        分類結果の dict。少なくとも以下のフィールドを含む:
        - status: "ok" | "pending" | "error"
        - confidence: float (0.0-1.0)
        - citations: list[dict]
        失敗時は {"status": "pending", "error": str} を返す。
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print(f"[Gemini] GEMINI_API_KEY が未設定です source_id={source_id!r}")
        return {"status": "pending", "error": "GEMINI_API_KEY が未設定"}

    primary_model = os.environ.get("GEMINI_MODEL", _DEFAULT_PRIMARY_MODEL)
    fallback_model = os.environ.get("GEMINI_FALLBACK_MODEL", _DEFAULT_FALLBACK_MODEL)

    # プロンプトに confidence/citations 出力を強制するシステム指示を追加
    augmented_prompt = _augment_prompt(prompt)

    for model_label, model_name in [("primary", primary_model), ("fallback", fallback_model)]:
        print(f"[Gemini] {model_label} モデル {model_name!r} で処理開始 source_id={source_id!r}")

        last_error: str = ""
        for attempt in range(_MAX_RETRIES):
            success, result = _call_gemini_api(model_name, api_key, pdf_bytes, augmented_prompt)

            if success:
                # result はテキスト文字列
                parsed = _parse_gemini_json(result, source_id)
                # status フィールドが無ければ ok を付与
                if "status" not in parsed:
                    parsed["status"] = "ok"
                # confidence/citations がなければデフォルト値
                parsed.setdefault("confidence", 0.0)
                parsed.setdefault("citations", [])
                print(
                    f"[Gemini] 分類成功 source_id={source_id!r} "
                    f"model={model_name!r} confidence={parsed.get('confidence')}"
                )
                return parsed

            last_error = str(result)
            if not _should_retry(last_error):
                # リトライ不要なエラー（認証エラーなど）は即座に次モデルへ
                print(f"[Gemini] リトライ不可エラー model={model_name!r}: {last_error[:100]}")
                break

            wait = _exponential_backoff(attempt)
            print(
                f"[Gemini] リトライ {attempt + 1}/{_MAX_RETRIES} "
                f"model={model_name!r} wait={wait:.1f}s error={last_error[:80]}"
            )
            time.sleep(wait)
        else:
            print(f"[Gemini] {model_label} モデル {model_name!r} 全リトライ失敗 last_error={last_error[:100]}")

    # プライマリ・フォールバック両方失敗
    print(f"[Gemini] 全モデル失敗 source_id={source_id!r}")
    return {"status": "pending", "error": f"全モデル失敗: {last_error[:200]}"}


def _augment_prompt(prompt: str) -> str:
    """
    ユーザー提供プロンプトに confidence/citations の出力要件を追記する。
    プロンプトにすでに含まれている場合は重複しないように配慮する。
    """
    addition = """

## 出力フォーマット（必須）
以下の JSON 形式で出力してください。コードブロック (```json ... ```) に包んでください。
過去の学習知識は使わず、添付PDFのテキストのみから判断してください。

```json
{
  "status": "ok",
  "category": "<カテゴリ名>",
  "summary": "<日本語の要約 200字以内>",
  "severity": "<critical|warning|info|upcoming>",
  "confidence": <0.0〜1.0の数値>,
  "citations": [
    {
      "text": "<根拠となる原文の抜粋>",
      "page": <ページ番号>,
      "source": "<文書識別子>"
    }
  ],
  "applicable_vessel_types": ["<船種>"],
  "effective_date": "<施行日 or null>"
}
```
"""
    if "confidence" in prompt and "citations" in prompt:
        return prompt
    return prompt + addition
