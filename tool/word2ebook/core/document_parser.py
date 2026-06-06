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
            
            if html.startswith("<h1"):  # 新章节（支持带ID的h1标签）
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
            anchor = self.id_generator.generate_heading_id(text)
            # heading 1 不添加到當前章節的 toc_list，因為它應該是新章節的開始
            # toc_list.append((1, text, anchor))  # 註釋掉這行
            return f'<h1 id="{anchor}">{text}</h1>'
        elif "heading 2" in style:
            anchor = self.id_generator.generate_heading_id(text)
            toc_list.append((2, text, anchor))
            return f'<h2 id="{anchor}">{text}</h2>'
        elif "heading 3" in style:
            anchor = self.id_generator.generate_heading_id(text)
            toc_list.append((3, text, anchor))
            return f'<h3 id="{anchor}">{text}</h3>'
        elif "heading 4" in style:
            anchor = self.id_generator.generate_heading_id(text)
            toc_list.append((4, text, anchor))
            return f'<h4 id="{anchor}">{text}</h4>'
        
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
        """完成章节处理（委派至共用的 chapter_finalizer）"""
        from core.chapter_finalizer import finalize_chapter
        return finalize_chapter(chapter, content_blocks, toc_items, self.settings)