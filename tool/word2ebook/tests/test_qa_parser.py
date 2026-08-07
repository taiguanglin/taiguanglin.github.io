"""Tests for core/qa_parser.py.

These exercise the pure parsing core (``parse_text`` / ``build_section`` /
``_sections_to_chapters``) with inline txt fixtures, so no real files are
needed. ``parse_folder`` (the only filesystem-touching method) is covered with
a small tmp_path fixture.
"""

import re
from urllib.parse import quote

import pytest

from core.qa_parser import QAParser, _timecode_to_seconds, _year_to_cn
from config.settings import DEFAULT_SETTINGS


# ---------------------------------------------------------------------------
# Inline fixtures (mirror the real qa/*.txt layout)
# ---------------------------------------------------------------------------

# 兩段：第 1 段未校稿（無「最後編輯」），第 2 段已人工校稿（有「最後編輯」）。
SAMPLE_TXT = """2025年11月10日 Tai師父官網答疑整理稿
（時間已依 SRT 字幕逐題校對；邊界以字幕 cue 為準，仍請以錄音為最終依據。）
開場時間：00:00:01.730 - 00:01:47.210
今天是十一月十號，週一。先回答官方網站的問題。


### 1. 未斷淫慾為何不可入初禪？
時間：00:01:47.210 - 00:06:42.680
Taiguanglin：
網上說初禪有什麼喜樂支、各種感覺。

那麼你想，淫慾屬於哪一個？

### 2. 母親病重，想助念回向往生極樂，她能不能去？
時間：00:06:42.680 - 00:08:00.000
最後播放：2026-06-16 15:12
最後編輯：2026-06-16 15:16
Taiguanglin：
首先是她自己想去，這個最重要。
"""


@pytest.fixture
def parser() -> QAParser:
    return QAParser(DEFAULT_SETTINGS)


# ---------------------------------------------------------------------------
# Timecode helper
# ---------------------------------------------------------------------------

class TestTimecodeToSeconds:
    def test_basic(self):
        assert _timecode_to_seconds("00:00:09.190") == pytest.approx(9.19)

    def test_minutes_and_hours(self):
        assert _timecode_to_seconds("01:02:03.500") == pytest.approx(3723.5)

    def test_comma_decimal(self):
        assert _timecode_to_seconds("00:00:23,648") == pytest.approx(23.648)

    def test_invalid_returns_none(self):
        assert _timecode_to_seconds("garbage") is None
        assert _timecode_to_seconds("") is None


class TestYearToCn:
    def test_year(self):
        assert _year_to_cn(2025) == "二〇二五"
        assert _year_to_cn(2026) == "二〇二六"


# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------

class TestParseFilename:
    def test_official_site(self, parser):
        assert parser._parse_filename("2025年11月10日Tai師父官網答疑.txt") == (
            2025, 11, 10, "官網"
        )

    def test_wechat(self, parser):
        assert parser._parse_filename("2026年3月4日Tai師父微信公眾號答疑.txt") == (
            2026, 3, 4, "微信公眾號"
        )

    def test_non_matching_returns_none(self, parser):
        assert parser._parse_filename("README.md") is None
        assert parser._parse_filename("random.txt") is None


# ---------------------------------------------------------------------------
# parse_text
# ---------------------------------------------------------------------------

class TestParseText:
    def test_opening_extracted(self, parser):
        parsed = parser.parse_text(SAMPLE_TXT)
        assert parsed["opening"]["range"] is not None
        start, end, label = parsed["opening"]["range"]
        assert start == pytest.approx(1.73)
        assert end == pytest.approx(107.21)
        assert parsed["opening"]["paras"] == ["今天是十一月十號，週一。先回答官方網站的問題。"]

    def test_editorial_note_dropped_from_opening(self, parser):
        parsed = parser.parse_text(SAMPLE_TXT)
        # 編者按（以「（」開頭）不應出現在開場白
        assert all("時間已依" not in p for p in parsed["opening"]["paras"])

    def test_title_dropped_from_opening(self, parser):
        parsed = parser.parse_text(SAMPLE_TXT)
        assert all("整理稿" not in p for p in parsed["opening"]["paras"])

    def test_two_segments(self, parser):
        parsed = parser.parse_text(SAMPLE_TXT)
        assert len(parsed["segments"]) == 2

    def test_segment_numbers_and_questions(self, parser):
        segs = parser.parse_text(SAMPLE_TXT)["segments"]
        assert segs[0]["number"] == "1"
        assert segs[0]["question"] == ["未斷淫慾為何不可入初禪？"]
        assert segs[1]["number"] == "2"

    def test_answer_paragraphs_split_on_blank_lines(self, parser):
        segs = parser.parse_text(SAMPLE_TXT)["segments"]
        # 第 1 段回答有兩個段落（中間一個空行）
        assert len(segs[0]["answer"]) == 2
        assert segs[0]["answer"][0].startswith("網上說初禪")
        assert segs[0]["answer"][1].startswith("那麼你想")

    def test_segment_time_range(self, parser):
        segs = parser.parse_text(SAMPLE_TXT)["segments"]
        start, end, label = segs[0]["range"]
        assert start == pytest.approx(107.21)
        assert end == pytest.approx(402.68)
        assert label == "00:01:47.210 - 00:06:42.680"

    def test_proofread_detection(self, parser):
        segs = parser.parse_text(SAMPLE_TXT)["segments"]
        assert segs[0]["edited"] == ""               # 未校稿
        assert segs[1]["edited"] == "2026-06-16 15:16"  # 已校稿

    def test_played_line_not_in_answer(self, parser):
        segs = parser.parse_text(SAMPLE_TXT)["segments"]
        # 「最後播放」不應跑進回答內文
        assert all("最後播放" not in a for a in segs[1]["answer"])
        assert segs[1]["answer"] == ["首先是她自己想去，這個最重要。"]


# ---------------------------------------------------------------------------
# build_section → HTML blocks
# ---------------------------------------------------------------------------

class TestBuildSection:
    def _section(self, parser):
        audio = "../audio/" + quote("2025年11月10日Tai師父官網答疑.opus")
        return parser.build_section(SAMPLE_TXT, 2025, 11, 10, "官網", audio), audio

    def test_h2_heading(self, parser):
        section, _ = self._section(parser)
        assert section["h2_text"] == "2025年11月10日 官網"
        assert section["blocks"][0].startswith('<h2 id="')

    def test_opening_block_has_play_button(self, parser):
        section, _ = self._section(parser)
        joined = "\n".join(section["blocks"])
        assert 'qa-meta-bar--opening' in joined
        assert '<p class="qa-opening">' in joined

    def test_proofread_placeholder_used(self, parser):
        section, _ = self._section(parser)
        joined = "\n".join(section["blocks"])
        assert "{{qa_proofread}} 2026-06-16 15:16" in joined
        assert "{{qa_unproofread}}" in joined

    def test_audio_data_attributes(self, parser):
        section, audio = self._section(parser)
        joined = "\n".join(section["blocks"])
        # 音檔以 percent-encode 寫入（CJK → %XX，OpenCC 不會破壞）
        assert f'data-audio="{audio}"' in joined
        assert "%E5%B9%B4" in audio  # 「年」字的 percent-encoding
        assert 'data-start="107.210"' in joined
        assert 'data-end="402.680"' in joined
        assert 'data-label="00:01:47 - 00:06:42"' in joined

    def test_question_and_answer_divs_have_ids(self, parser):
        section, _ = self._section(parser)
        joined = "\n".join(section["blocks"])
        assert re.search(r'<div class="question" id="question-[0-9a-f]+">', joined)
        assert re.search(r'<div class="answer" id="answer-[0-9a-f]+">', joined)

    def test_meta_bar_outside_question_answer(self, parser):
        """播放鈕與徽章須在 qa-meta-bar（非 question/answer/p），避免污染搜尋索引。"""
        section, _ = self._section(parser)
        for block in section["blocks"]:
            if "qa-play" in block or "qa-status" in block:
                assert block.startswith('<div class="qa-meta-bar')

    def test_empty_text_returns_none(self, parser):
        assert parser.build_section("", 2025, 11, 10, "官網", "../audio/x.opus") is None


# ---------------------------------------------------------------------------
# _sections_to_chapters – multi-year month grouping
# ---------------------------------------------------------------------------

class TestSectionsToChapters:
    def _make_sections(self, parser):
        sections = []
        for (y, m, d, src) in [
            (2025, 11, 10, "官網"),
            (2025, 11, 10, "微信公眾號"),
            (2025, 12, 8, "官網"),
            (2026, 1, 5, "官網"),
        ]:
            audio = "../audio/x.opus"
            sections.append(
                parser.build_section(SAMPLE_TXT, y, m, d, src, audio)
            )
        return sections

    def test_groups_by_year_month(self, parser):
        chapters = parser._sections_to_chapters(self._make_sections(parser), start_index=16)
        # 三個月份 → 三章（17, 18, 19）
        assert [c.filename for c in chapters] == ["17.html", "18.html", "19.html"]

    def test_titles_chronological(self, parser):
        chapters = parser._sections_to_chapters(self._make_sections(parser), start_index=16)
        assert chapters[0].title == "17二〇二五年十一月"
        assert chapters[1].title == "18二〇二五年十二月"
        assert chapters[2].title == "19二〇二六年一月"

    def test_is_qa_flag_set(self, parser):
        chapters = parser._sections_to_chapters(self._make_sections(parser), start_index=16)
        assert all(c.is_qa for c in chapters)

    def test_source_order_official_before_wechat(self, parser):
        chapters = parser._sections_to_chapters(self._make_sections(parser), start_index=16)
        nov = chapters[0]
        anchors = [item.text for item in nov.toc_items]
        # 同一天官網在微信公眾號之前
        assert anchors.index("2025年11月10日 官網") < anchors.index("2025年11月10日 微信公眾號")

    def test_start_index_offsets_numbering(self, parser):
        chapters = parser._sections_to_chapters(self._make_sections(parser), start_index=20)
        assert chapters[0].filename == "21.html"

    def test_empty_returns_empty(self, parser):
        assert parser._sections_to_chapters([], start_index=16) == []


# ---------------------------------------------------------------------------
# parse_folder – filesystem integration
# ---------------------------------------------------------------------------

class TestParseFolder:
    def test_parses_real_layout(self, parser, tmp_path):
        (tmp_path / "2025年11月10日Tai師父官網答疑.txt").write_text(
            SAMPLE_TXT, encoding="utf-8"
        )
        (tmp_path / "2025年11月10日Tai師父微信公眾號答疑.txt").write_text(
            SAMPLE_TXT, encoding="utf-8"
        )
        # 非答疑檔應略過
        (tmp_path / "README.md").write_text("ignore me", encoding="utf-8")
        (tmp_path / "_draft.txt").write_text(SAMPLE_TXT, encoding="utf-8")

        chapters = parser.parse_folder(tmp_path, start_index=16)
        assert len(chapters) == 1
        assert chapters[0].filename == "17.html"
        assert chapters[0].is_qa is True
        # 兩個來源 → 兩個 h2 區段
        assert len(chapters[0].toc_items) == 2

    def test_audio_filename_from_stem(self, parser, tmp_path):
        (tmp_path / "2025年11月10日Tai師父官網答疑.txt").write_text(
            SAMPLE_TXT, encoding="utf-8"
        )
        chapters = parser.parse_folder(tmp_path, start_index=16)
        expected = "../audio/" + quote("2025年11月10日Tai師父官網答疑.opus")
        assert f'data-audio="{expected}"' in chapters[0].content

    def test_empty_folder_returns_empty(self, parser, tmp_path):
        assert parser.parse_folder(tmp_path, start_index=16) == []
