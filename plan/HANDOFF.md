# 引継ぎ書 — MIHARIKUN Phase 2 開始

> **次のセッションはこのファイルから読み始めてください。**
> 最終更新: 2026-03-29 21:10 JST

---

## 1. 今どこにいるか

**Phase 1 完了。Phase 2（Ship Specs + 超軽量 UI MVP）に着手可能。**

```
Phase 0: 基盤構築              ✅ コミット済み
Phase 1 R1: スクレイパー       ✅ コミット済み
Phase 1 R2: DB + マッチング    ✅ 完了（本番検証済み）
Phase 2: Ship Specs + UI       📋 未着手 ← 次はここ
Phase 3: Fleet 管理 + 拡張     📋 未着手
```

### Phase 1 R2 の本番検証結果
- **NK**: 3件 PDF→Gemini→Supabase 全パイプライン成功 (Self-hosted Runner 経由)
- **MLIT RSS**: 3件 Supabase upsert 成功 (1件 Gemini 分類済み, 2件 429 レート制限で pending)
- Supabase `regulations` テーブルに計6件のデータが入っている状態

---

## 2. 最初にやること

```
1. plan/PROGRESS.md を読んで詳細を把握
2. plan/STRATEGIC_PIVOT_v5.md §4 で Phase 2 の設計を確認
3. Phase 2 タスクの優先順位を決定し、実装開始
```

---

## 3. Phase 2 タスク一覧

> 設計書: `plan/STRATEGIC_PIVOT_v5.md` §4

- [ ] Supabase Auth（ログイン / サインアップ）
- [ ] Ship Specs 登録画面 (`/ships/new`, `/ships/[id]`)
- [ ] パーソナライズダッシュボード (`/dashboard`) — 自船に関係ある規制のみ
- [ ] ニュースタブ (`/news`) — 全規制一覧（Free）
- [ ] 規制詳細 (`/news/[id]`) — AI 要約 + 根拠引用
- [ ] 超軽量通知設定 (`/settings`) — メール / LINE
- [ ] 週次サマリーメール — GHA 自動生成
- [ ] 初期ロード < 50KB、Service Worker キャッシュ

---

## 4. 知っておくべきこと

### Self-hosted Runner の状態
- ランナー名: `B-A59000-089`
- ラベル: `self-hosted, Windows, X64, nk-runner`
- 稼働方法: `C:\actions-runner\run.cmd` をバックグラウンド実行（サービス化は未完了）
- **PC 再起動後は `C:\actions-runner\run.cmd` を再実行する必要あり**

### NK スクレイパーの注意点
- `SCRAPE_USER_AGENT` 環境変数を設定してはいけない（Chrome UA のデフォルト値を使う）

### Gemini の注意点
- `GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` は Secret から削除済み。ワークフローで `vars || デフォルト値` パターンを使用
- 無料枠のレート制限 (429) に注意。日次定時実行なら問題なし
- `classify_pdf` は失敗時に例外を投げず `{"status": "pending"}` を返す

### Supabase の注意点
- upsert には `on_conflict=source,source_id` が必要（PK が UUID のため）
- `ship_profiles` + `user_matches` テーブル + RLS は適用済み

### 設計文書の優先順位
1. `plan/STRATEGIC_PIVOT_v5.md` — 最上位の意思決定文書
2. `plan/MARITIME_PROJECT_BLUEPRINT_v4.md` — 技術詳細（v5 と矛盾する場合は v5 優先）
3. `CLAUDE.md` — コーディング規約・運用ルール

### 過去の罠（再発防止）
1. `send_line_notify` は存在しない → 正しくは `send_alert`
2. `scripts/` から `utils/` を import するには `sys.path.insert` 必須
3. ClassNK は GHA IP + bot UA の両方をブロック → Self-hosted Runner + Chrome UA で解決
4. Supabase の空文字 Secret が環境変数のデフォルト値を上書きする
5. `classify_pdf` は例外ではなく `status=pending` を返す → `except` だけでは捕捉できない
6. MLIT スクレイパーのフィールド名は DB スキーマと一致させること（`confidence` not `confidence_score`）
7. PostgREST upsert は PK 以外の UNIQUE 制約には `on_conflict` パラメータが必要

---

## 5. 必要な環境変数（GitHub Secrets）

| 変数名 | 状態 | 備考 |
|--------|------|------|
| `SUPABASE_URL` | ✅ 設定済み | |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ 設定済み | |
| `GEMINI_API_KEY` | ✅ 設定済み | |
| `LINE_NOTIFY_TOKEN` | 未設定 | Phase 2 通知機能で必要 |
| `GDRIVE_FOLDER_ID` | 未設定 | テキスト保存不要なら後回し |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 未設定 | Drive API 不要なら後回し |

### Supabase 環境変数（フロントエンド用・Phase 2 で必要）
| 変数名 | 状態 | 備考 |
|--------|------|------|
| `NEXT_PUBLIC_SUPABASE_URL` | 未設定 | Vercel 環境変数 |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | 未設定 | Vercel 環境変数（公開OK） |
