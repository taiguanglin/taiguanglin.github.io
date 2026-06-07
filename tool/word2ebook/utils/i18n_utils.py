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
            "_x000B_": "",  # 將 _x000B_ 字符串替換為換行符
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
        """標準化異體字"""
        if not text:
            return text
        
        result = text
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
        3. 最後套用異體字標準化表收尾（補 s2tw 未涵蓋的港式異體字）。
        """
        if not text:
            return text

        # 1. 正規化成簡體（消除港式繁體的語意歧義）
        simplified = self.opencc_t2s.convert(text)
        # 2. 簡體轉台灣正體繁體
        traditional = self.opencc_s2tw.convert(simplified)
        # 3. 修正 s2tw 把副詞「只」過度轉成量詞「隻」的錯誤
        traditional = self._fix_only_overconversion(traditional)
        # 4. 標準化異體字
        return self.standardize_variant_chars(traditional)

    def _fix_only_overconversion(self, text: str) -> str:
        """把被 s2tw 過度轉換的量詞「隻」改回副詞「只」。

        詳見模組頂端 ``_ONLY_OVERCONVERT_RE`` 的說明。
        """
        if not text:
            return text
        return _ONLY_OVERCONVERT_RE.sub("只", text)
    
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