"""
マッチングエンジン v3 — 規制 × 船舶プロファイルの適用判定
=========================================================
4段階マッチング:
  Stage 1: ルールベースフィルタ（高速除外）
  Stage 0: 条約ベースマッチング（船に適用される条約のキーワード照合）
  Stage 2: applicability_rules 評価（API不要、JSONB ルール照合）
  Stage 3: AI マッチング（Gemini、Stage 0/1/2 で判断できなかった場合のみ）

使い方:
    from utils.matching import match_regulation_to_ship

    result = match_regulation_to_ship(regulation_dict, ship_dict)
    # {
    #   "is_applicable": True,
    #   "match_method": "convention_based",
    #   "confidence": 0.95,
    #   "reason": "SOLAS Ch.II-1 適用船 — GT 500 以上の国際航行船舶",
    #   "conventions": ["solas_ii1"],
    #   "actions": [...],
    #   "national_laws": [...],
    #   "certificates": [...],
    #   "needs_review": False,
    #   "citations": None,
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
# scripts/ と scripts/utils/ の両方をパスに追加
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests

try:
    from utils.ship_compliance import determine_compliance, get_applicable_keywords
except ImportError:
    from ship_compliance import determine_compliance, get_applicable_keywords

try:
    from utils.maritime_knowledge import KEYWORD_EXCLUSIONS
except ImportError:
    from maritime_knowledge import KEYWORD_EXCLUSIONS

try:
    from utils.validation import validate_matching
except ImportError:
    from validation import validate_matching

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
# キーワードマッチングヘルパー
# ---------------------------------------------------------------------------

def _keyword_in_text(keyword: str, text: str) -> bool:
    """
    キーワードがテキスト内に存在するか判定。
    英語キーワード: 単語境界マッチ（ISM が tourism にマッチしないように）
    日本語キーワード: 部分文字列マッチ
    """
    kw_lower = keyword.lower()
    # ASCII only かつ英字のみ = English keyword → use word boundary
    if kw_lower.isascii() and kw_lower.isalpha():
        return bool(re.search(r'\b' + re.escape(kw_lower) + r'\b', text, re.IGNORECASE))
    else:
        return kw_lower in text


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
    # "all" は全船適用を意味するため除外しない
    applicable_ship_types: list[str] = regulation.get("applicable_ship_types") or []
    if applicable_ship_types and "all" not in applicable_ship_types:
        if ship_type not in applicable_ship_types:
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
    # "all" は全航行区域適用を意味する
    applicable_routes: list[str] = regulation.get("applicable_routes") or []
    if applicable_routes and "all" not in applicable_routes and navigation_area:
        if not set(applicable_routes) & set(navigation_area):
            logger.debug(
                f"[rule] not_applicable: routes {applicable_routes} ∩ "
                f"navigation_area {navigation_area} = ∅"
            )
            return "not_applicable"

    # --- 旗国フィルタ ---
    # "all" は全旗国適用を意味する
    applicable_flags: list[str] = regulation.get("applicable_flags") or []
    if applicable_flags and "all" not in applicable_flags:
        if flag_state not in applicable_flags:
            logger.debug(
                f"[rule] not_applicable: flag_state={flag_state!r} "
                f"not in {applicable_flags}"
            )
            return "not_applicable"

    # --- カテゴリ/キーワードによる非船舶規制フィルタ ---
    title: str = (regulation.get("title") or "").lower()
    summary: str = (regulation.get("summary_ja") or "").lower()
    category: str = (regulation.get("category") or "").lower()
    combined_text: str = f"{title} {summary} {category}"

    # 港湾・陸上施設・インフラ系キーワード（船舶運航に直接関係しない）
    _INFRASTRUCTURE_KEYWORDS: list[str] = [
        "港湾施設", "陸上施設", "荷役施設", "ターミナル",
        "岸壁", "防波堤", "埠頭", "桟橋整備",
        "港湾計画", "港湾整備", "港湾局",
        "水素ステーション", "燃料供給施設", "バンカリング施設",
        "陸上電力供給", "陸電",
    ]
    # 会議・委員会・行政手続き系キーワード
    _ADMIN_KEYWORDS: list[str] = [
        "審議会", "委員会議事", "パブリックコメント募集",
        "意見募集", "会議開催", "議事録", "検討会",
        "人事異動", "組織改編", "予算案",
    ]

    for kw in _INFRASTRUCTURE_KEYWORDS:
        if kw in combined_text:
            # ただし船舶向けの記述も含む場合は AI に委譲
            _SHIP_OVERRIDE_KEYWORDS: list[str] = [
                "船舶", "船上", "搭載", "乗組員", "航行",
                "solas", "marpol", "stcw", "ism",
            ]
            if not any(_keyword_in_text(sk, combined_text) for sk in _SHIP_OVERRIDE_KEYWORDS):
                logger.debug(
                    f"[rule] not_applicable: インフラ/施設キーワード {kw!r} がヒット"
                )
                return "not_applicable"

    for kw in _ADMIN_KEYWORDS:
        if kw in combined_text:
            logger.debug(
                f"[rule] not_applicable: 行政/会議キーワード {kw!r} がヒット"
            )
            return "not_applicable"

    # いずれのフィルタにも引っかからなかった → AI に委譲
    logger.debug("[rule] needs_ai: ルールベースで除外できず")
    return "needs_ai"


# ---------------------------------------------------------------------------
# Stage 0: 条約ベースマッチング
# ---------------------------------------------------------------------------

def _passes_exclusion_check(conv_id: str, matched_keywords: list[str], reg_text: str) -> bool:
    """
    排他ルールを適用して、条約マッチが十分な証拠に基づくか検証する。

    Args:
        conv_id: 条約ルールの ID (例: "STCW", "SOLAS_CH_II1_STRUCTURE")
        matched_keywords: マッチしたキーワードのリスト
        reg_text: 規制のテキスト（小文字化済み）

    Returns:
        True — マッチは有効
        False — 排他ルールにより不十分と判定
    """
    exclusion = KEYWORD_EXCLUSIONS.get(conv_id)
    if exclusion is None:
        # 排他ルールなし → 1個でもマッチすれば OK
        return True

    min_matches = exclusion.get("min_keyword_matches", 1)
    required_any = exclusion.get("required_any", [])
    insufficient = exclusion.get("single_keyword_insufficient", [])

    # チェック 1: 最低マッチ数
    if len(matched_keywords) < min_matches:
        # ただし required_any のアンカーキーワードがあれば 1 個でも OK
        has_anchor = any(
            _keyword_in_text(anchor, reg_text) for anchor in required_any
        )
        if not has_anchor:
            logger.debug(
                f"[exclusion] {conv_id}: マッチ数 {len(matched_keywords)} < "
                f"min {min_matches}、アンカーなし → 除外"
            )
            return False

    # チェック 2: single_keyword_insufficient に該当するキーワードのみの場合
    if insufficient and matched_keywords:
        all_insufficient = all(
            kw.lower() in [s.lower() for s in insufficient]
            for kw in matched_keywords
        )
        if all_insufficient:
            # アンカーキーワードが 1 つでもあれば救済
            has_anchor = any(
                _keyword_in_text(anchor, reg_text) for anchor in required_any
            )
            if not has_anchor:
                logger.debug(
                    f"[exclusion] {conv_id}: マッチしたキーワード "
                    f"{matched_keywords} は全て insufficient リスト内 → 除外"
                )
                return False

    return True


def _convention_match(regulation: dict, compliance: list[dict]) -> dict | None:
    """
    規制のタイトル/サマリーと、船に適用される条約のキーワードを照合。
    マッチすれば条約ベースの判定結果を返す。マッチしなければ None。
    排他ルール (KEYWORD_EXCLUSIONS) を適用して cross-contamination を防止。
    """
    reg_text = (
        f"{regulation.get('title', '')} "
        f"{regulation.get('summary_ja', '')} "
        f"{regulation.get('category', '')}"
    ).lower()

    matched: list[dict] = []
    for conv in compliance:
        if conv["status"] == "not_applicable":
            continue

        # このコンベンションでマッチしたキーワードを全て収集
        conv_matched_kws: list[str] = []
        for kw in conv.get("keywords", []):
            if _keyword_in_text(kw, reg_text):
                conv_matched_kws.append(kw)

        if not conv_matched_kws:
            continue

        # 排他ルールチェック
        conv_id = conv.get("convention_id", "")
        if not _passes_exclusion_check(conv_id, conv_matched_kws, reg_text):
            logger.info(
                f"[Stage0] {conv_id} は排他ルールにより除外 "
                f"(マッチ: {conv_matched_kws})"
            )
            continue

        matched.append(conv)

    if not matched:
        return None

    # Best match (prefer "applicable" over "potential")
    applicable = [m for m in matched if m["status"] == "applicable"]
    potential = [m for m in matched if m["status"] == "potential"]

    if applicable:
        best = applicable[0]
        logger.info(
            f"[Stage0] convention_based: {best['convention']} {best.get('chapter', '')} "
            f"— {len(matched)} 条約マッチ"
        )
        return {
            "is_applicable": True,
            "match_method": "convention_based",
            "confidence": 0.95,
            "reason": f"{best['convention']} {best.get('chapter', '')} 適用船 — {best['reason']}",
            "conventions": [m.get("convention_id", "") for m in matched],
            "actions": best.get("typical_actions", []),
            "national_laws": best.get("national_laws", []),
            "certificates": best.get("certificates", []),
            "needs_review": False,
            "citations": None,
        }
    elif potential:
        best = potential[0]
        logger.info(
            f"[Stage0] potential_match: {best['convention']} — 要確認"
        )
        return {
            "is_applicable": None,  # Unknown — needs user confirmation
            "match_method": "potential_match",
            "confidence": 0.5,
            "reason": f"該当の可能性あり — {best.get('user_prompt', '')}",
            "conventions": [m.get("convention_id", "") for m in matched],
            "actions": [],
            "national_laws": [],
            "certificates": [],
            "needs_review": True,
            "citations": None,
        }

    return None


# ---------------------------------------------------------------------------
# Stage 2: AI マッチング（Gemini）
# ---------------------------------------------------------------------------

def _build_matching_prompt(
    regulation: dict,
    ship: dict,
    compliance: list[dict] | None = None,
) -> str:
    """
    Gemini に送るマッチング判定プロンプトを構築する。
    PDF なしのテキストのみで判定させる（classify_pdf とは異なる）。
    compliance が渡された場合は条約コンテキストを追加する。
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
        f"適用船種: {', '.join(regulation.get('applicable_ship_types') or []) or '未指定（※未指定＝全船適用ではない。規制内容から判断すること）'}\n"
        f"GT 下限: {regulation.get('applicable_gt_min') or '未指定'}\n"
        f"GT 上限: {regulation.get('applicable_gt_max') or '未指定'}\n"
        f"建造年以降適用: {regulation.get('applicable_built_after') or '未指定'}\n"
        f"適用航路: {', '.join(regulation.get('applicable_routes') or []) or '未指定'}\n"
        f"適用旗国: {', '.join(regulation.get('applicable_flags') or []) or '未指定'}\n"
        f"根拠引用: {json.dumps(regulation.get('citations') or [], ensure_ascii=False)}"
    )

    prompt = f"""あなたは海事規制の専門家です。以下の「自船スペック」と「規制情報」を照合し、
この規制が **当該船舶の運航・設備・乗組員に直接影響するか** を判定してください。

## 自船スペック
{ship_summary}

## 規制情報
{regulation_summary}

## 判定の核心原則（最重要 — 必ず守ること）

### 原則1: 「制限なし」≠「適用」
規制の適用船種・GT・建造年・航路・旗国が「制限なし」であっても、それだけで適用とは判断しない。
規制の **内容** が船舶の運航・設備・乗組員・航行安全に **積極的に関係している** 場合のみ is_applicable: true とする。

### 原則2: 規制の「対象者」を見極める
以下は **船舶オペレーターには非適用**（is_applicable: false）とする:
- **港湾施設・陸上インフラ** に関するガイドライン（水素/アンモニア供給施設、ターミナル設計、岸壁設備など）
- **港湾管理者・行政機関** が対象の通達（港湾計画、施設基準、行政手続き）
- **造船所・メーカー** 向けの技術基準（新造船設計基準であっても、既存船への改修義務がない場合）
- **会議・審議会・検討会** の開催案内、議事録、パブリックコメント募集
- **一般的な情報提供・啓発資料**（業界動向レポート、統計情報）

### 原則3: 船舶に適用される規制の特徴
以下のいずれかに該当する場合のみ is_applicable: true を検討する:
- SOLAS, MARPOL, STCW, ISM コード等の **国際条約改正** で、船舶に義務が生じるもの
- **船級規則** の改正（NK, LR, BV 等）で、検査・証書に影響するもの
- **旗国（船籍国）法令** の改正で、船舶の設備・運航に要件が変わるもの
- **寄港国検査（PSC）** に関する新基準・重点検査項目
- 特定海域での **航行制限・報告義務**（ECA, ECDIS 要件, 通航規制など）
- **乗組員** の資格・訓練・安全に関する要件変更

## 適用/非適用の具体例

### 適用される例 (is_applicable: true)
- 「MARPOL Annex VI 改正: 2025年以降、GT 400以上の国際航行船舶にCII格付け義務」→ バルクキャリア GT 5000 → **適用**
- 「SOLAS II-2 改正: 全旅客船に新型火災検知器の搭載を義務化」→ 旅客船 → **適用**
- 「東京湾における大型船舶の航行ルール変更」→ 東京湾を航行する船 → **適用**

### 非適用の例 (is_applicable: false)
- 「港湾における水素・アンモニア燃料供給施設の安全ガイドライン」→ バルクキャリア → **非適用**（施設管理者向け）
- 「港湾施設の耐震基準改定」→ 全船舶 → **非適用**（港湾管理者向け）
- 「第XX回海上安全委員会（MSC）開催案内」→ 全船舶 → **非適用**（会議案内）
- 「LNG燃料船の設計ガイドライン」→ 通常燃料のバルクキャリア → **非適用**（対象船種外）
- 「海事産業の脱炭素ロードマップ」→ 全船舶 → **非適用**（啓発資料、義務なし）

## confidence の付け方
- 0.85〜1.0: 規制文に船種/GT/旗国等の明示的な適用範囲があり、自船が該当
- 0.65〜0.84: 船舶運航に関係するが、適用範囲の記述があいまい
- 0.40〜0.64: 関係する可能性はあるが情報不足（needs_review になる）
- 0.0〜0.39: ほぼ無関係または対象外

## 対応事項の分類（必須）
規制への対応が必要な場合、以下の2カテゴリに分けて具体的な対応事項を列挙してください:

"onboard_actions": 船上で実施する対応（訓練実施、点検記録、ポスター掲示、乗組員周知、操練等）
"shore_actions": 陸上（管理会社側）で実施する対応（SMS改訂、機材調達、図面承認、証書書換、船級検査手配等）

## SMS章番号の推論（SMSに関連する場合のみ）
ISMコードに基づくSMS（安全管理マニュアル）の改訂が必要な場合、関連するSMS章番号を特定してください:
- 第6章: 資源及び人員（訓練・資格関連）
- 第7章: 船上作業の計画の策定（作業手順・閉囲区画立入等）
- 第8章: 緊急事態への準備（非常訓練・退船等）
- 第9章: 不適合の報告と分析
- 第10章: 船舶及び設備の保守整備
- 第11章: 文書管理
"sms_chapters": ["7"] のように番号のリストで返してください。

## 強制適用日
"effective_date": 規制の強制適用日（Entry into Force）がわかる場合は "YYYY-MM-DD" 形式で。不明なら null。

## 出力フォーマット（必須）
以下の JSON 形式で出力してください。コードブロック (```json ... ```) に包んでください。
過去の学習知識のみで判断せず、上記の規制情報テキストを根拠にしてください。

```json
{{
  "is_applicable": <true | false>,
  "confidence": <0.0〜1.0 の数値>,
  "reason": "<適用/非適用の理由を日本語で 100 字以内。例: GT 500 以上の国際航行船舶に適用（本船 GT 2,800）>",
  "onboard_actions": ["<船上対応1>", "<船上対応2>"],
  "shore_actions": ["<陸上対応1>", "<陸上対応2>"],
  "sms_chapters": ["<章番号>"],
  "effective_date": "<YYYY-MM-DD or null>",
  "citations": [
    {{
      "text": "<根拠となる規制文の抜粋>",
      "source": "<文書識別子>"
    }}
  ]
}}
```

"""
    # 条約コンテキストを追加（Stage 0 で判定不能だった場合の AI 補助情報）
    if compliance:
        applicable_convs = [c for c in compliance if c["status"] == "applicable"]
        if applicable_convs:
            prompt += "\n\n## この船に適用される条約・法令:\n"
            for c in applicable_convs:
                prompt += f"- {c['convention']} {c.get('chapter', '')}: {c.get('description', '')}\n"
                if c.get("national_laws"):
                    prompt += f"  関連国内法: {', '.join(c['national_laws'])}\n"
            prompt += "\n上記の条約に関連する規制であれば「該当」と判定してください。\n"

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


def _verify_matching_result(
    regulation: dict,
    ship: dict,
    initial_result: dict,
) -> dict:
    """
    Chain of Verification (CoVe) — 低確信度の結果を検証して精度を向上させる。
    confidence 0.4-0.84 の結果のみ対象。それ以外はそのまま返す。
    """
    confidence = initial_result.get("confidence", 0.0)

    # 高確信度 (>= 0.85) または極低確信度 (< 0.4) はスキップ
    if confidence >= 0.85 or confidence < 0.4:
        return initial_result

    logger.info(f"[CoVe] 検証開始: confidence={confidence:.2f}")

    # Step 1: 検証質問を生成
    reason = initial_result.get("reason", "")
    is_applicable = initial_result.get("is_applicable")
    reg_title = regulation.get("title", "")
    ship_type = ship.get("ship_type", "")
    gt = ship.get("gross_tonnage", "不明")

    verification_prompt = f"""以下のAI判定結果を検証してください。

判定対象:
- 規制: {reg_title}
- 船舶: {ship_type}, GT {gt}
- 判定: {"該当" if is_applicable else "非該当"}
- 理由: {reason}

以下の3つの検証質問に、規制の内容のみに基づいて簡潔に回答してください:

1. この規制は本当に{ship_type}（総トン数{gt}GT）に適用されるか？適用条件を引用せよ。
2. 判定理由に記載されたGT閾値や船種条件は、規制文書に実際に記載されているか？
3. この規制への対応として挙げられた事項は、規制の内容と矛盾していないか？

JSON形式で回答:
```json
{{
  "q1_answer": "回答",
  "q1_verified": true/false,
  "q2_answer": "回答",
  "q2_verified": true/false,
  "q3_answer": "回答",
  "q3_verified": true/false,
  "corrected_applicable": true/false/null,
  "corrected_confidence": 0.0-1.0,
  "correction_reason": "修正理由（修正がない場合は空文字）"
}}
```"""

    # Step 2: Gemini に検証を依頼
    api_key = os.environ.get("GEMINI_API_KEY", "")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    success, text = _call_gemini_text(model, api_key, verification_prompt)
    if not success:
        logger.warning(f"[CoVe] 検証API呼び出し失敗: {text[:100]}")
        return initial_result

    # Step 3: 検証結果をパース
    verification = _parse_json_response(text)
    if not verification:
        logger.warning("[CoVe] 検証結果のパース失敗")
        return initial_result

    # Step 4: 検証結果に基づいて修正
    verified_count = sum(1 for k in ["q1_verified", "q2_verified", "q3_verified"] if verification.get(k, False))

    logger.info(f"[CoVe] 検証結果: {verified_count}/3 verified")

    if verified_count >= 2:
        # 2/3以上検証成功 → 元の結果を信頼、ただし confidence を少し上げる
        result = initial_result.copy()
        result["confidence"] = min(1.0, confidence + 0.1)
        logger.info(f"[CoVe] 検証パス: confidence {confidence:.2f} → {result['confidence']:.2f}")
        return result
    else:
        # 検証失敗 → 修正結果を採用
        corrected_applicable = verification.get("corrected_applicable")
        corrected_confidence = verification.get("corrected_confidence", confidence * 0.5)
        correction_reason = verification.get("correction_reason", "")

        result = initial_result.copy()
        if corrected_applicable is not None:
            result["is_applicable"] = corrected_applicable
        result["confidence"] = max(0.0, min(1.0, float(corrected_confidence)))
        if correction_reason:
            result["reason"] = f"{result['reason']} [CoVe修正: {correction_reason}]"
        result["needs_review"] = True

        logger.info(
            f"[CoVe] 修正適用: applicable={corrected_applicable}, "
            f"confidence={result['confidence']:.2f}, reason={correction_reason[:50]}"
        )
        return result


# ---------------------------------------------------------------------------
# Stage 2: applicability_rules 評価（API不要）
# ---------------------------------------------------------------------------

def _not_applicable_result(reason: str) -> dict:
    """applicability_rules 評価で非適用と判定された場合の結果 dict を返す。"""
    return {
        "is_applicable": False,
        "match_method": "rule_evaluated",
        "confidence": 0.95,
        "reason": reason,
        "conventions": [],
        "actions": [],
        "national_laws": [],
        "certificates": [],
        "onboard_actions": [],
        "shore_actions": [],
        "sms_chapters": [],
        "effective_date": None,
        "citations": [],
        "needs_review": False,
    }


def evaluate_applicability_rules(regulation: dict, ship: dict) -> dict | None:
    """
    regulation の applicability_rules JSON を船舶スペックと照合し、
    適用/非適用を判定する。Gemini API は呼ばない。

    Args:
        regulation: regulations テーブルの行 dict（applicability_rules JSONB を含む）
        ship:       ship_profiles テーブルの行 dict

    Returns:
        判定結果 dict、または applicability_rules がない場合は None
    """
    rules = regulation.get("applicability_rules")
    if not rules or not isinstance(rules, dict):
        return None  # ルールなし → Stage 2 判定不能

    # 船舶向けでない規制は即非適用
    if rules.get("is_ship_regulation") is False:
        return _not_applicable_result(
            f"この規制は{rules.get('target_audience', '不明')}向けであり、船舶オペレーター向けではありません"
        )

    ship_type = ship.get("ship_type", "")
    gt = ship.get("gross_tonnage", 0)
    nav = ship.get("navigation_area") or []
    flag = ship.get("flag_state", "")
    build_year = ship.get("build_year", 0)
    radio = ship.get("radio_equipment") or []

    # 船種チェック（除外リスト）
    excluded = rules.get("excluded_types") or []
    if excluded and ship_type in excluded:
        return _not_applicable_result(f"船種 {ship_type} は除外対象")

    # 船種チェック（適用リスト）
    rule_types = rules.get("ship_types") or []
    if rule_types and ship_type not in rule_types:
        return _not_applicable_result(
            f"船種 {ship_type} は適用対象外 (対象: {rule_types})"
        )

    # GT チェック
    gt_min = rules.get("gt_min")
    gt_max = rules.get("gt_max")
    if gt_min is not None and gt is not None and gt < gt_min:
        return _not_applicable_result(f"GT {gt} < 下限 {gt_min}")
    if gt_max is not None and gt is not None and gt > gt_max:
        return _not_applicable_result(f"GT {gt} > 上限 {gt_max}")

    # 航行区域チェック
    rule_nav = rules.get("navigation") or []
    if rule_nav and nav:
        if not set(rule_nav) & set(nav):
            return _not_applicable_result(
                f"航行区域 {nav} は適用対象外 (対象: {rule_nav})"
            )

    # 旗国チェック
    rule_flag = rules.get("flag_state")
    if rule_flag and flag and flag != rule_flag:
        return _not_applicable_result(
            f"旗国 {flag} は適用対象外 (対象: {rule_flag})"
        )

    # 建造年チェック
    build_after = rules.get("build_year_after")
    build_before = rules.get("build_year_before")
    if build_after and build_year and build_year < build_after:
        return _not_applicable_result(f"建造年 {build_year} < {build_after}")
    if build_before and build_year and build_year > build_before:
        return _not_applicable_result(f"建造年 {build_year} > {build_before}")

    # 無線設備チェック
    rule_radio = rules.get("radio_equipment") or []
    if rule_radio and not set(rule_radio) & set(radio):
        return _not_applicable_result(f"必要な無線設備 {rule_radio} が未搭載")

    # 全条件クリア → 適用
    conventions = rules.get("conventions") or []
    reason_parts = []
    if rule_types:
        reason_parts.append(f"船種 {ship_type} が適用対象")
    if gt_min:
        reason_parts.append(f"GT {gt} ≥ {gt_min}")
    if conventions:
        reason_parts.append(f"関連条約: {', '.join(conventions)}")

    return {
        "is_applicable": True,
        "match_method": "rule_evaluated",
        "confidence": 0.90,
        "reason": "。".join(reason_parts) if reason_parts else "適用条件に合致",
        "conventions": conventions,
        "actions": [],
        "national_laws": [],
        "certificates": [],
        "onboard_actions": regulation.get("onboard_actions") or [],
        "shore_actions": regulation.get("shore_actions") or [],
        "sms_chapters": regulation.get("sms_chapters") or [],
        "effective_date": None,
        "citations": [],
        "needs_review": False,
    }


# ---------------------------------------------------------------------------
# Stage 3: AI マッチング（Gemini） — フォールバック
# ---------------------------------------------------------------------------

def ai_match(
    regulation: dict,
    ship: dict,
    compliance: list[dict] | None = None,
) -> dict:
    """
    Gemini に規制の要約・引用と船舶スペックを送り、適用/非適用を判定させる。

    Args:
        regulation:  regulations テーブルの行 dict（summary_ja, citations 等を含む）
        ship:        ship_profiles テーブルの行 dict
        compliance:  determine_compliance() の結果（条約コンテキスト追加用）

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
            "onboard_actions": [],
            "shore_actions": [],
            "sms_chapters": [],
            "effective_date": None,
            "citations": [],
        }

    primary_model = os.environ.get("GEMINI_MODEL", _DEFAULT_PRIMARY_MODEL)
    fallback_model = os.environ.get("GEMINI_FALLBACK_MODEL", _DEFAULT_FALLBACK_MODEL)

    prompt = _build_matching_prompt(regulation, ship, compliance=compliance)
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

                parsed = validate_matching(parsed)  # Pydantic バリデーション

                is_applicable = parsed.get("is_applicable")
                confidence = float(parsed.get("confidence", 0.0))
                reason = parsed.get("reason", "")
                citations = parsed.get("citations") or []

                logger.info(
                    f"[AI] 判定完了 regulation={source_label} "
                    f"is_applicable={is_applicable} confidence={confidence:.2f}"
                )
                ai_result = {
                    "is_applicable": is_applicable,
                    "confidence": confidence,
                    "reason": reason,
                    "onboard_actions": parsed.get("onboard_actions", []),
                    "shore_actions": parsed.get("shore_actions", []),
                    "sms_chapters": parsed.get("sms_chapters", []),
                    "effective_date": parsed.get("effective_date"),
                    "citations": citations,
                }

                # CoVe verification for medium-confidence results
                ai_result = _verify_matching_result(regulation, ship, ai_result)

                return ai_result

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
        "onboard_actions": [],
        "shore_actions": [],
        "sms_chapters": [],
        "effective_date": None,
        "citations": [],
    }


# ---------------------------------------------------------------------------
# 統合関数: 条約ベース → ルールベース → AI の3段階マッチング
# ---------------------------------------------------------------------------

def match_regulation_to_ship(regulation: dict, ship: dict) -> dict:
    """
    規制と船舶プロファイルの3段階マッチングを実行する。

    Stage 1: rule_based_filter           — 高速除外（Gemini 不使用）
    Stage 0: _convention_match           — 条約ベースキーワード照合（高速・高精度）
    Stage 2: evaluate_applicability_rules — applicability_rules JSONB 評価（API不要）
    Stage 3: ai_match                    — Gemini による精密判定（フォールバック）

    Args:
        regulation: regulations テーブルの行 dict
        ship:       ship_profiles テーブルの行 dict

    Returns:
        {
            "is_applicable":  bool | None,  # None = AI 失敗で不明 or 要ユーザー確認
            "match_method":   str,          # 'convention_based' | 'potential_match' | 'rule_based' | 'ai_matching'
            "confidence":     float,        # 0.0〜1.0
            "reason":         str,
            "conventions":    list[str],    # マッチした条約 ID
            "actions":        list[dict],   # アクション項目
            "national_laws":  list[str],    # 関連国内法
            "certificates":   list[str],    # 関連証書
            "citations":      list | None,
            "needs_review":   bool,         # confidence < 0.7 の場合 True
        }
    """
    source_label = f"{regulation.get('source', '?')}/{regulation.get('source_id', '?')}"
    ship_label = f"{ship.get('ship_name', '?')} (GT {ship.get('gross_tonnage', '?')})"
    logger.info(f"マッチング開始: regulation={source_label} ship={ship_label}")

    # --- Stage 1: ルールベースフィルタ（最初に明確な非該当を除外）---
    rule_result = rule_based_filter(regulation, ship)

    if rule_result == "not_applicable":
        logger.info(f"[Stage1] not_applicable: regulation={source_label}")
        return {
            "is_applicable": False,
            "match_method": "rule_based",
            "confidence": 1.0,
            "reason": "船種・GT・建造年・航行区域・旗国のいずれかが適用範囲外",
            "conventions": [],
            "actions": [],
            "national_laws": [],
            "certificates": [],
            "citations": [],
            "needs_review": False,
        }

    # --- Stage 0: 条約ベースマッチング（ルールベースを通過したもの）---
    compliance: list[dict] = []
    try:
        compliance = determine_compliance(ship)
        convention_result = _convention_match(regulation, compliance)
        if convention_result:
            logger.info(
                f"[Stage0] 条約マッチ確定: regulation={source_label} "
                f"method={convention_result['match_method']}"
            )
            return convention_result
        logger.debug(f"[Stage0] 条約マッチなし — Stage 2 へフォールスルー")
    except Exception as e:
        logger.warning(f"[Stage0] 条約ベースマッチング例外（Stage 2 へフォールスルー）: {e}")

    if rule_result == "applicable":
        # 現在このパスは使用しないが、将来の拡張のために保持
        logger.info(f"[Stage1] applicable (rule): regulation={source_label}")
        return {
            "is_applicable": True,
            "match_method": "rule_based",
            "confidence": 1.0,
            "reason": "全適用条件を満たす",
            "conventions": [],
            "actions": [],
            "national_laws": [],
            "certificates": [],
            "citations": [],
            "needs_review": False,
        }

    # --- Stage 2: applicability_rules 評価（API不要） ---
    rules_result = evaluate_applicability_rules(regulation, ship)
    if rules_result is not None:
        logger.info(
            f"[Stage2] {rules_result['match_method']}: "
            f"is_applicable={rules_result['is_applicable']} regulation={source_label}"
        )
        return rules_result

    # --- Stage 3: Gemini AI フォールバック（applicability_rules がない場合のみ） ---
    logger.info(f"[Stage3] applicability_rules なし → Gemini AI フォールバック: regulation={source_label}")
    ai_result = ai_match(regulation, ship, compliance=compliance)

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
        "conventions": [],
        "actions": [],
        "national_laws": [],
        "certificates": [],
        "onboard_actions": ai_result.get("onboard_actions", []),
        "shore_actions": ai_result.get("shore_actions", []),
        "sms_chapters": ai_result.get("sms_chapters", []),
        "effective_date": ai_result.get("effective_date"),
        "citations": ai_result.get("citations") or [],
        "needs_review": needs_review,
    }
