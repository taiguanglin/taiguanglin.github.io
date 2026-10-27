#!/usr/bin/env python3
"""一鍵同步遠端、完整重建 wenda2_ebook 並提交、推送到遠端。

更新 Word/PDF 來源後，在 ``tool/word2ebook/`` 執行：

    python3 gen_all_and_push.py

依序執行（2026-10-26 起三段全跑——wenda2_ebook_word/ 中繼目錄已移除，
stage 1 直接寫 ``wenda2_ebook/``，後兩段就地轉成分類合併版）：

    git pull
        && ./gen_all.py                                    # stage 1：21 章底稿
        && (cd ../qa_split_ebook && python extract.py)     # stage 2：重抽 items.jsonl
        && (cd ../qa_split_ebook && python gen_classified.py)  # stage 3：分類合併版
        && git add :/
        && git commit -m "Rebuild wenda2_ebook from Word + PDFs"
        && git push

自訂 commit 訊息：

    python3 gen_all_and_push.py -m "更新 2025 年 11 月–2026 年 3 月 PDF"
"""

from __future__ import annotations

import argparse
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

# 兩段式重建的 stage 2/3（就地轉換）：
QA_SPLIT_DIR = REPO_ROOT / "tool" / "qa_split_ebook"
CLASSIFIED_STAGES = ("extract.py", "gen_classified.py")


def _ensure_venv() -> None:
    """若當前直譯器非 canonical venv，自動以該 venv python 重新執行自己。

    實作抽到共用 SoT ``utils/env_guard.py``（word2ebook 與 books2ebook
    共用同一套守門：pytest 保險絲、``W2E_SKIP_ENV_GUARD``、venv 不存在
    時的警告語意都在那裡）。保留本函數名稱與模組常數，維持既有測試介面。

    ⚠️ 只能在 ``main()`` 內呼叫，**不可**在 import 時執行：``os.execv`` 會把
    整個行程換掉——若在 pytest import/collection 期間觸發，會以測試進程的
    argv 完整重跑 pull → rebuild → commit → push（曾因此發生未授權 push）。
    """
    reexec_into_venv(__file__, venv_dir=_VENV_DIR, venv_python=VENV_PYTHON)

if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

from gen_all import main as gen_all_main  # noqa: E402
from utils.env_guard import reexec_into_venv  # noqa: E402


def _run_git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def run_classified_stages() -> int:
    """就地轉換（stage 2/3）：extract.py 重抽 items.jsonl，gen_classified.py
    把 stage 1 的 21 章底稿就地轉成 12 章分類合併版。

    本腳本已在鎖版 venv 中執行（``_ensure_venv``），直接以 ``sys.executable``
    （＝該 venv 的 python）跑子腳本，環境與規則完全一致。
    """
    for script in CLASSIFIED_STAGES:
        print(f"\n▶️  stage：{script}")
        proc = subprocess.run(
            [sys.executable, str(QA_SPLIT_DIR / script)],
            cwd=str(QA_SPLIT_DIR),
        )
        if proc.returncode != 0:
            print(f"❌ {script} 失敗（exit {proc.returncode}），略過 commit 與 push")
            return proc.returncode
    return 0


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
        description="git pull → 三段重建 wenda2_ebook（底稿 → extract → 分類合併）→ git add / commit / push",
    )
    parser.add_argument(
        "-m",
        "--message",
        default=DEFAULT_COMMIT_MESSAGE,
        help=f"git commit 訊息（預設：{DEFAULT_COMMIT_MESSAGE!r}）",
    )
    return parser


def main() -> int:
    # re-exec 只在此處（CLI 入口）發生；import 本模組必須完全無副作用。
    _ensure_venv()
    args = create_argument_parser().parse_args()

    print("🚀 gen_all_and_push — 同步 → 重建 → 提交 → 推送")
    print()

    sync_rc = sync_to_local()
    if sync_rc != 0:
        print("❌ 同步失敗，略過後續操作")
        return sync_rc

    build_rc = gen_all_main()
    if build_rc != 0:
        print("❌ 重建失敗（stage 1），略過後續操作")
        return build_rc

    classified_rc = run_classified_stages()
    if classified_rc != 0:
        print("❌ 分類合併（stage 2/3）失敗，略過 commit 與 push")
        return classified_rc

    return commit_and_push(args.message)


if __name__ == "__main__":
    sys.exit(main())
