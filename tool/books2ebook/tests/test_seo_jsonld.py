"""books2ebook 的 JSON-LD（結構化資料）與 SEO 描述測試。

背景（2026-10-28 SEO 稽核）：`ebook/` 的 22 個頁面原本完全沒有 JSON-LD，
章節 meta description 也只是模板句、沒有段落數。本檔鎖住：

1. 首頁／章節頁的 JSON-LD payload 含 Book／Chapter／WebPage／BreadcrumbList。
2. `inject_jsonld()` 會把 marker 換成合法的 JSON-LD script，並轉義 ``</``。
3. 章節描述帶段落數（每章不同）。
4. 繁體頁的 JSON-LD 文字需為繁體（`<script>` 不會被整頁轉換器處理）。
"""

import json
import re
import sys
from pathlib import Path

import pytest

TOOL_DIR = Path(__file__).resolve().parent.parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import html_generator  # noqa: E402
from config import BookConfig  # noqa: E402


@pytest.fixture
def book():
    return BookConfig(1, "01《坐禅》", "01《坐禅》.pdf", "zuochan")


@pytest.fixture
def preface_book():
    return BookConfig(
        4, "感恩与讲经", "感恩与讲经（2024年4月14日）.pdf", "ganen", kind="preface"
    )


def _extract_jsonld(html):
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    )
    assert match, "page must contain a JSON-LD block"
    return json.loads(match.group(1))


class TestIndexJsonLd:
    def test_index_payload_has_expected_nodes(self, book):
        payload = html_generator.build_index_jsonld(
            [{"config": book, "blocks": []}], False, "標題", "描述"
        )
        types = {node["@type"] for node in payload["@graph"]}
        assert {"Book", "WebPage", "BreadcrumbList"} <= types
        series = next(n for n in payload["@graph"] if n["@type"] == "Book")
        assert series["hasPart"][0]["position"] == 1
        assert series["hasPart"][0]["url"].endswith("/ebook/01.html")

    def test_index_traditional_uses_trad_filename(self, book):
        payload = html_generator.build_index_jsonld(
            [{"config": book, "blocks": []}], True, "標題", "描述"
        )
        series = next(n for n in payload["@graph"] if n["@type"] == "Book")
        assert series["hasPart"][0]["url"].endswith("/ebook/01_trad.html")


class TestChapterJsonLd:
    def test_chapter_payload_has_expected_nodes(self, book):
        payload = html_generator.build_chapter_jsonld(
            book, False, "標題", "描述", position=1, total_books=10
        )
        types = {node["@type"] for node in payload["@graph"]}
        assert {"Book", "Chapter", "WebPage", "BreadcrumbList"} <= types
        chapter = next(n for n in payload["@graph"] if n["@type"] == "Chapter")
        assert chapter["position"] == 1
        assert chapter["url"].endswith("/ebook/01.html")
        breadcrumb = next(
            n for n in payload["@graph"] if n["@type"] == "BreadcrumbList"
        )
        assert len(breadcrumb["itemListElement"]) == 3


class TestInjectJsonLd:
    def test_marker_is_replaced(self, book):
        html = "<html><head>%s</head><body></body></html>" % html_generator.JSONLD_MARKER
        out = html_generator.inject_jsonld(
            html, html_generator.build_chapter_jsonld(book, False, "t", "d", 1, 10)
        )
        assert html_generator.JSONLD_MARKER not in out
        assert out.count('type="application/ld+json"') == 1
        _extract_jsonld(out)

    def test_closing_script_is_escaped(self):
        html = "<html><head>%s</head></html>" % html_generator.JSONLD_MARKER
        out = html_generator.inject_jsonld(
            html,
            {
                "@context": "https://schema.org",
                "@type": "Thing",
                "name": "</script><script>alert(1)</script>",
            },
        )
        body = out.split('application/ld+json">')[1].split("</script>")[0]
        assert "<script>" not in body
        _extract_jsonld(out)


class TestSeoDescription:
    def test_chapter_description_contains_count(self, book):
        desc = html_generator._chapter_seo_description(book, 1662)
        assert "1662" in desc
        assert "《坐禅》" in desc

    def test_preface_description_contains_count(self, preface_book):
        desc = html_generator._chapter_seo_description(preface_book, 81)
        assert "81" in desc
        assert "卷首" in desc
