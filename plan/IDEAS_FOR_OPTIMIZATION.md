# 改善バックログ — IDEAS FOR OPTIMIZATION

> 副船長（シニアアーキテクト）が発見した技術的負債・最適化案の管理台帳。
> 優先度: P0(致命的) / P1(高) / P2(中)
> 最終監査日: 2026-04-01

---

## P0: 致命的 — 即対応

### 1. Gemini 設定が3箇所で重複（MAX_RETRIES 不一致）
- `gemini_client.py`: MAX_RETRIES=6
- `matching.py`: MAX_RETRIES=4 ← **異なる値**
- `extract_applicability_rules.py`: 独自実装
- `generate_headlines.py`: 独自実装
- **対策**: `scripts/utils/gemini_config.py` を作成し、全モジュールから import
- **工数**: 2時間

### 2. 日次 RSS スクレイパーにテストがない
- `scrape_mlit_rss.py` (578行) — 毎日 GHA で実行されるが単体テストなし
- 壊れても気づかないリスク
- **対策**: `tests/python/test_scrape_mlit_rss.py` を作成
- **工数**: 4時間

### 3. フロントエンド単体テストがゼロ
- 30以上のコンポーネントにテストなし
- API ルート（4本）にもテストなし
- **対策**: Jest/Vitest を導入し、重要コンポーネントから順次追加
- **工数**: 初期セットアップ2時間 + テスト作成1日

---

## P1: 高優先 — 次のスプリントで対応

### 4. 船種定数が2ファイルで重複
- `maritime_knowledge.py` と `publication_requirements.py` に同一のリスト
- **対策**: `scripts/utils/ship_types.py` に抽出し、両方から import
- **工数**: 1時間

### 5. extract/generate スクリプトが Gemini API を独自実装
- `extract_applicability_rules.py` と `generate_headlines.py` が `gemini_client.py` を使わず直接 API 呼び出し
- **対策**: `gemini_client.py` に `call_gemini_text()` を追加し、両スクリプトから利用
- **工数**: 1時間

### 6. publication_requirements.py が 2,258行で巨大
- 67書籍のデータ定義 + ロジックが1ファイル
- **対策**: `scripts/utils/publications/` パッケージに分割（category_a.py, category_b.py 等）
- **工数**: 3時間

### 7. Python(67件) vs TypeScript(43件) の書籍データ乖離
- フロントエンドの `publication-data.ts` が Python のサブセット
- **対策**: フロントは DB から取得し、TS ハードコードはフォールバック専用に
- **状態**: 部分的に対応済み（コメント追加）。完全な DB ファースト化は API ルート拡張が必要
- **工数**: 3時間

---

## P2: 中優先 — 余裕がある時に対応

### 8. CoVe (Chain of Verification) のコスト対効果が不明
- 低確信度の結果に対して Gemini を2回呼ぶ
- 精度改善の実測データがない
- **対策**: `ENABLE_COVE_VERIFICATION` 環境変数でオン/オフ制御
- **工数**: 30分

### 9. framer-motion が 5.4MB
- 10個のDOM要素のアニメーションに使用
- 本番 gzip で約200KB
- **対策**: 受容可能だが、CSS アニメーションへの段階的移行も検討
- **工数**: 2時間（CSS移行する場合）

### 10. matching.py の magic numbers
- confidence 閾値 (0.4, 0.85, 0.1) がハードコード
- **対策**: `matching_config.py` に定数化
- **工数**: 30分

### 11. デッドコード
- `matching.py`: `_not_applicable_result()` が定義のみで未使用
- `matching.py`: `get_applicable_keywords` が import のみで未使用
- **対策**: 削除
- **工数**: 15分

### 12. notify_matches.py に URL ハードコード
- `miharikun.vercel.app` が直接記述
- **対策**: `MIHARIKUN_BASE_URL` 環境変数に統一
- **工数**: 15分

### 13. plan/ ドキュメントの陳腐化
- `STRATEGIC_PIVOT_v5.md` が crew_profiles を参照（実在しない）
- `AGENT_TEAMS_PLAN.md` の Phase 計画が古い
- **対策**: 定期的な Doc-Sync（CI チェック検討）
- **工数**: 30分

---

## 完了済み

| ID | 内容 | 完了日 |
|----|------|--------|
| — | マッチング Stage 2 → applicability_rules 評価に切り替え | 2026-04-01 |
| — | MLIT クローラー 409バグ + Gemini 分離 | 2026-04-01 |
| — | 書籍 ID 統一 (PUB_X_NNN → 記述的ID) | 2026-03-31 |
| — | Lambda → applicability_rules JSON | 2026-03-31 |
