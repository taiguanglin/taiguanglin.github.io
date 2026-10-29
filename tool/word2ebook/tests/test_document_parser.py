"""Tests for core/document_parser.py (Word .docx parsing)"""

import re

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


def _make_1x1_png(path, rgb=(255, 0, 0)):
    """產生一張有效的 1x1 PNG（zlib 手刻，不依賴 PIL）。

    ``rgb`` 讓不同圖檔有不同位元組內容——python-docx 會對相同內容的
    圖片重用同一個 relationship，測試多圖時必須給不同顏色。
    """
    import struct
    import zlib

    def chunk(typ, data):
        body = typ + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)   # 1x1、8bit、truecolor
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00" + bytes(rgb)))
        + chunk(b"IEND", b"")
    )


def _find_paragraph(doc, key):
    for p in doc.paragraphs:
        if key in p.text:
            return p
    raise AssertionError(f"paragraph containing {key!r} not found")


def _attach_image(paragraph, doc, tmp_path, name="pic.png", rgb=(255, 0, 0)):
    """在段落尾端附一張圖片（模擬 Word 的 w:drawing）。"""
    png = tmp_path / name
    _make_1x1_png(png, rgb)
    paragraph.add_run().add_picture(str(png))


class TestImageBearingQuestionParagraph:
    """段落同時含圖片與提問文字時，文字不可被丟棄。

    根因（2026-10）：_paragraph_to_html 只要 _extract_image_from_paragraph
    有回傳就 return image_html，同段落裡的「問者：日期」標頭與問題本文被整段
    丟棄。wenda2_ebook 中 2025-03-10 贴吧用户_QUDy8Na、2025-05-15 猫猫|、
    2025-03-12 心的选择 三題的提問就這樣消失，只剩孤立答案。
    """

    def test_question_text_survives_images(self, settings, tmp_path):
        docx_path = tmp_path / "img_question.docx"
        doc = Document()
        doc.add_heading("测试章", level=1)
        q = _add_multiline_paragraph(doc, [
            "贴吧用户_QUDy8Na：2025-03-10 18:29",
            "师父，目前降魔坐和莲花坐都能到一百分钟多些，怕受伤不敢再挑战。"
            "有附图请师父查阅，指点我姿势是否正确？",
        ])
        _add_multiline_paragraph(doc, [
            "Taiguanglin：",
            "贴吧用户_QUDy8Na，打坐的姿势本身是对的，这个没有什么。",
        ])
        _attach_image(q, doc, tmp_path)
        doc.save(docx_path)

        parser = DocumentParser(settings, FileManager(tmp_path / "out"))
        chapters, _ = parser.parse_document(docx_path)

        content = chapters[0].content
        # 問者與時間仍在（以前整段被丟棄，只剩圖片）
        assert '<span class="questioner">贴吧用户_QUDy8Na</span>' in content
        assert '<span class="question-time">2025-03-10 18:29</span>' in content
        assert "目前降魔坐和莲花坐都能到一百分钟多些" in content
        assert 'class="question-text"' in content
        # 圖片仍照常輸出
        assert "<img" in content
        # 答案與問題配對成同一組，不再孤立
        assert "贴吧用户_QUDy8Na，打坐的姿势本身是对的" in content

    def test_pure_image_paragraph_unchanged(self, settings, tmp_path):
        """純圖片段落（無文字）維持原行為：只輸出圖片，不產生空 <p>。"""
        docx_path = tmp_path / "img_only.docx"
        doc = Document()
        doc.add_heading("测试章", level=1)
        _add_multiline_paragraph(doc, [
            "Taiguanglin：",
            "先看这张图。",
        ])
        _attach_image(_find_paragraph(doc, "Taiguanglin"), doc, tmp_path)
        doc.save(docx_path)

        parser = DocumentParser(settings, FileManager(tmp_path / "out"))
        chapters, _ = parser.parse_document(docx_path)

        content = chapters[0].content
        assert "<img" in content
        assert "<p></p>" not in content

    def test_multiple_images_in_one_paragraph(self, settings, tmp_path):
        """同一段落的多張附圖都要輸出（提問常附「圖1／圖2／圖3」）。"""
        docx_path = tmp_path / "multi_img.docx"
        doc = Document()
        doc.add_heading("测试章", level=1)
        q = _add_multiline_paragraph(doc, [
            "贴吧用户_QUDy8Na：2025-03-10 18:29",
            "师父，有附图请师父查阅，指点我姿势是否正确？",
        ])
        doc.save(docx_path)
        _attach_image(q, doc, tmp_path, name="p1.png", rgb=(255, 0, 0))
        _attach_image(q, doc, tmp_path, name="p2.png", rgb=(0, 255, 0))
        _attach_image(q, doc, tmp_path, name="p3.png", rgb=(0, 0, 255))
        doc.save(docx_path)

        parser = DocumentParser(settings, FileManager(tmp_path / "out"))
        chapters, _ = parser.parse_document(docx_path)

        content = chapters[0].content
        assert content.count("<img") == 3, content.count("<img")
        # 三張圖的 src 必須互不相同
        srcs = re.findall(r'src="([^"]+)"', content)
        assert len(srcs) == 3 and len(set(srcs)) == 3, srcs
