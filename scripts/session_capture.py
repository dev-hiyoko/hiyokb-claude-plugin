#!/usr/bin/env python3
"""SessionEnd フックで実行。会話ログ(transcript)の要点を inbox/sessions に退避する。

暗黙キャプチャの経路B（決定論・冪等・非破壊）。モデルが inline 記録を忘れても、
セッション終了時に「何を話したか」の生ログをここに必ず残す。後で `/hiyokb:ingest` で
ドシエ/KB へ蒸留する。原本(inbox)は不変・同期除外なので隠れた破壊的操作にはあたらない。

- config の capture.enabled / capture.session_capture が false なら何もしない。
- 退避先 inbox/sessions/<日付>_<session 短縮id>.md（session_id で冪等＝二重生成しない）。
- transcript からユーザー発話とアシスタント本文だけを抜き、ツール詳細は落として可読化。

入力(stdin): SessionEnd フックの JSON（transcript_path / session_id / cwd / reason）。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import capture_config  # noqa: E402

TASK_ROOT = os.path.expanduser("~/.hiyokb")
SESSIONS = os.path.join(TASK_ROOT, "inbox", "sessions")
LOG = os.path.join(TASK_ROOT, "log.md")

MAX_TURNS = 80           # 抜き出す発話の最大数（古い順に間引く）
MAX_CHARS_PER_TURN = 800  # 1 発話あたりの最大文字数


def _text_from_content(content):
    """transcript の message.content（str か block list）からテキストだけ抽出。"""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = []
    for blk in content:
        if isinstance(blk, dict) and blk.get("type") == "text":
            parts.append(str(blk.get("text", "")).strip())
    return "\n".join(p for p in parts if p).strip()


def read_turns(transcript_path):
    turns = []
    try:
        f = open(transcript_path, encoding="utf-8")
    except Exception:
        return turns
    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            txt = _text_from_content(msg.get("content"))
            if not txt:
                continue  # ツールのみのターン等は落とす
            if len(txt) > MAX_CHARS_PER_TURN:
                txt = txt[:MAX_CHARS_PER_TURN].rstrip() + " …"
            turns.append((role, txt))
    return turns


def append_log(line):
    new = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8") as fh:
        if new:
            fh.write("# log — ingest/query/lint の追記専用クロニクル\n\n")
        fh.write(line + "\n")


def main():
    cfg = capture_config()
    if not (cfg["enabled"] and cfg["session_capture"]):
        return
    if not os.path.isdir(TASK_ROOT):
        return  # ストア未初期化なら何もしない

    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    transcript_path = payload.get("transcript_path", "")
    session_id = str(payload.get("session_id", "") or "unknown")
    cwd = payload.get("cwd", "")
    reason = payload.get("reason", "")
    # 日付はフック入力から取れないため transcript の mtime を使う（Date 非決定を避ける）
    try:
        import time
        mt = os.path.getmtime(transcript_path) if transcript_path else None
        today = time.strftime("%Y-%m-%d", time.localtime(mt)) if mt else "undated"
    except Exception:
        today = "undated"

    if not transcript_path or not os.path.isfile(transcript_path):
        return
    turns = read_turns(transcript_path)
    if not turns:
        return  # 実質空のセッションは退避しない

    if len(turns) > MAX_TURNS:
        turns = turns[-MAX_TURNS:]  # 直近の文脈を優先して残す

    os.makedirs(SESSIONS, exist_ok=True)
    short = re.sub(r"[^0-9a-zA-Z]", "", session_id)[:8] or "session"
    dest = os.path.join(SESSIONS, f"{today}_{short}.md")

    lines = [
        "---",
        f"source: session:{session_id}",
        f"captured: {today}",
        f"cwd: {cwd}",
        f"end_reason: {reason}",
        "kind: session-capture",
        "sensitive: false  # 不明。社外秘を含むなら true に",
        "---",
        "",
        f"# セッション生ログ {today}（{short}）",
        "",
        "> 暗黙キャプチャ（経路B）による自動退避。未蒸留の生ログ。"
        "`/hiyokb:ingest` でドシエ/KB へ要約・振り分けする。",
        "",
    ]
    for role, txt in turns:
        who = "🧑 user" if role == "user" else "🤖 assistant"
        lines.append(f"**{who}**: {txt}")
        lines.append("")

    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")

    rel = os.path.relpath(dest, TASK_ROOT)
    append_log(f"- [{today}] session-capture: {rel}（{len(turns)} 発話）")
    print(f"hiyokb: セッションの生ログを {rel} に退避しました（/hiyokb:ingest で蒸留できます）")


if __name__ == "__main__":
    main()
