# Gemini 分類精度検証レポート

## 概要

| 項目 | 値 |
|------|-----|
| 実行日時 | 2026-03-29 09:16:07 UTC (JST 18:16) |
| GHA Run ID | 23705846512 |
| 実行モード | 本番（dry_run=false） |
| limit | 5 件 |
| ワークフロー | scrape-mlit-rss.yml |
| 実行時間 | 43 秒 |

---

## 1. RSS フィード取得結果

| 指標 | 値 |
|------|-----|
| RSSフィードURL | https://www.mlit.go.jp/pressrelease.rdf |
| 総エントリ数 | 50 件 |
| 海事関連検出数 | 8 件（16.0%） |
| 既知URL（スキップ） | 0 件（初回実行） |
| 処理対象（limit適用後） | 5 件 |

---

## 2. PDF ダウンロード結果

全 5 件で PDF リンクを検出・ダウンロード成功。

| source_id | タイトル（冒頭） | PDFファイルサイズ | ページ数 | 文字数 |
|-----------|------------------|-------------------|-----------|--------|
| MLIT-20260326-001 | グリーンインフラに関するファイナンスガイドライン | 127,620 bytes | 1 | 1,019 |
| MLIT-20260326-002 | 下水道法等の一部を改正する法律案を閣議決定 | 186,345 bytes | 1 | 1,305 |
| MLIT-20260326-003 | 内航カーボンニュートラル推進に向けた検討会（第10回）| 457,261 bytes | 1 | 945 |
| MLIT-20260326-004 | 港湾における水素・アンモニアの受入環境整備ガイドライン | 155,995 bytes | 1 | 904 |
| MLIT-20260326-005 | 港湾工事でカーボンニュートラルに貢献 | （処理済み） | — | — |

PDF チェック: 全件アクセス可能 (check_pdf_url OK)、全件前処理通過 (status=ok)

---

## 3. Gemini 分類結果

### 結果サマリー

| 結果 | 件数 |
|------|------|
| 分類成功 (status=ok) | 0 件 |
| 分類失敗 (status=pending) | 5 件 |
| pending_queue 登録 | 0 件（バグ：後述） |

### エラー詳細

**根本原因：`GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` の GitHub Secret が未設定**

```
[Gemini] primary モデル '' で処理開始 source_id='MLIT-20260326-001'
[Gemini] リトライ不可エラー model='': HTTP 404:
[Gemini] fallback モデル '' で処理開始 source_id='MLIT-20260326-001'
[Gemini] リトライ不可エラー model='': HTTP 404:
[Gemini] 全モデル失敗 source_id='MLIT-20260326-001'
```

`gemini_client.py` のコードは以下のように環境変数からモデル名を取得している:

```python
primary_model = os.environ.get("GEMINI_MODEL", _DEFAULT_PRIMARY_MODEL)
fallback_model = os.environ.get("GEMINI_FALLBACK_MODEL", _DEFAULT_FALLBACK_MODEL)
```

GitHub Secret として `GEMINI_MODEL` と `GEMINI_FALLBACK_MODEL` が設定されているが、
値が**空文字列**であるため、デフォルト値（`gemini-2.5-flash` / `gemini-2.0-flash`）が
上書きされてしまい、モデル名が `''` のまま Gemini API に送信された。

Gemini API は `https://generativelanguage.googleapis.com/v1beta/models/:generateContent` を
呼び出すため、モデル名が空だと HTTP 404 が返る。

### confidence 値の分布

| confidence | 件数 |
|------------|------|
| 取得不可（全件エラー）| 5 件 |

---

## 4. Supabase upsert 結果

| 結果 | 件数 |
|------|------|
| upsert 成功 | 5 件 |
| upsert 失敗 | 0 件 |

5 件全て Supabase の `regulations` テーブルに保存された。
ただし Gemini 分類が失敗したため、以下のフィールドは `NULL` で保存されている:

- `category`
- `severity`
- `summary_ja`
- `confidence_score`
- `citations`
- `applicable_ship_types`
- `effective_date`
- `raw_gemini_response`

---

## 5. pending_queue 登録状況

**登録なし（0 件）** — これはバグ。

### 問題のフロー

`scrape_mlit_rss.py` の `process_entries()` では、
`classify_pdf()` が例外を投げた場合のみ `client.queue_pending()` を呼ぶ:

```python
try:
    classification = classify_pdf(...)
except Exception as e:
    logger.error("Gemini 分類エラー: ...")
    client.queue_pending(...)   # ← 例外時のみ登録
```

しかし `gemini_client.py` の `classify_pdf()` は**例外を投げず**、
失敗時には `{"status": "pending", "error": "..."}` を返す設計になっている。

そのため例外が発生せず `queue_pending()` が呼ばれない。
結果として、分類失敗したレコードが pending_queue に登録されないまま
Supabase に category=NULL で保存されてしまった。

---

## 6. 分類結果の妥当性評価

分類が実行されなかったため直接の精度評価は不可。
しかし検出された5件について、タイトルから手動で妥当なカテゴリを推定する。

| source_id | タイトル（要旨） | 想定カテゴリ | 海事関連性の妥当性 |
|-----------|-----------------|-------------|-------------------|
| MLIT-20260326-001 | グリーンインフラ ファイナンスガイドライン | 環境/金融 | 低〜中（海事キーワード「港湾」「沿岸」等でフィルタが反応した可能性）|
| MLIT-20260326-002 | 下水道法改正の閣議決定 | 法令改正 | 低（非海事。「安全」キーワードで誤検出の可能性）|
| MLIT-20260326-003 | 内航カーボンニュートラル推進検討会 | 環境/内航海運 | 高（直接的な海事規制関連）|
| MLIT-20260326-004 | 港湾における水素・アンモニア受入ガイドライン | 港湾/エネルギー | 高（港湾施設・海事インフラ）|
| MLIT-20260326-005 | 港湾工事でカーボンニュートラル | 港湾/環境 | 中〜高（港湾関連）|

**フィルタ精度の懸念**: 5 件中 1〜2 件（MLIT-20260326-001, 002）は
純粋な海事規制ではなく、キーワードの広すぎるマッチによる誤検出の可能性がある。

---

## 7. 発見した問題点

### 問題 1（高優先度）: GEMINI_MODEL / GEMINI_FALLBACK_MODEL が空文字列

**内容**: GitHub Secrets に `GEMINI_MODEL` と `GEMINI_FALLBACK_MODEL` が設定されているが、
値が空文字列のため Gemini 分類が全件失敗。

**影響**: 全5件で category/severity/summary_ja が NULL のまま Supabase に保存された。

**対処**: GitHub Settings > Secrets から `GEMINI_MODEL` と `GEMINI_FALLBACK_MODEL` を
**削除するか**、または値を正しいモデル名（`gemini-2.5-flash`）に設定する。
空文字列の Secret を削除すれば、コードのデフォルト値（`gemini-2.5-flash`）が使われる。

### 問題 2（中優先度）: classify_pdf() 失敗時に pending_queue 未登録

**内容**: `classify_pdf()` は失敗時に例外ではなく `{"status": "pending"}` を返すが、
`process_entries()` は例外の場合のみ `queue_pending()` を呼ぶ。

**影響**: Gemini 分類失敗レコードが pending_queue に登録されず、
再処理の仕組みが機能しない。

**対処**: `process_entries()` で `classification.get("status") == "pending"` の場合も
`queue_pending()` を呼ぶよう修正する。

```python
# 修正例
if classification and classification.get("status") == "pending":
    client.queue_pending(
        source="MLIT",
        source_id=source_id,
        pdf_url=primary_pdf_url or "",
        reason="gemini_pending",
        error_detail=classification.get("error", ""),
    )
```

### 問題 3（低優先度）: Gemini ログの出力タイミングが不自然

**内容**: `[Gemini] primary モデル '' で処理開始` のログが、
`処理完了: 5 件` の**後**に出力されている。

**推定原因**: `gemini_client.py` が `print()` を使っているが、
`scrape_mlit_rss.py` が `logging` モジュールを使っているため、
stdout と stderr/logging バッファのフラッシュタイミングがずれている。

**対処**: `gemini_client.py` でも `logging` モジュールを使うよう統一する。

### 問題 4（中優先度）: 非海事コンテンツのフィルタ漏れ

**内容**: 「下水道法等の一部を改正する法律案」が海事関連として検出されている。
「安全」「環境」等の汎用キーワードが原因と思われる。

**対処**: キーワードリストを見直し、「安全」「環境」など汎用語を削除または
複合条件（複数キーワードのAND）に変更する。あるいはURL `/kaiji/` パスチェックを
フィルタリングの優先条件とする。

---

## 8. プロンプト改善提案

Gemini が実際に動作した際の品質向上のための提案:

### 8.1 プロンプトの具体性向上

現在のプロンプトはカテゴリの選択肢を明示していない。以下を追加する:

```
"category" の選択肢（必ずこの中から選ぶこと）:
- "vessel_safety": 船舶安全（検査・証書・設備）
- "seafarer": 船員（資格・労働・健康）
- "environment": 環境（排出ガス・バラスト水・廃棄物）
- "port_facility": 港湾施設・保安
- "navigation": 航行安全・航路
- "international_convention": 国際条約（IMO・SOLAS・MARPOL等）
- "inland_shipping": 内航海運
- "other_maritime": その他海事関連
- "non_maritime": 海事関連でない（誤検出）
```

### 8.2 非海事文書の除外指示

```
もし文書が海事・船舶・港湾・船員に全く関係しない場合は、
category="non_maritime", confidence=0.9 を返してください。
```

### 8.3 プレスリリース専用の要約指示

MLIT の RSS はプレスリリース（1ページ）が多い。
プレスリリース特有の構造（背景・概要・問い合わせ先）に対応した指示を追加する。

---

## 9. 次のアクション

| 優先度 | アクション | 担当 |
|--------|-----------|------|
| 高 | `GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` の空Secretを削除 | 開発者（GitHub Settings） |
| 高 | 修正後、limit=5 で再実行し Gemini 分類が通ることを確認 | Agent C |
| 中 | pending_queue 登録バグを修正 (`process_entries()`) | Agent B |
| 中 | キーワードフィルタの非海事誤検出を改善 | Agent B |
| 低 | `gemini_client.py` のログを `logging` モジュールに統一 | Agent B |

---

*レポート生成: 2026-03-29 by Agent C (Claude Sonnet 4.6)*
