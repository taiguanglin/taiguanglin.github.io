"""文档数据模型定义"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class TOCItem:
    """目录项数据模型"""
    level: int
    text: str
    anchor: str


@dataclass
class QAPair:
    """问答对数据模型"""
    question_id: str
    answer_id: str
    questioner: str
    answerer: str = "Taiguanglin"
    question_text: str = ""
    answer_text: str = ""
    time_info: Optional[str] = None
    
    def to_html(self) -> str:
        """转换为 HTML 格式"""
        question_html = self._generate_question_html()
        answer_html = self._generate_answer_html()
        return f"{question_html}\n{answer_html}"
    
    def _generate_question_html(self) -> str:
        """生成问题的 HTML"""
        time_html = f'<span class="question-time">{self.time_info}</span>' if self.time_info else ''
        
        return f'''<div class="question" id="{self.question_id}">
    <div class="question-meta">
        <span class="questioner">{self.questioner}</span>
        {time_html}
    </div>
    <div class="question-text">{self.question_text}</div>
</div>'''
    
    def _generate_answer_html(self) -> str:
        """生成回答的 HTML"""
        return f'''<div class="answer" id="{self.answer_id}">
    <div class="answer-meta">
        <span class="answerer">{self.answerer}</span>
    </div>
    <div class="answer-text">{self.answer_text}</div>
</div>'''


@dataclass
class SearchItem:
    """搜索项数据模型"""
    id: str
    title: str
    type: str  # 'heading', 'question', 'answer', 'content'
    content: str
    context: str
    url: str
    weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 JSON 序列化）"""
        return {
            'id': self.id,
            'title': self.title,
            'type': self.type,
            'content': self.content,
            'context': self.context,
            'url': self.url,
            'weight': self.weight
        }


@dataclass
class Chapter:
    """章节数据模型"""
    title: str
    filename: str
    content: str = ""
    chapter_toc: str = ""
    toc_items: List[TOCItem] = field(default_factory=list)
    qa_pairs: List[QAPair] = field(default_factory=list)
    search_items: List[SearchItem] = field(default_factory=list)
    
    @property
    def safe_title(self) -> str:
        """获取安全的标题（移除 HTML 标签）"""
        import re
        return re.sub(r"<.*?>", "", self.title)
    
    @property
    def traditional_filename(self) -> str:
        """获取繁体版文件名"""
        return self.filename.replace(".html", "_trad.html")
    
    def add_toc_item(self, level: int, text: str, anchor: str) -> None:
        """添加目录项"""
        self.toc_items.append(TOCItem(level=level, text=text, anchor=anchor))
    
    def add_qa_pair(self, qa_pair: QAPair) -> None:
        """添加问答对"""
        self.qa_pairs.append(qa_pair)
    
    def add_search_item(self, search_item: SearchItem) -> None:
        """添加搜索项"""
        self.search_items.append(search_item)


@dataclass
class ConversionConfig:
    """转换配置数据模型"""
    input_file: Path
    output_folder: Path
    generate_search: bool = True
    generate_traditional: bool = True
    book_title: Optional[str] = None
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保路径是 Path 对象
        if not isinstance(self.input_file, Path):
            self.input_file = Path(self.input_file)
        if not isinstance(self.output_folder, Path):
            self.output_folder = Path(self.output_folder)
        
        # 如果没有指定书名，从文件名获取
        if self.book_title is None:
            self.book_title = self.input_file.stem