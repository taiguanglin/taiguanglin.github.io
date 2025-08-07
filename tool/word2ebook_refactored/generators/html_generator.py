"""HTML 生成器"""

import re
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

from models.document_models import Chapter, TOCItem
from templates.html_templates import TemplateManager
from utils.file_utils import FileManager
from utils.i18n_utils import I18nProcessor
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
    
    def build_index_toc(self, chapters: List[Chapter], is_traditional: bool = False) -> str:
        """建立首页目录"""
        html = "<ul>\n"
        for ch in chapters:
            filename = ch.filename
            if is_traditional:
                filename = filename.replace(".html", "_trad.html")
            
            html += f'<li><a href="{filename}">{ch.title}</a>\n'
            if ch.toc_items:
                # 转换 TOCItem 对象为元组
                toc_tuples = [(item.level, item.text, item.anchor) for item in ch.toc_items]
                html += self.build_chapter_toc(toc_tuples, filename)
            html += "</li>\n"
        html += "</ul>"
        return html


class HTMLGenerator:
    """HTML 生成器"""
    
    def __init__(self, settings: Settings, file_manager: FileManager):
        self.settings = settings
        self.file_manager = file_manager
        self.template_manager = TemplateManager()
        self.toc_generator = TOCGenerator()
        self.i18n_processor = I18nProcessor()
    
    def generate_chapter_pages(self, chapters: List[Chapter], generate_traditional: bool = True) -> None:
        """生成章节页面"""
        # 生成简体版
        self._generate_simplified_chapters(chapters)
        
        # 生成繁体版
        if generate_traditional:
            self._generate_traditional_chapters(chapters)
    
    def generate_index_pages(self, chapters: List[Chapter], book_title: str, 
                           generate_traditional: bool = True) -> None:
        """生成首页"""
        # 生成简体版首页
        self._generate_simplified_index(chapters, book_title)
        
        # 生成繁体版首页
        if generate_traditional:
            self._generate_traditional_index(chapters, book_title)
    
    def _generate_simplified_chapters(self, chapters: List[Chapter]) -> None:
        """生成简体版章节"""
        for i, chapter in enumerate(chapters):
            # 生成导航链接
            nav_data = self._generate_navigation_data(chapters, i, is_traditional=False)
            
            # 语言切换链接
            lang_switch_links = self._generate_lang_switch_links(chapter.filename, is_traditional=False)
            
            # 渲染页面
            html_content = self.template_manager.render_chapter(
                title=chapter.title,
                chapter_toc=chapter.chapter_toc,
                content=chapter.content,
                prev_link=nav_data['prev_link'],
                next_link=nav_data['next_link'],
                top_nav_links=nav_data['top_nav_links'],
                home_link="index.html",
                lang_switch_links=lang_switch_links
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
            
            # 繁体转换
            converted_title = self.i18n_processor.to_traditional(chapter.title)
            converted_chapter_toc = self.i18n_processor.to_traditional(chapter.chapter_toc)
            converted_content = self.i18n_processor.to_traditional(chapter.content)
            converted_prev_link = self.i18n_processor.to_traditional(nav_data['prev_link'])
            converted_next_link = self.i18n_processor.to_traditional(nav_data['next_link'])
            converted_top_nav_links = self.i18n_processor.to_traditional(nav_data['top_nav_links'])
            converted_lang_switch_links = self.i18n_processor.to_traditional(lang_switch_links)
            
            # 转换模板并渲染
            template = self.i18n_processor.to_traditional(self.template_manager.get_template('chapter'))
            html_content = template.format(
                title=converted_title,
                chapter_toc=converted_chapter_toc,
                content=converted_content,
                prev_link=converted_prev_link,
                next_link=converted_next_link,
                top_nav_links=converted_top_nav_links,
                home_link="index_trad.html",
                lang_switch_links=converted_lang_switch_links
            )
            
            # 写入文件
            self.file_manager.write_file(trad_filename, html_content)
    
    def _generate_simplified_index(self, chapters: List[Chapter], book_title: str) -> None:
        """生成简体版首页"""
        toc_html = self.toc_generator.build_index_toc(chapters, is_traditional=False)
        
        html_content = self.template_manager.render_index(
            book_title=book_title,
            toc_items=toc_html
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
        
        # 转换模板并渲染
        template = self.i18n_processor.to_traditional(self.template_manager.get_template('index'))
        html_content = template.format(
            book_title=self.i18n_processor.to_traditional(book_title),
            toc_items=trad_toc_html
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
            prev_link = f'<a href="{prev_filename}">⬅️ 上一章：{prev_title}</a>'
        
        # 下一章链接
        if current_index < len(chapters) - 1:
            next_chapter = chapters[current_index + 1]
            next_filename = next_chapter.filename
            if is_traditional:
                next_filename = self.i18n_processor.get_traditional_filename(next_filename)
            next_title = re.sub(r"<.*?>", "", next_chapter.title)  # 清理HTML标签
            next_link = f'<a href="{next_filename}">下一章：{next_title} ➡️</a>'
        
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
        if is_traditional:
            # 繁体页面：简体链接指向对应简体版，繁体链接指向当前页面
            simplified_filename = self.i18n_processor.get_simplified_filename(current_filename)
            return f'<a href="{simplified_filename}">简体</a> | <a href="{current_filename}">繁體</a>'
        else:
            # 简体页面：简体链接指向当前页面，繁体链接指向对应繁体版
            traditional_filename = self.i18n_processor.get_traditional_filename(current_filename)
            return f'<a href="{current_filename}">简体</a> | <a href="{traditional_filename}">繁體</a>'