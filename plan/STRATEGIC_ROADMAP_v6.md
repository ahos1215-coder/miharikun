# 戦略ロードマップ v7 — MIHARIKUN
> 「航海士個人のための情報の蒸留器」
> v6 の後継。v6 との矛盾時は本文書が優先。
> 最終更新: 2026-04-01

## 1. プロダクトの本質
複雑でバラバラな海事情報を、ユーザー一人ひとりの船舶スペックに合わせて「蒸留」し、必要な情報だけを届けるパーソナルアシスタント。

## 2. 戦略的 3 フェーズ

### フェーズ 1: 集約と鮮度維持 (Data Foundation) ✅ ほぼ完了
- [x] NK/MLIT/e-Gov スクレイパー (4ソース、15 GHA ワークフロー)
- [x] 453件の規制データ収集済み
- [x] 67書籍マスターデータ (publications テーブル投入済み)
- [x] 書籍 applicability_rules JSON 化
- [x] publications/ パッケージ分割 (2,369行→7ファイル)
- [ ] 版数監視の本実装 (海文堂 + JHA + IMO) ← 実装中
- [ ] 水路刊行物の2026年版をDBに反映

### フェーズ 2: 船舶スペックによる抽出 (Matching Engine) ✅ 完了
- [x] 43条約ルール + 871キーワード
- [x] 3段階マッチング → 4段階 (Stage1ルール→Stage0条約→Stage2ルール評価→Stage3 AIフォールバック)
- [x] Master Matching 方式 (applicability_rules JSON、API消費ゼロ)
- [x] 全453件の applicability_rules 抽出済み
- [x] 全件再マッチング完了 (適用4件、非適用35件、エラー0、429ゼロ)
- [x] Golden Set 29テスト全通過

### フェーズ 3: パーソナライズ通知 (Active Alerting) 📋 次の重点
- [x] LINE 通知実装済み (Secrets 未設定)
- [x] 週次サマリーメール実装済み (API Key 未設定)
- [ ] LINE_NOTIFY_TOKEN を GitHub Secrets に設定
- [ ] RESEND_API_KEY を Vercel env に設定
- [ ] 通知頻度の調整 (即時/日次/週次の切り分け)
- [ ] テキストベースの低帯域最適化

## 3. 完了済み機能
- [x] スクレイパー (NK/MLIT RSS/MLIT Crawl/e-Gov) — 4ソース
- [x] Gemini AI 分類 + 4段階マッチング (ルール→条約→ルール評価→AI)
- [x] Master Matching (applicability_rules JSON、API消費ゼロ)
- [x] CoVe 検証 + Pydantic バリデーション + 単語境界マッチング
- [x] Supabase Auth + RLS + 12マイグレーション適用済み
- [x] ダッシュボード (Glassmorphism + Framer Motion)
- [x] Yahoo!ニュース風ポータル (専門タブ + 書籍タブ)
- [x] Fleet管理 (/fleet + /fleet/summary)
- [x] 法定図書自動マッピング (67書籍 × 6判定項目)
- [x] 無線設備 (GMDSS/AIS/VDR/LRIT/SSAS) 判定対応
- [x] 書籍 G/A/R ステータス可視化
- [x] 書籍マスターデータ DB 投入 (seed_publications 実行済み)
- [x] 書籍 applicability_rules JSON + publications/ パッケージ分割
- [x] 週次版数チェッカー GHA (フレームワーク)
- [x] extract-rules.yml: 規制→applicability_rules 抽出バッチ
- [x] Cmd+K コマンドパレット
- [x] PWA オフライン対応 + Service Worker
- [x] ユーザーフィードバック (thumbs up/down)
- [x] Vercel デプロイ + カスタムドメイン (miharikun.vercel.app)
- [x] CI/CD (TSC + pytest + ESLint + Security Scan)
- [x] gemini_config.py: Gemini 設定の一元管理

## 4. 排除する機能（実装禁止）
- 管理会社向けのログ監視、完了報告ボタン、レポート出力
- PSC 検査対策に特化した重厚なシミュレーション
- 書籍内容の詳細な要約生成
- B2B 機能全般
- IMO ニュースソース直接取得（ClassNK経由で十分）
- 資格管理・証明書期限リマインダー（v5 で廃止決定）
- マルチテナント対応

## 5. 技術的方針
- **Gemini Flash** を主要AIとして継続（コスト効率最高、Tier 1 Pay-as-you-go）
- **gemini_config.py** でモデル名・パラメータを一元管理
- **Supabase** をDB/Auth/RLSの基盤として維持
- **GHA** をバッチ処理基盤として維持（Vercel はフロントのみ）
- **Master Matching**: applicability_rules JSON による API 消費ゼロのマッチング
- **publications/ パッケージ分割**: 2,369行を7ファイルに分割しメンテナンス性向上
- **テスト駆動**: Golden Set テストで精度を保証 (121テスト)
- **CoVe**: 低確信度の結果は自動検証してからユーザーに表示

## 6. 短期目標（1-2週間）
- [ ] 版数監視の本実装 (海文堂/JHA/IMO)
- [ ] LINE/メール通知の有効化 (Secrets 設定)
- [ ] テストカバレッジ向上 (MLIT RSS テスト、フロントテスト)
- [ ] 水路刊行物の2026年版をDBに反映

## 7. 中期目標（1-2ヶ月）
- [ ] DSPy プロンプト最適化（誤判定フィードバック50件蓄積後）
- [ ] 通知頻度の調整 (即時/日次/週次の切り分け)
- [ ] テキストベースの低帯域最適化
- [ ] ビジネスモデル (Free/Pro のティア設計)

## 8. アーキテクチャ概要
```
[ユーザー] → [Vercel (Next.js 16)] → [Supabase (Auth + DB + RLS)]
                                            ↑
[GitHub Actions (15 workflows)]
  ├── スクレイパー (NK/MLIT/e-Gov)
  ├── Gemini AI 分類 + マッチング v3 (4段階パイプライン)
  ├── applicability_rules 抽出 (extract-rules)
  ├── 書籍版数チェッカー
  ├── headline 生成
  ├── 週次サマリー
  └── CI/CD + Security
```

DB テーブル (8):
- regulations (+ applicability_rules JSONB), pending_queue, mlit_crawl_state
- ship_profiles (+ radio_equipment), user_matches
- user_preferences
- publications (+ applicability_rules JSONB), ship_publications
