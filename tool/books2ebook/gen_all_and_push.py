#!/usr/bin/env python3
"""一鍵同步遠端、完整重建 ebook 並提交、推送到遠端。

更新 books/ PDF 來源後，在 ``tool/books2ebook/`` 執行：

    python3 gen_all_and_push.py

任何直譯器皆可：非鎖版環境會自動切換到鎖版 venv
（``tool/word_audio_map2/.venv``；PyMuPDF 版本由 ``main.build()`` 守門）。

依序執行：

    git pull \\
        && ./gen_all.py \\
        && git add :/ \\
        && git commit -m "Rebuild ebook from books PDFs" \\
        && git push

自訂 commit 訊息：

    python3 gen_all_and_push.py -m "更新 08 壇經 PDF"
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import traceback
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOL_DIR.parent.parent

DEFAULT_COMMIT_MESSAGE = "Rebuild ebook from books PDFs"

if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))


def _load_env_guard():
    """以 spec 載入 word2ebook 的 env_guard（兩工具共用守門 SoT）。

    必須在 ``import main`` 之前就緒：main → extract → pymupdf 會在
    非鎖版直譯器上 import 失敗，re-exec 得先發生。
    """
    path = TOOL_DIR.parent / "word2ebook" / "utils" / "env_guard.py"
    spec = importlib.util.spec_from_file_location("_w2e_env_guard", path)
    if spec is None or spec.loader is None:
        raise ImportError("無法載入共用環境守門模組：%s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def rebuild() -> int:
    """執行 gen_all.py 的完整重建（books/ → ebook/）。"""
    import main  # noqa: E402  # 鎖版 venv 內才有 pymupdf/docx/opencc

    try:
        main.build()
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 1
    except Exception:
        print("❌ 重建失敗")
        traceback.print_exc()
        return 1
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
        description="git pull → 完整重建 ebook → git add / commit / push",
    )
    parser.add_argument(
        "-m",
        "--message",
        default=DEFAULT_COMMIT_MESSAGE,
        help=f"git commit 訊息（預設：{DEFAULT_COMMIT_MESSAGE!r}）",
    )
    return parser


def main_entry() -> int:
    args = create_argument_parser().parse_args()

    # CLI 入口先切換鎖版 venv（execv 成功時不返回，整個腳本於 venv 重跑；
    # pytest 保險絲與 W2E_SKIP_ENV_GUARD 見 env_guard）。
    _load_env_guard().reexec_into_venv(__file__)

    print("🚀 gen_all_and_push — 同步 → 重建 → 提交 → 推送")
    print()

    sync_rc = sync_to_local()
    if sync_rc != 0:
        print("❌ 同步失敗，略過後續操作")
        return sync_rc

    build_rc = rebuild()
    if build_rc != 0:
        print("❌ 重建失敗，略過 commit 與 push")
        return build_rc

    return commit_and_push(args.message)


if __name__ == "__main__":
    sys.exit(main_entry())
