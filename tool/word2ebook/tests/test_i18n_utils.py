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

    # ---- TW-phrase hijack protection（_PHRASE_PROTECT）----

    def test_to_traditional_duixiang_not_wujian(self, processor):
        # 使用者回報的原始案件：s2twp 台灣慣用詞把「对象」整詞換成「物件」
        result = processor.to_traditional("視周圍所有人為自己未來要度化的对象")
        assert result == "視周圍所有人為自己未來要度化的對象"
        assert "物件" not in result

    def test_to_traditional_duixiang_all_senses(self, processor):
        # 度化／講授／觀照／結婚對象：全部是「對象」，絕不「物件」
        assert processor.to_traditional("禅定中要消灭的对象") == "禪定中要消滅的對象"
        assert processor.to_traditional("《圆觉经》的讲授对象是菩萨") == "《圓覺經》的講授對象是菩薩"
        assert processor.to_traditional("观照的对象") == "觀照的對象"
        assert processor.to_traditional("找对象") == "找對象"
        assert "跟對象異地" in processor.to_traditional("跟对象异地")

    def test_to_traditional_fixes_source_typo_duixiang(self, processor):
        # 來源錯字「对像」（＝对象）→ 繁體正確形式「對象」
        assert processor.to_traditional("这就叫报复对像存在") == "這就叫報復對象存在"

    def test_to_traditional_keeps_genuine_wujian(self, processor):
        # 簡體原文真的用「物件」（實物義）→ 繁體保持「物件」
        assert "老物件" in processor.to_traditional("家里有一些老物件")

    def test_to_traditional_xunhuan_not_huiquan(self, processor):
        # 循环→迴圈 是 IT 詞劫持；血液／氣血循環
        assert processor.to_traditional("第04节 血液循环") == "第04節 血液循環"
        assert "氣血循環" in processor.to_traditional("气血循环")

    def test_to_traditional_wanxiang_not_yongzhen(self, processor):
        # 万象→永珍（永珍＝寮國首都）劫持；《壇經》「萬象皆現」
        assert processor.to_traditional("忽遇风吹云散，上下俱明，万象皆现。") == \
            "忽遇風吹雲散，上下俱明，萬象皆現。"

    def test_to_traditional_benchi_not_bensi(self, processor):
        # 奔驰→賓士（車牌）劫持；《楞伽經》「愚夫執實奔馳而取」
        assert processor.to_traditional("愚夫执实奔驰而取") == "愚夫執實奔馳而取"

    def test_to_traditional_fabu_not_shichu(self, processor):
        # 发布→釋出（軟體發布）劫持；本語料是公布義
        assert processor.to_traditional("国家宗教局发布相关公告") == "國家宗教局發布相關公告"

    def test_to_traditional_huchu_not_bochu(self, processor):
        # 呼出→撥出（撥打電話）劫持；本語料是呼吸吐納
        assert processor.to_traditional("再让气自然呼出去") == "再讓氣自然呼出去"

    def test_to_traditional_xinda_stays_xindao(self, processor):
        # 「信佛还是信道」＝信＋道，不被信道→通道劫持
        assert processor.to_traditional("不管你信佛还是信道") == "不管你信佛還是信道"

    def test_to_traditional_zixingneng_stays(self, processor):
        # 「自性能」＝自性＋能（《壇經》），不被性能→效能劫持
        assert processor.to_traditional("当自性能含万法是大") == "當自性能含萬法是大"
        assert processor.to_traditional("如果自性能生起妄想") == "如果自性能生起妄想"

    def test_to_traditional_qiangdiaoyong_stays(self, processor):
        # 「强调用」＝強調＋用；「强调度人」＝強調＋度人——
        # 不被調用→呼叫、調度→排程劫持
        assert processor.to_traditional("师强调用鼻子吸气") == "師強調用鼻子吸氣"
        assert processor.to_traditional("但强调度人时不分亲疏") == "但強調度人時不分親疏"

    def test_to_traditional_zhizhen_vs_zhenjiu(self, processor):
        # 「指针灸」＝指＋針灸，不被指针→指標劫持
        assert processor.to_traditional("这种针艾指针灸、艾灸") == "這種針艾指針灸、艾灸"

    def test_to_traditional_renwu_not_gong(self, processor):
        # 多任務→多工 劫持「很多任務」→「很多工」
        assert processor.to_traditional("我做了很多任务") == "我做了很多任務"
        assert processor.to_traditional("只要完成每天的任务就行") == "只要完成每天的任務就行"

    def test_to_traditional_lianjie_not_lianxian(self, processor):
        # 血管／神經「連接」不被連接→連線劫持
        assert processor.to_traditional("心脏连接着六根大血管") == "心臟連接著六根大血管"

    def test_to_traditional_yunxing_not_zhixing(self, processor):
        # 「氣的運行」不被運行→執行劫持
        assert processor.to_traditional("保证气的运行自如") == "保證氣的運行自如"

    def test_to_traditional_zhichi_not_zhiyuan(self, processor):
        # 「家人支持學佛」 endorsement 義不被支持→支援劫持
        assert processor.to_traditional("预计家人不会支持学佛") == "預計家人不會支持學佛"

    def test_to_traditional_chengxu_stays_procedure(self, processor):
        # 「練氣的程序」＝步驟義（56×），不被程序→程式劫持
        assert processor.to_traditional("这是道家练气的程序") == "這是道家練氣的程序"
        # 「文明進程」不被進程→程序劫持
        assert processor.to_traditional("严重影响文明进程") == "嚴重影響文明進程"

    def test_to_traditional_gaoji_consistent(self, processor):
        # 高級→高階 會和未轉換的初級／中階混用；統一成「高級」
        assert processor.to_traditional("分初级、中级、高级") == "分初級、中級、高級"

    def test_to_traditional_jihuo_stays(self, processor):
        # 「激活神經系統」生物義不被激活→啟用劫持
        assert processor.to_traditional("激活神经系统") == "激活神經系統"

    def test_to_traditional_zhouwei_no_zhou_hijack(self, processor):
        # 「一周围／上周围／下周围」：一周／上週／下週 貪婪匹配劫持成「週圍」
        assert processor.to_traditional("我们这一周围已经解脱的菩萨罗汉们") == \
            "我們這一周圍已經解脫的菩薩羅漢們"
        assert processor.to_traditional("忽悠商业上周围的人") == "忽悠商業上周圍的人"
        assert processor.to_traditional("了解一下周围有什么") == "瞭解一下周圍有什麼"
        assert "週圍" not in processor.to_traditional("看周围")

    def test_to_traditional_misc_hijacks(self, processor):
        assert processor.to_traditional("元音老人") == "元音老人"          # 不→母音
        assert processor.to_traditional("把线扩展成一个面") == "把線擴展成一個面"
        assert processor.to_traditional("风灾是局部性的刷新") == "風災是局部性的刷新"
        assert "去當地的社區看看" in processor.to_traditional("去当地的社区看看")
        assert processor.to_traditional("全息图像一样") == "全息圖像一樣"
        assert "的實例" in processor.to_traditional("恶人得善终的实例")
        assert "仿真花" in processor.to_traditional("仿真花可以供佛吗")
        assert processor.to_traditional("语言学范式") == "語言學範式"
        assert processor.to_traditional("就像镜像一样重叠") == "就像鏡像一樣重疊"
        assert "匯集成" in processor.to_traditional("汇集成一个整体")
        assert "拋出去" in processor.to_traditional("把神识给抛出去")
        assert "溢出來" in processor.to_traditional("精液还会自己溢出来吗")
        assert "分區域" in processor.to_traditional("要分区域呢")
        assert "持久不斷" in processor.to_traditional("大愿持久不断")
        assert "性價比" in processor.to_traditional("性价比高")
        assert "調回來" in processor.to_traditional("这回调回来半个多月")

    def test_to_traditional_keeps_legitimate_tw_it_terms(self, processor):
        # 受保護詞彙不可影響正確的台灣化
        assert processor.to_traditional("软件和鼠标") == "軟體和滑鼠"
        assert processor.to_traditional("获取信息") == "獲取資訊"
        assert processor.to_traditional("概率很高") == "機率很高"
        assert processor.to_traditional("通过习气这个第一指标") == "透過習氣這個第一指標"
        assert processor.to_traditional("芯片和内存") == "晶片和記憶體"
        assert "伺服器" in processor.to_traditional("游戏服务器")

    # ---- 同詞二形收斂（唸→念、回向→迴向）----

    def test_to_traditional_nian_uniform(self, processor):
        # STPhrases 只轉部分片語造成「唸佛／念佛」混雜 → 一律「念」
        assert "唸" not in processor.to_traditional("合掌念佛，磕下去念佛")
        assert "念《地藏經》" in processor.to_traditional("先念《地藏经》")
        assert "唸" not in processor.to_traditional("一边念佛号一边念咒")

    def test_to_traditional_huixiang_uniform(self, processor):
        # STPhrases 只轉裸詞「回向」造成「回向／迴向」混雜 → 一律「迴向」
        result = processor.to_traditional("念完做大回向和小回向，再回向给他")
        assert "迴向" in result and "回向" not in result
        assert result == "念完做大迴向和小迴向，再迴向給他"

    # ---- 其他新修正 ----

    def test_to_traditional_weiyinwang_hou(self, processor):
        # 「威音王后」＝威音王＋之後（禪宗術語），非皇后義
        result = processor.to_traditional("没有什么威音王前威音王后的")
        assert result == "沒有什麼威音王前威音王後的"

    def test_to_traditional_toufa_guoqu(self, processor):
        # 然燈佛故事「踩著自己的頭髮過去」——OpenCC 貪婪匹配失準的個案
        result = processor.to_traditional("然灯佛踩着自己的头发过去")
        assert result == "然燈佛踩著自己的頭髮過去"
        # 一般「頭髮」與「頭＋發X」不受影響
        assert processor.to_traditional("头发变白") == "頭髮變白"
        assert processor.to_traditional("总是头发胀") == "總是頭發脹"  # 頭＋發脹（正確）

    def test_to_traditional_digit_zhi_measure(self, processor):
        # 阿拉伯數字＋量詞「只」漏轉（片語字典只收中文數詞前綴）
        assert processor.to_traditional("我学佛是因为2只猫猫才学的") == "我學佛是因為2隻貓貓才學的"
        assert processor.to_traditional("一只猫") == "一隻貓"  # 既有行為不變

    def test_protect_phrases_pua_passthrough(self, processor):
        # 保護／還原機制：哨兵必須完整還原，不得殘留 PUA 字元
        result = processor.to_traditional("对象和程序还有高级支持，周围都是循环")
        assert "\ue000" not in result
        for i in range(60):
            assert chr(0xE000 + i) not in result
        assert result == "對象和程序還有高級支持，周圍都是循環"
