#!/usr/bin/env python3
"""SessionStart で実行し、タスク状況を簡潔に提示する（読み取りのみ・ネットワーク無し）。

cwd（起動リポジトリ）から hiyokb プロジェクトを解決し、**表示・自動記録・KB を現プロジェクトに
限定**する。未束縛のリポジトリなら「どのプロジェクトか」をユーザーに確認させる指示を出す。
出力はセッションのコンテキストに注入されるため短く保つ。
"""
import glob
import json
import os
import re
import subprocess
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)
import _config  # noqa: E402
from _config import capture_config  # noqa: E402

TASK_ROOT = os.path.expanduser("~/.hiyokb")
INDEX = os.path.join(TASK_ROOT, "index.md")


def read_cwd():
    """SessionStart フックの stdin(JSON) から cwd を取る。無ければ os.getcwd()。"""
    try:
        data = json.load(sys.stdin)
        return data.get("cwd") or os.getcwd()
    except Exception:
        return os.getcwd()


def index_rows():
    """index.md の表を読む。各行 [id,title,source,status,priority,due,project,dossier]。"""
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
                rows.append(cells)
    return rows, stale_line


def row_project(r):
    return r[6] if len(r) > 6 else ""


def known_projects():
    return sorted(os.path.basename(os.path.dirname(p))
                  for p in glob.glob(os.path.join(TASK_ROOT, "projects", "*", "tasks")))


def kb_page_count(project=None):
    dirs = ([os.path.join(TASK_ROOT, "projects", project, "kb")] if project
            else [os.path.join(TASK_ROOT, "kb")] + glob.glob(os.path.join(TASK_ROOT, "projects", "*", "kb")))
    n = 0
    for d in dirs:
        for p in glob.glob(os.path.join(d, "*.md")):
            if os.path.basename(p) not in ("index.md", "SCHEMA.md"):
                n += 1
    return n


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


def active_dossier(project=None):
    """最後に更新された未完ドシエ（in_progress/blocked/review）。project 指定時はその配下のみ。"""
    pattern = (os.path.join(TASK_ROOT, "projects", project, "tasks", "*.md") if project
               else os.path.join(TASK_ROOT, "projects", "*", "tasks", "*.md"))
    cands = []
    for p in glob.glob(pattern):
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


def print_capture_instruction(cfg, project=None, unbound=False):
    """暗黙キャプチャの常駐指示を context に注入する（経路A: LLM 駆動の inline 記録）。"""
    scope = cfg["auto_scope"]
    kb_dir = f"projects/{project}/kb" if project else "kb"
    print()
    print("## hiyokb: 暗黙キャプチャ（明示的に頼まれなくても自動で記録する）")
    if unbound:
        print("- このリポジトリは**プロジェクト未確定**。確定するまでドシエ/KB へ自動書き込みしない"
              "（要点はセッション終了時に inbox へ退避される）。上の確認でプロジェクトが決まったら、"
              "`projects/<決定>/` に記録を開始する。")
        print("- `sensitive` を含む内容は外部送信を伴う処理を避ける。")
        return
    print("作業しながら知識を貯める。タスクに取り組む中で **決定事項・調査結果・次アクション** が"
          "定まったら、その都度ドシエの該当セクション（決定事項 / 調査メモ / 次アクション / 進捗ログ）に"
          "**追記**する（追記のみ・既存行は消さない・出典を残す）。")
    act = active_dossier(project)
    if act:
        label = f"{act['id']} {act['title']}".strip() or act["rel"]
        print(f"- アクティブなドシエ: {label} → `{act['rel']}`（[{act['status']}]）")
        print("  別タスクの話なら該当ドシエへ。該当ドシエが無ければ作成してから記録する。")
    elif project:
        print(f"- `{project}` に未完ドシエなし。タスクに着手したら `projects/{project}/tasks/` に"
              "ドシエを作成し、以後そこに記録する。")
    else:
        print("- 未完のドシエは未検出。タスクに着手したらドシエを作成し（`/hiyokb:task-focus`）、"
              "以後そこに記録する。")
    if scope == "inbox":
        print("- 自動書き込みの範囲 = **inbox のみ**。ドシエ/KB への反映は人に確認してから行う。")
    elif scope == "kb":
        print(f"- 自動書き込みの範囲 = **KB まで**。ドシエ追記に加え、再利用可能な確定知見は"
              f"`~/.hiyokb/{kb_dir}` へ出典付きで自動追記してよい（横断汎用な知識のみ明示指示で global `kb/` へ）。"
              "索引は `build_kb_index.py` で再生成。")
    else:  # dossier
        print("- 自動書き込みの範囲 = **ドシエ追記まで**。KB への昇格は人に確認してから行う。")
    print("- `sensitive` を含む内容は外部送信を伴う処理を避ける。")


def print_unbound(repo):
    print("## hiyokb: このリポジトリは未束縛")
    print(f"- 現在地（git remote）: **{repo}** — どの hiyokb プロジェクトに属するか未設定。")
    kps = known_projects()
    print(f"- ユーザーに確認: 既知プロジェクト [{', '.join(kps) or 'なし'}] のどれか、または新規名。")
    print(f"- 決まったら保存（次回から自動解決）: "
          f"`python3 \"{os.path.join(SCRIPTS_DIR, 'project_bind.py')}\" github {repo} <project>`")
    print("- 束縛が決まるまで、記録先プロジェクトを勝手に決めない（先に確認する）。")


def main():
    if not os.path.isdir(TASK_ROOT):
        return
    cfg = capture_config()
    cwd = read_cwd()
    repo, project = _config.current_project(cwd)
    rows, stale_line = index_rows()

    # ストアはあるが index 未生成
    unbound = bool(repo and not project)
    if not rows and not os.path.exists(INDEX):
        if unbound:
            print_unbound(repo)
        if cfg["enabled"] and cfg["inline_recording"]:
            print_capture_instruction(cfg, project, unbound)
        return

    if project:
        prows = [r for r in rows if row_project(r) == project]
        print(f"## hiyokb の状況（プロジェクト: {project}）")
        print(f"- このプロジェクトのアクティブなタスク: {len(prows)} 件"
              + (f" / 全体 {len(rows)} 件（`/hiyokb:task-list --all`）" if len(rows) != len(prows) else ""))
        show = prows
    else:
        print("## hiyokb の状況")
        if repo:
            print(f"- 現在地 {repo} は未束縛（下記参照）。全プロジェクト横断で表示中。")
        print(f"- アクティブなタスク: {len(rows)} 件")
        show = rows

    show_proj = project is None   # 横断表示のときは各タスクの所属プロジェクトを併記
    for r in show[:6]:
        tid, title, status = r[0], r[1], r[3]
        due = r[5] if len(r) > 5 else ""
        proj = row_project(r)
        tags = []
        if show_proj and proj:
            tags.append(f"📁{proj}")
        if due:
            tags.append(f"期限 {due}")
        suffix = f"（{' / '.join(tags)}）" if tags else ""
        print(f"  - [{status}] {tid}: {title}{suffix}")
    if len(show) > 6:
        print(f"  - …他 {len(show) - 6} 件（`/hiyokb:task-list`）")
    if stale_line and "STALE" in stale_line:
        print("- ⚠️ 一部ソースは前回値（`/hiyokb:task-sync` で更新）")
    kb = kb_page_count(project)
    if kb:
        where = f"projects/{project}/kb" if project else "kb"
        print(f"- 知識ベース: {kb} ページ（{where} / `/hiyokb:kb`）")

    if unbound:
        print()
        print_unbound(repo)
    if cfg["enabled"] and cfg["inline_recording"]:
        print_capture_instruction(cfg, project, unbound)


if __name__ == "__main__":
    main()
