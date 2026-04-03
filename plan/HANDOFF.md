# 引継ぎ書 — MIHARIKUN

> **次のセッションはこのファイルから読み始めてください。**
> 最終更新: 2026-04-03

---

## 1. 今どこにいるか

**Phase 1 完了 → Phase 2 着手準備。** https://miharikun2.vercel.app

```
Phase 1: 情報の集約と鮮度維持     ✅ 完了 (2026-04-03)
Phase 2: パーソナライズマッチング  📋 次
Phase 3: 通知                      📋 その次
```

---

## 2. 最初にやること

```
1. plan/PROGRESS.md を読んで詳細を把握
2. plan/STRATEGIC_ROADMAP_v6.md (v7方針) を確認
3. CLAUDE.md のルールを遵守
```

---

## 3. 本番環境

| 項目 | 値 |
|------|-----|
| Public URL | https://miharikun2.vercel.app |
| デプロイ | Vercel 自動デプロイ (git push → 自動ビルド) |
| DB | Supabase (PostgreSQL + Auth + RLS) |
| AI | Google Gemini 2.5 Flash API (Tier 1 Pay-as-you-go) |
| バッチ | GitHub Actions (11 ワークフロー) |
| リポジトリ | Public (GHA 無制限のため) |

### GitHub Secrets (設定済み)
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`

### 未設定の Secrets (Phase 3 で必要)
- `LINE_NOTIFY_TOKEN` — LINE 通知
- `RESEND_API_KEY` — 週次サマリーメール

---

## 4. DB テーブル

| テーブル | 用途 |
|---------|------|
| `regulations` | 規制情報 (NK 99件 + MLIT 18件) |
| `ship_profiles` | ユーザーの船舶スペック登録 |
| `user_matches` | マッチング結果 (船舶×規制) |
| `user_preferences` | 通知設定 |
| `publications` | 書籍マスター (81冊) |
| `ship_publications` | 船舶別 備付書籍状況 |
| `mlit_crawl_state` | MLIT クローラー状態管理 |
| `pending_queue` | レガシー (未使用) |

マイグレーション: `supabase/migrations/` (13 ファイル、全て適用済み)

---

## 5. システム構成

### スクリプト (9個)
| ファイル | 用途 |
|---------|------|
| `scrape_nk.py` | NK 週次取得 (100件, --force-all対応) |
| `scrape_mlit_crawl.py` | MLIT シードURL方式 (即時Gemini解析) |
| `scrape_kanto_bureau.py` | 関東運輸局テスト監視 |
| `run_matching.py` | 4段階マッチング |
| `notify_matches.py` | LINE 通知 |
| `weekly_summary.py` | 週次サマリーメール |
| `health_check.py` | システム監視 |
| `check_publication_updates.py` | 書籍版数チェック (IMO/JHA/海文堂/成山堂) |
| `seed_publications.py` | 書籍マスター投入 (81冊) |

### GHA ワークフロー (11個)
| ファイル | スケジュール |
|---------|------------|
| `scrape-nk.yml` | 週次 日曜 07:00 JST |
| `scrape-mlit-crawl.yml` | 週次 日曜 06:00 JST |
| `scrape-kanto.yml` | 週次 火曜 12:00 JST |
| `run-matching.yml` | 手動トリガー |
| `weekly-summary.yml` | 週次 月曜 09:00 JST |
| `health-check.yml` | 6時間毎 |
| `check-publications.yml` | 月次 1日 11:00 JST |
| `seed-publications.yml` | 手動 (書籍追加時) |
| `ci.yml` | PR/push |
| `security-scan.yml` | 週次/PR |
| `notify-on-failure.yml` | 再利用可能 |

### ユーティリティ (SSoT)
| ファイル | 責務 |
|---------|------|
| `utils/gemini_client.py` | Gemini API + UNIFIED_PROMPT + Self-Critique |
| `utils/supabase_client.py` | Supabase REST (全スクリプト共通) |
| `utils/filters.py` | ノイズフィルタ v2.4 (351パターン) |
| `utils/matching.py` | 4段階マッチング (1073行) |
| `utils/maritime_knowledge.py` | 定数 + ユーティリティ (281行) |
| `utils/maritime_convention_rules.py` | 43条約ルールデータ (1725行) |
| `utils/ship_compliance.py` | 船舶→適用条約推論 |
| `utils/publications/` | 備付書籍判定パッケージ (81冊) |

---

## 6. コードベース健康状態 (2026-04-03 監査済み)

### 良好
- Gemini SSoT: 全呼び出しが gemini_client.py 経由
- Supabase SSoT: 全スクリプトが get_supabase_headers() 使用
- 循環import: なし
- secrets: ハードコードゼロ
- TypeScript strict: フロントエンド全体

### 改善済み (本日)
- process_queue.py 削除 (デッドコード)
- ハードコードURL → MIHARIKUN_BASE_URL 環境変数化
- 備付書タブ: ハードコード → DB取得に切替
- maritime_knowledge.py: 1995行 → 281行 + 1725行に分割

### 残存の技術的負債 (低優先)
- matching.py 1073行 (Phase 2 改善時に分割)
- news/page.tsx 732行, news/[id]/page.tsx 812行 (コンポーネント分離可)
- UKHO/ILO 版数チェッカー未実装 (更新頻度低)
- publication-data.ts 566行 (ダッシュボードがまだ使用中、段階的に廃止)

---

## 7. 4段階マッチングエンジン

1. **Stage 1: ルールベース** — 船種・GT・旗国・航行区域で高速除外
2. **Stage 0: 条約ベース** — 43条約 + 871キーワードで条約適用推論
3. **Stage 2: applicability_rules** — JSONB ルール評価 (API消費ゼロ)
4. **Stage 3: Gemini AI** — フォールバック (confidence + citations)

---

## 8. 過去の罠 (再発防止)

1. Agent Teams で7重複 `_headers()` 発生 → SSoT 強制ルールで解消
2. NK は UA ベースでブロック (IP ではない) → Chrome UA で解決
3. `is_too_old(null)` = True で NK データ誤削除 → null = False に修正
4. Supabase 空文字 Secret がデフォルト値を上書きする
5. MLIT の `title` が PDF 由来で文字化け → `headline` をメインタイトルに

---

## 9. 次のアクション (Phase 2)

### Phase 2: パーソナライズマッチング
- [ ] マッチングエンジンの検証・改善
- [ ] 「主要 / My Ship」タブで自船該当規制のみ表示
- [ ] applicability_rules の精度向上
- [ ] Golden Set テスト拡充

### Phase 3 準備 (手動)
- [ ] `LINE_NOTIFY_TOKEN` を GitHub Secrets に設定
- [ ] `RESEND_API_KEY` を Vercel env に設定

詳細: `plan/STRATEGIC_ROADMAP_v6.md` (v7 方針)
