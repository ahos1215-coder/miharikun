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

try:
    from utils.gemini_config import (
        DEFAULT_PRIMARY_MODEL,
        DEFAULT_FALLBACK_MODEL,
        GEMINI_API_BASE,
        GEMINI_API_KEY as _CFG_API_KEY,
        MAX_RETRIES,
        BASE_WAIT,
        MAX_WAIT,
        CLASSIFICATION_TEMPERATURE,
        MIN_REQUEST_INTERVAL,
    )
except ImportError:
    from gemini_config import (
        DEFAULT_PRIMARY_MODEL,
        DEFAULT_FALLBACK_MODEL,
        GEMINI_API_BASE,
        GEMINI_API_KEY as _CFG_API_KEY,
        MAX_RETRIES,
        BASE_WAIT,
        MAX_WAIT,
        CLASSIFICATION_TEMPERATURE,
        MIN_REQUEST_INTERVAL,
    )


# ---------- 定数（gemini_config から統一取得） ----------

_GEMINI_MIN_INTERVAL = float(os.environ.get("GEMINI_MIN_INTERVAL", "0.5")) or MIN_REQUEST_INTERVAL
_last_call_timestamp: float = 0.0


# ---------- 内部ユーティリティ ----------

def _rate_limit_wait() -> None:
    """
    前回の API 呼び出しから GEMINI_MIN_INTERVAL 秒経過するまで待機する。
    バースト的なリクエストによる 429 エラーを防止する。
    """
    global _last_call_timestamp
    if _last_call_timestamp > 0:
        elapsed = time.time() - _last_call_timestamp
        remaining = _GEMINI_MIN_INTERVAL - elapsed
        if remaining > 0:
            print(f"[Gemini] レートリミット待機: {remaining:.1f}s")
            time.sleep(remaining)
    _last_call_timestamp = time.time()

def _exponential_backoff(attempt: int, base: float = BASE_WAIT, max_wait: float = MAX_WAIT) -> float:
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
    # レートリミット: 前回呼び出しからの最小間隔を確保
    _rate_limit_wait()

    # PDF を base64 エンコード
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
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
            "temperature": CLASSIFICATION_TEMPERATURE,
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
    api_key = _CFG_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print(f"[Gemini] GEMINI_API_KEY が未設定です source_id={source_id!r}")
        return {"status": "pending", "error": "GEMINI_API_KEY が未設定"}

    primary_model = os.environ.get("GEMINI_MODEL", DEFAULT_PRIMARY_MODEL)
    fallback_model = os.environ.get("GEMINI_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL)

    # プロンプトに confidence/citations 出力を強制するシステム指示を追加
    augmented_prompt = _augment_prompt(prompt)

    for model_label, model_name in [("primary", primary_model), ("fallback", fallback_model)]:
        print(f"[Gemini] {model_label} モデル {model_name!r} で処理開始 source_id={source_id!r}")

        last_error: str = ""
        for attempt in range(MAX_RETRIES):
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
                f"[Gemini] リトライ {attempt + 1}/{MAX_RETRIES} "
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
  "headline": "<規制の内容を20〜30文字で要約した見出し>",
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

- "headline": 規制の内容を20〜30文字で要約した見出し。Yahoo!ニュースのように一般読者にもわかりやすい表現にすること。例: "閉囲区画の安全基準が改正", "NOx排出基準Tier IIIへ強化"
"""
    if "confidence" in prompt and "citations" in prompt:
        return prompt
    return prompt + addition


# ---------------------------------------------------------------------------
# テキスト専用 Gemini 呼び出し（SSoT: 全スクリプトはこれを使うこと）
# ---------------------------------------------------------------------------

def call_gemini_text(
    prompt: str,
    temperature: float = 0.1,
    source_id: str = "",
) -> dict | None:
    """
    テキストのみの Gemini API 呼び出し（PDF なし）。
    全スクリプトで共通利用すること。各スクリプトに独自の call_gemini を書くのは禁止。

    Returns:
        パースされた JSON dict、または失敗時は None
    """
    api_key = os.environ.get("GEMINI_API_KEY", "") or _CFG_API_KEY
    model = os.environ.get("GEMINI_MODEL", DEFAULT_PRIMARY_MODEL)

    if not api_key:
        print(f"[Gemini] GEMINI_API_KEY が未設定です")
        return None

    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }

    _rate_limit_wait()

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, timeout=90)

            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return _parse_gemini_json(text, source_id)

            elif _should_retry(str(resp.status_code)):
                wait = _exponential_backoff(attempt)
                print(f"[Gemini] {resp.status_code} — リトライ {attempt+1}/{MAX_RETRIES} ({wait:.1f}s)")
                time.sleep(wait)
                continue
            else:
                print(f"[Gemini] HTTP {resp.status_code}: {resp.text[:200]}")
                return None

        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait = _exponential_backoff(attempt)
                time.sleep(wait)
                continue
            print(f"[Gemini] 例外: {e}")
            return None

    return None


# ---------------------------------------------------------------------------
# Self-Critique 型プロンプトテンプレート（F-D-H ルール強制）
# ---------------------------------------------------------------------------

SELF_CRITIQUE_PROMPT = """あなたは一級海技士の資格を持つ海事規制の専門家です。
以下のPDF本文を読み、**本文に書いてある事実のみに基づいて**情報を構造化してください。

## ★ 絶対ルール（違反したら即失格）
1. **テンプレ推論は絶対禁止**。PDF に書いていないことは一切推測しない。
2. 「理解する」「認識する」「貢献する」「注意する」はアクションではない。除外せよ。
3. 既に日常業務として実施している基本作業（救命訓練の実施等）は新規性がないので除外。

## ★ F-D-H ルール（アクション抽出の3原則）
抽出するアクションは、以下の3つのいずれかの**実務的変化**を伴うものに限定せよ:
- **Form（様式）**: 第○号様式の変更、記録簿の備置義務、証書の書換・申請、届出書類の変更
- **Deadline（期限）**: ○年○月○日までに○○を完了、経過措置の期限、施行日
- **Hardware/Budget（金と物）**: 設備の換装・追加購入、検査の受検、SMS改訂

## PDF 本文
{pdf_text}

## ページタイトル
{page_title}

## 出力（JSON、Self-Critique 構造）
```json
{{
  "title_ja": "1行の日本語タイトル",
  "summary_ja": "背景・目的・具体的数値を含む要約（200-400字）",
  "legal_basis": "適用条約・法令（条文レベル）",
  "effective_date": "YYYY-MM-DD or null",
  "category": "船員資格/船舶安全/環境規制 等",
  "severity": "critical/action_required/informational",
  "draft_actions": [
    "候補1: ○○の届出が必要",
    "候補2: △△の理解を深める",
    "候補3: 第X号様式の備置義務"
  ],
  "self_critique_log": "候補1→YES（届出=Form変更）。候補2→NO（精神論、削除）。候補3→YES（様式=Form変更）。",
  "final_onboard_actions": ["Self-Critiqueを通過した船側アクションのみ"],
  "final_shore_actions": ["Self-Critiqueを通過した会社側アクションのみ"],
  "sms_chapters": [],
  "is_actionable": true
}}
```
"""
