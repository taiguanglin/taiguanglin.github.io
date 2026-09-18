"""gen_all_and_push.py 測試。"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from gen_all import REPO_ROOT, TOOL_DIR
from gen_all_and_push import (
    DEFAULT_COMMIT_MESSAGE,
    VENV_PYTHON,
    _ensure_venv,
    create_argument_parser,
    main,
    sync_to_local,
)


def test_gen_all_and_push_repo_layout():
    assert TOOL_DIR.name == "word2ebook"
    assert REPO_ROOT == TOOL_DIR.parent.parent


def test_default_commit_message():
    assert DEFAULT_COMMIT_MESSAGE == "Rebuild wenda2_ebook from Word + PDFs"


def test_custom_commit_message_arg():
    parser = create_argument_parser()
    args = parser.parse_args(["-m", "更新 QA 校稿"])
    assert args.message == "更新 QA 校稿"


def test_sync_to_local_runs_git_pull():
    with patch("gen_all_and_push._run_git") as run_git:
        run_git.return_value.returncode = 0
        run_git.return_value.stdout = "Already up to date."
        run_git.return_value.stderr = ""
        assert sync_to_local() == 0
        run_git.assert_called_once_with(["pull"], check=False)


def test_main_skips_build_when_pull_fails():
    with patch("sys.argv", ["gen_all_and_push.py"]):
        with patch("gen_all_and_push.sync_to_local", return_value=1) as sync:
            with patch("gen_all_and_push.gen_all_main") as gen_all:
                assert main() == 1
                sync.assert_called_once()
                gen_all.assert_not_called()


# ---------------------------------------------------------------------------
# re-exec 保險絲：import 本模組絕不能觸發 os.execv（歷史事故：pytest collection
# 期間 execv 把測試行程換成 gen_all_and_push.py，造成未授權 commit + push）。
# ---------------------------------------------------------------------------


def test_main_runs_ensure_venv(monkeypatch):
    """main() 的 CLI 入口負責呼叫 _ensure_venv（re-exec 語意保留）。"""
    calls = []
    monkeypatch.setattr("gen_all_and_push._ensure_venv", lambda: calls.append(1))
    monkeypatch.setattr(sys, "argv", ["gen_all_and_push.py"])
    monkeypatch.setattr("gen_all_and_push.sync_to_local", lambda: 1)
    assert main() == 1  # pull 失敗即返回，不會真的執行後續
    assert calls == [1]


def test_ensure_venv_never_execv_under_pytest(monkeypatch):
    """pytest 環境下（設了 PYTEST_CURRENT_TEST）_ensure_venv 必須是 no-op。"""
    monkeypatch.setattr(os, "execv", lambda *a, **k: pytest.fail("os.execv 在 pytest 下被呼叫"))
    assert os.environ.get("PYTEST_CURRENT_TEST")  # pytest 一定會設
    _ensure_venv()  # 即使當前 prefix ≠ venv，也不得 execv


def test_ensure_venv_execv_outside_pytest(monkeypatch, tmp_path):
    """非 pytest 環境才保留原本語意：prefix 不同 → 以 venv python 重跑自己。"""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    captured = {}

    def fake_execv(path, args):
        captured["path"] = path
        captured["args"] = args

    monkeypatch.setattr(os, "execv", fake_execv)
    import gen_all_and_push as gap
    monkeypatch.setattr(gap, "VENV_PYTHON", tmp_path / "bin" / "python")
    monkeypatch.setattr(gap, "_VENV_DIR", tmp_path)  # 必 ≠ sys.prefix
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "python").write_text("")  # 通過 exists() 檢查
    _ensure_venv()
    assert captured["path"] == str(tmp_path / "bin" / "python")
    assert captured["args"][0] == str(tmp_path / "bin" / "python")
    assert captured["args"][1] == str(Path(gap.__file__).resolve())


def test_ensure_venv_missing_venv_is_noop(monkeypatch, tmp_path, capsys):
    """venv 不存在時：印警告、不 re-exec（沿用當前直譯器）。"""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(os, "execv", lambda *a, **k: pytest.fail("不應 execv"))
    import gen_all_and_push as gap
    monkeypatch.setattr(gap, "VENV_PYTHON", tmp_path / "nope" / "bin" / "python")
    _ensure_venv()  # 不丟例外＝通過
    out = capsys.readouterr()
    assert "找不到 canonical venv" in out.err
