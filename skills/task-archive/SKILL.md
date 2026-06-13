---
name: task-archive
description: 完了したタスクのドシエをアーカイブして横断一覧を整理する。「完了タスクを片付けて」「古いタスクをアーカイブ」「indexを整理」などのときに使う。
allowed-tools: Bash, Read
---

# task-archive — 完了タスクのアーカイブ

done のタスクで一定日数（config の `archive_after_days`、既定30）を過ぎたドシエを
`projects/<名>/archive/` に退避し、index を整理する。KB の知見・リンクは消さず移動のみ。

## 手順
1. まず影響を確認（dry-run）:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/task_archive.py" --dry-run
   ```
2. 問題なければ実行:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/task_archive.py"
   ```
   - 退避は `~/.hiyokb/log.md` に記録される。
   - 実行後 index は自動再生成される。

## 注意
- ファイルは**移動（削除しない）**。再オープン（ソースが open に戻る）すれば次の sync で active に戻る。
- 最新状態で判定したい場合は先に `/hiyokb:task-sync` を実行。
