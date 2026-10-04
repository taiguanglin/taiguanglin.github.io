"""Tests for generators/html_generator.py"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.document_models import Chapter, TOCItem, QAPair, ConversionConfig
from generators.html_generator import HTMLGenerator
from generators.toc_generator import TOCGenerator
from templates.i18n_templates import I18nTemplateManager
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


class TestCollapsibleChapterToc:
    """巢狀可折疊 TOC：語意巢狀、展開鈕為 button、無 target=_blank。"""

    TOC_ITEMS = [
        (2, "A", "a"), (3, "A1", "a1"), (3, "A2", "a2"),
        (4, "A2a", "a2a"), (2, "B", "b"),
    ]

    def test_nested_ul_structure(self):
        gen = TOCGenerator()
        html = gen.build_collapsible_chapter_toc(self.TOC_ITEMS)
        # A 的子層必須包在 A 的 <li> 內（巢狀語意）
        assert '<a href="#a">A</a>\n<ul>' in html
        # A2a 在 A2 的巢狀 ul 內
        assert 'A2</a>\n<ul>' in html
        # 無 data-default-visible（JS 以 localStorage/預設層級決定顯示）
        assert "data-default-visible" not in html
        # 同頁連結不開新分頁
        assert 'target="_blank"' not in html

    def test_expand_icons_are_buttons_with_aria(self):
        gen = TOCGenerator()
        html = gen.build_collapsible_chapter_toc(self.TOC_ITEMS)
        assert '<button type="button" class="toc-expand-icon"' in html
        assert 'aria-expanded="true"' in html
        # 沒有子層的項目（A1、B）不出展開鈕
        assert '<a href="#b">B</a>' in html

    def test_index_page_links_same_tab_with_chapter_attr(self):
        gen = TOCGenerator()
        html = gen.build_collapsible_chapter_toc(
            self.TOC_ITEMS, filename="01.html", chapter_index=0,
            is_index_page=True,
        )
        assert '<a href="01.html#a">A</a>' in html
        assert 'data-chapter="0"' in html
        assert 'target="_blank"' not in html

    def test_build_index_toc_no_blank_no_default_visible(self, sample_chapters):
        gen = TOCGenerator()
        html = gen.build_index_toc(sample_chapters)
        assert "data-default-visible" not in html
        assert 'target="_blank"' not in html
        assert 'href="01.html"' in html


# ---------------------------------------------------------------------------
# TOC 初始狀態（回歸測試：JS 尚未載入時 HTML 本身必須已排版正確）
# ---------------------------------------------------------------------------

class TestTOCInitialState:
    """伺服器端必須輸出正確的初始 TOC 狀態，否則 script.js 到位前會亂版。

    根因：``04a-toc-levels.css`` 用 ``.toc-item:not(.toc-expandable)``
    決定葉節點排版，而 ``.toc-expandable`` 原本只由 JS 補上 —— JS 未執行時
    全部 ``li`` 命中 ``:not(...)`` 拿到 ``display:flex``，巢狀 ``<ul>``
    被拉成橫向並排。
    """

    ITEMS = [
        (2, "A", "a"), (3, "A1", "a1"), (3, "A2", "a2"),
        (4, "A2a", "a2a"), (2, "B", "b"),
    ]

    def test_expandable_items_carry_class(self):
        html = TOCGenerator().build_collapsible_chapter_toc(self.ITEMS)
        # 有子節點者（level 2 的 A、level 3 的 A2）必須帶 toc-expandable
        assert 'class="toc-item toc-level-2 toc-expandable"' in html
        assert 'class="toc-item toc-level-3 toc-expandable"' in html
        # 葉節點不得帶（否則會失去 display:flex）
        assert 'class="toc-item toc-level-2" data-level="2"' in html

    def test_no_item_that_has_children_lacks_expandable(self):
        """穩健性：任何含展開鈕的 li 都必須同時有 toc-expandable。"""
        html = TOCGenerator().build_collapsible_chapter_toc(self.ITEMS)
        for li in html.split("<li")[1:]:
            tag = li.split(">")[0]
            if "toc-expand-icon" in li.split(">", 2)[-1][:200] or "toc-expand-icon" in tag:
                assert "toc-expandable" in tag, li[:120]

    def test_index_page_default_level_two(self):
        html = TOCGenerator().build_collapsible_chapter_toc(
            self.ITEMS, is_index_page=True
        )
        # 第 3 層以上先隱藏；第 2 層展開鈕為收合
        assert 'class="toc-item toc-level-3 hidden"' in html
        assert 'class="toc-item toc-level-4 hidden"' in html
        assert 'aria-expanded="false">▶<' in html

    def test_chapter_page_default_level_three(self):
        html = TOCGenerator().build_collapsible_chapter_toc(self.ITEMS)
        # 章節頁預設第 3 層 → 只有第 4 層隱藏
        assert 'class="toc-item toc-level-4 hidden"' in html
        assert 'class="toc-item toc-level-3 hidden"' not in html

    def test_resolve_display_level_snaps_to_present_level(self):
        """只有第 2 層時必須退到第 2 層，與 JS selectValidLevel() 一致。"""
        resolve = TOCGenerator.resolve_display_level
        assert resolve({2}, 3, button_levels={2, 3, 4}) == 2
        assert resolve({2, 3}, 3, button_levels={2, 3, 4}) == 3
        assert resolve({2, 3, 4}, 2, button_levels={1, 2, 3, 4}) == 2
        # 完全沒有項目 → 保留預設
        assert resolve(set(), 3, button_levels={2, 3, 4}) == 3

    def test_chapter_toc_without_deep_levels_is_fully_visible(self):
        """只有單層標題的章節不應有任何 .hidden（否則 JS 啟動前目錄是空的）。"""
        html = TOCGenerator().build_collapsible_chapter_toc([(2, "A", "a"), (2, "B", "b")])
        assert "hidden" not in html

    def test_index_chapter_node_is_expandable(self, sample_chapters):
        html = TOCGenerator().build_index_toc(sample_chapters)
        assert 'class="toc-item toc-chapter toc-expandable"' in html

    def test_chapter_level_buttons_only_render_present_levels(self):
        """只渲染該章確實有標題的層級按鈕（對應 JS detectAndHideLevelButtons）。

        少渲染一顆按鈕，控制列就少一顆圓鈕的寬度；若留到 JS 才隱藏，
        控制列會在首繪後縮短而位移。
        """
        btns = I18nTemplateManager.build_level_buttons((2, 3, 4), 3, present_levels={2})
        assert 'data-level="2"' in btns
        assert 'data-level="3"' not in btns
        assert 'data-level="4"' not in btns
        # active 必須落在實際渲染的層級上
        assert 'toc-level-btn active" data-level="2"' in btns

    def test_chapter_level_buttons_active_falls_back_when_level_absent(self):
        """active 指定的層級若不在按鈕列內，退到第一顆（不會沒有 active）。"""
        btns = I18nTemplateManager.build_level_buttons((2, 3, 4), 3, present_levels={2, 4})
        assert 'toc-level-btn active" data-level="2"' in btns

    def test_chapter_level_buttons_without_present_levels_keeps_all(self):
        """未提供 present_levels 時維持全部按鈕（最小重建／測試相容）。"""
        btns = I18nTemplateManager.build_level_buttons((2, 3, 4), 3)
        for lv in (2, 3, 4):
            assert 'data-level="%d"' % lv in btns

    def test_chapter_level_buttons_active_matches_level(self):
        """層級按鈕的 .active 必須標在實際顯示層級上（否則 JS 啟動後高亮跳動）。"""
        btns = I18nTemplateManager.build_level_buttons((2, 3, 4), 2)
        assert 'class="toc-level-btn active" data-level="2"' in btns
        assert 'data-level="3"' in btns
        assert 'toc-level-btn active" data-level="3"' not in btns


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

    # -- SEO head -----------------------------------------------------------

    def test_chapter_page_has_seo_head(self, html_gen, sample_chapters, output_dir):
        ch = Chapter(title="01自性與意識", filename="01.html")
        ch.add_toc_item(1, "01自性與意識", "c1")
        html_gen.generate_chapter_pages(
            [ch], generate_traditional=True, generate_simplified=True
        )
        for name, lang in (("01.html", "zh-Hans"), ("01_trad.html", "zh-Hant")):
            content = (output_dir / name).read_text(encoding="utf-8")
            assert f'<html lang="{lang}">' in content
            assert '<meta name="description" content="' in content
            assert (
                f'<link rel="canonical" href="https://taiguanglin.info/'
                f'wenda2_ebook/{name}">' in content
            )
            assert 'hreflang="zh-Hant"' in content and 'hreflang="zh-Hans"' in content
            assert 'hreflang="x-default"' in content
            assert '<meta property="og:type" content="article">' in content
            assert '<meta property="og:image" content="' in content

    def test_seo_title_strips_chapter_number(self, html_gen, output_dir):
        ch = Chapter(title="13二〇二五年六月", filename="13.html")
        ch.add_toc_item(1, "13二〇二五年六月", "c13")
        html_gen.generate_chapter_pages(
            [ch], generate_traditional=True, generate_simplified=False
        )
        content = (output_dir / "13_trad.html").read_text(encoding="utf-8")
        assert "<title>二〇二五年六月・坐禪之問答錄2｜TaiGuangLin 禪師</title>" in content
        html_gen.generate_chapter_pages(
            [ch], generate_traditional=False, generate_simplified=True
        )
        content = (output_dir / "13.html").read_text(encoding="utf-8")
        assert "<title>二〇二五年六月・坐禅之问答录2｜TaiGuangLin 禅师</title>" in content

    def test_index_page_has_seo_head_and_preconnect(
        self, html_gen, sample_chapters, output_dir, tmp_path
    ):
        fake_input = tmp_path / "book.docx"
        fake_input.touch()
        cfg = ConversionConfig(
            input_file=fake_input,
            output_folder=output_dir,
            generate_simplified=True,
            generate_traditional=True,
        )
        html_gen.generate_index_pages(
            sample_chapters, cfg,
            generate_traditional=True, generate_simplified=True,
        )
        content = (output_dir / "index.html").read_text(encoding="utf-8")
        assert "<title>" in content and "｜TaiGuangLin 禅师</title>" in content
        assert '<meta property="og:type" content="website">' in content
        assert (
            '<link rel="canonical" href="https://taiguanglin.info/wenda2_ebook/index.html">'
            in content
        )
        # MiniSearch 改為本地自架（defer、無第三方 CDN 依賴；中國網路可達）
        assert '<script src="assets/js/minisearch.min.js" defer></script>' in content
        assert "cdn.jsdelivr.net/npm/minisearch" not in content
        assert "preconnect" not in content
        trad = (output_dir / "index_trad.html").read_text(encoding="utf-8")
        assert (
            '<link rel="canonical" href="https://taiguanglin.info/wenda2_ebook/index_trad.html">'
            in trad
        )
        assert 'hreflang="x-default" href="https://taiguanglin.info/wenda2_ebook/index_trad.html">' in content


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
        assert '<a href="../index.html">🏠 首頁</a>' in content
        assert '<a href="../ebook/index_trad.html">📚 坐禪與講經</a>' in content
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
