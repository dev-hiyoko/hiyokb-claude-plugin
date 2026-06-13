#!/usr/bin/env python3
"""生ソースを ~/.hiyokb/inbox に取り込む（不変保存）。

- 内容の SHA1 で冪等化（同一内容は再取り込みしない）。
- 取り込みを ~/.hiyokb/log.md に追記（追記専用クロニクル）。
- 原本は加工せずそのまま保存する（読むだけ・書き換えない）。

使い方:
  ingest_intake.py <file_path>               # ファイル/画像を取り込み
  ingest_intake.py --text --title "定例MTG"   # 標準入力のテキストを取り込み

出力(stdout): 取り込んだ inbox の相対パス。既取り込みなら 'EXISTS\\t<path>'。
"""
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime

TASK_ROOT = os.path.expanduser("~/.hiyokb")
INBOX = os.path.join(TASK_ROOT, "inbox")
MANIFEST = os.path.join(INBOX, ".manifest.json")
LOG = os.path.join(TASK_ROOT, "log.md")


def load_manifest():
    try:
        return json.load(open(MANIFEST, encoding="utf-8"))
    except Exception:
        return {}


def save_manifest(m):
    json.dump(m, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def slug(s):
    s = re.sub(r"[^\w\-.]+", "_", s.strip())[:60].strip("_")
    return s or "note"


def append_log(line):
    new = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8") as f:
        if new:
            f.write("# log — ingest/query/lint の追記専用クロニクル\n\n")
        f.write(line + "\n")


def uniq_dest(name):
    dest = os.path.join(INBOX, name)
    if not os.path.exists(dest):
        return dest
    root, ext = os.path.splitext(name)
    i = 1
    while os.path.exists(os.path.join(INBOX, f"{root}_{i}{ext}")):
        i += 1
    return os.path.join(INBOX, f"{root}_{i}{ext}")


def main():
    os.makedirs(INBOX, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    manifest = load_manifest()
    args = sys.argv[1:]

    if args and args[0] == "--text":
        title = args[args.index("--title") + 1] if "--title" in args else "note"
        data = sys.stdin.buffer.read()
        if not data:
            print("no stdin text", file=sys.stderr)
            sys.exit(2)
        key = "sha1:" + hashlib.sha1(data).hexdigest()
        if key in manifest:
            print("EXISTS\t" + manifest[key]["inbox"])
            return
        dest = uniq_dest(f"{today}_{slug(title)}.md")
        open(dest, "wb").write(data)
        src_label = f"text:{title}"
    else:
        if not args:
            print("usage: ingest_intake.py <file> | --text --title <t>", file=sys.stderr)
            sys.exit(2)
        src = os.path.expanduser(args[0])
        if not os.path.isfile(src):
            print(f"not a file: {src}", file=sys.stderr)
            sys.exit(2)
        data = open(src, "rb").read()
        key = "sha1:" + hashlib.sha1(data).hexdigest()
        if key in manifest:
            print("EXISTS\t" + manifest[key]["inbox"])
            return
        dest = uniq_dest(f"{today}_{os.path.basename(src)}")
        shutil.copy2(src, dest)
        src_label = src

    rel = os.path.relpath(dest, TASK_ROOT)
    manifest[key] = {"inbox": rel, "date": today, "source": src_label}
    save_manifest(manifest)
    append_log(f"- [{today}] ingest: {rel} ← {src_label}")
    print(rel)


if __name__ == "__main__":
    main()
