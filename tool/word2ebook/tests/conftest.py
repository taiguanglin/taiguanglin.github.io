"""Shared fixtures for word2ebook test suite."""

import sys
import os
from pathlib import Path
import pytest

# Ensure word2ebook package is importable
PACKAGE_DIR = Path(__file__).parent.parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from models.document_models import (
    Chapter, TOCItem, QAPair, SearchItem, ConversionConfig,
    QACountMetadata, QAPosition,
)
from config.settings import Settings, DEFAULT_SETTINGS


# ---------------------------------------------------------------------------
# Basic settings / config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_settings() -> Settings:
    return Settings(
        favicon_search_patterns=["favicon.ico", "favicon.png"],
    )


@pytest.fixture
def minimal_config(tmp_path) -> ConversionConfig:
    input_file = tmp_path / "test.docx"
    input_file.touch()
    return ConversionConfig(
        input_file=input_file,
        output_folder=tmp_path / "output",
    )


# ---------------------------------------------------------------------------
# Model fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_toc_item() -> TOCItem:
    return TOCItem(level=1, text="第一章", anchor="chapter-1")


@pytest.fixture
def sample_qa_pair() -> QAPair:
    return QAPair(
        question_id="question-abc123",
        answer_id="answer-abc123",
        questioner="學生甲",
        answerer="Tai師父",
        question_text="這是問題內容",
        answer_text="這是回答內容",
        time_info="2024-01-15 10:30",
    )


@pytest.fixture
def sample_search_item() -> SearchItem:
    return SearchItem(
        id="01.html-0",
        title="第一章標題",
        type="heading",
        content="第一章標題",
        context="第一章標題",
        url="01.html#heading-abc",
    )


@pytest.fixture
def simple_chapter(sample_qa_pair) -> Chapter:
    chapter = Chapter(
        title="第一章",
        filename="01.html",
        content="<h2>第一章</h2><p>內容</p>",
    )
    chapter.add_toc_item(1, "第一章", "chapter-1")
    chapter.add_qa_pair(sample_qa_pair)
    return chapter


@pytest.fixture
def chapter_list(simple_chapter) -> list:
    ch2 = Chapter(title="第二章", filename="02.html", content="<h2>第二章</h2>")
    return [simple_chapter, ch2]


# ---------------------------------------------------------------------------
# File-system fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def output_dir(tmp_path) -> Path:
    d = tmp_path / "ebook_output"
    d.mkdir()
    return d


@pytest.fixture
def config_yaml_path(tmp_path) -> Path:
    """Write a minimal config.yaml and return its path."""
    config_content = """
book_title:
  simplified: "測試書名（簡體）"
  traditional: "測試書名（繁體）"

i18n:
  navigation:
    home:
      simplified: "首页"
      traditional: "首頁"

generation:
  generate_traditional: true
  generate_simplified: true

favicon:
  enabled: true
  search_patterns:
    - favicon.ico
    - favicon.png
"""
    p = tmp_path / "config.yaml"
    p.write_text(config_content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# HTML snippet fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_html_with_qa() -> str:
    return """<html><body>
<h2 id="ch1">第一章</h2>
<div class="question" id="question-abc1">
  <div class="question-meta">
    <span class="questioner">學生甲</span>
    <span class="question-time">2024-01-15 10:30</span>
  </div>
  <div class="question-text">這是問題內容，需要有足夠長的文字才能被搜索索引。</div>
</div>
<div class="answer" id="answer-abc1">
  <div class="answer-meta">
    <span class="answerer">Tai師父</span>
  </div>
  <div class="answer-text">這是回答內容，包含詳細的解釋和說明文字。</div>
</div>
<p>這是一段普通段落，長度足夠進入搜索索引，包含一些示範文字。</p>
</body></html>"""
