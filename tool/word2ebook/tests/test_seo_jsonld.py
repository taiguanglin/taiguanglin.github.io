"""Tests for the SEO head / JSON-LD of generators/html_generator.py.

背景（2026-10-28 SEO 稽核）：兩套電子書原本完全沒有 JSON-LD，首頁描述的
問答數寫死在 config.yaml（9,241 則，實際 9,242 則），搜尋摘要因此與頁面
不一致。本檔鎖住三件事：

1. 章節／首頁各有且只有一個 JSON-LD block，且含 Book／Chapter／BreadcrumbList。
2. 首頁描述的問答數與章節數由建置期計算（不再硬編碼）。
3. JSON-LD 是合法 JSON，且不含未轉義的 ``</script>``。
"""

import json
import re

import pytest

from models.document_models import Chapter
from generators.html_generator import HTMLGenerator
from config.settings import Settings


@pytest.fixture
def settings():
    return Settings(favicon_search_patterns=["favicon.ico"])


@pytest.fixture
def html_gen(settings, tmp_path):
    from utils.file_utils import FileManager

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "assets").mkdir()
    source = tmp_path / "book.docx"
    source.touch()
    return HTMLGenerator(settings, FileManager(output_dir), source)


def _chapter(title="01自性與意識", filename="01.html", questions=3):
    chapter = Chapter(title=title, filename=filename)
    body = "".join(
        '<div class="question" id="question-%d">Q</div>'
        '<div class="answer" id="answer-%d">A</div>' % (i, i)
        for i in range(questions)
    )
    chapter.content = body
    return chapter


def _extract_jsonld(html):
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    )
    assert match, "page must contain a JSON-LD block"
    return json.loads(match.group(1))


class TestJsonLdChapter:
    def test_chapter_page_has_one_jsonld_block(self, html_gen):
        chapter = _chapter()
        html = html_gen._build_jsonld_chapter(
            chapter=chapter,
            position=1,
            total_chapters=12,
            is_traditional=False,
            filename="01.html",
            seo_title="自性與意識・坐禅之问答录2｜TaiGuangLin 禅师",
            description="說明",
            clean_title="自性與意識",
        )
        assert html.count('type="application/ld+json"') == 1

    def test_chapter_jsonld_contains_expected_nodes(self, html_gen):
        html = html_gen._build_jsonld_chapter(
            chapter=_chapter(),
            position=3,
            total_chapters=12,
            is_traditional=False,
            filename="03.html",
            seo_title="發心・坐禅之问答录2｜TaiGuangLin 禅师",
            description="說明",
            clean_title="發心",
        )
        payload = _extract_jsonld(html)
        types = {node["@type"] for node in payload["@graph"]}
        assert {"Book", "Chapter", "WebPage", "BreadcrumbList"} <= types
        chapter_node = next(n for n in payload["@graph"] if n["@type"] == "Chapter")
        assert chapter_node["position"] == 3
        assert chapter_node["name"] == "發心"
        assert chapter_node["url"].endswith("/wenda2_ebook/03.html")
        breadcrumb = next(
            n for n in payload["@graph"] if n["@type"] == "BreadcrumbList"
        )
        assert [i["position"] for i in breadcrumb["itemListElement"]] == [1, 2, 3]

    def test_traditional_jsonld_is_traditional(self, html_gen):
        html = html_gen._build_jsonld_chapter(
            chapter=_chapter(),
            position=1,
            total_chapters=12,
            is_traditional=True,
            filename="01_trad.html",
            seo_title="自性與意識・坐禪之問答錄2｜TaiGuangLin 禪師",
            description="說明",
            clean_title="自性與意識",
        )
        payload = _extract_jsonld(html)
        author = next(
            n for n in payload["@graph"] if n["@type"] == "Book"
        )["author"]["name"]
        assert author == "TaiGuangLin 禪師"

    def test_jsonld_escapes_closing_script(self, html_gen):
        html = html_gen._build_jsonld_chapter(
            chapter=_chapter(),
            position=1,
            total_chapters=12,
            is_traditional=False,
            filename="01.html",
            seo_title="</script><script>alert(1)</script>・坐禅之问答录2",
            description="說明",
            clean_title="自性與意識",
        )
        assert "</script>" not in html.split('application/ld+json">')[1].split(
            "</script>"
        )[0]
        _extract_jsonld(html)


class TestJsonLdIndex:
    def test_index_lists_every_chapter(self, html_gen):
        chapters = [_chapter("01甲", "01.html"), _chapter("02乙", "02.html")]
        html = html_gen._build_jsonld_index(
            chapters,
            "坐禅之问答录2",
            False,
            "index.html",
            "坐禅之问答录2｜TaiGuangLin 禅师",
            "說明",
        )
        payload = _extract_jsonld(html)
        book = next(n for n in payload["@graph"] if n["@type"] == "Book")
        assert [p["position"] for p in book["hasPart"]] == [1, 2]
        assert book["hasPart"][1]["url"].endswith("/wenda2_ebook/02.html")

    def test_index_traditional_uses_trad_filenames(self, html_gen):
        chapters = [_chapter("01甲", "01.html")]
        html = html_gen._build_jsonld_index(
            chapters,
            "坐禪之問答錄2",
            True,
            "index_trad.html",
            "坐禪之問答錄2｜TaiGuangLin 禪師",
            "說明",
        )
        payload = _extract_jsonld(html)
        book = next(n for n in payload["@graph"] if n["@type"] == "Book")
        assert book["hasPart"][0]["url"].endswith("/wenda2_ebook/01_trad.html")


class TestSeoDescriptionPlaceholders:
    def test_format_seo_text_replaces_known_placeholders(self):
        out = HTMLGenerator._format_seo_text(
            "共 {qa_count} 則，按 {chapter_count} 章", qa_count=9242, chapter_count=12
        )
        assert out == "共 9242 則，按 12 章"

    def test_format_seo_text_keeps_unknown_placeholders(self):
        out = HTMLGenerator._format_seo_text("共 {qa_count} 則 {other}", qa_count=10)
        assert out == "共 10 則 {other}"

    def test_chapter_qa_count_matches_rendered_count(self, html_gen):
        chapter = _chapter(questions=7)
        assert html_gen._chapter_qa_count(chapter) == 7
