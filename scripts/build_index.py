#!/usr/bin/env python3
"""~/.task/index.md を決定論的に再マージ生成する。

入力:
  - ~/.task/sources/*.md   … ソース所有のスナップショット（```json ブロック）
  - ~/.task/projects/*/tasks/*.md … ローカル所有のドシエ frontmatter
出力:
  - ~/.task/index.md       … 両者を task id でマージした横断ビュー

マージは所有権テーブルに従う:
  - ソース所有: title / status / due / labels / source_ref  → スナップショットが上書き
  - ローカル所有: priority / type / project / dossier / relates_to / sensitive → ドシエを保持
  - status の精緻化: GitHub Issue は open/closed しか持たないため、
    open のときはローカルの in_progress/blocked/review を尊重（無ければ todo）。closed→done。
  - relates_to: same_as は重複として1グループに畳む。

オプション: --all（done も含める） / --stdout（ファイルでなく標準出力へ）

PyYAML 非依存。frontmatter は本プラグインが書く統制された形式のみを想定した簡易パーサで読む。
"""
import glob
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _config  # noqa: E402

TASK_ROOT = os.path.expanduser("~/.task")
SRC_DIR = os.path.join(TASK_ROOT, "sources")
PROJ_DIR = os.path.join(TASK_ROOT, "projects")
INDEX_FILE = os.path.join(TASK_ROOT, "index.md")

ACTIVE_ORDER = {"in_progress": 0, "blocked": 1, "review": 2, "todo": 3, "done": 9}
LOCAL_STATUS = {"in_progress", "blocked", "review"}
DONE_STATES = {"done", "closed"}


# ---------- frontmatter 簡易パーサ（統制された形式専用） ----------
def parse_value(val):
    if val and val[0] not in "\"'[{":
        i = val.find(" #")          # space-hash 以降をインラインコメントとして除去
        if i != -1:
            val = val[:i].strip()
    if val == "":
        return None
    low = val.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if (val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'"):
        return val[1:-1]
    if val.startswith("[") and val.endswith("]"):
        return parse_flow_list(val)
    return val


def parse_flow_list(val):
    inner = val[1:-1].strip()
    if not inner:
        return []
    if "{" in inner:
        items = []
        for blk in re.findall(r"\{([^}]*)\}", inner):
            d = {}
            for part in blk.split(","):
                if ":" in part:
                    k, _, v = part.partition(":")
                    d[k.strip()] = v.strip().strip("\"'")
            items.append(d)
        return items
    return [x.strip().strip("\"'") for x in inner.split(",")]


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm = {}
    for line in text[3:end].split("\n"):
        if not line or line[0] in " \t" or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = parse_value(val.strip())
    return fm


# ---------- 読み込み ----------
def load_sources():
    enabled = _config.enabled_sources()       # 無効ソースの古いスナップショットは無視（非破壊）
    src_tasks, src_meta = {}, {}
    for path in sorted(glob.glob(os.path.join(SRC_DIR, "*.md"))):
        try:
            txt = open(path, encoding="utf-8").read()
            m = re.search(r"```json\n(.*?)\n```", txt, re.S)
            if not m:
                continue
            data = json.loads(m.group(1))
        except Exception:
            continue
        name = data.get("source", os.path.basename(path)[:-3])
        if name not in enabled:
            continue
        src_meta[name] = {"synced": data.get("synced"), "stale": bool(data.get("stale"))}
        for t in data.get("tasks", []):
            if t.get("id"):
                src_tasks[t["id"]] = t
    return src_tasks, src_meta


def load_dossiers():
    loc = {}
    for path in sorted(glob.glob(os.path.join(PROJ_DIR, "*", "tasks", "*.md"))):
        if os.sep + "archive" + os.sep in path:
            continue
        fm = parse_frontmatter(open(path, encoding="utf-8").read())
        tid = fm.get("id")
        if not tid:
            continue
        fm["dossier"] = os.path.relpath(path, TASK_ROOT)
        loc[tid] = fm
    return loc


# ---------- マージ ----------
def merge_status(s, l):
    if s:
        if str(s.get("status", "")).lower() in DONE_STATES:
            return "done"
        ls = (l or {}).get("status")
        return ls if ls in LOCAL_STATUS else (s.get("status") or "todo")
    return (l or {}).get("status") or "todo"


def merge(src_tasks, src_meta, loc):
    rows = {}
    for tid in set(src_tasks) | set(loc):
        s, l = src_tasks.get(tid), loc.get(tid)
        source = (s or {}).get("source") or (l or {}).get("source") or "local"
        rows[tid] = {
            "id": tid,
            "title": (s or {}).get("title") or (l or {}).get("title") or "(no title)",
            "source": source,
            "status": merge_status(s, l),
            "priority": (l or {}).get("priority") or "",
            "due": (s or {}).get("due") or (l or {}).get("due") or "",
            "project": (l or {}).get("project") or "",
            "dossier": (l or {}).get("dossier") or "",
            "sensitive": bool((l or {}).get("sensitive")),
            "relates_to": (l or {}).get("relates_to") or [],
            "stale": src_meta.get(source, {}).get("stale", False),
        }
    return fold_same_as(rows)


def fold_same_as(rows):
    """relates_to same_as で結ばれた id を1グループに畳む。"""
    parent = {tid: tid for tid in rows}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        if a in parent and b in parent:
            parent[find(a)] = find(b)

    for tid, r in rows.items():
        for rel in r["relates_to"]:
            if isinstance(rel, dict) and rel.get("rel") == "same_as" and rel.get("id"):
                union(tid, rel["id"])

    groups = {}
    for tid in rows:
        groups.setdefault(find(tid), []).append(tid)

    folded = []
    for members in groups.values():
        # 代表 = ドシエがあるもの優先、無ければ id 昇順の先頭
        members.sort(key=lambda t: (rows[t]["dossier"] == "", t))
        primary = rows[members[0]]
        if len(members) > 1:
            others = ", ".join(members[1:])
            primary = dict(primary)
            primary["id_display"] = f'{primary["id"]} (+{others})'
        folded.append(primary)
    return folded


# ---------- 出力 ----------
def render(rows, src_meta, include_done):
    today = datetime.now().strftime("%Y-%m-%d")
    out = ["# タスク横断インデックス", "",
           f"> 自動生成（build_index.py） / 更新: {today}。手で編集しない（ドシエ frontmatter とソースキャッシュが真実）。", ""]
    if src_meta:
        out.append("**ソース同期状況**: " + " / ".join(
            f"{name} {'⚠️STALE' if m['stale'] else 'ok'}({(m['synced'] or '')[:16]})"
            for name, m in sorted(src_meta.items())) + "\n")

    visible = [r for r in rows if include_done or r["status"] != "done"]
    visible.sort(key=lambda r: (ACTIVE_ORDER.get(r["status"], 5), r["due"] or "9999", r["id"]))

    out.append("| id | title | source | status | priority | due | project | dossier |")
    out.append("|----|-------|--------|--------|----------|-----|---------|---------|")
    for r in visible:
        idc = r.get("id_display", r["id"])
        st = r["status"] + (" ⚠️" if r["stale"] else "") + (" 🔒" if r["sensitive"] else "")
        title = (r["title"][:50] + "…") if len(r["title"]) > 51 else r["title"]
        title = title.replace("|", "\\|")
        out.append(f'| {idc} | {title} | {r["source"]} | {st} | {r["priority"]} | '
                   f'{r["due"]} | {r["project"]} | {r["dossier"]} |')

    done_n = sum(1 for r in rows if r["status"] == "done")
    if not include_done and done_n:
        out.append("")
        out.append(f"_完了 {done_n} 件は非表示（`/hiyokb:task-list --all` で表示）_")
    out.append("")
    return "\n".join(out)


def main():
    include_done = "--all" in sys.argv
    to_stdout = "--stdout" in sys.argv
    src_tasks, src_meta = load_sources()
    loc = load_dossiers()
    rows = merge(src_tasks, src_meta, loc)
    text = render(rows, src_meta, include_done)
    if to_stdout:
        sys.stdout.write(text)
    else:
        open(INDEX_FILE, "w", encoding="utf-8").write(text)
        n_active = sum(1 for r in rows if r["status"] != "done")
        stale = [n for n, m in src_meta.items() if m["stale"]]
        msg = f"index.md を再生成: active {n_active} 件"
        if stale:
            msg += f" / ⚠️ stale ソース: {', '.join(stale)}"
        print(msg)


if __name__ == "__main__":
    main()
