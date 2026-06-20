#!/usr/bin/env python3
"""~/.hiyokb/config.yaml の最小読み取り（PyYAML 非依存・統制された形式専用）。

参照範囲（GitHub owners）を取り出すための軽量パーサ。
"""
import os
import re
import subprocess

TASK_ROOT = os.path.expanduser("~/.hiyokb")
CONFIG = os.path.join(TASK_ROOT, "config.yaml")


def _text():
    try:
        return open(CONFIG, encoding="utf-8").read()
    except Exception:
        return ""


def _list_field(name, default):
    # 行頭アンカー。先頭行のキーも拾う（旧 \n 前置だと 1 行目を取りこぼした）
    m = re.search(rf"(?m)^[ \t]*{name}\s*:\s*(\[[^\]]*\])", _text())
    if not m:
        return default
    inner = m.group(1).strip()[1:-1]
    return [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]


def github_owners():
    """参照範囲。空なら @me 全体（owner 絞り込みなし）。"""
    m = re.search(r"(?m)^[ \t]*owners\s*:\s*(\[[^\]]*\])", _text())
    if not m:
        return []
    inner = m.group(1).strip()[1:-1]
    return [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]


def enabled_sources():
    """取得するソース。未指定なら github のみ（MCP不要で動く最小構成）。"""
    return _list_field("enabled_sources", ["github"])


GITHUB_FILTERS = ("assigned", "created", "involves", "all")


BACKLOG_FILTERS = ("assigned", "all")
SLACK_FILTERS = ("mentions", "all")
DEFAULT_FILTER = {"github": "assigned", "backlog": "assigned", "slack": "mentions"}
VALID_FILTERS = {"github": GITHUB_FILTERS, "backlog": BACKLOG_FILTERS, "slack": SLACK_FILTERS}


def _indented_block(text, header_re):
    """`header:`（値なし）の直後に続く、より深くインデントされた行群を返す。"""
    m = re.search(header_re, text)
    if not m:
        return ""
    base = len(re.match(r"[ \t]*", m.group(0)).group(0))
    out = []
    for ln in text[m.end():].splitlines():
        if ln.strip() == "":
            out.append(ln)
            continue
        if len(ln) - len(ln.lstrip()) <= base:
            break
        out.append(ln)
    return "\n".join(out)


def source_scopes(source):
    """`sources.<source>.scopes` を読み、取得範囲のスコープ一覧を返す（ソース非依存の汎用）。

    1 行 1 スコープの統制形式（github/backlog/slack 共通）:

        sources:
          <source>:
            scopes:
              - <target> : <filter>   # 例 github: me/web : created / backlog: APLUS : all
              - <target>              # filter 省略時はソース既定

    target の意味はソース依存（github=owner|owner/repo, backlog=projectKey, slack=channel）。
    filter は VALID_FILTERS[source] に正規化（不正値・省略は DEFAULT_FILTER[source]）。
    未設定なら空リスト。
    """
    sources_block = _indented_block(_text(), r"(?m)^[ \t]*sources\s*:\s*$")
    src_block = _indented_block(sources_block, rf"(?m)^[ \t]*{re.escape(source)}\s*:\s*$")
    scopes_block = _indented_block(src_block, r"(?m)^[ \t]*scopes\s*:\s*$")
    if not scopes_block:
        return []
    valid = VALID_FILTERS.get(source)
    default = DEFAULT_FILTER.get(source, "assigned")
    out = []
    for line in scopes_block.splitlines():
        ls = line.strip()
        if ls == "":
            continue
        if not ls.startswith("-"):
            break  # リストの終端
        body = ls[1:].strip()
        ci = body.find(" #")            # インラインコメント除去
        if ci != -1:
            body = body[:ci].strip()
        if not body:
            continue
        if ":" in body:
            tgt, _, filt = body.partition(":")
            tgt, filt = tgt.strip().strip("\"'"), filt.strip().lower()
        else:
            tgt, filt = body.strip("\"'"), default
        if valid and filt not in valid:
            filt = default
        if tgt:
            out.append({"target": tgt, "filter": filt})
    return out


def github_scopes():
    """GitHub の取得範囲スコープ（`sources.github.scopes`）。source_scopes の薄いラッパ。

    target は `/` を含めば repo 単位、無ければ owner 単位。filter は GITHUB_FILTERS
    （assigned/created/involves/all）。未設定なら空＝呼び出し側は owners を assigned で取得。
    """
    return source_scopes("github")


def capture_config():
    """暗黙キャプチャ（働きながら自動で貯める）の設定。

    config.yaml の `capture:` ブロックを読む。未設定なら暗黙キャプチャを有効
    （session_capture は inbox への非破壊退避、auto_scope は推奨の dossier）にする。
    auto_scope は自動書き込みの上限: inbox | dossier | kb。
    """
    defaults = {"enabled": True, "inline_recording": True,
                "session_capture": True, "auto_scope": "dossier"}
    txt = _text()
    m = re.search(r"(?m)^capture\s*:\s*$\n((?:[ \t]+\S.*\n?)+)", txt)
    if not m:
        return defaults
    block = m.group(1)

    def _b(key, d):
        mm = re.search(rf"(?m)^[ \t]+{key}\s*:\s*(\w+)", block)
        return (mm.group(1).lower() == "true") if mm else d

    def _s(key, d):
        mm = re.search(rf"(?m)^[ \t]+{key}\s*:\s*([A-Za-z_]+)", block)
        return mm.group(1).lower() if mm else d

    scope = _s("auto_scope", "dossier")
    if scope not in ("inbox", "dossier", "kb"):
        scope = "dossier"
    return {
        "enabled": _b("enabled", True),
        "inline_recording": _b("inline_recording", True),
        "session_capture": _b("session_capture", True),
        "auto_scope": scope,
    }


# ===== プロジェクト境界（cwd=リポジトリ → hiyokb プロジェクトの束縛） =====
# config の `project_map:` に「<source> <target> : <project>」を1行1件で持つ（起動時の質問で追記）。
#   project_map:
#     - github me/drovyu : drovyu
#     - github ai2-jp/a-plusplus : a-plusplus
#     - backlog DRV : drovyu
#     - slack #drovyu : drovyu

def project_map():
    """project_map ブロックを [{source, target, project}] にして返す。"""
    block = _indented_block(_text(), r"(?m)^[ \t]*project_map\s*:\s*$")
    out = []
    for line in block.splitlines():
        ls = line.strip()
        if ls == "":
            continue
        if not ls.startswith("-"):
            break
        body = ls[1:].strip()
        ci = body.find(" #")
        if ci != -1:
            body = body[:ci].strip()
        if ":" not in body:
            continue
        left, _, project = body.partition(":")
        project = project.strip().strip("\"'")
        parts = left.split(None, 1)
        if len(parts) != 2 or not project:
            continue
        out.append({"source": parts[0].strip().lower(),
                    "target": parts[1].strip().strip("\"'"), "project": project})
    return out


def _route(source, target):
    """source/target をプロジェクトに解決。github は repo 完全一致 → owner 一致の順。"""
    target = (target or "").lower()
    owner_hit = None
    for e in project_map():
        if e["source"] != source:
            continue
        t = e["target"].lower()
        if t == target:
            return e["project"]
        if source == "github" and "/" not in t and target.split("/", 1)[0] == t:
            owner_hit = e["project"]
    return owner_hit


def route_task(task_id):
    """タスク id（gh:owner/repo#n / bl:KEY-n / slack:ch-ts）からプロジェクトを解決（無ければ ""）。"""
    if not task_id:
        return ""
    if task_id.startswith("gh:"):
        return _route("github", task_id[3:].split("#", 1)[0]) or ""
    if task_id.startswith("bl:"):
        key = task_id[3:]
        return _route("backlog", key.rsplit("-", 1)[0] if "-" in key else key) or ""
    if task_id.startswith("slack:"):
        return _route("slack", task_id[6:].rsplit("-", 1)[0]) or ""
    return ""


def current_repo(cwd):
    """cwd の git remote(origin) から owner/repo を取り出す（無ければ None）。"""
    if not cwd:
        return None
    try:
        out = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=5)
        url = out.stdout.strip()
    except Exception:
        return None
    m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def current_project(cwd):
    """cwd → (repo, project)。repo 未取得なら (None, None)、未束縛なら (repo, None)。"""
    repo = current_repo(cwd)
    if not repo:
        return None, None
    return repo, _route("github", repo)


def add_binding(source, target, project):
    """project_map に束縛を1件追記する（hiyokb 唯一の config 書き込み＝「聞いて記憶」）。"""
    txt = _text()
    line = f"  - {source} {target} : {project}"
    if re.search(r"(?m)^[ \t]*project_map\s*:\s*$", txt):
        new = re.sub(r"(?m)^([ \t]*project_map\s*:[ \t]*)$", r"\1\n" + line, txt, count=1)
    else:
        new = txt.rstrip() + "\n\nproject_map:\n" + line + "\n"
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(new)
    return line.strip()
