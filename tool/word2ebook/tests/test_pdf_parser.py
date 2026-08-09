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

import sys
import types

from core.pdf_parser import (
    PDFParser, _year_to_cn, _normalize_spaces, _import_pymupdf, make_img_marker,
)
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

    def test_bare_page_counter_not_glued_into_word(self, parser):
        """2025-06-12-style bare footer digits must not split 菩萨 → 菩39萨."""
        lines = [
            (157.0, "Tai 师父2025 年6 月12 日答疑（文字版）"),
            (239.0, "完整音频请关注微信公众号：TaiGuangLin"),
            (IND,  "师父说：今天是2025 年6 月12 号，先回答贴吧的问题。"),
            (CONT, "学生甲：2025-06-12 08:00"),
            (IND,  "请问胖东来？"),
            (CONT, "Taiguanglin："),
            (IND,  "我觉得在菩"),
            (276.5, "39"),                 # bare per-session page counter
            (CONT, "萨这里商人职业是不求利的。"),
            (276.5, "1410 / 2379"),         # absolute counter also present
            (IND,  "师父说：今天贴吧的问题就回答到这里。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        assert "菩萨这里商人职业是不求利的" in ch.content
        assert "39萨" not in ch.content
        assert "2379" not in ch.content
        assert re.search(r">\s*39\s*<", ch.content) is None

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

    def test_cross_year_months_use_correct_year(self, parser):
        """Nov 2025 + Jan 2026 must not both become 二〇二五年."""
        lines = self._session(2025, 11, 10, "甲") + self._session(2026, 1, 5, "乙")
        chapters = parser.parse_lines(lines, start_index=16)
        assert [c.title for c in chapters] == ["17二〇二五年十一月", "18二〇二六年一月"]


# ---------------------------------------------------------------------------
# 官网 source switching (Nov–Mar PDF)
# ---------------------------------------------------------------------------

class TestGuanwangSource:
    def test_guanwang_then_weixin_sections(self, parser):
        lines = [
            (157.0, "Tai 师父2025 年11 月10 日答疑（文字版）"),
            (IND,  "师父说：今天是11 月10 号，周一，先回答官网的答疑。"),
            (CONT, "甲：2025-11-10 10:00"),
            (IND,  "官网问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "官网回答。"),
            (IND,  "师父说：今天是2025 年11 月10 号，回答微信公众号的问题。"),
            (CONT, "乙：2025-11-10 20:00"),
            (IND,  "微信问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "微信回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=16)[0]
        texts = [t.text for t in ch.toc_items]
        assert texts == ["2025年11月10日 官网", "2025年11月10日 微信公众号"]
        assert "官网问题。" in ch.content
        assert "微信问题。" in ch.content

    def test_same_day_continuation_keeps_guanwang(self, parser):
        """同一天多個「Tai 师父…日答疑」續錄不應重設成贴吧。"""
        lines = [
            (157.0, "Tai 师父2025 年11 月10 日答疑（文字版）"),
            (IND,  "师父说：今天是11 月10 号，先回答官网的答疑。"),
            (CONT, "甲：2025-11-10 10:00"),
            (IND,  "第一段问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "第一段回答。"),
            (157.0, "Tai 师父2025 年11 月10 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年11 月10 号，继续回答官网的问题。"),
            (CONT, "乙：2025-11-10 12:00"),
            (IND,  "第二段问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "第二段回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=16)[0]
        texts = [t.text for t in ch.toc_items]
        assert texts == ["2025年11月10日 官网"]
        assert texts.count("2025年11月10日 贴吧") == 0

    def test_floor_number_opening_is_guanwang(self, parser):
        """開場折行後才出現「N楼」時仍視為官网。"""
        lines = [
            (157.0, "Tai 师父2025 年11 月11 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年11 月11 号，周二，今天是什么？双"),
            (CONT, "11 吧，想买东西便宜的什么节日。咱们先来回答问题，昨天回答到127 楼。"),
            (CONT, "甲：2025-11-11 10:00"),
            (IND,  "问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=16)[0]
        assert [t.text for t in ch.toc_items] == ["2025年11月11日 官网"]

    def test_unlabeled_first_opening_defaults_to_guanwang(self, parser):
        """當天首段師父說完全未標來源時，預設官网（非贴吧）。"""
        lines = [
            (157.0, "Tai 师父2026 年1 月5 日答疑（文字版）"),
            (IND,  "师父说：今天是2026 年1 月5 号，周一，时间过得真快。"),
            (CONT, "甲：2026-01-05 10:00"),
            (IND,  "问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=18)[0]
        assert [t.text for t in ch.toc_items] == ["2026年1月5日 官网"]
        assert "贴吧" not in [t.text for t in ch.toc_items]

    def test_bare_today_is_opening_without_shifu_prefix(self, parser):
        """無「师父说」前綴的「今天是…先回答官网」也要切到官网，且首個
        無時間提問者（winnie：）不得併進開場。"""
        lines = [
            (157.0, "Tai 师父2025 年11 月15 日答疑（文字版）"),
            (IND,  "今天是2025 年11 月15 号周六，这个月的最后一次上线答疑，"),
            (CONT, "先回答官网的问题。"),
            (CONT, "winnie："),
            (IND,  "感恩顶礼Tai 师父。"),
            (CONT, "Taiguanglin："),
            (IND,  "回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=16)[0]
        assert [t.text for t in ch.toc_items] == ["2025年11月15日 官网"]
        assert "贴吧" not in [t.text for t in ch.toc_items]
        before_q = ch.content.split('<div class="question"', 1)[0]
        assert "感恩顶礼" not in before_q
        assert "先回答官网的问题" in before_q
        assert '<span class="questioner">winnie</span>' in ch.content
        assert len(re.findall(r'<div class="question"', ch.content)) == 1

    def test_incidental_gongzhonghao_in_tieba_opening(self, parser):
        """贴吧開場閒聊「回答了，去公众号领书」不應把整場誤判成微信。"""
        lines = [
            (157.0, "Tai 师父2025 年8 月4 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年8 月4 号，周一。有人问怎么领这个书，"),
            (CONT, "下边回答了，去公众号或者微信群。要贴吧不倒，从15 楼开始是正式问题。"),
            (CONT, "牧羊少年571：2025-08-04 10:00"),
            (IND,  "顶礼师父，请问三观问题？"),
            (CONT, "Taiguanglin："),
            (IND,  "贴吧回答内容。"),
            (IND,  "师父说：好了，贴吧的问题就回答到这里。"),
            (IND,  "师父说：今天是2025 年8 月4 号，回答微信公众号的问题。"),
            (CONT, "微信用户：2025-08-04 20:00"),
            (IND,  "微信问题内容。"),
            (CONT, "Taiguanglin："),
            (IND,  "微信回答内容。"),
        ]
        ch = parser.parse_lines(lines, start_index=15)[0]
        texts = [t.text for t in ch.toc_items]
        assert texts == ["2025年8月4日 贴吧", "2025年8月4日 微信公众号"]
        tieba = ch.content.index("2025年8月4日 贴吧")
        weixin = ch.content.index("2025年8月4日 微信公众号")
        assert "三观问题" in ch.content[tieba:weixin]
        assert "贴吧回答内容" in ch.content[tieba:weixin]
        assert "微信问题内容" in ch.content[weixin:]
        assert "微信问题内容" not in ch.content[tieba:weixin]

    def test_weixin_opening_mentions_tieba_overload(self, parser):
        """「微信公众号的问题。因为贴吧的问题太多了」仍應切到微信（2025-07-07）。"""
        lines = [
            (157.0, "Tai 师父2025 年7 月7 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年7 月7 号，周一，先回答贴吧的问题。"),
            (CONT, "甲：2025-07-07 10:00"),
            (IND,  "贴吧问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "贴吧回答。"),
            (IND,  "师父说：好了，今天贴吧的问题就回答到这里。"),
            (IND,  "师父说：今天是2025 年7 月7 号，虽然时间已经到了7 月8号，"),
            (CONT, "但是回答还是7 月7 号的问题，微信公众号的问题。因为贴吧的问题太多了。"),
            (CONT, "现在看微信公众号的问题。"),
            (CONT, "乙：2025-07-07 20:00"),
            (IND,  "微信问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "微信回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=14)[0]
        texts = [t.text for t in ch.toc_items]
        assert texts == ["2025年7月7日 贴吧", "2025年7月7日 微信公众号"]
        tieba = ch.content.index("2025年7月7日 贴吧")
        weixin = ch.content.index("2025年7月7日 微信公众号")
        assert "贴吧问题" in ch.content[tieba:weixin]
        assert "微信问题" in ch.content[weixin:]
        assert "微信问题" not in ch.content[tieba:weixin]

    def test_closing_does_not_spawn_empty_tieba(self, parser):
        """官网場次結尾「今天贴吧的答疑就到这里」不應長出空的贴吧段。"""
        lines = [
            (157.0, "Tai 师父2025 年8 月9 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年8 月9 号，周六，从164 楼开始回答。"),
            (CONT, "甲：2025-08-09 10:00"),
            (IND,  "官网问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "官网回答。"),
            (IND,  "师父说：今天贴吧的答疑就到这里，光是录音就一个半小时了。"),
            (IND,  "师父说：今天是2025 年8 月9 号，回答微信公众号的问题。"),
            (CONT, "乙：2025-08-09 20:00"),
            (IND,  "微信问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "微信回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=15)[0]
        texts = [t.text for t in ch.toc_items]
        assert texts == ["2025年8月9日 官网", "2025年8月9日 微信公众号"]
        assert "2025年8月9日 贴吧" not in texts
        assert "一个半小时" in ch.content
        guan = ch.content.index("2025年8月9日 官网")
        weixin = ch.content.index("2025年8月9日 微信公众号")
        assert "一个半小时" in ch.content[guan:weixin]


    def test_bang_suffix_questioner(self, parser):
        """Weixin nicknames sometimes end with ! (咩咩!) instead of a colon."""
        lines = [
            (157.0, "Tai 师父2025 年12 月11 日答疑（文字版）"),
            (IND,  "师父说：今天是12 月11 号，回答微信公众号的问题。"),
            (CONT, "娜娜："),
            (IND,  "上一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "上一个回答。"),
            (CONT, "咩咩!"),
            (CONT, '"'),
            (CONT, "#"),
            (CONT, "$"),
            (CONT, "%"),
            (CONT, "&"),
            (CONT, "+："),
            (IND,  "Tai师好，请问一下读《地藏经》时耳边有女人叹息声的幻听，为何？"),
            (CONT, "Taiguanglin："),
            (IND,  "那下一个问题，咩咩!"),
        ]
        ch = parser.parse_lines(lines, start_index=16)[0]
        assert '<span class="questioner">咩咩</span>' in ch.content
        assert "<p>咩咩!</p>" not in ch.content
        assert "<p>#</p>" not in ch.content
        assert "读《地藏经》时耳边有女人叹息声的幻听" in ch.content
        # junk symbols must not become answer/question paras
        assert ch.content.count('<div class="question"') == 2

    def test_symbol_junk_inside_open_question(self, parser):
        """PDF Symbol font runs after question body must not become question-text."""
        junk = ['"', "#", "$", "%", "&", "'", "(", ")", "*", "+", ",", "-", ".", "/"]
        lines = [
            (157.0, "Tai 师父2025 年12 月8 日答疑（文字版）"),
            (IND,  "师父说：今天是12 月8 号，先回答官网的问题。"),
            (CONT, "上官："),
            (IND,  "1、第一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "第一个回答。"),
            (IND,  "2、能听到您的法，已经不止是三生有幸。"),
            *[(CONT, s) for s in junk],
            (CONT, "Taiguanglin："),
            (IND,  "未来会传多长时间我不好说。"),
        ]
        ch = parser.parse_lines(lines, start_index=16)[0]
        assert '<span class="questioner">上官</span>' in ch.content
        assert "能听到您的法，已经不止是三生有幸。" in ch.content
        assert "未来会传多长时间我不好说。" in ch.content
        for s in junk:
            assert f'<div class="question-text">{s}</div>' not in ch.content
            assert f"<p>{s}</p>" not in ch.content
        assert '<div class="question-text">&amp;</div>' not in ch.content
        # body ends cleanly — no leftover junk question-text siblings
        assert (
            '能听到您的法，已经不止是三生有幸。</div>\n</div>\n<div class="answer"'
            in ch.content
        )
    def test_bare_name_then_emoji_qtime(self, parser):
        """Display name「咩咩」above an emoji+time line should become the questioner."""
        lines = [
            (157.0, "Tai 师父2025 年11 月11 日答疑（文字版）"),
            (IND,  "师父说：今天是11 月11 号，回答微信公众号的问题。"),
            (CONT, "甲：12:00:00"),
            (IND,  "前一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "前一个回答。"),
            (CONT, "咩咩"),
            (CONT, "🐏：14:20:56"),
            (IND,  "Tai师，您好，请问打坐后出现各种虚幻的相。"),
            (CONT, "Taiguanglin："),
            (IND,  "下一个问题，咩咩"),
        ]
        ch = parser.parse_lines(lines, start_index=16)[0]
        assert '<span class="questioner">咩咩</span>' in ch.content
        assert "<p>咩咩</p>" not in ch.content
        assert "打坐后出现各种虚幻的相" in ch.content


# ---------------------------------------------------------------------------
# PDF images (marker injected into parse_lines)
# ---------------------------------------------------------------------------

class TestPdfImages:
    def test_image_marker_becomes_img_tag(self, parser):
        lines = [
            (157.0, "Tai 师父2025 年11 月10 日答疑（文字版）"),
            (IND,  "师父说：今天是11 月10 号，先回答官网的问题。"),
            (CONT, "甲：2025-11-10 10:00"),
            (IND,  "问题上文。"),
            (CONT, make_img_marker("assets/images/image_99.png")),
            (IND,  "问题下文。"),
            (CONT, "Taiguanglin："),
            (IND,  "回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=16)[0]
        assert '<img src="assets/images/image_99.png" alt="Image">' in ch.content
        # image stays inside the question card (between 上文 and 下文)
        q_pos = ch.content.index("问题上文。")
        img_pos = ch.content.index('<img src="assets/images/image_99.png"')
        below_pos = ch.content.index("问题下文。")
        a_pos = ch.content.index("回答。")
        assert q_pos < img_pos < below_pos < a_pos
        # still inside .question … </div> before the answer
        q_open = ch.content.index('<div class="question"')
        q_close = ch.content.index("</div>", ch.content.index("问题下文。"))
        assert q_open < img_pos < a_pos

    def test_image_does_not_orphan_mid_sentence(self, parser):
        """Image mid-question must not spit the rest into bare <p> outside the card."""
        lines = [
            (157.0, "Tai 师父2025 年12 月11 日答疑（文字版）"),
            (IND,  "师父说：今天是12 月11 号，先回答官网的问题。"),
            (CONT, "甲：2025-12-11 10:00"),
            (IND,  "如果双方为了任务，稍"),
            (CONT, make_img_marker("assets/images/image_53.png")),
            (IND,  "微带点执著心做事，还会再造业吗?"),
            (CONT, "Taiguanglin："),
            (IND,  "回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=16)[0]
        assert "<p>微带点执著心做事，还会再造业吗?</p>" not in ch.content
        assert "稍微带点执著心做事，还会再造业吗?" in ch.content
        assert '<img src="assets/images/image_53.png" alt="Image">' in ch.content
        # merged sentence lives in the question card
        assert '<div class="question-text">' in ch.content
        q_block_start = ch.content.index('<div class="question"')
        a_block_start = ch.content.index('<div class="answer"')
        chunk = ch.content[q_block_start:a_block_start]
        assert "稍微带点执著心做事，还会再造业吗?" in chunk
        assert "<img" in chunk

    def test_vertical_glyph_lines_merge(self, parser):
        """One-char-per-line fragments after an image merge into one paragraph."""
        lines = [
            (157.0, "Tai 师父2025 年12 月11 日答疑（文字版）"),
            (IND,  "师父说：今天是12 月11 号，先回答官网的问题。"),
            (CONT, "甲：2025-12-11 10:00"),
            (IND,  "求观世音指点我找"),
            (CONT, make_img_marker("assets/images/image_54.png")),
            (IND,  "师"),
            (IND,  "父"),
            (IND,  "您"),
            (IND,  "。"),
            (IND,  "感"),
            (IND,  "恩"),
            (IND,  "师"),
            (IND,  "父"),
            (IND,  "。"),
            (CONT, "Taiguanglin："),
            (IND,  "回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=16)[0]
        assert "<p>师</p>" not in ch.content
        assert "<p>父</p>" not in ch.content
        assert "求观世音指点我找师父您。感恩师父。" in ch.content
        assert '<img src="assets/images/image_54.png" alt="Image">' in ch.content


# ---------------------------------------------------------------------------
# numbered-question handling
# ---------------------------------------------------------------------------

class TestNumberedQuestions:
    def test_consecutive_numbered_merge_into_one_card(self, parser):
        """1、2、3 listed consecutively (no answer between) -> ONE merged question
        card (a single multi-part question), with each number its own paragraph."""
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
        # exactly one question card, with a single questioner header
        assert len(re.findall(r'<div class="question"', ch.content)) == 1
        assert ch.content.count('<span class="questioner">甲</span>') == 1
        # all three numbered items present, each as its own question-text paragraph
        for q in ("1、问题一。", "2、问题二。", "3、问题三。"):
            assert f'<div class="question-text">{q}</div>' in ch.content

    def test_continuation_question_after_answer_opens_new_card(self, parser):
        """A numbered question that comes AFTER an answer is a new turn and opens
        a new card (still attributed to the same questioner)."""
        lines = [
            (157.0, "Tai 师父2025 年6 月9 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年6 月9 号，先回答贴吧的问题。"),
            (CONT, "甲：2025-06-09 08:00"),
            (IND,  "1、问题一。"),
            (IND,  "2、问题二。"),
            (CONT, "Taiguanglin："),
            (IND,  "答。"),
            (IND,  "3、追问的问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "再答。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        # 1、2、 merge into one card; 3、 after the answer opens a second card
        assert len(re.findall(r'<div class="question"', ch.content)) == 2
        names = re.findall(r'<span class="questioner">([^<]+)</span>', ch.content)
        assert names == ["甲", "甲"]

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
# WeChat HH:MM:SS questioners (2025-11-10 / 11-11 backend timestamps)
# ---------------------------------------------------------------------------

class TestWechatClockQuestioners:
    """WeChat official-account PDF dumps use clock-only stamps (HH:MM:SS), not
    YYYY-MM-DD HH:MM. Those must become question cards or they collapse into the
    opening paragraph (the 2025-11-10 regression)."""

    def test_hhmmss_questioners_split_from_opening(self, parser):
        lines = [
            (157.0, "Tai 师父2025 年11 月10 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年11 月10 号，回答微信公众号的问题。"),
            (CONT, "亻田：10:38:28"),
            (IND,  "师父吉祥，肌肉紧绷怎么办？"),
            (CONT, "Taiguanglin："),
            (IND,  "有妄想的话身体就会绷起来。"),
            (CONT, "———————————————————————————"),
            (CONT, "素山Celine ：10:42:42"),
            (IND,  "顶礼师父，静修期间有什么注意事项吗？"),
            (CONT, "Taiguanglin："),
            (IND,  "先把第一本书和第二本书都看一看。"),
            (CONT, "———————————————————————————"),
            (CONT, "淡薄：13:17:45"),
            (IND,  "师父好，"),
            (IND,  "1、为什么有的人生孩子不痛？"),
            (CONT, "Taiguanglin："),
            (IND,  "应该算是业力。"),
            (IND,  "2、打无痛是不是在逃避业力？"),
            (CONT, "Taiguanglin："),
            (IND,  "这个就不好说了。"),
        ]
        ch = parser.parse_lines(lines, start_index=16)[0]
        assert "2025年11月10日 微信公众号" in ch.content
        # opening is only the 师父说 intro
        before_q = ch.content.split('<div class="question"', 1)[0]
        assert "肌肉紧绷" not in before_q
        assert "静修期间" not in before_q
        assert "回答微信公众号的问题" in before_q
        # clock-stamp commenters become real cards
        assert '<span class="questioner">亻田</span>' in ch.content
        assert '<span class="question-time">10:38:28</span>' in ch.content
        assert '<span class="questioner">素山Celine</span>' in ch.content
        assert '<span class="question-time">10:42:42</span>' in ch.content
        assert '<span class="questioner">淡薄</span>' in ch.content
        # 1、 before answer + 2、 after answer → two cards, both 淡薄
        names = re.findall(r'<span class="questioner">([^<]+)</span>', ch.content)
        assert names == ["亻田", "素山Celine", "淡薄", "淡薄"]
        assert len(re.findall(r'<div class="question"', ch.content)) == 4


# ---------------------------------------------------------------------------
# questioners without a timestamp
# ---------------------------------------------------------------------------

class TestNoTimeQuestioners:
    """Many tieba/weixin comments carry only a name (no time). They are always
    introduced either by a separator line above, or by the 师父说 source-switch
    paragraph that opens a section."""

    def test_questioner_after_separator_without_time(self, parser):
        lines = [
            (157.0, "Tai 师父2025 年6 月9 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年6 月9 号，先回答贴吧的问题。"),
            (CONT, "甲：2025-06-09 08:00"),
            (IND,  "第一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "第一个回答。"),
            (CONT, "———————————————————————————"),
            (CONT, "无明萤火："),
            (IND,  "感恩师父，请问第二个问题？"),
            (CONT, "Taiguanglin："),
            (IND,  "第二个回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        # the no-time commenter is a real question card, not a stray paragraph
        assert '<span class="questioner">无明萤火</span>' in ch.content
        assert "感恩师父，请问第二个问题？" in ch.content
        # name must not leak into a paragraph and there is no empty time span
        assert "<p>无明萤火" not in ch.content
        # the question-text directly follows the (empty) meta -> no time span text
        assert "question-time" not in ch.content.split('无明萤火')[1].split('question-text')[0]
        assert len(re.findall(r'<div class="question"', ch.content)) == 2

    def test_section_start_questioner_without_time(self, parser):
        """First weixin commenter right after the 师父说 switch lacks a time."""
        lines = [
            (157.0, "Tai 师父2025 年6 月9 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年6 月9 号，回答微信公众号的问题。"),
            (CONT, "诚杨："),
            (IND,  "师父吉祥，请开示一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "这是回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        assert '<span class="questioner">诚杨</span>' in ch.content
        assert "师父吉祥，请开示一个问题。" in ch.content
        assert len(re.findall(r'<div class="question"', ch.content)) == 1

    def test_no_time_questioner_with_numbered_followups(self, parser):
        """无明萤火 pattern: greeting + 1、 share one card; 2、 opens another,
        both attributed to the same no-time questioner (the 无明萤火 case)."""
        lines = [
            (157.0, "Tai 师父2025 年7 月12 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年7 月12 号，先回答贴吧的问题。"),
            (CONT, "甲：2025-07-12 08:00"),
            (IND,  "前一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "前一个回答。"),
            (CONT, "———————————————————————————"),
            (CONT, "无明萤火："),
            (IND,  "感恩师父"),
            (IND,  "1、第一个泰国佛牌问题？"),
            (CONT, "Taiguanglin："),
            (IND,  "无名萤火，这是第一个回答。"),
            (IND,  "2、第二个佛牌问题？"),
            (CONT, "Taiguanglin："),
            (IND,  "这是第二个回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        cards = re.findall(r'<span class="questioner">([^<]+)</span>', ch.content)
        # 甲 + two 无明萤火 cards
        assert cards == ["甲", "无明萤火", "无明萤火"]
        first = ch.content.split('无明萤火', 1)[1]
        assert "感恩师父" in first
        assert "1、第一个泰国佛牌问题？" in first

    def test_wrapped_name_with_time_rejoined(self, parser):
        """A long name pushed onto the separator line ('———白瀑') with the rest
        ('印龙：time') on the next line must rejoin into one questioner."""
        lines = [
            (157.0, "Tai 师父2025 年8 月5 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年8 月5 号，先回答贴吧的问题。"),
            (CONT, "甲：2025-08-05 08:00"),
            (IND,  "前一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "前一个回答。"),
            (CONT, "———————————————————————————白瀑"),
            (CONT, "印龙：2025-08-05 10:34"),
            (IND,  "Tai 师好，平安吉祥。"),
            (CONT, "Taiguanglin："),
            (IND,  "白瀑印龙，这是回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        assert '<span class="questioner">白瀑印龙</span>' in ch.content
        assert '<span class="question-time">2025-08-05 10:34</span>' in ch.content
        # neither half leaks as its own questioner / paragraph
        assert '<span class="questioner">白瀑</span>' not in ch.content
        assert '<span class="questioner">印龙</span>' not in ch.content
        assert "<p>白瀑" not in ch.content

    def test_wrapped_name_without_time_rejoined(self, parser):
        """'———西瓜' + '柿：' (no time) rejoins into questioner 西瓜柿."""
        lines = [
            (157.0, "Tai 师父2025 年8 月7 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年8 月7 号，先回答贴吧的问题。"),
            (CONT, "甲：2025-08-07 08:00"),
            (IND,  "前一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "前一个回答。"),
            (CONT, "——————————————————————————— 西瓜"),
            (CONT, "柿："),
            (IND,  "顶礼师父，请问一个问题？"),
            (CONT, "Taiguanglin："),
            (IND,  "西瓜柿，这是回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        assert '<span class="questioner">西瓜柿</span>' in ch.content
        assert '<span class="questioner">西瓜</span>' not in ch.content
        assert '<span class="questioner">柿</span>' not in ch.content

    def test_standalone_short_name_questioner_unaffected(self, parser):
        """A genuine short name ('西瓜：') on its own line stays its own
        questioner and is NOT merged with the wrapped-name logic."""
        lines = [
            (157.0, "Tai 师父2025 年8 月7 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年8 月7 号，先回答贴吧的问题。"),
            (CONT, "甲：2025-08-07 08:00"),
            (IND,  "前一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "前一个回答。"),
            (CONT, "———————————————————————————"),
            (CONT, "西瓜："),
            (IND,  "师父，请问一个问题？"),
            (CONT, "Taiguanglin："),
            (IND,  "西瓜，这是回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        assert '<span class="questioner">西瓜</span>' in ch.content

    def test_split_name_and_colon_rejoined(self, parser):
        """A short name is justified so its colon lands on its own line
        ('M' then '：'); they must rejoin into questioner 'M'."""
        lines = [
            (157.0, "Tai 师父2025 年7 月9 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年7 月9 号，回答微信公众号的问题。"),
            (CONT, "M"),
            (117.1, "："),
            (IND,  "顶礼师父，打坐坐不住，怎么办？"),
            (CONT, "Taiguanglin："),
            (IND,  "M，就是坚持的问题。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        assert '<span class="questioner">M</span>' in ch.content
        assert "<p>M</p>" not in ch.content
        assert "<p>：</p>" not in ch.content
        assert "顶礼师父，打坐坐不住，怎么办？" in ch.content

    def test_split_name_and_colon_after_separator(self, parser):
        """Same split but introduced by a separator ('奔跑吧兄弟' + '：')."""
        lines = [
            (157.0, "Tai 师父2025 年9 月6 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年9 月6 号，先回答贴吧的问题。"),
            (CONT, "甲：2025-09-06 08:00"),
            (IND,  "前一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "前一个回答。"),
            (CONT, "———————————————————————————"),
            (CONT, "奔跑吧兄弟"),
            (174.0, "："),
            (IND,  "师父，三魂七魄能够分散到各处吗？"),
            (CONT, "Taiguanglin："),
            (IND,  "奔跑吧兄弟，我们不讲三魂七魄。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        assert '<span class="questioner">奔跑吧兄弟</span>' in ch.content
        assert "<p>奔跑吧兄弟</p>" not in ch.content

    def test_lone_colon_without_name_becomes_question(self, parser):
        """When the name is lost entirely (separator + bare '：' + body), the
        body must still be a question card, not a stray '<p>：</p>'."""
        lines = [
            (157.0, "Tai 师父2025 年6 月10 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年6 月10 号，先回答贴吧的问题。"),
            (CONT, "甲：2025-06-10 08:00"),
            (IND,  "前一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "前一个回答。"),
            (CONT, "———————————————————————————"),
            (CONT, "："),
            (IND,  "师父吉祥，修到什么程度可以知晓前世？"),
            (CONT, "Taiguanglin："),
            (IND,  "这是回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        assert "<p>：</p>" not in ch.content
        assert "师父吉祥，修到什么程度可以知晓前世？" in ch.content
        # the body sits in a question card (with empty questioner meta)
        assert '<div class="question-text">师父吉祥，修到什么程度可以知晓前世？</div>' in ch.content

    def test_indented_in_question_divider_does_not_split_card(self, parser):
        """A user-drawn divider INSIDE a question is indented (x0>=104) and is
        NOT followed by a questioner -> dropped, content stays in the card."""
        lines = [
            (157.0, "Tai 师父2025 年9 月6 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年9 月6 号，先回答贴吧的问题。"),
            (CONT, "极乐是我家：2025-09-06 18:05"),
            (IND,  "感恩师父，有个家庭困扰很久的问题请教："),
            (IND,  "———————————"),   # indented divider drawn by the user
            (IND,  "我目前全职在家修行，家先生脾气暴躁。"),
            (IND,  "以上是家里基本情况。"),
            (CONT, "Taiguanglin："),
            (IND,  "这是回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        # the post-divider text must stay inside the question, not leak as <p>
        assert "<p>我目前全职在家修行，家先生脾气暴躁。</p>" not in ch.content
        assert '<div class="question-text">我目前全职在家修行，家先生脾气暴躁。</div>' in ch.content
        assert "———" not in ch.content   # the divider is dropped
        assert len(re.findall(r'<div class="question"', ch.content)) == 1

    def test_indented_separator_before_questioner_still_splits(self, parser):
        """An indented separator that IS followed by a questioner stays a real
        boundary (the rare 随息居Lomi case)."""
        lines = [
            (157.0, "Tai 师父2025 年6 月13 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年6 月13 号，回答微信公众号的问题。"),
            (CONT, "甲：2025-06-13 08:00"),
            (IND,  "第一个问题。"),
            (CONT, "Taiguanglin："),
            (IND,  "第一个回答。"),
            (IND,  "———————————"),     # indented, but a questioner follows
            (CONT, "随息居Lomi："),
            (IND,  "第二个问题？"),
            (CONT, "Taiguanglin："),
            (IND,  "第二个回答。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        assert '<span class="questioner">随息居Lomi</span>' in ch.content
        assert len(re.findall(r'<div class="question"', ch.content)) == 2

    def test_colon_ending_continuation_is_not_a_questioner(self, parser):
        """A sentence wrapped onto a left-margin line that ends with '：' inside
        an open question must stay question text, not become a fake questioner."""
        lines = [
            (157.0, "Tai 师父2025 年6 月9 日答疑（文字版）"),
            (IND,  "师父说：今天是2025 年6 月9 号，先回答贴吧的问题。"),
            (CONT, "甲：2025-06-09 08:00"),
            (IND,  "Tai 师好，末学今天想请教以下三个"),
            (CONT, "问题："),
            (IND,  "1、问题一？"),
            (CONT, "Taiguanglin："),
            (IND,  "答一。"),
        ]
        ch = parser.parse_lines(lines, start_index=12)[0]
        names = re.findall(r'<span class="questioner">([^<]+)</span>', ch.content)
        assert names == ["甲"]               # no questioner named "问题"
        assert "想请教以下三个问题：" in ch.content   # reflowed into question text


# ---------------------------------------------------------------------------
# empty / edge
# ---------------------------------------------------------------------------

class TestEdge:
    def test_empty_input_returns_no_chapters(self, parser):
        assert parser.parse_lines([], start_index=12) == []


# ---------------------------------------------------------------------------
# PyMuPDF import resilience（避免冒牌 fitz 套件造成的命名衝突）
# ---------------------------------------------------------------------------

class TestImportPyMuPDF:
    def _clear(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "pymupdf", raising=False)
        monkeypatch.delitem(sys.modules, "fitz", raising=False)

    def test_prefers_pymupdf_module_name(self, monkeypatch):
        self._clear(monkeypatch)
        fake = types.ModuleType("pymupdf")
        fake.open = lambda *a, **k: None
        monkeypatch.setitem(sys.modules, "pymupdf", fake)
        assert _import_pymupdf() is fake

    def test_falls_back_to_fitz_when_no_pymupdf(self, monkeypatch):
        self._clear(monkeypatch)
        # 確保 import pymupdf 失敗
        monkeypatch.setitem(sys.modules, "pymupdf", None)
        fake = types.ModuleType("fitz")
        fake.open = lambda *a, **k: None
        monkeypatch.setitem(sys.modules, "fitz", fake)
        assert _import_pymupdf() is fake

    def test_rejects_bogus_fitz_without_open(self, monkeypatch):
        self._clear(monkeypatch)
        monkeypatch.setitem(sys.modules, "pymupdf", None)
        bogus = types.ModuleType("fitz")  # 沒有 open()，模擬冒牌套件
        monkeypatch.setitem(sys.modules, "fitz", bogus)
        with pytest.raises(ImportError, match="PyMuPDF"):
            _import_pymupdf()
