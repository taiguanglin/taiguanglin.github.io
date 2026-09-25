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

    def test_to_simplified_keeps_existing_information_wording(self, processor):
        assert processor.to_simplified("取得資訊") == "取得信息"
        assert processor.ensure_simplified("取得資訊") == "取得信息"

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

    def test_to_traditional_fixes_zhi_corpus_overconversions(self, processor):
        # 語料實測（2026-11 對 ebook/ + wenda2_ebook/ 全文盤查）s2tw/s2twp 仍會
        # 誤轉的「隻X」→「只X」——這些就是線上電子書出現的實際錯誤。
        assert processor.to_traditional("還是隻立一個就可以") == "還是只立一個就可以"
        assert processor.to_traditional("但是隻覺得那種人怎麼也救不了") == "但是只覺得那種人怎麼也救不了"
        assert processor.to_traditional("是不是隻靠心念") == "是不是只靠心念"
        assert processor.to_traditional("都是隻考量習氣") == "都是只考量習氣"
        assert processor.to_traditional("但是隻更新五十多次") == "但是只更新五十多次"
        assert processor.to_traditional("是隻授沙彌戒的") == "是只授沙彌戒的"
        assert processor.to_traditional("它是不是隻屬於我") == "它是不是只屬於我"
        assert processor.to_traditional("雙盤要換著坐，別隻坐一種") == "雙盤要換著坐，別只坐一種"
        assert processor.to_traditional("但是隻支援了一會兒") == "但是只支援了一會兒"
        assert processor.to_traditional("不是買東西就是隻取快遞") == "不是買東西就是只取快遞"
        assert processor.to_traditional("還是隻加入圓滿奉送咒") == "還是只加入圓滿奉送咒"
        assert processor.to_traditional("通常是隻建議插一根香") == "通常是只建議插一根香"
        assert processor.to_traditional("是隻消業還是跟您一樣") == "是只消業還是跟您一樣"
        assert processor.to_traditional("那就是隻創造一些物質") == "那就是只創造一些物質"
        assert processor.to_traditional("但是隻打坐兩個小時") == "但是只打坐兩個小時"
        assert processor.to_traditional("如果是隻向佛菩薩求") == "如果是只向佛菩薩求"
        assert processor.to_traditional("也是隻專注於講法") == "也是只專注於講法"
        # 簡體來源同樣要得到正確結果（轉換管線的完整路徑）
        assert processor.to_traditional("还是只立一个就可以") == "還是只立一個就可以"

    def test_to_traditional_keeps_measure_zhi_variants(self, processor):
        # 合法量詞「隻」不可被誤改（數量詞／量詞性指示詞前綴與固定詞）
        assert processor.to_traditional("一隻手") == "一隻手"
        assert processor.to_traditional("兩隻手合掌") == "兩隻手合掌"
        assert processor.to_traditional("那隻腳的膝蓋") == "那隻腳的膝蓋"
        assert processor.to_traditional("第三隻眼") == "第三隻眼"
        assert processor.to_traditional("半隻眼睛") == "半隻眼睛"
        assert processor.to_traditional("更多隻同一種類的螞蟻") == "更多隻同一種類的螞蟻"
        assert processor.to_traditional("每隻動物") == "每隻動物"
        assert processor.to_traditional("書包裡伸出隻手遞給他") == "書包裡伸出隻手遞給他"
        assert processor.to_traditional("去年還有隻一歲多的") == "去年還有隻一歲多的"
        assert "隻字不提" in processor.to_traditional("迴避、隻字不提")
        assert "隻身來到上海" in processor.to_traditional("孩子隻身來到上海")

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

    def test_to_traditional_uses_common_taiwan_variants(self, processor):
        assert processor.to_traditional("人才群众因为里面") == "人才群眾因為裡面"
        assert processor.to_traditional("纔羣爲裏衆") == "才群為裡眾"

    def test_to_traditional_uses_taiwan_phrases(self, processor):
        assert processor.to_traditional("软件和鼠标") == "軟體和滑鼠"
        assert processor.to_traditional("获取信息") == "獲取資訊"

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

    def test_to_traditional_fixes_houyi(self, processor):
        # 「大梵天后裔」是「大梵天＋後裔」（梵天之後代），不是「天后」＋裔；
        # 台灣正體作「後裔」，孤立「后裔」由 OpenCC 片語字典轉成「後裔」。
        assert processor.to_traditional("梵志是大梵天后裔") == "梵志是大梵天後裔"
        assert processor.to_traditional("后裔") == "後裔"

    def test_to_traditional_fixes_yun_say(self, processor):
        # 簡體「云」兼表「說」與「雲」；t2s → s2t 往返把引句「師云：」全寫成
        # 「師雲：」，需把冒號前的「雲」改回「云」
        assert processor.to_traditional("师云：") == "師云："
        assert processor.to_traditional("示众云：“") == "示眾云：“"
        assert "雲:" not in processor.to_traditional("《地藏经》云:起心动念")
        assert processor.to_traditional("《地藏经》云:起心动念") == "《地藏經》云:起心動念"
        # 真正的「雲」不受影響；「云何／云云」由片語字典轉換正確
        assert processor.to_traditional("白云") == "白雲"
        assert processor.to_traditional("虚云和尚") == "虛雲和尚"
        assert processor.to_traditional("云何") == "云何"
        assert processor.to_traditional("人云亦云") == "人云亦云"

    def test_to_traditional_fixes_mian_face(self, processor):
        # 簡體「面」兼表「臉」與「麵」；s2t 片語劫持把臉義誤轉成「麵」
        assert processor.to_traditional("面貌和面容") == "面貌和面容"
        assert processor.to_traditional("和面对未来") == "和面對未來"
        assert processor.to_traditional("直面人生") == "直面人生"
        assert processor.to_traditional("直面临人生") == "直面臨人生"
        # 真正的「麵」不受影響
        assert processor.to_traditional("面条") == "麵條"
        assert processor.to_traditional("面包") == "麵包"
        assert processor.to_traditional("泡面") == "泡麵"
        assert processor.to_traditional("米面") == "米麵"

    def test_to_traditional_fixes_jin_gan_world(self, processor):
        # 來源 OCR「千→干」：佛學術語 小千／中千／大千世界、三千大千世界
        assert processor.to_traditional("小干世界") == "小千世界"
        assert processor.to_traditional("中干世界") == "中千世界"
        assert processor.to_traditional("大干世界") == "大千世界"
        assert processor.to_traditional("三干大干世界") == "三千大千世界"
        # 真正的「幹／乾」不受影響
        assert processor.to_traditional("干杯") == "乾杯"
        assert processor.to_traditional("干净") == "乾淨"
        assert processor.to_traditional("若干") == "若干"

    def test_to_traditional_fixes_phrase_level_residuals(self, processor):
        # 「尽量」片語劫持（会尽量→會盡量）、「复杂」「干扰」字詞層級誤轉
        assert processor.to_traditional("会尽量帮你的") == "會儘量幫你的"
        assert processor.to_traditional("盡人事嘛，會盡量幫你的！") == "盡人事嘛，會儘量幫你的！"
        assert processor.to_traditional("尽力") == "盡力"
        assert processor.to_traditional("尽管") == "儘管"
        assert processor.to_traditional("更复杂") == "更複雜"
        assert processor.to_traditional("复杂") == "複雜"
        assert processor.to_traditional("恢复") == "恢復"
        assert processor.to_traditional("重复") == "重複"
        assert processor.to_traditional("因果干扰") == "因果干擾"
        assert processor.to_traditional("干扰") == "干擾"

    def test_to_traditional_fixes_measure_prefix_suppressed_zhi(self, processor):
        # 量詞前綴（一／多…）壓住「隻X→只」的語境修正；「最多隻能」等片語的
        # 「隻」一律是副詞「只」，由片語層級修正補上
        assert processor.to_traditional("最多只能算是") == "最多只能算是"
        assert processor.to_traditional("最多隻能算是") == "最多只能算是"
        assert processor.to_traditional("最多隻能證得近行定") == "最多只能證得近行定"
        assert processor.to_traditional("最多隻是消業而已") == "最多只是消業而已"
        assert processor.to_traditional("差不多隻有過去的十六") == "差不多只有過去的十六"
        assert processor.to_traditional("如果業很多隻能慢慢來消") == "如果業很多只能慢慢來消"
        assert processor.to_traditional("一隻能回到自性") == "一只能回到自性"
        # 量詞用法不受影響
        assert processor.to_traditional("一只猫") == "一隻貓"
        assert processor.to_traditional("更多只同一种类的蚂蚁") == "更多隻同一種類的螞蟻"

    # ---- 裡 / 里 (inside vs li/mile) ----

    def test_to_traditional_fixes_li_inside(self, processor):
        # s2tw 在片語後把「裡」漏轉成「里」，需修正回「裡」
        assert processor.to_traditional("剧本里写的") == "劇本裡寫的"
        assert processor.to_traditional("六道里") == "六道裡"
        assert processor.to_traditional("我知道里面有鬼") == "我知道裡面有鬼"
        assert processor.to_traditional("在他们视角里") == "在他們視角裡"
        assert processor.to_traditional("往轮回里拉") == "往輪迴裡拉"
        # 語料實測：相里／梅里／包里 都是「裡面」之意
        assert "在相裡產生" in processor.to_traditional("在相里产生的分别")
        assert "從梅裡生" in processor.to_traditional("如果是从梅里生的")
        assert processor.to_traditional("书包里") == "書包裡"
        assert "記憶包裡" in processor.to_traditional("都存在记忆包里的话")

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

    def test_to_traditional_localizes_xinxi(self, processor):
        # s2twp 將中國大陸慣用詞「信息」轉成台灣常用的「資訊」
        assert processor.to_traditional("信息很多") == "資訊很多"
        assert processor.to_traditional("获取信息") == "獲取資訊"
        assert processor.to_traditional("现在资讯传媒发达") == "現在資訊傳媒發達"

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
