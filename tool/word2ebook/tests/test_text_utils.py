"""Tests for utils/text_utils.py"""

import pytest
from utils.text_utils import normalize_text_for_id, simple_hash, TextProcessor, IDGenerator
from config.settings import Settings


@pytest.fixture
def settings():
    return Settings(
        id_content_length=50,
        favicon_search_patterns=["favicon.ico"],
    )


@pytest.fixture
def text_proc(settings):
    return TextProcessor(settings)


@pytest.fixture
def id_gen(settings):
    return IDGenerator(settings)


# ---------------------------------------------------------------------------
# normalize_text_for_id
# ---------------------------------------------------------------------------

class TestNormalizeTextForId:
    def test_empty_string(self):
        assert normalize_text_for_id("") == ""

    def test_none_like_falsy(self):
        assert normalize_text_for_id("") == ""

    def test_strips_whitespace(self):
        assert normalize_text_for_id("  hello  ") == "hello"

    def test_replaces_newlines(self):
        result = normalize_text_for_id("line1\nline2\rline3\t")
        assert "\n" not in result
        assert "\r" not in result
        assert "\t" not in result

    def test_html_entities_decoded(self):
        result = normalize_text_for_id("&nbsp;a&lt;b&gt;c&amp;d")
        assert result == " a<b>c&d"


# ---------------------------------------------------------------------------
# simple_hash
# ---------------------------------------------------------------------------

class TestSimpleHash:
    def test_returns_12_chars(self):
        assert len(simple_hash("hello")) == 12

    def test_deterministic(self):
        assert simple_hash("test") == simple_hash("test")

    def test_different_inputs_give_different_hashes(self):
        assert simple_hash("abc") != simple_hash("xyz")

    def test_empty_string(self):
        h = simple_hash("")
        assert len(h) == 12


# ---------------------------------------------------------------------------
# TextProcessor.process_line_breaks
# ---------------------------------------------------------------------------

class TestProcessLineBreaks:
    def test_newline_to_br(self, text_proc):
        result = text_proc.process_line_breaks("line1\nline2")
        assert "<br>" in result

    def test_windows_newline(self, text_proc):
        result = text_proc.process_line_breaks("line1\r\nline2")
        assert "<br>" in result

    def test_collapses_triple_br(self, text_proc):
        result = text_proc.process_line_breaks("a\n\n\n\nb")
        # More than 2 consecutive <br> should be collapsed
        assert "<br><br><br>" not in result

    def test_preserves_first_line_strips_leading_br(self, text_proc):
        result = text_proc.process_line_breaks("\n\nContent", preserve_first_line=True)
        assert not result.startswith("<br>")

    def test_no_preserve_keeps_leading_br(self, text_proc):
        result = text_proc.process_line_breaks("\nContent", preserve_first_line=False)
        assert result.startswith("<br>")


# ---------------------------------------------------------------------------
# TextProcessor.extract_time_from_text
# ---------------------------------------------------------------------------

class TestExtractTimeFromText:
    def test_standard_datetime(self, text_proc):
        time, remaining = text_proc.extract_time_from_text("2024-02-18 10:47 問題內容")
        assert time == "2024-02-18 10:47"
        assert "問題內容" in remaining

    def test_date_only(self, text_proc):
        time, remaining = text_proc.extract_time_from_text("2024-02-18 問題")
        assert time is not None
        assert "2024" in time

    def test_no_time_returns_none(self, text_proc):
        time, remaining = text_proc.extract_time_from_text("純文字沒有時間")
        assert time is None
        assert remaining == "純文字沒有時間"

    def test_slash_separator(self, text_proc):
        time, remaining = text_proc.extract_time_from_text("2024/02/18 09:00 內容")
        assert time is not None
        assert "-" in time  # normalized to dash


# ---------------------------------------------------------------------------
# TextProcessor.extract_questioner_info
# ---------------------------------------------------------------------------

class TestExtractQuestionerInfo:
    def test_colon_separator(self, text_proc):
        name, content = text_proc.extract_questioner_info("學生甲：這是問題")
        assert name == "學生甲"
        assert content == "這是問題"

    def test_ascii_colon(self, text_proc):
        name, content = text_proc.extract_questioner_info("Student: content here")
        assert name == "Student"
        assert content == "content here"

    def test_no_match(self, text_proc):
        name, content = text_proc.extract_questioner_info("沒有分隔符的文字")
        assert name is None


# ---------------------------------------------------------------------------
# IDGenerator
# ---------------------------------------------------------------------------

class TestIDGenerator:
    def test_stable_qa_id_deterministic(self, id_gen):
        id1 = id_gen.generate_stable_qa_id("甲", "問題內容", "2024-01-15 10:30", "question")
        id2 = id_gen.generate_stable_qa_id("甲", "問題內容", "2024-01-15 10:30", "question")
        assert id1 == id2

    def test_stable_qa_id_has_prefix(self, id_gen):
        qa_id = id_gen.generate_stable_qa_id("甲", "Q", "2024-01-01", "question")
        assert qa_id.startswith("question-")

    def test_stable_qa_id_different_questioner(self, id_gen):
        id1 = id_gen.generate_stable_qa_id("甲", "相同問題", "2024-01-15", "question")
        id2 = id_gen.generate_stable_qa_id("乙", "相同問題", "2024-01-15", "question")
        assert id1 != id2

    def test_generate_content_id_has_prefix(self, id_gen):
        cid = id_gen.generate_content_id("some text content", "content")
        assert cid.startswith("content-")

    def test_generate_content_id_deterministic(self, id_gen):
        assert (
            id_gen.generate_content_id("abc", "heading")
            == id_gen.generate_content_id("abc", "heading")
        )
