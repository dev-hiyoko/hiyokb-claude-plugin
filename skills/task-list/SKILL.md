---
name: task-list
description: 蓄積済みのタスク一覧を表示する。既定は「今いるリポジトリ＝プロジェクト」のタスクだけ。「タスク一覧」「今のタスク見せて」「やることリスト」などのときに使う。「全プロジェクト」「全部」と言われたら横断表示、「完了も」で done も含める。
allowed-tools: Bash, Read
---

# task-list — タスク（現プロジェクト既定）の一覧表示

`$ARGUMENTS` / 文脈の解釈: 「全プロジェクト・全部」=横断表示 / 「完了も・done も」=完了済みも含む。
（`build_index.py` のフラグ: `--project <名>`=絞り込み、`--all`=done 込み、`--stdout`=表示専用）

## 手順
1. **現プロジェクトを判定**（既定はこのリポジトリのタスクだけ表示）:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/project_bind.py" --whoami
   ```
2. **絞り込んで表示**:
   - **project が出た（既定）**: そのプロジェクトのみ:
     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_index.py" --stdout --project <project>
     ```
   - **「全プロジェクト」要求**: `--project` を付けずに横断表示:
     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_index.py" --stdout
     ```
   - **未束縛（repo はあるが project なし）**: その旨を伝え「どのプロジェクト？」を確認 → `project_bind.py github <repo> <project>` で記憶してから絞り込む。確認できるまでは横断表示にフォールバックし、未束縛である旨を明示。
   - **repo 無し（git 外）**: 横断表示。
   - 「完了も」のときは上記コマンドに `--all` を追加。
   - index が古い/空なら `/hiyokb:task-sync` を提案（勝手に同期しない。「最新で」と言われたら実行）。

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
