"""Shared fixtures for the books2ebook test suite."""

import sys
from pathlib import Path

import pytest

# Make the tool modules importable (config / para_audio_map / …)
TOOL_DIR = Path(__file__).resolve().parent.parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

REPO_ROOT = TOOL_DIR.parent.parent
EBOOK_DIR = REPO_ROOT / "ebook"
AUDIO_MAP3_DIR = REPO_ROOT / "audio_map3"


def pytest_configure(config):
    config.addinivalue_line("markers", "artifacts: 需要已建置的 ebook/ 與 audio_map3/ 產物")


@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT


@pytest.fixture(scope="session")
def ebook_dir():
    """已建置的電子書輸出目錄；沒有建置產物時跳過（不是測試失敗）。"""
    if not (EBOOK_DIR / "index.html").exists():
        pytest.skip("沒有 ebook/ 建置產物；請先 cd tool/books2ebook && python3 gen_all.py")
    return EBOOK_DIR


@pytest.fixture(scope="session")
def audio_map3_dir():
    if not AUDIO_MAP3_DIR.exists():
        pytest.skip("沒有 audio_map3/ 對齊資料")
    return AUDIO_MAP3_DIR


def book_html(ebook_dir, book, trad=False):
    name = "%s%s.html" % (book, "_trad" if trad else "")
    path = ebook_dir / name
    if not path.exists():
        pytest.skip("缺少 %s（先重建 ebook/）" % name)
    return path.read_text(encoding="utf-8")