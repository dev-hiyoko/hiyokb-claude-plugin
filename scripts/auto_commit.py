#!/usr/bin/env python3
"""Stop フックで実行。config の sync.auto_commit が true のときだけ ~/.task をコミットする。

既定は false（何もしない＝隠れた自動コミットをしない事故防止）。push はしない（手動）。
"""
import os
import re
import subprocess
from datetime import datetime

TASK_ROOT = os.path.expanduser("~/.task")
CONFIG = os.path.join(TASK_ROOT, "config.yaml")


def auto_commit_enabled():
    if not os.path.exists(CONFIG):
        return False
    txt = open(CONFIG, encoding="utf-8").read()
    m = re.search(r"auto_commit\s*:\s*(\w+)", txt)
    return bool(m and m.group(1).lower() == "true")


def main():
    if not auto_commit_enabled():
        return
    if not os.path.isdir(os.path.join(TASK_ROOT, ".git")):
        return
    status = subprocess.run(["git", "-C", TASK_ROOT, "status", "--porcelain"],
                            capture_output=True, text=True)
    if not status.stdout.strip():
        return
    subprocess.run(["git", "-C", TASK_ROOT, "add", "-A"], capture_output=True)
    msg = f"hiyokb auto-commit {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    subprocess.run(["git", "-C", TASK_ROOT, "commit", "-m", msg], capture_output=True)
    print(f"hiyokb: ~/.task を自動コミットしました（{msg}）")


if __name__ == "__main__":
    main()
