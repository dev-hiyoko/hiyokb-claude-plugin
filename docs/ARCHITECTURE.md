# hiyokb 設計ドキュメント

hiyokb は Claude Code 用のプラグインで、複数ソースに散らばったタスクを横断的に把握し、
タスクごとの知識（実装方針・調査・決定事項・進捗）を蓄積して**別セッションでも引き継げる**
ことを目的とする。本書はその設計思想とアーキテクチャを述べる。

## 1. 設計思想（原則）

1. **ツール非依存（正規化レイヤ）** — GitHub / Slack / Backlog 等はあくまで「ソース」の一実装。
   各ソースの取得結果を共通スキーマに正規化し、横断ビューを導出する。ソース追加＝Provider 追加。
2. **決定論（スクリプト）と LLM（スキル）の分離** — 索引のマージ・健全性チェック・取り込みの
   保存などは Python スクリプトで**決定論的・再現可能・テスト可能**に行う。要約・分類・昇格判断・
   引き継ぎなど判断が要る部分だけ LLM（スキル）が担う。
3. **ローカルの Markdown が主役** — 知識ストアは `~/.hiyokb` 配下の Markdown ファイル群。
   git/クラウドで同期でき、diff でレビューでき、Claude Code が直接読み書きできる。
   ベクタ DB/RAG は採らない（数百ページ規模まではコンテキスト方式が有利）。
4. **隠れた破壊的操作をしない** — 外部書き戻し・自動コミット・アーカイブ等は既定オフ/明示確認、
   かつ可逆（削除でなく移動）。原本は不変。

## 2. 全体構成

```
hiyokb (plugin)
├── skills/         … ワークフロー本体（LLM。スラッシュコマンド /hiyokb:<name>）
├── scripts/        … 決定論コア（Python 標準ライブラリのみ）
├── hooks/          … SessionStart（状況提示＋暗黙キャプチャ指示）/ Stop（opt-in 自動コミット）/ SessionEnd（生ログ退避）
└── templates/      … ドシエ・KB記事・種別ワークフローの雛形

~/.hiyokb (知識ストア・実行時に生成。プラグイン本体とは別)
├── config.yaml     … per-machine 設定（参照範囲・有効ソース・名寄せ）
├── index.md        … 全タスク横断ビュー（導出・自動生成）
├── log.md          … ingest/lint/archive の追記専用クロニクル
├── sources/<src>.md… ソース取得スナップショット（ソース所有）
├── inbox/          … 取り込んだ生ソース（不変）
│   └── sessions/    … セッション生ログの自動退避（暗黙キャプチャ経路B）
├── projects/<名>/
│   ├── tasks/<id>.md  … タスク・ドシエ（ローカル所有の知識）
│   ├── archive/       … 完了タスクの退避先
│   └── kb/            … プロジェクト知識ベース
└── kb/             … プロジェクト横断の知識ベース（+ SCHEMA.md）
```

## 3. データモデル — 3ファイル分離と所有権

横断一覧 `index.md` を機械的に再生成しても、ローカルで育てた注釈（プロジェクト割当・優先度・
ドシエへのパス・関連リンク等）が消えないように、**状態の所有者でファイルを分離**する。

| ファイル | 所有 | 内容 | 更新 |
|---|---|---|---|
| `sources/<src>.md` | ソース | title / status / due / labels / source_ref | 同期で上書き（失敗時は前回値保持） |
| `projects/<名>/tasks/<id>.md`（frontmatter） | ローカル | project / priority / type / relates_to / sensitive | 人・Claude が編集。同期では触らない |
| `index.md` | 導出 | 上2つを task id でマージした横断ビュー | 決定論的に再マージ（手編集しない） |

**マージ規則（所有権テーブル）**

| フィールド | 所有 | 同期時 |
|---|---|---|
| title / status / due / labels / source_ref | ソース | 上書き |
| priority / type / project / dossier / relates_to / sensitive | ローカル | 保持 |
| status の精緻化 | — | ソースが closed → done。open のときはローカルの in_progress/blocked/review を尊重 |

マージキーは **task id**（例 `gh:owner/repo#123`）。ソースを別ファイルにしたことで、
あるソースが取得失敗しても前回スナップショットを保持して index を壊さない（ソース単位の隔離）。
同一案件が複数ソースに重複する場合は `relates_to: same_as` で結び、index 上で1グループに畳む。
自動マッチングはしない（誤統合を避け、人が確信したものだけ結ぶ）。`task-list` は `link_audit.py`
（決定論）を併せて実行し、**紐づき状況**（ソースのみ / ドシエあり / 複数ソースをリンク済）と、
**未リンクの同名クロスソース候補**、`relates_to` の**迷子リンク**を提示する。候補の確定は
ユーザー確認のうえ `task-link`（`relates_to` 追記）で行う。`assigned`/`all` のような取得 filter とは
独立した、所有権を持つローカルの結節点（ドシエ）に紐づけを記録するため、再同期で消えない。

同期方向は当面「読み取り（収集）中心」。外部への書き戻しは破壊的なので段階導入・実行前確認とする。

## 4. 知識ベース — LLM-Wiki 三層

知識の蓄積は「LLM が読み書きする Markdown ライブラリ」（LLM-Wiki パターン）に倣う。

- **第1層 生ソース（不変）** — `inbox/` の原本。読むだけ・書き換えない・唯一の出所。
- **第2層 Wiki（LLM が育てる）** — `kb/` のページ。1ファイル1トピック。
- **第3層 Schema（規約）** — `kb/SCHEMA.md`。構造・命名・手順の規約。

**結びつきが中核**: ページは `[[トピック]]` で相互リンクし、関係に型を付ける
（`relates_to: depends_on/extends/supersedes/contradicts/...`）。孤立ページを作らない。

- **索引** `kb/index.md` は frontmatter の要約から**決定論的に再生成**（手編集しない）。
- **健全性チェック** は孤立・リンク切れ・片方向・出自欠落を検出。安全な修復（索引再生成・
  片方向→相互リンク化）のみ自動で行い、リンク切れの張り直しや矛盾解消は人が判断する。

## 5. 情報の取り込み（ingest）

ファイル/画像/文字起こし/貼り付けテキストを取り込み、要約・決定事項・TODO を抽出する。

- 原本は `inbox/` に**不変保存**。内容ハッシュで**冪等化**（同じ素材を二重取り込みしない）。
- **昇格ゲート** — 出所が明確で確定した情報だけを KB/ドシエへ昇格。未確定は inbox/draft に留める。
- **機密** — `sensitive: true` の素材は外部送信を伴う処理を避け、同期対象からも外す。

## 6. 設定（per-machine）

`~/.hiyokb/config.yaml` はマシンごとにローカル（git 除外）。**どのソースを・どの範囲で取得するか**
を設定で切り替える。プラグイン側に「個人/業務」のような区別ロジックは持たない。

- `enabled_sources` — 取得するソース（無効ソースは取得もせず index にも出ない）。
- `sources.github.owners` — GitHub の参照範囲（owner で限定。空なら担当 issue 全部）。`scopes` 未指定時の後方互換。
- `sources.<src>.scopes` — 取得範囲を target 単位で指定する**ソース横断の共通機構**（`_config.source_scopes`）。
  各スコープは `<target> : <filter>`（filter 省略時はソース既定）で、スコープごとに別クエリを投げて
  id でマージする。target/filter の意味はソース依存:
  - **github**: target = owner / owner/repo、filter = `assigned`(既定)/`created`/`involves`/`all`。`scopes` は
    `owners` に優先。マージ時 `assigned` を最優先。
  - **backlog**: target = プロジェクトキー、filter = `assigned`(既定)/`all`。
  - **slack**: target = チャンネル、filter = `mentions`(既定)/`all`。
  これにより「業務系は自分アサインのみ・個人系はアサインせず立てたものも拾う」を1設定で両立できる
  （アサインを前提にしない個人プロジェクトへの対応）。未設定ソースは従来どおり横断収集（後方互換）。
- `project_map` — リポジトリ等のソース対象を hiyokb プロジェクトに割り当てる（§6.5）。
- `identities` — 各ソースでの自分の識別子。

## 6.5 プロジェクト境界（cwd＝リポジトリ → プロジェクト）

1つのプロジェクトが複数リポジトリ・Backlog・Slack にまたがる。hiyokb は「**今いるリポジトリが
どのプロジェクトか**」を解決し、**表示・暗黙キャプチャ・KB の宛先を現プロジェクトに限定**する
（別プロジェクトの混入を防ぐ）。一方、**収集（sync）は全体**のまま行い、振り分けで絞る。

- **解決**: SessionStart 等で cwd の `git remote(origin)` → `owner/repo` → `project_map` で project を決定
  （`_config.current_project`）。タスク id からの振り分けは `_config.route_task`（`gh:owner/repo#n` →
  repo 一致 → owner 一致、`bl:KEY-n` → projectKey、`slack:ch-ts` → channel）。
- **割り当ては「聞いて記憶」**: プロジェクト未設定のリポジトリでは SessionStart が「どのプロジェクト？」の確認を促し、
  答えを `project_bind.py`（`_config.add_binding` で `project_map` に追記）で保存。これは hiyokb 唯一の
  config 書き込み。決まるまで自動記録の宛先を決めない（生ログは inbox に保存され続ける）。
- **所有権**: タスクの project は「ドシエ frontmatter の project が最優先、無ければ `project_map` で id から
  導出」。`build_index` は全件の index.md を生成しつつ `--project <名>` で現プロジェクトのみ表示できる。
- **KB の置き場所**: 既定で `projects/<project>/kb`。複数プロジェクトに効く横断汎用な知識だけ global `kb/`。

## 7. タスクのライフサイクル

1. **収集** — `sync` で各ソースから取得 → スナップショット更新 → index 再マージ。
2. **着手・誘導** — `focus` でドシエを作成/再開し、種別（bugfix/feature/research/review/docs/ops）の
   標準手順をチェックリストで展開、次アクションを1つずつ提示。
3. **引き継ぎ** — 進捗・決定・次アクションをドシエに記録。別セッションはドシエを読めば再開できる。
4. **アーカイブ** — 完了から一定日数経過したドシエを `archive/` へ退避（移動・非破壊）。

## 8. 暗黙キャプチャ（明示呼び出しに依存しない自動蓄積）

スキルを明示的に呼ばないと何も貯まらない、という運用上のギャップを埋める。**明示呼び出しを置き換える
のではなく補完する**。経路は2つで、どちらも追記専用・非破壊なので原則 #4（隠れた破壊的操作をしない）
と両立する。

- **経路A: LLM 駆動の inline 記録** — `SessionStart`（`session_context.py`）が、状況提示に続けて
  **常駐指示**を context に注入する：「作業中に決定/調査/次アクションが定まったら、その都度ドシエの
  該当セクションへ追記せよ」。宛先は**最後に更新された未完ドシエ**（in_progress/blocked/review を
  `updated` で最新優先）を自動推定して指示に埋める。要約済みの綺麗な知識がそのまま貯まるが、モデルが
  忘れると取りこぼす。
- **経路B: 決定論的な生ログ退避** — `SessionEnd`（`session_capture.py`）が transcript からユーザー
  発話とアシスタント本文だけを抽出し、`inbox/sessions/<日付>_<id>.md` に**冪等・非破壊**で退避する
  （ツール詳細は落として可読化）。モデルの記憶に依存せず確実に残る。生ログなので、後で `/hiyokb:ingest`
  でドシエ/KB へ蒸留する。

両経路を併用する（ハイブリッド）ことで、モデルが書き忘れても hook 側が拾う保険になる。

**自動書き込みの範囲は設定で選ぶ** — `config.yaml` の `capture.auto_scope`：

| 値 | 自動で書く先 | 人の確認が要る先 |
|---|---|---|
| `inbox` | `inbox/`（生ログ退避のみ） | ドシエ・KB すべて |
| `dossier`（既定・推奨） | `inbox/` ＋ アクティブドシエへの追記 | KB 昇格 |
| `kb` | inbox ＋ ドシエ ＋ KB 昇格 | なし |

`capture.enabled: false` で全停止（従来どおり明示呼び出しのみ）。`inline_recording` / `session_capture`
で経路ごとに個別 on/off できる。`capture:` ブロックが無い既定は「有効・`auto_scope: dossier`」。
生ログ（`inbox/`）は機密を含みうるため `~/.hiyokb/.gitignore` で同期対象外。

## 9. 拡張性

- **ソース追加** — 取得結果を正規化スキーマに変換し、共通ライターでスナップショットを書けば、
  index 再マージ（source-agnostic）にそのまま合流する。
- **配布** — `.claude-plugin/marketplace.json` により `/plugin marketplace add` で配布可能。

## 10. 前提・制約

- `gh` CLI が認証済みであること（GitHub ソース）。
- Slack/Backlog は Claude Code の MCP 連携が接続済みであること（スキルが MCP 経由で取得）。
- スクリプトは Python 3 標準ライブラリのみ（追加依存なし）。
- 知識ストアの規模が大きく育った場合に限り、将来的に検索手段の見直し（RAG 等）を検討する。
