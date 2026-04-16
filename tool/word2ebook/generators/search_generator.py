"""搜索索引生成器"""

import json
import hashlib
from typing import List

from models.document_models import Chapter, SearchItem
from core.content_processor import ContentProcessor
from utils.file_utils import FileManager
from utils.i18n_utils import I18nProcessor
from config.settings import Settings, Constants

# 搜索结果排序规则（type -> sort key）
_TYPE_ORDER = {"heading": 0, "question": 1, "answer": 2, "content": 3}


class SearchIndexGenerator:
    """搜索索引生成器

    Public API:
        generate_search_indexes(chapters, ...)          → 生成 search_index*.json
        generate_search_indexes_without_html_modification(...)  → 只读模式
        ensure_search_index_files(...)                  → 确保索引文件存在（增量模式）
        update_html_with_ids(chapters)                  → 补全 HTML 元素 ID
    """

    def __init__(self, settings: Settings, file_manager: FileManager):
        self.settings = settings
        self.file_manager = file_manager
        self.content_processor = ContentProcessor(settings)
        self.i18n_processor = I18nProcessor()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def generate_search_indexes(
        self,
        chapters: List[Chapter],
        generate_traditional: bool = True,
        generate_simplified: bool = True,
    ) -> None:
        """生成搜索索引文件（同时更新 HTML 以确保元素 ID 存在）。"""
        if generate_simplified:
            self._generate_index(chapters, is_traditional=False, update_html=True)
        if generate_traditional:
            self._generate_index(chapters, is_traditional=True, update_html=True)

    def generate_search_indexes_without_html_modification(
        self,
        chapters: List[Chapter],
        generate_traditional: bool = True,
        generate_simplified: bool = True,
    ) -> None:
        """生成搜索索引但不修改 HTML 文件（增量更新模式）。"""
        print("🔍 正在生成搜索索引（不修改HTML文件）...")
        if generate_simplified:
            self._generate_index(chapters, is_traditional=False, update_html=False)
        if generate_traditional:
            self._generate_index(chapters, is_traditional=True, update_html=False)

    def ensure_search_index_files(
        self,
        generate_traditional: bool = True,
        generate_simplified: bool = True,
    ) -> None:
        """确保索引文件存在；不存在时写入空 JSON（不修改 HTML）。"""
        pairs = []
        if generate_simplified:
            pairs.append(Constants.SEARCH_INDEX_SIMPLIFIED)
        if generate_traditional:
            pairs.append(Constants.SEARCH_INDEX_TRADITIONAL)

        for filename in pairs:
            if not self.file_manager.file_exists(filename):
                print(f"📝 创建空的搜索索引：{filename}")
                empty_index = json.dumps([], ensure_ascii=False, indent=2)
                self.file_manager.write_file(filename, empty_index)
            else:
                print(f"✅ 搜索索引已存在：{filename}")

    def update_html_with_ids(self, chapters: List[Chapter]) -> None:
        """更新 HTML 文件，确保所有元素都有 ID。"""
        for chapter in chapters:
            self._update_chapter_html_ids(chapter.filename)
            trad_fn = self.i18n_processor.get_traditional_filename(chapter.filename)
            if self.file_manager.file_exists(trad_fn):
                self._update_chapter_html_ids(trad_fn)

    # ------------------------------------------------------------------ #
    # Core: unified index generation                                      #
    # ------------------------------------------------------------------ #

    def _generate_index(
        self, chapters: List[Chapter], is_traditional: bool, update_html: bool
    ) -> None:
        """统一的索引生成实现，is_traditional 控制简/繁分支。"""
        all_items: List[SearchItem] = []

        for chapter in chapters:
            filename = (
                self.i18n_processor.get_traditional_filename(chapter.filename)
                if is_traditional
                else chapter.filename
            )
            html_file_path = self.file_manager.get_file_path(filename)
            if not html_file_path.exists():
                continue

            with open(html_file_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            search_items, updated_html = self.content_processor.extract_search_content(
                html_content, filename
            )

            # 简体版：确保内容都是简体字
            if not is_traditional:
                for item in search_items:
                    item.title = self.i18n_processor.ensure_simplified(item.title)
                    item.content = self.i18n_processor.ensure_simplified(item.content)
                    if hasattr(item, "context") and item.context:
                        item.context = self.i18n_processor.ensure_simplified(item.context)

            all_items.extend(search_items)

            if update_html:
                with open(html_file_path, "w", encoding="utf-8") as f:
                    f.write(updated_html)

        all_items.sort(key=lambda x: (_TYPE_ORDER.get(x.type, 4), x.id))

        index_filename = (
            Constants.SEARCH_INDEX_TRADITIONAL if is_traditional
            else Constants.SEARCH_INDEX_SIMPLIFIED
        )
        self._write_search_index(all_items, index_filename)

        variant = "繁体" if is_traditional else "简体"
        print(f"✅ {variant}搜索索引已生成：{index_filename} (共 {len(all_items)} 条记录)")

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _write_search_index(self, search_items: List[SearchItem], filename: str) -> None:
        """序列化搜索项并写入 JSON 文件，同时生成 .hash 文件。"""
        index_content = json.dumps(
            [item.to_dict() for item in search_items], ensure_ascii=False, indent=2
        )
        self.file_manager.write_file(filename, index_content)
        self._generate_hash_file(filename, index_content)

    def _generate_hash_file(self, json_filename: str, content: str) -> None:
        """为 JSON 文件生成 MD5 哈希文件。"""
        try:
            content_bytes = content.encode("utf-8")
            md5_hash = hashlib.md5(content_bytes).hexdigest()
            hash_data = {"hash": md5_hash, "algorithm": "md5", "size": len(content_bytes)}
            hash_content = json.dumps(hash_data, ensure_ascii=False, indent=2)
            hash_filename = f"{json_filename}.hash"
            self.file_manager.write_file(hash_filename, hash_content)
            print(f"📝 已生成哈希文件: {hash_filename} (MD5: {md5_hash[:8]}...)")
        except Exception as e:
            print(f"⚠️ 生成哈希文件失败: {e}")

    def _update_chapter_html_ids(self, filename: str) -> None:
        """更新单个 HTML 文件，确保所有可搜索元素都有 ID。"""
        html_file_path = self.file_manager.get_file_path(filename)
        if not html_file_path.exists():
            return
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        _, updated_html = self.content_processor.extract_search_content(html_content, filename)
        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(updated_html)
