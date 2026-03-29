# CLAUDE.md — Maritime Regulations Monitor (MIHARIKUN)

## プロジェクト概要
海事規制の自動収集・AI分類・パーソナライズ通知サービス。
設計書: `plan/MARITIME_PROJECT_BLUEPRINT_v4.md`

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

## コーディング規約
- TypeScript: strict mode、any 禁止
- Python: type hints 推奨、f-string 使用
- インデント: 2 spaces (TS/JS)、4 spaces (Python)
- コミットメッセージ: `feat:`, `fix:`, `chore:`, `docs:` プレフィックス
- 日本語コメント OK

## やらないこと
- Flask / Render は使わない
- Vercel API Routes で PDF 解析や Gemini 呼び出しをしない
- secrets をコード・コミット・ログに含めない
- node_modules/ をコミットしない
