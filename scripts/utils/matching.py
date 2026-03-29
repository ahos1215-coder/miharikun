"""
マッチングエンジン v1 — 規制 × 船舶プロファイルの適用判定
=========================================================
2段階マッチング:
  Stage 1: ルールベースフィルタ（高速除外）
  Stage 2: AI マッチング（Gemini、Stage 1 で判断できなかった場合のみ）

使い方:
    from utils.matching import match_regulation_to_ship

    result = match_regulation_to_ship(regulation_dict, ship_dict)
    # {
    #   "is_applicable": True,
    #   "match_method": "ai_matching",
    #   "confidence": 0.92,
    #   "reason": "GT 500 以上の国際航行船舶に適用（本船 GT 2,800）",
    #   "citations": [...]
    # }
"""

import json
import logging
import os
import re
import sys
import time
from typing import Optional

# utils/ 内の他モジュールを import 可能にする
sys.path.insert(0, os.path.dirname(__file__))

import requests

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[Matching] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_DEFAULT_PRIMARY_MODEL = "gemini-2.5-flash"
_DEFAULT_FALLBACK_MODEL = "gemini-2.0-flash"
_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_MAX_RETRIES = 4
_BASE_WAIT = 1.0
_MAX_WAIT = 16.0
_TEMPERATURE = 0.1

# confidence < この閾値の場合は "needs_review" フラグを立てる（フロント側で「要確認」表示）
_REVIEW_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# Stage 1: ルールベースフィルタ
# ---------------------------------------------------------------------------

def rule_based_filter(regulation: dict, ship: dict) -> str:
    """
    船舶スペックと規制のメタデータを比較し、明確に非適用なケースを高速除外する。

    Args:
        regulation: regulations テーブルの行 dict
                    参照フィールド:
                      applicable_ship_types (list[str] | None)
                      applicable_gt_min     (int | None)
                      applicable_gt_max     (int | None)
                      applicable_built_after (int | None)
                      applicable_routes     (list[str] | None)
                      applicable_flags      (list[str] | None)
        ship:       ship_profiles テーブルの行 dict
                    参照フィールド:
                      ship_type       (str)
                      gross_tonnage   (int)
                      build_year      (int)
                      navigation_area (list[str])
                      flag_state      (str)

    Returns:
        'applicable'     — ルールベースで適用と確定（現在は使用しないが拡張余地）
        'not_applicable' — ルールベースで非適用と確定（AI に送らない）
        'needs_ai'       — ルールベースでは判断不能、AI マッチングに委譲
    """
    ship_type: str = ship.get("ship_type", "")
    gross_tonnage: Optional[int] = ship.get("gross_tonnage")
    build_year: Optional[int] = ship.get("build_year")
    navigation_area: list[str] = ship.get("navigation_area") or []
    flag_state: str = ship.get("flag_state", "")

    # --- 船種フィルタ ---
    applicable_ship_types: list[str] = regulation.get("applicable_ship_types") or []
    if applicable_ship_types and ship_type not in applicable_ship_types:
        logger.debug(
            f"[rule] not_applicable: ship_type={ship_type!r} "
            f"not in {applicable_ship_types}"
        )
        return "not_applicable"

    # --- GT 下限フィルタ ---
    applicable_gt_min: Optional[int] = regulation.get("applicable_gt_min")
    if applicable_gt_min is not None and gross_tonnage is not None:
        if applicable_gt_min > gross_tonnage:
            logger.debug(
                f"[rule] not_applicable: GT min {applicable_gt_min} > ship GT {gross_tonnage}"
            )
            return "not_applicable"

    # --- GT 上限フィルタ ---
    applicable_gt_max: Optional[int] = regulation.get("applicable_gt_max")
    if applicable_gt_max is not None and gross_tonnage is not None:
        if applicable_gt_max < gross_tonnage:
            logger.debug(
                f"[rule] not_applicable: GT max {applicable_gt_max} < ship GT {gross_tonnage}"
            )
            return "not_applicable"

    # --- 建造年フィルタ ---
    applicable_built_after: Optional[int] = regulation.get("applicable_built_after")
    if applicable_built_after is not None and build_year is not None:
        if applicable_built_after > build_year:
            logger.debug(
                f"[rule] not_applicable: built_after {applicable_built_after} > build_year {build_year}"
            )
            return "not_applicable"

    # --- 航行区域フィルタ ---
    applicable_routes: list[str] = regulation.get("applicable_routes") or []
    if applicable_routes and navigation_area:
        # 規制の applicable_routes と船の navigation_area が全く交差しない場合は非適用
        if not set(applicable_routes) & set(navigation_area):
            logger.debug(
                f"[rule] not_applicable: routes {applicable_routes} ∩ "
                f"navigation_area {navigation_area} = ∅"
            )
            return "not_applicable"

    # --- 旗国フィルタ ---
    applicable_flags: list[str] = regulation.get("applicable_flags") or []
    if applicable_flags and flag_state not in applicable_flags:
        logger.debug(
            f"[rule] not_applicable: flag_state={flag_state!r} "
            f"not in {applicable_flags}"
        )
        return "not_applicable"

    # いずれのフィルタにも引っかからなかった → AI に委譲
    logger.debug("[rule] needs_ai: ルールベースで除外できず")
    return "needs_ai"


# ---------------------------------------------------------------------------
# Stage 2: AI マッチング（Gemini）
# ---------------------------------------------------------------------------

def _build_matching_prompt(regulation: dict, ship: dict) -> str:
    """
    Gemini に送るマッチング判定プロンプトを構築する。
    PDF なしのテキストのみで判定させる（classify_pdf とは異なる）。
    """
    ship_summary = (
        f"船名: {ship.get('ship_name', '不明')}\n"
        f"船種: {ship.get('ship_type', '不明')}\n"
        f"総トン数 (GT): {ship.get('gross_tonnage', '不明')} GT\n"
        f"載貨重量トン数 (DWT): {ship.get('dwt', '不明')} DWT\n"
        f"建造年: {ship.get('build_year', '不明')} 年\n"
        f"船級: {ship.get('classification_society', '不明')}\n"
        f"船籍国: {ship.get('flag_state', '不明')}\n"
        f"航行区域: {', '.join(ship.get('navigation_area') or []) or '不明'}\n"
        f"航路: {', '.join(ship.get('routes') or []) or '不明'}"
    )

    regulation_summary = (
        f"規制タイトル: {regulation.get('title', '不明')}\n"
        f"カテゴリ: {regulation.get('category', '不明')}\n"
        f"ソース: {regulation.get('source', '不明')} / ID: {regulation.get('source_id', '不明')}\n"
        f"AI 要約 (日本語): {regulation.get('summary_ja', '（なし）')}\n"
        f"適用船種: {', '.join(regulation.get('applicable_ship_types') or []) or '制限なし'}\n"
        f"GT 下限: {regulation.get('applicable_gt_min', '制限なし')}\n"
        f"GT 上限: {regulation.get('applicable_gt_max', '制限なし')}\n"
        f"建造年以降適用: {regulation.get('applicable_built_after', '制限なし')}\n"
        f"適用航路: {', '.join(regulation.get('applicable_routes') or []) or '制限なし'}\n"
        f"適用旗国: {', '.join(regulation.get('applicable_flags') or []) or '制限なし'}\n"
        f"根拠引用: {json.dumps(regulation.get('citations') or [], ensure_ascii=False)}"
    )

    prompt = f"""あなたは海事規制の専門家です。以下の「自船スペック」と「規制情報」を照合し、
この規制が当該船舶に適用されるかどうかを判定してください。

## 自船スペック
{ship_summary}

## 規制情報
{regulation_summary}

## 判定基準
- 規制の適用範囲（船種・GT・建造年・航行区域・旗国）と自船スペックを照合する
- 情報が不足している場合は confidence を低くする（0.5 以下）
- 適用可能性が否定できない場合は is_applicable: true とし、confidence で確度を表す

## 出力フォーマット（必須）
以下の JSON 形式で出力してください。コードブロック (```json ... ```) に包んでください。
過去の学習知識のみで判断せず、上記の規制情報テキストを根拠にしてください。

```json
{{
  "is_applicable": <true | false>,
  "confidence": <0.0〜1.0 の数値>,
  "reason": "<適用/非適用の理由を日本語で 100 字以内。例: GT 500 以上の国際航行船舶に適用（本船 GT 2,800）>",
  "citations": [
    {{
      "text": "<根拠となる規制文の抜粋>",
      "source": "<文書識別子>"
    }}
  ]
}}
```
"""
    return prompt


def _call_gemini_text(model: str, api_key: str, prompt: str) -> tuple[bool, str]:
    """
    テキストのみの Gemini API 呼び出し（PDF なし）。
    Returns: (success: bool, text_or_error: str)
    """
    url = f"{_GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": _TEMPERATURE,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=60)
    except requests.RequestException as e:
        return False, f"HTTPリクエスト例外: {e}"

    if resp.status_code == 200:
        try:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return True, text
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            return False, f"レスポンスパースエラー: {e} / body={resp.text[:200]}"
    else:
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"


def _should_retry(error_str: str) -> bool:
    """リトライ可能なエラーか判定"""
    return any(code in error_str for code in ["429", "500", "502", "503", "504", "HTTPリクエスト例外"])


def _parse_json_response(text: str) -> dict:
    """
    Gemini レスポンステキストから JSON ブロックを抽出して dict を返す。
    """
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            logger.warning("[AI] JSON ブロックが見つかりません")
            return {}

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"[AI] JSON パースエラー: {e}")
        return {}


def ai_match(regulation: dict, ship: dict) -> dict:
    """
    Gemini に規制の要約・引用と船舶スペックを送り、適用/非適用を判定させる。

    Args:
        regulation: regulations テーブルの行 dict（summary_ja, citations 等を含む）
        ship:       ship_profiles テーブルの行 dict

    Returns:
        {
            "is_applicable": bool,
            "confidence":    float,    # 0.0〜1.0
            "reason":        str,      # "GT 500 以上の国際航行船舶に適用（本船 GT 2,800）"
            "citations":     list,     # AI が根拠とした引用
        }
        失敗時は is_applicable=None, confidence=0.0 を返す。
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.warning("[AI] GEMINI_API_KEY が未設定です")
        return {
            "is_applicable": None,
            "confidence": 0.0,
            "reason": "GEMINI_API_KEY が未設定のため判定不能",
            "citations": [],
        }

    primary_model = os.environ.get("GEMINI_MODEL", _DEFAULT_PRIMARY_MODEL)
    fallback_model = os.environ.get("GEMINI_FALLBACK_MODEL", _DEFAULT_FALLBACK_MODEL)

    prompt = _build_matching_prompt(regulation, ship)
    source_label = f"{regulation.get('source', '?')}/{regulation.get('source_id', '?')}"

    for model_label, model_name in [("primary", primary_model), ("fallback", fallback_model)]:
        logger.info(f"[AI] {model_label} モデル {model_name!r} で判定開始 regulation={source_label}")

        last_error: str = ""
        for attempt in range(_MAX_RETRIES):
            success, result = _call_gemini_text(model_name, api_key, prompt)

            if success:
                parsed = _parse_json_response(result)
                if not parsed:
                    # JSON 抽出失敗 → フォールバックへ
                    last_error = "JSON 抽出失敗"
                    break

                is_applicable = parsed.get("is_applicable")
                confidence = float(parsed.get("confidence", 0.0))
                reason = parsed.get("reason", "")
                citations = parsed.get("citations") or []

                logger.info(
                    f"[AI] 判定完了 regulation={source_label} "
                    f"is_applicable={is_applicable} confidence={confidence:.2f}"
                )
                return {
                    "is_applicable": is_applicable,
                    "confidence": confidence,
                    "reason": reason,
                    "citations": citations,
                }

            last_error = str(result)
            if not _should_retry(last_error):
                logger.warning(f"[AI] リトライ不可エラー model={model_name!r}: {last_error[:100]}")
                break

            wait = min(_BASE_WAIT * (2 ** attempt), _MAX_WAIT)
            logger.warning(
                f"[AI] リトライ {attempt + 1}/{_MAX_RETRIES} "
                f"model={model_name!r} wait={wait:.1f}s"
            )
            time.sleep(wait)
        else:
            logger.error(f"[AI] {model_label} モデル {model_name!r} 全リトライ失敗")

    # プライマリ・フォールバック両方失敗
    logger.error(f"[AI] 全モデル失敗 regulation={source_label}")
    return {
        "is_applicable": None,
        "confidence": 0.0,
        "reason": f"AI 判定失敗: {last_error[:100]}",
        "citations": [],
    }


# ---------------------------------------------------------------------------
# 統合関数: ルールベース → AI の2段階マッチング
# ---------------------------------------------------------------------------

def match_regulation_to_ship(regulation: dict, ship: dict) -> dict:
    """
    規制と船舶プロファイルの2段階マッチングを実行する。

    Stage 1: rule_based_filter — 高速除外（Gemini 不使用）
    Stage 2: ai_match         — Gemini による精密判定（Stage 1 で needs_ai の場合のみ）

    Args:
        regulation: regulations テーブルの行 dict
        ship:       ship_profiles テーブルの行 dict

    Returns:
        {
            "is_applicable":  bool | None,  # None = AI 失敗で不明
            "match_method":   str,          # 'rule_based' | 'ai_matching'
            "confidence":     float,        # 0.0〜1.0
            "reason":         str,
            "citations":      list,
            "needs_review":   bool,         # confidence < 0.7 の場合 True
        }
    """
    source_label = f"{regulation.get('source', '?')}/{regulation.get('source_id', '?')}"
    ship_label = f"{ship.get('ship_name', '?')} (GT {ship.get('gross_tonnage', '?')})"
    logger.info(f"マッチング開始: regulation={source_label} ship={ship_label}")

    # --- Stage 1: ルールベースフィルタ ---
    rule_result = rule_based_filter(regulation, ship)

    if rule_result == "not_applicable":
        logger.info(f"[Stage1] not_applicable: regulation={source_label}")
        return {
            "is_applicable": False,
            "match_method": "rule_based",
            "confidence": 1.0,
            "reason": "船種・GT・建造年・航行区域・旗国のいずれかが適用範囲外",
            "citations": [],
            "needs_review": False,
        }

    if rule_result == "applicable":
        # 現在このパスは使用しないが、将来の拡張のために保持
        logger.info(f"[Stage1] applicable (rule): regulation={source_label}")
        return {
            "is_applicable": True,
            "match_method": "rule_based",
            "confidence": 1.0,
            "reason": "全適用条件を満たす",
            "citations": [],
            "needs_review": False,
        }

    # --- Stage 2: AI マッチング ---
    logger.info(f"[Stage2] AI マッチング開始: regulation={source_label}")
    ai_result = ai_match(regulation, ship)

    confidence = ai_result.get("confidence", 0.0)
    needs_review = confidence < _REVIEW_THRESHOLD

    if needs_review:
        logger.info(
            f"[Stage2] needs_review: confidence={confidence:.2f} < {_REVIEW_THRESHOLD} "
            f"regulation={source_label}"
        )

    return {
        "is_applicable": ai_result.get("is_applicable"),
        "match_method": "ai_matching",
        "confidence": confidence,
        "reason": ai_result.get("reason", ""),
        "citations": ai_result.get("citations") or [],
        "needs_review": needs_review,
    }
