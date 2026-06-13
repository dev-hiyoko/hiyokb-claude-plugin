#!/usr/bin/env python3
"""完了タスクのドシエをアーカイブする（決定論的）。

merged status が done で、一定日数（config の archive_after_days、既定30）経過した
ドシエを projects/<名>/archive/ に退避する。KB の知見・リンクは消さない（移動のみ）。
再オープン（ソースが open に戻る）すれば次の sync で active に戻る。

使い方: task_archive.py [--dry-run]
"""
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_index as bi  # noqa: E402

TASK_ROOT = bi.TASK_ROOT
CONFIG = os.path.join(TASK_ROOT, "config.yaml")
LOG = os.path.join(TASK_ROOT, "log.md")


def archive_after_days():
    try:
        m = re.search(r"archive_after_days\s*:\s*(\d+)", open(CONFIG, encoding="utf-8").read())
        return int(m.group(1)) if m else 30
    except Exception:
        return 30


def dossier_age_days(path, fm):
    upd = fm.get("updated")
    try:
        if upd:
            d = datetime.strptime(str(upd)[:10], "%Y-%m-%d").date()
        else:
            d = date.fromtimestamp(os.path.getmtime(path))
    except Exception:
        d = date.fromtimestamp(os.path.getmtime(path))
    return (date.today() - d).days


def append_log(line):
    new = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8") as f:
        if new:
            f.write("# log — ingest/query/lint の追記専用クロニクル\n\n")
        f.write(line + "\n")


def main():
    dry = "--dry-run" in sys.argv
    n_days = archive_after_days()
    src_tasks, src_meta = bi.load_sources()
    loc = bi.load_dossiers()
    rows = bi.merge(src_tasks, src_meta, loc)

    done = [r for r in rows if r["status"] == "done" and r["dossier"]]
    archived = 0
    today = date.today().isoformat()
    for r in done:
        path = os.path.join(TASK_ROOT, r["dossier"])
        if not os.path.isfile(path):
            continue
        fm = loc.get(r["id"], {})
        age = dossier_age_days(path, fm)
        if age < n_days:
            continue
        # projects/<名>/archive/ へ
        tasks_dir = os.path.dirname(path)           # projects/<名>/tasks
        proj_dir = os.path.dirname(tasks_dir)       # projects/<名>
        archive_dir = os.path.join(proj_dir, "archive")
        if dry:
            print(f"[dry-run] {r['id']} ({age}日経過) → {os.path.relpath(archive_dir, TASK_ROOT)}/")
            archived += 1
            continue
        os.makedirs(archive_dir, exist_ok=True)
        dest = os.path.join(archive_dir, os.path.basename(path))
        shutil.move(path, dest)
        append_log(f"- [{today}] archive: {r['id']} → {os.path.relpath(dest, TASK_ROOT)}")
        archived += 1

    if archived and not dry:
        # index 再生成（done は既定で非表示。ドシエパスの更新を反映）
        subprocess.run([sys.executable, os.path.join(HERE, "build_index.py")])
    print(f"アーカイブ対象: {archived} 件（{n_days}日超の done）" + ("（dry-run）" if dry else ""))


if __name__ == "__main__":
    main()
