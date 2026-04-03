> **⚠️ アーカイブ文書**: このドキュメントは歴史的記録として保持されています。現在のシステム構成は `plan/HANDOFF.md` を参照してください。

# 実装指示書パック — Maritime Regulations Monitor
Last updated: 2026-03-29

> **本ファイルは Claude Code（エージェント）がリポジトリを初期構築する際に参照する実装指示書です。**
> 設計書 v4（`plan/MARITIME_PROJECT_BLUEPRINT_v4.md`）と併せて使用してください。

---

# ① CLAUDE.md（プロジェクトルート直下に配置）

```markdown
# CLAUDE.md — Maritime Regulations Monitor

## プロジェクト概要
海事規制の自動収集・AI分類・パーソナライズ通知サービス。
設計書: `plan/MARITIME_PROJECT_BLUEPRINT_v4.md`

## テックスタック
- **Frontend**: Next.js 14+ (App Router) / TypeScript / Tailwind CSS
- **Backend 処理**: GitHub Actions (Python 3.11+) — スクレイピング・PDF解析・Gemini呼び出し
- **DB**: Supabase (PostgreSQL + Auth + RLS)
- **AI**: Google Gemini 2.5 Flash API
- **ストレージ**: Google Drive API (PDF全文テキスト保管)
- **ホスティング**: Vercel (Next.js) / GitHub Actions (バッチ)
- **通知**: LINE Notify + メール（Resend or nodemailer）

## アーキテクチャ原則（厳守）
1. **重い処理は GHA、軽い処理は Vercel**
   - GHA: スクレイピング、PDF ダウンロード、Gemini API 呼び出し、DB書き込み
   - Vercel: ユーザー認証、DB 読み取り、UI 表示
   - **Vercel API Routes で Gemini を呼ばない**（10秒タイムアウト）
2. **Supabase がソース・オブ・トゥルース**
   - フロントから Supabase 直アクセスは anon key + RLS 経由のみ
   - GHA からの書き込みは SERVICE_ROLE_KEY（RLS バイパス）
3. **secrets は環境変数のみ。コードにハードコードしない**
4. **リポジトリは Public**（GHA 無制限のため）
   - secrets は GitHub Secrets / Vercel env / Supabase env に設定
   - **API キーをコミットしたら即座にローテーション**

## コーディング規約
- TypeScript: strict mode、any 禁止
- Python: type hints 推奨、f-string 使用
- インデント: 2 spaces (TS/JS)、4 spaces (Python)
- コミットメッセージ: `feat:`, `fix:`, `chore:`, `docs:` プレフィックス
- 日本語コメント OK（ユーザーが日本語話者）
- console.log はデバッグ後に削除、本番は構造化ログ

## やらないこと（ハードルール）
- Flask / Render は使わない（v2 で廃止済み）
- Vercel API Routes で PDF 解析や Gemini 呼び出しをしない
- secrets をコード・コミット・ログに含めない
- NEXT_PUBLIC_ プレフィックスに secrets を入れない
- フロントから SERVICE_ROLE_KEY を使わない
- node_modules/ をコミットしない
- requirements.txt のバージョンを固定しないまま放置しない

## テスト方針
- Python スクレイパー: pytest + VCR.py（HTTP レスポンスのカセット記録）
- Gemini 分類: スナップショットテスト（既知のPDFに対する期待出力を保存）
- Next.js: Vitest + React Testing Library（コンポーネント単体）
- E2E: 将来 Playwright（Phase 3以降）

## デプロイ
- main ブランチへの push で Vercel 自動デプロイ
- GHA ワークフローは cron ベース（手動 dispatch も可能に設定）
- DB マイグレーション: `supabase/migrations/` に SQL ファイルを追加

## plan/ フォルダ
設計書・仕様書・意思決定ログを管理。コードを書く前に必ず参照。
- `MARITIME_PROJECT_BLUEPRINT_v4.md` — 設計書本体
- `ENV.md` — 環境変数一覧
- `INDEX.md` — ファイルマップ
```

---

# ② ENV.md（plan/ 配下に配置）

```markdown
# ENV.md — 環境変数一覧
Last updated: 2026-03-29

## Supabase（Project B — MEGRIBI とは別プロジェクト）

| 変数名 | 設定先 | 用途 |
|--------|--------|------|
| `NEXT_PUBLIC_SUPABASE_URL` | Vercel env | フロントからの Supabase 接続 |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Vercel env | フロントからの RLS 付きアクセス |
| `SUPABASE_URL` | GHA secrets | バッチ処理からの接続 |
| `SUPABASE_SERVICE_ROLE_KEY` | GHA secrets + Vercel env (server only) | RLS バイパス（書き込み用） |

## Gemini API（別 GCP プロジェクト — MEGRIBI とは独立枠）

| 変数名 | 設定先 | 用途 |
|--------|--------|------|
| `GEMINI_API_KEY` | GHA secrets | PDF 分類・要約 |
| `GEMINI_MODEL` | GHA secrets | 使用モデル（デフォルト: `gemini-2.5-flash`） |
| `GEMINI_FALLBACK_MODEL` | GHA secrets | フォールバック（デフォルト: `gemini-2.0-flash`） |

## Google Drive（PDF 全文テキスト保管）

| 変数名 | 設定先 | 用途 |
|--------|--------|------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | GHA secrets | サービスアカウント認証情報（JSON 全文） |
| `GOOGLE_DRIVE_FOLDER_ID` | GHA secrets | 保存先フォルダ ID |

## LINE Notify（管理者通知）

| 変数名 | 設定先 | 用途 |
|--------|--------|------|
| `LINE_NOTIFY_TOKEN` | GHA secrets | エラー通知・ヘルスチェック通知 |

## メール通知（週次サマリー・証明書リマインダー）

| 変数名 | 設定先 | 用途 |
|--------|--------|------|
| `RESEND_API_KEY` | GHA secrets + Vercel env | メール送信（Resend Free: 100通/日） |
| `ADMIN_EMAIL` | GHA secrets | 管理者メールアドレス |

## アプリケーション設定

| 変数名 | 設定先 | 用途 |
|--------|--------|------|
| `NEXT_PUBLIC_APP_URL` | Vercel env | アプリの公開 URL |
| `SCRAPE_USER_AGENT` | GHA secrets | スクレイピング時の User-Agent |

## ローカル開発

`.env.local`（`.gitignore` 対象）:
```env
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## 注意事項
- MEGRIBI と Supabase/Gemini のプロジェクトを分けているため、キーは完全に別物
- `GOOGLE_SERVICE_ACCOUNT_JSON` は JSON 全文を GitHub Secret に格納（改行含む）
- `SCRAPE_USER_AGENT` は礼儀正しいボットを示す文字列にする
  例: `MaritimeRegsMonitor/1.0 (+https://github.com/YOUR_REPO; contact@example.com)`
```

---

# ③ INDEX.md（plan/ 配下に配置 — ディレクトリ構成）

```markdown
# INDEX.md — ファイルマップ
Last updated: 2026-03-29

## ディレクトリ構成

```
maritime-regs-monitor/
├── CLAUDE.md                          # Claude Code 用プロジェクトルール
├── README.md                          # プロジェクト概要（公開用）
├── package.json                       # ルート（ワークスペース設定のみ）
│
├── plan/                              # 設計書・仕様書（コードではない）
│   ├── MARITIME_PROJECT_BLUEPRINT_v4.md
│   ├── ENV.md
│   ├── INDEX.md                       # ← このファイル
│   ├── DECISIONS.md                   # 意思決定ログ（随時追記）
│   └── GEMINI_PROMPT.md               # Gemini 分類プロンプト仕様
│
├── frontend/                          # Next.js アプリケーション
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.js
│   ├── .env.local                     # ローカル環境変数（.gitignore）
│   │
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx             # ルートレイアウト（免責フッター含む）
│   │   │   ├── page.tsx               # LP（/）
│   │   │   │
│   │   │   ├── (auth)/
│   │   │   │   ├── login/page.tsx     # ログイン
│   │   │   │   └── signup/page.tsx    # 新規登録
│   │   │   │
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx           # パーソナライズダッシュボード（Pro）
│   │   │   │
│   │   │   ├── news/
│   │   │   │   ├── page.tsx           # 規制ニュース一覧（6カテゴリタブ）
│   │   │   │   └── [id]/page.tsx      # 規制詳細（AI要約 + 根拠引用）
│   │   │   │
│   │   │   ├── crew/
│   │   │   │   ├── page.tsx           # 乗組員プロファイル管理
│   │   │   │   └── certificates/
│   │   │   │       └── page.tsx       # 証明書期限管理
│   │   │   │
│   │   │   ├── ships/
│   │   │   │   └── page.tsx           # 船舶スペック管理（Phase 3）
│   │   │   │
│   │   │   ├── admin/
│   │   │   │   └── health/
│   │   │   │       └── page.tsx       # ヘルスダッシュボード（乗船前チェック）
│   │   │   │
│   │   │   ├── settings/
│   │   │   │   └── page.tsx           # 通知設定
│   │   │   │
│   │   │   └── api/                   # API Routes（軽い読み書きのみ）
│   │   │       ├── health/route.ts    # ヘルスチェック API
│   │   │       └── match/route.ts     # マッチング結果取得
│   │   │
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Header.tsx
│   │   │   │   ├── Footer.tsx         # 免責事項を含む
│   │   │   │   └── Sidebar.tsx
│   │   │   ├── news/
│   │   │   │   ├── NewsList.tsx
│   │   │   │   ├── NewsCard.tsx
│   │   │   │   ├── CategoryTabs.tsx
│   │   │   │   └── ConfidenceBadge.tsx # AI確度バッジ（緑/黄/赤）
│   │   │   ├── crew/
│   │   │   │   ├── CertificateList.tsx
│   │   │   │   ├── CertificateForm.tsx
│   │   │   │   └── ExpiryAlert.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── MatchedRegulations.tsx
│   │   │   │   └── SourceStatus.tsx   # ソース別最終更新日
│   │   │   └── ui/                    # 共通 UI（Button, Card, Badge 等）
│   │   │
│   │   └── lib/
│   │       ├── supabase/
│   │       │   ├── client.ts          # ブラウザ用 Supabase クライアント
│   │       │   ├── server.ts          # サーバー用（SERVICE_ROLE_KEY）
│   │       │   └── types.ts           # DB 型定義（supabase gen types）
│   │       ├── matching/
│   │       │   └── matchRegulations.ts # 船スペック × 規制のマッチングロジック
│   │       └── utils/
│   │           └── formatDate.ts
│   │
│   └── public/
│       └── favicon.ico
│
├── scripts/                           # Python スクレイパー・バッチ処理
│   ├── requirements.txt
│   ├── scrape_nk.py                   # NK テクニカルインフォメーション
│   ├── scrape_mlit_rss.py             # 国交省 RSS（第1層）
│   ├── scrape_mlit_crawl.py           # 国交省 クロール（第2層）
│   ├── scrape_egov.py                 # e-Gov パブコメ（第3層）
│   ├── classify_gemini.py             # Gemini 分類パイプライン
│   ├── process_pending_queue.py       # 未処理キュー再処理
│   ├── health_check.py                # ヘルスチェック実行
│   ├── weekly_summary.py              # 週次サマリーメール生成
│   └── utils/
│       ├── supabase_client.py         # Supabase Python クライアント
│       ├── gemini_client.py           # Gemini API ラッパー（フォールバック付き）
│       ├── gdrive_client.py           # Google Drive API ラッパー
│       ├── line_notify.py             # LINE 通知ユーティリティ
│       └── pdf_preprocess.py          # PDF 品質チェック（サイズ、OCR判定）
│
├── .github/
│   └── workflows/
│       ├── scrape-nk.yml              # NK 日次スクレイピング（JST 07:00）
│       ├── scrape-mlit-rss.yml        # 国交省 RSS 日次（JST 08:00）
│       ├── scrape-mlit-crawl.yml      # 国交省 クロール 週次（日曜 JST 06:00）
│       ├── scrape-egov.yml            # e-Gov パブコメ 週次（月曜 JST 09:00）
│       ├── process-queue.yml          # 未処理キュー再処理 日次（JST 12:00）
│       ├── health-check.yml           # ヘルスチェック 日次（JST 12:00）
│       ├── weekly-summary.yml         # 週次サマリーメール（水曜 JST 09:00）
│       └── notify-on-failure.yml      # 共通失敗通知（再利用ワークフロー）
│
├── supabase/
│   └── migrations/
│       ├── 00001_initial_schema.sql   # regulations, ship_profiles, crew_profiles
│       ├── 00002_mlit_crawl.sql       # mlit_crawl_state
│       ├── 00003_rls_policies.sql     # Row Level Security
│       └── 00004_indexes.sql          # パフォーマンスインデックス
│
└── tests/
    ├── python/
    │   ├── test_scrape_nk.py
    │   ├── test_classify_gemini.py    # スナップショットテスト
    │   └── fixtures/                  # テスト用 PDF・HTML
    └── frontend/
        └── components/
            └── ConfidenceBadge.test.tsx
```

## GHA ワークフロー一覧

| ファイル | 頻度 | 内容 |
|---------|------|------|
| `scrape-nk.yml` | 日次 07:00 JST | NK TEC 一覧取得 → 新規 PDF → Gemini 分類 → Supabase |
| `scrape-mlit-rss.yml` | 日次 08:00 JST | 国交省 RSS → キーワードフィルタ → Gemini 分類 |
| `scrape-mlit-crawl.yml` | 週次 日曜 06:00 JST | `/maritime/` 全体クロール → diff → 新規 PDF 処理 |
| `scrape-egov.yml` | 週次 月曜 09:00 JST | e-Gov パブコメ検索 → 海事関連フィルタ |
| `process-queue.yml` | 日次 12:00 JST | `pending_queue` テーブルの未処理を再試行 |
| `health-check.yml` | 日次 12:00 JST | 全ソースの最終取得日・DB容量・エラー率チェック |
| `weekly-summary.yml` | 週次 水曜 09:00 JST | 週次サマリーメール生成・送信 |
| `notify-on-failure.yml` | 他 WF から呼出 | LINE + メールで失敗通知（再利用型） |

## Key Entry Points

### スクレイピング（Python）
- `scripts/scrape_nk.py` — NK テクニカルインフォメーション（v2 プロトタイプから本番化）
- `scripts/scrape_mlit_rss.py` — 国交省 RSS 第1層
- `scripts/scrape_mlit_crawl.py` — 国交省 `/maritime/` クロール第2層
- `scripts/classify_gemini.py` — Gemini 分類パイプライン（全ソース共通）

### フロントエンド（Next.js）
- `frontend/src/app/crew/page.tsx` — MVP の入口（資格管理）
- `frontend/src/app/news/page.tsx` — 規制ニュース一覧
- `frontend/src/app/admin/health/page.tsx` — 乗船前ヘルスチェック
- `frontend/src/lib/supabase/server.ts` — サーバー側 Supabase クライアント

### 共通ユーティリティ（Python）
- `scripts/utils/gemini_client.py` — モデルフォールバック付き Gemini ラッパー
- `scripts/utils/line_notify.py` — LINE 通知（全 WF から利用）
- `scripts/utils/pdf_preprocess.py` — PDF 品質判定（サイズ・OCR 要否）

## Constraints（ハードルール）
- Vercel API Routes で Gemini を呼ばない（タイムアウト）
- secrets をコミットしない（GitHub Secrets / Vercel env のみ）
- リポジトリは Public（GHA 無制限のため）
- Supabase は MEGRIBI と別プロジェクト（リソース干渉防止）
- Gemini API は MEGRIBI と別 GCP プロジェクト（RPD 独立枠）
- `NEXT_PUBLIC_*` に secrets を入れない
```
