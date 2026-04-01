"""
MLIT 規制データの全件エクスポート（タイトル + 要約）
Gemini レビュー用に全記事を一覧出力する。
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def fetch_all() -> list[dict]:
    all_rows: list[dict] = []
    offset = 0
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/regulations",
            params={
                "source": "eq.MLIT",
                "select": "id,source_id,title,headline,summary_ja,category,severity,published_at,effective_date,url,pdf_url",
                "order": "published_at.desc.nullslast",
                "limit": "1000",
                "offset": str(offset),
            },
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            break
        all_rows.extend(rows)
        offset += 1000
        if len(rows) < 1000:
            break
    return all_rows


def main():
    rows = fetch_all()
    print(f"# MLIT 規制データ一覧（{len(rows)}件）\n")
    print("Gemini レビュー用: 航海士にとって本当に必要な情報かどうか検査してください。\n")
    print("判定基準: 「読んでも設備変更/マニュアル改訂/免状手続き変更がない → ノイズ」\n")
    print("---\n")

    for i, row in enumerate(rows, 1):
        title = row.get("title") or "(タイトルなし)"
        headline = row.get("headline") or ""
        summary = row.get("summary_ja") or "(要約なし)"
        category = row.get("category") or ""
        severity = row.get("severity") or ""
        published = row.get("published_at") or "日付不明"
        effective = row.get("effective_date") or ""
        source_id = row.get("source_id") or ""

        print(f"## {i}. [{severity}] {headline or title}")
        if headline and title != headline:
            print(f"原題: {title}")
        print(f"カテゴリ: {category} | 掲載日: {published[:10] if published else '不明'}", end="")
        if effective:
            print(f" | 適用日: {effective[:10]}", end="")
        print(f" | ID: {source_id}")
        print(f"要約: {summary[:200]}")
        print()


if __name__ == "__main__":
    main()
