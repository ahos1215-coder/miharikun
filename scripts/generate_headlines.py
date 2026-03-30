"""
既存の regulations に Gemini で headline を一括生成するスクリプト
================================================================
headline カラムが NULL の全レコードに対して、
title + summary_ja から 20-30文字の短い見出しを生成する。

使い方:
    python generate_headlines.py              # 通常実行
    python generate_headlines.py --dry-run    # DB 書き込みなし
    python generate_headlines.py --limit 10   # 最大10件処理
"""

import argparse
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import requests

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logger = logging.getLogger("generate_headlines")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[Headline] %(levelname)s: %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Supabase / Gemini 設定
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MIN_INTERVAL = float(os.environ.get("GEMINI_MIN_INTERVAL", "0.5"))

_last_call: float = 0.0


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_regulations_without_headline(limit: int = 100) -> list[dict]:
    """headline が NULL の regulations を取得"""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/regulations",
        params={
            "select": "id,source,source_id,title,summary_ja,category",
            "headline": "is.null",
            "order": "created_at.desc",
            "limit": str(limit),
        },
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def generate_headline(title: str, summary: str, category: str) -> str | None:
    """Gemini でタイトルと要約から短い見出しを生成"""
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)

    prompt = f"""あなたはニュース編集者です。以下の海事規制の情報から、Yahoo!ニュースのような20〜30文字の見出しを作成してください。

ルール:
- 必ず20文字以上30文字以下にすること
- 具体的な内容がわかる見出しにすること（「海事条約」のような曖昧な表現は禁止）
- 見出しのテキストのみを1行で返すこと

良い例:
- 「閉囲区画の安全基準が大幅改正へ」(16文字)
- 「NOx排出規制がTier IIIに強化、対象船拡大」(20文字)
- 「シップリサイクル条約、キプロス批准で発効要件に近づく」(25文字)
- 「MARPOL附属書VI改正、2026年から新燃料基準適用」(24文字)

悪い例:
- 「海事条約」（曖昧すぎる）
- 「油」（短すぎる）
- 「造船業」（内容がわからない）

タイトル: {title}
要約: {summary or 'なし'}
カテゴリ: {category or 'なし'}

見出し（20-30文字）:"""

    try:
        url = f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        resp = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 100},
            },
            timeout=30,
        )
        _last_call = time.time()
        resp.raise_for_status()

        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        # 改行や余分な文字を除去
        text = text.split("\n")[0].strip().strip('"').strip("「」")
        if len(text) > 50:
            text = text[:47] + "..."
        return text

    except Exception as e:
        logger.error(f"Gemini エラー: {e}")
        return None


def update_headline(reg_id: str, headline: str) -> bool:
    """regulations テーブルの headline を更新"""
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/regulations",
        params={"id": f"eq.{reg_id}"},
        json={"headline": headline},
        headers={**_headers(), "Prefer": "return=minimal"},
        timeout=15,
    )
    return resp.status_code < 300


def main():
    parser = argparse.ArgumentParser(description="既存 regulations に headline を一括生成")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--force", action="store_true", help="既存 headline も再生成")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY or not GEMINI_API_KEY:
        logger.error("SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY が必要です")
        sys.exit(1)

    if args.force:
        logger.info(f"全 regulations を取得中 (force=true, limit={args.limit})...")
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/regulations",
            params={
                "select": "id,source,source_id,title,summary_ja,category",
                "order": "created_at.desc",
                "limit": str(args.limit),
            },
            headers=_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        regs = resp.json()
    else:
        logger.info(f"headline 未生成の regulations を取得中 (limit={args.limit})...")
        regs = fetch_regulations_without_headline(args.limit)
    logger.info(f"{len(regs)} 件の headline 未生成レコードを取得")

    if not regs:
        logger.info("全件 headline 生成済みです")
        return

    success = 0
    failed = 0

    for i, reg in enumerate(regs, 1):
        sid = reg.get("source_id", "?")
        title = reg.get("title", "")
        summary = reg.get("summary_ja", "")
        category = reg.get("category", "")

        logger.info(f"[{i}/{len(regs)}] {sid}: {title[:40]}...")

        headline = generate_headline(title, summary, category)
        if not headline:
            logger.warning(f"  headline 生成失敗: {sid}")
            failed += 1
            continue

        logger.info(f"  → {headline}")

        if not args.dry_run:
            if update_headline(reg["id"], headline):
                success += 1
            else:
                logger.error(f"  DB 更新失敗: {sid}")
                failed += 1
        else:
            success += 1

    logger.info("=" * 60)
    logger.info(f"  成功: {success}")
    logger.info(f"  失敗: {failed}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
