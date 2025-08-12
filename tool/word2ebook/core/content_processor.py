"""内容处理器"""

from typing import List, Dict, Tuple
from bs4 import BeautifulSoup

from models.document_models import Chapter, SearchItem
from utils.text_utils import TextProcessor, IDGenerator
from config.settings import Settings, Constants


class ContentProcessor:
    """内容处理器"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.text_processor = TextProcessor(settings)
        self.id_generator = IDGenerator(settings)
    
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
            
            weight = Constants.SEARCH_WEIGHTS.get(heading.name, 1.0)
            
            items.append(SearchItem(
                id=f"{base_filename}-{item_id}",
                title=content,
                type=Constants.SEARCH_TYPES['heading'],
                content=content,
                context=content,
                url=f"{base_filename}#{element_id}",
                weight=weight
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
            
            # 提取问题者和时间信息作为标题
            questioner = question.find(class_='questioner')
            time_elem = question.find(class_='question-time')
            title_parts = []
            if questioner:
                title_parts.append(questioner.get_text().strip())
            if time_elem:
                title_parts.append(time_elem.get_text().strip())
            title = ' | '.join(title_parts) if title_parts else '問題'
            
            items.append(SearchItem(
                id=f"{base_filename}-{item_id}",
                title=title,
                type=Constants.SEARCH_TYPES['question'],
                content=content,
                context=self._get_context(question, self.settings.search_context_length),
                url=f"{base_filename}#{element_id}",
                weight=Constants.SEARCH_WEIGHTS['question']
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
            
            # 提取回答者信息作为标题
            answerer = answer.find(class_='answerer')
            title = answerer.get_text().strip() if answerer else self.settings.default_answerer
            
            items.append(SearchItem(
                id=f"{base_filename}-{item_id}",
                title=f"{title}的回答",
                type=Constants.SEARCH_TYPES['answer'],
                content=content,
                context=self._get_context(answer, self.settings.search_context_length),
                url=f"{base_filename}#{element_id}",
                weight=Constants.SEARCH_WEIGHTS['answer']
            ))
            item_id += 1
            
        return items
    
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
                url=f"{base_filename}#{element_id}",
                weight=Constants.SEARCH_WEIGHTS['content']
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
        """获取元素的上下文，排除重複的meta信息"""
        # 嘗試只提取內容文本，排除姓名、時間等meta信息
        content_element = element.find(class_='question-text') or element.find(class_='answer-text')
        
        if content_element:
            # 如果找到純內容元素，使用它
            text = content_element.get_text()
        else:
            # 否則使用整個元素，但嘗試移除常見的meta信息
            text = element.get_text()
            
            # 移除常見的時間戳模式 (YYYY-MM-DD HH:MM 格式)
            import re
            text = re.sub(r'\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}', '', text)
            
            # 移除開頭可能的提問者/回答者標記（如果text開始就是姓名）
            # 這是一個簡單的啟發式方法
            lines = text.strip().split('\n')
            if len(lines) > 1:
                # 如果第一行很短且第二行較長，可能第一行是姓名，使用後續內容
                first_line = lines[0].strip()
                if len(first_line) < 20 and len(lines[1].strip()) > len(first_line):
                    text = '\n'.join(lines[1:])
        
        text = text.strip()
        if len(text) <= length * 2:
            return self.text_processor.clean_text(text)
        # 简单截取，避免截断词语
        context = text[:length] + "..." + text[-length:]
        return self.text_processor.clean_text(context)