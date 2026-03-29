# CLAUDE.md — Maritime Regulations Monitor (MIHARIKUN)

## プロジェクト概要
海事規制の自動収集・AI分類・パーソナライズ通知サービス。
**唯一最大の強み**: 膨大な規制情報の中から、自船にのみ関係ある情報を自動抽出・通知すること。

設計書: `plan/MARITIME_PROJECT_BLUEPRINT_v4.md`
**戦略方針**: `plan/STRATEGIC_PIVOT_v5.md`（v4 との矛盾時はこちらが優先）
進捗: `plan/PROGRESS.md`（**新規セッション開始時に必ず最初に読むこと**）
引継ぎ: `plan/HANDOFF.md`

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

## 戦略方針（v5 で確定）
- **資格管理フックは廃止** — `/crew/certificates` は作らない、crew_profiles テーブルも不要
- **Ship Specs 登録がコア機能** — マッチング精度に直結する船舶プロファイルを最優先
- **マッチングエンジンに全力** — ルールベース（高速除外）→ Gemini AI（精密判定）の2段階
- **超軽量 UI** — 船上低帯域対応、1ページ完結、初期ロード < 50KB
- **NK は Self-hosted Runner** — GHA IP ブロック回避のため開発 PC をランナーに設定

## やらないこと
- Flask / Render は使わない
- Vercel API Routes で PDF 解析や Gemini 呼び出しをしない
- secrets をコード・コミット・ログに含めない
- node_modules/ をコミットしない
- 資格管理・証明書期限リマインダーは作らない（v5 で廃止決定）
