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

    # ---- Taiwan-standard traditional: fix HK / over-converted source ----

    def test_to_traditional_fixes_overconverted_zhi(self, processor):
        # 港式/過度轉換的「隻能」應修正為台灣正體「只能」
        assert processor.to_traditional("隻能") == "只能"
        assert processor.to_traditional("隻是") == "只是"

    def test_to_traditional_fixes_zhi_after_copula(self, processor):
        # s2tw 會把「是只能」誤轉成「是隻能」，需修正回「是只能」
        assert processor.to_traditional("就是隻能治標") == "就是只能治標"
        assert processor.to_traditional("還是隻有地球") == "還是只有地球"
        assert processor.to_traditional("那隻能來地球度人") == "那只能來地球度人"
        assert processor.to_traditional("他們是隻關心修行") == "他們是只關心修行"

    def test_to_traditional_keeps_zhi_idioms(self, processor):
        # 固定詞「隻字」「隻身」必須保留
        assert "隻字不提" in processor.to_traditional("迴避、隻字不提")
        assert "隻身" in processor.to_traditional("孩子隻身來到上海")

    def test_to_traditional_fixes_overconverted_gan(self, processor):
        # 「幹預」應修正為「干預」，且在前綴後也要正確
        assert processor.to_traditional("幹預") == "干預"
        assert processor.to_traditional("不能貿然去幹預") == "不能貿然去干預"
        assert processor.to_traditional("以法術去幹擾別人") == "以法術去干擾別人"

    def test_to_traditional_fixes_overconverted_chong(self, processor):
        # 「沖突」應修正為「衝突」
        assert processor.to_traditional("業和修行相沖突") == "業和修行相衝突"

    def test_to_traditional_keeps_legit_gan_chong(self, processor):
        # 真正的「幹活/幹細胞」「對沖/興沖沖」不可被誤改
        assert "幹活" in processor.to_traditional("回家幹活")
        assert "幹細胞" in processor.to_traditional("幹細胞研究")
        assert "對沖" in processor.to_traditional("用善業來對沖惡業")
        assert "興沖沖" in processor.to_traditional("興沖沖地送去")

    def test_to_traditional_uses_taiwan_li(self, processor):
        # 港式/舊式「裏」應轉成台灣正體「裡」
        assert processor.to_traditional("裏面") == "裡面"

    def test_to_traditional_preserves_measure_word_zhi(self, processor):
        # 合法量詞「隻」必須保留（不可誤改成「只」）
        assert processor.to_traditional("一隻貓") == "一隻貓"
        assert processor.to_traditional("三隻小豬") == "三隻小豬"

    def test_to_traditional_from_simplified(self, processor):
        # 簡體來源也應得到正確台灣正體
        assert processor.to_traditional("只能干预") == "只能干預"

    def test_to_simplified_empty(self, processor):
        assert processor.to_simplified("") == ""

    def test_ensure_simplified_is_idempotent_like(self, processor):
        # Running twice should not raise
        once = processor.ensure_simplified("測試文字")
        twice = processor.ensure_simplified(once)
        assert isinstance(twice, str)
