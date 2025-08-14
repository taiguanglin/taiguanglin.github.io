"""中文分词工具"""

import re
from typing import List, Optional


class ChineseSegmenter:
    """中文分词器，使用 jieba 进行分词"""
    
    def __init__(self):
        self._jieba = None
        self._initialized = False
    
    @property
    def jieba(self):
        """懒加载 jieba"""
        if self._jieba is None:
            try:
                import jieba
                # 设置为静默模式，避免输出初始化信息
                jieba.setLogLevel(20)
                self._jieba = jieba
                self._initialized = True
            except ImportError:
                raise ImportError("需要安装 jieba 来支持中文分词: pip install jieba")
        return self._jieba
    
    def segment_text(self, text: str, use_hmm: bool = True) -> str:
        """
        对文本进行分词，返回用空格分隔的词汇字符串
        
        Args:
            text: 待分词的文本
            use_hmm: 是否使用 HMM 模型识别新词
            
        Returns:
            用空格分隔的分词结果字符串
        """
        if not text or not isinstance(text, str):
            return ""
        
        # 使用 jieba 进行分词
        words = list(self.jieba.cut(text.strip(), HMM=use_hmm))
        
        # 过滤和清理分词结果
        filtered_words = []
        for word in words:
            word = word.strip()
            if word and len(word) > 0:
                # 保留中文词汇、英文单词、数字
                if self._is_meaningful_word(word):
                    filtered_words.append(word)
        
        return " ".join(filtered_words)
    
    def segment_content_and_title(self, title: str, content: str) -> tuple[str, str]:
        """
        同时对标题和内容进行分词
        
        Args:
            title: 标题文本
            content: 内容文本
            
        Returns:
            (title_tokens, content_tokens) 元组
        """
        title_tokens = self.segment_text(title) if title else ""
        content_tokens = self.segment_text(content) if content else ""
        
        return title_tokens, content_tokens
    
    def _is_meaningful_word(self, word: str) -> bool:
        """
        判断词汇是否有意义（过滤标点符号等）
        
        Args:
            word: 待判断的词汇
            
        Returns:
            是否为有意义的词汇
        """
        # 过滤纯标点符号
        if re.match(r'^[^\w\u4e00-\u9fff]+$', word):
            return False
        
        # 过滤单个字符的标点或符号（但保留单个中文字符）
        if len(word) == 1:
            # 保留中文字符、英文字母、数字
            return bool(re.match(r'[\w\u4e00-\u9fff]', word))
        
        # 保留包含中文、英文、数字的词汇
        return bool(re.search(r'[\w\u4e00-\u9fff]', word))
    
    def is_available(self) -> bool:
        """检查 jieba 是否可用"""
        try:
            _ = self.jieba
            return self._initialized
        except ImportError:
            return False


# 全局分词器实例
_segmenter_instance: Optional[ChineseSegmenter] = None


def get_segmenter() -> ChineseSegmenter:
    """获取全局分词器实例"""
    global _segmenter_instance
    if _segmenter_instance is None:
        _segmenter_instance = ChineseSegmenter()
    return _segmenter_instance


def segment_text(text: str) -> str:
    """便捷函数：对文本进行分词"""
    return get_segmenter().segment_text(text)


def is_segmenter_available() -> bool:
    """检查分词器是否可用"""
    try:
        return get_segmenter().is_available()
    except ImportError:
        return False
