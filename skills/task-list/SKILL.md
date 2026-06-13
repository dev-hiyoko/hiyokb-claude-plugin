---
name: task-list
description: 蓄積済みのタスク横断一覧（~/.hiyokb/index.md）を表示する。「タスク一覧」「今のタスク見せて」「やることリスト」などのときに使う。完了済みも含めるときは --all。最新の取得が必要なら task-sync を先に促す。
allowed-tools: Bash, Read
---

# task-list — タスク横断一覧の表示

`$ARGUMENTS` に `--all` が含まれれば完了済みも表示。

## 手順
- **通常（active のみ）**: `~/.hiyokb/index.md` を Read してそのまま提示。
  - ファイルが古い/空の可能性があれば、`/hiyokb:task-sync` での同期を提案（こちらで勝手に同期はしない。ただしユーザーが「最新で」と言えば task-sync を実行）。
- **`--all`（完了済みも含む）**: 上書きせず標準出力に全件を生成して提示:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_index.py" --all --stdout
  ```

## 表示の補助
- 「今日やるべき」「優先度高」など聞かれたら、status（in_progress > blocked > review > todo）と due で絞って提示。
- `⚠️` は stale（前回値）、`🔒` は sensitive。これらは注記する。
- 着手したいと言われたら `/hiyokb:task-focus <id>` に繋ぐ。
