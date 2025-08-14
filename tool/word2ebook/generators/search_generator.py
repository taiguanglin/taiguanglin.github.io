"""搜索索引生成器"""

import json
import brotli
from typing import List, Dict, Any
from pathlib import Path

from models.document_models import Chapter, SearchItem
from core.content_processor import ContentProcessor
from utils.file_utils import FileManager
from utils.i18n_utils import I18nProcessor
from config.settings import Settings, Constants


class SearchIndexGenerator:
    """搜索索引生成器"""
    
    def __init__(self, settings: Settings, file_manager: FileManager):
        self.settings = settings
        self.file_manager = file_manager
        self.content_processor = ContentProcessor(settings)
        self.i18n_processor = I18nProcessor()
    
    def generate_search_indexes(self, chapters: List[Chapter], generate_traditional: bool = True, skip_compress: bool = False) -> None:
        """生成搜索索引文件"""
        print("🔍 正在生成搜索索引...")
        
        # 生成简体版搜索索引
        self._generate_simplified_index(chapters, skip_compress)
        
        # 生成繁体版搜索索引
        if generate_traditional:
            self._generate_traditional_index(chapters, skip_compress)
    
    def _generate_simplified_index(self, chapters: List[Chapter], skip_compress: bool = False) -> None:
        """生成简体版搜索索引"""
        all_search_items = []
        
        for chapter in chapters:
            # 从已生成的HTML文件中读取内容
            html_file_path = self.file_manager.get_file_path(chapter.filename)
            if html_file_path.exists():
                with open(html_file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # 提取搜索项
                search_items, updated_html = self.content_processor.extract_search_content(
                    html_content, chapter.filename
                )
                all_search_items.extend(search_items)
                
                # 更新HTML文件，确保所有元素都有ID
                with open(html_file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_html)
        
        # 按权重和相关性排序
        all_search_items.sort(key=lambda x: x.weight, reverse=True)
        
        # 生成索引文件
        self._write_search_index(all_search_items, Constants.SEARCH_INDEX_SIMPLIFIED, skip_compress)
        
        print(f"✅ 简体搜索索引已生成：{Constants.SEARCH_INDEX_SIMPLIFIED} (共 {len(all_search_items)} 条记录)")
    
    def _generate_traditional_index(self, chapters: List[Chapter], skip_compress: bool = False) -> None:
        """生成繁体版搜索索引"""
        all_search_items = []
        
        for chapter in chapters:
            # 获取繁体版文件名
            trad_filename = self.i18n_processor.get_traditional_filename(chapter.filename)
            html_file_path = self.file_manager.get_file_path(trad_filename)
            
            if html_file_path.exists():
                with open(html_file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # 提取搜索项
                search_items, updated_html = self.content_processor.extract_search_content(
                    html_content, trad_filename
                )
                all_search_items.extend(search_items)
                
                # 更新HTML文件
                with open(html_file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_html)
        
        # 按权重排序
        all_search_items.sort(key=lambda x: x.weight, reverse=True)
        
        # 生成繁体版索引文件
        self._write_search_index(all_search_items, Constants.SEARCH_INDEX_TRADITIONAL, skip_compress)
        
        print(f"✅ 繁体搜索索引已生成：{Constants.SEARCH_INDEX_TRADITIONAL} (共 {len(all_search_items)} 条记录)")
    
    def _write_search_index(self, search_items: List[SearchItem], filename: str, skip_compress: bool = False) -> None:
        """写入搜索索引文件（支持 Brotli 壓縮）"""
        # 转换为字典格式
        index_data = [item.to_dict() for item in search_items]
        
        # 生成 JSON 内容（不使用缩进以减少文件大小）
        index_content = json.dumps(index_data, ensure_ascii=False, separators=(',', ':'))
        
        # 写入原始 JSON 文件
        self.file_manager.write_file(filename, index_content)
        
        # 如果不跳过压缩，则进行 Brotli 压缩
        if not skip_compress:
            try:
                compressed_data = brotli.compress(index_content.encode('utf-8'), quality=11)
                compressed_filename = filename.replace('.json', '.br')
                self.file_manager.write_binary_file(compressed_filename, compressed_data)
                
                # 计算压缩率
                original_size = len(index_content.encode('utf-8'))
                compressed_size = len(compressed_data)
                compression_ratio = (1 - compressed_size / original_size) * 100
                
                print(f"📦 Brotli 壓縮完成：{filename}")
                print(f"   原始大小: {original_size:,} bytes")
                print(f"   壓縮大小: {compressed_size:,} bytes")
                print(f"   壓縮率: {compression_ratio:.1f}%")
                
            except Exception as e:
                print(f"⚠️ Brotli 壓縮失敗 {filename}: {e}")
                print("   將繼續使用未壓縮的 JSON 文件")
        else:
            print(f"⏭️  跳过 Brotli 压缩：{filename}")
    
    def ensure_search_index_files(self, generate_traditional: bool = True) -> None:
        """确保搜索索引文件存在，如果不存在则创建空的索引文件
        
        注意：此方法不会修改HTML文件，保持增量更新模式的文件稳定性
        """
        # 检查简体版索引文件
        if not self.file_manager.file_exists(Constants.SEARCH_INDEX_SIMPLIFIED):
            print(f"📝 创建空的简体搜索索引：{Constants.SEARCH_INDEX_SIMPLIFIED}")
            empty_index = json.dumps([], ensure_ascii=False, indent=2)
            self.file_manager.write_file(Constants.SEARCH_INDEX_SIMPLIFIED, empty_index)
        else:
            print(f"✅ 简体搜索索引已存在：{Constants.SEARCH_INDEX_SIMPLIFIED}")
        
        # 检查繁体版索引文件
        if generate_traditional:
            if not self.file_manager.file_exists(Constants.SEARCH_INDEX_TRADITIONAL):
                print(f"📝 创建空的繁体搜索索引：{Constants.SEARCH_INDEX_TRADITIONAL}")
                empty_index = json.dumps([], ensure_ascii=False, indent=2)
                self.file_manager.write_file(Constants.SEARCH_INDEX_TRADITIONAL, empty_index)
            else:
                print(f"✅ 繁体搜索索引已存在：{Constants.SEARCH_INDEX_TRADITIONAL}")
    
    def generate_search_indexes_without_html_modification(self, chapters: List[Chapter], generate_traditional: bool = True) -> None:
        """生成搜索索引但不修改HTML文件（用于增量更新模式）"""
        print("🔍 正在生成搜索索引（不修改HTML文件）...")
        
        # 生成简体版搜索索引
        self._generate_simplified_index_readonly(chapters)
        
        # 生成繁体版搜索索引
        if generate_traditional:
            self._generate_traditional_index_readonly(chapters)
    
    def _generate_simplified_index_readonly(self, chapters: List[Chapter]) -> None:
        """生成简体版搜索索引（只读模式，不修改HTML）"""
        all_search_items = []
        
        for chapter in chapters:
            # 从已生成的HTML文件中读取内容
            html_file_path = self.file_manager.get_file_path(chapter.filename)
            if html_file_path.exists():
                with open(html_file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # 提取搜索项，但不更新HTML
                search_items, _ = self.content_processor.extract_search_content(
                    html_content, chapter.filename
                )
                all_search_items.extend(search_items)
                # 注意：这里不写回HTML文件
        
        # 按权重和相关性排序
        all_search_items.sort(key=lambda x: x.weight, reverse=True)
        
        # 生成索引文件
        self._write_search_index(all_search_items, Constants.SEARCH_INDEX_SIMPLIFIED, skip_compress)
        
        print(f"✅ 简体搜索索引已生成：{Constants.SEARCH_INDEX_SIMPLIFIED} (共 {len(all_search_items)} 条记录)")
    
    def _generate_traditional_index_readonly(self, chapters: List[Chapter]) -> None:
        """生成繁体版搜索索引（只读模式，不修改HTML）"""
        all_search_items = []
        
        for chapter in chapters:
            # 获取繁体版文件名
            trad_filename = self.i18n_processor.get_traditional_filename(chapter.filename)
            html_file_path = self.file_manager.get_file_path(trad_filename)
            
            if html_file_path.exists():
                with open(html_file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # 提取搜索项，但不更新HTML
                search_items, _ = self.content_processor.extract_search_content(
                    html_content, trad_filename
                )
                all_search_items.extend(search_items)
                # 注意：这里不写回HTML文件
        
        # 按权重排序
        all_search_items.sort(key=lambda x: x.weight, reverse=True)
        
        # 生成繁体版索引文件
        self._write_search_index(all_search_items, Constants.SEARCH_INDEX_TRADITIONAL, skip_compress)
        
        print(f"✅ 繁体搜索索引已生成：{Constants.SEARCH_INDEX_TRADITIONAL} (共 {len(all_search_items)} 条记录)")
    
    def update_html_with_ids(self, chapters: List[Chapter]) -> None:
        """更新HTML文件，确保所有元素都有ID"""
        for chapter in chapters:
            self._update_chapter_html_ids(chapter, is_traditional=False)
            
            # 如果存在繁体版，也更新
            trad_filename = self.i18n_processor.get_traditional_filename(chapter.filename)
            if self.file_manager.file_exists(trad_filename):
                # 创建繁体版chapter对象
                trad_chapter = Chapter(
                    title=chapter.title,
                    filename=trad_filename
                )
                self._update_chapter_html_ids(trad_chapter, is_traditional=True)
    
    def _update_chapter_html_ids(self, chapter: Chapter, is_traditional: bool = False) -> None:
        """更新单个章节的HTML文件ID"""
        html_file_path = self.file_manager.get_file_path(chapter.filename)
        if not html_file_path.exists():
            return
        
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 提取搜索项并更新HTML
        _, updated_html = self.content_processor.extract_search_content(
            html_content, chapter.filename
        )
        
        # 写回文件
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(updated_html)