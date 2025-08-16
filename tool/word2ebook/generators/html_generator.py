"""HTML 生成器"""

import re
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

from models.document_models import Chapter, TOCItem, QACountMetadata, QAPosition
from templates.html_templates import TemplateManager
from templates.i18n_templates import I18nTemplateManager
from utils.file_utils import FileManager
from utils.i18n_utils import I18nProcessor
from utils.config_utils import get_i18n_text
from utils.favicon_utils import FaviconManager
from config.settings import Settings


class TOCGenerator:
    """目录生成器"""
    
    def _count_children_at_levels(self, toc_items: List[Tuple[int, str, str]], parent_index: int, max_level: int = 4) -> Dict[int, int]:
        """计算指定父项目在各个层级的子项目数量
        
        Args:
            toc_items: 目录项目列表 (level, text, anchor)
            parent_index: 父项目在列表中的索引
            max_level: 最大计算层级
            
        Returns:
            Dict[int, int]: {level: count} 各层级的子项目数量
        """
        if parent_index >= len(toc_items):
            return {}
            
        parent_level = toc_items[parent_index][0]
        level_counts = {}
        
        # 初始化计数器
        for level in range(parent_level + 1, max_level + 1):
            level_counts[level] = 0
        
        # 从父项目的下一个开始计算
        for i in range(parent_index + 1, len(toc_items)):
            current_level = toc_items[i][0]
            
            # 如果遇到同级或更高级别的项目，停止计算
            if current_level <= parent_level:
                break
                
            # 只计算在指定范围内的层级
            if current_level <= max_level:
                level_counts[current_level] += 1
        
        return level_counts
    
    def _get_qa_count_for_section(self, html_content: str, section_anchor: str, toc_items: List[Tuple[int, str, str]], current_index: int) -> int:
        """计算指定目录项目下的问答数量"""
        from bs4 import BeautifulSoup
        import re
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 找到当前目录项目对应的标题元素
            current_heading = soup.find(id=section_anchor)
            if not current_heading:
                return 0
            
            # 确定下一个同级或更高级别标题的anchor（作为结束边界）
            current_level = toc_items[current_index][0]
            next_boundary_anchor = None
            
            for i in range(current_index + 1, len(toc_items)):
                next_level = toc_items[i][0]
                if next_level <= current_level:
                    next_boundary_anchor = toc_items[i][2]
                    break
            
            # 使用正则表达式来查找section内容
            # 构建正则表达式来匹配从当前标题到下一个标题之间的内容
            if next_boundary_anchor:
                pattern = f'<[hH][2-4][^>]*id="{re.escape(section_anchor)}"[^>]*>.*?<[hH][2-4][^>]*id="{re.escape(next_boundary_anchor)}"[^>]*>'
            else:
                pattern = f'<[hH][2-4][^>]*id="{re.escape(section_anchor)}"[^>]*>.*$'
            
            match = re.search(pattern, html_content, re.DOTALL)
            if match:
                section_content = match.group(0)
                # 在section内容中计算问题数量
                question_pattern = r'<div[^>]*class="question"[^>]*>'
                questions = re.findall(question_pattern, section_content)
                qa_count = len(questions)
                return qa_count
            else:
                return 0
            
        except Exception as e:
            # 如果解析失败，返回0
            print(f"Warning: Failed to parse QA count for {section_anchor}: {e}")
            return 0
    
    def _get_total_qa_count_for_chapter(self, html_content: str) -> int:
        """计算整个章节的问答总数量"""
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            questions = soup.find_all('div', class_='question')
            return len(questions)
        except Exception as e:
            return 0
    
    def _generate_qa_count_metadata_optimized(self, html_content: str, toc_items: List[Tuple[int, str, str]], filename: str) -> QACountMetadata:
        """優化版本：一次性解析HTML並生成問答計數元數據"""
        import re
        
        metadata = QACountMetadata(chapter_filename=filename)
        metadata.toc_structure = toc_items.copy()
        
        try:
            # 1. 使用正則表達式找到所有標題的位置
            for level, text, anchor in toc_items:
                # 查找標題元素的位置
                pattern = f'<[hH][2-4][^>]*id="{re.escape(anchor)}"[^>]*>'
                match = re.search(pattern, html_content)
                if match:
                    metadata.heading_positions[anchor] = match.start()
            
            # 2. 使用正則表達式找到所有問答的位置
            question_pattern = r'<div[^>]*class="question"[^>]*>'
            question_matches = list(re.finditer(question_pattern, html_content))

            
            for match in question_matches:
                metadata.qa_positions.append(QAPosition(match.start(), match.end()))
            
            # 3. 將問答歸屬到對應的標題下
            for level, text, anchor in toc_items:
                if anchor not in metadata.heading_positions:
                    continue
                    
                heading_pos = metadata.heading_positions[anchor]
                
                # 找到下一個同級或更高級標題的位置作為邊界
                next_boundary = len(html_content)  # 默認到文檔末尾
                current_level = level
                
                # 在toc_items中找到當前項目的索引
                current_index = -1
                for i, (toc_level, toc_text, toc_anchor) in enumerate(toc_items):
                    if toc_anchor == anchor:
                        current_index = i
                        break
                
                # 從當前項目之後開始查找邊界
                if current_index != -1:
                    for i in range(current_index + 1, len(toc_items)):
                        next_level, next_text, next_anchor = toc_items[i]
                        if next_level <= current_level and next_anchor in metadata.heading_positions:
                            next_boundary = metadata.heading_positions[next_anchor]
                            break
                
                # 計算在這個範圍內的問答數量
                qa_count = 0
                for qa_pos in metadata.qa_positions:
                    if heading_pos <= qa_pos.question_start < next_boundary:
                        qa_count += 1
                
                metadata.anchor_counts[anchor] = qa_count
            
            return metadata
            
        except Exception as e:
            print(f"Warning: Failed to generate optimized QA count metadata: {e}")
            # 回退到空的元數據
            return metadata
    
    def _insert_qa_counts_to_html(self, html_content: str, qa_metadata: QACountMetadata) -> str:
        """將問答計數插入到HTML中"""
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 找到所有目錄項目的a標籤
            toc_links = soup.find_all('a', href=True)
            
            for link in toc_links:
                href = link.get('href', '')
                # 提取anchor（去掉#前綴）
                if href.startswith('#'):
                    anchor = href[1:]
                elif '#' in href:
                    anchor = href.split('#')[1]
                else:
                    continue
                
                # 獲取該anchor的問答計數
                qa_count = qa_metadata.get_count_for_anchor(anchor)
                
                if qa_count > 0:
                    # 檢查是否已經有計數span
                    parent_li = link.find_parent('li')
                    if parent_li and not parent_li.find('span', class_='toc-count'):
                        # 創建計數span
                        count_span = soup.new_tag('span', **{'class': 'toc-count'})
                        count_span.string = f'({qa_count})'
                        
                        # 插入到a標籤後面
                        link.insert_after(count_span)
            
            return str(soup)
            
        except Exception as e:
            print(f"Warning: Failed to insert QA counts to HTML: {e}")
            return html_content
    
    def _get_direct_children_count(self, toc_items: List[Tuple[int, str, str]], parent_index: int) -> int:
        """获取指定父项目的直接子项目数量（已弃用，保留用于兼容性）"""
        if parent_index >= len(toc_items):
            return 0
            
        parent_level = toc_items[parent_index][0]
        direct_children_count = 0
        
        # 从父项目的下一个开始计算
        for i in range(parent_index + 1, len(toc_items)):
            current_level = toc_items[i][0]
            
            # 如果遇到同级或更高级别的项目，停止计算
            if current_level <= parent_level:
                break
                
            # 只计算直接子项目（父级别+1）
            if current_level == parent_level + 1:
                direct_children_count += 1
        
        return direct_children_count
    
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
    
    def build_collapsible_chapter_toc(self, toc_items: List[Tuple[int, str, str]], filename: Optional[str] = None, chapter_index: Optional[int] = None, html_content: Optional[str] = None, enable_qa_count: bool = True, qa_metadata: Optional[QACountMetadata] = None) -> str:
        """构建可折叠的章节目录（扁平化结构，但確保層級正確）"""
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
            
            # 计算问答数量（只对前4层显示计数）
            count_display = ""
            if enable_qa_count and level <= 4:
                if qa_metadata:
                    # 使用新的元數據方式
                    qa_count = qa_metadata.get_count_for_anchor(anchor)
                elif html_content:
                    # 回退到舊的方式
                    qa_count = self._get_qa_count_for_section(html_content, anchor, toc_items, i)
                else:
                    qa_count = 0
                
                if qa_count > 0:
                    count_display = f'<span class="toc-count">({qa_count})</span>'
            
            # 添加折叠控制图标
            expand_icon = ""
            if i in items_with_children:
                expand_icon = f'<span class="toc-expand-icon" data-level="{level}">▼</span>'
            
            # 生成扁平化的li元素，通过CSS和JavaScript控制层级显示
            # 添加 data-chapter 屬性來區分不同章節的子目錄
            chapter_attr = f' data-chapter="{chapter_index}"' if chapter_index is not None else ''
            html += f'<li class="toc-item toc-level-{level}" data-level="{level}" data-default-visible="{level <= 2}"{chapter_attr}>'
            html += f'{expand_icon}<a href="{link}">{text}</a>{count_display}</li>\n'
        
        html += "</ul>"
        return html
    
    def build_index_toc(self, chapters: List[Chapter], is_traditional: bool = False, enable_qa_count: bool = True) -> str:
        """建立首页目录"""
        html = "<ul class='toc-level-1'>\n"
        
        for ch_index, ch in enumerate(chapters):
            filename = ch.filename
            if is_traditional:
                filename = filename.replace(".html", "_trad.html")
            
            # 检查这个章节是否有子项
            has_children = bool(ch.toc_items)
            expand_icon = ""
            if has_children:
                expand_icon = '<span class="toc-expand-icon" data-level="1">▼</span>'
            
            # 计算章节的问答数量
            chapter_count_display = ""
            if enable_qa_count:
                if hasattr(ch, 'qa_count_metadata') and ch.qa_count_metadata:
                    # 使用新的元數據方式，計算所有問答總數
                    total_qa_count = sum(ch.qa_count_metadata.anchor_counts.values())
                elif hasattr(ch, 'content') and ch.content:
                    # 回退到舊的方式
                    total_qa_count = self._get_total_qa_count_for_chapter(ch.content)
                else:
                    total_qa_count = 0
                
                if total_qa_count > 0:
                    chapter_count_display = f'<span class="toc-count">({total_qa_count})</span>'
            
            html += f'<li class="toc-item toc-chapter" data-level="1" data-chapter="{ch_index}" data-default-visible="true">'
            html += f'{expand_icon}<a href="{filename}">{ch.title}</a>{chapter_count_display}\n'
            
            if ch.toc_items:
                # 转换 TOCItem 对象为元组，並添加章節標識
                toc_tuples = [(item.level, item.text, item.anchor) for item in ch.toc_items]
                html += self.build_collapsible_chapter_toc(toc_tuples, filename, ch_index, ch.content, enable_qa_count, ch.qa_count_metadata)
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
    
    def generate_chapter_pages(self, chapters: List[Chapter], generate_traditional: bool = True, generate_simplified: bool = True) -> None:
        """生成章节页面"""
        # 生成简体版
        if generate_simplified:
            self._generate_simplified_chapters(chapters)
        
        # 生成繁体版
        if generate_traditional:
            self._generate_traditional_chapters(chapters)
    
    def generate_index_pages(self, chapters: List[Chapter], config, 
                           generate_traditional: bool = True, generate_simplified: bool = True) -> None:
        """生成首页"""
        # 生成简体版首页
        if generate_simplified:
            simplified_title = config.get_book_title(is_traditional=False)
            self._generate_simplified_index(chapters, simplified_title, self.settings.enable_qa_count)
        
        # 生成繁体版首页
        if generate_traditional:
            traditional_title = config.get_book_title(is_traditional=True)
            self._generate_traditional_index(chapters, traditional_title, self.settings.enable_qa_count)
    
    def _generate_simplified_chapters(self, chapters: List[Chapter]) -> None:
        """生成简体版章节"""
        for i, chapter in enumerate(chapters):
            # 生成导航链接
            nav_data = self._generate_navigation_data(chapters, i, is_traditional=False)
            
            # 语言切换链接
            lang_switch_links = self._generate_lang_switch_links(chapter.filename, is_traditional=False)
            
            # 處理內容中的國際化佔位符
            processed_content = self._process_i18n_placeholders(chapter.content, is_traditional=False)
            
            # 分離章節標題和內容
            chapter_title_html, content_without_title = self._extract_chapter_title(processed_content, chapter.title)
            
            # 強制確保所有內容都是簡體字
            simplified_title = self.i18n_processor.ensure_simplified(chapter.title)
            simplified_chapter_title = self.i18n_processor.ensure_simplified(chapter_title_html)
            simplified_chapter_toc = self.i18n_processor.ensure_simplified(chapter.chapter_toc)
            simplified_content = self.i18n_processor.ensure_simplified(content_without_title)
            simplified_prev_link = self.i18n_processor.ensure_simplified(nav_data['prev_link'])
            simplified_next_link = self.i18n_processor.ensure_simplified(nav_data['next_link'])
            simplified_top_nav_links = self.i18n_processor.ensure_simplified(nav_data['top_nav_links'])
            
            # 渲染页面
            html_content = self.i18n_template_manager.render_chapter(
                is_traditional=False,
                title=simplified_title,
                chapter_title=simplified_chapter_title,
                chapter_toc=simplified_chapter_toc,
                content=simplified_content,
                prev_link=simplified_prev_link,
                next_link=simplified_next_link,
                top_nav_links=simplified_top_nav_links,
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
            
            # 分離章節標題和內容
            chapter_title_html, content_without_title = self._extract_chapter_title(processed_content, chapter.title)
            
            # 繁体转换
            converted_title = self.i18n_processor.to_traditional(chapter.title)
            converted_chapter_title = self.i18n_processor.to_traditional(chapter_title_html)
            converted_chapter_toc = self.i18n_processor.to_traditional(chapter.chapter_toc)
            converted_content = self.i18n_processor.to_traditional(content_without_title)
            converted_prev_link = self.i18n_processor.to_traditional(nav_data['prev_link'])
            converted_next_link = self.i18n_processor.to_traditional(nav_data['next_link'])
            converted_top_nav_links = self.i18n_processor.to_traditional(nav_data['top_nav_links'])
            # 特別處理：語言切換鏈接不需要轉換，因為已經包含正確的簡體字"简体"
            converted_lang_switch_links = lang_switch_links
            
            # 渲染繁體版頁面
            html_content = self.i18n_template_manager.render_chapter(
                is_traditional=True,
                title=converted_title,
                chapter_title=converted_chapter_title,
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
    
    def _generate_simplified_index(self, chapters: List[Chapter], book_title: str, enable_qa_count: bool = True) -> None:
        """生成简体版首页"""
        toc_html = self.toc_generator.build_index_toc(chapters, is_traditional=False, enable_qa_count=enable_qa_count)
        
        # 生成语言切换链接
        lang_switch_links = self._generate_lang_switch_links("index.html", is_traditional=False)
        
        # 獲取原始文件名（只要文件名，不要路徑）
        source_filename = self.input_file.name if self.input_file else ""
        
        # 強制確保所有內容都是簡體字
        simplified_book_title = self.i18n_processor.ensure_simplified(book_title)
        simplified_toc_html = self.i18n_processor.ensure_simplified(toc_html)
        simplified_source_filename = self.i18n_processor.ensure_simplified(source_filename)
        
        html_content = self.i18n_template_manager.render_index(
            is_traditional=False,
            book_title=simplified_book_title,
            toc_items=simplified_toc_html,
            lang_switch_links=lang_switch_links,
            favicon_tag=self.favicon_tag,
            source_filename=simplified_source_filename
        )
        
        self.file_manager.write_file("index.html", html_content)
    
    def _generate_traditional_index(self, chapters: List[Chapter], book_title: str, enable_qa_count: bool = True) -> None:
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
            # 複製問答計數元數據
            trad_ch.qa_count_metadata = ch.qa_count_metadata
            trad_chapters.append(trad_ch)
        
        trad_toc_html = self.toc_generator.build_index_toc(trad_chapters, is_traditional=True, enable_qa_count=enable_qa_count)
        
        # 生成语言切换链接
        lang_switch_links = self._generate_lang_switch_links("index_trad.html", is_traditional=True)
        
        # 獲取原始文件名（只要文件名，不要路徑）
        source_filename = self.input_file.name if self.input_file else ""
        
        # 渲染繁體版首頁
        html_content = self.i18n_template_manager.render_index(
            is_traditional=True,
            book_title=self.i18n_processor.to_traditional(book_title),
            toc_items=trad_toc_html,
            lang_switch_links=lang_switch_links,
            favicon_tag=self.favicon_tag,
            source_filename=source_filename
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
            prev_link = f'<a href="{prev_filename}">⬅️ {prev_title}</a>'
        
        # 下一章链接
        if current_index < len(chapters) - 1:
            next_chapter = chapters[current_index + 1]
            next_filename = next_chapter.filename
            if is_traditional:
                next_filename = self.i18n_processor.get_traditional_filename(next_filename)
            next_title = re.sub(r"<.*?>", "", next_chapter.title)  # 清理HTML标签
            next_link = f'<a href="{next_filename}">{next_title} ➡️</a>'
        
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
            # 特別處理：在繁體版頁面中，簡體文字保持為簡體字形式（不被轉換）
            simplified_filename = self.i18n_processor.get_simplified_filename(current_filename)
            return f'<a href="{simplified_filename}">{simplified_text}</a> | <a href="{current_filename}">{traditional_text}</a>'
        else:
            # 简体页面：简体链接指向当前页面，繁体链接指向对应繁体版
            traditional_filename = self.i18n_processor.get_traditional_filename(current_filename)
            return f'<a href="{current_filename}">{simplified_text}</a> | <a href="{traditional_filename}">{traditional_text}</a>'
    
    def _extract_chapter_title(self, content: str, chapter_title: str) -> tuple[str, str]:
        """從內容中提取並移除章節標題，返回標題HTML和剩餘內容"""
        import re
        
        # 查找第一個 <h1> 標籤
        h1_pattern = r'<h1[^>]*>.*?</h1>'
        h1_match = re.search(h1_pattern, content, re.DOTALL)
        
        if h1_match:
            # 提取 h1 標籤
            chapter_title_html = h1_match.group(0)
            # 從內容中移除 h1 標籤
            content_without_title = content.replace(h1_match.group(0), '', 1)
        else:
            # 如果找不到 h1 標籤，就創建一個
            chapter_title_html = f'<h1>{chapter_title}</h1>'
            content_without_title = content
        
        return chapter_title_html, content_without_title