#!/usr/bin/env python3
"""KB の健全性チェック（リンク健全性を最重視）。

検出するもの:
  - broken : [[X]] の参照先ページが存在しない
  - orphan : どのページからも [[ ]] でリンクされていないページ
  - one_way: A→B はあるが B→A が無い（相互参照の欠落）
  - no_prov: frontmatter に source（出自）が無いページ
  - rel_missing: relates_to が存在しないページを指している

既定は検出＋提案のみ。--fix で機械的に安全なものだけ修復する:
  - 各 KB ディレクトリの index.md を再生成（build_kb_index.py 相当）
  - one_way を相互リンク化（対象ページの「## 関連」に [[A]] を追記。冪等）
  ※ broken の張り直しは意図を機械判断できないため report のみ（人が直す）。

使い方:
  kb_lint.py [--fix] [<kb_dir> ...]   # 省略時は ~/.task/kb と projects/*/kb 全て
"""
import glob
import os
import re
import subprocess
import sys

TASK_ROOT = os.path.expanduser("~/.task")
HERE = os.path.dirname(os.path.abspath(__file__))
SKIP = {"index.md", "SCHEMA.md"}
LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def parse_frontmatter(text):
    fm = {}
    if not text.startswith("---"):
        return fm
    end = text.find("\n---", 3)
    if end == -1:
        return fm
    for line in text[3:end].split("\n"):
        if not line or line[0] in " \t" or line.lstrip().startswith("#") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1]
            if "{" in inner:
                items = []
                for blk in re.findall(r"\{([^}]*)\}", inner):
                    d = {}
                    for part in blk.split(","):
                        if ":" in part:
                            kk, _, vv = part.partition(":")
                            d[kk.strip()] = vv.strip().strip("\"'")
                    items.append(d)
                v = items
            else:
                v = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
        else:
            v = v.strip("\"'") or None
        fm[k.strip()] = v
    return fm


def links_in(text):
    out = []
    for m in LINK_RE.findall(text):
        out.append(m.split("|")[0].strip())
    return out


def load_pages(dirs):
    """全 KB ディレクトリのページを読み、name→page の登録表を作る。"""
    pages = {}
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.md"))):
            if os.path.basename(path) in SKIP:
                continue
            text = open(path, encoding="utf-8").read()
            fm = parse_frontmatter(text)
            stem = os.path.splitext(os.path.basename(path))[0]
            title = fm.get("title") or stem
            pages[path] = {
                "path": path, "title": title, "stem": stem, "fm": fm,
                "text": text, "links": links_in(text),
            }
    return pages


def resolve_name(name, by_name):
    return by_name.get(name)


def lint(dirs, fix):
    pages = load_pages(dirs)
    by_name = {}
    for p in pages.values():
        by_name[p["title"]] = p
        by_name[p["stem"]] = p

    findings = {"broken": [], "orphan": [], "one_way": [], "no_prov": [], "rel_missing": []}
    inbound = {path: set() for path in pages}

    for p in pages.values():
        for tgt in p["links"]:
            r = resolve_name(tgt, by_name)
            if r is None:
                findings["broken"].append((p["title"], tgt))
            else:
                inbound[r["path"]].add(p["title"])
        if not p["fm"].get("source"):
            findings["no_prov"].append(p["title"])
        for rel in p["fm"].get("relates_to", []) or []:
            if isinstance(rel, dict) and rel.get("page") and rel["page"] not in by_name:
                findings["rel_missing"].append((p["title"], rel["page"]))

    for p in pages.values():
        if not inbound[p["path"]]:
            findings["orphan"].append(p["title"])

    # one_way: A links B but B does not link A
    for p in pages.values():
        for tgt in p["links"]:
            r = resolve_name(tgt, by_name)
            if r and p["title"] not in [resolve_name(t, by_name)["title"]
                                        for t in r["links"] if resolve_name(t, by_name)]:
                findings["one_way"].append((p["title"], r["title"]))

    if fix:
        # 1) index 再生成
        for d in dirs:
            if os.path.isdir(d):
                subprocess.run([sys.executable, os.path.join(HERE, "build_kb_index.py"), d])
        # 2) one_way を相互リンク化（対象ページの「## 関連」に追記・冪等）
        for src_title, tgt_title in findings["one_way"]:
            tgt = by_name.get(tgt_title)
            if not tgt:
                continue
            backlink = f"[[{src_title}]]"
            if backlink in tgt["text"]:
                continue
            text = tgt["text"].rstrip() + "\n"
            if "## 関連" in text:
                text = text.replace("## 関連", f"## 関連\n- {backlink}", 1)
            else:
                text += f"\n## 関連\n- {backlink}\n"
            open(tgt["path"], "w", encoding="utf-8").write(text)
            tgt["text"] = text

    return findings, len(pages)


def report(findings, n):
    print(f"KB lint: {n} ページを検査\n")
    labels = {
        "broken": "リンク切れ（[[X]] の参照先なし）※人手で修正",
        "orphan": "孤立ノート（被リンクなし）",
        "one_way": "片方向リンク（相互参照の欠落）",
        "no_prov": "出自(source)なし",
        "rel_missing": "relates_to の参照先なし",
    }
    total = 0
    for key, label in labels.items():
        items = findings[key]
        if not items:
            continue
        total += len(items)
        print(f"■ {label}: {len(items)} 件")
        for it in items[:50]:
            print(f"   - {it[0]} → {it[1]}" if isinstance(it, tuple) else f"   - {it}")
    if total == 0:
        print("問題は見つかりませんでした ✓")


def main():
    fix = "--fix" in sys.argv
    dirs = [a for a in sys.argv[1:] if a != "--fix"]
    if not dirs:
        dirs = [os.path.join(TASK_ROOT, "kb")]
        dirs += sorted(glob.glob(os.path.join(TASK_ROOT, "projects", "*", "kb")))
    dirs = [d for d in dirs if os.path.isdir(d)]
    if not dirs:
        print("KB ディレクトリがありません")
        return
    findings, n = lint(dirs, fix)
    report(findings, n)
    if fix:
        print("\n--fix: index 再生成と片方向リンクの相互化を実施しました")


if __name__ == "__main__":
    main()
