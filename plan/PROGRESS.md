# 実装進捗ログ — MIHARIKUN

> **このファイルはプロジェクトの唯一の進捗ソース・オブ・トゥルース。**
> - 新しいセッション開始時に **最初に読むこと**
> - 作業の開始・完了・ブロック時に **必ず更新すること**（CLAUDE.md 参照）
> - ステータス: `✅ 完了` / `⏳ 作業中` / `🚫 ブロック` / `📋 未着手`

---

## 現在の状態（要約）

| Phase | ラウンド | ステータス | 最終更新 |
|-------|---------|-----------|---------|
| Phase 0: 基盤構築 | — | ✅ 完了 | 2026-03-29 |
| Phase 1 R1: スクレイパー構築 | R1 | ✅ 完了 | 2026-03-29 |
| Phase 1 R2: DB + 検証 + マッチング基盤 | R2 | ✅ 完了 | 2026-03-29 |
| Phase 2: Ship Specs + マッチング + 超軽量 UI | — | 📋 未着手 ← 次 | — |
| Phase 3: Fleet 管理 + 拡張 | — | 📋 未着手 | — |

---

## Phase 0: 基盤構築 ✅ 完了

**完了日:** 2026-03-29

- Next.js 16 + Tailwind CSS + TypeScript のフロントエンド骨格
- Supabase プロジェクト接続設定
- plan/ 設計書一式（Blueprint v4, AGENT_TEAMS_PLAN, IMPLEMENTATION_GUIDE）
- CLAUDE.md（プロジェクトルール）
- `scripts/scrape_nk.py` プロトタイプ（658行）

---

## Phase 1: データ収集パイプライン

### ラウンド 1: スクレイパー構築 ✅ 完了

**完了日:** 2026-03-29
**担当:** Lead(Opus) + Agent A(NK/Sonnet) + Agent B(MLIT/Sonnet) + Agent C(共通基盤/Sonnet)
**テスト結果:** 41 passed in 6.71s

#### 成果物一覧

| ファイル | 行数 | 担当 | 役割 |
|---------|------|------|------|
| `scripts/utils/__init__.py` | 0 | C | パッケージ化 |
| `scripts/utils/gemini_client.py` | 234 | C | Gemini API。2 モデル切替 + 指数バックオフ(max 6回) + confidence/citations |
| `scripts/utils/supabase_client.py` | 465 | A | Supabase REST。7 メソッド（upsert_regulation, queue_pending 等） |
| `scripts/utils/line_notify.py` | 181 | C | LINE 通知。severity 別 5 分スロットリング |
| `scripts/utils/gdrive_client.py` | 202 | C | Google Drive API v3。認証未設定時ローカルフォールバック |
| `scripts/utils/pdf_preprocess.py` | 237 | B | PDF 品質チェック 4 段階（ok/skipped/scan_image/suspicious） |
| `scripts/scrape_nk.py` | 849 | A | ClassNK 本番版。v4 フィールド + pending_queue + LINE 通知 |
| `scripts/scrape_mlit_rss.py` | 570 | B | 国交省 RSS 第 1 層。27 キーワードフィルタ |
| `scripts/scrape_mlit_crawl.py` | 732 | B | 国交省クロール第 2 層。BFS + SHA256 差分 + 異常検知 |
| `scripts/requirements.txt` | 7 | C | Python 依存パッケージ |
| `.github/workflows/scrape-nk.yml` | — | A | NK 日次（JST 07:00） |
| `.github/workflows/scrape-mlit-rss.yml` | — | B | MLIT RSS 日次（JST 08:00） |
| `.github/workflows/scrape-mlit-crawl.yml` | — | B | MLIT クロール週次（日曜 JST 06:00） |
| `.github/workflows/notify-on-failure.yml` | — | C | 再利用可能失敗通知 |
| `tests/__init__.py` | 0 | A | パッケージ化 |
| `tests/python/__init__.py` | 0 | A | パッケージ化 |
| `tests/python/conftest.py` | 211 | A | pytest fixtures |
| `tests/python/test_scrape_nk.py` | 576 | A | 41 テスト・7 クラス |

#### 既知の問題・統合時の教訓

1. **import 不整合**: Agent A が `send_line_notify` を import したが、Agent C の実装は `send_alert` だった → リードが統合時に修正。**教訓: 並列エージェント後は cross-module import チェック必須**
2. **sys.path 未設定**: `scripts/` から `utils/` を import するには `sys.path.insert(0, os.path.dirname(__file__))` が必要 → CLAUDE.md のコーディング規約に追加済み
3. **テスト regex 誤マッチ**: プロンプト説明文中の `` ```json `` テキストに regex が誤マッチ → `\n` を追加して修正

---

### ラウンド 2: DB + 検証 + マッチング基盤 ✅ 完了

**完了日:** 2026-03-29

> **v5 戦略方針転換**: 資格管理フック廃止、Ship Specs + マッチングエンジンに全力集中。
> 詳細: `plan/STRATEGIC_PIVOT_v5.md`

#### 完了済み

- [x] Supabase マイグレーション SQL 作成（`supabase/migrations/`）✅
  - `regulations`, `pending_queue`, `mlit_crawl_state` + RLS + インデックス
  - **Supabase ダッシュボードで適用済み**
- [x] `process-queue.yml` + `health-check.yml` ✅
- [x] MLIT RSS 実データテスト ✅（GHA dry-run 成功、8件海事関連検出）
- [x] NK IP ブロック調査 ✅（GHA IP 完全ブロック確認）

#### Agent Teams 並列実装（2026-03-29）

- [x] **Self-hosted Runner** ✅ — 手順書 + NK ワークフロー修正済み
  - `plan/SELF_HOSTED_RUNNER_SETUP.md` 作成
  - `scrape-nk.yml`: `runs-on: self-hosted`、cron 再有効化、Python フォールバック
  - **ユーザー手動作業待ち**: Runner ダウンロード・設定・サービス化
- [x] **ship_profiles テーブル** ✅ — `00005_ship_profiles.sql` 作成
  - ship_profiles + user_matches テーブル + RLS + インデックス
  - **ユーザー手動作業待ち**: Supabase ダッシュボードで SQL 実行
- [x] **マッチングエンジン v1** ✅ — `scripts/utils/matching.py`
  - ルールベース（6条件で高速除外）→ Gemini AI（精密判定）の2段階
  - confidence + reason + citations を返す
- [x] **MLIT RSS 本番実行** ✅ — Gemini 分類精度検証
  - 結果: Gemini 全件失敗（GEMINI_MODEL Secret が空文字で 404）
  - **対策**: GEMINI_MODEL / GEMINI_FALLBACK_MODEL Secret を削除 → デフォルト値が効く
  - pending_queue 未登録バグ修正済み
  - 精度レポート: `plan/GEMINI_ACCURACY_REPORT.md`

#### 本番検証（2026-03-29）

- [x] **ユーザー作業**: Self-hosted Runner をローカル PC にセットアップ ✅
- [x] **ユーザー作業**: `00005_ship_profiles.sql` を Supabase で実行 ✅
- [x] **ユーザー作業**: GEMINI_MODEL / GEMINI_FALLBACK_MODEL Secret を削除 ✅
- [x] MLIT ワークフロー GEMINI_MODEL を `vars || デフォルト値` に修正 ✅ (a9ee0c7)
- [x] MLIT スクレイパー `confidence_score` → `confidence` カラム名修正 ✅ (eb314ff)
- [x] Supabase upsert に `on_conflict=source,source_id` 追加 ✅ (55d276e)
- [x] NK 本番実行 ✅ — 3件 upsert 成功 (recycling×2, environment×1, confidence=0.95)
- [x] MLIT RSS 本番実行 ✅ — 3件 upsert 成功 (1件 Gemini 分類済み, 2件 429 レート制限で pending)

---

## Phase 2: Ship Specs + マッチング + 超軽量 UI 📋 未着手

> 設計書: `plan/STRATEGIC_PIVOT_v5.md` §4

- [ ] Supabase Auth（ログイン / サインアップ）
- [ ] Ship Specs 登録画面 (`/ships/new`, `/ships/[id]`)
- [ ] パーソナライズダッシュボード (`/dashboard`) — 自船に関係ある規制のみ
- [ ] ニュースタブ (`/news`) — 全規制一覧（Free）
- [ ] 規制詳細 (`/news/[id]`) — AI 要約 + 根拠引用
- [ ] 超軽量通知設定 (`/settings`) — メール / LINE
- [ ] 週次サマリーメール — GHA 自動生成
- [ ] 初期ロード < 50KB、Service Worker キャッシュ

## Phase 3: Fleet 管理 + 拡張 📋 未着手

- [ ] Fleet 管理（複数船一括）
- [ ] e-Gov パブコメ監視
- [ ] LINE リアルタイム通知
- [ ] ユーザーフィードバック（AI 精度改善ループ）

---

## 変更ログ

> エージェントは作業のたびにここに 1 行追記すること。
> 形式: `- YYYY-MM-DD HH:MM — [担当] 内容`

- 2026-03-29 15:00 — [Lead/Opus] Phase 1 R1 完了。Agent A/B/C の成果物を統合、import 不整合 3 件修正、41 テスト全通過
- 2026-03-29 16:00 — [Lead/Opus] CLAUDE.md にエージェント運用ルール追加、PROGRESS.md リデザイン
- 2026-03-29 — [Opus] Phase 1 R2: マイグレーション SQL 4ファイル作成、Supabase 適用済み
- 2026-03-29 — [Opus] Phase 1 R2: process_queue.py + health_check.py + GHA ワークフロー 2つ作成
- 2026-03-29 — [Opus] MLIT RSS URL 修正 (maritime.xml→pressrelease.rdf)、GHA dry-run 成功
- 2026-03-29 — [Opus] NK: GHA IP ブロック判明。requests/curl_cffi/Playwright 全滅。cron 無効化、ローカル実行用に維持
- 2026-03-29 — [Opus] **戦略方針転換 v5**: 資格管理フック廃止、Ship Specs + マッチングエンジン最優先、Self-hosted Runner 採用
- 2026-03-29 — [Opus] plan/STRATEGIC_PIVOT_v5.md 作成、CLAUDE.md・PROGRESS.md を v5 方針に更新
- 2026-03-29 — [Agent A/Sonnet] Self-hosted Runner 手順書 + NK ワークフロー修正
- 2026-03-29 — [Agent B/Sonnet] ship_profiles SQL + matching.py（ルールベース + AI 2段階）
- 2026-03-29 — [Agent C/Sonnet] MLIT RSS 本番実行、Gemini 全件失敗の原因特定（GEMINI_MODEL Secret 空文字）
- 2026-03-29 — [Lead/Opus] 統合チェック、classify_pdf pending ハンドリングバグ修正（NK + MLIT 両方）
- 2026-03-29 — [Lead/Opus] Self-hosted Runner 稼働確認（online）、NK dry-run 成功（50件パース、3件処理）
- 2026-03-29 — [Lead/Opus] NK bot UA 環境変数 (SCRAPE_USER_AGENT) 削除 → 403 解消
- 2026-03-29 — [Lead/Opus] HANDOFF.md 更新（Phase 1 R2 継続用）
- 2026-03-29 20:57 — [Lead/Opus] MLIT ワークフロー GEMINI_MODEL を vars+デフォルト値に修正 (a9ee0c7)
- 2026-03-29 21:00 — [Lead/Opus] MLIT confidence_score→confidence カラム名修正 (eb314ff)
- 2026-03-29 21:03 — [Lead/Opus] Supabase upsert on_conflict 追加 (55d276e)
- 2026-03-29 21:06 — [Lead/Opus] NK 本番成功 (3件), MLIT RSS 本番成功 (3件) — Phase 1 R2 完了
- 2026-03-29 21:10 — [Lead/Opus] CLAUDE.md にリソース適応型 Agent Teams ルール追加
