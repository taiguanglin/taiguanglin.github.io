"""答疑日期格式與排序的回歸測試（stage 2／stage 3）。

本檔鎖住：
* 顯示日期統一為 ``YYYY-MM-DD [HH:MM[:SS]]``；
* PDF 只有時刻時，依所屬小節日期補齊；
* 每個小節由新到舊排序，無法解析日期者最後；
* 發布版 12 章每個小節都符合上述規則；
* 13–21 章必須是 stage 3 跳轉頁（防止只跑 stage 1 就發布）。
"""

import json
import re
from pathlib import Path

import pytest
from lxml import html as lhtml

import extract as stage2_extract
import gen_classified as gc


_ISO_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}(?::\d{2})?)?$"
)


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
        assert gc.parse_time_parts("24-02-2024 19:34") == (
            2024, 2, 24, 19, 34, 0, True, False)

    def test_month_first(self):
        assert gc.parse_time_parts("02-24-2024 19:34") == (
            2024, 2, 24, 19, 34, 0, True, False)

    def test_ambiguous_uses_source_convention(self):
        """兩組都 ≤12 時，依已核對的 Word／Excel 來源慣例當日先月後。"""
        assert gc.parse_time_parts("05-03-2025") == (2025, 3, 5, 0, 0, 0, False, False)

    def test_time_only_is_not_a_date(self):
        assert gc.parse_time_parts("09:39:18") is None

    def test_garbage_is_not_a_date(self):
        assert gc.parse_time_parts("無日期") is None

    def test_calendar_invalid_date_is_rejected(self):
        assert gc.parse_time_parts("2025-02-30") is None
        assert gc.parse_time_parts("2025-13-01") is None


class TestNormalizeTimeStr:

    def test_pads_month_and_day(self):
        assert gc.normalize_time_str("2025-11-7 11:42") == "2025-11-07 11:42"

    def test_reorders_day_first(self):
        assert gc.normalize_time_str("18-06-2024") == "2024-06-18"

    def test_keeps_seconds(self):
        assert gc.normalize_time_str("2025-12-09 09:39:18") == "2025-12-09 09:39:18"

    def test_keeps_midnight(self):
        assert gc.normalize_time_str("2025-01-01 00:00") == "2025-01-01 00:00"

    def test_time_only_untouched(self):
        assert gc.normalize_time_str("09:39:18") == "09:39:18"


class TestCompleteTimeFromSection:

    def test_completes_pdf_time_only_from_session_date(self):
        assert stage2_extract.complete_time_from_section(
            "10:38:28", "2025年11月10日 微信公众号(42)"
        ) == "2025-11-10 10:38:28"

    def test_keeps_complete_date(self):
        assert stage2_extract.complete_time_from_section(
            "2025-11-10 10:38:28", "2025年11月10日 微信公众号(42)"
        ) == "2025-11-10 10:38:28"

    def test_does_not_guess_without_section_date(self):
        assert stage2_extract.complete_time_from_section(
            "10:38:28", "微信公众号"
        ) == "10:38:28"


class TestExtractTimeKey:
    """排序 key 採新到舊；Python 的遞增排序即得正確輸出。"""

    def test_later_date_has_smaller_key(self):
        earlier = gc.extract_time_key('<span class="question-time">2024-09-09</span>')
        later = gc.extract_time_key('<span class="question-time">2025-12-09 09:39:18</span>')
        assert later < earlier

    def test_seconds_are_part_of_the_key(self):
        a = gc.extract_time_key('<span class="question-time">2025-12-09 09:00:00</span>')
        b = gc.extract_time_key('<span class="question-time">2025-12-09 09:00:01</span>')
        assert b < a

    def test_unparsable_sorts_last(self):
        unknown = gc.extract_time_key('<span class="question-time">09:39:18</span>')
        known = gc.extract_time_key('<span class="question-time">2024-09-09</span>')
        assert unknown > known

    def test_missing_span_sorts_last(self):
        assert gc.extract_time_key("<div class='question'>x</div>") > gc.extract_time_key(
            '<span class="question-time">2024-09-09</span>')


class TestPrepareQuestionHtml:

    def test_infers_missing_date(self):
        qid = "question-3e36e90ed714"
        html = _question_html(qid, "")
        out = gc._prepare_question_html(html)
        assert "2024-02-23" in out

    def test_keeps_existing_date(self):
        html = _question_html("question-plain", "2024-09-09")
        out = gc._prepare_question_html(html)
        assert "2024-09-09" in out
        assert "2025-12-09" not in out


class TestBuildMergedChapterOrdering:
    """端到端：小節內的 Word／PDF 條目依最終顯示日期由新到舊。"""

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

    def test_inferred_date_does_not_jump_to_back(self):
        blocks = [
            '<h3 id="test-sec">測試小節</h3>',
            _question_html("question-36f022d174a3", "", text="新"),
            _answer_html("新答"),
            _question_html("question-plain", "2024-09-09", text="舊"),
            _answer_html("舊答"),
        ]
        out, _toc = gc.build_merged_chapter(1, blocks, [], [])
        assert self._ids(out) == ["question-36f022d174a3", "question-plain"]

    def test_pdf_item_merges_by_date(self):
        blocks = [
            '<h3 id="test-sec">測試小節</h3>',
            _question_html("question-plain", "2024-09-09", text="舊"),
            _answer_html("舊答"),
        ]
        pdf_items = [{
            "path": "01-01-01",
            "q_html": _question_html("question-pdf", "2025-03-03", text="新"),
            "a_html": _answer_html("新答"),
        }]
        out, _toc = gc.build_merged_chapter(1, blocks, [], pdf_items)
        assert self._ids(out) == ["question-pdf", "question-plain"]


class TestPublishedEbookOrdering:

    @staticmethod
    def _sections(chapter_path: Path):
        """回傳 [(小節標題, [(qid, 日期字串), …])]。"""
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
                times.append((qs[0].get("id", ""), ts[0].strip() if ts else ""))
        if times:
            out.append((current, times))
        return out

    def test_all_sections_are_date_ordered(self, ebook_dir):
        chapters = [
            ebook_dir / f"{ch:02d}.html" for ch in range(1, 13)
        ]
        if not all(path.exists() for path in chapters):
            pytest.skip("發布版電子書未建置（wenda2_ebook/ 不存在）")

        problems = []
        for path in chapters:
            for title, entries in self._sections(path):
                keys = []
                for qid, raw in entries:
                    if not _ISO_DATE_RE.fullmatch(raw):
                        problems.append(
                            f"{path.name} [{title}] {qid} 日期未統一：{raw!r}")
                        keys = []
                        break
                    parts = gc.parse_time_parts(raw)
                    if parts is None:
                        problems.append(
                            f"{path.name} [{title}] {qid} 日期無法解析：{raw!r}")
                        keys = []
                        break
                    keys.append(parts[:6])
                for prev, cur in zip(keys, keys[1:]):
                    if cur > prev:
                        problems.append(
                            f"{path.name} [{title}] 日期逆序：{prev} → {cur}")

        assert not problems, "發布版小節內日期未由新到舊或格式未統一：\n" + "\n".join(problems)

    def test_pet_section_exists_and_is_ordered(self, ebook_dir):
        """指定的「養寵物/喂流浪動物」小節必須存在，且全段由新到舊。"""
        path = ebook_dir / "12.html"
        if not path.exists():
            pytest.skip("發布版電子書未建置（wenda2_ebook/ 不存在）")
        matches = [
            (title, entries) for title, entries in self._sections(path)
            if "养宠物" in title or "養寵物" in title
        ]
        assert len(matches) == 1, f"應恰有一個養寵物小節，實際 {len(matches)}"
        title, entries = matches[0]
        parsed = [gc.parse_time_parts(raw) for _qid, raw in entries]
        assert all(part is not None for part in parsed)
        keys = [part[:6] for part in parsed]
        assert keys == sorted(keys, reverse=True), f"[{title}] 未由新到舊"

    def test_redirect_chapters_are_classified_output(self, ebook_dir):
        """13–21 必須是 stage 3 跳轉頁，不能是 stage 1 的月度底稿。"""
        for ch in range(13, 22):
            for suffix in (".html", "_trad.html"):
                path = ebook_dir / f"{ch:02d}{suffix}"
                if not path.exists():
                    pytest.skip("發布版電子書未建置（wenda2_ebook/ 不存在）")
                text = path.read_text(encoding="utf-8")
                assert "此章節已重新分類" in text, f"{path.name} 不是 stage 3 跳轉頁"
                assert 'class="question"' not in text, f"{path.name} 仍含月度底稿問答"

    def test_pdf_classified_entries_are_present(self, ebook_dir, repo_root):
        """抽查版控分類結果中的 qid，確保成品不是只含 Word 的半套版本。"""
        classified_dir = repo_root / "tool" / "qa_split_ebook" / "classified"
        sample_qids = []
        for path in sorted(classified_dir.glob("batch_*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                if not row.get("split"):
                    sample_qids.append(row.get("qid", ""))
                if len(sample_qids) >= 50:
                    break
            if len(sample_qids) >= 50:
                break
        assert sample_qids

        published = ""
        for ch in range(1, 13):
            published += (ebook_dir / f"{ch:02d}.html").read_text(encoding="utf-8")
        missing = [qid for qid in sample_qids if f'id="{qid}"' not in published]
        assert not missing, f"PDF 分類條目未進入成品：{missing[:10]}"
