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

    def test_answer_title_includes_question_time(self, processor):
        items, _ = processor.extract_search_content(SIMPLE_HTML, "01.html")
        answers = [i for i in items if i.type == "answer"]
        assert len(answers) >= 1
        assert answers[0].title == "Tai師父的回答 | 2024-01-15 10:30"

    def test_question_title_includes_time(self, processor):
        items, _ = processor.extract_search_content(SIMPLE_HTML, "01.html")
        questions = [i for i in items if i.type == "question"]
        assert len(questions) >= 1
        assert questions[0].title == "學生甲 | 2024-01-15 10:30"

    def test_answer_title_without_question_time(self, processor):
        html = """<html><body>
<div class="question">
  <div class="question-meta"><span class="questioner">學生乙</span></div>
  <div class="question-text">沒有時間的問題內容，長度足夠。</div>
</div>
<div class="answer">
  <div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
  <div class="answer-text">對應回答的詳細內容，長度足夠。</div>
</div>
</body></html>"""
        items, _ = processor.extract_search_content(html, "01.html")
        answers = [i for i in items if i.type == "answer"]
        assert len(answers) == 1
        assert answers[0].title == "Tai師父的回答"

    def test_pdf_section_label_fallback_for_question_and_answer(self, processor):
        html = """<html><body>
<h2 id="sec">2025年11月10日 官網<span class="chapter-qa-count">(138)</span></h2>
<div class="question">
  <div class="question-meta"><span class="questioner">印龍</span></div>
  <div class="question-text">PDF 章節沒有時間戳的問題內容。</div>
</div>
<div class="answer">
  <div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
  <div class="answer-text">對應回答的詳細內容，長度足夠說明。</div>
</div>
</body></html>"""
        items, _ = processor.extract_search_content(html, "17.html")
        questions = [i for i in items if i.type == "question"]
        answers = [i for i in items if i.type == "answer"]
        assert questions[0].title == "印龍 | 2025年11月10日 官網"
        assert answers[0].title == "Tai師父的回答 | 2025年11月10日 官網"

    def test_topical_heading_not_used_as_time_fallback(self, processor):
        html = """<html><body>
<h2>初始設定1.自性恆常<span class="chapter-qa-count">(50)</span></h2>
<div class="question">
  <div class="question-meta"><span class="questioner">無名</span></div>
  <div class="question-text">Word 章節沒有時間的問題內容。</div>
</div>
<div class="answer">
  <div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
  <div class="answer-text">對應回答的詳細內容，長度足夠說明。</div>
</div>
</body></html>"""
        items, _ = processor.extract_search_content(html, "01.html")
        questions = [i for i in items if i.type == "question"]
        answers = [i for i in items if i.type == "answer"]
        assert questions[0].title == "無名"
        assert answers[0].title == "Tai師父的回答"

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
