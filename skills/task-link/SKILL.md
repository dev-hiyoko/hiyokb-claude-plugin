---
name: task-link
description: 同一案件が複数ソースに重複しているタスクを手動でリンクし、横断一覧で1グループに畳む。「このタスクとあのタスクは同じ」「重複をまとめて」「gh#123 と slack-xxx を紐付け」などのときに使う。
allowed-tools: Read, Edit, Write, Bash, Glob
---

# task-link — 重複タスクの手動リンク（same_as）

複数ソースに流れた同一案件（例: GitHub Issue の議論が Slack にもある）を `relates_to: same_as` で結び、index で1行に畳む。

## 手順
1. リンクする2つ以上のタスクID（`$ARGUMENTS`）を確認。**代表（primary）**を決める（ドシエがある方／開発の実体がある方を推奨）。
2. 代表のドシエ（`~/.hiyokb/projects/<名>/tasks/<id>.md`）を特定。無ければ `${CLAUDE_PLUGIN_ROOT}/templates/dossier.md` を雛形に作成（frontmatter の id/source/project を埋める）。
3. 代表ドシエの frontmatter `relates_to` に同件を追記（**ローカル所有・sync で消えない**）:
   ```yaml
   relates_to: [{id: "slack-1718", rel: same_as}]
   ```
   複数なら配列に足す。`rel` は `same_as`（重複）。関連だが別物なら `relates_to`（畳まない）。
4. index を再マージして畳み込みを反映:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_index.py"
   ```
5. 結果を報告（代表行が `id (+other...)` で畳まれていることを確認）。

## 注意
- 畳み込みは index 表示上のグループ化。元タスクは各ソースに残る（破壊しない）。
- 解除はドシエの `relates_to` から該当エントリを削除して再マージ。
- 別物だが関連、程度なら `rel: relates_to` を使い畳まない（誤って統合しない）。
