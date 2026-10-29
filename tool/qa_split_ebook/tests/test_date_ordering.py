"""答疑日期排序的回歸測試（stage 3：gen_classified）。

背景（2026-11）：
發布版 ``wenda2_ebook/01.html`` 的「修行翻出情緒/習氣」小節，答疑並沒有
由上往下依日期排列——首則是 2025-12-09，後面卻接 2024-09-09。

根因有兩個，都在 stage 3 的排序步驟：

1. **推斷日期在排序「之後」才補上**：``infer_missing_date()`` 原本寫在
   排序迴圈裡面；被補日期的條目在排序當下只有 ``HH:MM:SS``（沒有日期），
   于是被視為「無時間」而排到最前面。
2. **時間解析不認秒**：``extract_time_key()`` 只接受 ``YYYY-M-D [HH:MM]``，
   微信後端時間戳的 ``HH:MM:SS`` 整串落空 → 同樣被當成「無時間」。

本檔鎖住：
* 時間字串解析／正規化（含秒、DD-MM-YYYY、MM-DD-YYYY）；
* 排序 key 的先後關係（無法解析者排最後）；
* 推斷日期必須在排序前補上（build_merged_chapter 的端到端排序）；
* 產物層守門：發布版 12 章每個小節的答疑日期必須由早到晚。
"""

import re
from pathlib import Path

import pytest
from lxml import html as lhtml

import gen_classified as gc


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _question_html(qid: str, time: str, who: str = "某某", text: str = "問") -> str:
    return (
        f'<div class="question" id="{qid}">\n'
        f'<div class="question-meta">\n'
        f'<span class="questioner">{who}</span>\n'
        f'<span class="question-time">{time}</span>\n'
        f'</div>\n'
        f'<div class="question-text">{text}</div>\n'
        f'</div>'
    )


def _answer_html(text: str = "答") -> str:
    return (
        '<div class="answer" id="answer-x">\n'
        '<div class="answer-meta">\n<span class="answerer">Taiguanglin</span>\n</div>\n'
        f'<div class="answer-text">{text}</div>\n'
        '</div>'
    )


# --------------------------------------------------------------------------- #
# 單元：時間解析
# --------------------------------------------------------------------------- #

class TestParseTimeParts:

    def test_iso_date(self):
        assert gc.parse_time_parts("2024-09-09") == (2024, 9, 9, 0, 0, 0, False, False)

    def test_iso_date_with_minutes(self):
        assert gc.parse_time_parts("2025-05-17 20:39") == (
            2025, 5, 17, 20, 39, 0, True, False)

    def test_iso_date_with_seconds(self):
        assert gc.parse_time_parts("2025-12-09 09:39:18") == (
            2025, 12, 9, 9, 39, 18, True, True)

    def test_slash_and_single_digit(self):
        assert gc.parse_time_parts("2025/11/7 11:42") == (
            2025, 11, 7, 11, 42, 0, True, False)

    def test_day_first(self):
        """首組 >12 → 日先月後。"""
        assert gc.parse_time_parts("24-02-2024 19:34") == (
            2024, 2, 24, 19, 34, 0, True, False)

    def test_month_first(self):
        """次組 >12 → 月先日後。"""
        assert gc.parse_time_parts("02-24-2024 19:34") == (
            2024, 2, 24, 19, 34, 0, True, False)

    def test_ambiguous_uses_source_convention(self):
        """兩組都 ≤12 → 依 Word 源檔慣例當日先月後。"""
        assert gc.parse_time_parts("05-03-2025") == (2025, 3, 5, 0, 0, 0, False, False)

    def test_time_only_is_not_a_date(self):
        assert gc.parse_time_parts("09:39:18") is None

    def test_garbage_is_not_a_date(self):
        assert gc.parse_time_parts("無日期") is None


class TestNormalizeTimeStr:

    def test_pads_month_and_day(self):
        assert gc.normalize_time_str("2025-11-7 11:42") == "2025-11-07 11:42"

    def test_keeps_seconds(self):
        assert gc.normalize_time_str("2025-12-09 09:39:18") == "2025-12-09 09:39:18"

    def test_keeps_midnight(self):
        assert gc.normalize_time_str("2025-01-01 00:00") == "2025-01-01 00:00"

    def test_time_only_untouched(self):
        assert gc.normalize_time_str("09:39:18") == "09:39:18"


class TestExtractTimeKey:

    def test_seconds_are_part_of_the_key(self):
        a = gc.extract_time_key('<span class="question-time">2025-12-09 09:00:00</span>')
        b = gc.extract_time_key('<span class="question-time">2025-12-09 09:00:01</span>')
        assert a < b

    def test_date_beats_time(self):
        early = gc.extract_time_key('<span class="question-time">2024-09-09</span>')
        late = gc.extract_time_key('<span class="question-time">2025-12-09 09:39:18</span>')
        assert early < late

    def test_unparsable_sorts_last(self):
        """沒有日期（或只有 HH:MM:SS）者排最後，不再假裝是最早。"""
        unknown = gc.extract_time_key('<span class="question-time">09:39:18</span>')
        known = gc.extract_time_key('<span class="question-time">2024-09-09</span>')
        assert unknown > known

    def test_missing_span_sorts_last(self):
        assert gc.extract_time_key("<div class='question'>x</div>") > gc.extract_time_key(
            '<span class="question-time">2024-09-09</span>')


# --------------------------------------------------------------------------- #
# 單元：推斷日期必須在排序前補上
# --------------------------------------------------------------------------- #

class TestPrepareQuestionHtml:

    def test_infers_missing_date(self):
        """_INFERRED_DATES 的條目：只給 HH:MM:SS 也要補成完整日期。"""
        qid = "question-50ff9cbb6237"      # → 2025-12-09 09:39:18
        html = _question_html(qid, "09:39:18")
        out = gc._prepare_question_html(html)
        assert "2025-12-09 09:39:18" in out

    def test_keeps_existing_date(self):
        html = _question_html("question-plain", "2024-09-09")
        out = gc._prepare_question_html(html)
        assert "2024-09-09" in out
        assert "2025-12-09" not in out


class TestBuildMergedChapterOrdering:
    """端到端：小節內的 Word／PDF 條目依「最終顯示日期」由早到晚。"""

    @pytest.fixture(autouse=True)
    def _fake_tree(self, monkeypatch):
        monkeypatch.setitem(gc.NAME_TO_PATH, "測試小節", "01-01-01")
        monkeypatch.setitem(gc.PATH_TO_NAME, "01-01-01", "測試小節")
        monkeypatch.setitem(gc.TREE_ORDER, 1, ["01-01-01"])

    def _ids(self, blocks):
        return [
            re.search(r'id="(question-[^"]+)"', b).group(1)
            for b in blocks if 'class="question"' in b
        ]

    def test_inferred_date_does_not_jump_to_front(self):
        """回歸：2025-12-09（推斷）不得排在 2024-09-09 之前。"""
        blocks = [
            '<h3 id="test-sec">測試小節</h3>',
            _question_html("question-50ff9cbb6237", "09:39:18", text="晚"),
            _answer_html("晚答"),
            _question_html("question-plain", "2024-09-09", text="早"),
            _answer_html("早答"),
        ]
        out, _toc = gc.build_merged_chapter(1, blocks, [], [])
        assert self._ids(out) == ["question-plain", "question-50ff9cbb6237"]

    def test_pdf_item_merges_by_date(self):
        """PDF 條目與 Word 條目一起依日期合併排序。"""
        blocks = [
            '<h3 id="test-sec">測試小節</h3>',
            _question_html("question-plain", "2024-09-09", text="早"),
            _answer_html("早答"),
        ]
        pdf_items = [{
            "path": "01-01-01",
            "q_html": _question_html("question-pdf", "2025-03-03", text="中"),
            "a_html": _answer_html("中答"),
        }]
        out, _toc = gc.build_merged_chapter(1, blocks, [], pdf_items)
        assert self._ids(out) == ["question-plain", "question-pdf"]


# --------------------------------------------------------------------------- #
# 產物層守門：發布版 12 章每個小節的日期必須由早到晚
# --------------------------------------------------------------------------- #

class TestPublishedEbookOrdering:

    @staticmethod
    def _sections(chapter_path: Path):
        """回傳 [(小節標題, [日期字串…])]。"""
        doc = lhtml.parse(str(chapter_path)).getroot()
        main = doc.xpath("//main")
        if not main:
            return []
        out = []
        current = "(chapter root)"
        times = []
        for el in main[0]:
            if not isinstance(el.tag, str):
                continue
            if el.tag in ("h2", "h3", "h4"):
                if times:
                    out.append((current, times))
                    times = []
                current = (el.text_content() or "").strip()
                continue
            if el.tag == "article" and "qa-pair" in (el.get("class") or ""):
                qs = el.xpath('./div[@class="question"]')
                if not qs:
                    continue
                ts = qs[0].xpath('.//span[@class="question-time"]/text()')
                times.append(ts[0].strip() if ts else "")
        if times:
            out.append((current, times))
        return out

    def test_all_sections_are_date_ordered(self, ebook_dir):
        chapters = sorted(ebook_dir.glob("[0-9][0-9].html"))
        chapters = [p for p in chapters if 1 <= int(p.stem) <= 12]
        if not chapters:
            pytest.skip("發布版電子書未建置（wenda2_ebook/ 不存在）")

        problems = []
        for path in chapters:
            for title, times in self._sections(path):
                keys = []
                for raw in times:
                    parts = gc.parse_time_parts(raw)
                    if parts is None:
                        problems.append(
                            f"{path.name} [{title}] 日期無法解析：{raw!r}")
                        keys = []
                        break
                    keys.append(parts[:6])
                for prev, cur in zip(keys, keys[1:]):
                    if cur < prev:
                        problems.append(
                            f"{path.name} [{title}] 日期逆序：{prev} → {cur}")

        assert not problems, "發布版小節內日期未由早到晚：\n" + "\n".join(problems)
