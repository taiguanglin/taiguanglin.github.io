"""TOC（目录）生成器"""

import re
from typing import List, Tuple, Optional, Dict

from models.document_models import Chapter, TOCItem, QACountMetadata, QAPosition


class TOCGenerator:
    """目录生成器 — 负责构建 TOC HTML 和计算问答计数元数据"""

    # ------------------------------------------------------------------ #
    # QA 计数元数据                                                        #
    # ------------------------------------------------------------------ #

    def generate_qa_count_metadata(
        self,
        html_content: str,
        toc_items: List[Tuple[int, str, str]],
        filename: str,
    ) -> QACountMetadata:
        """一次性解析 HTML，返回每个 anchor 对应的问答计数元数据。

        Args:
            html_content: 章节 HTML 字符串
            toc_items: (level, text, anchor) 列表
            filename: 章节文件名（用于元数据标识）

        Returns:
            QACountMetadata，包含 anchor_counts / qa_positions / heading_positions
        """
        metadata = QACountMetadata(chapter_filename=filename)
        metadata.toc_structure = toc_items.copy()

        try:
            # 1. 记录每个标题在 HTML 中的字符偏移
            for level, text, anchor in toc_items:
                pattern = f'<[hH][2-4][^>]*id="{re.escape(anchor)}"[^>]*>'
                match = re.search(pattern, html_content)
                if match:
                    metadata.heading_positions[anchor] = match.start()

            # 2. 记录所有问答 div 的位置
            question_pattern = r'<div[^>]*class="question"[^>]*>'
            for match in re.finditer(question_pattern, html_content):
                metadata.qa_positions.append(QAPosition(match.start(), match.end()))

            # 3. 归属问答到对应标题区域
            for level, text, anchor in toc_items:
                if anchor not in metadata.heading_positions:
                    continue

                heading_pos = metadata.heading_positions[anchor]
                next_boundary = len(html_content)

                current_index = next(
                    (i for i, (_, _, a) in enumerate(toc_items) if a == anchor), -1
                )
                if current_index != -1:
                    for i in range(current_index + 1, len(toc_items)):
                        next_level, _, next_anchor = toc_items[i]
                        if (
                            next_level <= level
                            and next_anchor in metadata.heading_positions
                        ):
                            next_boundary = metadata.heading_positions[next_anchor]
                            break

                metadata.anchor_counts[anchor] = sum(
                    1
                    for qa in metadata.qa_positions
                    if heading_pos <= qa.question_start < next_boundary
                )

        except Exception as e:
            print(f"Warning: Failed to generate QA count metadata: {e}")

        return metadata

    def get_chapter_level_qa_count(self, chapter: "Chapter") -> int:
        """返回章节的问答总数（仅累计 level=2 标题下的计数）。"""
        if not chapter.qa_count_metadata or not chapter.toc_items:
            return 0
        return sum(
            chapter.qa_count_metadata.get_count_for_anchor(item.anchor)
            for item in chapter.toc_items
            if item.level == 2
        )

    def get_total_qa_count_for_chapter(self, html_content: str) -> int:
        """计算章节 HTML 中问答 div 的总数（回退方式，不依赖元数据）。"""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_content, "html.parser")
            return len(soup.find_all("div", class_="question"))
        except Exception:
            return 0

    # ------------------------------------------------------------------ #
    # TOC HTML 构建                                                        #
    # ------------------------------------------------------------------ #

    def build_chapter_toc(
        self,
        toc_items: List[Tuple[int, str, str]],
        filename: Optional[str] = None,
    ) -> str:
        """将 (level, text, anchor) 列表转为嵌套 <ul>（不可折叠版本）。"""
        if not toc_items:
            return "<ul></ul>"

        html = "<ul>\n"
        prev_level = 2

        for level, text, anchor in toc_items:
            link = f"{filename}#{anchor}" if filename else f"#{anchor}"
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

    def build_collapsible_chapter_toc(
        self,
        toc_items: List[Tuple[int, str, str]],
        filename: Optional[str] = None,
        chapter_index: Optional[int] = None,
        html_content: Optional[str] = None,
        qa_metadata: Optional[QACountMetadata] = None,
        is_index_page: bool = False,
    ) -> str:
        """构建扁平化可折叠 TOC（层级通过 CSS/JS data 属性控制）。"""
        if not toc_items:
            return "<ul></ul>"

        items_with_children = {
            i
            for i, (level, _, _) in enumerate(toc_items)
            if i + 1 < len(toc_items) and toc_items[i + 1][0] > level
        }

        html = "<ul>\n"
        for i, (level, text, anchor) in enumerate(toc_items):
            link = f"{filename}#{anchor}" if filename else f"#{anchor}"
            link_attrs = ' target="_blank" rel="noopener noreferrer"' if is_index_page else ""
            chapter_attr = f' data-chapter="{chapter_index}"' if chapter_index is not None else ""
            expand_icon = (
                f'<span class="toc-expand-icon" data-level="{level}">▼</span>'
                if i in items_with_children
                else ""
            )

            count_display = ""
            if level <= 4:
                if qa_metadata:
                    qa_count = qa_metadata.get_count_for_anchor(anchor)
                elif html_content:
                    qa_count = self._get_qa_count_for_section(html_content, anchor, toc_items, i)
                else:
                    qa_count = 0
                if qa_count > 0:
                    count_display = f'<span class="toc-count">({qa_count})</span>'

            html += (
                f'<li class="toc-item toc-level-{level}" '
                f'data-level="{level}" data-default-visible="{level <= 2}"{chapter_attr}>'
                f'{expand_icon}<a href="{link}"{link_attrs}>{text}</a>{count_display}</li>\n'
            )

        html += "</ul>"
        return html

    def build_index_toc(
        self, chapters: List["Chapter"], is_traditional: bool = False
    ) -> str:
        """构建首页目录（章节列表 + 子 TOC）。"""
        html = "<ul class='toc-level-1'>\n"

        for ch_index, ch in enumerate(chapters):
            filename = ch.filename
            if is_traditional:
                filename = filename.replace(".html", "_trad.html")

            expand_icon = (
                '<span class="toc-expand-icon" data-level="1">▼</span>'
                if ch.toc_items
                else ""
            )

            if ch.qa_count_metadata:
                total_qa = self.get_chapter_level_qa_count(ch)
            elif ch.content:
                total_qa = self.get_total_qa_count_for_chapter(ch.content)
            else:
                total_qa = 0

            count_display = f'<span class="toc-count">({total_qa})</span>' if total_qa > 0 else ""

            html += (
                f'<li class="toc-item toc-chapter" data-level="1" '
                f'data-chapter="{ch_index}" data-default-visible="true">'
                f'{expand_icon}'
                f'<a href="{filename}" target="_blank" rel="noopener noreferrer">'
                f'{ch.title}</a>{count_display}\n'
            )

            if ch.toc_items:
                toc_tuples = [(item.level, item.text, item.anchor) for item in ch.toc_items]
                html += self.build_collapsible_chapter_toc(
                    toc_tuples, filename, ch_index, ch.content, ch.qa_count_metadata,
                    is_index_page=True,
                )
            html += "</li>\n"

        html += "</ul>"
        return html

    # ------------------------------------------------------------------ #
    # 内部辅助                                                             #
    # ------------------------------------------------------------------ #

    def _get_qa_count_for_section(
        self,
        html_content: str,
        section_anchor: str,
        toc_items: List[Tuple[int, str, str]],
        current_index: int,
    ) -> int:
        """回退方式：用正则统计 section 内的问答数量（不依赖元数据）。"""
        try:
            current_level = toc_items[current_index][0]
            next_boundary_anchor = next(
                (toc_items[i][2] for i in range(current_index + 1, len(toc_items))
                 if toc_items[i][0] <= current_level),
                None,
            )

            if next_boundary_anchor:
                pattern = (
                    f'<[hH][2-4][^>]*id="{re.escape(section_anchor)}"[^>]*>'
                    f".*?"
                    f'<[hH][2-4][^>]*id="{re.escape(next_boundary_anchor)}"[^>]*>'
                )
            else:
                pattern = f'<[hH][2-4][^>]*id="{re.escape(section_anchor)}"[^>]*>.*$'

            match = re.search(pattern, html_content, re.DOTALL)
            if match:
                return len(re.findall(r'<div[^>]*class="question"[^>]*>', match.group(0)))
            return 0
        except Exception as e:
            print(f"Warning: Failed to parse QA count for {section_anchor}: {e}")
            return 0
