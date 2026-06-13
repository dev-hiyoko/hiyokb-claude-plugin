#!/usr/bin/env python3
"""KB の内容カタログ（index.md）を決定論的に再生成する。

各ページの frontmatter（title / summary / tags）から1行要約をカテゴリ別に並べる。
LLM ではなくファイル走査でメカニカルに作るため、再現性が高くトークンも使わない。

使い方:
  build_kb_index.py [<kb_dir> ...]   # 省略時は ~/.task/kb と projects/*/kb 全て
"""
import glob
import os
import re
import sys

TASK_ROOT = os.path.expanduser("~/.task")
SKIP = {"index.md", "SCHEMA.md"}


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm, body = {}, text[end + 4:]
    for line in text[3:end].split("\n"):
        if not line or line[0] in " \t" or line.lstrip().startswith("#") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
        else:
            v = v.strip("\"'") or None
        fm[k.strip()] = v
    return fm, body


def page_info(path):
    text = open(path, encoding="utf-8").read()
    fm, body = parse_frontmatter(text)
    stem = os.path.splitext(os.path.basename(path))[0]
    title = fm.get("title") or stem
    summary = fm.get("summary")
    if not summary:
        for line in body.split("\n"):
            s = line.strip()
            if s and not s.startswith("#") and not s.startswith("<!--"):
                summary = s[:80]
                break
    tags = fm.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return {"title": title, "summary": summary or "", "tags": tags}


def build_one(kb_dir):
    pages = []
    for path in sorted(glob.glob(os.path.join(kb_dir, "*.md"))):
        if os.path.basename(path) in SKIP:
            continue
        pages.append(page_info(path))
    rel = os.path.relpath(kb_dir, TASK_ROOT)
    out = [f"# KB 内容カタログ — {rel}", "",
           "> 自動生成（build_kb_index.py）。手で編集しない。", ""]
    if not pages:
        out.append("_まだページがありません_")
    else:
        by_tag = {}
        for p in pages:
            cat = p["tags"][0] if p["tags"] else "未分類"
            by_tag.setdefault(cat, []).append(p)
        for cat in sorted(by_tag):
            out.append(f"## {cat}")
            for p in sorted(by_tag[cat], key=lambda x: x["title"]):
                line = f'- [[{p["title"]}]]'
                if p["summary"]:
                    line += f' — {p["summary"]}'
                out.append(line)
            out.append("")
    open(os.path.join(kb_dir, "index.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    return len(pages)


def main():
    dirs = sys.argv[1:]
    if not dirs:
        dirs = [os.path.join(TASK_ROOT, "kb")]
        dirs += sorted(glob.glob(os.path.join(TASK_ROOT, "projects", "*", "kb")))
    total = 0
    for d in dirs:
        if os.path.isdir(d):
            n = build_one(d)
            total += n
            print(f"{os.path.relpath(d, TASK_ROOT)}: {n} ページ")
    if not total:
        print("KB ページはまだありません")


if __name__ == "__main__":
    main()
