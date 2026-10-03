"""TOC（目录）生成器"""

import re
from typing import List, Tuple, Optional, Dict

from models.document_models import Chapter, TOCItem, QACountMetadata, QAPosition

# 預設顯示層級：首頁 2 層、章節頁 3 層。
# ⚠️ 這兩個值必須與 assets/js/modules/06-toc-collapse.js 的
# initTocCollapseControl()（``defaultLevel = isChapterPage ? '3' : '2'``）
# 以及 templates/i18n_templates.py 內 `.toc-level-btn.active` 的標記一致，
# 否則 JS 啟動時會重算層級、把伺服器端已渲染好的目錄改掉（視覺跳動）。
DEFAULT_TOC_LEVEL_INDEX = 2
DEFAULT_TOC_LEVEL_CHAPTER = 3


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
    # TOC 初始狀態（讓 HTML 本身就能正確排版）                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def resolve_display_level(
        present_levels, default_level: int, button_levels=None
    ) -> int:
        """決定「初始顯示到第幾層」，且必須與 JS 算出的結果一致。

        對應 JS ``selectValidLevel()``：把 ``default_level`` 對齊到
        「確實有項目」且「确有按鈕」的層級；沒有完全對得上時取距離最近的
        （同距離取較小者，與 JS 的 ``distance < minDistance`` 嚴格小於一致）。

        兩邊不一致的話，JS 啟動時會重算並改掉已渲染的目錄，造成視覺跳動。
        """
        available = sorted(
            lv for lv in present_levels
            if button_levels is None or lv in button_levels
        )
        if not available or default_level in available:
            return default_level
        return min(available, key=lambda lv: (abs(lv - default_level), lv))

    @staticmethod
    def _expand_icon_html(level: int, expanded: bool) -> str:
        """展開鈕初始標記，與 JS ``setTocIconState()`` 的輸出一致。

        展開 → ``▼`` / ``aria-expanded="true"``；收合 → ``▶`` ＋ ``.collapsed``
        （``.collapsed`` 由 04a-toc-levels.css 旋轉 -90deg）。
        """
        return (
            '<button type="button" class="toc-expand-icon{cls}" data-level="{level}"'
            ' aria-label="展開或收合子目錄" aria-expanded="{aria}">{glyph}</button>'
        ).format(
            level=level,
            cls="" if expanded else " collapsed",
            aria="true" if expanded else "false",
            glyph="▼" if expanded else "▶",
        )

    def _toc_item_classes(self, level: int, expandable: bool, display_level: int) -> str:
        """組出 ``<li>`` 的 class。

        ``toc-expandable`` 必須由伺服器端輸出：``04a-toc-levels.css`` 用
        ``.toc-item:not(.toc-expandable) { display: flex }`` 決定葉節點排版，
        而該 class 原本只由 JS 補上 —— JS 尚未執行時全部 ``li`` 都命中
        ``:not(.toc-expandable)``，巢狀 ``<ul>`` 被拉成 ``display:flex`` 的
        子項而橫向並排，就是未套用樣式時目錄「排列很怪」的真正原因。
        """
        classes = ["toc-item", "toc-level-%d" % level]
        if expandable:
            classes.append("toc-expandable")
        if level > display_level:
            classes.append("hidden")
        return " ".join(classes)

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
        display_level: Optional[int] = None,
    ) -> str:
        """构建巢狀可折疊 TOC。

        語意層級以巢狀 <ul> 呈現（螢幕閱讀器可感知結構）；視覺仍為扁平
        ——縮排由 04a-toc-levels.css 歸零，層級感由展開鈕定位與配色呈現。
        展開控制沿用 .toc-item 的 data-level（JS 06-toc-collapse 已同時支援
        巢狀與扁平兩種結構）。

        ``display_level`` 為 None 時沿用頁面預設（首頁 2 層／章節頁 3 層），
        並在伺服器端就輸出 ``.hidden`` 與收合的展開鈕，使 HTML 本身已是
        正確的初始狀態；JS 之後只負責套用 ``localStorage`` 裡的使用者偏好。

        ⚠️ 預設層級必須再經 ``resolve_display_level()`` 對齊到「確實有項目」的
        層級：章節頁預設第 3 層，但若該章只有第 2 層標題，JS 的
        ``selectValidLevel()`` 會退到第 2 層；伺服器端不對齊的話，
        ``.toc-level-btn.active`` 標在第 3 層鈕上，JS 啟動後又移到第 2 層，
        使用者會看到按鈕高亮跳動。
        """
        if not toc_items:
            return "<ul></ul>"

        if display_level is None:
            display_level = (
                DEFAULT_TOC_LEVEL_INDEX if is_index_page else DEFAULT_TOC_LEVEL_CHAPTER
            )
            display_level = self.resolve_display_level(
                {lvl for lvl, _, _ in toc_items},
                display_level,
                # 章節頁模板渲染 data-level 2/3/4 三顆按鈕
                button_levels={2, 3, 4} if not is_index_page else {1, 2, 3, 4},
            )

        items_with_children = {
            i
            for i, (level, _, _) in enumerate(toc_items)
            if i + 1 < len(toc_items) and toc_items[i + 1][0] > level
        }


        parts = ["<ul>\n"]
        prev_level = 2
        li_open = False

        for i, (level, text, anchor) in enumerate(toc_items):
            if level > prev_level:
                parts.append("<ul>\n" * (level - prev_level))
            elif level < prev_level:
                if li_open:
                    parts.append("</li>\n")
                    li_open = False
                parts.append("</ul>\n</li>\n" * (prev_level - level))
            elif li_open:
                parts.append("</li>\n")
                li_open = False

            link = f"{filename}#{anchor}" if filename else f"#{anchor}"
            chapter_attr = f' data-chapter="{chapter_index}"' if chapter_index is not None else ""
            # 有子節點才輸出展開鈕，並與 JS setTocDisplayLevel() 的規則一致：
            # 層級 < 顯示層級 → 展開；= 顯示層級 → 收合（更深層已被 .hidden 隱藏）。
            expand_icon = (
                self._expand_icon_html(level, expanded=level < display_level)
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

            parts.append(
                f'<li class="{self._toc_item_classes(level, i in items_with_children, display_level)}" '
                f'data-level="{level}"{chapter_attr}>'
                f'{expand_icon}<a href="{link}">{text}</a>{count_display}\n'
            )
            li_open = True
            prev_level = level

        if li_open:
            parts.append("</li>\n")
        parts.append("</ul>\n</li>\n" * max(0, prev_level - 2))
        parts.append("</ul>")
        return "".join(parts)

    def build_index_toc(
        self, chapters: List["Chapter"], is_traditional: bool = False
    ) -> str:
        """构建首页目录（章节列表 + 子 TOC）。

        伺服器端即輸出 ``.hidden`` / 收合展開鈕 / ``.toc-expandable``，
        使 HTML 未載入 JS 時已是正確的初始畫面（見
        ``build_collapsible_chapter_toc`` 的說明）。
        """
        # 與 JS selectValidLevel() 一致：可選層級 = 有項目且有按鈕的層級
        # （模板 i18n_templates.py 首頁渲染 data-level 1–4 這四顆按鈕）。
        present_levels = {1}
        for ch in chapters:
            present_levels.update(item.level for item in ch.toc_items)
        display_level = self.resolve_display_level(
            present_levels, DEFAULT_TOC_LEVEL_INDEX, button_levels={1, 2, 3, 4}
        )

        html = "<ul class='toc-level-1'>\n"

        for ch_index, ch in enumerate(chapters):
            filename = ch.filename
            if is_traditional:
                filename = filename.replace(".html", "_trad.html")

            expandable = bool(ch.toc_items)
            # 第 1 層恆小於顯示層級（預設 2）→ 展開，與 JS 一致
            expand_icon = (
                self._expand_icon_html(1, expanded=1 < display_level)
                if expandable
                else ""
            )
            li_classes = "toc-item toc-chapter"
            if expandable:
                # 有子章節 → 必須帶 toc-expandable，否則 04a-toc-levels.css 的
                # `.toc-item:not(.toc-expandable){display:flex}` 會把巢狀 <ul>
                # 拉成橫向並排（JS 未載入時目錄亂版的根因）
                li_classes += " toc-expandable"

            if ch.qa_count_metadata:
                total_qa = self.get_chapter_level_qa_count(ch)
            elif ch.content:
                total_qa = self.get_total_qa_count_for_chapter(ch.content)
            else:
                total_qa = 0

            count_display = f'<span class="toc-count">({total_qa})</span>' if total_qa > 0 else ""

            html += (
                f'<li class="{li_classes}" data-level="1" '
                f'data-chapter="{ch_index}">'
                f'{expand_icon}'
                f'<a href="{filename}">'
                f'{ch.title}</a>{count_display}\n'
            )

            if ch.toc_items:
                toc_tuples = [(item.level, item.text, item.anchor) for item in ch.toc_items]
                html += self.build_collapsible_chapter_toc(
                    toc_tuples, filename, ch_index, ch.content, ch.qa_count_metadata,
                    is_index_page=True, display_level=display_level,
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
