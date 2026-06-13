#!/usr/bin/env python3
"""SessionStart で実行し、タスク状況を簡潔に提示する（読み取りのみ・ネットワーク無し）。

出力はセッションのコンテキストに注入されるため短く保つ。
"""
import glob
import os
import subprocess

TASK_ROOT = os.path.expanduser("~/.task")
INDEX = os.path.join(TASK_ROOT, "index.md")


def index_rows():
    if not os.path.exists(INDEX):
        return [], None
    rows, stale_line = [], None
    in_table = False
    for line in open(INDEX, encoding="utf-8"):
        if line.startswith("**ソース同期状況**"):
            stale_line = line.strip()
        if line.startswith("|----"):
            in_table = True
            continue
        if in_table and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 6:
                rows.append(cells)  # id,title,source,status,priority,due,...
    return rows, stale_line


def kb_page_count():
    n = 0
    for d in [os.path.join(TASK_ROOT, "kb")] + glob.glob(os.path.join(TASK_ROOT, "projects", "*", "kb")):
        for p in glob.glob(os.path.join(d, "*.md")):
            if os.path.basename(p) not in ("index.md", "SCHEMA.md"):
                n += 1
    return n


def git_note():
    if not os.path.isdir(os.path.join(TASK_ROOT, ".git")):
        return None
    try:
        out = subprocess.run(["git", "-C", TASK_ROOT, "status", "--porcelain"],
                             capture_output=True, text=True, timeout=5)
        n = len([x for x in out.stdout.splitlines() if x.strip()])
        return f"未コミットの変更 {n} 件" if n else None
    except Exception:
        return None


def main():
    if not os.path.isdir(TASK_ROOT):
        return
    rows, stale_line = index_rows()
    if not rows and not os.path.exists(INDEX):
        return
    print("## hiyokb の状況")
    print(f"- アクティブなタスク: {len(rows)} 件")
    for r in rows[:6]:
        tid, title, _src, status = r[0], r[1], r[2], r[3]
        due = r[5] if len(r) > 5 else ""
        print(f"  - [{status}] {tid}: {title}" + (f"（期限 {due}）" if due else ""))
    if len(rows) > 6:
        print(f"  - …他 {len(rows) - 6} 件（`/hiyokb:task-list`）")
    if stale_line and "STALE" in stale_line:
        print(f"- ⚠️ 一部ソースは前回値（`/hiyokb:task-sync` で更新）")
    kb = kb_page_count()
    if kb:
        print(f"- 知識ベース: {kb} ページ（`/hiyokb:kb`）")
    g = git_note()
    if g:
        print(f"- {g}")


if __name__ == "__main__":
    main()
