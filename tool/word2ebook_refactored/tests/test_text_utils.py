"""文本处理工具测试"""

import pytest
from utils.text_utils import TextProcessor, IDGenerator, normalize_text_for_id, simple_hash
from config.settings import Settings


class TestTextProcessor:
    """文本处理器测试"""
    
    def setup_method(self):
        """测试前的设置"""
        self.settings = Settings()
        self.processor = TextProcessor(self.settings)
    
    def test_process_line_breaks(self):
        """测试换行处理"""
        # 测试基本换行转换
        text = "第一行\n第二行\r\n第三行"
        result = self.processor.process_line_breaks(text)
        expected = "第一行<br>第二行<br>第三行"
        assert result == expected
    
    def test_extract_time_from_text(self):
        """测试时间提取"""
        # 测试完整时间格式
        text = "2024-02-18 10:47 这是问题内容"
        time_info, remaining = self.processor.extract_time_from_text(text)
        assert time_info == "2024-02-18 10:47"
        assert remaining == "这是问题内容"
        
        # 测试无时间情况
        text = "这是没有时间的内容"
        time_info, remaining = self.processor.extract_time_from_text(text)
        assert time_info is None
        assert remaining == "这是没有时间的内容"
    
    def test_extract_questioner_info(self):
        """测试提问者信息提取"""
        # 测试正常格式
        text = "张三：这是问题内容"
        questioner, content = self.processor.extract_questioner_info(text)
        assert questioner == "张三"
        assert content == "这是问题内容"
        
        # 测试无提问者格式
        text = "这只是普通文本"
        questioner, content = self.processor.extract_questioner_info(text)
        assert questioner is None
        assert content == "这只是普通文本"
    
    def test_clean_text(self):
        """测试文本清理"""
        text = "  这是   有多余   空格的   文本  "
        result = self.processor.clean_text(text)
        assert result == "这是 有多余 空格的 文本"


class TestIDGenerator:
    """ID生成器测试"""
    
    def setup_method(self):
        """测试前的设置"""
        self.settings = Settings()
        self.generator = IDGenerator(self.settings)
    
    def test_generate_stable_qa_id(self):
        """测试稳定问答ID生成"""
        # 相同输入应产生相同ID
        id1 = self.generator.generate_stable_qa_id("张三", "问题内容", "2024-02-18", "question")
        id2 = self.generator.generate_stable_qa_id("张三", "问题内容", "2024-02-18", "question")
        assert id1 == id2
        
        # 不同输入应产生不同ID
        id3 = self.generator.generate_stable_qa_id("李四", "问题内容", "2024-02-18", "question")
        assert id1 != id3
    
    def test_generate_content_id(self):
        """测试内容ID生成"""
        id1 = self.generator.generate_content_id("测试内容", "content")
        assert id1.startswith("content-")
        assert len(id1) == 16  # "content-" + 8位hash


class TestUtilityFunctions:
    """工具函数测试"""
    
    def test_normalize_text_for_id(self):
        """测试文本标准化"""
        text = "  测试\n内容\r\n带有\t制表符  "
        result = normalize_text_for_id(text)
        assert result == "测试 内容 带有 制表符"
    
    def test_simple_hash(self):
        """测试简单hash函数"""
        text = "测试文本"
        hash_result = simple_hash(text)
        assert len(hash_result) == 12
        assert isinstance(hash_result, str)
        
        # 相同输入产生相同hash
        hash_result2 = simple_hash(text)
        assert hash_result == hash_result2