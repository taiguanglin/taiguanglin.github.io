"""国际化工具"""

from typing import Optional


class I18nProcessor:
    """国际化处理器"""
    
    def __init__(self):
        self._opencc_s2t = None
        self._opencc_t2s = None
        
        # 異體字標準化對照表
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
        """简体转繁体"""
        if not text:
            return text
        
        # 先進行簡體轉繁體
        converted = self.opencc_s2t.convert(text)
        
        # 然後標準化異體字
        return self.standardize_variant_chars(converted)
    
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