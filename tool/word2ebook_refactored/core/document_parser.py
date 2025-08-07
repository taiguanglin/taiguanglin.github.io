"""Word 文档解析器"""

import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from docx import Document
from docx.oxml.ns import qn

from models.document_models import Chapter, QAPair, TOCItem, SearchItem
from utils.text_utils import TextProcessor, IDGenerator
from utils.file_utils import ImageHandler, FileManager
from config.settings import Settings


class DocumentParser:
    """Word 文档解析器"""
    
    def __init__(self, settings: Settings, file_manager: FileManager):
        self.settings = settings
        self.file_manager = file_manager
        self.text_processor = TextProcessor(settings)
        self.id_generator = IDGenerator(settings)
        self.image_handler = ImageHandler(file_manager)
        
    def parse_document(self, input_file: Path) -> Tuple[List[Chapter], Dict[str, str]]:
        """解析 Word 文档
        
        Args:
            input_file: 输入的 Word 文档路径
            
        Returns:
            Tuple[chapters, image_map]: 章节列表和图片映射字典
        """
        doc = Document(input_file)
        
        # 提取图片
        image_map = {}
        if self.settings.extract_images:
            image_map = self.image_handler.extract_images_from_document(doc, image_map)
        
        # 解析章节
        chapters = self._parse_chapters(doc, image_map)
        
        return chapters, image_map
    
    def _parse_chapters(self, doc: Document, image_map: Dict[str, str]) -> List[Chapter]:
        """解析文档中的章节"""
        chapters = []
        current_chapter = None
        toc_items = []
        bold_mode_state = {"bold_mode": False}
        content_blocks = []
        
        for paragraph in doc.paragraphs:
            html = self._paragraph_to_html(paragraph, image_map, toc_items, bold_mode_state)
            if not html:
                continue
            
            if html.startswith("<h1>"):  # 新章节
                if current_chapter:
                    # 完成上一章节
                    current_chapter = self._finalize_chapter(current_chapter, content_blocks, toc_items)
                    chapters.append(current_chapter)
                
                # 开始新章节
                title = re.sub(r"<.*?>", "", html)
                filename = self._generate_chapter_filename(title, len(chapters) + 1)
                current_chapter = Chapter(title=title, filename=filename)
                toc_items = []
                content_blocks = [html]
            else:
                if current_chapter:
                    content_blocks.append(html)
        
        # 处理最后一个章节
        if current_chapter:
            current_chapter = self._finalize_chapter(current_chapter, content_blocks, toc_items)
            chapters.append(current_chapter)
        
        return chapters
    
    def _paragraph_to_html(self, paragraph, image_map: Dict[str, str], 
                          toc_list: List[Tuple[int, str, str]], 
                          bold_mode_state: Dict[str, bool]) -> str:
        """将段落转换为 HTML"""
        # 检查是否包含图片
        image_html = self._extract_image_from_paragraph(paragraph, image_map)
        if image_html:
            return image_html
        
        # 获取段落文本（包含换行）
        text = self._extract_paragraph_text(paragraph)
        text = self.text_processor.process_line_breaks(text)
        
        if not text:
            return ""
        
        # 检查分隔线
        if self.text_processor.is_separator_line(text):
            bold_mode_state["bold_mode"] = False
            return "<hr>"
        
        # 处理标题
        heading_html = self._process_heading(paragraph, text, toc_list)
        if heading_html:
            return heading_html
        
        # 处理问答内容
        qa_html = self._process_qa_content(text, bold_mode_state)
        if qa_html:
            return qa_html
        
        # 处理普通段落
        return self._process_regular_paragraph(text, bold_mode_state)
    
    def _extract_image_from_paragraph(self, paragraph, image_map: Dict[str, str]) -> Optional[str]:
        """从段落中提取图片"""
        for run in paragraph.runs:
            drawing = run.element.find(qn('w:drawing'))
            pict = run.element.find(qn('w:pict'))
            if drawing is not None or pict is not None:
                blips = run.element.findall('.//a:blip', 
                                          namespaces={'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'})
                for blip in blips:
                    rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    if rId in image_map:
                        return f'<img src="{image_map[rId]}" alt="Image">'
        return None
    
    def _extract_paragraph_text(self, paragraph) -> str:
        """提取段落文本（包含换行）"""
        text_parts = []
        for run in paragraph.runs:
            # 获取run的文字内容
            run_text = run.text
            
            # 检查run的XML元素中是否包含换行标签
            run_xml = run.element
            
            # 重新构建包含换行的文字
            current_text = ""
            for child in run_xml:
                if child.tag == qn('w:t'):
                    # 文字节点
                    current_text += child.text or ""
                elif child.tag == qn('w:br'):
                    # 换行节点
                    current_text += '\n'
                elif child.tag == qn('w:tab'):
                    # Tab节点
                    current_text += '\t'
            
            # 如果没有特殊元素，使用原始文字
            if not current_text and run_text:
                current_text = run_text
                
            text_parts.append(current_text)
        
        return ''.join(text_parts).strip()
    
    def _process_heading(self, paragraph, text: str, toc_list: List[Tuple[int, str, str]]) -> Optional[str]:
        """处理标题"""
        style = paragraph.style.name.lower()
        
        if "heading 1" in style:
            return f"<h1>{text}</h1>"
        elif "heading 2" in style:
            anchor = self.id_generator.generate_heading_id(text)
            toc_list.append((2, text, anchor))
            return f'<h2 id="{anchor}">{text}</h2>'
        elif "heading 3" in style:
            anchor = self.id_generator.generate_heading_id(text)
            toc_list.append((3, text, anchor))
            return f'<h3 id="{anchor}">{text}</h3>'
        
        return None
    
    def _process_qa_content(self, text: str, bold_mode_state: Dict[str, bool]) -> Optional[str]:
        """处理问答内容"""
        # 检查是否为回答
        answerer, answer_content = self.text_processor.extract_answerer_info(text)
        if answerer:
            bold_mode_state["bold_mode"] = True
            time_info, clean_content = self.text_processor.extract_time_from_text(answer_content)
            
            # 确保回答内容第一行不换行
            clean_content = re.sub(r'^(<br>\s*)+', '', clean_content)
            
            # 生成稳定的ID
            answer_id = self.id_generator.generate_stable_qa_id(answerer, clean_content, time_info, 'answer')
            
            time_html = f'<span class="question-time">{time_info}</span>' if time_info else ''
            
            return f'''<div class="answer" id="{answer_id}">
    <div class="answer-meta">
        <span class="answerer">{answerer}</span>
        {time_html}
    </div>
    <div class="answer-text">{clean_content}</div>
</div>'''
        
        # 检查是否为问题
        questioner, question_content = self.text_processor.extract_questioner_info(text)
        if questioner and not bold_mode_state["bold_mode"]:
            return self._process_question(questioner, question_content)
        
        return None
    
    def _process_question(self, questioner: str, question_content: str) -> str:
        """处理问题内容"""
        # 如果问题内容为空，表示只有姓名，没有时间和内容
        if not question_content:
            question_id = self.id_generator.generate_stable_qa_id(questioner, '', '', 'question')
            return f'''<div class="question" id="{question_id}">
    <div class="question-meta">
        <span class="questioner">{questioner}</span>
    </div>
    <div class="question-text"></div>
</div>'''
        
        # 尝试提取时间
        time_info, clean_content = self.text_processor.extract_time_from_text(question_content)
        
        # 如果提取到时间但内容为空，说明这行只有姓名和时间，问题内容在后续段落
        if time_info and not clean_content.strip():
            time_html = f'<span class="question-time">{time_info}</span>'
            question_id = self.id_generator.generate_stable_qa_id(questioner, '', time_info, 'question')
            return f'''<div class="question" id="{question_id}">
    <div class="question-meta">
        <span class="questioner">{questioner}</span>
        {time_html}
    </div>
    <div class="question-text"></div>
</div>'''
        
        # 如果没有时间信息，整个 question_content 就是问题内容
        if not time_info:
            clean_content = question_content
            time_html = ''
        else:
            time_html = f'<span class="question-time">{time_info}</span>'
        
        # 确保问题内容第一行不换行
        clean_content = re.sub(r'^(<br>\s*)+', '', clean_content)
        
        # 生成稳定的ID
        question_id = self.id_generator.generate_stable_qa_id(questioner, clean_content, time_info, 'question')
        
        return f'''<div class="question" id="{question_id}">
    <div class="question-meta">
        <span class="questioner">{questioner}</span>
        {time_html}
    </div>
    <div class="question-text">{clean_content}</div>
</div>'''
    
    def _process_regular_paragraph(self, text: str, bold_mode_state: Dict[str, bool]) -> str:
        """处理普通段落"""
        if bold_mode_state["bold_mode"]:
            # 在回答模式中，作为回答内容的延续
            text_content = re.sub(r'^(<br>\s*)+', '', text)
            return f'<div class="answer-text">{text_content}</div>'
        else:
            return f"<p>{text}</p>"
    
    def _generate_chapter_filename(self, title: str, index: int) -> str:
        """生成章节文件名"""
        from utils.file_utils import safe_filename
        return safe_filename(title, index)
    
    def _finalize_chapter(self, chapter: Chapter, content_blocks: List[str], 
                         toc_items: List[Tuple[int, str, str]]) -> Chapter:
        """完成章节处理"""
        from generators.html_generator import TOCGenerator
        
        # 处理内容块
        if self.settings.merge_qa_blocks:
            content_blocks = self._merge_qa_blocks(content_blocks)
        
        if self.settings.enable_back_to_top:
            content_blocks = self._insert_back_to_top(content_blocks)
        
        # 设置章节内容
        chapter.content = "\n".join(content_blocks)
        
        # 生成目录
        toc_generator = TOCGenerator()
        chapter.chapter_toc = toc_generator.build_chapter_toc(toc_items)
        
        # 转换 toc_items 为 TOCItem 对象
        chapter.toc_items = [TOCItem(level=level, text=text, anchor=anchor) 
                           for level, text, anchor in toc_items]
        
        return chapter
    
    def _merge_qa_blocks(self, content_blocks: List[str]) -> List[str]:
        """合并连续的问答区块"""
        merged_blocks = []
        i = 0
        
        while i < len(content_blocks):
            current_block = content_blocks[i]
            
            # 检查是否为问题开始
            if current_block.startswith('<div class="question">'):
                # 收集所有连续的问题内容
                question_parts = [current_block]
                i += 1
                
                # 收集后续的普通段落作为问题内容的延续
                while i < len(content_blocks):
                    next_block = content_blocks[i]
                    
                    # 如果遇到新的问题、回答或标题，停止收集
                    if (next_block.startswith('<div class="question">') or 
                        next_block.startswith('<div class="answer">') or
                        next_block.startswith('<h1>') or 
                        next_block.startswith('<h2>') or 
                        next_block.startswith('<h3>') or
                        next_block.startswith('<hr>')):
                        break
                    
                    # 如果是普通段落，添加为问题内容
                    if next_block.startswith('<p>'):
                        content = next_block.replace('<p>', '').replace('</p>', '')
                        question_parts.append(f'    <div class="question-text">{content}</div>')
                        i += 1
                    else:
                        break
                
                # 确保问题区块正确结束
                if not question_parts[-1].endswith('</div>'):
                    question_parts.append('</div>')
                    
                merged_blocks.append('\n'.join(question_parts))
                
            # 检查是否为回答开始
            elif current_block.startswith('<div class="answer">'):
                # 收集所有连续的回答内容
                answer_parts = [current_block]
                i += 1
                
                # 收集后续的 answer-text div 或普通段落（如果是多段落回答）
                while i < len(content_blocks):
                    next_block = content_blocks[i]
                    
                    # 如果遇到新的问题、回答或标题，停止收集
                    if (next_block.startswith('<div class="question">') or 
                        next_block.startswith('<div class="answer">') or
                        next_block.startswith('<h1>') or 
                        next_block.startswith('<h2>') or 
                        next_block.startswith('<h3>') or
                        next_block.startswith('<hr>')):
                        break
                    
                    # 如果是answer-text或普通段落，添加为回答内容
                    if next_block.startswith('<div class="answer-text">'):
                        answer_parts.append('    ' + next_block)
                        i += 1
                    elif next_block.startswith('<p>'):
                        content = next_block.replace('<p>', '').replace('</p>', '')
                        answer_parts.append(f'    <div class="answer-text">{content}</div>')
                        i += 1
                    else:
                        break
                
                # 确保回答区块正确结束
                if not answer_parts[-1].endswith('</div>'):
                    answer_parts.append('</div>')
                    
                merged_blocks.append('\n'.join(answer_parts))
                
            else:
                merged_blocks.append(current_block)
                i += 1
        
        return merged_blocks
    
    def _insert_back_to_top(self, content_blocks: List[str]) -> List[str]:
        """根据章节内 H2/H3 结构插入回到顶部连结"""
        output_blocks = []
        h3_count = 0
        h2_count = 0
        last_heading_type = None

        for block in content_blocks:
            is_h2 = block.startswith("<h2 ")
            is_h3 = block.startswith("<h3 ")

            if is_h3:
                if last_heading_type == "h3":
                    output_blocks.append('<div class="back-to-top"><a href="#top">⬆️ 回到本章目錄</a></div>')
                h3_count += 1
                last_heading_type = "h3"
            elif is_h2 and h3_count == 0:  # 無 H3 時 H2 也加按鈕
                if last_heading_type == "h2":
                    output_blocks.append('<div class="back-to-top"><a href="#top">⬆️ 回到本章目錄</a></div>')
                h2_count += 1
                last_heading_type = "h2"

            output_blocks.append(block)

        # 補最後一個小節的回到頂部
        output_blocks.append('<div class="back-to-top"><a href="#top">⬆️ 回到本章目錄</a></div>')
        return output_blocks