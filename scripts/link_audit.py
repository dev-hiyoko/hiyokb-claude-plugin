#!/usr/bin/env python3
"""参照元（ソース）とタスク（ドシエ・横断リンク）の紐づき状況を監査して提示する。

決定論コア。task-list がこれを呼び、ユーザーに「この紐づけで合っているか」を確認させ、
必要なら /hiyokb:task-link でリンクを確定させるための材料を出す。判定は安全側（exact）に留め、
あいまいなクロスソース候補の提案は LLM（スキル）側に委ねる。

出力（stdout・Markdown）:
  1. 紐づき状況   … 各タスクが ⊘ソースのみ / 📄ドシエあり / 🔗複数ソースをリンク済 のどれか
  2. 紐づけ候補   … 未リンクで「正規化タイトルが一致」かつ「別ソース」のグループ（要確認）
  3. リンク健全性 … ドシエの relates_to が指す id が現在どのソースにも無い（迷子リンク）

PyYAML 非依存。build_index のローダ/マージを再利用する。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_index as bi  # noqa: E402  ローダ・マージ・畳み込みを再利用

SRC_LABEL = {"gh": "github", "bl": "backlog", "slack": "slack", "local": "local"}


def src_of(tid, src_tasks, loc):
    t = src_tasks.get(tid) or {}
    if t.get("source"):
        return t["source"]
    l = loc.get(tid) or {}
    if l.get("source"):
        return l["source"]
    return SRC_LABEL.get(tid.split(":", 1)[0], tid.split(":", 1)[0])


def title_of(tid, src_tasks, loc):
    return ((src_tasks.get(tid) or {}).get("title")
            or (loc.get(tid) or {}).get("title") or "(no title)")


def norm(t):
    return re.sub(r"\s+", "", re.sub(r"[^\w\s]+", "", (t or "").lower())).strip()


def same_as_groups(loc):
    """ドシエの relates_to: same_as から union-find でグループ（id -> 代表）を作る。"""
    ids = set(loc)
    for l in loc.values():
        for rel in (l.get("relates_to") or []):
            if isinstance(rel, dict) and rel.get("id"):
                ids.add(rel["id"])
    parent = {i: i for i in ids}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for tid, l in loc.items():
        for rel in (l.get("relates_to") or []):
            if isinstance(rel, dict) and rel.get("rel") == "same_as" and rel.get("id"):
                parent[find(tid)] = find(rel["id"])
    groups = {}
    for i in ids:
        groups.setdefault(find(i), set()).add(i)
    return groups


def main():
    src_tasks, src_meta = bi.load_sources()
    loc = bi.load_dossiers()
    all_ids = set(src_tasks) | set(loc)
    if not all_ids:
        print("（タスクがありません。まず `/hiyokb:task-sync` で収集してください）")
        return

    groups = same_as_groups(loc)
    rep = {i: r for r, members in groups.items() for i in members}

    # ---------- 1. 紐づき状況 ----------
    print("## 紐づき状況（参照元 ↔ タスク）")
    print("> 凡例: 🔗複数ソースをリンク済 / 📄ドシエあり / ⊘ソースのみ（未着手）")
    seen_groups = set()
    lines = []
    for tid in all_ids:
        r = rep.get(tid, tid)
        if r in seen_groups:
            continue
        seen_groups.add(r)
        members = [m for m in sorted(groups.get(r, {tid})) if m in all_ids] or [tid]
        # 代表はドシエ保有側を優先（build_index の畳み込みと表示を揃える）
        members.sort(key=lambda m: (not (m in loc and loc[m].get("dossier")), m))
        srcs = sorted({src_of(m, src_tasks, loc) for m in members})
        dossier = next((loc[m]["dossier"] for m in members if m in loc and loc[m].get("dossier")), None)
        icon = "🔗" if len(members) > 1 else ("📄" if dossier else "⊘")
        title = title_of(members[0], src_tasks, loc)
        idc = members[0] + (f" (+{', '.join(members[1:])})" if len(members) > 1 else "")
        tail = f"dossier: {dossier}" if dossier else "dossier: なし"
        lines.append((icon, f"- {icon} `{idc}` {title} | sources: {'+'.join(srcs)} | {tail}"))
    for _, line in sorted(lines, key=lambda x: {"🔗": 0, "📄": 1, "⊘": 2}.get(x[0], 3)):
        print(line)

    # ---------- 2. 紐づけ候補（未リンク・同名・別ソース） ----------
    by_title = {}
    for tid in all_ids:
        by_title.setdefault(norm(title_of(tid, src_tasks, loc)), []).append(tid)
    candidates = []
    for key, ids in by_title.items():
        if not key or len(ids) < 2:
            continue
        # 既に同一グループに畳まれているものは除外
        if len({rep.get(i, i) for i in ids}) < 2:
            continue
        srcs = {src_of(i, src_tasks, loc) for i in ids}
        if len(srcs) < 2:  # 別ソースをまたぐものだけ（クロスソース）
            continue
        candidates.append(sorted(ids))
    print("\n## 紐づけ候補（未リンク・同名・別ソース）")
    if not candidates:
        print("- なし（exact一致のクロスソース重複は検出されませんでした）")
    else:
        for i, ids in enumerate(candidates, 1):
            print(f"{i}. 「{title_of(ids[0], src_tasks, loc)}」")
            for tid in ids:
                print(f"   - `{tid}` ({src_of(tid, src_tasks, loc)})")
            print(f"   → 同一なら: `/hiyokb:task-link {' '.join(ids)}`")

    # ---------- 3. リンク健全性（迷子リンク） ----------
    dangling = []
    for tid, l in loc.items():
        for rel in (l.get("relates_to") or []):
            if isinstance(rel, dict) and rel.get("id") and rel["id"] not in all_ids:
                dangling.append((l.get("dossier") or tid, rel["id"], rel.get("rel", "")))
    print("\n## リンク健全性")
    if not dangling:
        print("- 問題なし（relates_to の参照先はすべて現存）")
    else:
        for dossier, missing, relkind in dangling:
            print(f"- ⚠ `{dossier}` の relates_to → `{missing}`（{relkind}）が現在どのソースにも無い"
                  f"（解決済み/別ownerで非取得/typo のいずれか。要確認）")


if __name__ == "__main__":
    main()
