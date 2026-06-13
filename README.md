# hiyokb

**ツール非依存のタスク管理＆知識ベース for Claude Code。**

GitHub / Slack / Backlog などに散らばったタスクを横断的に把握し、タスクごとの「ドシエ」
（実装方針・調査・決定事項・進捗）を `~/.hiyokb` に蓄積して、**別の Claude セッションでも
続きから引き継げる**ことを目指したプラグインです。

種別ごとのワークフローで着手から完了まで1ステップずつ誘導し、MTG文字起こしやスクリーンショット
などの情報を取り込み、プロジェクトの知識を相互リンクされた知識ベースとして育てます。

## 特徴

- **横断タスク収集** — 複数ソースから自分担当のタスクを集約し、1つの一覧に正規化
- **タスク・ドシエ** — タスク単位の Markdown に文脈を蓄積。別セッションで読めば再開できる
- **ワークフロー誘導** — bugfix / feature / research / review / docs / ops の標準手順をチェックリストで提示
- **情報の取り込み** — ファイル/画像/文字起こし/貼り付けテキストを要約し、ドシエ・知識ベースへ振り分け
- **暗黙キャプチャ** — 明示的にコマンドを呼ばなくても作業しながら自動で貯まる（作業中の決定/調査/次アクションをドシエへ追記する常駐指示＋セッション終了時の生ログ退避のハイブリッド。自動書き込みの範囲は設定可能）
- **知識ベース（LLM-Wiki）** — `[[リンク]]` と型付き関連で知識をグラフ化。索引と健全性チェックは自動
- **決定論 × LLM の分離** — 索引マージ・lint・取り込み保存は Python スクリプトで再現可能に、判断は LLM スキルが担当
- **per-machine 設定** — どのソースを・どの範囲で取得するかをマシンごとの設定で切り替え
- **追加依存なし** — スクリプトは Python 3 標準ライブラリのみ

設計の詳細は [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) を参照してください。

## インストール

**前提**
- [GitHub CLI (`gh`)](https://cli.github.com/) が認証済みであること（`gh auth status` / 未ログインなら `gh auth login`）
- Python 3
- Claude Code

**開発用に読み込む**（クローンしたディレクトリを指定）:
```bash
claude --plugin-dir /path/to/hiyokb
```

**マーケットプレイス経由**（任意）:
```
/plugin marketplace add <this-repo>
/plugin install hiyokb
```

初回にスキルを実行すると `~/.hiyokb/` 一式（`config.yaml` / `index.md` / `projects/` / `inbox/` / `sources/` / `kb/`）が作成されます。

## 使い方

スキルは名前空間付きで呼び出します（自然言語でも文脈が合えば自動起動します）。

| コマンド | 役割 |
|---|---|
| `/hiyokb:task-sync` | 各ソースから収集し、横断 index を再生成 |
| `/hiyokb:task-list` | タスク横断一覧を表示（`--all` で完了済みも） |
| `/hiyokb:task-focus <id>` | タスクに着手/再開。ドシエ作成と手順誘導 |
| `/hiyokb:task-link` | 重複タスクを手動リンク（`same_as`） |
| `/hiyokb:task-archive` | 完了タスクのドシエをアーカイブ |
| `/hiyokb:ingest` | ファイル/画像/文字起こしを取り込み・要約・振り分け |
| `/hiyokb:kb` | 知識の追記・検索・昇格 |
| `/hiyokb:kb-lint` | 知識ベースの健全性チェック（`--fix` で安全な修復） |
| `/hiyokb:handoff` | 引き継ぎサマリをドシエに記録 |

典型的な流れ:
```
/hiyokb:task-sync          # タスクを集める
/hiyokb:task-list          # 一覧を見る
/hiyokb:task-focus <id>    # 着手して手順に沿って進める
/hiyokb:handoff            # 中断時に引き継ぎを記録
```

## 設定（per-machine / `~/.hiyokb/config.yaml`）

設定はマシンごとにローカル（git 除外）。**どのソースを・どの範囲で取得するか**を切り替えます。

| キー | 説明 | 例 |
|---|---|---|
| `enabled_sources` | 取得するソース。無効ソースは取得せず一覧にも出ない | `[github]` / `[github, slack, backlog]` |
| `sources.github.owners` | GitHub の参照範囲（owner で限定。空なら担当 issue 全部）。`scopes` 未指定時の後方互換 | `[your-org]` / `[your-account]` / `[]` |
| `sources.<src>.scopes` | 取得範囲を target 単位で指定（github=owner/repo・backlog=projectKey・slack=channel）。`<target> : <filter>` を1行1スコープ。下記参照 | 下記参照 |
| `identities` | 各ソースでの自分の識別子（Slack/Backlog 収集に必要） | `github: your-account` |
| `timezone` | 日付判定の基準 | `Asia/Tokyo` |
| `capture.enabled` | 暗黙キャプチャ全体の on/off（false で従来どおり明示呼び出しのみ） | `true` |
| `capture.inline_recording` | 作業中に決定/調査/次アクションをドシエへ追記する常駐指示を注入（経路A） | `true` |
| `capture.session_capture` | セッション終了時に会話ログを `inbox/sessions/` へ退避（経路B・非破壊） | `true` |
| `capture.auto_scope` | 自動書き込みの上限。`inbox`=生ログ退避のみ自動 / `dossier`=ドシエ追記まで自動（推奨） / `kb`=KB昇格まで自動 | `dossier` |

> 例えば「業務用 PC と個人用 PC で同じ GitHub アカウントを使うが見たい範囲は違う」場合、各マシンの
> `enabled_sources` と `owners` を変えるだけで分離できます（プラグイン側に区別ロジックは持ちません）。
>
> 暗黙キャプチャを完全に止めたいマシンでは `capture.enabled: false`、「勝手にドシエへ書くのは避けて生ログだけ残したい」なら `capture.auto_scope: inbox` にします。`capture:` ブロックが無い場合は暗黙キャプチャ有効・`auto_scope: dossier` が既定です。

**取得範囲を細かく変える（`scopes`）** — 業務系はアサインされたものだけ、個人系はアサインせず立てた
ものも拾う、を 1 設定で両立できます。**GitHub / Backlog / Slack で同じ `sources.<src>.scopes` 形式**
（`<target> : <filter>` を 1 行 1 スコープ。filter 省略時はソース既定）。各スコープを別クエリで取得し
id でマージします。GitHub では `scopes` が `owners` より優先されます。

```yaml
sources:
  github:                          # target = owner または owner/repo
    scopes:
      - your-org : assigned          # owner 全体 → 自分にアサインされた issue（業務系）
      - your-account/notes : created # 特定 repo → 自分が立てた issue 全部（未アサインも拾う）
      - your-account/sandbox : all   # その repo の open issue を全部
      - your-account/ideas           # filter 省略 → 既定 assigned
  backlog:                         # target = プロジェクトキー
    scopes:
      - APLUS : assigned             # そのプロジェクトで自分担当の未完課題
      - SANDBOX : all                # そのプロジェクトの未完課題を全部
  slack:                           # target = チャンネル
    scopes:
      - "#aplus-dev" : mentions      # 自分へのメンション/スレッド
      - "#aplus-ops" : all           # チャンネルのタスク候補を広めに
```

| source | target | filter |
|---|---|---|
| `github` | owner / owner-repo | `assigned`(既定) / `created`（自分が立てた・未アサインも） / `involves` / `all` |
| `backlog` | プロジェクトキー | `assigned`(既定) / `all` |
| `slack` | チャンネル | `mentions`(既定) / `all` |

> `scopes` 未設定のソースは従来どおり「自分宛/自分担当を横断収集」（後方互換）。個人プロジェクトで
> 「アサインせず issue を立てる」運用は、その repo/プロジェクトを `created` か `all` で追加すれば拾えます。

## ストア構成（`~/.hiyokb/`）

```
~/.hiyokb/
├── config.yaml                 # per-machine 設定（git 除外）
├── index.md                    # 全タスク横断ビュー（自動生成）
├── log.md                      # ingest/lint/archive の追記専用クロニクル
├── sources/<src>.md            # ソース取得スナップショット（ソース所有）
├── inbox/                      # 取り込んだ生ソース（不変）
│   └── sessions/                # セッション生ログの自動退避先（暗黙キャプチャ経路B）
├── projects/<名>/
│   ├── tasks/<id>.md            # タスク・ドシエ（ローカル所有の知識）
│   ├── archive/                 # 完了タスクの退避先
│   └── kb/                      # プロジェクト知識ベース
└── kb/                         # プロジェクト横断の知識ベース（+ SCHEMA.md）
```

機密を含みうる `config.yaml` / `inbox/` / `sources/` は `~/.hiyokb/.gitignore` で同期対象外にできます。

## プラグイン構成

```
.claude-plugin/   plugin.json（マニフェスト）/ marketplace.json（配布用）
skills/           ワークフロー本体（SKILL.md）
scripts/          決定論コア（Python 標準ライブラリのみ）
hooks/            SessionStart（状況提示＋暗黙キャプチャ指示）/ Stop（opt-in 自動コミット）/ SessionEnd（セッション生ログ退避）
templates/        ドシエ・KB記事・種別ワークフローの雛形
docs/             設計ドキュメント
```

## 開発・テスト

- スクリプトは追加依存なしで動きます: `python3 scripts/build_index.py` など単体実行可能。
- 決定論コア（index 再マージ・KB 索引・lint）は入出力が固定なので回帰テストに向きます。特に
  「ローカル注釈が再同期で消えない」ことが最重要の不変条件です。

## ライセンス

[MIT](LICENSE)
