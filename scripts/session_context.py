#!/usr/bin/env python3
"""SessionStart で実行し、タスク状況を簡潔に提示する（読み取りのみ・ネットワーク無し）。

cwd（起動リポジトリ）から hiyokb プロジェクトを解決し、**表示・自動記録・KB を現プロジェクトに
限定**する。プロジェクト未設定のリポジトリなら「どのプロジェクトか」をユーザーに確認させる指示を出す。
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
import build_index as bi  # noqa: E402  ローダ/マージを再利用（index.md の表フォーマットに依存しない）
from _config import capture_config  # noqa: E402

TASK_ROOT = os.path.expanduser("~/.hiyokb")

STATUS_DISP = {"in_progress": "🔵", "blocked": "⛔", "review": "👀", "todo": "⚪", "done": "✅"}


def read_cwd():
    """SessionStart フックの stdin(JSON) から cwd を取る。無ければ os.getcwd()。"""
    try:
        data = json.load(sys.stdin)
        return data.get("cwd") or os.getcwd()
    except Exception:
        return os.getcwd()


def active_rows():
    """build_index のデータ関数から、未完タスク（dict）を状態→優先度順で返す。"""
    src_tasks, src_meta = bi.load_sources()
    loc = bi.load_dossiers()
    rows = bi.merge(src_tasks, src_meta, loc)
    active = [r for r in rows if r["status"] != "done"]
    active.sort(key=lambda r: (bi.ACTIVE_ORDER.get(r["status"], 5),
                               bi.PRIO_ORDER.get(r["priority"], 3),
                               r["due"] or "9999", r["id"]))
    stale = any(m.get("stale") for m in src_meta.values())
    return active, stale


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
        print("- このリポジトリは**プロジェクト未設定**。決まるまではドシエ/KB へ自動で書き込まない"
              "（要点はセッション終了時に控えとして inbox に保存されます）。上の確認でプロジェクトが決まったら、"
              "`projects/<決まった名前>/` に記録を始める。")
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
        tmpl = os.path.join(os.path.dirname(SCRIPTS_DIR), "templates", "kb-article.md")
        bk = os.path.join(SCRIPTS_DIR, "build_kb_index.py")
        print(f"- 自動書き込みの範囲 = **KB まで**（人への確認は不要・確定知見は自動で昇格する）。"
              "**ドシエの有無に関わらず**、再利用可能な確定知見（設定・手順・原因と対策・"
              "設計判断など、後で引けて役立つもの）が定まったら、その都度 "
              f"`~/.hiyokb/{kb_dir}/` に出典付きで**追記する**（未確定・噂・要約途中は昇格しない）。")
        print(f"  - 雛形 `{tmpl}` を使い、`source`(出自) を必ず埋め、本文は既存ページへ `[[ ]]` で"
              "リンクして孤立させない。アクティブなドシエがあれば経緯はそちらにも残す。"
              "横断汎用な知識のみ明示指示で global `kb/` へ。")
        print(f"  - 追記後は索引を再生成: `python3 \"{bk}\"`。")
    else:  # dossier
        print("- 自動書き込みの範囲 = **ドシエ追記まで**。KB への昇格は人に確認してから行う。")
    print("- `sensitive` を含む内容は外部送信を伴う処理を避ける。")


def print_unbound(repo):
    print("## hiyokb: このリポジトリのプロジェクトが未設定です")
    print(f"- 今いるリポジトリ: **{repo}**（どのプロジェクトの作業か、まだ登録されていません）")
    kps = known_projects()
    print(f"- ユーザーに「このリポジトリはどのプロジェクトの作業ですか？」と確認する"
          f"（登録済み: [{', '.join(kps) or 'まだ無し'}] から選ぶ／新しい名前でもOK）。")
    print(f"- 決まったら登録（次回から自動で判別されます）: "
          f"`python3 \"{os.path.join(SCRIPTS_DIR, 'project_bind.py')}\" github {repo} <プロジェクト名>`")
    print("- 登録できるまでは、タスクやメモの保存先を勝手に決めない（先に確認する）。")


def main():
    if not os.path.isdir(TASK_ROOT):
        return
    cfg = capture_config()
    cwd = read_cwd()
    repo, project = _config.current_project(cwd)
    rows, stale = active_rows()
    unbound = bool(repo and not project)

    # タスクもドシエもまだ無い（収集前）
    if not rows:
        if unbound:
            print_unbound(repo)
        if cfg["enabled"] and cfg["inline_recording"]:
            print_capture_instruction(cfg, project, unbound)
        return

    if project:
        show = [r for r in rows if r["project"] == project]
        print(f"## hiyokb の状況（プロジェクト: {project}）")
        print(f"- このプロジェクトの未完タスク: {len(show)} 件"
              + (f"（全体 {len(rows)} 件は `/hiyokb:task-list --all`）" if len(rows) != len(show) else ""))
    else:
        show = rows
        print("## hiyokb の状況")
        if repo:
            print(f"- 今いるリポジトリ {repo} はプロジェクト未設定（下記参照）。今は全プロジェクトをまとめて表示中。")
        print(f"- 未完タスク: {len(rows)} 件")

    show_proj = project is None   # 横断表示のときは所属プロジェクトを併記
    for r in show[:6]:
        icon = STATUS_DISP.get(r["status"], "・")
        tid = r.get("id_display", r["id"])
        tags = []
        if show_proj and r["project"]:
            tags.append(f"📁{r['project']}")
        if r["priority"] in ("high", "mid"):
            tags.append("🔴高" if r["priority"] == "high" else "🟡中")
        if r["due"]:
            tags.append(f"期限{r['due']}")
        suffix = f"（{' / '.join(tags)}）" if tags else ""
        print(f"  - {icon} {tid}: {r['title']}{suffix}")
    if len(show) > 6:
        print(f"  - …他 {len(show) - 6} 件（`/hiyokb:task-list`）")
    if stale:
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
