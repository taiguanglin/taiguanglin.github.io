"""Tests for core/document_parser.py (Word .docx parsing)"""

import pytest
from docx import Document

from config.settings import Settings
from core.document_parser import DocumentParser
from utils.file_utils import FileManager


@pytest.fixture
def settings():
    return Settings(
        id_content_length=50,
        favicon_search_patterns=["favicon.ico"],
    )


def _add_multiline_paragraph(doc, lines):
    """加入一個內含多行（w:br 換行）的段落，模擬 Word 提問／回答段落。"""
    p = doc.add_paragraph()
    for i, line in enumerate(lines):
        run = p.add_run(line)
        if i < len(lines) - 1:
            run.add_break()
    return p


class TestSpaceSeparatedQuestionHeader:
    """「名字 日期 HH:MM」空格分隔提問頭（名字後無冒號）。

    Word 偶發此格式（2025-05-14 貼吧 恒河沙丫）。時間戳裡的冒號（19:28）
    不可被當成名字分隔符，否則日期與小時被併進名字、分鐘（28）漏成內文開頭。
    """

    def test_space_header_question_markup(self, settings, tmp_path):
        docx_path = tmp_path / "space_header.docx"
        doc = Document()
        doc.add_heading("测试章", level=1)
        _add_multiline_paragraph(doc, [
            "恒河沙丫 2025-05-14 19:28",
            "师父曾讲过极乐世界分九品，分别与娑婆世界的哪些道相对应呢？",
        ])
        _add_multiline_paragraph(doc, [
            "Taiguanglin：",
            "师父讲过极乐世界分九品……，这个在第一本书里说过了。",
        ])
        doc.save(docx_path)

        parser = DocumentParser(settings, FileManager(tmp_path / "out"))
        chapters, _ = parser.parse_document(docx_path)

        assert len(chapters) == 1
        content = chapters[0].content
        assert '<span class="questioner">恒河沙丫</span>' in content
        assert '<span class="question-time">2025-05-14 19:28</span>' in content
        # 「28」必須歸入時間分鐘，不可出現在問題文字開頭
        assert '<div class="question-text">28' not in content
        assert (
            '<div class="question-text">师父曾讲过极乐世界分九品，'
            '分别与娑婆世界的哪些道相对应呢？</div>'
        ) in content
        # 問題 id 以修正後的名字／時間／內容計算（hash 輸入不含漏出的 28）
        assert '<span class="questioner">恒河沙丫 2025-05-14 19</span>' not in content

    def test_colon_header_question_unchanged(self, settings, tmp_path):
        """標準「名字：日期 HH:MM」格式不受新邏輯影響。"""
        docx_path = tmp_path / "colon_header.docx"
        doc = Document()
        doc.add_heading("测试章", level=1)
        _add_multiline_paragraph(doc, [
            "恒河沙丫：2025-05-14 19:01",
            "顶礼Tai师父！",
        ])
        _add_multiline_paragraph(doc, [
            "Taiguanglin：",
            "感恩。",
        ])
        doc.save(docx_path)

        parser = DocumentParser(settings, FileManager(tmp_path / "out"))
        chapters, _ = parser.parse_document(docx_path)

        content = chapters[0].content
        assert '<span class="questioner">恒河沙丫</span>' in content
        assert '<span class="question-time">2025-05-14 19:01</span>' in content
        assert '<div class="question-text">顶礼Tai师父！</div>' in content
