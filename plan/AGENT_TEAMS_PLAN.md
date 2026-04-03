> **⚠️ アーカイブ文書**: このドキュメントは歴史的記録として保持されています。現在のシステム構成は `plan/HANDOFF.md` を参照してください。

# MIHARIKUN — Agent Teams 実装計画書
Last updated: 2026-03-29

> **前提**: Max $100 プラン（5時間あたり ~88,000 トークン）
> Agent Teams はリサーチプレビュー。`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` で有効化。
> 設計書: `plan/MARITIME_PROJECT_BLUEPRINT_v4.md`

---

## 1. Gemini 調査からの重要な制約（設計に直接影響するもの）

### 1.1 コストの現実

| 構成 | トークン消費倍率 | $100 Max での実稼働イメージ |
|------|----------------|--------------------------|
| 単一セッション | 1x | 1日中使える |
| Agent Teams 3人 | 3-4x | **1日2-3回の集中セッション** |
| Agent Teams 5人 | 5-7x | 1日1-2回が限界 |

→ **3人チームを基本単位とし、1回のセッションで明確なゴールを設定して使い切る**。

### 1.2 ルール違反リスク

Gemini調査が指摘した3つのリスクはMIHARIKUNでも直接該当する:

| リスク | MIHARIKUNでの具体例 | 対策 |
|--------|-------------------|------|
| ラッシュモード | 「スクレイパーもGHAもDBも全部一気に作って」→ テストを飛ばす | 1セッション1目標に限定 |
| コンテキスト圧縮による忘却 | 長時間セッション後半で「Vercelで Gemini を呼ばない」ルールを忘れる | CLAUDE.md を5行以内の致命ルールに凝縮 |
| 自律的リスク評価の誤謬 | 「この小さな修正ならRLSポリシーは不要だろう」と判断 | Hooks でテスト通過を強制 |

### 1.3 CLAUDE.md の設計指針

Gemini調査の知見: **200行超のCLAUDE.mdはアテンション分散でルール遵守率が低下する**。
→ 致命ルールを「5行の非交渉的命令」に凝縮し、詳細は `plan/` に分離。

---

## 2. CLAUDE.md（Agent Teams 最適化版）

IMPLEMENTATION_GUIDE.md に記載した CLAUDE.md を Agent Teams 向けに再設計する。

```markdown
# CLAUDE.md — MIHARIKUN

## 絶対ルール（破ったら即停止）
1. Vercel API Routes で Gemini API を呼ぶな（GHA でやれ）
2. secrets をコミットするな（GitHub Secrets / Vercel env のみ）
3. Supabase の書き込みに SERVICE_ROLE_KEY を使え（anon key で書くな）
4. テストなしのPR・完了報告を出すな
5. `plan/MARITIME_PROJECT_BLUEPRINT_v4.md` と矛盾するコードを書くな

## 参照ドキュメント（詳細はこちら）
- 設計書: `plan/MARITIME_PROJECT_BLUEPRINT_v4.md`
- 環境変数: `plan/ENV.md`
- ディレクトリ構成: `plan/INDEX.md`
- 意思決定ログ: `plan/DECISIONS.md`

## テックスタック
- Frontend: Next.js 14+ (App Router) / TypeScript / Tailwind CSS
- Backend バッチ: GitHub Actions / Python 3.11+
- DB: Supabase (PostgreSQL + Auth + RLS)
- AI: Gemini 2.5 Flash
- 通知: LINE Notify + Resend (メール)
```

**ポイント**: 致命ルール5行 + 参照リンクだけ。コーディング規約やテスト方針の詳細は `plan/` に置く。Agent Teams のチームメイトは必要に応じて `plan/` を読みに行く。

---

## 3. Phase 別 Agent Teams 戦略

### Phase 0: 基盤構築 — 単一セッション（Agent Teams 不要）

**理由**: リポジトリ作成、Supabase/Vercel 設定、plan/ 配置は順序依存が強く、並列化の余地がない。トークンを節約すべき。

```
Claude Code（単一セッション）
  └─ リポジトリ作成 + CLAUDE.md 配置
  └─ plan/ フォルダに設計書・ENV.md・INDEX.md を配置
  └─ Next.js プロジェクト初期化（npx create-next-app）
  └─ Supabase マイグレーション SQL 実行
  └─ GHA ワークフローの雛形作成
  └─ Vercel 連携設定
```

**所要トークン**: 単一セッション × 1-2回 ≈ 通常消費

---

### Phase 1: データ収集パイプライン — Agent Teams（3人チーム × 2ラウンド）

**理由**: NK スクレイパー、国交省スクレイパー、Gemini 分類パイプラインは**独立したモジュール**であり、並列開発に最適。互いのコードに依存しないため、マージ競合も起きにくい。

#### ラウンド 1: スクレイパー構築（チーム 3人）

```
チーム・リード: 全体の統合・品質管理

  ├─ Agent A「NK担当」
  │    ├─ scrape_nk.py の本番化（プロトタイプから）
  │    ├─ scrape-nk.yml の GHA ワークフロー
  │    ├─ test_scrape_nk.py（pytest + fixtures）
  │    └─ utils/supabase_client.py
  │
  ├─ Agent B「国交省担当」
  │    ├─ scrape_mlit_rss.py（第1層 RSS）
  │    ├─ scrape_mlit_crawl.py（第2層 クロール）
  │    ├─ scrape-mlit-rss.yml + scrape-mlit-crawl.yml
  │    ├─ utils/pdf_preprocess.py
  │    └─ テスト
  │
  └─ Agent C「共通基盤担当」
       ├─ utils/gemini_client.py（フォールバック付き）
       ├─ utils/line_notify.py
       ├─ utils/gdrive_client.py
       ├─ notify-on-failure.yml（再利用ワークフロー）
       └─ テスト
```

**リードへの指示プロンプト（例）**:
```
MIHARIKUNプロジェクトのPhase 1を開始する。
Agent Teamを3人で構成してほしい。

計画:
- Agent A: scripts/scrape_nk.py の本番化。プロトタイプは既に
  plan/ に仕様がある。GHAワークフローとテストも書く。
- Agent B: scripts/scrape_mlit_rss.py と scrape_mlit_crawl.py を
  新規作成。plan/MARITIME_PROJECT_BLUEPRINT_v4.md のセクション3.3を参照。
- Agent C: scripts/utils/ の共通ユーティリティ（gemini_client.py,
  line_notify.py, gdrive_client.py）を作成。他の2人が使う基盤。

Agent C は先に共通ユーティリティを完成させ、A と B に知らせること。
各自、完了前にテストを必ず実行すること。
```

#### ラウンド 2: 分類パイプライン + 自動回復（チーム 3人）

```
チーム・リード: 統合テスト

  ├─ Agent A「Gemini 分類」
  │    ├─ classify_gemini.py（本番プロンプト組み込み）
  │    ├─ Confidence Score + Citations の JSON 出力検証
  │    ├─ スナップショットテスト（既知 PDF → 期待出力）
  │    └─ process_pending_queue.py（未処理リトライ）
  │
  ├─ Agent B「ヘルスチェック + 自動回復」
  │    ├─ health_check.py
  │    ├─ health-check.yml
  │    ├─ process-queue.yml
  │    └─ 各スクレイパーのフォールバック機構追加
  │
  └─ Agent C「週次サマリー + 通知」
       ├─ weekly_summary.py
       ├─ weekly-summary.yml
       └─ メール送信テスト（Resend）
```

---

### Phase 2: フロントエンド MVP — Agent Teams（3人チーム × 2ラウンド）

**理由**: ページコンポーネント、認証/DB層、UI共通部品は並列開発可能。ただし同一ファイル（layout.tsx等）への競合に注意。

#### ラウンド 1: 基盤 + 認証 + 資格管理（チーム 3人）

```
  ├─ Agent A「認証 + DB 層」
  │    ├─ lib/supabase/client.ts + server.ts + types.ts
  │    ├─ (auth)/login/page.tsx + signup/page.tsx
  │    ├─ Supabase Auth の設定
  │    └─ RLS ポリシーの検証
  │
  ├─ Agent B「資格管理ページ」（MVP の入口）
  │    ├─ crew/page.tsx
  │    ├─ crew/certificates/page.tsx
  │    ├─ components/crew/CertificateList.tsx
  │    ├─ components/crew/CertificateForm.tsx
  │    └─ components/crew/ExpiryAlert.tsx
  │
  └─ Agent C「共通 UI + レイアウト」
       ├─ app/layout.tsx（免責フッター含む）
       ├─ components/layout/Header.tsx + Footer.tsx
       ├─ components/ui/（Button, Card, Badge）
       └─ tailwind.config.ts のカスタマイズ
```

#### ラウンド 2: ニュース + ダッシュボード（チーム 3人）

```
  ├─ Agent A「ニュースページ」
  │    ├─ news/page.tsx（6カテゴリタブ）
  │    ├─ news/[id]/page.tsx（AI要約 + 根拠引用）
  │    ├─ components/news/NewsList.tsx + NewsCard.tsx
  │    └─ components/news/ConfidenceBadge.tsx
  │
  ├─ Agent B「ダッシュボード + マッチング」
  │    ├─ dashboard/page.tsx
  │    ├─ lib/matching/matchRegulations.ts
  │    ├─ components/dashboard/MatchedRegulations.tsx
  │    └─ components/dashboard/SourceStatus.tsx
  │
  └─ Agent C「管理者ページ + 設定」
       ├─ admin/health/page.tsx（乗船前チェック）
       ├─ settings/page.tsx（通知設定）
       ├─ api/health/route.ts
       └─ api/match/route.ts
```

---

### Phase 3: 拡張 — 状況に応じて単一 or チーム

Phase 3 は機能追加が主なので、各機能の規模に応じて判断する。
- 船舶スペック登録（小規模）→ 単一セッション
- LINE 通知本格化（中規模）→ 単一セッション
- Fleet プラン・B2B（大規模）→ Agent Teams 3人

---

## 4. トークン節約戦術

### 4.1 仕様駆動開発（Spec-Driven）

Gemini調査の最重要指摘: **曖昧な指示は並列環境で莫大なコスト増になる**。

→ 各ラウンドの前に、人間が `plan/` に仕様書を書いておく。Agent Teams は仕様書を読んでコードを書くだけ。「何を作るか」で迷わせない。

今日このチャットで作成した設計書v4 + 実装指示書が、そのまま仕様書として機能する。

### 4.2 セッション管理

| アクション | タイミング | 効果 |
|-----------|----------|------|
| `/compact` 実行 | 各ラウンドの中盤 | 過去の履歴を要約し、プロンプトコスト削減 |
| チームのクリーンアップ | 各ラウンド完了時 | **必ずリードから終了**。チームメイトから終了しない |
| ラウンド間の休憩 | ラウンド完了後 | 5時間ローリングウィンドウのリセットを待つ |

### 4.3 1日の推奨スケジュール（$100 Max）

```
09:00-12:00  Agent Teams ラウンド 1（3人チーム、集中作業）
             └─ 完了後クリーンアップ
12:00-14:00  休憩（ローリングウィンドウ回復待ち）
14:00-17:00  Agent Teams ラウンド 2（3人チーム、集中作業）
             └─ 完了後クリーンアップ
17:00-       単一セッションで軽いバグ修正・ドキュメント更新
```

**1日2ラウンドが $100 Max の現実的な上限**。無理に3ラウンド目を詰めるとトークン枯渇で中途半端に終わるリスクがある。

---

## 5. Hooks によるガードレール

CLAUDE.md だけでは「確率的に」無視されるリスクがある。以下の Hooks で物理的に強制する。

### 5.1 設定ファイル（`.claude/hooks.json`）

```json
{
  "hooks": {
    "TaskCompleted": {
      "command": "bash .claude/hooks/check-tests.sh",
      "description": "テスト未実行のタスク完了を拒否"
    },
    "PreCommit": {
      "command": "bash .claude/hooks/check-secrets.sh",
      "description": "secrets のコミットを物理的にブロック"
    }
  }
}
```

### 5.2 テスト強制スクリプト（`.claude/hooks/check-tests.sh`）

```bash
#!/bin/bash
# Python テストの実行チェック
if ls scripts/test_*.py 1>/dev/null 2>&1; then
  cd scripts && python -m pytest --tb=short -q
  if [ $? -ne 0 ]; then
    echo "ERROR: Python テストが失敗しています。タスクを完了できません。"
    exit 1
  fi
fi

# フロントエンドテストのチェック
if [ -f frontend/package.json ]; then
  cd frontend && npx vitest run --reporter=verbose 2>/dev/null
  if [ $? -ne 0 ]; then
    echo "ERROR: フロントエンドテストが失敗しています。"
    exit 1
  fi
fi

echo "OK: すべてのテストが通過しました。"
exit 0
```

### 5.3 Secrets 漏洩防止（`.claude/hooks/check-secrets.sh`）

```bash
#!/bin/bash
# コミット対象に secrets パターンが含まれていないかチェック
PATTERNS="SUPABASE_SERVICE_ROLE_KEY|GEMINI_API_KEY|GOOGLE_SERVICE_ACCOUNT|LINE_NOTIFY_TOKEN|RESEND_API_KEY"
FOUND=$(git diff --cached --name-only | xargs grep -l -E "$PATTERNS" 2>/dev/null)
if [ -n "$FOUND" ]; then
  echo "BLOCKED: 以下のファイルに secrets パターンが検出されました:"
  echo "$FOUND"
  echo "secrets は GitHub Secrets / Vercel env に設定してください。"
  exit 1
fi
exit 0
```

---

## 6. Agent Skills の活用

Gemini調査の知見: **大きなドキュメントは初期コンテキストにロードせず、Skills としてオンデマンドで呼び出す**。

### 6.1 Skills ディレクトリ構成

```
.claude/skills/
  ├─ supabase-schema.md      # 全テーブル定義 + RLS ポリシー
  ├─ gemini-prompt.md         # 分類プロンプトの仕様
  ├─ nk-scraper-spec.md       # NK スクレイパーの詳細仕様
  ├─ mlit-strategy.md         # 国交省 3層戦略の詳細
  └─ error-handling.md        # エラーハンドリング表
```

→ CLAUDE.md は5行のルールだけ。詳細な仕様はスキルとして必要なときだけ読み込ませる。トークン節約効果が大きい。

---

## 7. 6つの危惧への具体的対策

### 危惧①: 意図せぬ方向に進み出すこと

**根本原因**: リードへの指示が曖昧だと、エージェントが「良かれと思って」独自に判断し、設計書と矛盾する実装を始める。

**対策: 「チェックポイント承認制」を導入する**

各ラウンドを3段階に分け、段階ごとに人間の承認を挟む。

```
Step 1: 計画提示（エージェントが作業計画を出す → 人間がレビュー）
   ↓ 人間が「OK」と言うまで進まない
Step 2: 実装（承認された計画に沿ってコードを書く）
   ↓ 50%完了時点でリードが中間報告
Step 3: 完了報告（テスト結果 + diff サマリー → 人間がレビュー）
   ↓ 人間が「マージ」と言うまで main に入れない
```

**リードへの指示プロンプトに以下を必ず含める**:
```
【重要ルール】
1. 作業開始前に「何をどのファイルに書くか」の計画を出して、
   私の承認を待ってから実装に入ること。
2. 計画にないファイルの作成・既存ファイルの大幅な変更は
   事前に私に相談すること。
3. 設計書 plan/MARITIME_PROJECT_BLUEPRINT_v4.md に
   書いていない機能を勝手に追加しないこと。
4. 迷ったら止まって聞くこと。推測で進めないこと。
```

**Git ブランチ戦略**:
```
main（保護ブランチ — 直接 push 禁止）
  └─ feat/phase1-round1（Agent Teams の作業ブランチ）
       ├─ Agent A → scraper-nk ファイル群
       ├─ Agent B → scraper-mlit ファイル群
       └─ Agent C → utils ファイル群
  人間がレビュー後に main へ merge
```

GitHub の Branch Protection Rules で `main` への直接 push を禁止し、
必ず PR 経由にすることで、人間のレビューなしにコードが本番に入ることを防ぐ。

---

### 危惧②: ループして無駄にトークンを消費すること

**根本原因**: エージェントがエラーを解決できず、同じ修正を繰り返す無限ループに陥る。
特に「テスト失敗 → 修正 → 別のテスト失敗 → 修正 → 最初のテストが再度失敗」のサイクル。

**対策: 3つのブレーカーを設置する**

**ブレーカー 1: リトライ上限の明示指示**
```
【リトライルール】
- 同じエラーが3回続いたら、修正を試みず「このエラーを解決できません」と
  報告して私に判断を仰ぐこと。
- テストが5回連続で失敗したら、作業を中断して現状を報告すること。
- 「もう少しで直りそう」という判断で勝手にリトライ回数を延長しないこと。
```

**ブレーカー 2: タイムボックスの設定**
```
【時間制限】
- 各チームメイトの1タスクあたりの作業時間の目安は30分以内。
- 30分経過しても完了しない場合は、途中経過を報告して指示を待つこと。
```

**ブレーカー 3: Hooks による物理制限**

```bash
# .claude/hooks/check-loop.sh
#!/bin/bash
# 同じファイルが短時間に10回以上編集されていたらループ疑い
FILE_EDITS=$(git log --oneline --since="30 minutes ago" --name-only | sort | uniq -c | sort -rn | head -1 | awk '{print $1}')
if [ "$FILE_EDITS" -gt 10 ] 2>/dev/null; then
  echo "WARNING: 同じファイルが30分間に10回以上編集されています。ループの疑いがあります。"
  echo "作業を一時停止し、人間に確認を取ってください。"
  exit 1
fi
exit 0
```

---

### 危惧③: ファイルの同時編集でファイルが壊れること

**根本原因**: 2人のエージェントが同じファイル（layout.tsx, package.json 等）を同時に編集し、
一方の変更が他方に上書きされてコードが壊れる。

**対策: ファイル所有権マップを明示する**

各ラウンドのリード指示に「ファイル所有権マップ」を含める。

```
【ファイル所有権（厳守）】

Agent A の専有ファイル（Agent A 以外は触るな）:
- scripts/scrape_nk.py
- scripts/test_scrape_nk.py
- .github/workflows/scrape-nk.yml

Agent B の専有ファイル:
- scripts/scrape_mlit_rss.py
- scripts/scrape_mlit_crawl.py
- .github/workflows/scrape-mlit-*.yml

Agent C の専有ファイル:
- scripts/utils/*.py
- .github/workflows/notify-on-failure.yml

共有ファイル（Agent C が一元管理。A, B は編集禁止）:
- requirements.txt
- frontend/src/app/layout.tsx
- package.json

他のエージェントの専有ファイルを編集する必要がある場合は、
メッセージで依頼して相手に書いてもらうこと。自分で直接編集しないこと。
```

**Git Worktrees の活用**（Phase 2 以降、フロントエンドで特に重要）:
```
【リードへの指示】
各チームメイトに独立した Git Worktree を割り当てて作業させること。
完了後に私がマージする。同一ディレクトリでの同時作業は禁止。
```

---

### 危惧④: 私の意志が介入する隙間がなくなること

**根本原因**: Agent Teams が自律的に進めすぎて、人間が状況を把握できないまま
大量のコードが生成され、後から修正するコストが膨大になる。

**対策:「人間ゲート」を設計に組み込む**

```
【全ラウンド共通のワークフロー】

         人間         リード        チームメイト
          │              │              │
  目標を指示 ──────→      │              │
          │      計画を提示 ←─────       │
  計画を承認 ──────→      │              │
          │        タスク分配 ──────→     │
          │              │         作業中...
          │      中間報告 ←──────        │
  方向性確認 ──────→      │              │
          │              │         作業継続...
          │      完了報告 ←──────        │
  diff 確認  ──────→      │              │
  merge 判断 ──────→      │              │
          │              │              │
```

**具体的な介入ポイント**:

| タイミング | 人間がやること | 所要時間 |
|-----------|-------------|---------|
| ラウンド開始時 | リードが出す計画をレビュー | 5分 |
| 中間報告時 | 方向性がずれていないか確認 | 3分 |
| 完了報告時 | `git diff` でコード差分を確認 | 10分 |
| merge 前 | PR をレビューして main に merge | 5分 |

**ラウンド中にリアルタイムで介入したい場合**:
- インプロセスモードなら `Shift+Down` でフォーカスを切り替えて直接指示
- 分割ペインモードなら個別のチームメイトのパネルに直接メッセージ
- Dispatch（モバイル）からリードにメッセージを送ることも可能

**「今は見てるだけ」モードと「今は積極介入」モードを宣言する**:
```
リードへの指示例:
「今から30分間は質問があっても止まらずに進めてよい。
 30分後に中間報告をして、そこで私がレビューする。」

または:
「今回は各タスクの完了ごとに私に報告して承認を待つこと。
 自分の判断で次のタスクに進まないこと。」
```

---

### 危惧⑤: モデル選定が最適でないままトークンを浪費すること

**根本原因**: Agent Teams のデフォルトでは全エージェントが Opus を使うが、
すべてのタスクに Opus が必要なわけではない。単純なコード生成やテスト作成は
Sonnet で十分であり、Opus はアーキテクチャ判断やコードレビューに使うべき。

**対策: 役割ごとにモデルを指定する**

```
【モデル割り当て戦略】

リード（計画・統合・品質管理）: Opus 4.6
  → アーキテクチャ判断、タスク分解、最終レビューに Opus の推論力が必要

チームメイト（実装・テスト）: Sonnet 4.6
  → コード生成、テスト作成は Sonnet で十分。トークンコストも低い

リードへの指示:
「チームメイトは全員 Sonnet を使用すること。
 model: sonnet で各チームメイトを生成すること。」
```

**タスクごとの使い分け表**:

| タスク | 推奨モデル | 理由 |
|--------|----------|------|
| タスク分解・計画立案 | Opus | 複雑な依存関係の分析 |
| スクレイパーのコード生成 | Sonnet | 定型的な処理 |
| GHA ワークフロー作成 | Sonnet | YAML の定型パターン |
| Gemini プロンプト設計 | Opus | プロンプトエンジニアリングには高い推論力 |
| React コンポーネント作成 | Sonnet | UI パターンの適用 |
| テストコード作成 | Sonnet | テストは定型的 |
| DB スキーマ設計 | Opus | RLS やインデックスの設計判断 |
| コードレビュー・統合 | Opus | 全体の整合性チェック |

**トークン節約効果**:
Sonnet は Opus の約 1/5 のトークンコスト。チームメイト3人を Sonnet にすれば、
同じ予算で **2-3倍の作業量** をこなせる。

---

### 危惧⑥: 時間があるときはシングルモードで作業したいこと

**根本原因**: Agent Teams が常に最適とは限らない。小規模な修正、バグ修正、
ドキュメント更新は単一セッションの方がトークン効率がよく、制御もしやすい。

**対策:「モード判定マトリクス」を用意する**

```
【判定フロー: Agent Teams vs 単一セッション】

Q1: 作業の所要時間は？
  → 30分以内で終わる → 単一セッション
  → 1時間以上かかる → Q2へ

Q2: 独立した並列作業に分解できるか？
  → できない（順序依存が強い）→ 単一セッション
  → 3つ以上に分解できる → Q3へ

Q3: 今日のトークン残量は十分か？
  → 残り少ない → 単一セッション
  → 十分ある → Agent Teams

Q4: 自分がリアルタイムで監視できるか？
  → できない（忙しい）→ 単一セッション（安全策）
  → 監視できる → Agent Teams
```

**具体的な使い分けガイド**:

| 作業 | モード | 理由 |
|------|--------|------|
| バグ修正（1ファイル） | 単一 | 並列化の余地なし |
| ドキュメント更新 | 単一 | 軽量作業 |
| 新機能の設計相談 | 単一 | 対話的な議論が必要 |
| Phase 0（基盤構築） | 単一 | 順序依存が強い |
| Phase 1-2 のラウンド実装 | Teams | 独立モジュールの並列開発 |
| 統合テスト | 単一 | 全体の流れを1人が追う方が効率的 |
| リリース前の最終確認 | 単一 | 慎重さが必要 |
| CSS/デザイン調整 | 単一 | 細かい調整は対話的に |
| DB マイグレーション追加 | 単一 | 順序が重要 |
| 3モジュール以上の新規作成 | Teams | 並列化の効果大 |

**切り替え方法**: 特別な設定は不要。Claude Code を起動して、
Agent Teams を使いたければ「チームを作って」と指示し、
単一セッションで進めたければそのままコードの話を始めるだけ。

---

## 8. 全体のガードレール設計（まとめ図）

```
┌─────────────────────────────────────────────────────┐
│                  人間のコントロール層                   │
│                                                     │
│  ・ラウンド開始時の計画承認                            │
│  ・中間報告での方向性確認                              │
│  ・完了後の diff レビュー + merge 判断                 │
│  ・モード選択（Teams / 単一）の判断権                  │
│  ・main ブランチの保護（PR 必須）                     │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│                ルール層（CLAUDE.md）                   │
│                                                     │
│  5行の致命ルール + plan/ への参照リンク               │
│  ・Vercel で Gemini 呼ぶな                           │
│  ・secrets コミットするな                             │
│  ・テストなしの完了報告出すな                          │
│  ・設計書と矛盾するコード書くな                        │
│  ・迷ったら止まって聞け                               │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│              物理制限層（Hooks + Git）                 │
│                                                     │
│  ・TaskCompleted → テスト通過を強制                   │
│  ・PreCommit → secrets パターン検出でブロック          │
│  ・ループ検知 → 同一ファイル10回編集で停止             │
│  ・Branch Protection → main 直接 push 禁止           │
│  ・ファイル所有権マップ → 他人のファイル編集禁止        │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│              コスト制御層                              │
│                                                     │
│  ・チームメイトは Sonnet（リードのみ Opus）            │
│  ・リトライ上限 3回（超えたら人間に聞く）              │
│  ・タイムボックス 30分/タスク                          │
│  ・1日2ラウンドが上限                                 │
│  ・/compact を各ラウンド中盤で実行                     │
└─────────────────────────────────────────────────────┘
```

---

## 9. リードへのマスタープロンプト（テンプレート）

すべてのラウンドで以下のテンプレートを使用する。
`{変数}` の部分をラウンドごとに書き換えて使う。

```
MIHARIKUNプロジェクトの {Phase名} {ラウンド名} を開始する。

■ 目標
{このラウンドの具体的なゴール}

■ チーム構成（全員 Sonnet を使用すること）
- Agent A「{役割名}」: {担当ファイル一覧}
- Agent B「{役割名}」: {担当ファイル一覧}
- Agent C「{役割名}」: {担当ファイル一覧}

■ ファイル所有権（厳守）
- 各エージェントは自分の担当ファイルのみ編集すること
- 共有ファイル（{共有ファイル一覧}）は Agent C が一元管理
- 他のエージェントのファイルを変更したい場合は、
  メッセージで依頼して相手に書いてもらうこと

■ ワークフロー（厳守）
1. まず作業計画を出して、私の承認を待つこと
2. 承認後に実装を開始すること
3. 50%完了時点で中間報告をすること
4. 完了時にテスト結果 + 変更ファイル一覧を報告すること
5. 私が「merge」と言うまで main にマージしないこと

■ 制限事項（厳守）
- 同じエラーが3回続いたら止まって報告すること
- テストが5回連続失敗したら作業を中断すること
- plan/MARITIME_PROJECT_BLUEPRINT_v4.md に書いていない
  機能を勝手に追加しないこと
- 迷ったら推測で進めず、私に質問すること

■ 参照ドキュメント
- 設計書: plan/MARITIME_PROJECT_BLUEPRINT_v4.md
- 環境変数: plan/ENV.md
- ディレクトリ構成: plan/INDEX.md
```

---

## 10. 全体タイムライン（更新版）

```
Week 1:  Phase 0（単一セッション × 2-3回）
         └─ リポジトリ、DB、Vercel、plan/ の基盤構築
         └─ Hooks + Branch Protection の設定

Week 2:  Phase 1 ラウンド 1（Agent Teams 3人 Sonnet）
         └─ スクレイパー 3本 + 共通ユーティリティ
         └─ 人間ゲート: 計画承認 → 中間確認 → diff レビュー

Week 3:  Phase 1 ラウンド 2（Agent Teams 3人 Sonnet）
         └─ Gemini 分類 + ヘルスチェック + 週次サマリー

Week 4:  Phase 1 統合テスト（単一セッション）
         └─ 全パイプラインの E2E 確認 + バグ修正

Week 5:  Phase 2 ラウンド 1（Agent Teams 3人 Sonnet）
         └─ 認証 + 資格管理 + 共通 UI

Week 6:  Phase 2 ラウンド 2（Agent Teams 3人 Sonnet）
         └─ ニュース + ダッシュボード + 管理者ページ

Week 7:  Phase 2 統合テスト + バグ修正（単一セッション）
         └─ MVP リリース準備

Week 8:  MVP リリース 🚀
```

---

## 11. 最初の一歩（明日やること）

1. Claude Desktop に `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` を設定
2. `claude --version` でバージョン確認（2.1.32 以降必須）
3. tmux をインストール（分割ペインモード用）
4. GitHub に `miharikun` リポジトリを **Public** で作成
5. Branch Protection Rules で main への直接 push を禁止
6. 今日作った設計書・実装指示書をリポジトリに push
7. Phase 0 を**単一セッション**で開始（Agent Teams はまだ使わない）
