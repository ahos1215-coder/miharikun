# 引継ぎ書 — MIHARIKUN

> **次のセッションはこのファイルから読み始めてください。**
> 最終更新: 2026-03-30

---

## 1. 今どこにいるか

**Phase 2 完了・本番稼働中。推論型コンプライアンスエンジン実装済み。** https://miharikun.vercel.app

```
Phase 0: 基盤構築              ✅
Phase 1 R1: スクレイパー       ✅
Phase 1 R2: DB + マッチング    ✅
Phase 2: Ship Specs + UI       ✅ 完了（コンプライアンスエンジン + Yahoo!ニュース風UI）
Phase 3: Fleet 管理 + 拡張     📋 未着手
```

---

## 2. 最初にやること

```
1. plan/PROGRESS.md を読んで詳細を把握
2. Phase 3（Fleet 管理）に進むか、既存機能の改善を続けるか判断
```

---

## 3. 本番環境

| 項目 | 値 |
|------|-----|
| Public URL | https://miharikun.vercel.app |
| デプロイ | Vercel 自動デプロイ (git push → 自動ビルド) |
| DB | Supabase (PostgreSQL + Auth + RLS) |
| AI | Google Gemini 2.5 Flash API (**Tier 1 Pay-as-you-go**) |
| バッチ | GitHub Actions (9 ワークフロー) |
| リポジトリ | Public (GHA 無制限のため) |

### Vercel 環境変数 (設定済み)
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

### GitHub Secrets (設定済み)
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_API_KEY`

### 未設定の Secrets
- `LINE_NOTIFY_TOKEN` — LINE 通知を有効化するために必要
- `RESEND_API_KEY` — 週次サマリーメール送信に必要

---

## 4. DB テーブル

| テーブル | 用途 |
|---------|------|
| `regulations` | 規制情報 (NK + MLIT) |
| `pending_queue` | Gemini 分類失敗時のリトライキュー |
| `mlit_crawl_state` | MLIT クローラーの BFS 状態管理 |
| `ship_profiles` | ユーザーの船舶スペック登録 |
| `user_matches` | マッチング結果 (船舶×規制) |
| `user_preferences` | 通知設定 (LINE/メール/頻度) |

マイグレーション: `supabase/migrations/` (7 ファイル、全て適用済み)

---

## 5. GitHub Actions ワークフロー (全 9 + 1)

| ファイル | スケジュール | 内容 |
|---------|------------|------|
| `scrape-nk.yml` | 日次 JST 07:00 | ClassNK スクレイパー (**ubuntu-latest**) |
| `scrape-mlit-rss.yml` | 日次 JST 08:00 | 国交省 RSS スクレイパー |
| `scrape-mlit-crawl.yml` | 週次 日曜 JST 06:00 | 国交省 BFS クローラー |
| `run-matching.yml` | スクレイパー完了後 | マッチングエンジン + LINE 通知 |
| `process-queue.yml` | 毎時 | pending_queue リトライ |
| `health-check.yml` | 6 時間毎 | システムヘルスチェック |
| `weekly-summary.yml` | 週次 月曜 JST 09:00 | 週次サマリーメール |
| `ci.yml` | PR / push | CI (lint + test + build) |
| `security-scan.yml` | 週次 / PR | TruffleHog + npm/pip audit |
| `notify-on-failure.yml` | — | 再利用可能失敗通知 (called by others) |

**重要: NK は ubuntu-latest で動作する。Self-hosted Runner は不要。**
ClassNK のブロックは IP ベースではなく UA ベースだった。UA 修正済みのため GHA 直接実行が可能。

---

## 6. テスト

| 種別 | 件数 | ファイル |
|------|------|---------|
| pytest 単体テスト | 41 | `tests/python/test_scrape_nk.py` |
| Golden Set 精度テスト | 19 | `tests/python/test_matching_golden.py` |
| Playwright E2E | 9 | `frontend/e2e/{landing,news,auth}.spec.ts` |
| **合計** | **69** | |

---

## 7. 知っておくべきこと

### アーキテクチャ概要
```
[ユーザー] → [Vercel (Next.js 16)] → [Supabase (Auth + DB + RLS)]
                                            ↑
[GitHub Actions (ubuntu-latest)] → [スクレイパー] → [Gemini AI] → [Supabase upsert]
```

### Gemini Tier 1 Pay-as-you-go
- Free Tier から Tier 1 に移行済み（2026-03-30）
- レートリミッター: 4秒→0.5秒に短縮
- 429 エラーはほぼ解消（NK 40件 upsert で 429 ゼロ）
- `pending_queue` + `process-queue.yml` は引き続きフォールバックとして稼働

### 推論型コンプライアンスエンジン (3段階)
1. **Stage 1: ルールベース** — 6 条件で高速除外 (船種・GT・旗国・航行区域・建造年・カテゴリ)
2. **Stage 0: 条約ベース** — `maritime_knowledge.py` の 43 条約ルール + 871 キーワードで条約適用を自動推論。`ship_compliance.py` が船舶スペック 5 項目から適用条約を推定
3. **Gemini AI** — Stage 0/1 を通過した規制に対して精密判定 (confidence + reason + citations)

**主要ファイル:**
- `scripts/utils/maritime_knowledge.py` — 条約ルール・キーワード・国内法マッピング
- `scripts/utils/ship_compliance.py` — 船舶スペックから適用条約を自動推論
- `scripts/utils/matching.py` — 3段階マッチングパイプライン (v3)

### Vercel ドメイン
- `miharikun.vercel.app` エイリアスはデプロイ後に手動更新が必要な場合がある (Vercel domain settings)
- 自動デプロイ自体は git push で動作する

### 過去の罠 (再発防止)
1. `send_line_notify` は存在しない → 正しくは `send_alert`
2. `scripts/` から `utils/` を import するには `sys.path.insert(0, os.path.dirname(__file__))` 必須
3. ClassNK は **UA ベース**でブロック (IP ではない) → Chrome UA で解決済み
4. Supabase の空文字 Secret が環境変数のデフォルト値を上書きする
5. `classify_pdf` は例外ではなく `status=pending` を返す
6. MLIT スクレイパーのフィールド名は DB スキーマと一致させること (`confidence` not `confidence_score`)
7. PostgREST upsert は PK 以外の UNIQUE 制約には `on_conflict` パラメータが必要

### 設計文書の優先順位
1. `plan/STRATEGIC_PIVOT_v5.md` — 最上位の意思決定文書
2. `plan/MARITIME_PROJECT_BLUEPRINT_v4.md` — 技術詳細 (v5 と矛盾する場合は v5 優先)
3. `CLAUDE.md` — コーディング規約・運用ルール

---

## 8. 既知の問題

- **miharikun.vercel.app エイリアス**: デプロイ後に Vercel domain settings で手動更新が必要な場合がある
- **LINE_NOTIFY_TOKEN 未設定**: LINE 通知機能は実装済みだが Token 未設定のため動作しない
- **RESEND_API_KEY 未設定**: 週次サマリーメール機能は実装済みだが API キー未設定のため動作しない

---

## 9. 次のフェーズ (Phase 3)

- [ ] Fleet 管理 (複数船一括登録・管理)
- [ ] e-Gov パブコメ監視
- [ ] LINE リアルタイム通知 (TOKEN 設定後)
- [ ] ユーザーフィードバック (AI 精度改善ループ)
- [ ] Google Drive MCP 認証設定 (GOOGLE_SERVICE_ACCOUNT_JSON_PATH)
- [ ] マッチング精度の継続改善 (convention_based 57件の精度検証)
- [ ] ニュースポータルの UX 改善 (headline 表示の最適化)

---

## 10. プロジェクト全体のファイル構成

```
miharikun/
├── CLAUDE.md                              # 運用ルール + コーディング規約
├── plan/                                  # 設計・進捗・引継ぎ文書
│   ├── PROGRESS.md                        # 唯一の進捗ソース・オブ・トゥルース
│   ├── HANDOFF.md                         # セッション引継ぎ (このファイル)
│   ├── STRATEGIC_PIVOT_v5.md              # 最上位意思決定文書
│   ├── MARITIME_PROJECT_BLUEPRINT_v4.md   # 技術詳細設計
│   ├── SELF_HOSTED_RUNNER_SETUP.md        # Runner セットアップ手順 (現在不要)
│   ├── GEMINI_ACCURACY_REPORT.md          # AI 精度検証レポート
│   ├── AGENT_TEAMS_PLAN.md               # エージェント並列開発フレームワーク
│   ├── IMPLEMENTATION_GUIDE.md            # 初期実装ガイド
│   ├── MCP_SETUP.md                       # Google Drive MCP 設定ガイド
│   └── SECURITY_CHECKLIST.md              # セキュリティチェックリスト
├── frontend/                              # Next.js 16 フロントエンド
│   ├── next.config.ts
│   ├── package.json
│   ├── playwright.config.ts
│   ├── tsconfig.json
│   ├── public/
│   │   ├── icon.svg
│   │   ├── manifest.json
│   │   ├── offline.html                   # PWA オフラインページ
│   │   └── sw.js                          # Service Worker (4段階キャッシュ)
│   ├── e2e/                               # Playwright E2E テスト (9件)
│   │   ├── landing.spec.ts
│   │   ├── news.spec.ts
│   │   └── auth.spec.ts
│   └── src/
│       ├── middleware.ts                   # 認証ミドルウェア (未認証→/login)
│       ├── app/
│       │   ├── layout.tsx                 # ルートレイアウト
│       │   ├── page.tsx                   # ランディングページ
│       │   ├── loading.tsx                # グローバルローディング
│       │   ├── error.tsx                  # エラーバウンダリ
│       │   ├── not-found.tsx              # 404 ページ
│       │   ├── globals.css
│       │   ├── favicon.ico
│       │   ├── login/page.tsx             # ログイン/サインアップ
│       │   ├── auth/callback/route.ts     # Auth コールバック
│       │   ├── news/page.tsx              # 全規制一覧 (フィルタ+ページネーション)
│       │   ├── news/[id]/page.tsx         # 規制詳細 (AI要約+引用+OGメタ)
│       │   ├── dashboard/page.tsx         # パーソナライズダッシュボード (要認証)
│       │   ├── ships/new/page.tsx         # 船舶新規登録 (要認証)
│       │   ├── ships/[id]/page.tsx        # 船舶詳細 (要認証)
│       │   ├── ships/[id]/ship-edit-form.tsx  # 船舶編集フォーム
│       │   ├── settings/page.tsx          # 通知設定 (要認証)
│       │   ├── settings/SettingsForm.tsx   # 設定フォームコンポーネント
│       │   ├── admin/health/page.tsx      # システムヘルスダッシュボード
│       │   └── api/send-summary/route.ts  # 週次サマリー API
│       ├── components/
│       │   ├── nav.tsx                    # ナビゲーション (モバイルハンバーガー対応)
│       │   ├── footer.tsx                 # 免責事項フッター
│       │   ├── sw-register.tsx            # Service Worker 登録
│       │   └── theme-provider.tsx         # ダークモード対応
│       └── lib/
│           ├── types.ts                   # TypeScript 型定義 + 日本語ラベル
│           └── supabase/
│               ├── client.ts              # ブラウザ用クライアント
│               ├── server.ts              # サーバー用クライアント
│               └── middleware.ts          # Auth ミドルウェアヘルパー
├── scripts/                               # Python バックエンド
│   ├── scrape_nk.py                       # ClassNK スクレイパー
│   ├── scrape_mlit_rss.py                 # 国交省 RSS スクレイパー
│   ├── scrape_mlit_crawl.py               # 国交省 BFS クローラー
│   ├── run_matching.py                    # マッチングエンジン実行
│   ├── process_queue.py                   # pending_queue リトライ
│   ├── notify_matches.py                  # LINE 通知送信
│   ├── weekly_summary.py                  # 週次サマリー生成
│   ├── health_check.py                    # ヘルスチェック
│   ├── requirements.txt                   # Python 依存パッケージ
│   └── utils/                             # 共通ユーティリティ
│       ├── __init__.py
│       ├── gemini_client.py               # Gemini API (2モデル切替 + 指数バックオフ)
│       ├── supabase_client.py             # Supabase REST (7メソッド)
│       ├── matching.py                    # マッチングエンジン v3 (3段階: ルール→条約→AI)
│       ├── maritime_knowledge.py          # 43条約ルール + 871キーワード + 国内法マッピング
│       ├── ship_compliance.py             # 船舶スペック→適用条約自動推論
│       ├── line_notify.py                 # LINE 通知 (severity 別スロットリング)
│       ├── gdrive_client.py               # Google Drive API v3
│       ├── pdf_preprocess.py              # PDF 品質チェック 4段階
│       └── stealth_fetcher.py             # Scrapling StealthyFetcher + fallback
├── .github/workflows/                     # GitHub Actions (9 + 1)
│   ├── scrape-nk.yml                      # NK 日次 (ubuntu-latest)
│   ├── scrape-mlit-rss.yml                # MLIT RSS 日次
│   ├── scrape-mlit-crawl.yml              # MLIT クロール週次
│   ├── run-matching.yml                   # マッチング + LINE 通知
│   ├── process-queue.yml                  # 毎時リトライ
│   ├── health-check.yml                   # 6時間毎ヘルスチェック
│   ├── weekly-summary.yml                 # 週次サマリーメール
│   ├── ci.yml                             # CI (lint + test + build)
│   ├── security-scan.yml                  # TruffleHog + audit
│   └── notify-on-failure.yml              # 再利用可能失敗通知
├── supabase/migrations/                   # DB マイグレーション (6ファイル、全適用済み)
│   ├── 00001_initial_schema.sql           # regulations + pending_queue
│   ├── 00002_mlit_crawl.sql               # mlit_crawl_state
│   ├── 00003_rls_policies.sql             # RLS ポリシー
│   ├── 00004_indexes.sql                  # インデックス
│   ├── 00005_ship_profiles.sql            # ship_profiles + user_matches
│   ├── 00006_user_preferences.sql         # user_preferences
│   └── 00007_headline.sql                 # regulations.headline カラム追加
└── tests/python/                          # テスト (69件)
    ├── __init__.py
    ├── conftest.py                        # pytest fixtures
    ├── test_scrape_nk.py                  # NK 単体テスト (41件)
    └── test_matching_golden.py            # マッチング精度テスト (19件)
```
