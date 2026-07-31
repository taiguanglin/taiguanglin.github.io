"""内容处理器"""

import re
from typing import List, Dict, Tuple
from bs4 import BeautifulSoup

from models.document_models import Chapter, SearchItem
from utils.text_utils import TextProcessor, IDGenerator
from utils.text_segmentation import get_segmenter, is_segmenter_available
from config.settings import Settings, Constants

# PDF 日期+來源小節標題，例如「2025年11月10日 官網」
_PDF_SECTION_LABEL_RE = re.compile(
    r'^\d{4}年\d{1,2}月\d{1,2}日\s+'
    r'(?:贴吧|貼吧|官网|官網|微信公众号|微信公眾號)$'
)


class ContentProcessor:
    """内容处理器"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.text_processor = TextProcessor(settings)
        self.id_generator = IDGenerator(settings)
        self.segmenter = get_segmenter() if is_segmenter_available() else None
        
        # 输出分词器状态
        if self.segmenter and self.segmenter.is_available():
            print("✅ jieba 分词器已启用，将生成预分词索引")
        else:
            print("⚠️ jieba 分词器不可用，将使用原始文本索引")
    
    def extract_search_content(self, html_content: str, base_filename: str) -> Tuple[List[SearchItem], str]:
        """从HTML内容中提取搜索索引数据
        
        Args:
            html_content: HTML内容
            base_filename: 基础文件名
            
        Returns:
            Tuple[search_items, updated_html]: 搜索项列表和更新后的HTML
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        search_items = []
        item_id = 0
        
        # 提取标题
        search_items.extend(self._extract_headings(soup, base_filename, item_id))
        item_id += len(search_items)
        
        # 提取问题
        questions = self._extract_questions(soup, base_filename, item_id)
        search_items.extend(questions)
        item_id += len(questions)
        
        # 提取答案
        answers = self._extract_answers(soup, base_filename, item_id)
        search_items.extend(answers)
        item_id += len(answers)
        
        # 提取其他内容
        content_items = self._extract_content(soup, base_filename, item_id)
        search_items.extend(content_items)
        
        return search_items, str(soup)
    

    
    def _extract_headings(self, soup: BeautifulSoup, base_filename: str, start_id: int) -> List[SearchItem]:
        """提取标题"""
        items = []
        item_id = start_id
        
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
            if not heading.get_text().strip():
                continue
                
            content = self.text_processor.clean_text(heading.get_text())
            element_id = self._generate_or_get_id(heading, 'heading', content)
            heading['id'] = element_id  # 确保HTML中有ID
            
            items.append(SearchItem(
                id=f"{base_filename}-{item_id}",
                title=content,
                type=Constants.SEARCH_TYPES['heading'],
                content=content,
                context=content,
                url=f"{base_filename}#{element_id}"
            ))
            item_id += 1
            
        return items
    
    def _extract_questions(self, soup: BeautifulSoup, base_filename: str, start_id: int) -> List[SearchItem]:
        """提取问题"""
        items = []
        item_id = start_id
        
        for question in soup.find_all(class_='question'):
            if not question.get_text().strip():
                continue
                
            content = self.text_processor.clean_text(question.get_text())
            element_id = self._generate_or_get_id(question, 'question', content)
            question['id'] = element_id
            
            # 提取问题者和时间信息作为标题；无时间则回退到 PDF 日期+來源小節名
            questioner = question.find(class_='questioner')
            time_elem = question.find(class_='question-time')
            title_parts = []
            if questioner:
                title_parts.append(questioner.get_text().strip())
            time_text = time_elem.get_text().strip() if time_elem else ''
            if time_text:
                title_parts.append(time_text)
            else:
                section_label = self._pdf_section_label_for(question)
                if section_label:
                    title_parts.append(section_label)
            title = ' | '.join(title_parts) if title_parts else Constants.DEFAULT_QUESTION_TITLE
            
            items.append(SearchItem(
                id=f"{base_filename}-{item_id}",
                title=title,
                type=Constants.SEARCH_TYPES['question'],
                content=content,
                context=self._get_context(question, self.settings.search_context_length),
                url=f"{base_filename}#{element_id}"
            ))
            item_id += 1
            
        return items
    
    def _extract_answers(self, soup: BeautifulSoup, base_filename: str, start_id: int) -> List[SearchItem]:
        """提取答案"""
        items = []
        item_id = start_id
        
        for answer in soup.find_all(class_='answer'):
            if not answer.get_text().strip():
                continue
                
            content = self.text_processor.clean_text(answer.get_text())
            element_id = self._generate_or_get_id(answer, 'answer', content)
            answer['id'] = element_id
            
            # 提取回答者信息作为标题；时间点取该回答对应问题的时间，
            # 无时间则回退到 PDF 日期+來源小節名
            answerer = answer.find(class_='answerer')
            title = answerer.get_text().strip() if answerer else self.settings.default_answerer
            
            if title == Constants.ANSWERER_RAW_NAME:
                title = Constants.ANSWERER_DISPLAY_NAME

            title = f"{title}的回答"
            prev_question = answer.find_previous_sibling(class_='question')
            time_text = ''
            if prev_question:
                time_elem = prev_question.find(class_='question-time')
                if time_elem:
                    time_text = time_elem.get_text().strip()
            if time_text:
                title = f"{title} | {time_text}"
            else:
                section_label = self._pdf_section_label_for(prev_question or answer)
                if section_label:
                    title = f"{title} | {section_label}"
            
            items.append(SearchItem(
                id=f"{base_filename}-{item_id}",
                title=title,
                type=Constants.SEARCH_TYPES['answer'],
                content=content,
                context=self._get_context(answer, self.settings.search_context_length),
                url=f"{base_filename}#{element_id}"
            ))
            item_id += 1
            
        return items

    def _pdf_section_label_for(self, element) -> str:
        """若元素位於 PDF「日期 + 來源」h2 下，回傳該小節名（不含答疑數）。"""
        if element is None:
            return ''
        h2 = element.find_previous('h2')
        if not h2:
            return ''
        label_parts = []
        for node in h2.contents:
            if getattr(node, 'name', None) == 'span' and 'chapter-qa-count' in (node.get('class') or []):
                continue
            if hasattr(node, 'get_text'):
                label_parts.append(node.get_text())
            else:
                label_parts.append(str(node))
        label = ''.join(label_parts).strip()
        if _PDF_SECTION_LABEL_RE.match(label):
            return label
        return ''
    
    def _extract_content(self, soup: BeautifulSoup, base_filename: str, start_id: int) -> List[SearchItem]:
        """提取其他内容"""
        items = []
        item_id = start_id
        
        for para in soup.find_all('p'):
            if para.find_parent(class_=['question', 'answer']):
                continue  # 跳过问答内容中的段落
                
            content = self.text_processor.clean_text(para.get_text())
            if len(content) <= self.settings.search_min_paragraph_length:
                continue  # 只索引较长的段落
                
            element_id = self._generate_or_get_id(para, 'content', content)
            para['id'] = element_id
            
            items.append(SearchItem(
                id=f"{base_filename}-{item_id}",
                title=content[:50] + "..." if len(content) > 50 else content,
                type=Constants.SEARCH_TYPES['content'],
                content=content,
                context=self._get_context(para, 60),
                url=f"{base_filename}#{element_id}"
            ))
            item_id += 1
            
        return items
    
    def _generate_or_get_id(self, element, item_type: str, content: str) -> str:
        """为元素生成或获取ID"""
        if element.get('id'):
            return element.get('id')
        
        # 对于问答元素，使用稳定的ID生成逻辑
        if item_type in ['question', 'answer']:
            questioner = ''
            time_info = ''
            
            if item_type == 'question':
                questioner_elem = element.find(class_='questioner')
                time_elem = element.find(class_='question-time')
                questioner = questioner_elem.get_text().strip() if questioner_elem else ''
                time_info = time_elem.get_text().strip() if time_elem else ''
            elif item_type == 'answer':
                answerer_elem = element.find(class_='answerer')
                questioner = answerer_elem.get_text().strip() if answerer_elem else self.settings.default_answerer
                # 答案通常没有时间信息
                time_info = ''
            
            return self.id_generator.generate_stable_qa_id(questioner, content, time_info, item_type)
        else:
            # 其他元素使用一般ID生成逻辑
            return self.id_generator.generate_content_id(content, item_type)
    
    def _get_context(self, element, length: int = 50) -> str:
        """获取元素的上下文"""
        text = element.get_text()
        if len(text) <= length * 2:
            return self.text_processor.clean_text(text)
        # 简单截取，避免截断词语
        context = text[:length] + "..." + text[-length:]
        return self.text_processor.clean_text(context)