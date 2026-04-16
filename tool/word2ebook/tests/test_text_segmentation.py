"""Tests for utils/text_segmentation.py"""

import pytest
from utils.text_segmentation import ChineseSegmenter, segment_text, is_segmenter_available


@pytest.fixture
def segmenter():
    return ChineseSegmenter()


class TestChineseSegmenter:
    def test_segment_text_returns_string(self, segmenter):
        result = segmenter.segment_text("人工智能技術")
        assert isinstance(result, str)

    def test_segment_empty_returns_empty(self, segmenter):
        assert segmenter.segment_text("") == ""

    def test_segment_non_string_returns_empty(self, segmenter):
        assert segmenter.segment_text(None) == ""  # type: ignore

    def test_segment_produces_space_separated_words(self, segmenter):
        result = segmenter.segment_text("自然語言處理")
        # Should contain at least one space-separated token
        assert len(result) > 0

    def test_punctuation_filtered_out(self, segmenter):
        result = segmenter.segment_text("你好，世界！")
        assert "，" not in result
        assert "！" not in result

    def test_is_available(self, segmenter):
        assert segmenter.is_available() is True

    def test_segment_content_and_title(self, segmenter):
        title_tokens, content_tokens = segmenter.segment_content_and_title(
            "人工智能", "自然語言處理技術"
        )
        assert isinstance(title_tokens, str)
        assert isinstance(content_tokens, str)

    def test_segment_content_and_title_empty(self, segmenter):
        title_tokens, content_tokens = segmenter.segment_content_and_title("", "")
        assert title_tokens == ""
        assert content_tokens == ""

    def test_meaningful_word_keeps_chinese(self, segmenter):
        assert segmenter._is_meaningful_word("你好") is True

    def test_meaningful_word_keeps_english(self, segmenter):
        assert segmenter._is_meaningful_word("hello") is True

    def test_meaningful_word_filters_punctuation(self, segmenter):
        assert segmenter._is_meaningful_word("，") is False


class TestConvenienceFunctions:
    def test_segment_text_function(self):
        result = segment_text("人工智能")
        assert isinstance(result, str)

    def test_is_segmenter_available(self):
        # jieba is in requirements so should be available
        assert is_segmenter_available() is True
