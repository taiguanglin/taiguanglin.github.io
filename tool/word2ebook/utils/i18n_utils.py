"""国际化工具"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# 修正 opencc-python-reimplemented 的 s2tw 過度轉換：把「只」（only，副詞）
# 錯誤轉成量詞「隻」。例如「是只能」會被錯轉成「是隻能」。
#
# 判斷準則（語言學）：
#   - 「只」當「僅、唯」解時是副詞，後面接的是動詞／助動詞／繫詞（能、要、是、有…）。
#   - 「隻」當量詞時，前面通常是數詞／量詞（一、兩、幾…），後面接名詞（貓、手、鳥…）。
# 因此：當「隻」的「後一字」屬於下列副詞後接字集合、且「前一字」不是數量詞時，
# 判定為被過度轉換的「只」，改回「只」。固定詞（隻字、隻身、船隻…）因後接字
# 不在集合內，會自然保留。
# ---------------------------------------------------------------------------

# 數量詞／量詞性指示詞（出現在量詞「隻」前面 → 視為真正的量詞，不修改）。
# 「多第半每另某各此」後面的「隻」也幾乎必是量詞（更多隻、第三隻眼、半隻眼睛、
# 每隻、另隻、某隻、各隻…）；「這／那／哪」刻意不列入——它們也能接副詞「只」
# （那只不過、那只能回到自性），交由後接字集合判斷。
_MEASURE_PREFIX = (
    "一二三四五六七八九十兩零百千萬億幾數壹貳參肆伍陸柒捌玖拾０１２３４５６７８９0123456789"
    "多第半每另某各此"
)

# 副詞「只」常見的後接字（動詞／助動詞／繫詞／副詞）。刻意排除名詞，避免誤判量詞。
# 第三段為語料實測（2026-11 對 ebook/ + wenda2_ebook/ 全文盤查）s2tw/s2twp 仍會
# 誤轉的字：是隻立、隻覺得、隻靠、隻考量、隻更新、隻授、隻屬於、別隻坐、隻支援、
# 隻取、隻加入、隻建議、隻消業、隻創造、隻打坐、隻向、隻專注。
# 第四段為防禦性常用動詞（語料中「只X」確有用例，現行 OpenCC 片語字典恰好涵蓋，
# 補進來以防未來字典版本變動後漏轉）。
# 注意：lang-switch.js（前端即時轉換）有同源修正層，兩份字集必須同步維護。
_ONLY_FOLLOWER = (
    "能會要可得想須應該肯願是有好不在知道說講念唸寫認看去下度吃喝給做求等待差欠"
    "顧管剩怕見為留談聽針受跟提叫過關放思接穿傳夠允動信走用把將顯對供選挑問答"
    "立覺靠考更授屬坐支取加建消創打向專"
    "修讓買賣睡站練幫來停存當限許記"
)

# 例：把「是隻能」修正回「是只能」；「一隻貓」「隻字不提」維持不變。
_ONLY_OVERCONVERT_RE = re.compile(
    r"(?<![" + _MEASURE_PREFIX + r"])隻(?=[" + _ONLY_FOLLOWER + r"])"
)

# ---------------------------------------------------------------------------
# 修正 s2tw 把「發」（emit/issue，发）過度轉成「髮」（hair，发）的錯誤。
# 簡體「发」對應繁體「發」與「髮」兩字；s2tw 在某些前綴後（例如「亂发愿」被
# 當成「亂髮」+「願」、「眾生发願」被當成「生髮」）會誤選「髮」。
#
# 判斷準則：
#   - 「髮」（頭髮）固定出現在毛髮類詞：前接「頭白脫長短掉…」或後接「際型絲…」。
#   - 其餘情況（尤其後接動詞／抽象名詞，如願現生出音揮作展…）多為被誤轉的「發」。
# 規則：當「髮」的後一字屬於「發」的後接字集合，或（前一字非毛髮修飾字 且
#       後一字非毛髮類名詞）時，判定為被過度轉換的「發」，改回「發」。
# ---------------------------------------------------------------------------

# 「發」常見後接字（動詞／抽象名詞）—— 毛髮詞不會以這些字接續。
_FA_FOLLOWER = set(
    "願現生出音揮作展菩善悶火熱財明動言表射放送芽炎燒洩誓怒愁呆抖達號脾瘋楞起揚緊哮酵汗黃脹"
)
# 毛髮修飾字（出現在「髮」前 → 視為真正的頭髮，不修改）
_FA_HAIR_PREV = set("頭白脫長短掉毛理染燙捲金黑銀假鬚削落洗護美禿鬢結披散束拔")
# 毛髮類後接名詞（出現在「髮」後 → 視為真正的頭髮，不修改，例如髮際、髮型）
_FA_HAIR_NEXT = set("際型絲夾膠根量質色梢網飾辮")

# ---------------------------------------------------------------------------
# 修正 s2tw 把「後」（after，后）漏轉、保留成「后」的錯誤。
# 簡體「后」對應繁體「後」（之後）與「后」（皇后）；s2tw 在「天后、東西后、
# 父母后、聊天后」等情境會誤判為皇后義而保留「后」。
# 規則：當「后」的前一字不是皇后類修飾字、且後一字不是皇后類名詞時，改成「後」。
#       固定詞「皇后、太后、呂后、武后、蟻后、天后宮、后土」等因前／後字命中
#       下列集合而保留。
# ---------------------------------------------------------------------------
_QUEEN_PREV = "皇太呂武蟻王神褒妲媽"
# 「裔」刻意不列入——「大梵天后裔」是「大梵天＋後裔」（梵天之後代，台灣正體作
# 「後裔」），不是「天后」＋裔；孤立「后裔」由 OpenCC 片語字典轉成「後裔」。
_QUEEN_NEXT = "土羿稷冠宮娘妃主座"
_HOU_OVERCONVERT_RE = re.compile(
    r"(?<![" + _QUEEN_PREV + r"])后(?![" + _QUEEN_NEXT + r"])"
)

# ---------------------------------------------------------------------------
# 修正 s2tw 把「裡」（inside，里）漏轉、保留成「里」的錯誤。
# s2tw 對「這裡、心裡、手裡」轉換正確，但在片語後（劇本里、知道里面、六道里、
# 視角里、相里、梅里、记忆包里…）會保留簡體「里」。下列前綴後的「里」一律是
# 「裡面」之意，改成「裡」。
# 真正的「里」（公里、千里、鄰里、斯里蘭卡等音譯／距離詞）前綴不在此集合，保留。
# ---------------------------------------------------------------------------
_LI_INSIDE_PREV = "本道會角方場子迴穴識經向梅相包"
_LI_INSIDE_RE = re.compile(r"(?<=[" + _LI_INSIDE_PREV + r"])里")

# ---------------------------------------------------------------------------
# 台灣慣用詞層（s2twp = ST 字／片語轉換 + TWVariants + TWPhrasesIT…）的
# 「IT／科技詞」詞彙劫持：字典把一般語境的常用詞換成軟體術語或專名——
# 「对象→物件」「循环→迴圈」「万象→永珍（永珍＝寮國首都！）」
# 「奔驰→賓士（Mercedes-Benz）」「呼出→撥出（撥打電話）」——在本語料
# （佛法問答＋講經）全部是語意走山的誤轉，實例：
#
#   視周圍所有人為自己未來要度化的对象 → …度化的物件   ← 使用者回報的原始案件
#   自性能含萬法（《六祖壇經》）      → 自效能含萬法
#   愚夫執實奔馳而取（《楞伽經》）    → 愚夫執實賓士而取
#   血液循环                        → 血液迴圈
#   不管你信佛还是信道              → 不管你信佛還是通道
#   师强调用鼻子吸气                → 師強呼叫鼻子吸氣
#
# 語料實證（2026-12 對 ebook/ + wenda2_ebook/ 全文 diff s2tw vs s2twp、
# 逐詞核對語境）：下表每個詞在兩套電子書的出現全部是一般語義，台灣正體
# 也用原詞（對象、循環、支持、連接、運行、任務…）。因此 s2twp 之前先以
# PUA 私用區哨兵把這些詞隔離（OpenCC 不轉換 PUA 字元），轉換後還原成指定
# 的台灣正體形式；正確的台灣化（軟體、滑鼠、資訊、伺服器、機率、透過…）
# 不受影響。
#
# ⚠️ lang-switch.js 的前端即時轉換（OpenCC-JS cn→tw）有同源的
#    PHRASE_PROTECT 表（另含繁體輸入形式），兩份必須同步維護。
# ---------------------------------------------------------------------------
_PHRASE_PROTECT = [
    # ── 語意完全走山（字典換成 IT 術語／專名）──
    ("对象", "對象"),     # →物件（OpenCC 多候選詞，預設取首候選「物件」）
    ("对像", "對象"),     # 來源錯字（对像＝对象）；繁體只有「對象」
    ("循环", "循環"),     # →迴圈（程式迴圈；本語料是血液／氣血循環，363×）
    ("万象", "萬象"),     # →永珍（寮國首都；本語料是森羅萬象，21×）
    ("奔驰", "奔馳"),     # →賓士（車牌；經文「奔馳而取」＋弟子暱稱）
    ("发布", "發布"),     # →釋出（軟體發布；本語料是公布義，「发布灭佛运动」）
    ("呼出", "呼出"),     # →撥出（撥打電話；本語料是呼吸吐納，34×）
    ("信道", "信道"),     # →通道（通信頻道；「信佛還是信道」＝信＋道）
    ("任务", "任務"),     # 多任務→多工（「很多任务」被劫持成「很多工」）
    ("性能", "性能"),     # →效能（「自性能」＝自性＋能，《壇經》語，24×）
    ("指针", "指針"),     # →指標（滑鼠指標；「指针灸」＝指＋針灸）
    ("调用", "調用"),     # →呼叫（函式呼叫；「強调用」＝強調＋用）
    ("调度", "調度"),     # →排程（作業排程；「強调度人時」＝強調＋度人）
    ("调回", "調回"),     # →撥回（回撥電話；「工作調回來」）
    ("集成", "集成"),     # →整合（匯集＋成被併入：匯集成→匯整合）
    ("抛出", "拋出"),     # →丟擲（擲骰／丟例外；本語料是一般拋出）
    ("溢出", "溢出"),     # →溢位（記憶體溢位；本語料是精液／血液溢出）
    ("局部", "局部"),     # →區域性（局部麻醉是台灣正體）
    ("镜像", "鏡像"),     # →映象（磁碟映象；「就像镜像一样」是鏡像）
    ("映射", "映射"),     # →對映（隔空映射的映射義）
    ("范式", "範式"),     # →正規化（語言范式＝paradigm）
    ("仿真", "仿真"),     # →模擬（仿真花＝人造花）
    ("元音", "元音"),     # →母音（元音老人是心中心法人名）
    ("性价比", "性價比"),  # →價效比（台灣也用性價比）
    ("持久", "持久"),     # →永續（永續＝ESG 語彙；「加持持久」）
    # ── 一般語義被 IT 化（本語料無／幾乎無對應 IT 語境）──
    ("程序", "程序"),     # →程式（本語料是程序＝步驟：練氣的程序，56×）
    ("进程", "進程"),     # →程序（文明進程／本土化進程，81×）
    ("运行", "運行"),     # →執行（氣的運行／血液運行，44×）
    ("连接", "連接"),     # →連線（血管連接／神經連接，153×）
    ("支持", "支持"),     # →支援（家人支持學佛；僅 1× 技術支持，128:1）
    ("高级", "高級"),     # →高階（與未轉換的初級／中級並存，造成同句混用）
    ("激活", "激活"),     # →啟用（激活神經系統／卵巢被激活）
    ("扩展", "擴展"),     # →擴充套件（把線擴展成面，18×）
    ("刷新", "刷新"),     # →重新整理（世界刷新＝更新，台灣也用刷新）
    ("社区", "社區"),     # →社群（實體社區：去當地的社區找工作）
    ("图像", "圖像"),     # →影象（全息圖像；台灣正體是圖像）
    ("实例", "實例"),     # →例項（惡人善終的實例）
    ("脚本", "腳本"),     # →指令碼（「左脚本來」＝腳＋本來被劫持）
    ("导入", "導入"),     # →匯入（導入修行法門＝引入義）
    ("分区", "分區"),     # →分割槽（「分區域」被劫持成「分割槽域」）
    # ── STPhrases 層「一週」貪婪匹配劫持「周圍」──
    ("周围", "周圍"),     # 一周/上週/下週 + 圍 → 誤成「一週圍」（3×）；
                         # 台灣正體「周圍」不寫「週」（589×）
]
_PUA_PROTECT_BASE = 0xE000  # PUA-A：OpenCC 不轉換私用區字元，作隔離哨兵

# ---------------------------------------------------------------------------
# 收斂 OpenCC 造成的「同詞二形」：
#   1. 「唸」→「念」：STPhrases 把「念佛／念經／念咒」轉成「唸」但只覆蓋部分
#      片語（「念《地藏經》」「念六字大明咒」不轉），同書「唸佛」與「念佛」
#      混雜（實測：唸 5,303×／念 10,748×）。台灣用法與佛門慣用（教育部辭典
#      「念佛」條、CBETA）均作「念」，且簡體來源全用「念」（t2s 也把「唸」
#      正規化成「念」）→ 一律統一為「念」。
#   2. 「回向」→「迴向」：STPhrases 只轉了裸詞「回向→迴向」（2,102× 中
#      1,791×），「大回向」「小回向」「回向給」「回向他」未覆蓋，同頁混雜
#      （「我回向給其他人：迴向給一個人」）。台灣佛門慣用作「迴向」（迴向文、
#      迴向偈）；語料 2,102×「回向」全是佛教義（無「回＋向」動補用法，
#      「回向佛」「答向」皆 0×）→ 一律統一為「迴向」。
# ---------------------------------------------------------------------------
_NIAN_RECITE = ("唸", "念")
_HUIXIANG_DEDICATION = ("回向", "迴向")

# ---------------------------------------------------------------------------
# 修正阿拉伯數字＋量詞「只」漏轉：OpenCC 片語字典只收錄「一隻／兩隻…」等
# 中文數詞前綴，阿拉伯數字（「2只貓貓」）漏轉。後接名詞限定為動物／手腳眼
# 等量詞「隻」專屬名詞，避免誤改其他「只」。
# ---------------------------------------------------------------------------
_DIGIT_ZHI_MEASURE_RE = re.compile(
    r"(?<=[0-9０-９])只(?=[貓狗雞鴨鳥兔豬牛羊魚蟲蟻鼠手腳眼])"
)

# 需人工判斷的個別情境（通用規則無法自動判斷者）。
# 1.「一歸何處，那一隻能回到自性」中的「一」是禪宗的「那個一」（代詞），
#    語意是「只能」；但通用規則因前一字是數字「一」而保留「隻」，故特別修正。
#    以「回到自性」為語意錨點，確保不誤改真正的量詞用法（如「這一隻能飛」）。
# 2.「反而你現在困才是更大的問題」中的「困」是「睏」（睡意），非「受困」之困；
#    s2tw 無從分辨，以整句錨點修正成「睏」。
_CONTEXT_FIXES = {
    "一隻能回到自性": "一只能回到自性",
    "現在困才是": "現在睏才是",
    # 量詞前綴（一／多…）會壓住「隻X→只」的語境修正；下列「最多隻能」等片語
    # 的「隻」一律是副詞「只」（最多＋只能算／只能看…），用片語層級修正補上。
    "最多隻能": "最多只能",
    "最多隻是": "最多只是",
    "差不多隻有": "差不多只有",
    "業很多隻能": "業很多只能",
    # 「威音王」是佛名（威音王佛）；「威音王前／威音王後」是禪宗術語
    # ＝威音王＋之前／之後，不是「皇后」義。后→後 的通用修正被皇后類
    # 前綴「王」壓住，以整詞錨點修正。
    "威音王后": "威音王後",
    # OpenCC 片語貪婪匹配失準：「自己的头发过去」被轉成「頭發」（頭+發X
    # 規則誤判）——然燈佛故事「踩著自己的頭髮過去」是頭髮義。
    "的頭發過去": "的頭髮過去",
}

# ---------------------------------------------------------------------------
# 修正 t2s → s2t 往返把「云」（說）誤轉成「雲」的錯誤。
# 簡體「云」同時代表「說」（師云、示眾云）與「雲」（雲朵）；來源若是繁體
# 「師云」經 t2s 變「师云」，s2t 一律還原成「雲」。古文引句的「云」是「說」
# 之意，後接冒號（全形／半形）——「雲：」一律改回「云：」。「云何」「云爾」
# 「云云」「人云亦云」由 OpenCC 片語字典轉換正確，不在錯誤之列；真正的
# 「雲」（雲朵、雲霧、虛雲和尚、法雲地）不接冒號，保留。
# ---------------------------------------------------------------------------
_YUN_SAY_RE = re.compile(r"雲(?=[：:])")

# ---------------------------------------------------------------------------
# 修正 s2t 把臉義「面」誤轉成「麵」的錯誤。
# 簡體「面」同時代表「臉」（面容、面對）與「麵」（麵條）；s2t 片語字典在
# 某些前綴後誤轉：面貌和面容→面貌和麵容、和面对→和麵對。臉義「面」後接
# 容／部／對／臨／向／貌／目／孔／色／前；「麵條、麵食、麵包、泡麵、米麵」
# 等真正的「麵」字詞不接這些字，不受影響。「麵」後接「人」（捏麵人等面人義）
# 刻意不列入——由 variant_char_map 的「直麵人生」片語層級修正處理。
# ---------------------------------------------------------------------------
_MIAN_FACE_RE = re.compile(r"麵(?=[容部對臨向貌目孔色前])")

# ---------------------------------------------------------------------------
# 移除 OOXML（Word）控制字元轉義。
# Word 在寫入 .docx 時，會把無法以 XML 表示的控制字元（C0 控制碼 0x00–0x1F 與
# DEL 0x7F）轉義成形如「_x0001_」「_x000B_」的字串，python-docx 會原樣讀出。
# 這些都是無意義的雜訊字元，一律取代成空字串。
# 注意：可列印字元的轉義（例如底線本身 _x005F_、字母 _x0041_）不在此範圍，
# 予以保留，以免誤刪內文。
# ---------------------------------------------------------------------------
_OOXML_CONTROL_CHAR_RE = re.compile(r"_x00[01][0-9A-Fa-f]_|_x007[Ff]_")
_SIMPLIFIED_WORD_NORMALIZATION = {
    # 維持既有簡體版用詞；只在簡體輸出套用，不反向污染台灣正體版。
    "資訊": "信息",
}


class I18nProcessor:
    """国际化处理器"""
    
    def __init__(self):
        self._opencc_s2t = None
        self._opencc_s2twp = None
        self._opencc_t2s = None
        
        # 異體字標準化對照表（台灣正體收尾用，補 OpenCC s2tw 未涵蓋的港式／舊式用字）
        self.variant_char_map = {
            # 繁體異體字標準化
            "衆": "眾",
            "喫": "吃",
            "麪": "麵",
            "綫": "線",
            "衹": "只",
            "僱": "雇",
            "麽": "麼",
            "纔": "才",
            "着": "著",
            "牀": "床",
            "箇": "個",
            "乾點": "幹點",
            "羣": "群",
            "裏": "裡",
            "爲": "為",   # 港式異體 爲 → 台灣 為
            "綉": "繡",
            "衞": "衛",   # 港式 衞 → 台灣 衛
            "説": "說",   # 港式異體 説 → 台灣 說
            "鷄": "雞",
            "啓": "啟",   # 港式 啓 → 台灣 啟
            "硏": "研",
            # 修正 s2tw 對「干」「衝」的過度轉換：下列詞在繁體只有一種正確寫法，
            # 但 opencc-python-reimplemented 在某些前綴後會誤寫成「幹／沖」。
            # （「幹活、幹嘛、幹細胞」等真正的「幹」字詞不在此列，不受影響；
            #   「對沖、相沖、興沖沖」等真正的「沖」字詞同樣不受影響。）
            "幹預": "干預",
            "幹涉": "干涉",
            "幹擾": "干擾",
            "沖突": "衝突",
            "沖動": "衝動",
            "沖擊": "衝擊",
            "沖撞": "衝撞",
            # 修正 s2tw 對「製／制」「鐘／鍾」的字詞層級誤轉（這些詞繁體只有一種寫法）。
            "制造": "製造",   # 製造（manufacture）誤寫成 制造
            "制作": "製作",   # 製作 誤寫成 制作
            "製度": "制度",   # 制度（system）誤寫成 製度
            "分鍾": "分鐘",   # 分鐘（minute）誤寫成 分鍾（鍾 only for 鍾情/姓鍾）
            # 修正 s2t「復／複」「乾／干」字詞層級誤轉、「尽量」片語劫持殘留，
            # 以及來源 OCR「千→干」的佛學術語錯字（這些詞繁體只有一種寫法）。
            "復雜": "複雜",   # 複雜 誤寫成 復雜（s2t 片語未涵蓋「更復雜」等前綴）
            "乾擾": "干擾",   # 干擾 誤寫成 乾擾（干 → 乾；「幹擾」已在上列）
            "盡量": "儘量",   # 儘量（as much as possible）；「会尽量」片語劫持後殘留 盡量
            "直麵人生": "直面人生",  # 「面人」片語劫持：直面人生（face life）
            # 「三幹大幹世界」必須排在「幹世界」之前（dict 依插入順序替換）。
            "三幹大幹世界": "三千大千世界",  # 來源 OCR 千→干
            "幹世界": "千世界",  # 小幹/中幹/大幹世界 → 小千/中千/大千世界
            # OOXML 控制字元轉義（_x0001_、_x000B_ 等）改由 _OOXML_CONTROL_CHAR_RE
            # 統一移除，見 standardize_variant_chars。
            # 可以根據需要繼續添加
        }
    
    @property
    def opencc_s2t(self):
        """懒加载 OpenCC 简体转繁体"""
        if self._opencc_s2t is None:
            try:
                from opencc import OpenCC
                self._opencc_s2t = OpenCC('s2t')
            except ImportError:
                raise ImportError("需要安装 opencc-python-reimplemented 来支持繁体转换")
        return self._opencc_s2t
    
    @property
    def opencc_s2tw(self):
        """懶載入 OpenCC 簡體轉台灣正體（含台灣慣用詞）轉換器。

        保留 ``opencc_s2tw`` 屬性名稱以相容既有呼叫端；實際使用較完整的
        ``s2twp`` profile。它在台灣字形之外，也會把「軟件／鼠標／信息」
        等地區詞彙轉成「軟體／滑鼠／資訊」。
        """
        if self._opencc_s2twp is None:
            try:
                from opencc import OpenCC
                self._opencc_s2twp = OpenCC('s2twp')
            except ImportError:
                raise ImportError("需要安装 opencc-python-reimplemented 来支持繁体转换")
        return self._opencc_s2twp

    @property
    def opencc_t2s(self):
        """懒加载 OpenCC 繁体转简体"""
        if self._opencc_t2s is None:
            try:
                from opencc import OpenCC
                self._opencc_t2s = OpenCC('t2s')
            except ImportError:
                raise ImportError("需要安装 opencc-python-reimplemented 来支持简体转换")
        return self._opencc_t2s

    def standardize_variant_chars(self, text: str) -> str:
        """標準化異體字，並移除 OOXML 控制字元轉義（_x0001_、_x000B_ 等雜訊）"""
        if not text:
            return text
        
        # 先移除 Word 殘留的控制字元轉義字串
        result = _OOXML_CONTROL_CHAR_RE.sub("", text)
        for variant, standard in self.variant_char_map.items():
            result = result.replace(variant, standard)
        return result
    
    def to_traditional(self, text: str) -> str:
        """轉成台灣正體繁體。

        來源內容可能是簡體，也可能是港式／舊式繁體（例如「隻能」「幹預」「裏面」
        「沖突」這類語意上過度轉換或港用字）。直接用 s2t/s2tw 無法修正「已是繁體」
        的港式用字（隻、幹 都是合法繁體字，只是語意用錯），因此採兩段式轉換：

        1. 先用 t2s 正規化成簡體 —— 讓 OpenCC 的片語字典處理語意歧義，
           例如「隻能」→「只能」、「幹預」→「干預」、「沖突」→「冲突」。
           合法的量詞「隻」（如「一隻貓」）會被片語字典保留。
        1.5 以 PUA 哨兵隔離「受保護詞彙」（``_PHRASE_PROTECT``）——
           防止 s2twp 台灣慣用詞字典把一般語義的詞劫持成 IT 術語
           （对象→物件、循环→迴圈、自性能→自效能…）。
        2. 再用 s2twp 轉成台灣正體與台灣慣用詞 —— 例如「裏」→「裡」、
           「软件」→「軟體」、「鼠标」→「滑鼠」。
        2.5 還原受保護詞彙為指定的台灣正體形式。
        2.6 收斂 OpenCC 片語字典覆蓋不全造成的同詞二形：
           唸→念（念佛／念經）、回向→迴向（大回向／回向給）。
        3. 修正 s2twp 對一簡多繁字的語境誤轉（OpenCC 既有缺陷，兩個套件皆然）：
           只／隻、發／髮、後／后、裡／里。
        4. 套用個別情境的人工修正（禪宗「那個一」、睡意「睏」、威音王後…）。
        5. 最後套用異體字／字詞標準化表收尾（補 s2tw 未涵蓋的港式異體字與誤轉詞）。
        """
        if not text:
            return text

        # 1. 正規化成簡體（消除港式繁體的語意歧義）
        simplified = self.opencc_t2s.convert(text)
        # 1.5 隔離受保護詞彙（PUA 哨兵）
        simplified, protected = self._protect_phrases(simplified)
        # 2. 簡體轉台灣正體繁體（含台灣慣用詞）
        traditional = self.opencc_s2tw.convert(simplified)
        # 2.5 還原受保護詞彙
        traditional = self._unprotect_phrases(traditional, protected)
        # 2.6 收斂同詞二形（唸→念；回向→迴向）
        traditional = self._fix_nian_recitation(traditional)
        traditional = self._fix_huixiang_dedication(traditional)
        # 3. 修正 s2twp 對一簡多繁字的語境誤轉
        traditional = self._fix_only_overconversion(traditional)   # 隻 → 只
        traditional = self._fix_digit_zhi_measure(traditional)     # 2只貓 → 2隻貓
        traditional = self._fix_fa_overconversion(traditional)     # 髮 → 發
        traditional = self._fix_hou_overconversion(traditional)    # 后 → 後
        traditional = self._fix_li_overconversion(traditional)     # 里 → 裡
        traditional = self._fix_yun_say_overconversion(traditional)  # 雲（說）→ 云
        traditional = self._fix_mian_overconversion(traditional)   # 麵（臉）→ 面
        # 4. 個別需人工判斷的情境修正
        traditional = self._apply_context_fixes(traditional)
        # 5. 標準化異體字與誤轉字詞
        return self.standardize_variant_chars(traditional)

    # ---- 受保護詞彙（PUA 哨兵隔離） ----

    @staticmethod
    def _protect_phrases(simplified: str):
        """把受保護詞彙換成 PUA 哨兵，回傳（隔離後文字，已用條目索引）。

        來源若天然含同號 PUA 字元則跳過該條（寧可少保護、不可還原錯亂）。
        """
        if not simplified:
            return simplified, []
        used = []
        for i, (src, _dst) in enumerate(_PHRASE_PROTECT):
            sentinel = chr(_PUA_PROTECT_BASE + i)
            if sentinel in simplified or src not in simplified:
                continue
            simplified = simplified.replace(src, sentinel)
            used.append(i)
        return simplified, used

    @staticmethod
    def _unprotect_phrases(traditional: str, used) -> str:
        """把 PUA 哨兵還原成指定的台灣正體形式（只還原確實使用過的條目）。"""
        if not traditional or not used:
            return traditional
        for i in used:
            traditional = traditional.replace(
                chr(_PUA_PROTECT_BASE + i), _PHRASE_PROTECT[i][1]
            )
        return traditional

    # ---- 同詞二形收斂 ----

    @staticmethod
    def _fix_nian_recitation(text: str) -> str:
        """統一「唸」為「念」（說明見 ``_NIAN_RECITE``）。"""
        if not text:
            return text
        return text.replace(*_NIAN_RECITE)

    @staticmethod
    def _fix_huixiang_dedication(text: str) -> str:
        """統一「回向」為「迴向」（說明見 ``_HUIXIANG_DEDICATION``）。"""
        if not text:
            return text
        return text.replace(*_HUIXIANG_DEDICATION)

    @staticmethod
    def _fix_digit_zhi_measure(text: str) -> str:
        """把阿拉伯數字後漏轉的量詞「只」改成「隻」（如 2只貓→2隻貓）。"""
        if "只" not in text:
            return text
        return _DIGIT_ZHI_MEASURE_RE.sub("隻", text)

    @staticmethod
    def _apply_context_fixes(text: str) -> str:
        """套用個別需人工判斷的整句／片語修正（詳見 ``_CONTEXT_FIXES``）。"""
        if not text:
            return text
        for wrong, right in _CONTEXT_FIXES.items():
            if wrong in text:
                text = text.replace(wrong, right)
        return text

    @staticmethod
    def _fix_only_overconversion(text: str) -> str:
        """把被 s2tw 過度轉換的量詞「隻」改回副詞「只」。

        詳見模組頂端 ``_ONLY_OVERCONVERT_RE`` 的說明。
        """
        if not text:
            return text
        return _ONLY_OVERCONVERT_RE.sub("只", text)

    @staticmethod
    def _fix_fa_overconversion(text: str) -> str:
        """把被 s2tw 過度轉換的「髮」（hair）改回「發」（emit/issue）。

        詳見模組頂端 ``_FA_FOLLOWER`` 等集合的說明。
        """
        if "髮" not in text:
            return text
        chars = list(text)
        n = len(chars)
        for i, ch in enumerate(chars):
            if ch != "髮":
                continue
            prev = chars[i - 1] if i > 0 else ""
            nxt = chars[i + 1] if i + 1 < n else ""
            if nxt in _FA_FOLLOWER or (
                prev not in _FA_HAIR_PREV and nxt not in _FA_HAIR_NEXT
            ):
                chars[i] = "發"
        return "".join(chars)

    @staticmethod
    def _fix_hou_overconversion(text: str) -> str:
        """把被 s2tw 漏轉的「后」（after）改成「後」。

        詳見模組頂端 ``_HOU_OVERCONVERT_RE`` 的說明。
        """
        if "后" not in text:
            return text
        return _HOU_OVERCONVERT_RE.sub("後", text)

    @staticmethod
    def _fix_li_overconversion(text: str) -> str:
        """把被 s2tw 漏轉的「里」（inside）改成「裡」。

        詳見模組頂端 ``_LI_INSIDE_RE`` 的說明。
        """
        if "里" not in text:
            return text
        return _LI_INSIDE_RE.sub("裡", text)

    @staticmethod
    def _fix_yun_say_overconversion(text: str) -> str:
        """把被 t2s → s2t 往返誤轉的「雲」（說）改回「云」。

        詳見模組頂端 ``_YUN_SAY_RE`` 的說明。
        """
        if "雲" not in text:
            return text
        return _YUN_SAY_RE.sub("云", text)

    @staticmethod
    def _fix_mian_overconversion(text: str) -> str:
        """把被 s2t 誤轉的臉義「麵」改回「面」。

        詳見模組頂端 ``_MIAN_FACE_RE`` 的說明。
        """
        if "麵" not in text:
            return text
        return _MIAN_FACE_RE.sub("面", text)

    def to_simplified(self, text: str) -> str:
        """繁體轉簡體。"""
        if not text:
            return text
        
        # 先標準化異體字（確保轉換前字符統一）
        standardized = self.standardize_variant_chars(text)
        
        for traditional, simplified in _SIMPLIFIED_WORD_NORMALIZATION.items():
            standardized = standardized.replace(traditional, simplified)
        return self.opencc_t2s.convert(standardized)
    
    def ensure_simplified(self, text: str) -> str:
        """確保文本完全是簡體字（強制轉換）"""
        if not text:
            return text
        
        # 無論輸入是什麼，都先轉成繁體再轉簡體，確保完全轉換。
        traditional = self.opencc_s2t.convert(text)
        standardized = self.standardize_variant_chars(traditional)
        for taiwan_word, mainland_word in _SIMPLIFIED_WORD_NORMALIZATION.items():
            standardized = standardized.replace(taiwan_word, mainland_word)
        return self.opencc_t2s.convert(standardized)
    
    def get_traditional_filename(self, filename: str) -> str:
        """获取繁体版文件名"""
        return filename.replace(".html", "_trad.html")
    
    def get_simplified_filename(self, filename: str) -> str:
        """获取简体版文件名"""
        return filename.replace("_trad.html", ".html")
    
    def is_traditional_filename(self, filename: str) -> bool:
        """检查是否为繁体文件名"""
        return "_trad.html" in filename