"""Tests for models/document_models.py"""

from pathlib import Path
import pytest

from models.document_models import (
    TOCItem, QAPair, SearchItem, Chapter,
    ConversionConfig, QACountMetadata, QAPosition,
)


class TestTOCItem:
    def test_creation(self):
        item = TOCItem(level=2, text="小節", anchor="section-1")
        assert item.level == 2
        assert item.text == "小節"
        assert item.anchor == "section-1"


class TestQAPair:
    def test_to_html_contains_question(self, sample_qa_pair):
        html = sample_qa_pair.to_html()
        assert 'class="question"' in html
        assert sample_qa_pair.question_text in html

    def test_to_html_contains_answer(self, sample_qa_pair):
        html = sample_qa_pair.to_html()
        assert 'class="answer"' in html
        assert sample_qa_pair.answer_text in html

    def test_to_html_has_questioner(self, sample_qa_pair):
        html = sample_qa_pair.to_html()
        assert sample_qa_pair.questioner in html

    def test_to_html_has_time(self, sample_qa_pair):
        html = sample_qa_pair.to_html()
        assert sample_qa_pair.time_info in html

    def test_to_html_no_time_when_none(self):
        pair = QAPair(
            question_id="q-1", answer_id="a-1",
            questioner="A", question_text="Q", answer_text="Ans",
        )
        html = pair.to_html()
        assert "question-time" not in html

    def test_to_html_ids_are_set(self, sample_qa_pair):
        html = sample_qa_pair.to_html()
        assert f'id="{sample_qa_pair.question_id}"' in html
        assert f'id="{sample_qa_pair.answer_id}"' in html


class TestSearchItem:
    def test_to_dict_basic(self, sample_search_item):
        d = sample_search_item.to_dict()
        assert d["id"] == sample_search_item.id
        assert d["type"] == "heading"
        assert d["content"] == sample_search_item.content
        assert d["url"] == sample_search_item.url

    def test_to_dict_no_context_when_same(self, sample_search_item):
        # context == content → context field should be omitted
        d = sample_search_item.to_dict()
        assert "context" not in d

    def test_to_dict_has_context_when_different(self):
        item = SearchItem(
            id="x-0", title="T", type="content",
            content="long content here",
            context="short ctx",
            url="01.html#x",
        )
        d = item.to_dict()
        assert "context" in d
        assert d["context"] == "short ctx"


class TestChapter:
    def test_safe_title_strips_html(self):
        ch = Chapter(title="<b>第一章</b>", filename="01.html")
        assert ch.safe_title == "第一章"

    def test_traditional_filename(self):
        ch = Chapter(title="T", filename="01.html")
        assert ch.traditional_filename == "01_trad.html"

    def test_add_toc_item(self):
        ch = Chapter(title="T", filename="01.html")
        ch.add_toc_item(1, "Section", "sec-1")
        assert len(ch.toc_items) == 1
        assert ch.toc_items[0].text == "Section"

    def test_add_qa_pair(self, sample_qa_pair):
        ch = Chapter(title="T", filename="01.html")
        ch.add_qa_pair(sample_qa_pair)
        assert len(ch.qa_pairs) == 1

    def test_add_search_item(self, sample_search_item):
        ch = Chapter(title="T", filename="01.html")
        ch.add_search_item(sample_search_item)
        assert len(ch.search_items) == 1


class TestConversionConfig:
    def test_default_flags(self, tmp_path):
        f = tmp_path / "book.docx"
        f.touch()
        cfg = ConversionConfig(input_file=f, output_folder=tmp_path / "out")
        assert cfg.generate_search is True
        assert cfg.generate_traditional is True
        assert cfg.generate_simplified is True

    def test_book_title_from_filename(self, tmp_path):
        f = tmp_path / "my_book.docx"
        f.touch()
        cfg = ConversionConfig(input_file=f, output_folder=tmp_path / "out")
        assert cfg.book_title == "my_book"

    def test_book_title_explicit(self, tmp_path):
        f = tmp_path / "book.docx"
        f.touch()
        cfg = ConversionConfig(
            input_file=f,
            output_folder=tmp_path / "out",
            book_title="Custom Title",
        )
        assert cfg.book_title == "Custom Title"

    def test_paths_become_path_objects(self, tmp_path):
        f = tmp_path / "book.docx"
        f.touch()
        cfg = ConversionConfig(
            input_file=str(f),
            output_folder=str(tmp_path / "out"),
        )
        assert isinstance(cfg.input_file, Path)
        assert isinstance(cfg.output_folder, Path)


class TestQACountMetadata:
    def test_get_count_for_anchor_missing(self):
        meta = QACountMetadata(chapter_filename="01.html")
        assert meta.get_count_for_anchor("nonexistent") == 0

    def test_get_count_for_anchor_present(self):
        meta = QACountMetadata(
            chapter_filename="01.html",
            anchor_counts={"ch1": 5},
        )
        assert meta.get_count_for_anchor("ch1") == 5
