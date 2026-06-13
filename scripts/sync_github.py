#!/usr/bin/env python3
"""GitHub から自分担当の open issue を取得し ~/.hiyokb/sources/github.md を更新する。

- 成功時: 取得結果でスナップショットを上書き（stale: false）。
- 失敗時（認証切れ/レート制限/オフライン）: 前回スナップショットを保持し stale: true を立てる
  （部分失敗のソース単位隔離）。他ソースや index 再生成を止めないため exit 0 で返す。
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _config  # noqa: E402

TASK_ROOT = os.path.expanduser("~/.hiyokb")
SRC_DIR = os.path.join(TASK_ROOT, "sources")
SRC_FILE = os.path.join(SRC_DIR, "github.md")
LIMIT = 200  # 取得上限。到達したら切り捨ての可能性を警告する


def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def read_existing_tasks():
    if not os.path.exists(SRC_FILE):
        return []
    try:
        txt = open(SRC_FILE, encoding="utf-8").read()
        m = re.search(r"```json\n(.*?)\n```", txt, re.S)
        if m:
            return json.loads(m.group(1)).get("tasks", [])
    except Exception:
        pass
    return []


def write_snapshot(tasks, stale, error=None):
    os.makedirs(SRC_DIR, exist_ok=True)
    data = {"source": "github", "synced": now_iso(), "stale": stale, "tasks": tasks}
    if error:
        data["error"] = error
    status = "STALE（前回値を表示中・取得失敗）" if stale else "ok"
    head = [
        "# github source snapshot",
        "",
        f"- synced: {data['synced']}",
        f"- status: {status}",
    ]
    if error:
        head.append(f"- error: {error}")
    head += [f"- count: {len(tasks)}", "", "```json",
             json.dumps(data, ensure_ascii=False, indent=2), "```", ""]
    open(SRC_FILE, "w", encoding="utf-8").write("\n".join(head))


def fetch():
    owners = _config.github_owners()          # 参照範囲（config。空なら @me 全部）
    cmd = ["gh", "search", "issues", "--assignee=@me", "--state=open",
           "--json", "number,title,url,repository,labels,updatedAt", "--limit", str(LIMIT)]
    for o in owners:                           # 指定 owner のみに絞る
        cmd.append(f"--owner={o}")
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "gh search failed")
    items = json.loads(out.stdout or "[]")
    if len(items) >= LIMIT:
        print(f"github: ⚠️ 取得が上限 {LIMIT} 件に達しました。切り捨ての可能性があります"
              f"（owner を config で絞るか、上限調整を検討）", file=sys.stderr)
    tasks = []
    for it in items:
        repo = (it.get("repository") or {}).get("nameWithOwner", "")
        num = it.get("number")
        tasks.append({
            "id": f"gh:{repo}#{num}",
            "source": "github",
            "source_ref": it.get("url", ""),
            "title": it.get("title", ""),
            "status": "todo",
            "due": None,
            "assignee": "me",
            "labels": [l.get("name") for l in (it.get("labels") or [])],
            "updated": (it.get("updatedAt") or "")[:10],
        })
    return tasks


def main():
    if "github" not in _config.enabled_sources():
        print("github: 無効（config の enabled_sources に含まれていません）")
        sys.exit(0)
    try:
        tasks = fetch()
        write_snapshot(tasks, stale=False)
        print(f"github: {len(tasks)} 件を同期しました")
    except Exception as e:
        existing = read_existing_tasks()
        write_snapshot(existing, stale=True, error=str(e))
        print(f"github: 同期失敗（{e}）。前回の {len(existing)} 件を stale として保持します",
              file=sys.stderr)
    # per-source isolation: 常に 0 で返し、他ソース/index 再マージを止めない
    sys.exit(0)


if __name__ == "__main__":
    main()
