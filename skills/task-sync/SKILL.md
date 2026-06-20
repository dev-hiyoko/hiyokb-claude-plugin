---
name: task-sync
description: 各ソース（GitHub / Slack / Backlog）から自分担当のタスクを取得し、~/.hiyokb/index.md を再生成して横断一覧を最新化する。「タスクを同期/更新」「今日のタスク（最新）を取ってきて」「割り当てられた issue を一覧」などのときに使う。
allowed-tools: Bash, Read
---

# task-sync — ソース横断のタスク収集と index 再マージ

`~/.hiyokb/config.yaml` の `enabled_sources` / `identities` / `sources` を読み、**`enabled_sources` に含まれるソースだけ**収集する（個人PCは `[github]`、会社PCは `[github, slack, backlog]` 等）。**ソースごとに独立**して実行し、1つ失敗しても他と index を止めない。最後に決定論マージで index を再生成する。

> `enabled_sources` に無いソースは取得もせず、index にも出さない（無効ソースの古いスナップショットは build_index が無視する）。

GitHub は `gh` CLI（スクリプトが直接取得）、Slack/Backlog は **MCP ツール経由**（このスキルが取得し、正規化して正準ライターに渡す）。

## 1. GitHub（gh CLI）

### 1-0. 初回だけ：見る範囲をユーザーに確認する
config に GitHub の範囲指定（`sources.github.owners` も `sources.github.scopes`）が**まだ無い**＝初回セットアップのときは、**黙って既定で進めず**、平易に質問する（既定のままだと「自分にアサインされた issue」しか拾わず、**組織(org)のリポジトリや、自分が立てただけ/未アサインの issue が漏れる**ため）:

1. **どこを見ますか？** 「個人のリポジトリだけ」か「会社・組織(org)の issue も見る」か。org も見るなら **org 名**を聞く（`gh org list` で候補を見せてもよい）。複数可。
2. **どの issue を拾いますか？** 「自分にアサインされたものだけ」／「自分が立てたものも」／「その範囲の issue 全部」。

聞いた答えを config に書く（owner 単位で行を足す。filter は `assigned` 既定 / `created` / `all`）:
```yaml
sources:
  github:
    scopes:
      - <your-account> : assigned     # 個人：自分にアサインされたもの
      - <your-org>     : assigned     # 組織：必要に応じて created / all
```
> 一度書けば次回からは聞かない。後で変えたいときは config を直すか、その都度頼めばよい旨を伝える。

### 1-1. 取得
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_github.py"
```
- 成功: `~/.hiyokb/sources/github.md` を上書き。失敗: 前回値を保持（古いデータのまま表示）。
- `gh auth status` が未ログインなら、その旨を伝え `gh auth login` を促す（こちらで認証はしない）。
- 範囲は `sources.github.scopes` で決まる（未設定時は `owners` を assigned で取得）。「**アサインせず立てた issue が出ない**」「**org のが出ない**」という相談には、その owner/repo を `scopes` に `created` か `all` で足すよう案内（例: `- your-org : all`）。

## 2. Slack（MCP）
`enabled_sources` に `slack` が無ければスキップ。`identities.slack` 未設定もスキップ（一言伝える）。両方OKなら:
0. **取得範囲（scopes）を読む** — チャンネル単位で指定できる（`sources.slack.scopes`、target = チャンネル、filter = `mentions`(既定) / `all`）:
   ```bash
   python3 -c "import sys;sys.path.insert(0,'${CLAUDE_PLUGIN_ROOT}/scripts');import _config,json;print(json.dumps(_config.source_scopes('slack'),ensure_ascii=False))"
   ```
   scopes があれば各チャンネルで filter に従う（`mentions`=自分へのメンション/スレッド / `all`=そのチャンネルのタスク候補を広めに）。空なら従来どおりワークスペース横断で自分宛を集める。
1. MCP の Slack 検索ツールで**自分宛のタスク候補**を収集する。現状の MCP は検索ベースなので、`sources.slack.signals`（例: 指定リアクション/ブックマーク）を厳密取得できない場合は、**自分へのメンション/DM を候補**として集める。
2. 候補はノイズを含むため、**タスクとみなすかをユーザーに確認**してから採用（雑談メンションを除外）。`done_emoji` が付くものは done 扱い。
3. 採用分を正規化してソースキャッシュへ:
   ```bash
   echo '[{"id":"slack:<channel>-<ts>","source":"slack","source_ref":"<permalink>","title":"<要約>","status":"todo"}]' \
     | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/write_source.py" slack
   ```
4. Slack MCP が未接続/失敗なら、stale を記録して**他を止めない**:
   ```bash
   echo '{"stale":true,"error":"slack mcp unavailable"}' | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/write_source.py" slack
   ```

## 3. Backlog（MCP）
`enabled_sources` に `backlog` が無ければスキップ。`identities.backlog` 未設定もスキップ。両方OKなら:
1. **接続確認**: Backlog MCP が認証済みか確認。未認証なら `authenticate` ツールでの認証をユーザーに促し、このソースはスキップ（stale 記録）。
2. **取得範囲（scopes）を読む** — GitHub と同じくプロジェクト単位で取得範囲を指定できる（`sources.backlog.scopes`、target = Backlog の projectKey、filter = `assigned`(既定) / `all`）:
   ```bash
   python3 -c "import sys;sys.path.insert(0,'${CLAUDE_PLUGIN_ROOT}/scripts');import _config,json;print(json.dumps(_config.source_scopes('backlog'),ensure_ascii=False))"
   ```
   - **scopes が設定されていれば**、各 projectKey ごとに取得し、filter に従う: `assigned`=その プロジェクトで**自分担当**の未完課題 / `all`=そのプロジェクトの未完課題**全部**（アサイン不問。個人運用の拾い漏れ対策）。
   - **scopes が空なら**従来どおり、自分担当で「完了」以外の課題を全プロジェクト横断で取得。
3. ステータスを正規化（未対応→todo / 処理中→in_progress / 処理済み→review / 完了→done / `blocked`相当→blocked）。
   ```bash
   echo '[{"id":"bl:<issueKey>","source":"backlog","source_ref":"<url>","title":"<件名>","status":"in_progress","due":"<YYYY-MM-DD>"}]' \
     | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/write_source.py" backlog
   ```
4. 失敗時は stale 記録（Slack と同様）。

## 4. index 再マージ（決定論）
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_index.py"
```
ソース由来とローカル注釈（ドシエ frontmatter）を所有権ルールでマージ。ローカル注釈は保持される。

## 5. 報告と「次の一手」
まず結果を一言で（ソース別の同期件数、`⚠️ 古いデータのまま`のソースがあればその旨）。

そのうえで**「次に何をすればいいか」を、迷わない順で 1〜2 個だけ**示す（設定の話は最後に、必要な人だけ向けに）:
1. **まず一覧を見る** → `/hiyokb:task-list`（今いるリポジトリのプロジェクトのタスクだけ表示。「全部見たい」なら全プロジェクト横断）
2. **取りかかるタスクを決めて着手** → `/hiyokb:task-focus <タスクID>`（手順に沿って1ステップずつ進む。作業メモは自動でそのタスクに貯まる）

（任意・必要になったら）同じ案件が複数ソースにある／取得範囲を変えたいときだけ:
- 複数ソースの重複をまとめる → `/hiyokb:task-link`
- Slack/Backlog も集めたい・GitHub の取得範囲を変えたい → README の「設定」を案内（**普段は触らなくてよい**）

用語は避けて平易に伝える（「config の enabled_sources に…」のような設定用語を最初から並べない）。

## 注意
- index.md は**自動生成物**。手で編集しない（真実はソースキャッシュとドシエ frontmatter）。
- MCP ツールはセッションに接続済みである必要がある（claude.ai 連携）。未接続のソースは stale でスキップし、他を止めない。
