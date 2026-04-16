"""Tests for utils/i18n_utils.py"""

import pytest
from utils.i18n_utils import I18nProcessor


@pytest.fixture
def processor():
    return I18nProcessor()


class TestI18nProcessor:
    # ---- filename helpers ----

    def test_get_traditional_filename(self, processor):
        assert processor.get_traditional_filename("01.html") == "01_trad.html"

    def test_get_simplified_filename(self, processor):
        assert processor.get_simplified_filename("01_trad.html") == "01.html"

    def test_is_traditional_filename_true(self, processor):
        assert processor.is_traditional_filename("01_trad.html") is True

    def test_is_traditional_filename_false(self, processor):
        assert processor.is_traditional_filename("01.html") is False

    # ---- variant char standardization ----

    def test_standardize_variant_chars_empty(self, processor):
        assert processor.standardize_variant_chars("") == ""

    def test_standardize_variant_chars_replaces(self, processor):
        # 衆 -> 眾
        result = processor.standardize_variant_chars("衆多")
        assert "眾" in result
        assert "衆" not in result

    def test_standardize_variant_chars_passthrough(self, processor):
        text = "沒有異體字"
        assert processor.standardize_variant_chars(text) == text

    # ---- conversion (requires opencc) ----

    def test_to_traditional_returns_string(self, processor):
        result = processor.to_traditional("你好世界")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_to_simplified_returns_string(self, processor):
        result = processor.to_simplified("你好世界")
        assert isinstance(result, str)

    def test_to_traditional_empty(self, processor):
        assert processor.to_traditional("") == ""

    def test_to_simplified_empty(self, processor):
        assert processor.to_simplified("") == ""

    def test_ensure_simplified_is_idempotent_like(self, processor):
        # Running twice should not raise
        once = processor.ensure_simplified("測試文字")
        twice = processor.ensure_simplified(once)
        assert isinstance(twice, str)
