"""章節收尾邏輯（共用）

把一組已生成的 HTML 內容區塊（content_blocks）與目錄項（toc_items）整理成
完整的 ``Chapter``：合併連續問答、插入回到頂部連結、計算問答計數、生成本章目錄。

此模組由 ``DocumentParser``（Word）與 ``PDFParser``（PDF）共用，確保不同來源
產生的章節在版型與標記上完全一致；未來新增的解析器（例如從 ``qa/`` 資料夾
產生）也應呼叫這裡的 :func:`finalize_chapter`。
"""

from typing import List, Tuple

from models.document_models import Chapter, TOCItem
from config.settings import Settings


def finalize_chapter(
    chapter: Chapter,
    content_blocks: List[str],
    toc_items: List[Tuple[int, str, str]],
    settings: Settings,
) -> Chapter:
    """完成章節處理（合併問答、回到頂部、計算問答計數、生成目錄）。

    Args:
        chapter: 已設定 ``title``/``filename`` 的章節物件
        content_blocks: 章節內所有 HTML 區塊（含第一個 ``<h1>``）
        toc_items: ``(level, text, anchor)`` 清單（通常為 h2-h4）
        settings: 程式設定（控制 ``merge_qa_blocks`` / ``enable_back_to_top``）

    Returns:
        填好 ``content`` / ``chapter_toc`` / ``toc_items`` / ``qa_count_metadata``
        的同一個 ``Chapter`` 物件。
    """
    from generators.toc_generator import TOCGenerator

    if settings.merge_qa_blocks:
        content_blocks = merge_qa_blocks(content_blocks)

    if settings.enable_back_to_top:
        content_blocks = insert_back_to_top(content_blocks)

    chapter.content = "\n".join(content_blocks)

    toc_generator = TOCGenerator()

    chapter.qa_count_metadata = toc_generator.generate_qa_count_metadata(
        chapter.content, toc_items, chapter.filename
    )

    chapter.chapter_toc = toc_generator.build_collapsible_chapter_toc(
        toc_items,
        html_content=chapter.content,
        qa_metadata=chapter.qa_count_metadata,
    )

    chapter.toc_items = [
        TOCItem(level=level, text=text, anchor=anchor)
        for level, text, anchor in toc_items
    ]

    return chapter


def merge_qa_blocks(content_blocks: List[str]) -> List[str]:
    """合併連續的問答區塊。

    對於已經是完整 ``<div class="question" id=...>...</div>`` /
    ``<div class="answer" id=...>...</div>`` 的區塊（PDF 解析器即如此產生），
    下方的 ``startswith`` 判斷不會命中，因此會原樣保留，屬於無害的 no-op。
    """
    merged_blocks = []
    i = 0

    while i < len(content_blocks):
        current_block = content_blocks[i]

        if current_block.startswith('<div class="question">'):
            current_block = current_block.rstrip()
            if current_block.endswith('</div>'):
                current_block = current_block[:current_block.rfind('</div>')].rstrip()
            question_parts = [current_block]
            i += 1

            while i < len(content_blocks):
                next_block = content_blocks[i]

                if (next_block.startswith('<div class="question">') or
                        next_block.startswith('<div class="answer">') or
                        next_block.startswith('<h1') or
                        next_block.startswith('<h2>') or
                        next_block.startswith('<h3>') or
                        next_block.startswith('<hr>')):
                    break

                if next_block.startswith('<p>'):
                    content = next_block.replace('<p>', '').replace('</p>', '')
                    question_parts.append(f'    <div class="question-text">{content}</div>')
                    i += 1
                else:
                    break

            question_parts.append('</div>')
            merged_blocks.append('\n'.join(question_parts))

        elif current_block.startswith('<div class="answer">'):
            answer_parts = [current_block]
            i += 1

            while i < len(content_blocks):
                next_block = content_blocks[i]

                if (next_block.startswith('<div class="question">') or
                        next_block.startswith('<div class="answer">') or
                        next_block.startswith('<h1') or
                        next_block.startswith('<h2>') or
                        next_block.startswith('<h3>') or
                        next_block.startswith('<hr>')):
                    break

                if next_block.startswith('<div class="answer-text">'):
                    answer_parts.append('    ' + next_block)
                    i += 1
                elif next_block.startswith('<p>'):
                    content = next_block.replace('<p>', '').replace('</p>', '')
                    answer_parts.append(f'    <div class="answer-text">{content}</div>')
                    i += 1
                else:
                    break

            if not answer_parts[-1].endswith('</div>'):
                answer_parts.append('</div>')

            merged_blocks.append('\n'.join(answer_parts))

        else:
            merged_blocks.append(current_block)
            i += 1

    return merged_blocks


def insert_back_to_top(content_blocks: List[str]) -> List[str]:
    """根據章節內 H2/H3 結構插入回到頂部連結。"""
    output_blocks = []
    h3_count = 0
    h2_count = 0
    last_heading_type = None

    for block in content_blocks:
        is_h2 = block.startswith("<h2 ")
        is_h3 = block.startswith("<h3 ")

        if is_h3:
            if last_heading_type == "h3":
                output_blocks.append('<div class="back-to-top"><a href="#top">🔝 {{back_to_chapter_toc}}</a></div>')
            h3_count += 1
            last_heading_type = "h3"
        elif is_h2 and h3_count == 0:
            if last_heading_type == "h2":
                output_blocks.append('<div class="back-to-top"><a href="#top">🔝 {{back_to_chapter_toc}}</a></div>')
            h2_count += 1
            last_heading_type = "h2"

        output_blocks.append(block)

    output_blocks.append('<div class="back-to-top"><a href="#top">🔝 {{back_to_chapter_toc}}</a></div>')
    return output_blocks
