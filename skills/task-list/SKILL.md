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

## 参照元 ↔ タスクの紐づき状況（毎回あわせて提示）
一覧と一緒に、各タスクが「ソースのみ／ドシエあり／複数ソースをリンク済」のどれか、未リンクの重複候補、リンクの健全性を出す:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/link_audit.py"
```
- **紐づき状況**: 🔗複数ソースをリンク済 / 📄ドシエあり / ⊘ソースのみ（未着手）。そのまま提示する。
- **紐づけ候補（要確認）**: exact 同名でソースをまたぐ未リンク組を決定論で検出したもの。**さらに**、一覧のタイトル/URLを見て「Backlog の課題と GitHub issue が同じ案件」のような**ゆるい候補**にも気づいたら補足提案してよい（あいまいな判断はここで）。
- 候補が出たら **ユーザーに「これらは同一案件ですか？」と確認**し、**合っていると言われたら** `/hiyokb:task-link <id> <id> ...` を実行してリンクを確定（勝手に結ばない）。違うと言われた組は結ばない。
- **リンク健全性**: `relates_to` の参照先が現存しない（迷子）警告。typo か、別owner非取得か、解決済みかをユーザーと確認し、必要なら該当ドシエの `relates_to` を修正/削除。

## 表示の補助
- 「今日やるべき」「優先度高」など聞かれたら、status（in_progress > blocked > review > todo）と due で絞って提示。
- `⚠️` は stale（前回値）、`🔒` は sensitive。これらは注記する。
- 着手したいと言われたら `/hiyokb:task-focus <id>` に繋ぐ。
