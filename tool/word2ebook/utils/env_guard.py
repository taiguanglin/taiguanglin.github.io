"""鎖版重建環境守門 —— word2ebook 與 books2ebook 共用的單一真相來源。

為什麼需要這個模組
--------------------
PyMuPDF 的版本會改變 PDF 抽字的斷行與空白（books2ebook ``parsers._join()``
依賴抽取片段的邊界空白判斷）。換版重建會讓 ``ebook/*.html`` 的文字、
段落 pid（= md5(文字+段序)）與 ``search_index*.json`` 一起漂移——
2026-10-16 的 17a21bc 就是以 ``/usr/bin/python3``（PyMuPDF 1.26.5）重建
``ebook/``，造成 36 段空白漂移、10 段已校對跟播靜默遺失、7 條契約測試變紅
（詳見 repo 根目錄 ``search_index_rebuild_research.md``）。

鎖版環境：``tool/word_audio_map2/.venv``（``requirements.txt`` 全 ``==``）。
root AGENTS.md「依賴已鎖版」要求重建電子書一律用它。

兩道防線（入口腳本請兩者都用）
--------------------------------
1. :func:`reexec_into_venv` —— 目前直譯器不是鎖版 venv 時，以 ``os.execv``
   原地切換（語意沿用 word2ebook ``gen_all_and_push.py`` 先前的
   ``_ensure_venv``）。⚠️ 只能在 CLI 入口（``main()`` / ``__main__``）呼叫，
   **不可**在 import 時執行：pytest collection 期間觸發 execv 曾把測試行程
   換成 push 腳本，造成未授權 commit + push。
2. :func:`ensure_locked_pymupdf` —— 比對 PyMuPDF 版本與 ``requirements.txt``
   的 pin，不符即 ``SystemExit(1)``：把「靜默漂移」變成「大聲失敗」。

保險絲
------
- 偵測 pytest（``PYTEST_CURRENT_TEST``）時一律不 re-exec。
- ``W2E_SKIP_ENV_GUARD=1`` 跳過兩道防線（升級鎖版環境時的暫時逃生口）。
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_DIR = REPO_ROOT / "tool" / "word_audio_map2" / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"
REQUIREMENTS_PATH = REPO_ROOT / "tool" / "word_audio_map2" / "requirements.txt"
SKIP_ENV_VAR = "W2E_SKIP_ENV_GUARD"


def env_guard_disabled() -> bool:
    """``W2E_SKIP_ENV_GUARD=1`` 時停用兩道防線。"""
    return os.environ.get(SKIP_ENV_VAR, "") == "1"


def under_locked_venv(venv_dir: Path = VENV_DIR) -> bool:
    """目前是否在鎖版 venv 內。

    venv 的 ``bin/python`` 是 symlink 指向 base python，不能比對執行檔；
    改用 ``sys.prefix``（venv 內會指到 ``.venv`` 目錄本身）。
    """
    try:
        return Path(sys.prefix).resolve() == Path(venv_dir).resolve()
    except OSError:
        return False


def locked_pymupdf_pin(requirements_path: Path = REQUIREMENTS_PATH) -> Optional[str]:
    """從 requirements.txt 讀 ``pymupdf==X.Y.Z`` 的 pin；找不到回 None。"""
    if not requirements_path.exists():
        return None
    match = re.search(
        r"^\s*pymupdf\s*==\s*([^\s#]+)",
        requirements_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return match.group(1) if match else None


def current_pymupdf_version() -> Optional[str]:
    """偵測目前直譯器的 PyMuPDF 版本；未安裝回 None。"""
    try:
        import pymupdf  # noqa: F401
        return getattr(pymupdf, "__version__", None)
    except ImportError:
        pass
    try:
        import fitz  # 舊名稱（PyMuPDF ≤1.28 的棄用別名）
        return getattr(fitz, "__version__", None)
    except ImportError:
        return None


def pymupdf_version_error(
    actual: str, pin: str, venv_python: Path = VENV_PYTHON
) -> Optional[str]:
    """版本不符時回傳錯誤訊息（純函式，供測試）；相符回 None。"""
    if actual == pin:
        return None
    return (
        f"PyMuPDF 版本不符：目前 {actual}，鎖版 pin 為 {pin}。\n"
        "   版本差異會改變 PDF 抽字的斷行與空白 → 段落 pid 與 search_index\n"
        "   一起漂移，已校對講次的段落跟播會靜默失效（root AGENTS.md 規則 13）。\n"
        f"   請改用鎖版環境重建：{venv_python} <tool>/gen_all.py\n"
        f"   （暫時跳過：{SKIP_ENV_VAR}=1）"
    )


def reexec_into_venv(
    script_path, venv_dir: Path = VENV_DIR, venv_python: Optional[Path] = None
) -> None:
    """非鎖版環境時，以鎖版 venv 的 python 重跑 ``script_path``。

    - 已在鎖版 venv 內 / pytest / W2E_SKIP_ENV_GUARD=1 → no-op。
    - venv 不存在 → 印警告、沿用當前直譯器（之後由
      :func:`ensure_locked_pymupdf` 或 import 失敗接手擋下）。
    - ``os.execv`` 成功時不返回（整個行程被替換）。
    """
    if env_guard_disabled():
        return
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if under_locked_venv(venv_dir):
        return
    python = Path(venv_python) if venv_python else Path(venv_dir) / "bin" / "python"
    if not python.exists():
        print(
            f"⚠️  找不到 canonical venv：{python}\n"
            "   將沿用當前直譯器執行；若缺少 docx 等相依套件，請先建立該 venv。",
            file=sys.stderr,
        )
        return
    print(f"🔄 非 venv 執行環境，切換到鎖版 venv：{python}", flush=True)
    os.execv(str(python), [str(python), str(Path(script_path).resolve()), *sys.argv[1:]])


def ensure_locked_pymupdf(requirements_path: Path = REQUIREMENTS_PATH) -> None:
    """PyMuPDF 版本與鎖版 pin 不符時 ``SystemExit(1)``。

    沒有 pin（找不到 requirements.txt 或其中無 pymupdf 行）或偵測不到
    PyMuPDF 時只警告不擋（後者緊接著的 PDF 解析 import 自然會失敗）。
    """
    if env_guard_disabled():
        return
    pin = locked_pymupdf_pin(requirements_path)
    if pin is None:
        print(
            f"⚠️  {requirements_path} 沒有 pymupdf 的 pin，跳過版本檢查。",
            file=sys.stderr,
        )
        return
    actual = current_pymupdf_version()
    if actual is None:
        print(
            f"⚠️  無法偵測 PyMuPDF 版本（未安裝？）；鎖版 pin 為 {pin}。",
            file=sys.stderr,
        )
        return
    error = pymupdf_version_error(actual, pin)
    if error:
        raise SystemExit("❌ " + error)
