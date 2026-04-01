"""
MLIT 規制データの全件エクスポート（リッチ版）
タイトル + 要約 + 適用条約 + 会社側対応 + 船側対応 + 引用・根拠
Gemini レビュー用に全記事を一覧出力する。
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def fetch_all(source: str = "MLIT") -> list[dict]:
    all_rows: list[dict] = []
    offset = 0
    while True:
        params: dict[str, str] = {
            "select": "id,source_id,source,title,headline,summary_ja,category,severity,"
                      "published_at,effective_date,url,pdf_url,"
                      "applicable_ship_types,applicable_gt_min,applicable_gt_max,"
                      "onboard_actions,shore_actions,sms_chapters,"
                      "citations,confidence,applicability_rules",
            "order": "published_at.desc.nullslast",
            "limit": "1000",
            "offset": str(offset),
        }
        if source:
            params["source"] = f"eq.{source}"

        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/regulations",
            params=params,
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


def format_list(items: list | None) -> str:
    if not items:
        return "なし"
    if isinstance(items, str):
        return items
    return ", ".join(str(x) for x in items)


def format_citations(citations: list | None) -> str:
    if not citations:
        return "なし"
    parts = []
    for c in citations:
        if isinstance(c, dict):
            text = c.get("text", "")
            source = c.get("source", "")
            if text:
                parts.append(f"「{text}」" + (f" ({source})" if source else ""))
        elif isinstance(c, str):
            parts.append(c)
    return " / ".join(parts) if parts else "なし"


def format_rules(rules: dict | None) -> str:
    if not rules:
        return "未抽出"
    parts = []
    convs = rules.get("conventions") or []
    if convs:
        parts.append(f"条約: {', '.join(convs)}")
    types = rules.get("ship_types") or []
    if types:
        parts.append(f"船種: {', '.join(types)}")
    gt_min = rules.get("gt_min")
    if gt_min:
        parts.append(f"GT≥{gt_min}")
    nav = rules.get("navigation") or []
    if nav:
        parts.append(f"航行区域: {', '.join(nav)}")
    target = rules.get("target_audience", "")
    if target:
        parts.append(f"対象: {target}")
    is_ship = rules.get("is_ship_regulation")
    if is_ship is False:
        parts.append("★船舶向けではない")
    return " | ".join(parts) if parts else "条件なし"


def main():
    source = os.environ.get("EXPORT_SOURCE", "MLIT")
    rows = fetch_all(source=source)
    print(f"# {source} 規制データ一覧（{len(rows)}件）\n")
    print("## Gemini レビュー用")
    print("以下の各記事について、航海士にとって本当に必要な情報かどうか検査してください。\n")
    print("**判定基準**: 「読んでも設備変更/マニュアル改訂/免状手続き変更がない → ノイズ」\n")
    print("**検査項目**: 適用条約・関連法令、会社側対応、船側対応が適切か\n")
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
        confidence = row.get("confidence")

        ship_types = row.get("applicable_ship_types")
        gt_min = row.get("applicable_gt_min")
        gt_max = row.get("applicable_gt_max")
        onboard = row.get("onboard_actions")
        shore = row.get("shore_actions")
        sms = row.get("sms_chapters")
        citations = row.get("citations")
        rules = row.get("applicability_rules")

        print(f"## {i}. [{severity}] {headline or title}")
        if headline and title != headline:
            print(f"原題: {title}")
        print(f"カテゴリ: {category} | 掲載日: {published[:10] if published and published != '日付不明' else '不明'}", end="")
        if effective:
            print(f" | 適用日: {effective[:10]}", end="")
        if confidence is not None:
            print(f" | 確度: {confidence:.0%}", end="")
        print(f" | ID: {source_id}")
        print()
        print(f"**要約**: {summary[:300]}")
        print()

        # 適用条件
        print(f"**適用条約・関連法令**: ", end="")
        if rules:
            print(format_rules(rules))
        else:
            parts = []
            if ship_types:
                parts.append(f"船種: {format_list(ship_types)}")
            if gt_min:
                parts.append(f"GT≥{gt_min}")
            if gt_max:
                parts.append(f"GT≤{gt_max}")
            print(", ".join(parts) if parts else "未指定")
        print()

        # 対応事項
        print(f"**船側対応**: {format_list(onboard)}")
        print(f"**会社側対応**: {format_list(shore)}")
        if sms:
            print(f"**SMS章**: {format_list(sms)}")
        print()

        # 引用・根拠
        print(f"**引用・根拠**: {format_citations(citations)}")
        print()
        print("---")
        print()


if __name__ == "__main__":
    main()
