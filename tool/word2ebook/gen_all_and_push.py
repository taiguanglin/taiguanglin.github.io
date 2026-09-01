#!/usr/bin/env python3
"""一鍵同步遠端、完整重建 wenda2_ebook 並提交、推送到遠端。

更新 Word/PDF 來源後，在 ``tool/word2ebook/`` 執行：

    python3 gen_all_and_push.py

依序執行：

    git pull \\
        && ./gen_all.py \\
        && git add :/ \\
        && git commit -m "Rebuild wenda2_ebook from Word + PDFs" \\
        && git push

自訂 commit 訊息：

    python3 gen_all_and_push.py -m "更新 2025 年 11 月–2026 年 3 月 PDF"
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# 專案全域唯一裝有 docx / opencc / slugify / yaml / jieba / pymupdf 的環境。
# 若目前直譯器不是這個 venv，就自動 re-exec 一次，讓用戶無論用
# `python3 gen_all_and_push.py` 或 `./gen_all_and_push.py` 都能直接跑。
_VENV_DIR = Path(__file__).resolve().parent.parent / "word_audio_map2" / ".venv"
VENV_PYTHON = _VENV_DIR / "bin" / "python"

TOOL_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOL_DIR.parent.parent

DEFAULT_COMMIT_MESSAGE = "Rebuild wenda2_ebook from Word + PDFs"


def _ensure_venv() -> None:
    """若當前直譯器非 canonical venv，自動以該 venv python 重新執行自己。

    venv 的 ``bin/python`` 是 symlink 指向 base python，因此不能用 realpath 比對
    執行檔；改用 ``sys.prefix``（venv 內會指到 .venv 目錄本身）來判斷。
    """
    venv_prefix = _VENV_DIR.resolve()
    current_prefix = Path(sys.prefix).resolve()
    if VENV_PYTHON.exists():
        if current_prefix != venv_prefix:
            os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    else:
        print(
            f"⚠️  找不到 canonical venv：{VENV_PYTHON}\n"
            "   將沿用當前直譯器執行；若缺少 docx 等相依套件，請先建立該 venv。",
            file=sys.stderr,
        )


_ensure_venv()

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


def sync_to_local() -> int:
    """從遠端拉取最新變更到本地（git pull）。"""
    print("🔄 同步遠端變更到本地（git pull）")
    print(f"   {REPO_ROOT}")
    print()

    pull = _run_git(["pull"], check=False)
    if pull.returncode != 0:
        print("❌ git pull 失敗")
        if pull.stdout:
            print(pull.stdout.strip())
        if pull.stderr:
            print(pull.stderr.strip())
        return pull.returncode
    if pull.stdout:
        print(pull.stdout.strip())
    if pull.stderr:
        print(pull.stderr.strip())

    print("✅ 本地已與遠端同步")
    return 0


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
        description="git pull → 完整重建 wenda2_ebook → git add / commit / push",
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

    print("🚀 gen_all_and_push — 同步 → 重建 → 提交 → 推送")
    print()

    sync_rc = sync_to_local()
    if sync_rc != 0:
        print("❌ 同步失敗，略過後續操作")
        return sync_rc

    build_rc = gen_all_main()
    if build_rc != 0:
        print("❌ 重建失敗，略過 commit 與 push")
        return build_rc

    return commit_and_push(args.message)


if __name__ == "__main__":
    sys.exit(main())
