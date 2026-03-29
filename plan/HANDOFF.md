# 引継ぎ書 — MIHARIKUN Phase 1 R2 継続

> **次のセッションはこのファイルから読み始めてください。**
> 最終更新: 2026-03-29 19:40 JST

---

## 1. 今どこにいるか

**Phase 1 R2（DB + マッチング基盤）の終盤。ユーザー手動作業2つ待ち。**

```
Phase 0: 基盤構築              ✅ コミット済み
Phase 1 R1: スクレイパー       ✅ コミット済み
Phase 1 R2: DB + マッチング    ⏳ ほぼ完了、ユーザー作業待ち ← 今ここ
Phase 2: Ship Specs + UI       📋 未着手
Phase 3: Fleet 管理 + 拡張     📋 未着手
```

### v5 戦略方針転換（本セッションで確定）
- **資格管理フック完全廃止** — `/crew/certificates` は作らない
- **Ship Specs + マッチングエンジンに 100% 集中**
- **Self-hosted Runner 採用**（NK の GHA IP ブロック対策）
- 詳細: `plan/STRATEGIC_PIVOT_v5.md`

---

## 2. 最初にやること

```
1. plan/PROGRESS.md を読んで詳細を把握
2. ユーザーに以下2つの手動作業が完了したか確認:
   a) Supabase で 00005 SQL の残り部分を実行（下記参照）
   b) GitHub Secrets の GEMINI_MODEL / GEMINI_FALLBACK_MODEL を削除
3. 完了していれば → MLIT RSS 本番再実行 + NK 本番実行
4. 未完了であれば → ユーザーに作業を促す
```

---

## 3. ユーザー待ちの手動作業（2つ）

### A. Supabase SQL 実行（途中で止まっている）

`00005_ship_profiles.sql` を Supabase で実行中にトリガー重複エラーが発生。
`ship_profiles` テーブルとトリガーは作成済みだが、以下がまだ：

```sql
-- user_matches テーブル
CREATE TABLE IF NOT EXISTS user_matches (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    regulation_id           UUID NOT NULL REFERENCES regulations(id) ON DELETE CASCADE,
    ship_profile_id         UUID NOT NULL REFERENCES ship_profiles(id) ON DELETE CASCADE,
    is_applicable           BOOLEAN,
    match_method            TEXT NOT NULL DEFAULT 'rule_based',
    confidence              FLOAT,
    reason                  TEXT,
    citations               JSONB,
    notified                BOOLEAN DEFAULT false,
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now(),
    UNIQUE(regulation_id, ship_profile_id)
);

CREATE TRIGGER user_matches_updated_at
    BEFORE UPDATE ON user_matches
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE INDEX IF NOT EXISTS idx_user_matches_ship_profile ON user_matches(ship_profile_id);
CREATE INDEX IF NOT EXISTS idx_user_matches_regulation   ON user_matches(regulation_id);
CREATE INDEX IF NOT EXISTS idx_user_matches_unnotified   ON user_matches(notified) WHERE notified = false;

-- RLS: ship_profiles
ALTER TABLE ship_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ship_profiles_owner_select" ON ship_profiles
    FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "ship_profiles_owner_insert" ON ship_profiles
    FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "ship_profiles_owner_update" ON ship_profiles
    FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "ship_profiles_owner_delete" ON ship_profiles
    FOR DELETE TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "ship_profiles_service_all" ON ship_profiles
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- RLS: user_matches
ALTER TABLE user_matches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_matches_owner_select" ON user_matches
    FOR SELECT TO authenticated
    USING (ship_profile_id IN (SELECT id FROM ship_profiles WHERE user_id = auth.uid()));
CREATE POLICY "user_matches_service_all" ON user_matches
    FOR ALL TO service_role USING (true) WITH CHECK (true);
```

### B. GitHub Secrets の削除

`GEMINI_MODEL` と `GEMINI_FALLBACK_MODEL` を Secrets から**削除**する。
空文字の Secret が環境変数を上書きして Gemini API が 404 になる原因。
削除すれば `gemini_client.py` のデフォルト値（`gemini-2.5-flash` / `gemini-2.0-flash`）が使われる。

---

## 4. 完了済みタスク一覧

| タスク | 状態 | コミット |
|--------|------|---------|
| Supabase マイグレーション (00001-00004) | ✅ 適用済み | f852231 |
| process-queue + health-check ワークフロー | ✅ | 6380a7c |
| MLIT RSS URL 修正 (pressrelease.rdf) | ✅ | 6888519 |
| 戦略方針転換 v5 文書 | ✅ | cd0fe81 |
| Self-hosted Runner 手順書 + NK ワークフロー修正 | ✅ | 9a33fc7 |
| ship_profiles SQL + matching.py | ✅ | 2b40a09 |
| Gemini 精度レポート | ✅ | 2b40a09 |
| classify_pdf pending バグ修正 | ✅ | 2b40a09 |
| NK bot UA 環境変数削除 | ✅ | ca4e0f1 |
| **Self-hosted Runner 稼働** | ✅ | — |
| **NK dry-run (Self-hosted 経由)** | ✅ **50件パース成功** | — |
| **MLIT RSS dry-run (GHA)** | ✅ **8件海事関連検出** | — |

---

## 5. ユーザー作業完了後の次のアクション

### 1. MLIT RSS 本番実行（Gemini Secret 修正後）
```bash
gh workflow run scrape-mlit-rss.yml --field dry_run=false --field limit=5
```
- Gemini 分類が成功するか確認
- confidence 値、category の妥当性を検証

### 2. NK 本番実行（Self-hosted Runner で）
```bash
gh workflow run scrape-nk.yml --field dry_run=false --field limit=3
```
- Self-hosted Runner 経由で ClassNK にアクセス
- PDF ダウンロード → Gemini 分類 → Supabase upsert の全パイプラインを検証

### 3. Phase 1 R2 完了判定
上記2つが成功すれば Phase 1 R2 完了。Phase 2（フロントエンド MVP）に進む。

---

## 6. 知っておくべきこと

### Self-hosted Runner の状態
- ランナー名: `B-A59000-089`
- ラベル: `self-hosted, Windows, X64, nk-runner`
- 稼働方法: `C:\actions-runner\run.cmd` をバックグラウンド実行（サービス化は未完了、管理者権限不足）
- **PC 再起動後は `C:\actions-runner\run.cmd` を再実行する必要あり**

### NK スクレイパーの注意点
- `SCRAPE_USER_AGENT` 環境変数を設定してはいけない（Chrome UA のデフォルト値を使う）
- ワークフローの `environment: production` が設定されている — GitHub で Environment `production` を作成していない場合、ジョブが保留になる可能性あり（現在は未作成でも動いている）

### Gemini の注意点
- `GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` は Secret ではなく Variables (vars) で設定するか、未設定でデフォルト値を使う
- `classify_pdf` は失敗時に例外を投げず `{"status": "pending"}` を返す → 呼び出し側でチェック必須（修正済み）

### 設計文書の優先順位
1. `plan/STRATEGIC_PIVOT_v5.md` — 最上位の意思決定文書
2. `plan/MARITIME_PROJECT_BLUEPRINT_v4.md` — 技術詳細（v5 と矛盾する場合は v5 優先）
3. `CLAUDE.md` — コーディング規約・運用ルール

### 過去の罠（再発防止）
1. `send_line_notify` は存在しない → 正しくは `send_alert`
2. `scripts/` から `utils/` を import するには `sys.path.insert` 必須
3. ClassNK は GHA IP + bot UA の両方をブロック → Self-hosted Runner + Chrome UA で解決
4. Supabase の空文字 Secret が環境変数のデフォルト値を上書きする
5. `classify_pdf` は例外ではなく `status=pending` を返す → `except` だけでは捕捉できない
6. `00005_ship_profiles.sql` は途中で止まった → user_matches + RLS が未適用

---

## 7. 必要な環境変数（GitHub Secrets）

| 変数名 | 状態 | 備考 |
|--------|------|------|
| `SUPABASE_URL` | ✅ 設定済み | |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ 設定済み | |
| `GEMINI_API_KEY` | ✅ 設定済み | |
| `GEMINI_MODEL` | ❌ **削除必要** | 空文字 Secret が 404 の原因 |
| `GEMINI_FALLBACK_MODEL` | ❌ **削除必要** | 同上 |
| `LINE_NOTIFY_TOKEN` | 未設定 | 通知不要なら後回し |
| `GDRIVE_FOLDER_ID` | 未設定 | テキスト保存不要なら後回し |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 未設定 | Drive API 不要なら後回し |
