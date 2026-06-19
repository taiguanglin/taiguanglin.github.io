"""HTML 生成器"""

import os
import re
from html import escape
from typing import List, Optional, Dict
from pathlib import Path

from models.document_models import Chapter, TOCItem, QACountMetadata
from generators.toc_generator import TOCGenerator
from templates.i18n_templates import I18nTemplateManager
from utils.file_utils import FileManager
from utils.i18n_utils import I18nProcessor
from utils.config_utils import get_i18n_text
from utils.favicon_utils import FaviconManager
from config.settings import Settings, Constants


class HTMLGenerator:
    """HTML 生成器 — 将 Chapter 列表渲染为 HTML 文件。

    Public API:
        generate_chapter_pages(chapters, ...)  → writes chapter .html files
        generate_index_pages(chapters, ...)    → writes index.html / index_trad.html
        copy_favicon_after_setup()             → copies favicon after dir is ready
    """

    def __init__(
        self,
        settings: Settings,
        file_manager: FileManager,
        input_file: Optional[Path] = None,
        extra_source_files: Optional[List[Path]] = None,
        include_qa_source: bool = False,
    ):
        self.settings = settings
        self.file_manager = file_manager
        self.i18n_template_manager = I18nTemplateManager()
        self.toc_generator = TOCGenerator()
        self.i18n_processor = I18nProcessor()
        self.input_file = input_file
        # 額外的來源檔（例如附加的 PDF）；會與 input_file 一起顯示在首頁底部的 Source
        self.extra_source_files = [Path(p) for p in (extra_source_files or [])]
        # 是否在首頁來源加上第三個連結，直接連到線上校稿工具 qa/index.html
        self.include_qa_source = include_qa_source
        self.favicon_manager = None
        self.favicon_tag = ""

        if input_file and settings.favicon_enabled:
            self.favicon_manager = FaviconManager(
                input_file,
                file_manager.output_folder,
                settings.favicon_search_patterns,
            )
            self.favicon_manager.find_favicon()
            self.favicon_tag = self.favicon_manager.get_favicon_html_tag()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def copy_favicon_after_setup(self) -> None:
        """在目录设置完成后复制 favicon 文件。"""
        if self.favicon_manager:
            self.favicon_manager.copy_favicon_to_output()

    def generate_chapter_pages(
        self,
        chapters: List[Chapter],
        generate_traditional: bool = True,
        generate_simplified: bool = True,
    ) -> None:
        """生成章节页面（简体和/或繁体）。"""
        if generate_simplified:
            self._generate_chapters(chapters, is_traditional=False)
        if generate_traditional:
            print("🈴 正在生成繁體版...")
            self._generate_chapters(chapters, is_traditional=True)

    def generate_index_pages(
        self,
        chapters: List[Chapter],
        config,
        generate_traditional: bool = True,
        generate_simplified: bool = True,
    ) -> None:
        """生成首页（简体和/或繁体）。"""
        if generate_simplified:
            self._generate_index(chapters, config.get_book_title(is_traditional=False), is_traditional=False)
        if generate_traditional:
            self._generate_index(chapters, config.get_book_title(is_traditional=True), is_traditional=True)

    # ------------------------------------------------------------------ #
    # Chapter generation (unified)                                        #
    # ------------------------------------------------------------------ #

    def _generate_chapters(self, chapters: List[Chapter], is_traditional: bool) -> None:
        """生成所有章节页面的统一实现，is_traditional 控制简/繁分支。"""
        for i, chapter in enumerate(chapters):
            filename = (
                self.i18n_processor.get_traditional_filename(chapter.filename)
                if is_traditional
                else chapter.filename
            )

            nav_data = self._build_navigation(chapters, i, is_traditional)
            lang_switch_links = self._build_lang_switch_links(filename, is_traditional)

            processed_content = self._process_i18n_placeholders(chapter.content, is_traditional)
            chapter_title_html, content_body = self._extract_chapter_title(
                processed_content, chapter.title
            )

            if is_traditional:
                title = self.i18n_processor.to_traditional(chapter.title)
                chapter_title_html = self.i18n_processor.to_traditional(chapter_title_html)
                chapter_toc = self.i18n_processor.to_traditional(chapter.chapter_toc)
                content_body = self.i18n_processor.to_traditional(content_body)
                prev_link = self.i18n_processor.to_traditional(nav_data["prev_link"])
                next_link = self.i18n_processor.to_traditional(nav_data["next_link"])
                top_nav_links = self.i18n_processor.to_traditional(nav_data["top_nav_links"])
            else:
                title = self.i18n_processor.ensure_simplified(chapter.title)
                chapter_title_html = self.i18n_processor.ensure_simplified(chapter_title_html)
                chapter_toc = self.i18n_processor.ensure_simplified(chapter.chapter_toc)
                content_body = self.i18n_processor.ensure_simplified(content_body)
                prev_link = self.i18n_processor.ensure_simplified(nav_data["prev_link"])
                next_link = self.i18n_processor.ensure_simplified(nav_data["next_link"])
                top_nav_links = self.i18n_processor.ensure_simplified(nav_data["top_nav_links"])

            chapter_title_html = self._inject_qa_count_into_h1(
                chapter_title_html, chapter, is_traditional
            )
            content_body = self._add_qa_counts_to_content_headings(
                content_body, chapter.qa_count_metadata, is_traditional
            )

            home_link = "index_trad.html" if is_traditional else "index.html"
            qa_banner = (
                self._build_qa_banner(is_traditional)
                if getattr(chapter, "is_qa", False)
                else ""
            )
            html_content = self.i18n_template_manager.render_chapter(
                is_traditional=is_traditional,
                title=title,
                chapter_title=chapter_title_html,
                chapter_qa_count="",
                chapter_toc=chapter_toc,
                content=content_body,
                prev_link=prev_link,
                next_link=next_link,
                top_nav_links=top_nav_links,
                home_link=home_link,
                lang_switch_links=lang_switch_links,
                favicon_tag=self.favicon_tag,
                qa_banner=qa_banner,
            )

            self.file_manager.write_file(filename, html_content)

    # ------------------------------------------------------------------ #
    # Index generation (unified)                                          #
    # ------------------------------------------------------------------ #

    def _generate_index(
        self, chapters: List[Chapter], book_title: str, is_traditional: bool
    ) -> None:
        """生成首页的统一实现，is_traditional 控制简/繁分支。"""
        if is_traditional:
            trad_chapters = self._build_traditional_chapter_list(chapters)
            toc_html = self.toc_generator.build_index_toc(trad_chapters, is_traditional=True)
            index_filename = "index_trad.html"
            lang_switch_links = self._build_lang_switch_links(index_filename, is_traditional=True)
            source_filename = self._build_source_filename(is_traditional=True)
            html_content = self.i18n_template_manager.render_index(
                is_traditional=True,
                book_title=self.i18n_processor.to_traditional(book_title),
                toc_items=toc_html,
                lang_switch_links=lang_switch_links,
                favicon_tag=self.favicon_tag,
                source_filename=source_filename,
            )
        else:
            toc_html = self.toc_generator.build_index_toc(chapters, is_traditional=False)
            index_filename = "index.html"
            lang_switch_links = self._build_lang_switch_links(index_filename, is_traditional=False)
            source_filename = self._build_source_filename(is_traditional=False)
            html_content = self.i18n_template_manager.render_index(
                is_traditional=False,
                book_title=self.i18n_processor.ensure_simplified(book_title),
                toc_items=self.i18n_processor.ensure_simplified(toc_html),
                lang_switch_links=lang_switch_links,
                favicon_tag=self.favicon_tag,
                # 來源檔連結保持原樣（不做簡繁轉換），避免破壞檔名與資料夾路徑
                source_filename=source_filename,
            )

        self.file_manager.write_file(index_filename, html_content)

    def _build_traditional_chapter_list(self, chapters: List[Chapter]) -> List[Chapter]:
        """复制 chapters 列表，将 title/toc_items 转为繁体，保留元数据引用。"""
        trad_chapters = []
        for ch in chapters:
            trad_ch = Chapter(
                title=self.i18n_processor.to_traditional(ch.title),
                filename=ch.filename,
            )
            trad_ch.toc_items = [
                TOCItem(
                    level=item.level,
                    text=self.i18n_processor.to_traditional(item.text),
                    anchor=item.anchor,
                )
                for item in ch.toc_items
            ]
            trad_ch.qa_count_metadata = ch.qa_count_metadata
            trad_chapters.append(trad_ch)
        return trad_chapters

    # ------------------------------------------------------------------ #
    # Navigation & i18n helpers                                           #
    # ------------------------------------------------------------------ #

    def _build_navigation(
        self, chapters: List[Chapter], current_index: int, is_traditional: bool
    ) -> Dict[str, str]:
        """生成上/下章导航链接。"""
        prev_link = next_link = top_nav_links = ""

        if current_index > 0:
            prev_ch = chapters[current_index - 1]
            prev_fn = (
                self.i18n_processor.get_traditional_filename(prev_ch.filename)
                if is_traditional
                else prev_ch.filename
            )
            prev_title = re.sub(r"<.*?>", "", prev_ch.title)
            prev_link = f'<a href="{prev_fn}">⬅️ {prev_title}</a>'

        if current_index < len(chapters) - 1:
            next_ch = chapters[current_index + 1]
            next_fn = (
                self.i18n_processor.get_traditional_filename(next_ch.filename)
                if is_traditional
                else next_ch.filename
            )
            next_title = re.sub(r"<.*?>", "", next_ch.title)
            next_link = f'<a href="{next_fn}">{next_title} ➡️</a>'

        if prev_link or next_link:
            top_nav_links = f'<div class="top-nav-buttons">{prev_link}{next_link}</div>'

        return {"prev_link": prev_link, "next_link": next_link, "top_nav_links": top_nav_links}

    def _build_source_filename(self, is_traditional: bool = False) -> str:
        """組合首頁底部的來源連結（Word + 任何附加 PDF + 線上 QA 校稿工具）。

        每個來源檔輸出成一個可下載的超連結：
        - ``href`` 指向來源檔相對於輸出資料夾的路徑，點擊即可下載原始檔。
        - 連結文字保留原始檔名。

        若有附加 QA 來源，再加上第三個連結，直接連到線上校稿工具
        ``qa/index.html``（非下載，標籤可隨語言切換）。

        來源檔連結的 HTML 不做任何簡繁轉換，以免破壞實際檔名或資料夾路徑
        （例如以繁體命名的「問答錄2」資料夾若被轉成簡體就會連結失效）。
        """
        sources: List[Path] = []
        if self.input_file:
            sources.append(Path(self.input_file))
        sources.extend(self.extra_source_files)

        links = []
        for source in sources:
            name = source.name
            href = self._build_source_href(source)
            links.append(
                f'<a class="source-link" href="{escape(href, quote=True)}" '
                f'download="{escape(name, quote=True)}">{escape(name)}</a>'
            )

        if self.include_qa_source:
            qa_link = getattr(Constants, "QA_INDEX_LINK", "../qa/index.html")
            qa_label = get_i18n_text(
                "qa.source_label", is_traditional, "線上答疑校稿稿（qa）"
            )
            links.append(
                f'<a class="source-link" href="{escape(qa_link, quote=True)}">'
                f"{escape(qa_label)}</a>"
            )

        return "、".join(links)

    def _build_source_href(self, source: Path) -> str:
        """計算來源檔相對於輸出資料夾的下載連結（使用 POSIX 斜線）。

        來源檔（Word / PDF）與輸出的電子書一同部署在站台上，因此以輸出資料夾
        為基準計算相對路徑即可正確連到原始檔；若無法計算（例如不同磁碟）則
        退回只用檔名。
        """
        try:
            rel = os.path.relpath(
                Path(source).resolve(),
                self.file_manager.output_folder.resolve(),
            )
        except (ValueError, OSError):
            rel = source.name
        return Path(rel).as_posix()

    def _build_lang_switch_links(self, current_filename: str, is_traditional: bool) -> str:
        """生成语言切换 HTML 片段。"""
        simplified_text = get_i18n_text("language_switch.simplified", False, "简体")
        traditional_text = get_i18n_text("language_switch.traditional", True, "繁體")

        if is_traditional:
            simplified_fn = self.i18n_processor.get_simplified_filename(current_filename)
            return (
                f'<a href="{simplified_fn}">{simplified_text}</a> | '
                f'<a href="{current_filename}">{traditional_text}</a>'
            )
        else:
            traditional_fn = self.i18n_processor.get_traditional_filename(current_filename)
            return (
                f'<a href="{current_filename}">{simplified_text}</a> | '
                f'<a href="{traditional_fn}">{traditional_text}</a>'
            )

    def _process_i18n_placeholders(self, content: str, is_traditional: bool) -> str:
        """替换内容中的 i18n 占位符（如 {{back_to_chapter_toc}}）。

        QA 章節的校稿徽章使用 ``{{qa_proofread}}`` / ``{{qa_unproofread}}`` 佔位符；
        在此（OpenCC 轉換之前）換成對應語言的文字，避免徽章被雙重轉換。
        """
        back_to_toc = get_i18n_text("ui.back_to_chapter_toc", is_traditional, "回到本章目錄")
        content = content.replace("{{back_to_chapter_toc}}", back_to_toc)

        qa_proofread = get_i18n_text("qa.proofread", is_traditional, "已人工校稿")
        qa_unproofread = get_i18n_text(
            "qa.unproofread", is_traditional, "AI 轉錄，尚未校對"
        )
        content = content.replace("{{qa_proofread}}", qa_proofread)
        content = content.replace("{{qa_unproofread}}", qa_unproofread)
        return content

    def _build_qa_banner(self, is_traditional: bool) -> str:
        """為 QA 章節建立頂部來源橫幅（連到線上校稿工具 qa/index.html）。

        徽章文字取自 config（已是對應語言），連結為 ASCII 路徑；本片段在內文
        OpenCC 轉換之後才併入模板，不會被再次轉換。
        """
        text = get_i18n_text(
            "qa.banner",
            is_traditional,
            "本章由錄音 AI 轉錄、人工校稿中。點此查看來源與校稿進度",
        )
        link = getattr(Constants, "QA_INDEX_LINK", "../qa/index.html")
        return (
            f'<div class="qa-source-banner">'
            f'<a href="{escape(link, quote=True)}">📝 {escape(text)}</a>'
            f"</div>"
        )

    # ------------------------------------------------------------------ #
    # Content transforms                                                  #
    # ------------------------------------------------------------------ #

    def _extract_chapter_title(self, content: str, chapter_title: str):
        """提取并移除内容中的第一个 <h1>，返回 (h1_html, remaining_content)。"""
        h1_match = re.search(r"<h1[^>]*>.*?</h1>", content, re.DOTALL)
        if h1_match:
            return h1_match.group(0), content.replace(h1_match.group(0), "", 1)
        return f"<h1>{chapter_title}</h1>", content

    def _inject_qa_count_into_h1(
        self, chapter_title_html: str, chapter: Chapter, is_traditional: bool
    ) -> str:
        """将章节问答总数注入到 h1 标签内部。"""
        if chapter.qa_count_metadata:
            total_qa = self.toc_generator.get_chapter_level_qa_count(chapter)
        elif chapter.content:
            total_qa = self.toc_generator.get_total_qa_count_for_chapter(chapter.content)
        else:
            total_qa = 0

        if total_qa > 0 and "</h1>" in chapter_title_html:
            count_span = f'<span class="chapter-qa-count">({total_qa})</span>'
            if is_traditional:
                count_span = self.i18n_processor.to_traditional(count_span)
            chapter_title_html = chapter_title_html.replace("</h1>", f"{count_span}</h1>")

        return chapter_title_html

    def _add_qa_counts_to_content_headings(
        self,
        content: str,
        qa_metadata: Optional[QACountMetadata],
        is_traditional: bool = False,
    ) -> str:
        """为内容中所有 h2-h4 标题注入问答数量 span。"""
        if not qa_metadata or not qa_metadata.anchor_counts:
            return content

        heading_pattern = r'<(h[2-4])[^>]*id="([^"]+)"[^>]*>(.*?)</\1>'

        def replace_heading(match):
            tag, anchor, title_content = match.group(1), match.group(2), match.group(3)
            qa_count = qa_metadata.get_count_for_anchor(anchor)
            if qa_count > 0:
                count_span = f'<span class="chapter-qa-count">({qa_count})</span>'
                if is_traditional:
                    count_span = self.i18n_processor.to_traditional(count_span)
                return f'<{tag} id="{anchor}">{title_content}{count_span}</{tag}>'
            return match.group(0)

        return re.sub(heading_pattern, replace_heading, content)
