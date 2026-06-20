#!/usr/bin/env python3
"""一鍵完整重建 wenda2_ebook 並提交、推送到遠端。

修正 ``qa/`` 文字稿後，在 ``tool/word2ebook/`` 執行：

    python3 gen_all_and_push.py

等同於：

    ./gen_all.py \\
        && git add :/ \\
        && git commit -m "New txt changes to new wenda2ebook" \\
        && git push

自訂 commit 訊息：

    python3 gen_all_and_push.py -m "更新 2026 年 3 月 QA 校稿"
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOL_DIR.parent.parent

DEFAULT_COMMIT_MESSAGE = "New txt changes to new wenda2ebook"

if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

from gen_all import main as gen_all_main  # noqa: E402


def _run_git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def has_staged_or_unstaged_changes() -> bool:
    result = _run_git(["status", "--porcelain"], check=True)
    return bool(result.stdout.strip())


def commit_and_push(message: str) -> int:
    print()
    print("📦 準備提交並推送（repo 根目錄）")
    print(f"   {REPO_ROOT}")
    print()

    stage = _run_git(["add", ":/"], check=False)
    if stage.returncode != 0:
        print("❌ git add 失敗")
        if stage.stderr:
            print(stage.stderr.strip())
        return stage.returncode

    if not has_staged_or_unstaged_changes():
        print("ℹ️  沒有變更可提交，略過 commit 與 push")
        return 0

    commit = _run_git(["commit", "-m", message], check=False)
    if commit.returncode != 0:
        print("❌ git commit 失敗")
        if commit.stdout:
            print(commit.stdout.strip())
        if commit.stderr:
            print(commit.stderr.strip())
        return commit.returncode
    if commit.stdout:
        print(commit.stdout.strip())

    push = _run_git(["push"], check=False)
    if push.returncode != 0:
        print("❌ git push 失敗")
        if push.stdout:
            print(push.stdout.strip())
        if push.stderr:
            print(push.stderr.strip())
        return push.returncode
    if push.stdout:
        print(push.stdout.strip())
    if push.stderr:
        print(push.stderr.strip())

    print("✅ 已提交並推送到遠端")
    return 0


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="完整重建 wenda2_ebook 後，git add / commit / push",
    )
    parser.add_argument(
        "-m",
        "--message",
        default=DEFAULT_COMMIT_MESSAGE,
        help=f"git commit 訊息（預設：{DEFAULT_COMMIT_MESSAGE!r}）",
    )
    return parser


def main() -> int:
    args = create_argument_parser().parse_args()

    print("🚀 gen_all_and_push — 重建 → 提交 → 推送")
    print()

    build_rc = gen_all_main()
    if build_rc != 0:
        print("❌ 重建失敗，略過 git 操作")
        return build_rc

    return commit_and_push(args.message)


if __name__ == "__main__":
    sys.exit(main())
