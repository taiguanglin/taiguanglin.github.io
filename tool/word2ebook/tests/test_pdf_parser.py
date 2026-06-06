"""Tests for core/pdf_parser.py.

These exercise the pure ``parse_lines`` core with synthetic ``(x0, text)`` line
fixtures that mimic PyMuPDF output, so no real PDF / PyMuPDF install is needed.

Layout convention (from the real PDF):
* x0 == 118  -> indented first line of a paragraph
* x0 == 90   -> wrapped continuation / questioner / answer marker / separator
* x0 == 157/239/276 -> day header / footer / page-number (all stripped or special)
"""

import re
import pytest

from core.pdf_parser import PDFParser, _year_to_cn, _normalize_spaces
from config.settings import DEFAULT_SETTINGS

IND = 118.0   # indented (new paragraph)
CONT = 90.0   # continuation / left-margin markers


@pytest.fixture
def parser():
    return PDFParser(DEFAULT_SETTINGS)


@pytest.fixture
def one_day_two_sources():
    """A June 9 session: 贴吧 (3 questions incl. multi-part) then 微信公众号 (1)."""
    return [
        (157.0, "Tai 师父2025 年6 月9 日答疑（文字版）"),
        (239.0, "完整音频请关注微信公众号：TaiGuangLin"),
        (IND,  "师父说：今天是2025 年6 月9 号，先回答贴吧的问题。"),
        (CONT, "学生甲：2025-06-09 08:00"),
        (IND,  "1、第一个问题的内容，"),
        (CONT, "继续第一个问题。"),
        (CONT, "Taiguanglin："),
        (IND,  "这是第一个回答。"),
        (IND,  "2、第二个问题？"),
        (CONT, "Taiguanglin："),
        (IND,  "第二个回答第一段。"),
        (IND,  "第二个回答第二段。"),
        (276.5, "1234 / 2379"),
        (CONT, "———————————————————————————紫蘇："),
        (CONT, "2025-06-09 09:00"),
        (IND,  "顶礼师父，请问一个问题？"),
        (CONT, "Taiguanglin："),
        (IND,  "单个问题的回答。"),
        (IND,  "师父说：今天贴吧的问题就回答到这里。"),
        (IND,  "师父说：今天是2025 年6 月9 号，回答微信公众号的问题。"),
        (CONT, "微信用户：2025-06-08 20:00"),
        (IND,  "微信问题内容。"),
        (CONT, "Taiguanglin："),
        (IND,  "微信回答内容。"),
    ]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_year_to_cn_uses_circle_zero(self):
        assert _year_to_cn(2025) == "二〇二五"
        assert _year_to_cn(2030) == "二〇三〇"

    def test_normalize_removes_cjk_adjacent_spaces(self):
        assert _normalize_spaces("Tai 师父2025 年6 月10 号") == "Tai师父2025年6月10号"
        assert _normalize_spaces("QQ 群") == "QQ群"


# ---------------------------------------------------------------------------
# single-day structure
# ---------------------------------------------------------------------------

class TestSingleDay:
    def test_one_chapter_with_two_sections(self, parser, one_day_two_sources):
        chapters = parser.parse_lines(one_day_two_sources, start_index=12)
        assert len(chapters) == 1
        ch = chapters[0]
        assert ch.filename == "13.html"
        assert ch.title == "13二〇二五年六月"

    def test_date_source_h2_sections(self, parser, one_day_two_sources):
        ch = parser.parse_lines(one_day_two_sources, start_index=12)[0]
        texts = [t.text for t in ch.toc_items]
        assert texts == ["2025年6月9日 贴吧", "2025年6月9日 微信公众号"]
        # tieba comes before weixin and anchors are stable/unique
        anchors = [t.anchor for t in ch.toc_items]
        assert anchors[0] == "2025nian-6yue-9ri-tie-ba"
        assert anchors[1] == "2025nian-6yue-9ri-wei-xin-gong-zhong-hao"
        # h2 ids exist in content and match the toc anchors
        for a in anchors:
            assert f'id="{a}"' in ch.content

    def test_question_and_answer_counts(self, parser, one_day_two_sources):
        ch = parser.parse_lines(one_day_two_sources, start_index=12)[0]
        n_q = len(re.findall(r'<div class="question"', ch.content))
        n_a = len(re.findall(r'<div class="answer"', ch.content))
        assert n_q == 4   # tieba: q1, q2, single ; weixin: 1
        assert n_a == 4

    def test_artifacts_stripped(self, parser, one_day_two_sources):
        ch = parser.parse_lines(one_day_two_sources, start_index=12)[0]
        assert "完整音频" not in ch.content     # footer removed
        assert "2379" not in ch.content         # page number removed

    def test_reflow_joins_wrapped_lines(self, parser, one_day_two_sources):
        ch = parser.parse_lines(one_day_two_sources, start_index=12)[0]
        assert "1、第一个问题的内容，继续第一个问题。" in ch.content

    def test_multi_paragraph_answer(self, parser, one_day_two_sources):
        ch = parser.parse_lines(one_day_two_sources, start_index=12)[0]
        assert '<div class="answer-text">第二个回答第一段。</div>' in ch.content
        assert '<div class="answer-text">第二个回答第二段。</div>' in ch.content

    def test_wrapped_separator_questioner(self, parser, one_day_two_sources):
        """'———…———紫蘇：' glued + next-line time becomes a clean questioner."""
        ch = parser.parse_lines(one_day_two_sources, start_index=12)[0]
        assert '<span class="questioner">紫蘇</span>' in ch.content
        assert '<span class="question-time">2025-06-09 09:00</span>' in ch.content
        assert "———" not in ch.content   # separator dropped, not rendered

    def test_year_numeral_in_title_heading(self, parser, one_day_two_sources):
        ch = parser.parse_lines(one_day_two_sources, start_index=12)[0]
        assert "二〇二五年六月" in ch.content   # h1 uses circle-zero numerals

    def test_source_switch_paragraph_order(self, parser, one_day_two_sources):
        ch = parser.parse_lines(one_day_two_sources, start_index=12)[0]
        # tieba closer paragraph sits before the weixin h2
        closer = ch.content.index("今天贴吧的问题就回答到这里")
        weixin_h2 = ch.content.index('id="2025nian-6yue-9ri-wei-xin-gong-zhong-hao"')
        assert closer < weixin_h2

    def test_answerer_is_raw_name(self, parser, one_day_two_sources):
        ch = parser.parse_lines(one_day_two_sources, start_index=12)[0]
        assert '<span class="answerer">Taiguanglin</span>' in ch.content


# ---------------------------------------------------------------------------
# month grouping (date-based, not page-based)
# ---------------------------------------------------------------------------

class TestMonthGrouping:
    def _session(self, y, m, d, name):
        return [
            (157.0, f"Tai 师父{y} 年{m} 月{d} 日答疑（文字版）"),
            (IND,  f"师父说：今天是{y} 年{m} 月{d} 号，先回答贴吧的问题。"),
            (CONT, f"{name}：{y}-{m:02d}-{d:02d} 10:00"),
            (IND,  "问题内容。"),
            (CONT, "Taiguanglin："),
            (IND,  "回答内容。"),
        ]

    def test_out_of_order_days_grouped_by_date(self, parser):
        # August session physically before July session (mirrors real PDF 7/12)
        lines = self._session(2025, 8, 4, "甲") + self._session(2025, 7, 12, "乙")
        chapters = parser.parse_lines(lines, start_index=12)
        assert [c.title for c in chapters] == ["13二〇二五年七月", "14二〇二五年八月"]
        july, august = chapters
        assert "2025年7月12日 贴吧" in [t.text for t in july.toc_items]
        assert "2025年8月4日 贴吧" in [t.text for t in august.toc_items]

    def test_days_sorted_ascending_within_month(self, parser):
        lines = self._session(2025, 6, 11, "甲") + self._session(2025, 6, 9, "乙")
        ch = parser.parse_lines(lines, start_index=12)[0]
        texts = [t.text for t in ch.toc_items]
        assert texts == ["2025年6月9日 贴吧", "2025年6月11日 贴吧"]

    def test_start_index_offsets_chapter_numbers(self, parser):
        lines = self._session(2025, 6, 9, "甲")
        ch = parser.parse_lines(lines, start_index=12)[0]
        assert ch.filename == "13.html"
        ch2 = parser.parse_lines(lines, start_index=0)[0]
        assert ch2.filename == "01.html"
        assert ch2.title == "01二〇二五年六月"


# ---------------------------------------------------------------------------
# numbered-question handling
# ---------------------------------------------------------------------------

class TestNumberedQuestions:
    def test_all_questions_listed_then_answered(self, parser):
        """1、2、3 listed before any answer -> three separate question cards."""
        lines = [
            (157.0, "Tai 师父2025 年6 月9 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年6 月9 号，先回答贴吧的问题。"),
            (CONT, "甲：2025-06-09 08:00"),
            (IND,  "1、问题一。"),
            (IND,  "2、问题二。"),
            (IND,  "3、问题三。"),
            (CONT, "Taiguanglin："),
            (IND,  "答一。"),
            (CONT, "Taiguanglin："),
            (IND,  "答二。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        assert len(re.findall(r'<div class="question"', ch.content)) == 3

    def test_greeting_attached_to_first_numbered_question(self, parser):
        """An intro/greeting before '1、' stays in the same first question card."""
        lines = [
            (157.0, "Tai 师父2025 年6 月9 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年6 月9 号，先回答贴吧的问题。"),
            (CONT, "甲：2025-06-09 08:00"),
            (IND,  "顶礼师父，想请教三个问题："),
            (IND,  "1、问题一。"),
            (CONT, "Taiguanglin："),
            (IND,  "答一。"),
            (IND,  "2、问题二。"),
            (CONT, "Taiguanglin："),
            (IND,  "答二。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        # 2 question cards (greeting+Q1 merged, then Q2)
        assert len(re.findall(r'<div class="question"', ch.content)) == 2
        # greeting and Q1 share the same card
        first_card = ch.content.split('<div class="question"', 2)[1]
        assert "顶礼师父，想请教三个问题：" in first_card
        assert "1、问题一。" in first_card


# ---------------------------------------------------------------------------
# empty / edge
# ---------------------------------------------------------------------------

class TestEdge:
    def test_empty_input_returns_no_chapters(self, parser):
        assert parser.parse_lines([], start_index=12) == []
