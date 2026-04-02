# 戦略ロードマップ v7 — MIHARIKUN
> 最終更新: 2026-04-02

## 1. プロダクトの本質（最重要 — 全開発判断の根幹）

**バラバラで複雑な海事情報を、ユーザー一人ひとりの船舶スペックに合わせて蒸留し、必要な情報だけを届け、知らせること。**

## 2. 戦略的 3 フェーズ

### フェーズ 1: 情報の集約と鮮度維持 ⏳ 作業中
**目的**: バラバラの情報を一か所に集め、最新情報を提供し続ける

**完了済み**:
- [x] スクレイパー基盤: NK + MLIT RSS + MLIT Crawl + e-Gov + 関東運輸局
- [x] ノイズフィルタ v2.4 (351パターン) + Self-Critique + F-D-H ルール
- [x] シードURL方式 + Discovery Mode + 金脈キーワードバイパス
- [x] 67書籍マスターデータ + 版数監視 (海文堂/JHA/IMO)
- [x] Gemini SSoT統合 (call_gemini_text / download_and_extract_pdf_text)
- [x] Supabase SSoT統合 (get_supabase_headers)

**未完了（現在の課題）**:
- [ ] **NK テクニカルインフォメーション**: 直近100件の安定取得 + Web表示確認
- [ ] **国交省フィルタ検証**: 船側（航海士・機関士）と会社側（運航担当）に関係あるものだけが表示されているか
- [ ] **ニュースページの品質**: 全船共通の情報が正しく公開されているか
- [ ] **2024年以前のデータ**: published_at=null のデータの扱い

### フェーズ 2: パーソナライズマッチング 📋 次
**目的**: ユーザーの船舶情報に合わせて必要な情報を正確にマッチングさせる

**実装済み（検証・改善待ち）**:
- [x] 43条約ルール + 871キーワード
- [x] 4段階マッチング (ルール→条約→applicability_rules評価→AIフォールバック)
- [x] Master Matching 方式 (API消費ゼロ)
- [x] Golden Set 29テスト全通過

**フェーズ1完了後に取り組む**:
- [ ] フェーズ1で確立したクリーンなデータに対してマッチング精度を検証
- [ ] ユーザーフィードバック (👍👎) による改善ループ

### フェーズ 3: 通知 📋 その次
**目的**: マッチングした情報に更新があれば通知する

- [x] LINE 通知実装済み (Secrets 未設定)
- [x] 週次サマリーメール実装済み (API Key 未設定)
- [ ] LINE_NOTIFY_TOKEN / RESEND_API_KEY 設定 → 即稼働
- [ ] 通知頻度の調整 (即時/日次/週次)

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
- [x] 週次版数チェッカー: 海文堂 + JHA + IMO 実装済み (NK/UKHO/ILO stub)
- [x] 国交省スクレイピング再設計 (シードURL方式 + Discovery Mode)
- [x] ノイズフィルタ v2.4 (filters.py SSoT, 351パターン)
- [x] Gemini アクション抽出 (extract_actions.py)
- [x] Vercel miharikun2.vercel.app 再デプロイ
- [x] 副船長プロトコル + 効率優先思考 (CLAUDE.md)
- [x] extract-rules.yml: 規制→applicability_rules 抽出バッチ
- [x] Cmd+K コマンドパレット
- [x] PWA オフライン対応 + Service Worker
- [x] ユーザーフィードバック (thumbs up/down)
- [x] Vercel デプロイ + カスタムドメイン (miharikun2.vercel.app)
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
