# Self-hosted Runner セットアップガイド

## 目的

ClassNK (classnk.or.jp) は GitHub Actions が使用する IP レンジを完全にブロックしている。
ローカル PC (Windows 11) は正常にアクセスできるため、開発 PC を GitHub Self-hosted Runner として
登録し、NK スクレイパーをローカル環境から自動実行する。

---

## セキュリティ警告（必読）

> **このリポジトリは Public です。Self-hosted Runner を Public リポジトリに登録する場合、
> 外部からのプルリクエストに含まれる悪意あるワークフローがあなたの PC 上で実行される
> 可能性があります。**

### リスク

- 任意の fork からの PR がワークフローをトリガーし、ランナー上でコードを実行できる
- ランナーの PC に保存された secrets や環境変数が漏洩する恐れがある
- PC のファイルシステム・ネットワークへの不正アクセスが起こりえる

### 必須の対策

1. **Environment Protection Rules を設定する**
   - GitHub: Settings → Environments → New environment → `production`
   - "Required reviewers" にあなた自身を追加
   - NK ワークフローで `environment: production` を指定（本手順書の設定に含まれる）

2. **外部 PR による自動実行を抑止する**
   - Settings → Actions → General → "Fork pull request workflows"
   - "Require approval for all outside collaborators" を選択

3. **ランナーを専用ユーザーで実行する（推奨）**
   - Windows のローカルアカウントを別途作成し、最小権限で運用する
   - ただし開発 PC の兼用であれば通常ユーザーでも許容範囲

4. **不要なときはランナーサービスを停止する**
   - 長期間 PC を離れる際は `Stop-Service actions.runner.*` で停止

---

## 前提条件

| 項目 | 要件 |
|------|------|
| OS | Windows 11 |
| Python | 3.11 以上（`python --version` で確認） |
| Git | インストール済み |
| ネットワーク | classnk.or.jp に HTTP アクセスできること |
| GitHub アカウント | `ahos1215-coder` リポジトリへの Admin 権限 |

---

## Step 1: GitHub でランナーを登録する

1. ブラウザで `https://github.com/ahos1215-coder/miharikun` を開く
2. **Settings** → **Actions** → **Runners** → **New self-hosted runner** をクリック
3. OS: **Windows** を選択
4. 画面に表示される `config.cmd` コマンドと**トークン**をコピーしておく（次の手順で使用）

---

## Step 2: ランナーエージェントをダウンロードする

PowerShell（管理者権限）を開き、以下を実行する。

```powershell
# ランナーを配置するディレクトリを作成
mkdir C:\actions-runner
cd C:\actions-runner

# GitHub が表示した最新バージョンの URL に合わせること（例は執筆時点のもの）
$version = "2.324.0"
Invoke-WebRequest -Uri "https://github.com/actions/runner/releases/download/v${version}/actions-runner-win-x64-${version}.zip" -OutFile "actions-runner-win-x64-${version}.zip"

# 展開
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory("$PWD\actions-runner-win-x64-${version}.zip", "$PWD")
```

> 実際のバージョンと URL は GitHub の "New self-hosted runner" 画面に表示されるものを使用すること。

---

## Step 3: ランナーを設定する

```powershell
# GitHub の画面に表示されたコマンドをそのまま実行（トークンは画面から取得）
.\config.cmd --url https://github.com/ahos1215-coder/miharikun --token <TOKEN>
```

対話形式で以下を設定する。

| プロンプト | 推奨値 |
|-----------|--------|
| Runner group | `Default` (そのまま Enter) |
| Runner name | `win11-local`（任意。識別しやすい名前） |
| Additional labels | `nk-runner` |
| Work folder | `_work` (そのまま Enter) |

---

## Step 4: Windows サービスとして常駐させる

PowerShell（管理者権限）で実行。

```powershell
# サービスとしてインストール
.\svc.cmd install

# サービスを開始
.\svc.cmd start

# 状態確認
.\svc.cmd status
```

サービス名は `actions.runner.ahos1215-coder-miharikun.win11-local` のような形式になる。

### サービスの管理コマンド

```powershell
# 停止
.\svc.cmd stop

# 再起動
.\svc.cmd stop; .\svc.cmd start

# アンインストール（ランナー登録解除時）
.\svc.cmd uninstall
```

---

## Step 5: Environment Protection Rules を設定する

1. GitHub: **Settings** → **Environments** → **New environment**
2. 名前: `production`
3. **Required reviewers** にあなたのアカウントを追加
4. **Save protection rules**

これにより、外部 PR からのワークフロー実行が `production` 環境への承認なしに進まなくなる。

---

## Step 6: 動作確認

1. GitHub: **Actions** → **NK Daily Scraper** → **Run workflow** を手動実行
2. ランナー PC のタスクマネージャーで `Runner.Worker.exe` が起動することを確認
3. ワークフローログで `self-hosted` ランナーが使われていることを確認

---

## Step 7: Python 環境の確認

Self-hosted Runner では `actions/setup-python` が動作しない場合がある。
スクリプトは以下の優先順位で Python を解決する。

1. `python3.11`（PATH に存在する場合）
2. `python3`
3. `python`（system Python）

Windows の場合は `py -3.11` コマンドも利用可能。
インストール済み Python のバージョンを確認しておく。

```powershell
python --version
py -3.11 --version   # Python Launcher 経由
```

依存パッケージは初回実行前に手動でインストールしておくことを推奨。

```powershell
cd C:\Users\Shouma.abe\Desktop\All Python project\miharikun
pip install -r scripts/requirements.txt
```

---

## トラブルシューティング

| 症状 | 確認事項 |
|------|---------|
| ランナーが "Offline" | サービスが起動しているか `.\svc.cmd status` で確認 |
| Python が見つからない | `python --version` で確認。ワークフローの fallback ステップを参照 |
| pip install が失敗 | `pip install --upgrade pip` の後に再試行 |
| classnk.or.jp に接続できない | ブラウザで直接アクセスして確認。VPN や Proxy の影響を疑う |
| サービスがクラッシュする | `C:\actions-runner\_diag\` 配下のログを確認 |

---

## 参考リンク

- [GitHub Docs: About self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners)
- [GitHub Docs: Security hardening for self-hosted runners](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions#hardening-for-self-hosted-runners)
- [GitHub Docs: Using environments for deployment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
