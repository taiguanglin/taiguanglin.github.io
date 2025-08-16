"""文档数据模型定义"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
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
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 JSON 序列化）"""
        result = {
            'id': self.id,
            'title': self.title,
            'type': self.type,
            'content': self.content,
            'url': self.url
        }
        
        # 只有當 context 與 content 不同時才添加 context 字段
        if self.context != self.content:
            result['context'] = self.context
            
        return result


@dataclass
class QACountItem:
    """問答計數項目"""
    anchor: str
    level: int
    direct_qa_count: int  # 直接問答數量（葉子節點）
    total_qa_count: int = 0  # 總問答數量（包含子節點）
    is_leaf: bool = True  # 是否為葉子節點


@dataclass
class QACountMetadata:
    """問答計數元數據"""
    chapter_filename: str
    counts: Dict[str, QACountItem] = field(default_factory=dict)  # anchor -> QACountItem
    toc_structure: List[Tuple[int, str, str]] = field(default_factory=list)  # (level, text, anchor)
    
    def add_leaf_count(self, anchor: str, level: int, qa_count: int) -> None:
        """添加葉子節點的問答計數"""
        self.counts[anchor] = QACountItem(
            anchor=anchor,
            level=level,
            direct_qa_count=qa_count,
            total_qa_count=qa_count,
            is_leaf=True
        )
    
    def calculate_parent_counts(self) -> None:
        """計算父節點的問答計數"""
        # 首先標記所有非葉子節點
        for i, (level, text, anchor) in enumerate(self.toc_structure):
            # 檢查是否有子節點
            has_children = False
            for j in range(i + 1, len(self.toc_structure)):
                next_level = self.toc_structure[j][0]
                if next_level <= level:
                    break
                if next_level == level + 1:
                    has_children = True
                    break
            
            if has_children and anchor not in self.counts:
                # 這是一個父節點，需要計算其總計數
                self.counts[anchor] = QACountItem(
                    anchor=anchor,
                    level=level,
                    direct_qa_count=0,
                    total_qa_count=0,
                    is_leaf=False
                )
        
        # 計算每個父節點的總計數
        for i, (level, text, anchor) in enumerate(self.toc_structure):
            if anchor in self.counts and not self.counts[anchor].is_leaf:
                total_count = 0
                # 找到所有直接子節點
                for j in range(i + 1, len(self.toc_structure)):
                    child_level, child_text, child_anchor = self.toc_structure[j]
                    if child_level <= level:
                        break
                    if child_level == level + 1 and child_anchor in self.counts:
                        total_count += self.counts[child_anchor].total_qa_count
                
                self.counts[anchor].total_qa_count = total_count
    
    def get_count_for_anchor(self, anchor: str) -> int:
        """獲取指定anchor的問答計數"""
        if anchor in self.counts:
            return self.counts[anchor].total_qa_count
        return 0


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
    qa_count_metadata: Optional[QACountMetadata] = None
    
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
    generate_simplified: bool = True
    enable_qa_count: bool = True
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
    
    def get_book_title(self, is_traditional: bool = False) -> str:
        """獲取電子書標題，優先使用配置文件中的設定
        
        Args:
            is_traditional: 是否為繁體版
            
        Returns:
            電子書標題
        """
        try:
            # 導入配置管理器（延遲導入避免循環依賴）
            from utils.config_utils import get_book_title
            
            # 優先使用配置文件中的標題，如果沒有則使用當前設定的書名
            config_title = get_book_title(is_traditional, "")
            if config_title:
                return config_title
            else:
                return self.book_title or self.input_file.stem
                
        except ImportError:
            # 如果配置工具不可用，使用默認邏輯
            return self.book_title or self.input_file.stem