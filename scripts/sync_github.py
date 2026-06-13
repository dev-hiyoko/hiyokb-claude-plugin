#!/usr/bin/env python3
"""GitHub から open issue を取得し ~/.hiyokb/sources/github.md を更新する。

取得範囲は config の `sources.github.scopes` でプロジェクト（owner / owner/repo）単位に指定できる
（業務 repo は assigned、個人 repo は created/all 等）。scopes 未設定なら従来どおり owners を
assigned で取得する（後方互換）。

- 成功時: 取得結果でスナップショットを上書き（stale: false）。
- 失敗時（認証切れ/レート制限/オフライン）: 前回スナップショットを保持し stale: true を立てる
  （部分失敗のソース単位隔離）。他ソースや index 再生成を止めないため exit 0 で返す。
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _config  # noqa: E402

TASK_ROOT = os.path.expanduser("~/.hiyokb")
SRC_DIR = os.path.join(TASK_ROOT, "sources")
SRC_FILE = os.path.join(SRC_DIR, "github.md")
LIMIT = 200  # 取得上限。到達したら切り捨ての可能性を警告する


def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def read_existing_tasks():
    if not os.path.exists(SRC_FILE):
        return []
    try:
        txt = open(SRC_FILE, encoding="utf-8").read()
        m = re.search(r"```json\n(.*?)\n```", txt, re.S)
        if m:
            return json.loads(m.group(1)).get("tasks", [])
    except Exception:
        pass
    return []


def write_snapshot(tasks, stale, error=None):
    os.makedirs(SRC_DIR, exist_ok=True)
    data = {"source": "github", "synced": now_iso(), "stale": stale, "tasks": tasks}
    if error:
        data["error"] = error
    status = "STALE（前回値を表示中・取得失敗）" if stale else "ok"
    head = [
        "# github source snapshot",
        "",
        f"- synced: {data['synced']}",
        f"- status: {status}",
    ]
    if error:
        head.append(f"- error: {error}")
    head += [f"- count: {len(tasks)}", "", "```json",
             json.dumps(data, ensure_ascii=False, indent=2), "```", ""]
    open(SRC_FILE, "w", encoding="utf-8").write("\n".join(head))


FILTER_FLAG = {"assigned": "--assignee=@me", "created": "--author=@me",
               "involves": "--involves=@me", "all": None}


def _search(target=None, owners=None, filt="assigned"):
    """gh search issues を1回実行し、生 items を返す。

    target 指定時は owner/repo 単位（`/` 有無で自動判別）。owners 指定時は複数 owner を
    1クエリに束ねる（従来挙動）。filt に応じて assignee/author/involves 修飾を付ける
    （all は actor 修飾なし＝その範囲の open issue 全部）。
    """
    cmd = ["gh", "search", "issues", "--state=open",
           "--json", "number,title,url,repository,labels,updatedAt", "--limit", str(LIMIT)]
    flag = FILTER_FLAG.get(filt)
    if flag:
        cmd.append(flag)
    if target:
        cmd.append(f"--repo={target}" if "/" in target else f"--owner={target}")
    for o in (owners or []):
        cmd.append(f"--owner={o}")
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "gh search failed")
    items = json.loads(out.stdout or "[]")
    if len(items) >= LIMIT:
        where = target or (",".join(owners) if owners else "@me")
        print(f"github: ⚠️ 取得が上限 {LIMIT} 件に達しました（範囲 {where} / {filt}）。"
              f"切り捨ての可能性があります（scope を repo 単位に絞るか上限調整を検討）", file=sys.stderr)
    return items


def _normalize(items, filt):
    tasks = {}
    for it in items:
        repo = (it.get("repository") or {}).get("nameWithOwner", "")
        num = it.get("number")
        tid = f"gh:{repo}#{num}"
        tasks[tid] = {
            "id": tid,
            "source": "github",
            "source_ref": it.get("url", ""),
            "title": it.get("title", ""),
            "status": "todo",
            "due": None,
            "assignee": "me" if filt == "assigned" else None,
            "scope": filt,
            "labels": [l.get("name") for l in (it.get("labels") or [])],
            "updated": (it.get("updatedAt") or "")[:10],
        }
    return tasks


def fetch():
    scopes = _config.github_scopes()          # プロジェクト単位の取得範囲（あれば優先）
    merged = {}
    if scopes:
        for sc in scopes:                      # スコープごとに1クエリ。id でマージ（重複除去）
            items = _search(target=sc["target"], filt=sc["filter"])
            for tid, t in _normalize(items, sc["filter"]).items():
                # 既出が assigned で後勝ちが弱い修飾なら上書きしない（出自の格上げを優先）
                if tid not in merged or merged[tid].get("scope") != "assigned":
                    merged[tid] = t
    else:                                      # 後方互換: owners を assigned で（空なら @me 全体）
        owners = _config.github_owners()
        items = _search(owners=owners, filt="assigned")
        merged = _normalize(items, "assigned")
    return list(merged.values())


def main():
    if "github" not in _config.enabled_sources():
        print("github: 無効（config の enabled_sources に含まれていません）")
        sys.exit(0)
    try:
        tasks = fetch()
        write_snapshot(tasks, stale=False)
        print(f"github: {len(tasks)} 件を同期しました")
    except Exception as e:
        existing = read_existing_tasks()
        write_snapshot(existing, stale=True, error=str(e))
        print(f"github: 同期失敗（{e}）。前回の {len(existing)} 件を stale として保持します",
              file=sys.stderr)
    # per-source isolation: 常に 0 で返し、他ソース/index 再マージを止めない
    sys.exit(0)


if __name__ == "__main__":
    main()
