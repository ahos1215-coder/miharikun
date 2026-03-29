# 引継ぎ書 — MIHARIKUN Phase 2 デプロイ + 仕上げ

> **次のセッションはこのファイルから読み始めてください。**
> 最終更新: 2026-03-29 22:00 JST

---

## 1. 今どこにいるか

**Phase 2 フロントエンド MVP 実装済み。Vercel デプロイ待ち。**

```
Phase 0: 基盤構築              ✅ コミット済み
Phase 1 R1: スクレイパー       ✅ コミット済み（41テスト通過）
Phase 1 R2: DB + マッチング    ✅ 完了（NK 3件 + MLIT 3件 本番検証済み）
Phase 2: Ship Specs + UI       ⏳ MVP 実装済み、デプロイ待ち ← 今ここ
Phase 3: Fleet 管理 + 拡張     📋 未着手
```

---

## 2. 最初にやること

```
1. plan/PROGRESS.md を読んで詳細を把握
2. ユーザーに以下の手動作業が完了したか確認:
   a) Vercel デプロイ + 環境変数設定
   b) Supabase Auth メール設定
3. 完了していれば → E2E テスト（ログイン→船舶登録→ダッシュボード）
4. 未完了であれば → ユーザーに作業を促す
```

---

## 3. Phase 2 実装状況

### 完了済み（3fa5105）

| ファイル | 種類 | 内容 |
|---------|------|------|
| `src/lib/supabase/{client,server,middleware}.ts` | 基盤 | Supabase SSR クライアント |
| `src/middleware.ts` | 基盤 | 認証ミドルウェア（未認証→/login リダイレクト） |
| `src/lib/types.ts` | 基盤 | TypeScript 型定義 + 日本語ラベル |
| `src/components/{nav,footer}.tsx` | 共通 | ナビゲーション + 免責事項フッター |
| `src/app/page.tsx` | Public | ランディングページ |
| `src/app/login/page.tsx` | Public | ログイン/サインアップ |
| `src/app/auth/callback/route.ts` | Public | Auth コールバック |
| `src/app/news/page.tsx` | Public | 全規制一覧（重要度バッジ付き） |
| `src/app/news/[id]/page.tsx` | Public | 規制詳細（AI要約 + 引用） |
| `src/app/dashboard/page.tsx` | 要認証 | パーソナライズダッシュボード |
| `src/app/ships/new/page.tsx` | 要認証 | 船舶新規登録 |
| `src/app/ships/[id]/page.tsx` + `ship-edit-form.tsx` | 要認証 | 船舶編集・削除 |
| `src/app/settings/page.tsx` | 要認証 | 通知設定（プレースホルダー） |

**TypeScript コンパイル: エラーゼロ**

### ユーザー手動作業（デプロイに必要）

#### A. Vercel デプロイ
1. Vercel で GitHub リポジトリをインポート
2. Root Directory を `frontend` に設定
3. 環境変数を追加:
   - `NEXT_PUBLIC_SUPABASE_URL` — Supabase プロジェクト URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Supabase anon key

#### B. Supabase Auth メール設定
- Supabase ダッシュボード → Authentication → Email Templates
- SMTP設定: Resend or カスタム SMTP（デフォルトでも動くが送信制限あり）

---

## 4. 残タスク

### Phase 2 仕上げ
- [ ] Vercel デプロイ + 環境変数設定
- [ ] Supabase Auth メール設定
- [ ] E2E テスト（サインアップ → 船舶登録 → ダッシュボード → ニュース閲覧）
- [ ] 初期ロード < 50KB 確認（Lighthouse）
- [ ] 入力バリデーション強化（/ships/new フォーム）

### Phase 2 → Phase 3 の間
- [ ] 週次サマリーメール（GHA ワークフロー + Resend/nodemailer）
- [ ] /settings の通知トグル実装
- [ ] Service Worker キャッシュ（オフライン対応）

---

## 5. 知っておくべきこと

### アーキテクチャ概要
```
[ユーザー] → [Vercel (Next.js 16)] → [Supabase (Auth + DB + RLS)]
                                            ↑
[GitHub Actions] → [スクレイパー] → [Gemini AI] → [Supabase upsert]
                      ↑
              [Self-hosted Runner (NK のみ)]
```

### Self-hosted Runner
- ランナー名: `B-A59000-089` (Windows, self-hosted)
- **PC 再起動後は `C:\actions-runner\run.cmd` を再実行する必要あり**

### 過去の罠（再発防止）
1. `send_line_notify` は存在しない → 正しくは `send_alert`
2. `scripts/` から `utils/` を import するには `sys.path.insert` 必須
3. ClassNK は GHA IP + bot UA の両方をブロック → Self-hosted Runner + Chrome UA で解決
4. Supabase の空文字 Secret が環境変数のデフォルト値を上書きする
5. `classify_pdf` は例外ではなく `status=pending` を返す
6. MLIT スクレイパーのフィールド名は DB スキーマと一致させること（`confidence` not `confidence_score`）
7. PostgREST upsert は PK 以外の UNIQUE 制約には `on_conflict` パラメータが必要

### 設計文書の優先順位
1. `plan/STRATEGIC_PIVOT_v5.md` — 最上位の意思決定文書
2. `plan/MARITIME_PROJECT_BLUEPRINT_v4.md` — 技術詳細（v5 と矛盾する場合は v5 優先）
3. `CLAUDE.md` — コーディング規約・運用ルール

---

## 6. 必要な環境変数

### GitHub Secrets（バックエンド用）
| 変数名 | 状態 | 備考 |
|--------|------|------|
| `SUPABASE_URL` | ✅ 設定済み | |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ 設定済み | |
| `GEMINI_API_KEY` | ✅ 設定済み | |
| `LINE_NOTIFY_TOKEN` | 未設定 | Phase 3 通知機能で必要 |

### Vercel 環境変数（フロントエンド用）
| 変数名 | 状態 | 備考 |
|--------|------|------|
| `NEXT_PUBLIC_SUPABASE_URL` | ❌ **未設定** | Supabase プロジェクト URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ❌ **未設定** | Supabase anon key（公開OK） |

---

## 7. プロジェクト全体のファイル構成

```
miharikun/
├── CLAUDE.md                          # 運用ルール + コーディング規約
├── plan/                              # 設計・進捗・引継ぎ文書
│   ├── PROGRESS.md                    # 唯一の進捗ソース・オブ・トゥルース
│   ├── HANDOFF.md                     # セッション引継ぎ（このファイル）
│   ├── STRATEGIC_PIVOT_v5.md          # 最上位意思決定文書
│   ├── MARITIME_PROJECT_BLUEPRINT_v4.md # 技術詳細設計
│   ├── SELF_HOSTED_RUNNER_SETUP.md    # Runner セットアップ手順
│   ├── GEMINI_ACCURACY_REPORT.md      # AI 精度検証レポート
│   ├── AGENT_TEAMS_PLAN.md            # エージェント並列開発フレームワーク
│   └── IMPLEMENTATION_GUIDE.md        # 初期実装ガイド
├── frontend/                          # Next.js 16 フロントエンド
│   └── src/
│       ├── app/                       # 8 ルート（page.tsx）
│       ├── components/                # Nav, Footer
│       └── lib/                       # Supabase, 型定義
├── scripts/                           # Python バックエンド
│   ├── scrape_nk.py                   # ClassNK スクレイパー (856行)
│   ├── scrape_mlit_rss.py             # 国交省 RSS (584行)
│   ├── scrape_mlit_crawl.py           # 国交省クロール (732行)
│   ├── process_queue.py               # 失敗リトライ
│   ├── health_check.py                # ヘルスチェック
│   └── utils/                         # 共通ユーティリティ
│       ├── matching.py                # マッチングエンジン (452行)
│       ├── gemini_client.py           # Gemini API
│       ├── supabase_client.py         # Supabase REST
│       ├── line_notify.py             # LINE 通知
│       ├── gdrive_client.py           # Google Drive
│       └── pdf_preprocess.py          # PDF 品質チェック
├── .github/workflows/                 # 6 ワークフロー
│   ├── scrape-nk.yml                  # NK 日次 (self-hosted)
│   ├── scrape-mlit-rss.yml            # MLIT RSS 日次
│   ├── scrape-mlit-crawl.yml          # MLIT クロール週次
│   ├── process-queue.yml              # 毎時リトライ
│   ├── health-check.yml               # 6時間毎
│   └── notify-on-failure.yml          # 失敗通知（再利用可能）
├── supabase/migrations/               # DB マイグレーション (5ファイル)
└── tests/python/                      # pytest (41テスト)
```
