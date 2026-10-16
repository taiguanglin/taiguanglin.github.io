"""utils/env_guard.py 測試——鎖版重建環境守門（re-exec 切換 + PyMuPDF pin）。

事故背景（2026-10-16 17a21bc）：以 /usr/bin/python3（PyMuPDF 1.26.5）
重建 ebook/，PDF 抽字空白漂移 → 段落 pid 與 search_index 一起變、
10 段已校對跟播靜默遺失。守門把這種「靜默漂移」變成「大聲失敗」。
"""

import os
import sys
from pathlib import Path

import pytest

from utils import env_guard
from utils.env_guard import (
    REQUIREMENTS_PATH,
    SKIP_ENV_VAR,
    ensure_locked_pymupdf,
    locked_pymupdf_pin,
    pymupdf_version_error,
    reexec_into_venv,
    under_locked_venv,
)


# ---------------------------------------------------------------------------
# pin 解析
# ---------------------------------------------------------------------------

def test_pin_from_real_requirements():
    """正式 repo 的鎖版 pin 應為 requirements.txt 內的 pymupdf==X.Y.Z。"""
    pin = locked_pymupdf_pin()
    assert pin == "1.28.2"
    assert REQUIREMENTS_PATH.exists()


def test_pin_missing_file_or_no_pin(tmp_path):
    assert locked_pymupdf_pin(tmp_path / "nope.txt") is None
    no_pin = tmp_path / "requirements.txt"
    no_pin.write_text("docx==1.1.0\n", encoding="utf-8")
    assert locked_pymupdf_pin(no_pin) is None
    with_pin = tmp_path / "requirements2.txt"
    with_pin.write_text(
        "# 註解\npymupdf==9.9.9  # 後綴註解\njieba==0.42\n",
        encoding="utf-8",
    )
    assert locked_pymupdf_pin(with_pin) == "9.9.9"


# ---------------------------------------------------------------------------
# 版本比對（純函式）
# ---------------------------------------------------------------------------

def test_version_error_message():
    error = pymupdf_version_error("1.26.5", "1.28.2")
    assert "1.26.5" in error and "1.28.2" in error
    assert "規則 13" in error
    assert SKIP_ENV_VAR in error
    assert pymupdf_version_error("1.28.2", "1.28.2") is None


def test_ensure_passes_when_version_matches_pin(tmp_path):
    actual = env_guard.current_pymupdf_version()
    if actual is None:
        pytest.skip("本環境沒有 PyMuPDF")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(f"pymupdf=={actual}\n", encoding="utf-8")
    ensure_locked_pymupdf(requirements)  # 不丟例外即通過


def test_ensure_fails_on_version_mismatch(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pymupdf==0.0.0\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        ensure_locked_pymupdf(requirements)
    assert "0.0.0" in str(exc_info.value)


def test_ensure_without_pin_only_warns(tmp_path, capsys):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("docx==1.1.0\n", encoding="utf-8")
    ensure_locked_pymupdf(requirements)  # 不丟例外
    assert "跳過版本檢查" in capsys.readouterr().err


def test_ensure_respects_skip_env(monkeypatch, tmp_path):
    monkeypatch.setenv(SKIP_ENV_VAR, "1")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pymupdf==0.0.0\n", encoding="utf-8")
    ensure_locked_pymupdf(requirements)  # 不丟例外


# ---------------------------------------------------------------------------
# re-exec 切換
# ---------------------------------------------------------------------------

def _no_pytest(monkeypatch):
    """模擬「非 pytest 執行」：env_guard 的保險絲靠 PYTEST_CURRENT_TEST。"""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)


def test_reexec_noop_under_pytest(monkeypatch, tmp_path):
    """pytest 環境（PYTEST_CURRENT_TEST 已設）一律不 execv（歷史事故守則）。"""
    assert os.environ.get("PYTEST_CURRENT_TEST")
    monkeypatch.setattr(os, "execv", lambda *a: pytest.fail("execv 在 pytest 下被呼叫"))
    monkeypatch.setattr(sys, "prefix", str(tmp_path))  # 非 venv 也不行
    reexec_into_venv(__file__, venv_dir=tmp_path, venv_python=tmp_path / "bin" / "python")


def test_reexec_noop_when_already_in_venv(monkeypatch, tmp_path):
    _no_pytest(monkeypatch)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "python").write_text("", encoding="utf-8")
    monkeypatch.setattr(os, "execv", lambda *a: pytest.fail("已在 venv 內不應 execv"))
    monkeypatch.setattr(sys, "prefix", str(tmp_path))  # sys.prefix == venv_dir
    reexec_into_venv(__file__, venv_dir=tmp_path)
    assert under_locked_venv(tmp_path) is True


def test_reexec_switches_when_outside_venv(monkeypatch, tmp_path):
    _no_pytest(monkeypatch)
    elsewhere = tmp_path / "current-prefix"
    monkeypatch.setattr(sys, "prefix", str(elsewhere))  # 目前不在 venv
    venv_dir = tmp_path / ".venv"
    (venv_dir / "bin").mkdir(parents=True)
    python = venv_dir / "bin" / "python"
    python.write_text("", encoding="utf-8")

    captured = {}
    monkeypatch.setattr(os, "execv", lambda path, args: captured.update(path=path, args=args))
    monkeypatch.setattr(sys, "argv", ["gen_all.py", "--flag", "x"])

    reexec_into_venv(__file__, venv_dir=venv_dir)
    assert captured["path"] == str(python)
    assert captured["args"] == [str(python), str(Path(__file__).resolve()), "--flag", "x"]


def test_reexec_missing_venv_warns_without_execv(monkeypatch, tmp_path, capsys):
    _no_pytest(monkeypatch)
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "elsewhere"))
    monkeypatch.setattr(os, "execv", lambda *a: pytest.fail("venv 不存在不應 execv"))
    reexec_into_venv(__file__, venv_dir=tmp_path)  # tmp_path 沒有 bin/python
    out = capsys.readouterr()
    assert "找不到 canonical venv" in out.err


def test_reexec_respects_skip_env(monkeypatch, tmp_path):
    _no_pytest(monkeypatch)
    monkeypatch.setenv(SKIP_ENV_VAR, "1")
    monkeypatch.setattr(os, "execv", lambda *a: pytest.fail("SKIP_ENV_VAR=1 不應 execv"))
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "elsewhere"))
    reexec_into_venv(__file__, venv_dir=tmp_path)
