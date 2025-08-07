"""数据模型测试"""

import pytest
from pathlib import Path
from models.document_models import Chapter, QAPair, SearchItem, TOCItem, ConversionConfig


class TestChapter:
    """章节模型测试"""
    
    def test_chapter_creation(self):
        """测试章节创建"""
        chapter = Chapter(title="测试章节", filename="test.html")
        assert chapter.title == "测试章节"
        assert chapter.filename == "test.html"
        assert chapter.content == ""
        assert len(chapter.toc_items) == 0
    
    def test_safe_title(self):
        """测试安全标题（移除HTML标签）"""
        chapter = Chapter(title="<h1>测试章节</h1>", filename="test.html")
        assert chapter.safe_title == "测试章节"
    
    def test_traditional_filename(self):
        """测试繁体文件名"""
        chapter = Chapter(title="测试章节", filename="test.html")
        assert chapter.traditional_filename == "test_trad.html"
    
    def test_add_toc_item(self):
        """测试添加目录项"""
        chapter = Chapter(title="测试章节", filename="test.html")
        chapter.add_toc_item(2, "子标题", "anchor")
        
        assert len(chapter.toc_items) == 1
        assert chapter.toc_items[0].level == 2
        assert chapter.toc_items[0].text == "子标题"
        assert chapter.toc_items[0].anchor == "anchor"


class TestQAPair:
    """问答对模型测试"""
    
    def test_qapair_creation(self):
        """测试问答对创建"""
        qa = QAPair(
            question_id="q1",
            answer_id="a1",
            questioner="张三",
            question_text="这是问题",
            answer_text="这是回答"
        )
        
        assert qa.questioner == "张三"
        assert qa.answerer == "Taiguanglin"  # 默认值
        assert qa.question_text == "这是问题"
        assert qa.answer_text == "这是回答"
    
    def test_to_html(self):
        """测试转换为HTML"""
        qa = QAPair(
            question_id="q1",
            answer_id="a1",
            questioner="张三",
            question_text="这是问题",
            answer_text="这是回答",
            time_info="2024-01-01"
        )
        
        html = qa.to_html()
        assert 'class="question"' in html
        assert 'class="answer"' in html
        assert "张三" in html
        assert "这是问题" in html
        assert "这是回答" in html
        assert "2024-01-01" in html


class TestSearchItem:
    """搜索项模型测试"""
    
    def test_searchitem_creation(self):
        """测试搜索项创建"""
        item = SearchItem(
            id="test1",
            title="测试标题",
            type="heading",
            content="测试内容",
            context="测试上下文",
            url="test.html#anchor",
            weight=3.0
        )
        
        assert item.id == "test1"
        assert item.title == "测试标题"
        assert item.weight == 3.0
    
    def test_to_dict(self):
        """测试转换为字典"""
        item = SearchItem(
            id="test1",
            title="测试标题",
            type="heading",
            content="测试内容",
            context="测试上下文",
            url="test.html#anchor",
            weight=3.0
        )
        
        data = item.to_dict()
        assert data["id"] == "test1"
        assert data["title"] == "测试标题"
        assert data["weight"] == 3.0


class TestConversionConfig:
    """转换配置模型测试"""
    
    def test_config_creation(self):
        """测试配置创建"""
        config = ConversionConfig(
            input_file="input.docx",
            output_folder="output"
        )
        
        assert isinstance(config.input_file, Path)
        assert isinstance(config.output_folder, Path)
        assert config.generate_search is True  # 默认值
        assert config.generate_traditional is True  # 默认值
    
    def test_book_title_auto_generation(self):
        """测试书名自动生成"""
        config = ConversionConfig(
            input_file="test_book.docx",
            output_folder="output"
        )
        
        assert config.book_title == "test_book"