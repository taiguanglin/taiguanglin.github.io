"""配置管理"""

from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class Settings:
    """程序配置类"""
    
    # 文档处理配置
    preserve_line_breaks: bool = True
    merge_qa_blocks: bool = True
    extract_images: bool = True
    
    # 搜索配置
    search_results_per_page: int = 20
    search_context_length: int = 80
    search_min_paragraph_length: int = 20
    
    # HTML 生成配置
    enable_back_to_top: bool = True
    enable_reading_toolbar: bool = True
    enable_floating_toc: bool = True
    
    # 多语言配置
    default_answerer: str = "Taiguanglin"
    
    # ID 生成配置
    id_content_length: int = 50  # 用于生成稳定ID的内容长度
    
    # 文件配置
    assets_css_path: str = "assets/css/style.css"
    assets_js_path: str = "assets/js/script.js"
    assets_images_path: str = "assets/images"
    
    # Favicon 配置
    favicon_enabled: bool = True
    favicon_search_patterns: List[str] = None
    
    def __post_init__(self):
        if self.favicon_search_patterns is None:
            # 嘗試從配置文件讀取
            try:
                from utils.config_utils import get_favicon_config
                self.favicon_enabled = get_favicon_config('enabled', True)
                self.favicon_search_patterns = get_favicon_config('search_patterns', ["favicon.ico", "favicon.png", "favicon.svg"])
            except ImportError:
                # 如果配置工具不可用，使用默認值
                self.favicon_search_patterns = ["favicon.ico", "favicon.png", "favicon.svg"]
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'Settings':
        """从字典创建配置对象"""
        return cls(**{k: v for k, v in config.items() if hasattr(cls, k)})
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            field.name: getattr(self, field.name) 
            for field in self.__dataclass_fields__.values()
        }


# 默认配置
DEFAULT_SETTINGS = Settings()


# 常量定义
class Constants:
    """常量定义"""
    
    # HTML 模板占位符
    TEMPLATE_PLACEHOLDERS = {
        'title': '{title}',
        'content': '{content}',
        'book_title': '{book_title}',
        'toc_items': '{toc_items}',
        'chapter_toc': '{chapter_toc}',
        'prev_link': '{prev_link}',
        'next_link': '{next_link}',
        'top_nav_links': '{top_nav_links}',
        'home_link': '{home_link}',
        'lang_switch_links': '{lang_switch_links}'
    }
    
    # 文件扩展名
    HTML_EXT = '.html'
    TRAD_SUFFIX = '_trad'
    JSON_EXT = '.json'
    
    # 搜索索引文件名
    SEARCH_INDEX_SIMPLIFIED = 'search_index.json'
    SEARCH_INDEX_TRADITIONAL = 'search_index_trad.json'
    
    # MiniSearch 索引文件名
    MINISEARCH_INDEX_SIMPLIFIED = 'minisearch_index.json'
    MINISEARCH_INDEX_TRADITIONAL = 'minisearch_index_trad.json'
    
    # CDN 配置
    MINISEARCH_CDN_PRIMARY = 'https://cdn.jsdelivr.net/npm/minisearch@6.3.0/dist/umd/index.min.js'
    MINISEARCH_CDN_BACKUP = 'https://unpkg.com/minisearch@6.3.0/dist/umd/index.min.js'
    
    # 问答类型标识
    QA_TYPES = {
        'question': 'question',
        'answer': 'answer',
        'qa_pair': 'qa-pair'
    }
    
    # 搜索项类型
    SEARCH_TYPES = {
        'heading': 'heading',
        'question': 'question', 
        'answer': 'answer',
        'content': 'content'
    }
    
    # 搜索权重
    SEARCH_WEIGHTS = {
        'h1': 4.0,
        'h2': 3.0,
        'h3': 2.0,
        'h4': 2.0,
        'question': 3.0,
        'answer': 2.0,
        'content': 1.0
    }