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

    # ---- OOXML control-char escape removal ----

    def test_standardize_strips_ooxml_control_escape(self, processor):
        # Word 殘留的控制字元轉義（_x0001_ / _x000B_）應被移除
        assert processor.standardize_variant_chars("希望_x0001_，沒有問題") == "希望，沒有問題"
        assert processor.standardize_variant_chars("一行_x000B_文字") == "一行文字"
        assert processor.standardize_variant_chars("_x001F_開頭") == "開頭"
        assert processor.standardize_variant_chars("結尾_x007F_") == "結尾"

    def test_standardize_keeps_printable_char_escape(self, processor):
        # 可列印字元的轉義（底線 _x005F_、字母 _x0041_）不在控制字元範圍，應保留
        assert "_x005F_" in processor.standardize_variant_chars("保留_x005F_底線")
        assert "_x0041_" in processor.standardize_variant_chars("保留_x0041_字母")

    def test_to_traditional_strips_ooxml_control_escape(self, processor):
        # 繁體輸出（經 to_traditional）也應移除控制字元轉義
        assert processor.to_traditional("真實不虛的希望_x0001_") == "真實不虛的希望"

    def test_ensure_simplified_strips_ooxml_control_escape(self, processor):
        # 簡體輸出（經 ensure_simplified）也應移除控制字元轉義
        assert "_x0001_" not in processor.ensure_simplified("希望_x0001_沒有問題")

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

    def test_to_traditional_context_fix_zen_one(self, processor):
        # 禪宗「那個一」語境：「那一隻能回到自性」應為「只能」（人工判斷的個案修正）
        result = processor.to_traditional("一歸何處，那一隻能回到自性當中去")
        assert "那一只能回到自性" in result
        assert "隻能" not in result

    def test_to_traditional_keeps_measure_one_can(self, processor):
        # 真正的量詞用法（這一隻能飛）不可被個案修正影響
        assert processor.to_traditional("這一隻能飛") == "這一隻能飛"

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

    # ---- 發 / 髮 (emit vs hair) ----

    def test_to_traditional_fixes_fa_over_hair(self, processor):
        # s2tw 把「發」誤轉成「髮」，需修正回「發」
        assert processor.to_traditional("不要乱发愿") == "不要亂發願"
        assert processor.to_traditional("众生发愿") == "眾生發願"
        assert processor.to_traditional("一抬头发现自己") == "一抬頭發現自己"
        assert processor.to_traditional("舌头发生变化") == "舌頭發生變化"
        assert processor.to_traditional("额头发紧") == "額頭發緊"
        assert processor.to_traditional("一直发呆") == "一直發呆"

    def test_to_traditional_keeps_real_hair(self, processor):
        # 真正的「頭髮」類詞必須保留
        assert processor.to_traditional("头发的颜色") == "頭髮的顏色"
        assert processor.to_traditional("白发变黑") == "白髮變黑"
        assert processor.to_traditional("发际线") == "髮際線"
        assert processor.to_traditional("脱发和白发问题") == "脫髮和白髮問題"
        assert processor.to_traditional("理发") == "理髮"

    # ---- 後 / 后 (after vs queen) ----

    def test_to_traditional_fixes_hou_after(self, processor):
        # s2tw 把「後」漏轉成「后」，需修正回「後」
        assert processor.to_traditional("吃了东西后盘腿") == "吃了東西後盤腿"
        assert processor.to_traditional("49天后再看看") == "49天後再看看"
        assert processor.to_traditional("上天后断开关系") == "上天後斷開關係"
        assert processor.to_traditional("聊天后出现") == "聊天後出現"

    def test_to_traditional_keeps_queen_hou(self, processor):
        # 真正的皇后／太后／呂后／蟻后必須保留「后」
        assert "皇后" in processor.to_traditional("娶一个皇后")
        assert "太后" in processor.to_traditional("慈禧太后")
        assert "吕后" not in processor.to_traditional("仿效吕后")
        assert "呂后" in processor.to_traditional("仿效吕后")
        assert "蟻后" in processor.to_traditional("蚂蚁离开蚁后")

    # ---- 裡 / 里 (inside vs li/mile) ----

    def test_to_traditional_fixes_li_inside(self, processor):
        # s2tw 在片語後把「裡」漏轉成「里」，需修正回「裡」
        assert processor.to_traditional("剧本里写的") == "劇本裡寫的"
        assert processor.to_traditional("六道里") == "六道裡"
        assert processor.to_traditional("我知道里面有鬼") == "我知道裡面有鬼"
        assert processor.to_traditional("在他们视角里") == "在他們視角裡"
        assert processor.to_traditional("往轮回里拉") == "往輪迴裡拉"

    def test_to_traditional_keeps_real_li(self, processor):
        # 真正的距離／音譯「里」必須保留
        assert processor.to_traditional("公里") == "公里"
        assert processor.to_traditional("千里之外") == "千里之外"
        assert processor.to_traditional("斯里兰卡") == "斯里蘭卡"
        assert processor.to_traditional("邻里") == "鄰里"

    # ---- 製 / 制, 分鐘, 睏 ----

    def test_to_traditional_fixes_zhi_zhi(self, processor):
        # 製造 / 制度 的字詞層級誤轉
        assert processor.to_traditional("少和人制造矛盾") == "少和人製造矛盾"
        assert processor.to_traditional("中国制度规定") == "中國制度規定"

    def test_to_traditional_fixes_minute(self, processor):
        # 分鐘（minute）不可寫成 分鍾
        assert processor.to_traditional("十几分钟") == "十幾分鐘"

    def test_to_traditional_keeps_xinxi(self, processor):
        # 「信息」在台灣通用，統一保留為「信息」（不轉成「資訊」）
        assert processor.to_traditional("信息很多") == "信息很多"
        assert processor.to_traditional("获取信息") == "獲取信息"
        # 來源若為「资讯」也一併歸一成「信息」
        assert processor.to_traditional("现在资讯传媒发达") == "現在信息傳媒發達"

    def test_to_traditional_context_fix_sleepy_kun(self, processor):
        # 「現在困才是更大的問題」的「困」是睡意「睏」（人工判斷的個案修正）
        result = processor.to_traditional("反而你现在困才是更大的问题")
        assert "現在睏才是" in result

    def test_to_traditional_keeps_trapped_kun(self, processor):
        # 真正「受困／困難」的困不可被誤改成睏
        assert "困難" in processor.to_traditional("遇到困难")
        assert "被困" in processor.to_traditional("被困住")

    def test_to_simplified_empty(self, processor):
        assert processor.to_simplified("") == ""

    def test_ensure_simplified_is_idempotent_like(self, processor):
        # Running twice should not raise
        once = processor.ensure_simplified("測試文字")
        twice = processor.ensure_simplified(once)
        assert isinstance(twice, str)
