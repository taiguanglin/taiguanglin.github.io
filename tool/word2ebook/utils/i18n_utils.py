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

# 數量詞（出現在量詞「隻」前面 → 視為真正的量詞，不修改）
_MEASURE_PREFIX = "一二三四五六七八九十兩零百千萬億幾數壹貳參肆伍陸柒捌玖拾０１２３４５６７８９0123456789"

# 副詞「只」常見的後接字（動詞／助動詞／繫詞／副詞）。刻意排除名詞，避免誤判量詞。
_ONLY_FOLLOWER = (
    "能會要可得想須應該肯願是有好不在知道說講念唸寫認看去下度吃喝給做求等待差欠"
    "顧管剩怕見為留談聽針受跟提叫過關放思接穿傳夠允動信走用把將顯對供選挑問答"
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
_QUEEN_NEXT = "土羿稷冠宮娘妃主座裔"
_HOU_OVERCONVERT_RE = re.compile(
    r"(?<![" + _QUEEN_PREV + r"])后(?![" + _QUEEN_NEXT + r"])"
)

# ---------------------------------------------------------------------------
# 修正 s2tw 把「裡」（inside，里）漏轉、保留成「里」的錯誤。
# s2tw 對「這裡、心裡、手裡」轉換正確，但在片語後（劇本里、知道里面、六道里、
# 視角里…）會保留簡體「里」。下列前綴後的「里」一律是「裡面」之意，改成「裡」。
# 真正的「里」（公里、千里、鄰里、斯里蘭卡等音譯／距離詞）前綴不在此集合，保留。
# ---------------------------------------------------------------------------
_LI_INSIDE_PREV = "本道會角方場子迴穴識經向"
_LI_INSIDE_RE = re.compile(r"(?<=[" + _LI_INSIDE_PREV + r"])里")

# 需人工判斷的個別情境（通用規則無法自動判斷者）。
# 1.「一歸何處，那一隻能回到自性」中的「一」是禪宗的「那個一」（代詞），
#    語意是「只能」；但通用規則因前一字是數字「一」而保留「隻」，故特別修正。
#    以「回到自性」為語意錨點，確保不誤改真正的量詞用法（如「這一隻能飛」）。
# 2.「反而你現在困才是更大的問題」中的「困」是「睏」（睡意），非「受困」之困；
#    s2tw 無從分辨，以整句錨點修正成「睏」。
_CONTEXT_FIXES = {
    "一隻能回到自性": "一只能回到自性",
    "現在困才是": "現在睏才是",
}

# ---------------------------------------------------------------------------
# 移除 OOXML（Word）控制字元轉義。
# Word 在寫入 .docx 時，會把無法以 XML 表示的控制字元（C0 控制碼 0x00–0x1F 與
# DEL 0x7F）轉義成形如「_x0001_」「_x000B_」的字串，python-docx 會原樣讀出。
# 這些都是無意義的雜訊字元，一律取代成空字串。
# 注意：可列印字元的轉義（例如底線本身 _x005F_、字母 _x0041_）不在此範圍，
# 予以保留，以免誤刪內文。
# ---------------------------------------------------------------------------
_OOXML_CONTROL_CHAR_RE = re.compile(r"_x00[01][0-9A-Fa-f]_|_x007[Ff]_")


class I18nProcessor:
    """国际化处理器"""
    
    def __init__(self):
        self._opencc_s2t = None
        self._opencc_s2tw = None
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
            # 「信息」在台灣已通用且看得懂，統一保留「信息」，不改成台灣慣用語「資訊」。
            # （s2tw 本就保留「信息」，此處再把來源中少數「资讯→資訊」一併歸一為「信息」。）
            "資訊": "信息",
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
        """懒加载 OpenCC 简体转台湾正体繁体"""
        if self._opencc_s2tw is None:
            try:
                from opencc import OpenCC
                self._opencc_s2tw = OpenCC('s2tw')
            except ImportError:
                raise ImportError("需要安装 opencc-python-reimplemented 来支持繁体转换")
        return self._opencc_s2tw

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
        2. 再用 s2tw 轉成台灣正體 —— 例如「裏」→「裡」、「冲突」→「衝突」。
        3. 修正 s2tw 對一簡多繁字的語境誤轉（OpenCC 既有缺陷，兩個套件皆然）：
           只／隻、發／髮、後／后、裡／里。
        4. 套用個別情境的人工修正（禪宗「那個一」、睡意「睏」等）。
        5. 最後套用異體字／字詞標準化表收尾（補 s2tw 未涵蓋的港式異體字與誤轉詞）。
        """
        if not text:
            return text

        # 1. 正規化成簡體（消除港式繁體的語意歧義）
        simplified = self.opencc_t2s.convert(text)
        # 2. 簡體轉台灣正體繁體
        traditional = self.opencc_s2tw.convert(simplified)
        # 3. 修正 s2tw 對一簡多繁字的語境誤轉
        traditional = self._fix_only_overconversion(traditional)   # 隻 → 只
        traditional = self._fix_fa_overconversion(traditional)     # 髮 → 發
        traditional = self._fix_hou_overconversion(traditional)    # 后 → 後
        traditional = self._fix_li_overconversion(traditional)     # 里 → 裡
        # 4. 個別需人工判斷的情境修正
        traditional = self._apply_context_fixes(traditional)
        # 5. 標準化異體字與誤轉字詞
        return self.standardize_variant_chars(traditional)

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
    
    def to_simplified(self, text: str) -> str:
        """繁体转简体"""
        if not text:
            return text
        
        # 先標準化異體字（確保轉換前字符統一）
        standardized = self.standardize_variant_chars(text)
        
        # 然後進行繁體轉簡體
        return self.opencc_t2s.convert(standardized)
    
    def ensure_simplified(self, text: str) -> str:
        """確保文本完全是簡體字（強制轉換）"""
        if not text:
            return text
        
        # 無論輸入是什麼，都先轉成繁體再轉簡體，確保完全轉換
        traditional = self.opencc_s2t.convert(text)
        standardized = self.standardize_variant_chars(traditional)
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