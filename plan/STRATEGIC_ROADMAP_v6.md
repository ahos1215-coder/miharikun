# 戦略ロードマップ v6 — MIHARIKUN
> v5 の後継文書。v5 との矛盾時は本文書が優先。
> 最終更新: 2026-03-31

## 1. 現在地
Phase 3 本番稼働中。法定図書自動マッピング + Maritime Command Center 実装済み。
- 453件の規制データ (NK + MLIT + e-Gov)
- 推論型コンプライアンスエンジン (43条約, 871キーワード)
- 3段階マッチング + CoVe 検証
- 14 GHA ワークフロー自動実行中
- 法定図書自動マッピング (67書籍, 4カテゴリ, G/A/R可視化)
- Maritime Command Center (Glassmorphism + Framer Motion)
- Vibe OS (4ロール自動憑依システム)
- 130テスト全通過

## 2. プロダクトの核心価値（不変）
「膨大な規制情報の中から、自船にのみ関係ある情報を自動抽出・通知し、
具体的な対応事項（船側/会社側）まで提示すること」

**第二の柱**: 「船舶スペックから備付義務書籍を自動判定し、最新版を監視すること」

## 3. 完了済み機能
- [x] スクレイパー (NK/MLIT RSS/MLIT Crawl/e-Gov)
- [x] Gemini AI 分類 + 3段階マッチング (ルール→条約→AI)
- [x] CoVe 検証 + Pydantic バリデーション + 単語境界マッチング
- [x] Supabase Auth + RLS + 10マイグレーション適用済み
- [x] Maritime Command Center (ダッシュボード完全リデザイン)
- [x] Yahoo!ニュース風ポータル (専門タブ + 書籍タブ)
- [x] Fleet管理 (/fleet + /fleet/summary)
- [x] 法定図書自動マッピング (67書籍 × 6判定項目)
- [x] 無線設備 (GMDSS/AIS/VDR/LRIT/SSAS) 判定対応
- [x] 書籍 G/A/R ステータス可視化
- [x] 書籍マスターデータ DB 投入 (seed_publications 実行済み)
- [x] 週次版数チェッカー GHA (フレームワーク)
- [x] Cmd+K コマンドパレット
- [x] PWA オフライン対応 + Service Worker
- [x] ユーザーフィードバック (👍👎)
- [x] Vercel デプロイ + カスタムドメイン
- [x] CI/CD (TSC + pytest + ESLint + Security Scan)

## 4. 短期目標（1-2週間）
- [ ] LINE/メール通知の有効化 (Secrets 設定)
- [ ] Version Tracker スクレイパー実装 (IMO Publishing / 海上保安庁 水路部)
- [ ] 最新エンジンでの全件再マッチング (Gemini API)
- [ ] フロントエンド単体テスト導入 (Jest/Vitest)

## 5. 中期目標（1-2ヶ月）
- [ ] DSPy プロンプト最適化（誤判定フィードバック50件蓄積後）
- [ ] IMO ニュースソース追加
- [ ] 複数船一括管理（Fleet強化）
- [ ] ビジネスモデル実装（Free/Pro/Fleet ティア）
- [ ] マルチテナント対応
- [ ] PSC 検査対策機能

## 6. 長期目標（3-6ヶ月）
- [ ] LlamaIndex RAG（条約原文のインデキシング）
- [ ] 英語UI（海外船籍対応）
- [ ] モバイルアプリ（React Native or PWA強化）
- [ ] 書籍購入・サブスクリプション連携

## 7. 技術的方針
- Gemini Flash を主要AIとして継続（コスト効率最高）
- Supabase をDB/Auth/RLSの基盤として維持
- GHA をバッチ処理基盤として維持（Vercel はフロントのみ）
- テスト駆動: Golden Set テストで精度を保証
- CoVe: 低確信度の結果は自動検証してからユーザーに表示
- Vibe OS: 4ロール自動憑依でAIの専門性を最大化
- ハイエンドUI: Glassmorphism + Framer Motion + ダークモード基調

## 8. アーキテクチャ概要
```
[ユーザー] → [Vercel (Next.js 16)] → [Supabase (Auth + DB + RLS)]
                                            ↑
[GitHub Actions (14 workflows)]
  ├── スクレイパー (NK/MLIT/e-Gov)
  ├── Gemini AI 分類 + マッチング v3
  ├── 書籍版数チェッカー
  ├── headline 生成
  ├── 週次サマリー
  └── CI/CD + Security
```

DB テーブル (8):
- regulations, pending_queue, mlit_crawl_state
- ship_profiles (+ radio_equipment), user_matches
- user_preferences
- publications, ship_publications
