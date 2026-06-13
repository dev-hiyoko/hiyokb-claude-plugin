#!/usr/bin/env python3
"""~/.task/config.yaml の最小読み取り（PyYAML 非依存・統制された形式専用）。

参照範囲（GitHub owners）を取り出すための軽量パーサ。
"""
import os
import re

TASK_ROOT = os.path.expanduser("~/.task")
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
