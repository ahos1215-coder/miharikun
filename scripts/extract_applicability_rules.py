"""
Gemini を使って regulations テーブルから適用条件 (applicability_rules) を抽出するバッチスクリプト。

処理フロー:
1. Supabase の regulations テーブルから対象レコードを取得
2. 既に applicability_rules が設定済みのものはスキップ（--force で再抽出）
3. Gemini API を1回/レコード呼び出して適用条件を構造化 JSON で抽出
4. 抽出結果を applicability_rules JSONB カラムに保存

使い方:
    python scripts/extract_applicability_rules.py
    python scripts/extract_applicability_rules.py --dry-run
    python scripts/extract_applicability_rules.py --force --limit 10
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import argparse
import json
import logging
import re
import time
from typing import Optional

import requests

try:
    from utils.gemini_config import (
        DEFAULT_PRIMARY_MODEL,
        GEMINI_API_BASE,
        GEMINI_API_KEY as _CFG_API_KEY,
        MAX_RETRIES as _CFG_MAX_RETRIES,
        MIN_REQUEST_INTERVAL,
        DEFAULT_TEMPERATURE,
    )
except ImportError:
    from gemini_config import (
        DEFAULT_PRIMARY_MODEL,
        GEMINI_API_BASE,
        GEMINI_API_KEY as _CFG_API_KEY,
        MAX_RETRIES as _CFG_MAX_RETRIES,
        MIN_REQUEST_INTERVAL,
        DEFAULT_TEMPERATURE,
    )

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 環境変数・定数（gemini_config から統一取得）
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
GEMINI_API_KEY = _CFG_API_KEY or os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", DEFAULT_PRIMARY_MODEL)

# レート制限: Tier 1 = 15 RPM → 最低 4 秒間隔
GEMINI_MIN_INTERVAL = float(os.environ.get("GEMINI_MIN_INTERVAL", "4.0")) or MIN_REQUEST_INTERVAL

# 指数バックオフ設定（このスクリプト固有: より保守的な設定）
MAX_RETRIES = 5
BASE_WAIT = 4.0
MAX_WAIT = 64.0

# ページネーション
PAGE_SIZE = 1000

# ---------------------------------------------------------------------------
# Gemini プロンプト
# ---------------------------------------------------------------------------

GEMINI_RULE_EXTRACTOR_PROMPT = """あなたは海事規制の専門家です。
以下の規制情報を分析し、この規制が「どの船舶に適用されるか」の条件を構造化JSONで抽出してください。

## 規制情報
タイトル: {title}
ソース: {source}
カテゴリ: {category}
要約: {summary_ja}
適用船種(既存): {applicable_ship_types}
GT下限(既存): {applicable_gt_min}
施行日: {effective_date}

## 抽出する条件

```json
{{
  "ship_types": ["bulk_carrier", "tanker", ...],
  "excluded_types": [],
  "gt_min": null,
  "gt_max": null,
  "navigation": ["international"],
  "flag_state": null,
  "conventions": ["SOLAS", "MARPOL"],
  "build_year_after": null,
  "build_year_before": null,
  "radio_equipment": [],
  "is_ship_regulation": true,
  "target_audience": "ship_operator"
}}
```

### フィールド説明
- ship_types: 適用される船種（空配列 = 全船種 or 船種制限なし）。値は "bulk_carrier", "tanker", "container", "general_cargo", "passenger", "ro_ro", "lpg_carrier", "lng_carrier", "chemical_tanker", "offshore", "fishing", "tug", "other" 等
- excluded_types: 除外船種
- gt_min: 最小GT（null = 制限なし）
- gt_max: 最大GT（null = 制限なし）
- navigation: 航行区域 "international", "coastal", "near_sea", "smooth_water"
- flag_state: 特定旗国（"JPN" 等、null = 全旗国）
- conventions: 関連する条約 SOLAS, MARPOL, STCW, ISM, ISPS, MLC, BWM, Hong_Kong 等
- build_year_after: 建造年下限（null = 制限なし）
- build_year_before: 建造年上限（null = 制限なし）
- radio_equipment: 必要な無線設備
- is_ship_regulation: これが船舶に適用される規制か（港湾施設向け等ならfalse）
- target_audience: "ship_operator" | "port_authority" | "shipyard" | "administration" | "general"

## 重要ルール
- 船舶オペレーター向けでない規制（港湾施設、行政、造船所向け）は is_ship_regulation: false とする
- 「全船適用」の場合は ship_types: [], gt_min: null とする
- 条約改正の場合は conventions に該当する条約名を入れる
- SOLAS, MARPOL, STCW, ISM, ISPS 等の主要条約を正確に特定する
- 不明な場合は null を使う（推測で値を入れない）

## 出力
```json で囲んでJSONのみを出力してください。
"""

# ---------------------------------------------------------------------------
# 必須フィールド（バリデーション用）
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = [
    "ship_types",
    "is_ship_regulation",
    "target_audience",
]

VALID_TARGET_AUDIENCES = {
    "ship_operator",
    "port_authority",
    "shipyard",
    "administration",
    "general",
}

# ---------------------------------------------------------------------------
# レートリミッター
# ---------------------------------------------------------------------------

_last_call_timestamp: float = 0.0


def _rate_limit_wait() -> None:
    """前回の API 呼び出しから GEMINI_MIN_INTERVAL 秒経過するまで待機する。"""
    global _last_call_timestamp
    if _last_call_timestamp > 0:
        elapsed = time.time() - _last_call_timestamp
        remaining = GEMINI_MIN_INTERVAL - elapsed
        if remaining > 0:
            logger.debug(f"レートリミット待機: {remaining:.1f}s")
            time.sleep(remaining)
    _last_call_timestamp = time.time()


def _exponential_backoff(attempt: int) -> float:
    """指数バックオフの待機秒数を計算する。attempt は 0 始まり。"""
    wait = BASE_WAIT * (2 ** attempt)
    return min(wait, MAX_WAIT)


# ---------------------------------------------------------------------------
# Supabase ヘルパー
# ---------------------------------------------------------------------------

def _supabase_headers() -> dict[str, str]:
    """Supabase REST API の共通ヘッダー"""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_regulations(force: bool = False) -> list[dict]:
    """
    regulations テーブルから対象レコードを全件取得する。
    force=False の場合、applicability_rules が null のもののみ取得。
    ページネーション（PAGE_SIZE 件ずつ）で全件取得する。
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL または SUPABASE_SERVICE_ROLE_KEY が未設定です")
        return []

    all_rows: list[dict] = []
    offset = 0

    while True:
        params: dict[str, str] = {
            "select": "id,title,source,category,summary_ja,applicable_ship_types,applicable_gt_min,effective_date,applicability_rules",
            "order": "created_at.asc",
            "offset": str(offset),
            "limit": str(PAGE_SIZE),
        }

        # force でなければ applicability_rules が null のもののみ
        if not force:
            params["applicability_rules"] = "is.null"

        try:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/regulations",
                params=params,
                headers={
                    **_supabase_headers(),
                    "Prefer": "count=exact",
                },
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"regulations 取得失敗 (offset={offset}): {e}")
            break

        rows = resp.json()
        if not rows:
            break

        all_rows.extend(rows)
        logger.info(f"取得済み: {len(all_rows)} 件 (このページ: {len(rows)} 件)")

        if len(rows) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    logger.info(f"対象レコード合計: {len(all_rows)} 件")
    return all_rows


# ---------------------------------------------------------------------------
# Gemini API 呼び出し
# ---------------------------------------------------------------------------

def _parse_gemini_json(text: str) -> Optional[dict]:
    """
    Gemini のレスポンステキストから JSON ブロックを抽出して dict を返す。
    パース失敗時は None を返す。
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
            logger.warning("JSON ブロックが見つかりません")
            return None

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON パースエラー: {e}")
        return None


def _validate_rules(rules: dict) -> bool:
    """抽出結果のバリデーション。必須フィールドが存在するか確認。"""
    for field in REQUIRED_FIELDS:
        if field not in rules:
            logger.warning(f"必須フィールド '{field}' が欠落しています")
            return False

    # target_audience の値チェック
    if rules.get("target_audience") not in VALID_TARGET_AUDIENCES:
        logger.warning(
            f"target_audience の値が不正: {rules.get('target_audience')}"
        )
        return False

    # ship_types は配列であるべき
    if not isinstance(rules.get("ship_types"), list):
        logger.warning("ship_types が配列ではありません")
        return False

    # is_ship_regulation は bool であるべき
    if not isinstance(rules.get("is_ship_regulation"), bool):
        logger.warning("is_ship_regulation が bool ではありません")
        return False

    return True


def extract_rules(regulation: dict) -> Optional[dict]:
    """
    Gemini API を1回呼び出して applicability_rules を抽出する。
    指数バックオフ + 429 対応。
    成功時は dict、失敗時は None を返す。
    """
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY が未設定です")
        return None

    # プロンプトを構築
    prompt = GEMINI_RULE_EXTRACTOR_PROMPT.format(
        title=regulation.get("title", ""),
        source=regulation.get("source", ""),
        category=regulation.get("category", ""),
        summary_ja=regulation.get("summary_ja", ""),
        applicable_ship_types=regulation.get("applicable_ship_types", ""),
        applicable_gt_min=regulation.get("applicable_gt_min", ""),
        effective_date=regulation.get("effective_date", ""),
    )

    url = f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "temperature": DEFAULT_TEMPERATURE,
        },
    }

    last_error = ""
    for attempt in range(MAX_RETRIES):
        _rate_limit_wait()

        try:
            resp = requests.post(url, json=payload, timeout=60)
        except requests.RequestException as e:
            last_error = f"HTTPリクエスト例外: {e}"
            logger.warning(f"リクエストエラー (attempt {attempt + 1}): {last_error}")
            wait = _exponential_backoff(attempt)
            time.sleep(wait)
            continue

        if resp.status_code == 200:
            try:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                logger.warning(f"レスポンスパースエラー: {e}")
                return None

            rules = _parse_gemini_json(text)
            if rules is None:
                logger.warning("JSON 抽出失敗")
                return None

            if not _validate_rules(rules):
                logger.warning("バリデーション失敗、結果をスキップ")
                return None

            return rules

        elif resp.status_code in (429, 500, 502, 503, 504):
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            wait = _exponential_backoff(attempt)
            logger.warning(
                f"リトライ {attempt + 1}/{MAX_RETRIES} wait={wait:.1f}s: {last_error}"
            )
            time.sleep(wait)
        else:
            # リトライ不可のエラー（400, 401, 403 等）
            logger.error(f"リトライ不可エラー HTTP {resp.status_code}: {resp.text[:200]}")
            return None

    logger.error(f"全リトライ失敗: {last_error}")
    return None


# ---------------------------------------------------------------------------
# DB 保存
# ---------------------------------------------------------------------------

def save_rules(reg_id: str, rules: dict, dry_run: bool = False) -> bool:
    """
    regulations テーブルの applicability_rules を更新する。
    dry_run=True の場合は実際には更新しない。
    """
    if dry_run:
        logger.info(f"[DRY-RUN] id={reg_id} の applicability_rules を更新（スキップ）")
        return True

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL または SUPABASE_SERVICE_ROLE_KEY が未設定です")
        return False

    try:
        resp = requests.patch(
            f"{SUPABASE_URL}/rest/v1/regulations",
            params={"id": f"eq.{reg_id}"},
            json={"applicability_rules": rules},
            headers=_supabase_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        logger.info(f"保存成功: id={reg_id}")
        return True
    except requests.RequestException as e:
        logger.error(f"保存失敗: id={reg_id}: {e}")
        return False


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gemini を使って regulations の applicability_rules を抽出・保存する"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gemini 呼び出しと JSON 抽出は行うが、DB への保存はスキップする",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="既に applicability_rules が設定されているレコードも再抽出する",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="処理件数の上限（デバッグ・テスト用）",
    )
    args = parser.parse_args()

    logger.info("=== extract_applicability_rules 開始 ===")
    logger.info(f"  dry_run={args.dry_run}, force={args.force}, limit={args.limit}")
    logger.info(f"  model={GEMINI_MODEL}, interval={GEMINI_MIN_INTERVAL}s")

    # 環境変数チェック
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if missing:
        logger.error(f"必須環境変数が未設定: {', '.join(missing)}")
        sys.exit(1)

    # 対象レコードを取得
    regulations = fetch_regulations(force=args.force)
    if not regulations:
        logger.info("処理対象のレコードがありません。終了します。")
        return

    # limit 適用
    if args.limit is not None and args.limit > 0:
        regulations = regulations[: args.limit]
        logger.info(f"--limit={args.limit} 適用後: {len(regulations)} 件")

    # 処理開始
    total = len(regulations)
    success_count = 0
    skip_count = 0
    fail_count = 0

    logger.info(f"処理開始: {total} 件（推定所要時間: {total * GEMINI_MIN_INTERVAL / 60:.1f} 分）")

    for i, reg in enumerate(regulations, 1):
        reg_id = reg.get("id", "?")
        title = reg.get("title", "（タイトルなし）")
        logger.info(f"[{i}/{total}] id={reg_id}: {title[:60]}")

        # Gemini で抽出
        rules = extract_rules(reg)

        if rules is None:
            fail_count += 1
            logger.warning(f"  -> 抽出失敗: id={reg_id}")
            continue

        # ログ出力（主要フィールド）
        logger.info(
            f"  -> 抽出成功: is_ship={rules.get('is_ship_regulation')}, "
            f"target={rules.get('target_audience')}, "
            f"types={rules.get('ship_types')}, "
            f"conventions={rules.get('conventions')}"
        )

        # DB に保存
        if save_rules(reg_id, rules, dry_run=args.dry_run):
            success_count += 1
        else:
            fail_count += 1

    # サマリー
    logger.info("=== 処理完了 ===")
    logger.info(f"  合計: {total} 件")
    logger.info(f"  成功: {success_count} 件")
    logger.info(f"  失敗: {fail_count} 件")
    logger.info(f"  スキップ: {skip_count} 件")

    if fail_count > 0:
        logger.warning(f"失敗が {fail_count} 件あります。ログを確認してください。")


if __name__ == "__main__":
    main()
