"""
既存ノイズデータの一括清掃
===========================
「航海士が読んでも、設備を変える必要も、マニュアルを改訂する必要も、
免状の手続きが変わることもない情報」を regulations テーブルから削除する。

ノイズの定義:
  - 旅客船・遊覧船の事故対策検討会
  - 造船・舶用工業の産業政策
  - 港湾施設・インフラ整備
  - 審議会・検討会・議事録
  - 統計・調査報告
  - 一般啓発・広報（海の日等）
  - 漁船・プレジャーボート専用の規制

使い方:
  python cleanup_noise.py --dry-run   # 削除対象の確認のみ
  python cleanup_noise.py             # 実際に削除
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import argparse
import logging
from typing import Optional

import requests

from utils.supabase_client import SupabaseClient  # type: ignore

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cleanup_noise")

# ---------------------------------------------------------------------------
# ノイズパターン（タイトルまたは要約に含まれる文字列）
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ノイズ判定: 「アクション性テスト」
# 以下のいずれかを行う必要があるか？
#   1. 設備の換装  2. 書類の更新  3. 免状の手続き  4. SMSの変更
# いずれにも該当しない → ノイズ
# ---------------------------------------------------------------------------

# タイトルまたは要約に含まれればノイズと判定（単独条件）
NOISE_KEYWORDS_SINGLE: list[str] = [
    # 旅客船・遊覧船の事故対策
    "旅客船安全対策",
    "知床遊覧船",
    "遊覧船事故",
    "小型旅客船の安全",
    "観光船事故",
    # 造船・舶用工業・産業政策
    "造船業の再生",
    "造船・舶用工業",
    "舶用工業の振興",
    "造船所の生産性",
    "造船業の経営",
    "環境対応船の建造",
    "海事産業の現状",
    "海事産業の基盤強化",
    "三菱造船",
    "大島造船所",
    "Wind Challenger",
    # 港湾施設・インフラ
    "港湾建設",
    "岸壁整備",
    "しゅんせつ",
    "防波堤",
    "港湾施設の耐震",
    "ターミナル設計",
    "水素ステーション",
    "アンモニア燃料供給",
    "陸上電力供給",
    "バンカリング施設",
    "港湾の施設の新しい点検",
    "港湾インフラ",
    "港湾統計",
    "港湾工事",
    "港湾局",
    "港湾を核",
    "サーキュラーエコノミーポート",
    "遠隔操作等荷役機械",
    "荷役機械の安全確保",
    # 審議会・検討会・議事録・行政手続き・参加者リスト
    "審議会開催",
    "検討委員会",
    "検討会の開催",
    "委員会議事",
    "議事録",
    "議事次第",
    "議事要旨",
    "パブリックコメント募集結果",
    "意見募集の結果",
    "人事異動",
    "組織改編",
    "参加者リスト",
    "参考資料1",
    "関係者の氏名",
    "プロジェクトマネージャー",
    # GHGゼロエミッション検討会・ロードマップ（航海士個人にアクション不要）
    "GHGゼロエミッション",
    "GHGゼロエミッション プロジェクト",
    "ゼロエミッションプロジェクト",
    "ゼロエミッション・プロジェクト",
    "ロードマップ作成事業",
    "活動方針案",
    "検討体制案",
    "検討状況",
    "タスクフォース",
    # 統計・調査・レポート
    "海事レポート",
    "船員数統計",
    "海運統計",
    "交通統計",
    "海事産業調査",
    "実態調査の結果",
    "速報値",
    "統計速報",
    # 一般啓発・広報
    "海の日",
    "海事教育",
    "海事アワード",
    "海事週間",
    "海事観光",
    "海洋教育",
    "海の恩恵",
    # 非海事関連（RSS由来のノイズ）
    "非海事関連",
    "海事関連ではな",
    "海事関連文書ではない",
    "海事関連の規制ではありません",
    "チャイルドシート",
    "事業用自動車",
    "空港における保安検査",
    "河川管理",
    "特定都市河川",
    "航空安全情報",
    "航空運送分野",
    # 他業種（漁船・プレジャーボート等）
    "プレジャーボート",
    "遊漁船",
    "漁船の登録",
    "小型船舶操縦免許",
    "ボート免許",
    "モーターボート競走",
    "帆船模型",
    # 予算・入札
    "予算概算要求",
    "入札公告",
    "補助金交付",
    "決算報告",
]

# AND条件: 2つのキーワードが両方含まれる場合にノイズ
NOISE_KEYWORD_PAIRS: list[tuple[str, str]] = [
    ("旅客船", "検討会"),
    ("旅客船", "対策"),
    ("旅客船", "委員会"),
    ("旅客船", "中間とりまとめ"),
    ("旅客船", "方向性"),
    ("知床", "事故"),
    ("観光船", "安全対策"),
    ("造船", "振興"),
    ("造船", "支援"),
    ("造船", "国際競争力"),
    ("港湾", "グリーン化"),
    ("港湾", "脱炭素"),
    ("港湾", "受入環境"),
    ("カーボンニュートラル", "ビジョン"),
    ("カーボンニュートラル", "長期"),
    ("カーボンニュートラル", "港湾"),
    ("GHG", "プロジェクト"),
    ("GHG", "会合"),
    ("GHG", "会議"),
    ("GHG", "ロードマップ"),
    ("EEDI", "提案"),
    ("EEDI", "検討"),
    ("分類対象外", ""),  # Geminiが「対象外」と判定したもの
    ("該当なし", ""),
    ("対象外", ""),
    ("分類対象には該当しません", ""),
    ("発行元を示すものではありません", ""),
    ("文書ではないため", ""),
]

# 要約が空または要約なしのレコードもノイズ候補
EMPTY_SUMMARY_IS_NOISE = True


# ---------------------------------------------------------------------------
# ノイズレコード検索
# ---------------------------------------------------------------------------

def is_noise(title: str, summary: str) -> tuple[bool, str]:
    """
    タイトルと要約からノイズかどうかを判定。

    Returns:
        (is_noise: bool, reason: str)
    """
    combined = f"{title} {summary}".lower()

    # 要約なしのレコード（Gemini分類が未完了 or 失敗）
    if EMPTY_SUMMARY_IS_NOISE:
        summary_stripped = (summary or "").strip()
        if not summary_stripped or summary_stripped == "(要約なし)":
            # ただしタイトルに明らかに海事関連のキーワードがあれば残す
            _KEEP_KEYWORDS = [
                "solas", "marpol", "stcw", "ism", "isps", "mlc",
                "船員法", "船舶安全法", "海防法", "海技免状",
                "救命", "消火", "航行", "検査", "証書",
            ]
            if not any(kw.lower() in title.lower() for kw in _KEEP_KEYWORDS):
                return True, "要約なし（未分類）"

    # 単独キーワード除外
    for kw in NOISE_KEYWORDS_SINGLE:
        if kw.lower() in combined:
            return True, f"単独キーワード: {kw}"

    # AND条件除外
    for kw1, kw2 in NOISE_KEYWORD_PAIRS:
        if kw2 == "":
            # kw2が空 → kw1だけで判定（実質単独条件）
            if kw1.lower() in combined:
                return True, f"判定キーワード: {kw1}"
        elif kw1.lower() in combined and kw2.lower() in combined:
            return True, f"AND条件: {kw1} + {kw2}"

    return False, ""


def find_noise_records(client: SupabaseClient) -> list[dict]:
    """
    全ソースの regulations から、ノイズ判定されるレコードを全取得。
    全件取得してローカルで判定（Supabase の or フィルタの複雑さを回避）。
    """
    if not client._configured:
        logger.warning("Supabase 未設定: ノイズレコードを検索できません。")
        return []

    # 全件取得（ページネーション付き）
    all_records: list[dict] = []
    offset = 0
    page_size = 1000

    while True:
        try:
            resp = requests.get(
                f"{client.url}/rest/v1/regulations",
                params={
                    "select": "id,source_id,source,title,summary_ja,url,pdf_url",
                    "limit": str(page_size),
                    "offset": str(offset),
                },
                headers=client._headers,
                timeout=30,
            )
            resp.raise_for_status()
            records = resp.json()
            if not records:
                break
            all_records.extend(records)
            offset += page_size
            if len(records) < page_size:
                break
        except Exception as e:
            logger.error("全件取得エラー (offset=%d): %s", offset, e)
            break

    logger.info("全規制レコード取得: %d 件", len(all_records))

    # ローカルでノイズ判定
    noise_records: list[dict] = []
    for record in all_records:
        title = record.get("title") or ""
        summary = record.get("summary_ja") or ""
        noise, reason = is_noise(title, summary)
        if noise:
            record["_noise_reason"] = reason
            noise_records.append(record)
            logger.debug("ノイズ: [%s] %s — %s", record.get("source", "?"), title[:60], reason)

    return noise_records


# ---------------------------------------------------------------------------
# ノイズレコード削除
# ---------------------------------------------------------------------------

def delete_noise_records(
    client: SupabaseClient,
    records: list[dict],
    dry_run: bool,
) -> int:
    """
    ノイズレコードを regulations テーブルから削除する。
    関連する pending_queue エントリも削除する。

    Returns:
        削除件数
    """
    deleted = 0

    for record in records:
        record_id = record.get("id")
        source_id = record.get("source_id", "?")
        title = record.get("title", "?")

        if dry_run:
            logger.info("[dry-run] 削除対象: %s — %s", source_id, title)
            deleted += 1
            continue

        try:
            # regulations から削除
            resp = requests.delete(
                f"{client.url}/rest/v1/regulations",
                params={"id": f"eq.{record_id}"},
                headers=client._headers,
                timeout=15,
            )
            resp.raise_for_status()

            # pending_queue からも削除（source_id で紐付け）
            if source_id and source_id != "?":
                try:
                    resp_pq = requests.delete(
                        f"{client.url}/rest/v1/pending_queue",
                        params={"source_id": f"eq.{source_id}"},
                        headers=client._headers,
                        timeout=15,
                    )
                    resp_pq.raise_for_status()
                except Exception:
                    pass  # pending_queue になくてもエラーにしない

            deleted += 1
            logger.info("削除完了: %s — %s", source_id, title)

        except Exception as e:
            logger.error("削除エラー: %s — %s", source_id, e)

    return deleted


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="既存ノイズデータの一括清掃"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="削除対象の確認のみ（実際には削除しない）",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=== DRY RUN モード ===")

    client = SupabaseClient()

    # ノイズレコード検索
    total_keywords = len(NOISE_KEYWORDS_SINGLE) + len(NOISE_KEYWORD_PAIRS)
    logger.info("ノイズレコード検索開始（単独%d + AND%d = %d パターン）",
                len(NOISE_KEYWORDS_SINGLE), len(NOISE_KEYWORD_PAIRS), total_keywords)
    noise_records = find_noise_records(client)

    if not noise_records:
        logger.info("ノイズレコードは見つかりませんでした。")
        return

    # ソース別カウント
    source_counts: dict[str, int] = {}
    for r in noise_records:
        src = r.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    logger.info("ノイズレコード検出: %d 件", len(noise_records))
    for src, cnt in sorted(source_counts.items()):
        logger.info("  %s: %d 件", src, cnt)

    # 削除対象のタイトル一覧（dry-run でも表示）
    for r in noise_records:
        logger.info("  [%s] %s — 理由: %s",
                    r.get("source", "?"),
                    (r.get("title") or "?")[:60],
                    r.get("_noise_reason", "?"))

    # 削除
    deleted = delete_noise_records(client, noise_records, args.dry_run)

    if args.dry_run:
        logger.info("=== DRY RUN 完了: %d 件が削除対象 ===", deleted)
    else:
        logger.info("=== 清掃完了: %d 件を削除 ===", deleted)


if __name__ == "__main__":
    main()
