#!/usr/bin/env python3
"""MCP 等から取得したタスク一覧を、正準フォーマットで ~/.task/sources/<source>.md に書く。

GitHub は gh CLI でスクリプトが直接取得できるが、Slack/Backlog 等は MCP ツール経由
（セッション内で Claude が呼ぶ）。スキルが正規化した結果をこのスクリプトに渡すことで、
スナップショットの形式を一定に保ち、build_index.py がそのまま読めるようにする。

使い方:
  write_source.py <source>          # stdin に正規化済みタスクの JSON
    stdin: [ {task}, ... ]  または  {"tasks":[...], "stale":false, "error":null}
  失敗を記録する場合: {"stale": true, "error": "..."} を渡すと、tasks 省略時は前回値を保持。

正規化タスクの想定キー: id(必須) / source / source_ref / title / status / due / assignee / labels / updated
"""
import json
import os
import re
import sys
from datetime import datetime

TASK_ROOT = os.path.expanduser("~/.task")
SRC_DIR = os.path.join(TASK_ROOT, "sources")


def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def read_existing(path):
    if not os.path.exists(path):
        return []
    try:
        m = re.search(r"```json\n(.*?)\n```", open(path, encoding="utf-8").read(), re.S)
        if m:
            return json.loads(m.group(1)).get("tasks", [])
    except Exception:
        pass
    return []


def normalize(t, source):
    return {
        "id": t["id"],
        "source": t.get("source", source),
        "source_ref": t.get("source_ref", ""),
        "title": t.get("title", ""),
        "status": t.get("status", "todo"),
        "due": t.get("due"),
        "assignee": t.get("assignee", "me"),
        "labels": t.get("labels", []),
        "updated": (t.get("updated") or "")[:10],
    }


def main():
    if len(sys.argv) < 2:
        print("usage: write_source.py <source>  (stdin: JSON tasks)", file=sys.stderr)
        sys.exit(2)
    source = sys.argv[1]
    os.makedirs(SRC_DIR, exist_ok=True)
    path = os.path.join(SRC_DIR, f"{source}.md")

    raw = sys.stdin.read().strip() or "[]"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"invalid JSON: {e}", file=sys.stderr)
        sys.exit(2)

    stale, error = False, None
    if isinstance(payload, dict):
        stale = bool(payload.get("stale"))
        error = payload.get("error")
        items = payload.get("tasks")
        if items is None:
            items = read_existing(path) if stale else []
    else:
        items = payload

    tasks = []
    for t in items:
        if t.get("id"):
            tasks.append(normalize(t, source))

    data = {"source": source, "synced": now_iso(), "stale": stale, "tasks": tasks}
    if error:
        data["error"] = error
    head = [f"# {source} source snapshot", "",
            f"- synced: {data['synced']}",
            f"- status: {'STALE（前回値・取得失敗）' if stale else 'ok'}"]
    if error:
        head.append(f"- error: {error}")
    head += [f"- count: {len(tasks)}", "", "```json",
             json.dumps(data, ensure_ascii=False, indent=2), "```", ""]
    open(path, "w", encoding="utf-8").write("\n".join(head))
    print(f"{source}: {len(tasks)} 件を書き込み{'（stale）' if stale else ''}")


if __name__ == "__main__":
    main()
