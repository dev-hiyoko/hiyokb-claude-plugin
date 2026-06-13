#!/usr/bin/env python3
"""SessionStart で実行し、タスク状況を簡潔に提示する（読み取りのみ・ネットワーク無し）。

出力はセッションのコンテキストに注入されるため短く保つ。
"""
import glob
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import capture_config  # noqa: E402

TASK_ROOT = os.path.expanduser("~/.hiyokb")
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


def _read_frontmatter(path):
    fm = {}
    try:
        txt = open(path, encoding="utf-8").read()
    except Exception:
        return fm
    m = re.match(r"^---\n(.*?)\n---", txt, re.S)
    if not m:
        return fm
    for line in m.group(1).splitlines():
        mm = re.match(r"\s*([A-Za-z_]+)\s*:\s*(.*)", line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip()
    return fm


def active_dossier():
    """最後に更新された未完ドシエ（in_progress/blocked/review）を推定し返す。"""
    cands = []
    for p in glob.glob(os.path.join(TASK_ROOT, "projects", "*", "tasks", "*.md")):
        fm = _read_frontmatter(p)
        if fm.get("status") in ("in_progress", "blocked", "review"):
            cands.append((fm.get("updated", ""), p, fm))
    if not cands:
        return None
    cands.sort(reverse=True)
    _, path, fm = cands[0]
    return {"rel": os.path.relpath(path, TASK_ROOT), "title": fm.get("title", ""),
            "id": fm.get("id", ""), "project": fm.get("project", ""),
            "status": fm.get("status", "")}


def print_capture_instruction(cfg):
    """暗黙キャプチャの常駐指示を context に注入する（経路A: LLM 駆動の inline 記録）。"""
    scope = cfg["auto_scope"]
    print()
    print("## hiyokb: 暗黙キャプチャ（明示的に頼まれなくても自動で記録する）")
    print("作業しながら知識を貯める。タスクに取り組む中で **決定事項・調査結果・次アクション** が"
          "定まったら、その都度ドシエの該当セクション（決定事項 / 調査メモ / 次アクション / 進捗ログ）に"
          "**追記**する（追記のみ・既存行は消さない・出典を残す）。")
    act = active_dossier()
    if act:
        label = f"{act['id']} {act['title']}".strip() or act["rel"]
        print(f"- アクティブなドシエ: {label} → `{act['rel']}`（[{act['status']}]）")
        print("  別タスクの話なら該当ドシエへ。該当ドシエが無ければ作成してから記録する。")
    else:
        print("- 未完のドシエは未検出。タスクに着手したらドシエを作成し（`/hiyokb:task-focus`）、"
              "以後そこに記録する。")
    if scope == "inbox":
        print("- 自動書き込みの範囲 = **inbox のみ**。ドシエ/KB への反映は人に確認してから行う"
              "（このセッションの要点は終了時に inbox へ自動退避される）。")
    elif scope == "kb":
        print("- 自動書き込みの範囲 = **KB まで**。ドシエ追記に加え、再利用可能な確定知見は"
              "`~/.hiyokb/kb`（または `projects/<名>/kb`）へ出典付きで昇格してよい。索引は "
              "`build_kb_index.py` で再生成。")
    else:  # dossier
        print("- 自動書き込みの範囲 = **ドシエ追記まで**。KB への昇格（再利用知見の共有知識化）は"
              "人に確認してから行う。")
    print("- `sensitive` を含む内容は外部送信を伴う処理を避ける。")


def main():
    if not os.path.isdir(TASK_ROOT):
        return
    cfg = capture_config()
    rows, stale_line = index_rows()
    if not rows and not os.path.exists(INDEX):
        if cfg["enabled"] and cfg["inline_recording"]:
            print_capture_instruction(cfg)
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
    if cfg["enabled"] and cfg["inline_recording"]:
        print_capture_instruction(cfg)


if __name__ == "__main__":
    main()
