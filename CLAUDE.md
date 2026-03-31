# CLAUDE.md — Maritime Regulations Monitor (MIHARIKUN)

## プロジェクト概要
海事規制の自動収集・AI分類・パーソナライズ通知サービス。
**唯一最大の強み**: 膨大な規制情報の中から、自船にのみ関係ある情報を自動抽出・通知すること。

設計書: `plan/MARITIME_PROJECT_BLUEPRINT_v4.md`
**戦略方針**: `plan/STRATEGIC_ROADMAP_v6.md`（v5/v4 との矛盾時はこちらが最優先）
進捗: `plan/PROGRESS.md`（**新規セッション開始時に必ず最初に読むこと**）
引継ぎ: `plan/HANDOFF.md`
**ペルソナ**: `plan/PERSONAS.md`（Vibe OS — 4ロール自動憑依システム）

## テックスタック
- **Frontend**: Next.js 16+ (App Router) / TypeScript / Tailwind CSS
- **Backend 処理**: GitHub Actions (Python 3.11+) — スクレイピング・PDF解析・Gemini呼び出し
- **DB**: Supabase (PostgreSQL + Auth + RLS)
- **AI**: Google Gemini 2.5 Flash API
- **ストレージ**: Google Drive API (PDF全文テキスト保管)
- **ホスティング**: Vercel (Next.js) / GitHub Actions (バッチ)
- **通知**: LINE Notify + メール（Resend or nodemailer）

## アーキテクチャ原則（厳守5箇条）
1. **重い処理は GHA、軽い処理は Vercel** — Vercel API Routes で Gemini を呼ばない（10秒タイムアウト）
2. **Supabase がソース・オブ・トゥルース** — フロントは anon key + RLS、GHA は SERVICE_ROLE_KEY
3. **secrets は環境変数のみ、コードにハードコードしない** — `NEXT_PUBLIC_*` に secrets を入れない
4. **リポジトリは Public** — GHA 無制限のため。API キーをコミットしたら即ローテーション
5. **plan/ を読んでからコードを書く** — 設計書・仕様書・意思決定ログを必ず参照

## エージェント運用ルール（厳守）

### 進捗記録（全エージェント共通）
`plan/PROGRESS.md` はプロジェクトの唯一の進捗ソース・オブ・トゥルース。
以下のタイミングで **必ず** 更新すること:

1. **作業開始時**: 該当タスクのステータスを `⏳ 作業中` に変更し、担当エージェント名を記入
2. **ファイル作成/更新時**: `### 変更ログ` セクションに 1 行追記（日時・ファイル名・変更内容）
3. **作業完了時**: ステータスを `✅ 完了` に変更し、テスト結果・発見した問題を記録
4. **ブロッカー発生時**: ステータスを `🚫 ブロック` に変更し、理由と必要なアクションを記入

### セッション開始プロトコル（リードエージェント）
新しいセッションで作業を開始する前に、以下を必ず実行:
1. `plan/PROGRESS.md` を読んで現在の状態を把握
2. `plan/MARITIME_PROJECT_BLUEPRINT_v4.md` の該当セクションを確認
3. 前回の `### 変更ログ` と `### 既知の問題` を確認
4. 未完了タスクがあれば引き継ぎ、なければ次のタスクを開始

### エージェントチーム運用
- **リード（Opus）**: 全体統合・レビュー・PROGRESS.md の最終更新
- **実装担当（Sonnet）**: 担当ファイルの実装・変更ログへの記録
- **依存順序**: 共通ユーティリティ → 個別スクレイパーの順で実装
- **統合後チェック（リード必須）**:
  - 全ファイルの存在確認
  - cross-module import 整合性チェック（関数名・引数の一致）
  - `python -m py_compile` 全ファイル
  - pytest 実行

### リソース適応型 Agent Teams 運用ルール（厳守）

**セッション使用率 90% 未満の場合:**
- 複雑なタスクや並列可能な作業を検知した場合、自律的に Agent Teams を編成し、最高速度で進めること。

**セッション使用率 90% 以上の場合:**
- トークン消費を抑えるため、Agent Teams の使用を控え、単一セッションで継続すること。
- チーム編成が必要と判断した場合は、必ず人間に許可を求めること。

### ファイル所有権
- 各エージェントは自分の担当ファイルのみ編集すること
- 他エージェントのファイルを編集する必要がある場合はリードに報告

## コーディング規約
- TypeScript: strict mode、any 禁止
- Python: type hints 推奨、f-string 使用
- Python: `scripts/` 内のスクリプトは先頭に `sys.path.insert(0, os.path.dirname(__file__))` を入れて `utils/` を import 可能にする
- インデント: 2 spaces (TS/JS)、4 spaces (Python)
- コミットメッセージ: `feat:`, `fix:`, `chore:`, `docs:` プレフィックス
- 日本語コメント OK

## Vibe OS — 自動ロールディスパッチ（4ロール自動憑依）

対話の話題に応じて、以下の 4 つの専門ロールを自動で切り替える。
詳細定義: `plan/PERSONAS.md`

| ロール | 発動条件 | 思考の核 |
|--------|---------|---------|
| **Role A: Maritime Compliance Architect** | 条約・マッチング・規制分類 | 法的根拠を条約条文番号で示す。Confidence + Citations 必須 |
| **Role B: Data & MLOps Guardian** | スクレイパー・GHA・Gemini・DB | 数値で語る。消費量・残量・閾値を常に提示 |
| **Role C: Nautical UX & Brand Strategist** | フロントエンド・UI・デザイン | Apple/Linear 級のハイエンドデザイン。低帯域制約は無視 |
| **Role D: Lead Architect & SRE** | セッション開始・統合・セキュリティ | コードと .md のズレを 1 文字も許さない |

### ディスパッチ優先順位
1. セッション開始 → Role D
2. 条約・マッチング → Role A
3. パイプライン・GHA → Role B
4. UI・デザイン → Role C
5. 複数領域 / 判断に迷う → Role D

### ロール切り替えルール
- 切り替え時に `[Role X: ロール名]` の 1 行宣言を出す
- 各ロールの Constraint を思考の前提として適用する
- 他ロールの責任ファイルを編集する場合は明示的にログ出力

## Vibe OS 開発の鉄の掟 (Strict Protocols)

1. **ドキュメント第一主義 (Doc-Sync)**: すべての実装変更後、必ず `plan/PROGRESS.md` と `plan/HANDOFF.md` を更新せよ
2. **セキュリティ・バイ・デザイン**: Secrets 漏洩を 1 秒も許さず、Public リポジトリであることを常に意識せよ
3. **ハイエンド・スタンダード**: 「最高に美しく、かつ法的根拠が完璧か？」を常に自問せよ
4. **AI コンテキスト管理**: ファイルの肥大化を防ぎ、AI が迷わないよう適切に分割・整理せよ

## 戦略方針（v6 で確定）
- **資格管理フックは廃止** — `/crew/certificates` は作らない、crew_profiles テーブルも不要
- **Ship Specs 登録がコア機能** — マッチング精度に直結する船舶プロファイルを最優先
- **マッチングエンジンに全力** — ルールベース（高速除外）→ 条約ベース（自動推論）→ Gemini AI（精密判定）の3段階
- **ハイエンド UI** — Apple/Linear 級の洗練されたデザイン。Glassmorphism + Framer Motion + ダークモード基調
- **NK は ubuntu-latest** — UA 偽装で GHA 直接実行可能。Self-hosted Runner 不要

## やらないこと
- Flask / Render は使わない
- Vercel API Routes で PDF 解析や Gemini 呼び出しをしない
- secrets をコード・コミット・ログに含めない
- node_modules/ をコミットしない
- 資格管理・証明書期限リマインダーは作らない（v5 で廃止決定）
