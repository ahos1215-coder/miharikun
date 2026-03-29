# 引継ぎ書 — MIHARIKUN Phase 1 R1 → R2

> **次のセッションはこのファイルから読み始めてください。**
> 最終更新: 2026-03-29

---

## 1. 今どこにいるか

**Phase 1 ラウンド 1（スクレイパー構築）が完了し、コミット待ちの状態。**

```
Phase 0: 基盤構築         ✅ コミット済み (99b7246)
Phase 1 R1: スクレイパー  ✅ 実装完了・テスト通過・未コミット ← 今ここ
Phase 1 R2: DB + 検証     📋 未着手
Phase 2: UI + 認証        📋 未着手
Phase 3: 通知 + 船舶管理  📋 未着手
```

---

## 2. 最初にやること

```
1. git status で未コミット状態を確認
2. ユーザーにコミット実行の許可を取る
3. コミットメッセージ: "feat: Phase 1 R1 データ収集パイプライン（スクレイパー + 共通ユーティリティ）"
4. plan/PROGRESS.md を読んで詳細を把握
```

---

## 3. 未コミットファイル一覧（18ファイル）

### 変更（既存ファイル）
| ファイル | 変更内容 |
|---------|---------|
| `scripts/scrape_nk.py` | プロトタイプ(658行)→本番版(849行)。共通ユーティリティ使用、v4 フィールド追加 |
| `CLAUDE.md` | エージェント運用ルール・進捗記録ルール追加 |

### 新規
| ファイル | 概要 |
|---------|------|
| `scripts/utils/__init__.py` | パッケージ化 |
| `scripts/utils/gemini_client.py` | Gemini API（2モデル切替 + 指数バックオフ） |
| `scripts/utils/supabase_client.py` | Supabase REST クライアント（7メソッド） |
| `scripts/utils/line_notify.py` | LINE Notify（スロットリング付き） |
| `scripts/utils/gdrive_client.py` | Google Drive API v3（ローカルフォールバック付き） |
| `scripts/utils/pdf_preprocess.py` | PDF 品質チェック（4段階判定） |
| `scripts/scrape_mlit_rss.py` | 国交省 RSS 第1層スクレイパー |
| `scripts/scrape_mlit_crawl.py` | 国交省クロール第2層スクレイパー |
| `scripts/requirements.txt` | Python 依存パッケージ |
| `.github/workflows/scrape-nk.yml` | NK 日次（JST 07:00） |
| `.github/workflows/scrape-mlit-rss.yml` | MLIT RSS 日次（JST 08:00） |
| `.github/workflows/scrape-mlit-crawl.yml` | MLIT クロール週次（日曜 JST 06:00） |
| `.github/workflows/notify-on-failure.yml` | 再利用可能失敗通知 |
| `tests/python/conftest.py` | pytest fixtures |
| `tests/python/test_scrape_nk.py` | 41テスト全通過 |
| `plan/PROGRESS.md` | 進捗ソース・オブ・トゥルース |
| `plan/HANDOFF.md` | この引継ぎ書 |

---

## 4. 品質状態

| チェック | 結果 |
|---------|------|
| `python -m py_compile` 全8 .pyファイル | ✅ 全通過 |
| YAML バリデーション 全4ワークフロー | ✅ 全通過 |
| `pytest tests/python/test_scrape_nk.py` | ✅ 41 passed in 6.71s |
| secrets ハードコード | ✅ なし |
| cross-module import 整合性 | ✅ 全一致（修正済み） |

---

## 5. コミット後の次のアクション（Phase 1 R2）

優先順に:

1. **Supabase マイグレーション SQL** — `supabase/migrations/` に作成
   - `regulations` テーブル（Blueprint §7.1）
   - `pending_queue` テーブル
   - `mlit_crawl_state` テーブル
   - RLS ポリシー

2. **追加ワークフロー**
   - `process-queue.yml`（pending_queue リトライ、毎日 JST 12:00）
   - `health-check.yml`（ソース鮮度・DB 容量）

3. **実データ動作検証**
   - NK dry-run テスト
   - MLIT RSS 実取得テスト
   - Gemini 分類精度検証

---

## 6. 知っておくべきこと

### アーキテクチャ
- 重い処理（スクレイピング・Gemini・DB書込）→ **GHA Python バッチ**
- 軽い処理（UI表示・DB読取）→ **Vercel Next.js**
- Vercel API Routes で Gemini を呼んではいけない（10秒タイムアウト）

### 共通ユーティリティの API

```python
# scripts/ 内のスクリプトでは必ずこの1行を入れてから import
sys.path.insert(0, os.path.dirname(__file__))

from utils.gemini_client import classify_pdf
# classify_pdf(pdf_bytes: bytes, prompt: str, source_id: str = "") -> dict

from utils.supabase_client import SupabaseClient
# client = SupabaseClient()
# client.upsert_regulation(dict) -> bool
# client.get_max_source_id(source: str) -> Optional[str]
# client.queue_pending(source, source_id, pdf_url, reason, error_detail) -> bool
# client.get_pending_queue(source=None) -> list[dict]
# client.check_source_health(source, days=30) -> dict

from utils.line_notify import send_alert, send_scraper_error, send_health_check_report
# send_alert(title: str, message: str, severity: str = "info") -> bool

from utils.gdrive_client import upload_text, upload_json, create_subfolder
# upload_json(data: dict, filename: str, folder_id=None) -> Optional[str]

from utils.pdf_preprocess import preprocess_pdf, check_pdf_url, extract_text
# preprocess_pdf(url: str, pdf_bytes: bytes) -> dict  # status: ok/skipped/scan_image/suspicious
```

### 過去の罠（再発防止）
1. `send_line_notify` は存在しない → 正しくは `send_alert`
2. `scripts/` から `utils/` を import するには `sys.path.insert` 必須
3. プロンプト内の `` ```json `` を regex で検出する際、説明文に誤マッチするので `\n` を含めること
4. ワークツリーで並列エージェント実行した際、エージェントがコミットしないことがある → 統合時に `git status` で確認

### 運用ルール
- 作業中は `plan/PROGRESS.md` の変更ログに追記すること（CLAUDE.md 参照）
- 設計書: `plan/MARITIME_PROJECT_BLUEPRINT_v4.md`（特に §3, §7, §11, §12 が重要）

---

## 7. 必要な環境変数（GitHub Secrets）

> R2 で実データ検証を始める際に設定が必要

| 変数名 | 用途 | 必須タイミング |
|--------|------|--------------|
| `SUPABASE_URL` | Supabase プロジェクト URL | DB 操作時 |
| `SUPABASE_SERVICE_ROLE_KEY` | RLS バイパス用キー | DB 操作時 |
| `GEMINI_API_KEY` | Gemini API キー | 分類実行時 |
| `GEMINI_MODEL` | プライマリモデル名（default: gemini-2.5-flash） | 任意 |
| `GEMINI_FALLBACK_MODEL` | フォールバックモデル名（default: gemini-2.0-flash） | 任意 |
| `LINE_NOTIFY_TOKEN` | LINE 通知トークン | 通知時 |
| `GDRIVE_FOLDER_ID` | Google Drive 保存先フォルダ ID | テキスト保存時 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | GCP Service Account JSON | Drive API 時 |
