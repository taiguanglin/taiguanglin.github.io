"""Tests for generators/search_generator.py"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.document_models import Chapter, SearchItem
from generators.search_generator import SearchIndexGenerator
from utils.file_utils import FileManager
from config.settings import Settings, Constants


@pytest.fixture
def settings():
    return Settings(
        search_context_length=80,
        search_min_paragraph_length=20,
        favicon_search_patterns=["favicon.ico"],
    )


@pytest.fixture
def output_with_html(tmp_path, settings):
    """Set up output directory with pre-generated HTML files."""
    out = tmp_path / "output"
    out.mkdir()
    for sub in ["assets/css", "assets/js", "assets/images"]:
        (out / sub).mkdir(parents=True)

    # Write minimal chapter HTML files
    html = """<html><body>
<h2>第一章</h2>
<div class="question">
  <div class="question-meta">
    <span class="questioner">學生甲</span>
    <span class="question-time">2024-01-15 10:30</span>
  </div>
  <div class="question-text">這是問題的內容文字，用於測試搜索索引生成功能。</div>
</div>
<div class="answer">
  <div class="answer-meta"><span class="answerer">Tai師父</span></div>
  <div class="answer-text">這是回答的詳細內容，包含足夠的說明文字。</div>
</div>
<p>這是一段普通段落文字，長度足夠進入搜索索引，超過最小長度限制。</p>
</body></html>"""

    (out / "01.html").write_text(html, encoding="utf-8")
    (out / "01_trad.html").write_text(html, encoding="utf-8")

    return out


@pytest.fixture
def chapters():
    return [Chapter(title="第一章", filename="01.html")]


@pytest.fixture
def generator(settings, output_with_html):
    fm = FileManager(output_with_html)
    return SearchIndexGenerator(settings, fm)


class TestSearchIndexGenerator:
    def test_generate_simplified_creates_json(self, generator, chapters, output_with_html):
        generator.generate_search_indexes(chapters, generate_traditional=False, generate_simplified=True)
        index_file = output_with_html / Constants.SEARCH_INDEX_SIMPLIFIED
        assert index_file.exists()

    def test_generate_simplified_json_is_valid(self, generator, chapters, output_with_html):
        generator.generate_search_indexes(chapters, generate_traditional=False, generate_simplified=True)
        index_file = output_with_html / Constants.SEARCH_INDEX_SIMPLIFIED
        data = json.loads(index_file.read_text(encoding="utf-8"))
        assert isinstance(data, list)

    def test_generate_traditional_creates_json(self, generator, chapters, output_with_html):
        generator.generate_search_indexes(chapters, generate_traditional=True, generate_simplified=False)
        index_file = output_with_html / Constants.SEARCH_INDEX_TRADITIONAL
        assert index_file.exists()

    def test_generate_simplified_contains_items(self, generator, chapters, output_with_html):
        generator.generate_search_indexes(chapters, generate_traditional=False, generate_simplified=True)
        data = json.loads(
            (output_with_html / Constants.SEARCH_INDEX_SIMPLIFIED).read_text(encoding="utf-8")
        )
        assert len(data) > 0

    def test_generate_search_indexes_both(self, generator, chapters, output_with_html):
        generator.generate_search_indexes(chapters, generate_traditional=True, generate_simplified=True)
        assert (output_with_html / Constants.SEARCH_INDEX_SIMPLIFIED).exists()
        assert (output_with_html / Constants.SEARCH_INDEX_TRADITIONAL).exists()

    def test_generate_search_indexes_simplified_only(self, generator, chapters, output_with_html):
        generator.generate_search_indexes(chapters, generate_traditional=False, generate_simplified=True)
        assert (output_with_html / Constants.SEARCH_INDEX_SIMPLIFIED).exists()
        assert not (output_with_html / Constants.SEARCH_INDEX_TRADITIONAL).exists()

    def test_generate_search_indexes_traditional_only(self, generator, chapters, output_with_html):
        generator.generate_search_indexes(chapters, generate_traditional=True, generate_simplified=False)
        assert not (output_with_html / Constants.SEARCH_INDEX_SIMPLIFIED).exists()
        assert (output_with_html / Constants.SEARCH_INDEX_TRADITIONAL).exists()

    def test_ensure_search_index_files_creates_empty(self, settings, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        fm = FileManager(out)
        gen = SearchIndexGenerator(settings, fm)
        gen.ensure_search_index_files(generate_traditional=True, generate_simplified=True)
        simplified = out / Constants.SEARCH_INDEX_SIMPLIFIED
        traditional = out / Constants.SEARCH_INDEX_TRADITIONAL
        assert simplified.exists()
        assert traditional.exists()

    def test_search_items_have_required_fields(self, generator, chapters, output_with_html):
        generator.generate_search_indexes(chapters, generate_traditional=False, generate_simplified=True)
        data = json.loads(
            (output_with_html / Constants.SEARCH_INDEX_SIMPLIFIED).read_text(encoding="utf-8")
        )
        for item in data:
            assert "id" in item
            assert "content" in item
            assert "type" in item
            assert "url" in item
