"""Tests for generators/html_generator.py"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.document_models import Chapter, TOCItem, QAPair, ConversionConfig
from generators.html_generator import HTMLGenerator
from generators.toc_generator import TOCGenerator
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
    def test_build_chapter_toc_structure(self):
        gen = TOCGenerator()
        toc_items = [
            (2, "A", "a"), (3, "A1", "a1"), (3, "A2", "a2"), (2, "B", "b")
        ]
        html = gen.build_chapter_toc(toc_items)
        assert '<a href="#a">A</a>' in html
        assert '<a href="#a1">A1</a>' in html

    def test_build_chapter_toc_stops_nesting(self):
        gen = TOCGenerator()
        toc_items = [
            (2, "A", "a"), (3, "A1", "a1"), (2, "B", "b"), (3, "B1", "b1")
        ]
        html = gen.build_chapter_toc(toc_items)
        # both A1 and B1 should appear
        assert '<a href="#a1">A1</a>' in html
        assert '<a href="#b1">B1</a>' in html


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

    def test_chapter_header_links_to_ebook_toc_not_site(
        self, html_gen, sample_chapters, output_dir
    ):
        html_gen.generate_chapter_pages(
            sample_chapters, generate_traditional=True, generate_simplified=False
        )
        content = (output_dir / "01_trad.html").read_text(encoding="utf-8")
        assert '<a href="index_trad.html">📖 問答錄2總目錄</a>' in content
        assert 'href="../ebook/' not in content
        assert 'href="../index.html"' not in content


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

    def test_traditional_index_header_uses_single_site_home(
        self, html_gen, sample_chapters, output_dir, tmp_path
    ):
        fake_input = tmp_path / "book.docx"
        fake_input.touch()
        cfg = ConversionConfig(input_file=fake_input, output_folder=output_dir)
        html_gen.generate_index_pages(
            sample_chapters, cfg,
            generate_traditional=True, generate_simplified=False,
        )
        content = (output_dir / "index_trad.html").read_text(encoding="utf-8")
        assert '<a href="../index.html">🏠 網站首頁</a>' in content
        assert '<a href="../ebook/index_trad.html">📚 坐禪與講經系列</a>' in content
        assert "../index_trad.html" not in content


# ---------------------------------------------------------------------------
# Source filename (homepage footer) — Word + extra PDF sources
# ---------------------------------------------------------------------------

class TestSourceFilename:
    def test_word_only_source(self, settings, file_manager, fake_input):
        gen = HTMLGenerator(settings, file_manager, fake_input)
        html = gen._build_source_filename()
        # 來源檔輸出成可下載的超連結（href 為相對於輸出資料夾的路徑）
        assert '<a class="source-link"' in html
        assert 'href="../book.docx"' in html
        assert 'download="book.docx"' in html
        assert ">book.docx</a>" in html

    def test_word_plus_pdf_source(self, settings, file_manager, fake_input, tmp_path):
        pdf = tmp_path / "answers.pdf"
        gen = HTMLGenerator(settings, file_manager, fake_input, extra_source_files=[pdf])
        html = gen._build_source_filename()
        assert html.count("<a ") == 2
        assert "、" in html
        assert 'href="../book.docx"' in html
        assert ">book.docx</a>" in html
        assert 'href="../answers.pdf"' in html
        assert ">answers.pdf</a>" in html

    def test_word_plus_two_pdf_sources_no_qa(self, settings, file_manager, fake_input, tmp_path):
        pdf1 = tmp_path / "2025年6月-9月答疑合并（未分类）.pdf"
        pdf2 = tmp_path / "2025年11月-2026年3月答疑合并（未分类）.pdf"
        gen = HTMLGenerator(
            settings, file_manager, fake_input,
            extra_source_files=[pdf1, pdf2],
            include_qa_source=False,
        )
        html = gen._build_source_filename()
        assert html.count("<a ") == 3
        assert ">book.docx</a>" in html
        assert "2025年6月-9月答疑合并（未分类）.pdf" in html
        assert "2025年11月-2026年3月答疑合并（未分类）.pdf" in html
        assert "qa/index.html" not in html
        assert "线上答疑" not in html and "線上答疑" not in html

    def test_source_href_is_relative_to_output(self, settings, file_manager, fake_input):
        # output_dir 與來源檔同在 tmp_path 下，連結應以 ../ 退回上層再指向來源檔
        gen = HTMLGenerator(settings, file_manager, fake_input)
        assert gen._build_source_href(fake_input) == "../book.docx"

    def test_index_shows_both_sources(self, settings, file_manager, fake_input, output_dir, tmp_path):
        pdf = tmp_path / "answers.pdf"
        gen = HTMLGenerator(settings, file_manager, fake_input, extra_source_files=[pdf])
        cfg = ConversionConfig(input_file=fake_input, output_folder=output_dir)
        ch = Chapter(title="第一章", filename="01.html")
        ch.add_toc_item(1, "第一章", "ch1")
        gen.generate_index_pages([ch], cfg, generate_traditional=False, generate_simplified=True)
        content = (output_dir / "index.html").read_text(encoding="utf-8")
        assert ">book.docx</a>" in content
        assert ">answers.pdf</a>" in content
        assert 'download="answers.pdf"' in content
