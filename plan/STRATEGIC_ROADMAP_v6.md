# 戦略ロードマップ v7 — MIHARIKUN
> 最終更新: 2026-04-03

## 1. プロダクトの本質（最重要 — 全開発判断の根幹）

**バラバラで複雑な海事情報を、ユーザー一人ひとりの船舶スペックに合わせて蒸留し、必要な情報だけを届け、知らせること。**

## 2. 戦略的 3 フェーズ

### フェーズ 1: 情報の集約と鮮度維持 ⏳ 作業中
- バラバラの情報を一か所に集め、最新情報を提供し続ける
- NK テクニカルインフォメーション + 国交省海事局の情報を網羅的に収集
- 船側（航海士・機関士）と会社側（運航担当）に関係あるものだけをニュースに表示
- **現在地**: NK の情報量不足 + 国交省フィルタの検証中

### フェーズ 2: パーソナライズマッチング 📋 次
- ユーザーの船舶情報に合わせて必要な情報を正確にマッチングさせる
- applicability_rules + 4段階マッチングエンジン（実装済み、検証・改善フェーズ）

### フェーズ 3: 通知 📋 その次
- マッチングした情報に更新があれば LINE/メールで通知する
- LINE_NOTIFY_TOKEN / RESEND_API_KEY の設定で即稼働

## 3. システム構成（シンプル化後）

### スクリプト (10個)
| スクリプト | 用途 | スケジュール |
|-----------|------|------------|
| `scrape_nk.py` | NK 週次取得 (直近100件差分) | 週次 日曜 07:00 |
| `scrape_mlit_crawl.py` | MLIT シードURL方式 (即時解析) | 週次 日曜 06:00 |
| `scrape_kanto_bureau.py` | 関東運輸局テスト監視 | 週次 火曜 12:00 |
| `run_matching.py` | 4段階マッチング | スクレイプ完了後 |
| `notify_matches.py` | LINE 通知 | マッチング完了後 |
| `weekly_summary.py` | 週次サマリーメール | 月曜 09:00 |
| `health_check.py` | システム監視 | 6時間毎 |
| `check_publication_updates.py` | 書籍版数チェック | 月次 1日 |
| `process_queue.py` | pending_queue 消化 (レガシー) | 必要時のみ |
| `seed_publications.py` | 書籍マスターデータ投入 | 実行済み |

### GHA ワークフロー (10個)
| ワークフロー | スケジュール |
|-------------|------------|
| `scrape-nk.yml` | 週次 日曜 |
| `scrape-mlit-crawl.yml` | 週次 日曜 |
| `scrape-kanto.yml` | 週次 火曜 |
| `run-matching.yml` | トリガー |
| `weekly-summary.yml` | 週次 月曜 |
| `health-check.yml` | 6時間毎 |
| `check-publications.yml` | 月次 1日 |
| `ci.yml` | PR/push |
| `security-scan.yml` | 週次/PR |
| `notify-on-failure.yml` | 再利用可能 |

### 統一プロンプト (UNIFIED_PROMPT)
全ソース共通。1回の Gemini 呼び出しで以下を全て出力:
- headline, summary_ja, legal_basis, effective_date
- severity (critical/action_required/informational)
- applicable_ship_types, applicable_gt_min/max
- confidence, citations
- Self-Critique + F-D-H → onboard_actions, shore_actions, sms_chapters

## 4. 排除する機能（実装禁止）
- 管理会社向けのログ監視、完了報告ボタン、レポート出力
- PSC 検査対策に特化した重厚なシミュレーション
- B2B 機能全般
- 書籍内容の詳細な要約生成
- IMO ニュースソース直接取得（ClassNK経由で十分）
