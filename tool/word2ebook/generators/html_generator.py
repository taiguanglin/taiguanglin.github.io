"""HTML 生成器"""

import re
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

from models.document_models import Chapter, TOCItem
from templates.html_templates import TemplateManager
from templates.i18n_templates import I18nTemplateManager
from utils.file_utils import FileManager
from utils.i18n_utils import I18nProcessor
from utils.config_utils import get_i18n_text
from utils.favicon_utils import FaviconManager
from config.settings import Settings


class TOCGenerator:
    """目录生成器"""
    
    def build_chapter_toc(self, toc_items: List[Tuple[int, str, str]], filename: Optional[str] = None) -> str:
        """将 (level, text, anchor) 结构转成巢状 <ul>"""
        if not toc_items:
            return "<ul></ul>"
            
        html = "<ul>\n"
        prev_level = 2
        
        for level, text, anchor in toc_items:
            link = f'{filename}#{anchor}' if filename else f'#{anchor}'
            if level > prev_level:
                html += "<ul>\n" * (level - prev_level)
            elif level < prev_level:
                html += "</ul>\n" * (prev_level - level)
            html += f'<li><a href="{link}">{text}</a></li>\n'
            prev_level = level
            
        while prev_level > 2:
            html += "</ul>\n"
            prev_level -= 1
        html += "</ul>"
        return html
    
    def build_collapsible_chapter_toc(self, toc_items: List[Tuple[int, str, str]], filename: Optional[str] = None) -> str:
        """构建可折叠的章节目录（扁平化结构，便于JavaScript控制）"""
        if not toc_items:
            return "<ul></ul>"
            
        # 分析结构，找出每个项目是否有子项
        items_with_children = set()
        for i, (level, text, anchor) in enumerate(toc_items):
            # 检查下一项是否是更深层级
            if i + 1 < len(toc_items) and toc_items[i + 1][0] > level:
                items_with_children.add(i)
                
        html = "<ul>\n"
        
        for i, (level, text, anchor) in enumerate(toc_items):
            link = f'{filename}#{anchor}' if filename else f'#{anchor}'
            
            # 添加折叠控制图标
            expand_icon = ""
            if i in items_with_children:
                expand_icon = f'<span class="toc-expand-icon" data-level="{level}">▼</span>'
            
            # 生成扁平化的li元素，通过CSS和JavaScript控制层级显示
            html += f'<li class="toc-item toc-level-{level}" data-level="{level}" data-default-visible="{level <= 2}">'
            html += f'{expand_icon}<a href="{link}">{text}</a></li>\n'
        
        html += "</ul>"
        return html
    
    def build_index_toc(self, chapters: List[Chapter], is_traditional: bool = False) -> str:
        """建立首页目录"""
        html = "<ul class='toc-level-1'>\n"
        
        for ch in chapters:
            filename = ch.filename
            if is_traditional:
                filename = filename.replace(".html", "_trad.html")
            
            # 检查这个章节是否有子项
            has_children = bool(ch.toc_items)
            expand_icon = ""
            if has_children:
                expand_icon = '<span class="toc-expand-icon" data-level="1">▼</span>'
            
            html += f'<li class="toc-item toc-chapter" data-level="1" data-default-visible="true">'
            html += f'{expand_icon}<a href="{filename}">{ch.title}</a>\n'
            
            if ch.toc_items:
                # 转换 TOCItem 对象为元组
                toc_tuples = [(item.level, item.text, item.anchor) for item in ch.toc_items]
                html += self.build_collapsible_chapter_toc(toc_tuples, filename)
            html += "</li>\n"
        html += "</ul>"
        return html


class HTMLGenerator:
    """HTML 生成器"""
    
    def __init__(self, settings: Settings, file_manager: FileManager, input_file: Optional[Path] = None):
        self.settings = settings
        self.file_manager = file_manager
        self.template_manager = TemplateManager()
        self.i18n_template_manager = I18nTemplateManager()
        self.toc_generator = TOCGenerator()
        self.i18n_processor = I18nProcessor()
        self.input_file = input_file
        self.favicon_manager = None
        self.favicon_tag = ""
        
        # 初始化favicon管理器（但先不處理，等目錄設置完成後）
        if input_file and settings.favicon_enabled:
            self.favicon_manager = FaviconManager(
                input_file, 
                file_manager.output_folder,
                settings.favicon_search_patterns
            )
            # 只找文件，不複製
            self.favicon_manager.find_favicon()
            self.favicon_tag = self.favicon_manager.get_favicon_html_tag()
    
    def copy_favicon_after_setup(self) -> None:
        """在目錄設置完成後複製favicon文件"""
        if self.favicon_manager:
            self.favicon_manager.copy_favicon_to_output()
    
    def _process_i18n_placeholders(self, content: str, is_traditional: bool) -> str:
        """處理內容中的國際化佔位符"""
        # 替換回到本章目錄的佔位符
        back_to_chapter_toc = get_i18n_text('ui.back_to_chapter_toc', is_traditional, '回到本章目錄')
        content = content.replace('{{back_to_chapter_toc}}', back_to_chapter_toc)
        
        # 可以在此添加其他佔位符的處理
        # content = content.replace('{{other_placeholder}}', other_text)
        
        return content
    
    def generate_chapter_pages(self, chapters: List[Chapter], generate_traditional: bool = True) -> None:
        """生成章节页面"""
        # 生成简体版
        self._generate_simplified_chapters(chapters)
        
        # 生成繁体版
        if generate_traditional:
            self._generate_traditional_chapters(chapters)
    
    def generate_index_pages(self, chapters: List[Chapter], config, 
                           generate_traditional: bool = True) -> None:
        """生成首页"""
        # 生成简体版首页
        simplified_title = config.get_book_title(is_traditional=False)
        self._generate_simplified_index(chapters, simplified_title)
        
        # 生成繁体版首页
        if generate_traditional:
            traditional_title = config.get_book_title(is_traditional=True)
            self._generate_traditional_index(chapters, traditional_title)
    
    def _generate_simplified_chapters(self, chapters: List[Chapter]) -> None:
        """生成简体版章节"""
        for i, chapter in enumerate(chapters):
            # 生成导航链接
            nav_data = self._generate_navigation_data(chapters, i, is_traditional=False)
            
            # 语言切换链接
            lang_switch_links = self._generate_lang_switch_links(chapter.filename, is_traditional=False)
            
            # 處理內容中的國際化佔位符
            processed_content = self._process_i18n_placeholders(chapter.content, is_traditional=False)
            
            # 渲染页面
            html_content = self.i18n_template_manager.render_chapter(
                is_traditional=False,
                title=chapter.title,
                chapter_toc=chapter.chapter_toc,
                content=processed_content,
                prev_link=nav_data['prev_link'],
                next_link=nav_data['next_link'],
                top_nav_links=nav_data['top_nav_links'],
                home_link="index.html",
                lang_switch_links=lang_switch_links,
                favicon_tag=self.favicon_tag
            )
            
            # 写入文件
            self.file_manager.write_file(chapter.filename, html_content)
    
    def _generate_traditional_chapters(self, chapters: List[Chapter]) -> None:
        """生成繁体版章节"""
        print("🈴 正在生成繁體版...")
        
        for i, chapter in enumerate(chapters):
            trad_filename = self.i18n_processor.get_traditional_filename(chapter.filename)
            
            # 生成导航链接
            nav_data = self._generate_navigation_data(chapters, i, is_traditional=True)
            
            # 语言切换链接
            lang_switch_links = self._generate_lang_switch_links(trad_filename, is_traditional=True)
            
            # 處理內容中的國際化佔位符
            processed_content = self._process_i18n_placeholders(chapter.content, is_traditional=True)
            
            # 繁体转换
            converted_title = self.i18n_processor.to_traditional(chapter.title)
            converted_chapter_toc = self.i18n_processor.to_traditional(chapter.chapter_toc)
            converted_content = self.i18n_processor.to_traditional(processed_content)
            converted_prev_link = self.i18n_processor.to_traditional(nav_data['prev_link'])
            converted_next_link = self.i18n_processor.to_traditional(nav_data['next_link'])
            converted_top_nav_links = self.i18n_processor.to_traditional(nav_data['top_nav_links'])
            converted_lang_switch_links = self.i18n_processor.to_traditional(lang_switch_links)
            
            # 渲染繁體版頁面
            html_content = self.i18n_template_manager.render_chapter(
                is_traditional=True,
                title=converted_title,
                chapter_toc=converted_chapter_toc,
                content=converted_content,
                prev_link=converted_prev_link,
                next_link=converted_next_link,
                top_nav_links=converted_top_nav_links,
                home_link="index_trad.html",
                lang_switch_links=converted_lang_switch_links,
                favicon_tag=self.favicon_tag
            )
            
            # 写入文件
            self.file_manager.write_file(trad_filename, html_content)
    
    def _generate_simplified_index(self, chapters: List[Chapter], book_title: str) -> None:
        """生成简体版首页"""
        toc_html = self.toc_generator.build_index_toc(chapters, is_traditional=False)
        
        # 生成语言切换链接
        lang_switch_links = self._generate_lang_switch_links("index.html", is_traditional=False)
        
        html_content = self.i18n_template_manager.render_index(
            is_traditional=False,
            book_title=book_title,
            toc_items=toc_html,
            lang_switch_links=lang_switch_links,
            favicon_tag=self.favicon_tag
        )
        
        self.file_manager.write_file("index.html", html_content)
    
    def _generate_traditional_index(self, chapters: List[Chapter], book_title: str) -> None:
        """生成繁体版首页"""
        # 转换章节数据为繁体
        trad_chapters = []
        for ch in chapters:
            trad_ch = Chapter(
                title=self.i18n_processor.to_traditional(ch.title),
                filename=ch.filename
            )
            trad_ch.toc_items = [
                TOCItem(
                    level=item.level,
                    text=self.i18n_processor.to_traditional(item.text),
                    anchor=item.anchor
                ) for item in ch.toc_items
            ]
            trad_chapters.append(trad_ch)
        
        trad_toc_html = self.toc_generator.build_index_toc(trad_chapters, is_traditional=True)
        
        # 生成语言切换链接
        lang_switch_links = self._generate_lang_switch_links("index_trad.html", is_traditional=True)
        
        # 渲染繁體版首頁
        html_content = self.i18n_template_manager.render_index(
            is_traditional=True,
            book_title=self.i18n_processor.to_traditional(book_title),
            toc_items=trad_toc_html,
            lang_switch_links=lang_switch_links,
            favicon_tag=self.favicon_tag
        )
        
        self.file_manager.write_file("index_trad.html", html_content)
    
    def _generate_navigation_data(self, chapters: List[Chapter], current_index: int, 
                                 is_traditional: bool = False) -> Dict[str, str]:
        """生成导航数据"""
        prev_link = ""
        next_link = ""
        top_nav_links = ""
        
        # 上一章链接
        if current_index > 0:
            prev_chapter = chapters[current_index - 1]
            prev_filename = prev_chapter.filename
            if is_traditional:
                prev_filename = self.i18n_processor.get_traditional_filename(prev_filename)
            prev_title = re.sub(r"<.*?>", "", prev_chapter.title)  # 清理HTML标签
            prev_text = get_i18n_text('ui.previous_chapter', is_traditional, '上一章')
            prev_link = f'<a href="{prev_filename}">⬅️ {prev_text}：{prev_title}</a>'
        
        # 下一章链接
        if current_index < len(chapters) - 1:
            next_chapter = chapters[current_index + 1]
            next_filename = next_chapter.filename
            if is_traditional:
                next_filename = self.i18n_processor.get_traditional_filename(next_filename)
            next_title = re.sub(r"<.*?>", "", next_chapter.title)  # 清理HTML标签
            next_text = get_i18n_text('ui.next_chapter', is_traditional, '下一章')
            next_link = f'<a href="{next_filename}">{next_text}：{next_title} ➡️</a>'
        
        # 顶部导航按钮
        if prev_link or next_link:
            top_nav_links = f'<div class="top-nav-buttons">{prev_link}{next_link}</div>'
        
        return {
            'prev_link': prev_link,
            'next_link': next_link,
            'top_nav_links': top_nav_links
        }
    
    def _generate_lang_switch_links(self, current_filename: str, is_traditional: bool = False) -> str:
        """生成语言切换链接
        
        Args:
            current_filename: 当前页面的文件名
            is_traditional: 当前是否为繁体页面
        """
        # 根據用戶需求：在繁體頁面中，"簡體"兩個字要使用簡體中文
        simplified_text = get_i18n_text('language_switch.simplified', False, '简体')  # 始終使用簡體字
        traditional_text = get_i18n_text('language_switch.traditional', True, '繁體')  # 始終使用繁體字
        
        if is_traditional:
            # 繁体页面：简体链接指向对应简体版，繁体链接指向当前页面
            simplified_filename = self.i18n_processor.get_simplified_filename(current_filename)
            return f'<a href="{simplified_filename}">{simplified_text}</a> | <a href="{current_filename}">{traditional_text}</a>'
        else:
            # 简体页面：简体链接指向当前页面，繁体链接指向对应繁体版
            traditional_filename = self.i18n_processor.get_traditional_filename(current_filename)
            return f'<a href="{current_filename}">{simplified_text}</a> | <a href="{traditional_filename}">{traditional_text}</a>'