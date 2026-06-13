#!/usr/bin/env python3
"""~/.hiyokb/config.yaml の最小読み取り（PyYAML 非依存・統制された形式専用）。

参照範囲（GitHub owners）を取り出すための軽量パーサ。
"""
import os
import re

TASK_ROOT = os.path.expanduser("~/.hiyokb")
CONFIG = os.path.join(TASK_ROOT, "config.yaml")


def _text():
    try:
        return open(CONFIG, encoding="utf-8").read()
    except Exception:
        return ""


def _list_field(name, default):
    m = re.search(rf"\n{name}\s*:\s*(\[[^\]]*\])", _text())
    if not m:
        return default
    inner = m.group(1).strip()[1:-1]
    return [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]


def github_owners():
    """参照範囲。空なら @me 全体（owner 絞り込みなし）。"""
    m = re.search(r"owners\s*:\s*(\[[^\]]*\])", _text())
    if not m:
        return []
    inner = m.group(1).strip()[1:-1]
    return [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]


def enabled_sources():
    """取得するソース。未指定なら github のみ（MCP不要で動く最小構成）。"""
    return _list_field("enabled_sources", ["github"])


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
