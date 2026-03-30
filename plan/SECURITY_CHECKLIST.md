# Security Checklist — MIHARIKUN (Public Repository)

## リポジトリは Public です

このリポジトリは GitHub Actions の無制限利用のために **Public** に設定されています。
つまり、コミットされた全てのファイル・履歴は誰でも閲覧可能です。

**絶対にやってはいけないこと:**
- API キー、トークン、パスワードをコードやコミット履歴に含める
- `.env` ファイルをコミットする
- サービスアカウント JSON をコミットする

---

## シークレット管理一覧

| シークレット名 | 用途 | 保管場所 |
|---|---|---|
| `SUPABASE_URL` | Supabase プロジェクト URL | GitHub Secrets / Vercel env |
| `SUPABASE_ANON_KEY` | Supabase anon key (RLS 適用) | GitHub Secrets / Vercel env / `NEXT_PUBLIC_*` OK |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase 管理用キー (RLS バイパス) | GitHub Secrets のみ |
| `GEMINI_API_KEY` | Google Gemini API キー | GitHub Secrets のみ |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Drive API 用サービスアカウント | GitHub Secrets のみ |
| `LINE_NOTIFY_TOKEN` | LINE Notify 通知用トークン | GitHub Secrets のみ |
| `RESEND_API_KEY` | メール送信 API キー | GitHub Secrets / Vercel env |
| `NK_USERNAME` / `NK_PASSWORD` | NK サイトログイン情報 | GitHub Secrets のみ |

### 保管場所の使い分け
- **GitHub Secrets**: GHA ワークフローから参照。`${{ secrets.KEY_NAME }}`
- **Vercel Environment Variables**: Next.js アプリから参照。フロント公開可は `NEXT_PUBLIC_` プレフィックス
- **ローカル `.env`**: 開発時のみ使用。`.gitignore` に含まれていること

---

## RLS (Row Level Security) ポリシー

Supabase の RLS により、anon key でアクセスしてもデータが制限されます。

| テーブル | ポリシー | 説明 |
|---|---|---|
| `regulations` | SELECT: 全ユーザー読み取り可 | 規制情報は公開データ |
| `ship_profiles` | SELECT/INSERT/UPDATE/DELETE: `auth.uid() = user_id` | 自分の船舶情報のみ操作可 |
| `notifications` | SELECT: `auth.uid() = user_id` | 自分宛の通知のみ閲覧可 |
| `matching_results` | SELECT: `auth.uid() = user_id` | 自分のマッチング結果のみ |
| `user_preferences` | SELECT/UPDATE: `auth.uid() = user_id` | 自分の設定のみ |

**重要**: `SERVICE_ROLE_KEY` は RLS をバイパスします。GHA ワークフロー内でのみ使用し、フロントエンドには絶対に渡さないこと。

---

## 公開データ vs 非公開データ

### 公開 (誰でもアクセス可)
- リポジトリのソースコード
- 規制情報のメタデータ (タイトル、発行日、ソース)
- GitHub Actions のワークフロー定義

### 非公開 (認証必須)
- ユーザーの船舶プロファイル
- マッチング結果 (どの規制がどの船に関係あるか)
- 通知設定・通知履歴
- ユーザーアカウント情報

### インフラ非公開 (Secrets で保護)
- 全ての API キー・トークン
- DB 接続情報
- サービスアカウント認証情報

---

## シークレット漏洩時の対応手順

### 即座に実施 (5分以内)

1. **漏洩したキーを無効化/ローテーション**
   - Supabase: ダッシュボード > Settings > API > Regenerate keys
   - Gemini: Google Cloud Console > Credentials > 該当キーを削除・再作成
   - LINE Notify: トークンを revoke して再発行
   - Google Service Account: キーを削除して新しい JSON を生成

2. **GitHub 履歴からの削除**
   ```bash
   # コミット履歴からファイルを完全削除
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch <漏洩ファイルパス>" \
     --prune-empty --tag-name-filter cat -- --all
   git push --force --all
   ```

3. **新しいキーを GitHub Secrets / Vercel env に設定**

### 確認事項
- [ ] 漏洩したキーで不正アクセスがなかったか確認 (Supabase ログ, GCP ログ)
- [ ] GitHub の Secret scanning alerts を確認
- [ ] 全ワークフローが新しいキーで動作するかテスト

### 予防策
- `security-scan.yml` ワークフローが PR ごとに TruffleHog を実行
- `.gitignore` に `.env*`, `*.pem`, `*credentials*.json` が含まれていること
- コミット前に `git diff --staged` で secrets が含まれていないか目視確認

---

## 定期チェック項目 (月1回)

- [ ] GitHub Secret scanning alerts に未対応のものがないか
- [ ] `npm audit` / `pip-audit` で critical 脆弱性がないか
- [ ] Supabase ダッシュボードで不審なアクセスがないか
- [ ] 使用していない API キーがないか (不要なら無効化)
- [ ] RLS ポリシーが意図通り動作しているか (テスト実行)
- [ ] `.gitignore` が適切か (新しい機密ファイルパターンが漏れていないか)
