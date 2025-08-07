"""国际化工具"""

from typing import Optional


class I18nProcessor:
    """国际化处理器"""
    
    def __init__(self):
        self._opencc = None
    
    @property
    def opencc(self):
        """懒加载 OpenCC"""
        if self._opencc is None:
            try:
                from opencc import OpenCC
                self._opencc = OpenCC('s2t')
            except ImportError:
                raise ImportError("需要安装 opencc-python-reimplemented 来支持繁体转换")
        return self._opencc
    
    def to_traditional(self, text: str) -> str:
        """简体转繁体"""
        if not text:
            return text
        
        # 转换并修复特定字符
        converted = self.opencc.convert(text)
        return converted.replace("喫", "吃")
    
    def get_traditional_filename(self, filename: str) -> str:
        """获取繁体版文件名"""
        return filename.replace(".html", "_trad.html")
    
    def get_simplified_filename(self, filename: str) -> str:
        """获取简体版文件名"""
        return filename.replace("_trad.html", ".html")
    
    def is_traditional_filename(self, filename: str) -> bool:
        """检查是否为繁体文件名"""
        return "_trad.html" in filename