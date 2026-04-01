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
| Phase 2: Ship Specs + マッチング + 超軽量 UI | — | ✅ 完了 | 2026-03-30 |
| Phase 3: Fleet + 拡張 + コンプライアンスエンジン | — | ⏳ 作業中 | 2026-04-01 |
| マッチングエンジン刷新 (v3→4段階) | — | ✅ 完了 | 2026-04-01 |
| コードベース整理 (publications分割等) | — | ✅ 完了 | 2026-04-01 |

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

## Phase 2: Ship Specs + マッチング + 超軽量 UI ✅ 完了

> 設計書: `plan/STRATEGIC_PIVOT_v5.md` §4

#### フロントエンド MVP（2026-03-29）

- [x] Supabase Auth（ログイン / サインアップ / ミドルウェア） ✅ (3fa5105)
- [x] Ship Specs 登録画面 (`/ships/new`, `/ships/[id]`) ✅ (3fa5105)
- [x] パーソナライズダッシュボード (`/dashboard`) ✅ (3fa5105)
- [x] ニュースタブ (`/news`) + 規制詳細 (`/news/[id]`) ✅ (3fa5105)
- [x] 通知設定 (`/settings`) プレースホルダー ✅ (3fa5105)
- [x] Nav + Footer + ランディングページ ✅ (3fa5105)
- [x] TypeScript 型定義 + コンパイルエラーゼロ ✅

#### デプロイ + E2E テスト（2026-03-29）

- [x] login ページ Suspense boundary 追加（Vercel ビルドエラー修正） ✅ (5796a1f)
- [x] Vercel デプロイ ✅ — https://frontend-nine-chi-56.vercel.app
- [x] 環境変数設定 (NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY) ✅
- [x] Supabase Auth Site URL + Redirect URL 設定 ✅
- [x] E2E テスト: サインアップ → 確認メール → ログイン → 船舶登録 → ダッシュボード ✅
- [x] /news ページで実データ 6件の表示確認 ✅

#### マッチング + 品質改善（2026-03-29）

- [x] マッチングワークフロー (`run_matching.py` + `run-matching.yml`) ✅ (28a23b5)
- [x] ダッシュボード regulation JOIN 修正 ✅ (cc27de8)
- [x] regulations に authenticated SELECT RLS 追加 ✅ (4619170)
- [x] ダッシュボード: 船舶編集導線 [EDIT] + エラーメッセージ改善 ✅ (2edbb18)
- [x] マッチング精度改善: ルールベース強化 + AI プロンプト刷新 ✅ (33f77ab)
- [x] マッチング再処理: confidence=0 の失敗レコード再処理ロジック ✅ (0bb006c)
- [x] ニュースページ: ソースフィルタ + 件数 + サマリー表示 ✅ (6fa8726)
- [x] 入力バリデーション: GT範囲, 建造年, IMO7桁, 航行区域必須 ✅ (6fa8726)
- [x] 週次サマリー (`weekly_summary.py` + `weekly-summary.yml`) ✅ (6fa8726)

#### 追加機能 + インフラ（2026-03-29）

- [x] ニュース詳細改善: OGメタタグ, 色付き信頼度, 原文/PDFリンク ✅ (eda97cb)
- [x] ダッシュボード該当フィルタ (`?filter=applicable`) ✅ (eda97cb)
- [x] LINE 通知 (`notify_matches.py` + run-matching.yml 連携) ✅ (eda97cb)
- [x] Playwright E2E テスト (9テスト) ✅ (eda97cb)
- [x] ニュースページネーション (10件ずつ) + フォント軽量化 ✅ (a521b8c)
- [x] カスタムドメイン: https://miharikun.vercel.app ✅
- [x] Vercel 自動デプロイ (Git push → 自動ビルド) ✅

#### フルアップグレード（2026-03-30）

- [x] PWA 強化: モバイルナビ (ハンバーガー), Loading/404/Error ページ ✅ (517352a)
- [x] Settings 実装: user_preferences テーブル + 通知設定フォーム ✅ (517352a)
- [x] Admin ヘルス: /admin/health システム状態ダッシュボード ✅ (517352a)
- [x] Scrapling 統合: NK スクレイパーに StealthyFetcher + graceful fallback ✅ (fab3c26)
- [x] Golden Set テスト: マッチング精度バリデーション 19テスト全通過 ✅ (fab3c26)
- [x] PWA 船上命綱: 4段階キャッシュ + オフラインページ + 復帰通知 ✅ (fab3c26)
- [x] Security: TruffleHog + npm/pip audit + セキュリティチェックリスト ✅ (fab3c26)
- [x] MCP: Google Drive MCP サーバー設定テンプレート ✅ (fab3c26)

#### NK GHA 直接実行検証（2026-03-30）

- [x] NK ワークフローを ubuntu-latest に一時変更 ✅ (3f8b9d1)
- [x] dry-run テスト: **200 OK で成功** (50件パース、403 なし) ✅
- [x] **発見: ClassNK は IP ではなく bot UA でブロックしていた** — UA 修正済みのため GHA 直接実行が可能
- [x] NK ワークフローを ubuntu-latest に正式移行 ✅ (a92c89d)
- [x] **Self-hosted Runner 不要に** — PC 再起動後の手動 run.cmd 実行が解消
- [x] NK 本番実行完了（ubuntu-latest, Gemini 分類付き, 40件 upsert）✅

#### 出自隠蔽技術の調査結果（将来 IP ブロック再発時の備え）

| 手法 | 月額 | 信頼度 | 推奨度 |
|------|------|--------|--------|
| Tailscale トンネル (自宅PC経由) | $0 | 高 (日本IP) | ★★★★★ |
| SmartProxy 住宅用プロキシ | $7-15 | 高 | ★★★★ |
| ScrapingBee API | $0-49 | 良 | ★★★ |
| Zyte API | $0-15 | 未検証 | ★★★ |
| 無料プロキシ | $0 | 極低 | 使用禁止 |

**結論**: 現在は GHA 直接実行で問題なし。再発時は Tailscale (無料) が最善。

#### 推論型コンプライアンスエンジン（2026-03-30）

- [x] maritime_knowledge.py: 43条約ルール, 871キーワード, 国内法マッピング ✅
- [x] ship_compliance.py: 5項目→適用条約自動推論 + Potential Match ✅
- [x] matching.py v3: Stage1(ルール)→Stage0(条約)→Stage2(AI) 3段階 ✅
- [x] "all" バグ修正: ルールベースが全船適用規制を非該当と判定するバグ修正 ✅
- [x] --force オプション: 全件再マッチング機能 ✅

#### Yahoo!ニュース風ポータル（2026-03-30）

- [x] news/page.tsx: 6タブ(全て/主要/安全/環境/船員/船級) + カードデザイン ✅
- [x] Gemini headline生成: 20-30文字の短い見出し ✅
- [x] 00007_headline.sql マイグレーション ✅

#### Gemini 有料プラン移行（2026-03-30）

- [x] Tier 1 Pay-as-you-go に切り替え ✅
- [x] レートリミッター 4秒→0.5秒に短縮 ✅
- [x] NK 全件取り込み: 40件 upsert, 429ゼロ ✅
- [x] 全件再マッチング: 88件, convention_based 57件 ✅

#### NK ubuntu-latest 移行（2026-03-30）

- [x] GHA直接実行テスト: 200 OK, 403なし ✅
- [x] Self-hosted Runner 不要に ✅
- [x] 出自隠蔽調査: Tailscale推奨（将来の備え）✅

#### 残タスク

- [ ] LINE_NOTIFY_TOKEN を GitHub Secrets に設定（LINE 通知を有効化）
- [ ] Google Drive MCP の認証設定（GOOGLE_SERVICE_ACCOUNT_JSON_PATH）
- [x] 00006_user_preferences.sql の Supabase 適用 ✅

## Phase 3: Fleet + 拡張 + コンプライアンスエンジン ⏳ 作業中

### 推論型コンプライアンスエンジン（2026-03-30）
- [x] maritime_knowledge.py: 43条約, 871キーワード, 12 SMS章, 船側/会社側アクション ✅
- [x] ship_compliance.py: 5項目→適用条約自動推論 + Potential Match ✅
- [x] matching.py v3: Stage1(ルール)→Stage0(条約)→Stage2(AI) 3段階 ✅
- [x] "all" バグ修正 + --force 全件再マッチングオプション ✅
- [x] Gemini Tier 1 移行 (429→0, 0.5秒間隔) ✅
- [x] NK ubuntu-latest 移行 (Self-hosted Runner 不要) ✅

### 精度極限向上（2026-03-31）
- [x] Step 1: フロントを Gemini データに直接接続 (ハルシネーション排除) ✅
- [x] Step 2: Pydantic バリデーション (validation.py) ✅
- [x] Step 3: Chain of Verification (CoVe) — 低確信度の自動検証 ✅
- [x] Step 4: 単語境界マッチング — ISM≠tourism ✅
- [x] Golden Set 29テスト全通過 (ルール19 + 条約7 + アクション精度3) ✅

### Yahoo!ニュース風ポータル + プロUI（2026-03-30〜31）
- [x] 専門タブ: SOLAS/安全, MARPOL/環境, STCW/船員, 国内法/旗国 ✅
- [x] headline 一括生成 (453件) + PDF名除去 ✅
- [x] 適用日ソート + 船側/会社側ラベル + SMS章番号推論 ✅
- [x] 詳細ページ: AI分析 vs キーワード推論の明示 ✅

### Fleet管理 + 通知（2026-03-30）
- [x] /fleet: 全船一覧 + 適用条約バッジ + コンプライアンス率 ✅
- [x] /fleet/summary: 管理者ビュー + アクション要約 ✅
- [x] e-Gov パブコメスクレイパー ✅
- [x] LINE通知 (user_preferences連携) ✅
- [x] 週次サマリーメール (Resend API接続) ✅

### UI/UX プロ化（2026-03-30）
- [x] Badge システム (bracket text 全廃→カラフルピルバッジ) ✅
- [x] ランディングページ完全リデザイン (6セクション) ✅
- [x] Sonner トースト + next-themes ダークモード ✅
- [x] モバイルハンバーガーメニュー + Loading/404/Error ✅
- [x] tailwindcss-motion アニメーション ✅

### インフラ強化（2026-03-30）
- [x] Scrapling StealthyFetcher (NK + MLIT) ✅
- [x] CI (TypeScript + pytest + ESLint) ✅
- [x] Security Scan (TruffleHog + npm/pip audit) ✅
- [x] Vercel 自動デプロイ + カスタムドメイン ✅
- [x] PWA 4段階キャッシュ + オフラインページ ✅

### ユーザーフィードバック + 排他キーワード強化（2026-03-29）
- [x] FeedbackButtons コンポーネント (thumbs up/down) ✅
- [x] /api/feedback エンドポイント (user_feedback / needs_review 更新) ✅
- [x] ダッシュボードに FeedbackButtons 統合 (convention_based / ai_matching のみ) ✅
- [x] 00008_feedback.sql マイグレーション (user_feedback, feedback_at, needs_review) ✅
- [x] KEYWORD_EXCLUSIONS: 8条約の排他ルール (min_keyword_matches, required_any, single_keyword_insufficient) ✅
- [x] matching.py: _passes_exclusion_check() で cross-contamination 防止 ✅
- [x] ship_compliance.py: convention_id が "UNKNOWN" になるバグ修正 (rule["id"] を使用) ✅
- [x] 全70テスト通過 + TSC エラーゼロ ✅
- [x] **ユーザー作業**: 00008_feedback.sql を Supabase ダッシュボードで実行 ✅

### Vibe OS 導入 + Maritime Command Center（2026-03-31）
- [x] plan/PERSONAS.md 新規作成 (4ロール自動憑依システム) ✅
- [x] CLAUDE.md 更新 (Vibe OS セクション + 鉄の掟4条 + v6方針) ✅
- [x] framer-motion インストール ✅
- [x] globals.css: Glassmorphism + glow + gauge アニメーション + ダークスクロールバー ✅
- [x] ComplianceGauge: SVGアニメーション付き円形ゲージ ✅
- [x] TimelineStrip: 施行日横スクロールタイムライン (urgency色変化) ✅
- [x] GlassRegulationCard: Glassmorphismパネル + luminous glow ✅
- [x] CommandPalette: Cmd+K コマンドパレット (9コマンド) ✅
- [x] DashboardShell: Framer Motion staggered animation wrapper ✅
- [x] Dashboard page.tsx: Maritime Command Center 完全リデザイン ✅
- [x] Badge: ダークファースト カラースキーム更新 ✅
- [x] layout.tsx: CommandPalette + Sonner dark theme 統合 ✅
- [x] TSC --noEmit エラーゼロ + next build 成功 ✅

### 船内備付書籍管理システム（2026-03-31）
- [x] publication_requirements.py: 67書籍 × 4カテゴリの自動判定ロジック ✅
- [x] 00009_publications.sql: publications + ship_publications テーブル + RLS ✅
- [x] /api/publications: GET(一覧) + PUT(版数更新) APIルート ✅
- [x] /ships/[id]/publications: Glassmorphism UI + コンプライアンスゲージ ✅
- [x] glass-publication-card.tsx: ステータス別 glow + インライン版数編集 ✅
- [x] publication-stats.tsx: 4カードサマリー + カウントアップアニメーション ✅
- [x] TypeScript型: Publication, ShipPublication + ラベル定義 ✅
- [x] テスト: 51テスト全通過 (全体121テスト) + TSC + next build 全パス ✅
- [x] **ユーザー作業**: 00009_publications.sql を Supabase ダッシュボードで実行 ✅

### 法定図書自動マッピング完全版（2026-03-31）
- [x] 00010_radio_equipment.sql: ship_profiles に radio_equipment (GMDSS/AIS/VDR等) 追加 ✅
- [x] 無線設備関連書籍5件追加 (GMDSS Manual/ITU/無線局運用規則/AIS/VDR) ✅
- [x] 船舶登録・編集フォームに無線設備チェックボックス追加 ✅
- [x] seed_publications.py: 67書籍マスターデータの初期投入スクリプト ✅
- [x] check_publication_updates.py: 週次版数チェッカー (5発行元フレームワーク) ✅
- [x] GHA: seed-publications.yml (手動) + check-publications.yml (週次月曜) ✅
- [x] ステータス可視化: Green(最新)/Amber(要確認)/Red(要更新) ダッシュボード表示 ✅
- [x] 全121テスト通過 + TSC + next build 全パス ✅
- [x] **ユーザー作業**: 00010_radio_equipment.sql を Supabase ダッシュボードで実行 ✅
- [x] **ユーザー作業**: GHA で seed-publications を手動実行（67書籍投入完了）✅

### 残タスク
- [ ] LINE_NOTIFY_TOKEN を GitHub Secrets に設定
- [ ] RESEND_API_KEY を Vercel env に設定
- [ ] 00008_feedback.sql を Supabase ダッシュボードで実行
- [x] 00009_publications.sql を Supabase ダッシュボードで実行 ✅
- [ ] フロントエンド単体テスト (Jest/Vitest)
- [ ] Gemini プロンプトの DSPy 最適化 (本番フィードバック蓄積後)
- [ ] LlamaIndex RAG (条約原文のインデキシング、将来)

### マッチングエンジン刷新（2026-04-01）
- [x] matching.py v3: 4段階パイプライン (Stage1ルール→Stage0条約→Stage2ルール評価→Stage3 AIフォールバック) ✅
- [x] Master Matching: applicability_rules JSON による API 消費ゼロ判定 ✅
- [x] extract_applicability_rules.py + extract-rules.yml: 全453件の applicability_rules 抽出 ✅
- [x] 全件再マッチング完了 (適用4件、非適用35件、エラー0、429ゼロ) ✅
- [x] Golden Set 29テスト全通過 ✅
- [x] 00012_regulations_applicability.sql マイグレーション ✅

### コードベース整理（2026-04-01）
- [x] publications/ パッケージ分割: publication_requirements.py (2,369行) → 7ファイルに分割 ✅
- [x] gemini_config.py: Gemini モデル名・パラメータの一元管理 ✅
- [x] 書籍ID統一: PUB_X_NNN → 記述的ID (67件全件) ✅
- [x] 書籍 applicability_rules JSON 化 ✅
- [x] 00011_publications_v2.sql: applicability_rules JSONB + last_verified_at + verified_by ✅
- [x] 戦略ロードマップ v6→v7 更新: 「航海士個人のための情報の蒸留器」方針 ✅

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
- 2026-03-29 21:30 — [Lead/Opus] Phase 2 基盤: Supabase クライアント, Auth ミドルウェア, Nav/Footer, 型定義
- 2026-03-29 21:30 — [Agent A/Sonnet] Ship Specs 登録・編集画面 (/ships/new, /ships/[id])
- 2026-03-29 21:30 — [Agent B/Sonnet] News + Dashboard + Settings ページ
- 2026-03-29 21:35 — [Lead/Opus] 統合チェック: TSC エラーゼロ, コミット (3fa5105)
- 2026-03-29 22:00 — [Lead/Opus] 全ドキュメント整合性更新 (HANDOFF/STRATEGIC_PIVOT/BLUEPRINT)
- 2026-03-29 22:10 — [Lead/Opus] login Suspense boundary 修正、Vercel デプロイ成功
- 2026-03-29 22:15 — [Lead/Opus] Vercel 環境変数設定、Supabase Auth リダイレクト URL 修正
- 2026-03-29 22:20 — [User] E2E テスト完了: サインアップ→ログイン→船舶登録→ダッシュボード確認
- 2026-03-29 22:30 — [Lead/Opus] マッチングワークフロー実装 (run_matching.py + run-matching.yml)
- 2026-03-29 22:35 — [Lead/Opus] ダッシュボード修正: JOIN分離, RLS追加, 編集導線, エラー表示改善
- 2026-03-29 22:40 — [Agent/Sonnet] マッチング精度改善: ルールベース強化 + AI プロンプト刷新
- 2026-03-29 22:45 — [Lead/Opus] マッチング再処理ロジック修正 (confidence=0 再処理)
- 2026-03-29 22:50 — [Lead/Opus] ニュースページ: ソースフィルタ + 件数表示
- 2026-03-29 22:50 — [Agent A/Sonnet] 入力バリデーション: GT範囲, 建造年, IMO7桁, 航行区域必須
- 2026-03-29 22:50 — [Agent B/Sonnet] 週次サマリー (weekly_summary.py + weekly-summary.yml)
- 2026-03-29 23:00 — [Lead/Opus] ニュースページネーション (10件) + Mono フォント削除 + OG メタタグ
- 2026-03-29 23:05 — [Lead/Opus] カスタムドメイン: miharikun.vercel.app 設定
- 2026-03-29 23:10 — [Agent/Sonnet] ニュース詳細: OGメタ, 色付き信頼度, リンク改善
- 2026-03-29 23:10 — [Agent/Sonnet] ダッシュボード: 該当のみフィルタ + 件数表示
- 2026-03-29 23:10 — [Agent/Sonnet] LINE 通知: notify_matches.py + ワークフロー連携
- 2026-03-29 23:10 — [Agent/Sonnet] Playwright E2E テスト: 9テスト (landing/news/auth)
- 2026-03-29 23:20 — [Lead/Opus] Vercel 自動デプロイ設定完了 (Git push → 自動ビルド)
- 2026-03-30 00:00 — [Agent/Sonnet] PWA: モバイルナビ + Loading/404/Error ページ
- 2026-03-30 00:00 — [Agent/Sonnet] Settings: user_preferences テーブル + 通知設定フォーム
- 2026-03-30 00:00 — [Agent/Sonnet] Admin: /admin/health システムヘルスダッシュボード
- 2026-03-30 00:00 — [Agent/Sonnet] PWA: Service Worker 4段階キャッシュ + オフライン対応
- 2026-03-30 00:10 — [Agent/Sonnet] Scrapling: NK stealth_fetcher 統合 + graceful fallback
- 2026-03-30 00:10 — [Agent/Sonnet] Golden Set: マッチング精度テスト 19件 (全通過 1.68s)
- 2026-03-30 00:10 — [Agent/Sonnet] Security: TruffleHog + audit + チェックリスト
- 2026-03-30 00:10 — [Agent/Sonnet] MCP: Google Drive MCP 設定 + セットアップガイド
- 2026-03-30 — [Lead/Opus] 推論型コンプライアンスエンジン: maritime_knowledge.py (43条約, 871キーワード) + ship_compliance.py (適用条約自動推論)
- 2026-03-30 — [Lead/Opus] matching.py v3: Stage1(ルール)→Stage0(条約)→Stage2(AI) 3段階パイプライン
- 2026-03-30 — [Lead/Opus] "all" バグ修正: ルールベースが全船適用規制を非該当と判定する問題を修正
- 2026-03-30 — [Lead/Opus] --force オプション追加: 全件再マッチング機能
- 2026-03-30 — [Lead/Opus] Yahoo!ニュース風ポータル: news/page.tsx 6タブ + カードデザイン + Gemini headline生成
- 2026-03-30 — [Lead/Opus] 00007_headline.sql マイグレーション作成
- 2026-03-30 — [User] Gemini 有料プラン移行: Tier 1 Pay-as-you-go, レートリミッター 4秒→0.5秒
- 2026-03-30 — [Lead/Opus] NK 全件取り込み: 40件 upsert, 429ゼロ (有料プラン効果)
- 2026-03-30 — [Lead/Opus] 全件再マッチング: 88件処理, convention_based 57件
- 2026-03-30 — [Lead/Opus] NK ubuntu-latest 移行確定: GHA直接実行 200 OK, Self-hosted Runner 不要に
- 2026-03-30 — [Lead/Opus] 出自隠蔽技術調査: Tailscale推奨（将来のIP ブロック再発時の備え）
- 2026-03-31 — [Lead/Opus] Phase 3 開始: Fleet管理 + e-Gov + headline生成 + UI全面リニューアル
- 2026-03-31 — [Lead/Opus] 推論型コンプライアンスエンジン: maritime_knowledge.py (43条約, 871キーワード) + ship_compliance.py
- 2026-03-31 — [Lead/Opus] matching.py v3: 3段階パイプライン (Stage1ルール→Stage0条約→Stage2 AI)
- 2026-03-31 — [Lead/Opus] 精度極限向上4Step: validation.py (Pydantic), CoVe検証, 単語境界マッチング
- 2026-03-31 — [Lead/Opus] Golden Set テスト29件全通過 (ルール19 + 条約7 + アクション精度3)
- 2026-03-31 — [Lead/Opus] Yahoo!ニュース風ポータル: 専門タブ + headline一括生成 + 適用日ソート
- 2026-03-31 — [Lead/Opus] Fleet管理: /fleet (全船一覧) + /fleet/summary (管理者ビュー)
- 2026-03-31 — [Lead/Opus] e-Gov パブコメスクレイパー (scrape_egov.py + scrape-egov.yml)
- 2026-03-31 — [Lead/Opus] UI/UXプロ化: Badgeシステム + ランディングリデザイン + ダークモード + Sonner
- 2026-03-31 — [Lead/Opus] インフラ: CI/Security Scan/PWA強化 + generate-headlines.yml ワークフロー
- 2026-03-31 — [Lead/Opus] ドキュメント全面更新: PROGRESS.md + HANDOFF.md + STRATEGIC_ROADMAP_v6.md
- 2026-03-29 — [Agent/Opus] ユーザーフィードバック: FeedbackButtons + /api/feedback + 00008_feedback.sql
- 2026-03-29 — [Agent/Opus] 排他キーワード強化: KEYWORD_EXCLUSIONS (8条約) + _passes_exclusion_check()
- 2026-03-29 — [Agent/Opus] バグ修正: ship_compliance.py の convention_id が "UNKNOWN" になる問題
- 2026-03-31 — [Lead/Opus] Vibe OS 導入: plan/PERSONAS.md (4ロール自動憑依) + CLAUDE.md 更新
- 2026-03-31 — [Role C/Opus] Maritime Command Center: ダッシュボード完全リデザイン
- 2026-03-31 — [Role C/Opus] ComplianceGauge (SVGアニメーション) + TimelineStrip (横スクロール) + GlassRegulationCard (Glassmorphism)
- 2026-03-31 — [Role C/Opus] CommandPalette (Cmd+K, 9コマンド) + globals.css (glow/glass/gauge/skeleton)
- 2026-03-31 — [Role C/Opus] framer-motion 導入, Badge ダークファースト化, Sonner dark theme
- 2026-03-31 — [Role D/Opus] Doc-Sync: PROGRESS.md + HANDOFF.md 更新, TSC + next build 全パス
- 2026-03-31 — [Agent A/Role A] publication_requirements.py: 67書籍の自動判定ロジック (4カテゴリ)
- 2026-03-31 — [Agent B/Role B] 00009_publications.sql: publications + ship_publications + RLS + API route
- 2026-03-31 — [Agent C/Role C] /ships/[id]/publications: Glassmorphism UI + インライン版数編集
- 2026-03-31 — [Agent A/Role A] test_publication_requirements.py: 51テスト全通過
- 2026-03-31 — [Role D/Opus] 統合チェック: 121テスト全通過 + TSC + next build (18ルート) 全パス
- 2026-03-31 — [Role C/Opus] ダッシュボード書籍サマリー + ニュース書籍タブ + 導線追加
- 2026-03-31 — [Agent A/Role A] 00010_radio_equipment.sql + 無線設備書籍5件 + フォームUI更新
- 2026-03-31 — [Agent B/Role B] seed_publications.py + check_publication_updates.py + GHA 2ワークフロー
- 2026-03-31 — [Agent C/Role C] G/A/R ステータス可視化 (発光ドット + 行ハイライト + サマリーカウント)
- 2026-03-31 — [Role D/Opus] 全ドキュメント最終同期: HANDOFF.md + STRATEGIC_ROADMAP_v6.md + PROGRESS.md
- 2026-03-31 — [Agent A/Role A] 書籍ID統一: PUB_X_NNN → 記述的ID (67件全件) + applicability_rules JSON追加
- 2026-03-31 — [Agent A/Role A] 2026年版更新: 潮汐表/天測暦/灯台表/海図総目録/NK Rules を2026年版に
- 2026-03-31 — [Agent A/Role B] 00011_publications_v2.sql: applicability_rules JSONB + last_verified_at + verified_by
- 2026-03-31 — [Agent C/Role C] Verified バッジ: 年次刊行物の2026年版を ✓ Verified 2026 で表示
- 2026-03-31 — [Agent C/Role C] publication-data.ts: 2026年版更新 + フォールバック化コメント追加
- 2026-03-31 — [Role D/Opus] 統合チェック: 121テスト全通過 + TSC + next build 全パス + 旧IDゼロ確認
- 2026-04-01 — [User] 00011_publications_v2.sql を Supabase で実行 ✅
- 2026-04-01 — [Role D/Opus] seed-publications 再実行成功: 67書籍 (新ID + applicability_rules + 2026年版)
- 2026-04-01 — [Role D/Opus] 全ドキュメント v7 方針更新: STRATEGIC_ROADMAP_v6.md→v7, HANDOFF.md, PROGRESS.md, CLAUDE.md
