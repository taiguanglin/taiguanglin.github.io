"""Tests for generators/html_generator.py"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.document_models import Chapter, TOCItem, QAPair, ConversionConfig
from generators.html_generator import HTMLGenerator, TOCGenerator
from utils.file_utils import FileManager
from config.settings import Settings


@pytest.fixture
def settings():
    return Settings(favicon_search_patterns=["favicon.ico"])


@pytest.fixture
def output_dir(tmp_path):
    d = tmp_path / "output"
    d.mkdir()
    for sub in ["assets/css", "assets/js", "assets/images"]:
        (d / sub).mkdir(parents=True)
    return d


@pytest.fixture
def fake_input(tmp_path):
    f = tmp_path / "book.docx"
    f.touch()
    return f


@pytest.fixture
def file_manager(output_dir):
    return FileManager(output_dir)


@pytest.fixture
def html_gen(settings, file_manager, fake_input):
    return HTMLGenerator(settings, file_manager, fake_input)


@pytest.fixture
def sample_chapters():
    ch1 = Chapter(title="第一章", filename="01.html")
    ch1.add_toc_item(1, "第一章", "ch1")
    ch2 = Chapter(title="第二章", filename="02.html")
    ch2.add_toc_item(1, "第二章", "ch2")
    return [ch1, ch2]


# ---------------------------------------------------------------------------
# TOCGenerator
# ---------------------------------------------------------------------------

class TestTOCGenerator:
    def test_count_children_at_levels(self):
        gen = TOCGenerator()
        toc_items = [
            (1, "A", "a"), (2, "A1", "a1"), (2, "A2", "a2"), (1, "B", "b")
        ]
        counts = gen._count_children_at_levels(toc_items, 0, max_level=4)
        assert counts[2] == 2  # two level-2 children under level-1 item 0

    def test_count_children_stops_at_same_level(self):
        gen = TOCGenerator()
        toc_items = [
            (1, "A", "a"), (2, "A1", "a1"), (1, "B", "b"), (2, "B1", "b1")
        ]
        counts = gen._count_children_at_levels(toc_items, 0, max_level=4)
        # A only has 1 level-2 child (B is same level, stops counting)
        assert counts[2] == 1


# ---------------------------------------------------------------------------
# HTMLGenerator - chapter page generation
# ---------------------------------------------------------------------------

class TestHTMLGeneratorChapterPages:
    def test_generates_simplified_chapter_file(self, html_gen, sample_chapters, output_dir):
        html_gen.generate_chapter_pages(
            sample_chapters, generate_traditional=False, generate_simplified=True
        )
        assert (output_dir / "01.html").exists()
        assert (output_dir / "02.html").exists()

    def test_generates_traditional_chapter_file(self, html_gen, sample_chapters, output_dir):
        html_gen.generate_chapter_pages(
            sample_chapters, generate_traditional=True, generate_simplified=False
        )
        assert (output_dir / "01_trad.html").exists()
        assert (output_dir / "02_trad.html").exists()

    def test_chapter_html_contains_title(self, html_gen, sample_chapters, output_dir):
        html_gen.generate_chapter_pages(
            sample_chapters, generate_traditional=False, generate_simplified=True
        )
        content = (output_dir / "01.html").read_text(encoding="utf-8")
        # Title should appear somewhere in the HTML
        assert "第" in content  # part of the chapter title

    def test_chapter_html_has_script_link(self, html_gen, sample_chapters, output_dir):
        html_gen.generate_chapter_pages(
            sample_chapters, generate_traditional=False, generate_simplified=True
        )
        content = (output_dir / "01.html").read_text(encoding="utf-8")
        assert "script.js" in content

    def test_chapter_html_has_css_link(self, html_gen, sample_chapters, output_dir):
        html_gen.generate_chapter_pages(
            sample_chapters, generate_traditional=False, generate_simplified=True
        )
        content = (output_dir / "01.html").read_text(encoding="utf-8")
        assert "style.css" in content


# ---------------------------------------------------------------------------
# HTMLGenerator - index page generation
# ---------------------------------------------------------------------------

class TestHTMLGeneratorIndexPages:
    def test_generates_simplified_index(self, html_gen, sample_chapters, output_dir, tmp_path):
        fake_input = tmp_path / "book.docx"
        fake_input.touch()
        cfg = ConversionConfig(
            input_file=fake_input,
            output_folder=output_dir,
            generate_simplified=True,
            generate_traditional=False,
        )
        html_gen.generate_index_pages(
            sample_chapters, cfg,
            generate_traditional=False, generate_simplified=True,
        )
        assert (output_dir / "index.html").exists()

    def test_generates_traditional_index(self, html_gen, sample_chapters, output_dir, tmp_path):
        fake_input = tmp_path / "book.docx"
        fake_input.touch()
        cfg = ConversionConfig(
            input_file=fake_input,
            output_folder=output_dir,
            generate_simplified=False,
            generate_traditional=True,
        )
        html_gen.generate_index_pages(
            sample_chapters, cfg,
            generate_traditional=True, generate_simplified=False,
        )
        assert (output_dir / "index_trad.html").exists()

    def test_index_html_contains_chapters(self, html_gen, sample_chapters, output_dir, tmp_path):
        fake_input = tmp_path / "book.docx"
        fake_input.touch()
        cfg = ConversionConfig(
            input_file=fake_input,
            output_folder=output_dir,
        )
        html_gen.generate_index_pages(
            sample_chapters, cfg,
            generate_traditional=False, generate_simplified=True,
        )
        content = (output_dir / "index.html").read_text(encoding="utf-8")
        assert "01.html" in content or "第一章" in content
