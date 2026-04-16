"""Tests for core/content_processor.py"""

import pytest
from config.settings import Settings
from core.content_processor import ContentProcessor


@pytest.fixture
def settings():
    return Settings(
        search_context_length=80,
        search_min_paragraph_length=20,
        favicon_search_patterns=["favicon.ico"],
    )


@pytest.fixture
def processor(settings):
    return ContentProcessor(settings)


SIMPLE_HTML = """<html><body>
<h2>第一章</h2>
<div class="question">
  <div class="question-meta">
    <span class="questioner">學生甲</span>
    <span class="question-time">2024-01-15 10:30</span>
  </div>
  <div class="question-text">這是問題的內容，包含足夠的文字。</div>
</div>
<div class="answer">
  <div class="answer-meta">
    <span class="answerer">Tai師父</span>
  </div>
  <div class="answer-text">這是回答的詳細內容，包含足夠的說明。</div>
</div>
<p>這是一段普通段落文字，長度足夠進入搜索索引，超過最小長度限制。</p>
</body></html>"""


class TestExtractSearchContent:
    def test_returns_list_and_string(self, processor):
        items, updated_html = processor.extract_search_content(SIMPLE_HTML, "01.html")
        assert isinstance(items, list)
        assert isinstance(updated_html, str)

    def test_extracts_heading(self, processor):
        items, _ = processor.extract_search_content(SIMPLE_HTML, "01.html")
        headings = [i for i in items if i.type == "heading"]
        assert len(headings) >= 1
        assert "第一章" in headings[0].content

    def test_extracts_question(self, processor):
        items, _ = processor.extract_search_content(SIMPLE_HTML, "01.html")
        questions = [i for i in items if i.type == "question"]
        assert len(questions) >= 1

    def test_extracts_answer(self, processor):
        items, _ = processor.extract_search_content(SIMPLE_HTML, "01.html")
        answers = [i for i in items if i.type == "answer"]
        assert len(answers) >= 1

    def test_extracts_content_paragraphs(self, processor):
        items, _ = processor.extract_search_content(SIMPLE_HTML, "01.html")
        content_items = [i for i in items if i.type == "content"]
        assert len(content_items) >= 1

    def test_items_have_url_pointing_to_file(self, processor):
        items, _ = processor.extract_search_content(SIMPLE_HTML, "01.html")
        for item in items:
            assert item.url.startswith("01.html")

    def test_short_paragraphs_excluded(self, processor):
        html = "<html><body><p>短段落</p></body></html>"
        items, _ = processor.extract_search_content(html, "01.html")
        content_items = [i for i in items if i.type == "content"]
        assert len(content_items) == 0

    def test_updated_html_has_ids(self, processor):
        _, updated_html = processor.extract_search_content(SIMPLE_HTML, "01.html")
        assert 'id="' in updated_html

    def test_question_answer_not_in_content_items(self, processor):
        items, _ = processor.extract_search_content(SIMPLE_HTML, "01.html")
        content_items = [i for i in items if i.type == "content"]
        for item in content_items:
            # Content items should not contain question/answer text inside qa divs
            assert "question" not in item.url.split("#")[1] if "#" in item.url else True


class TestGetContext:
    def test_short_text_unchanged(self, processor):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<p>short</p>", "html.parser")
        elem = soup.find("p")
        ctx = processor._get_context(elem, 50)
        assert "short" in ctx

    def test_long_text_truncated(self, processor):
        long_text = "a" * 300
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(f"<p>{long_text}</p>", "html.parser")
        elem = soup.find("p")
        ctx = processor._get_context(elem, 50)
        assert "..." in ctx
