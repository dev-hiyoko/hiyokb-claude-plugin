#!/usr/bin/env python3
"""リポジトリ等を hiyokb プロジェクトに割り当てて記憶する（「どのリポジトリ＝どのプロジェクトか」）。

プロジェクト未設定のリポジトリで起動したとき、スキルがユーザーに「どのプロジェクト？」と確認し、
答えをここで config の project_map に追記する。これで次回からは自動でそのプロジェクトに判別される。

使い方:
  project_bind.py <source> <target> <project>   # 例: project_bind.py github me/drovyu drovyu
  project_bind.py --list                          # 登録済みの割り当てとプロジェクト一覧を表示
  project_bind.py --whoami [<cwd>]                # 今いるリポジトリと、その所属プロジェクトを表示
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _config  # noqa: E402

TASK_ROOT = _config.TASK_ROOT


def known_projects():
    return sorted(os.path.basename(os.path.dirname(p))
                  for p in glob.glob(os.path.join(TASK_ROOT, "projects", "*", "tasks")))


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        sys.exit(2)

    if args[0] == "--list":
        m = _config.project_map()
        print("## リポジトリ→プロジェクトの割り当て")
        for e in m or []:
            print(f"- {e['source']} {e['target']} → {e['project']}")
        if not m:
            print("- （まだ無し）")
        print("## 登録済みプロジェクト")
        print(", ".join(known_projects()) or "（まだ無し）")
        return

    if args[0] == "--whoami":
        cwd = args[1] if len(args) > 1 else os.getcwd()
        repo, project = _config.current_project(cwd)
        print(f"repo: {repo or '(git remote なし)'}")
        print(f"project: {project or '(未設定)'}")
        if repo and not project:
            print(f"このリポジトリはプロジェクト未設定。登録するには: project_bind.py github {repo} <プロジェクト名>")
        return

    if len(args) < 3:
        print("usage: project_bind.py <source> <target> <project>", file=sys.stderr)
        sys.exit(2)
    source, target, project = args[0].lower(), args[1], args[2]
    if source not in ("github", "backlog", "slack"):
        print(f"source は github/backlog/slack のいずれか: {source}", file=sys.stderr)
        sys.exit(2)
    if not os.path.exists(_config.CONFIG):
        os.makedirs(TASK_ROOT, exist_ok=True)
        open(_config.CONFIG, "w", encoding="utf-8").write("enabled_sources: [github]\n")
    line = _config.add_binding(source, target, project)
    # プロジェクトのディレクトリも用意（無ければ）
    os.makedirs(os.path.join(TASK_ROOT, "projects", project, "tasks"), exist_ok=True)
    os.makedirs(os.path.join(TASK_ROOT, "projects", project, "kb"), exist_ok=True)
    print(f"プロジェクトに割り当てて登録しました: {line}")


if __name__ == "__main__":
    main()
