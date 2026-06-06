"""Tests for core/chapter_finalizer.py (shared Word/PDF chapter finalize logic)."""

import pytest

from core.chapter_finalizer import (
    finalize_chapter,
    merge_qa_blocks,
    insert_back_to_top,
)
from models.document_models import Chapter, TOCItem
from config.settings import DEFAULT_SETTINGS


# ---------------------------------------------------------------------------
# insert_back_to_top
# ---------------------------------------------------------------------------

class TestInsertBackToTop:
    def test_back_to_top_between_consecutive_h2_and_at_end(self):
        blocks = [
            '<h1 id="c">章</h1>',
            '<h2 id="a">A</h2>',
            '<p>x</p>',
            '<h2 id="b">B</h2>',
            '<p>y</p>',
        ]
        out = insert_back_to_top(blocks)
        # one inserted before second h2, one appended at the very end
        assert sum(1 for b in out if 'back-to-top' in b) == 2
        assert 'back-to-top' in out[-1]
        # the inserted one sits before <h2 id="b">
        idx_btt = next(i for i, b in enumerate(out) if 'back-to-top' in b)
        idx_h2b = next(i for i, b in enumerate(out) if 'id="b"' in b)
        assert idx_btt < idx_h2b

    def test_single_section_only_final_back_to_top(self):
        blocks = ['<h1 id="c">章</h1>', '<h2 id="a">A</h2>', '<p>x</p>']
        out = insert_back_to_top(blocks)
        assert sum(1 for b in out if 'back-to-top' in b) == 1


# ---------------------------------------------------------------------------
# merge_qa_blocks
# ---------------------------------------------------------------------------

class TestMergeQABlocks:
    def test_legacy_question_merges_following_paragraphs(self):
        blocks = [
            '<div class="question">\n  <span class="questioner">甲</span>\n</div>',
            '<p>第一段問題</p>',
            '<p>第二段問題</p>',
            '<div class="answer">\n</div>',
        ]
        out = merge_qa_blocks(blocks)
        merged_q = out[0]
        assert merged_q.count('<div class="question-text">') == 2
        assert '第一段問題' in merged_q and '第二段問題' in merged_q

    def test_id_bearing_divs_are_noop(self):
        """PDF-style complete divs (with id) must be passed through untouched."""
        q = '<div class="question" id="question-abc">\n    <div class="question-text">問</div>\n</div>'
        a = '<div class="answer" id="answer-abc">\n    <div class="answer-text">答</div>\n</div>'
        out = merge_qa_blocks([q, a])
        assert out == [q, a]


# ---------------------------------------------------------------------------
# finalize_chapter
# ---------------------------------------------------------------------------

class TestFinalizeChapter:
    def test_populates_content_toc_and_metadata(self):
        chapter = Chapter(title="測試章", filename="13.html")
        anchor = "2025nian-6yue-9ri-tie-ba"
        content_blocks = [
            '<h1 id="ch">測試章</h1>',
            f'<h2 id="{anchor}">2025年6月9日 贴吧</h2>',
            '<div class="question" id="question-1">\n    <div class="question-text">問題</div>\n</div>',
            '<div class="answer" id="answer-1">\n    <div class="answer-text">回答</div>\n</div>',
        ]
        toc_items = [(2, "2025年6月9日 贴吧", anchor)]

        result = finalize_chapter(chapter, content_blocks, toc_items, DEFAULT_SETTINGS)

        assert result is chapter
        assert anchor in chapter.content
        assert '<div class="question"' in chapter.content
        # toc_items converted to TOCItem objects
        assert len(chapter.toc_items) == 1
        assert isinstance(chapter.toc_items[0], TOCItem)
        assert chapter.toc_items[0].anchor == anchor
        # collapsible chapter toc built
        assert chapter.chapter_toc
        assert "2025年6月9日" in chapter.chapter_toc
        # qa metadata generated
        assert chapter.qa_count_metadata is not None

    def test_final_back_to_top_present(self):
        chapter = Chapter(title="X", filename="13.html")
        blocks = ['<h1 id="x">X</h1>', '<h2 id="a">A</h2>', '<p>p</p>']
        finalize_chapter(chapter, blocks, [(2, "A", "a")], DEFAULT_SETTINGS)
        assert 'back-to-top' in chapter.content
