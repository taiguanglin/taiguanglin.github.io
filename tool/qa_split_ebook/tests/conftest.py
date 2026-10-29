"""Shared fixtures for qa_split_ebook test suite.

The two pipeline stages are plain scripts at the tool root:

* ``extract.py``       — stage 2, reads the stage-1 draft's PDF chapters
* ``gen_classified.py`` — stage 3, merges Word + PDF entries into the
  published 12-chapter book

Both resolve paths from ``ROOT`` at import time, so importing them is
side-effect free and safe from tests.
"""

import sys
from pathlib import Path

import pytest

TOOL_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = TOOL_DIR.parents[1]
WORD2EBOOK_DIR = TOOL_DIR.parent / "word2ebook"

# word2ebook 也要在路徑上——測試會用到它的 utils.image_markup.encode_webp
# 來重算來源圖片的 WebP 雜湊做對帳（gen_classified 自己也會把它加進去，
# 但顯式列出避免依賴 import 副作用）。
for _p in (str(TOOL_DIR), str(WORD2EBOOK_DIR), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture
def repo_root() -> Path:
    """Repository root (contains 問答錄2/ and wenda2_ebook/)."""
    return REPO_ROOT


@pytest.fixture
def ebook_dir(repo_root) -> Path:
    """Published ebook output directory."""
    return repo_root / "wenda2_ebook"


@pytest.fixture
def source_dir(repo_root) -> Path:
    """問答錄2/ source directory (Word + monthly PDFs)."""
    return repo_root / "問答錄2"
