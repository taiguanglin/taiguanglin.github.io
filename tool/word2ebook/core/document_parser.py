"""Word 文档解析器"""

import re
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional
from docx import Document
from docx.oxml.ns import qn

from models.document_models import Chapter, QAPair, TOCItem, SearchItem
from utils.text_utils import TextProcessor, IDGenerator
from utils.file_utils import ImageHandler, FileManager
from utils.image_markup import render_img_tag
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
        # bold_mode：是否處於「回答模式」（回答段落沒有前綴時，靠它續接成 answer-text）
        # prev_kind：上一個輸出的區塊種類（question / answer / other），
        #   供「整段粗體卻漏了『Taiguanglin：』前綴的回答」判定用。
        #   ⚠️ 這份 state 跨章共用，故章界（h1）必須重設 prev_kind。
        bold_mode_state = {"bold_mode": False, "prev_kind": "other"}
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
                # 章界重設上一區塊種類（bold_mode 沿用既有行為，只由分隔線重設）
                bold_mode_state["prev_kind"] = "other"
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
                          bold_mode_state: Dict[str, Any]) -> str:
        """将段落转换为 HTML"""
        # 检查是否包含图片
        image_html = self._extract_image_from_paragraph(paragraph, image_map)

        # 获取段落文本（包含换行）
        text = self._extract_paragraph_text(paragraph)
        text = self.text_processor.process_line_breaks(text)

        if not text:
            # 純圖片段落：維持原行為，只輸出圖片
            bold_mode_state["prev_kind"] = "other"
            return image_html or ""

        # 检查分隔线
        if self.text_processor.is_separator_line(text):
            bold_mode_state["bold_mode"] = False
            bold_mode_state["prev_kind"] = "other"
            return self._append_image("<hr>", image_html)

        # 处理标题
        heading_html = self._process_heading(paragraph, text, toc_list)
        if heading_html:
            bold_mode_state["prev_kind"] = "other"
            return self._append_image(heading_html, image_html)

        # 处理问答内容
        qa_html = self._process_qa_content(
            text, bold_mode_state, self._is_fully_bold(paragraph))
        if qa_html:
            return self._append_image(qa_html, image_html)

        # 处理普通段落（回答模式中＝回答的續段；否則是一般段落）
        bold_mode_state["prev_kind"] = (
            "answer" if bold_mode_state["bold_mode"] else "other")
        return self._append_image(
            self._process_regular_paragraph(text, bold_mode_state), image_html)

    @staticmethod
    def _is_fully_bold(paragraph) -> bool:
        """段落是否「整段加粗」（所有非空 run 的 bold 都明確為 True）。

        Word 底稿的正常回答都帶「Taiguanglin：」前綴；少數回答段落整段加粗
        卻漏了前綴（見 :meth:`_process_answer_without_prefix`）。整段加粗是
        這些漏網段落的唯一可靠訊號——普通內文段落不會整段加粗。
        """
        runs = [r for r in paragraph.runs if (r.text or "").strip()]
        if not runs:
            return False
        return all(r.bold is True for r in runs)

    @staticmethod
    def _append_image(html: str, image_html: Optional[str]) -> str:
        """把段落內的圖片附在區塊 HTML 之後

        過去只要段落含圖片就直接 ``return image_html``，同段落內的文字
        （可能是「問者：日期」標頭＋問題本文）被整段丟棄——例如
        2025-03-10 贴吧用户_QUDy8Na、2025-05-15 猫猫|、2025-03-12 心的选择
        三題的提問文字就是這麼從電子書消失，只留下孤立的答案。
        純圖片段落（無文字）行為不變，仍是只輸出圖片。
        """
        if not image_html:
            return html
        return f"{html}\n{image_html}"
    
    def _extract_image_from_paragraph(self, paragraph, image_map: Dict[str, str]) -> Optional[str]:
        """从段落中提取图片

        同一段落可能含多張附圖（提問者附「圖1／圖2／圖3」時常見，例如
        2025-03-10 贴吧用户_QUDy8Na 一題就有 3 張）。過去在第一張圖後即
        ``return``，其餘附圖全被丟棄——本函式改為收集段落內所有圖片，
        以 ``\\n`` 串接後一併輸出。
        """
        images: List[str] = []
        alt = (paragraph.text or "").strip()[:40] or "文章配圖"

        for run in paragraph.runs:
            drawing = run.element.find(qn('w:drawing'))
            pict = run.element.find(qn('w:pict'))
            if drawing is None and pict is None:
                continue
            blips = run.element.findall('.//a:blip',
                                        namespaces={'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'})
            for blip in blips:
                rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                if rId in image_map:
                    rel = image_map[rId]
                    abs_path = None
                    try:
                        abs_path = self.image_handler.file_manager.get_file_path(rel)
                    except Exception:
                        abs_path = None
                    images.append(render_img_tag(rel, alt, abs_path))

        if not images:
            return None
        return "\n".join(images)
    
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
    
    def _process_qa_content(self, text: str, bold_mode_state: Dict[str, Any],
                            fully_bold: bool = False) -> Optional[str]:
        """处理问答内容"""
        # 检查是否为回答
        answerer, answer_content = self.text_processor.extract_answerer_info(text)
        if answerer:
            bold_mode_state["bold_mode"] = True
            bold_mode_state["prev_kind"] = "answer"
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
            bold_mode_state["prev_kind"] = "question"
            return self._process_question(questioner, question_content)
        
        # 补捞：整段加粗、却没有「Taiguanglin：」前缀的回答段落
        # 条件：既不像回答（前缀缺失）也不像提问（无「名字：」）、不在回答模式、
        #       整段加粗，且上一個輸出的區塊是「提问」。
        if (questioner is None
                and not bold_mode_state["bold_mode"]
                and bold_mode_state.get("prev_kind") == "question"
                and fully_bold):
            bold_mode_state["prev_kind"] = "answer"
            return self._process_answer_without_prefix(text)
        
        return None
    
    def _process_answer_without_prefix(self, text: str) -> str:
        """处理「漏了『Taiguanglin：』前缀」的回答段落。

        Word 底稿有少數回答段落整段加粗、卻沒有作者前缀（本文件 2 处：
        ch02 的「佛菩萨是否会直接干预命运？…」（2025-05-15 11:54）与
        ch04 的「还有修罗道相当于天界的畜生…」（2024-02-14 18:28））。
        过去这些段落被当成一般段落输出 <p>，而 stage 3 只收 question/answer
        区块 → 该则的提问与回答整组从电子书消失。

        回答者一律补回 ``Constants.ANSWERER_RAW_NAME``（与其它回答一致）；
        该则的日期由它的提問區塊顯示（回答正文本身没有时间戳），故此处
        不产生 question-time 栏位。
        """
        from config.settings import Constants
        answerer = Constants.ANSWERER_RAW_NAME
        
        # 正文逐字保留（不抽时间戳，避免把内文中的日期片段抽走）
        clean_content = re.sub(r'^(<br>\s*)+', '', text)
        
        answer_id = self.id_generator.generate_stable_qa_id(
            answerer, clean_content, '', 'answer')
        
        return f'''<div class="answer" id="{answer_id}">
    <div class="answer-meta">
        <span class="answerer">{answerer}</span>
    </div>
    <div class="answer-text">{clean_content}</div>
</div>'''
    
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
        
        # 補充日期：原始文字無時間戳時，從音頻映射推導的日期表查找
        # ⚠️ ID 用原始 time_info 生成（保持穩定），補充日期只影響顯示
        if not time_html:
            from core.date_supplement import lookup_date
            supplement = lookup_date(question_id)
            if supplement:
                time_html = f'<span class="question-time">{supplement}</span>'
        
        return f'''<div class="question" id="{question_id}">
    <div class="question-meta">
        <span class="questioner">{questioner}</span>
        {time_html}
    </div>
    <div class="question-text">{clean_content}</div>
</div>'''
    
    def _process_regular_paragraph(self, text: str, bold_mode_state: Dict[str, Any]) -> str:
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