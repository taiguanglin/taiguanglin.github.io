"""文本处理工具"""

import re
import hashlib
from typing import Optional, Tuple

from config.settings import Settings


def normalize_text_for_id(text: str) -> str:
    """标准化文本内容，提高ID生成的稳定性"""
    if not text:
        return ''
    
    return (text
            .strip()                                    # 移除首尾空白
            .replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')  # 替换换行符和制表符为空格
            .replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')  # 处理HTML实体
            )


def simple_hash(text: str) -> str:
    """生成简单hash"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:12]


class TextProcessor:
    """文本处理器"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def process_line_breaks(self, text: str, preserve_first_line: bool = True) -> str:
        """处理文字中的换行符，将其转换为HTML的<br>标签
        
        Args:
            text: 要处理的文字
            preserve_first_line: 是否保持第一行不换行（默认True，适用于问答内容）
        """
        if not text:
            return text
        
        # 将换行符转换为<br>标签
        # 处理Windows(\r\n)、Unix(\n)、Mac(\r)的换行符
        text = re.sub(r'\r\n|\r|\n', '<br>', text)
        
        # 清理多余的连续<br>标签（超过2个连续的<br>）
        text = re.sub(r'(<br>\s*){3,}', '<br><br>', text)
        
        if preserve_first_line:
            # 清理开头和结尾的<br>标签（问答内容第一行不换行）
            text = re.sub(r'^(<br>\s*)+|(<br>\s*)+$', '', text)
        else:
            # 只清理结尾的<br>标签（保留开头换行，适用于一般段落）
            text = re.sub(r'(<br>\s*)+$', '', text)
        
        return text
    
    def extract_time_from_text(self, text: str) -> Tuple[Optional[str], str]:
        """从文字中提取时间，支援多种格式，正确处理换行符"""
        
        def normalize_time_format(time_str: str) -> str:
            """标准化时间格式为 YYYY-MM-DD HH:MM"""
            # 处理无空格但有冒号的格式：2024-03-0310:57 -> 2024-03-03 10:57
            time_str = re.sub(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})(\d{1,2}:\d{2})', r'\1 \2', time_str)
            
            # 处理无空格且无冒号的格式：2024-03-031057 -> 2024-03-03 10:57
            time_str = re.sub(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})(\d{4})$', 
                             lambda m: f"{m.group(1)} {m.group(2)[:2]}:{m.group(2)[2:]}", time_str)
            
            # 统一分隔符为 - 
            time_str = re.sub(r'/', '-', time_str)
            
            return time_str
        
        # 完整时间格式：2024-02-18 10:47 或 2024-2-23 15:45  
        time_pattern1 = r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2})'
        match = re.search(time_pattern1, text)
        if match:
            time_str = normalize_time_format(match.group(1))
            remaining = text.replace(match.group(1), '', 1).strip()
            remaining = re.sub(r'^\s*\n\s*', '', remaining)
            return time_str, remaining
        
        # 无空格但有冒号的格式：2024-03-0310:57
        time_pattern2 = r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}\d{1,2}:\d{2})'
        match = re.search(time_pattern2, text)
        if match:
            time_str = normalize_time_format(match.group(1))
            remaining = text.replace(match.group(1), '', 1).strip()
            remaining = re.sub(r'^\s*\n\s*', '', remaining)
            return time_str, remaining
        
        # 无空格且无冒号的格式：2024-03-031057
        time_pattern3 = r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}\d{4})\b'
        match = re.search(time_pattern3, text)
        if match:
            time_str = normalize_time_format(match.group(1))
            remaining = text.replace(match.group(1), '', 1).strip()
            remaining = re.sub(r'^\s*\n\s*', '', remaining)
            return time_str, remaining
        
        # 只有日期：2024/02/03 或 18/02/2024 或 2024-02-18
        time_pattern4 = r'(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})'
        match = re.search(time_pattern4, text)
        if match:
            time_str = normalize_time_format(match.group(1))
            remaining = text.replace(match.group(1), '', 1).strip()
            remaining = re.sub(r'^\s*\n\s*', '', remaining)
            return time_str, remaining
        
        return None, text
    
    def clean_text(self, text: str) -> str:
        """清理文本，移除多余空白"""
        return ' '.join(text.split())
    
    def is_separator_line(self, text: str) -> bool:
        """检测是否为分隔线"""
        return bool(re.match(r"^_+$", text)) and len(text) >= 10
    
    def extract_questioner_info(self, text: str) -> Tuple[Optional[str], str]:
        """提取提问者信息
        
        Returns:
            Tuple[questioner_name, remaining_content]
        """
        questioner_match = re.match(r'^([^：:]+)[:：]\s*(.*)', text, re.DOTALL)
        if questioner_match:
            questioner_name = questioner_match.group(1).strip()
            question_content = questioner_match.group(2).strip()
            return questioner_name, question_content
        return None, text
    
    def extract_answerer_info(self, text: str) -> Tuple[Optional[str], str]:
        """提取回答者信息"""
        from config.settings import Constants
        answerer_match = re.match(Constants.ANSWERER_REGEX, text, re.IGNORECASE | re.DOTALL)
        if answerer_match:
            answer_content = answerer_match.group(2)
            return Constants.ANSWERER_RAW_NAME, answer_content
        return None, text


class IDGenerator:
    """ID生成器"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def generate_stable_qa_id(self, questioner: str, content: str, time: str, item_type: str) -> str:
        """
        生成稳定的问答ID，基于：人名 + 时间 + 前N个字
        这确保每次重新生成HTML时ID保持一致
        """
        # 标准化各组件
        normalized_questioner = normalize_text_for_id(questioner or '')
        normalized_content = normalize_text_for_id(content or '')
        normalized_time = re.sub(r'[^\d]', '', time or '')[:8] if time else ''  # 只保留数字
        
        # 取前N个字符
        content_part = normalized_content[:self.settings.id_content_length] if normalized_content else ''
        
        # 组合：人名 + 时间 + 前N个字
        stable_content = normalized_questioner + normalized_time + content_part
        
        # 生成hash
        content_hash = simple_hash(stable_content)
        return f"{item_type}-{content_hash}"
    
    def generate_content_id(self, content: str, item_type: str) -> str:
        """为一般内容生成ID"""
        content_hash = hashlib.md5(content[:100].encode()).hexdigest()[:8]
        return f"{item_type}-{content_hash}"
    
    def generate_heading_id(self, text: str) -> str:
        """为标题生成ID（使用slugify）"""
        from slugify import slugify
        return slugify(text)