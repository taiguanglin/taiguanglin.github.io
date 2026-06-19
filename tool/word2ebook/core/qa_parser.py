"""QA 答疑解析器（qa/ 資料夾 txt 文字稿 → 月份章節）

把 ``qa/`` 資料夾裡「由 AI 轉錄音檔、部分經人工校稿」的 txt 文字稿，解析成
與 :class:`~core.pdf_parser.PDFParser` 形狀一致的、按「月份」分章的 ``Chapter``，
讓它們能無縫接在 Word / PDF 章節之後（例如 2025 年 11 月 → ``17.html``）。

與 PDF 來源相比，QA 章節額外具備兩項特性（``word``/``pdf`` 沒有）：

* **每段可播放對應音檔**：每個答疑段落上方有一條 ``qa-meta-bar``，含一個
  ``.qa-play`` 按鈕（``data-audio`` / ``data-start`` / ``data-end``），由前端
  ``08-qa-audio.js`` 接管，播放時顯示音檔名稱與起訖時間。
* **校稿狀態徽章**：若該段含「最後編輯」時間戳，視為已人工校稿（顯示校稿時間）；
  否則標注為「AI 轉錄、尚未校對」。

設計重點
--------
* **可測試**：唯一碰檔案系統的是 :meth:`parse_folder`；核心 :meth:`parse_text`
  與 :meth:`build_section` 都是純函式，測試可直接餵入字串。
* **i18n 安全**：
  - 校稿徽章文字用 ``{{qa_proofread}}`` / ``{{qa_unproofread}}`` 佔位符，
    由 :class:`~generators.html_generator.HTMLGenerator` 在 OpenCC 轉換「之前」
    換成對應語言，避免雙重轉換。
  - 音檔檔名（含中文）以 percent-encode 寫進 ``data-audio``，全為 ASCII，
    OpenCC 簡繁轉換不會破壞檔名。
* **不污染搜尋索引**：播放按鈕與徽章放在 ``<div class="qa-meta-bar">`` 內，
  既不是 ``<p>`` 也不是 ``.question`` / ``.answer``，``ContentProcessor`` 不會
  將其文字納入搜尋。
"""

import re
from html import escape
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

from models.document_models import Chapter
from utils.text_utils import IDGenerator
from config.settings import Settings, Constants
from core.chapter_finalizer import finalize_chapter


# ---------------------------------------------------------------------------
# 佔位符（由 HTMLGenerator._process_i18n_placeholders 在 OpenCC 之前替換）
# ---------------------------------------------------------------------------

PROOFREAD_PLACEHOLDER = "{{qa_proofread}}"
UNPROOFREAD_PLACEHOLDER = "{{qa_unproofread}}"


# ---------------------------------------------------------------------------
# 正則 / 常量
# ---------------------------------------------------------------------------

# 檔名：2025年11月10日Tai師父官網答疑.txt → (年, 月, 日, 來源)
FILENAME_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日.*?師父(.+?)答疑")

# 段落標題：### 1. 問題內容
HEADING_RE = re.compile(r"^###\s+(\d+)\.\s*(.*)$", re.M)

# 時間範圍：開場時間：00:00:00.570 - 00:00:09.190 / 時間：00:00:09.190 - 00:01:39.160
TIME_RANGE_RE = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s*[-–—]\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})"
)

EDITED_RE = re.compile(r"^最後編輯[：:]\s*(.*)$")
PLAYED_RE = re.compile(r"^最後播放[：:]\s*(.*)$")
ANSWER_RE = re.compile(r"^Taiguanglin[：:]\s*(.*)$")
TIME_LINE_RE = re.compile(r"^(?:開場時間|時間)[：:]")
NOTE_LINE_RE = re.compile(r"^[（(]")

# 來源排序：同一天先「官網」再「微信公眾號」
SOURCE_RANK = {"官網": 0, "微信公眾號": 1, "微信公众号": 1, "贴吧": 2, "貼吧": 2}

MONTH_CN = {
    1: "一月", 2: "二月", 3: "三月", 4: "四月", 5: "五月", 6: "六月",
    7: "七月", 8: "八月", 9: "九月", 10: "十月", 11: "十一月", 12: "十二月",
}
_DIGIT_CN = "〇一二三四五六七八九"


def _year_to_cn(year: int) -> str:
    """2025 → 二〇二五"""
    return "".join(_DIGIT_CN[int(d)] for d in str(year))


def _timecode_to_seconds(tc: str) -> Optional[float]:
    """``HH:MM:SS.mmm`` → 秒（float）。無法解析時回傳 ``None``。"""
    if not tc:
        return None
    tc = tc.strip().replace(",", ".")
    m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2}(?:\.\d{1,3})?)$", tc)
    if not m:
        return None
    h, mm, ss = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mm * 60 + ss


class QAParser:
    """把 ``qa/`` 資料夾的 txt 文字稿解析成依月份分章的 ``Chapter`` 清單。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.id_generator = IDGenerator(settings)
        self.audio_base = getattr(Constants, "QA_AUDIO_BASE", "../audio/")

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def parse_folder(self, folder: Path, start_index: int = 16) -> List[Chapter]:
        """讀取資料夾內所有答疑 txt，回傳依月份分章的 ``Chapter`` 清單。

        Args:
            folder: ``qa/`` 資料夾路徑
            start_index: 既有章節數（章節編號從 ``start_index + 1`` 開始，
                例如 16 → 第一個月份章節為 17）
        """
        folder = Path(folder)
        sections: List[Dict] = []
        for txt_path in sorted(folder.glob("*.txt")):
            name = txt_path.name
            if name.startswith("_") or name.lower().startswith("readme"):
                continue
            meta = self._parse_filename(name)
            if meta is None:
                continue
            year, month, day, source = meta
            text = txt_path.read_text(encoding="utf-8")
            audio_rel = self.audio_base + quote(txt_path.stem + ".opus")
            section = self.build_section(text, year, month, day, source, audio_rel)
            if section is not None:
                sections.append(section)
        return self._sections_to_chapters(sections, start_index)

    # ------------------------------------------------------------------ #
    # 1. 檔名 → (年, 月, 日, 來源)                                          #
    # ------------------------------------------------------------------ #

    def _parse_filename(self, name: str) -> Optional[Tuple[int, int, int, str]]:
        m = FILENAME_RE.search(name)
        if not m:
            return None
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4).strip())

    # ------------------------------------------------------------------ #
    # 2. 文字稿 → 開場 + 段落（純函式）                                     #
    # ------------------------------------------------------------------ #

    def parse_text(self, text: str) -> Dict:
        """把單一份文字稿解析成 ``{"opening": {...}, "segments": [...]}``。

        - ``opening``: ``{"range": (start, end, label)|None, "paras": [str]}``
        - ``segments[i]``: ``{"number": str, "question": [str], "answer": [str],
          "range": (start, end, label)|None, "edited": str}``
        """
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        matches = list(HEADING_RE.finditer(text))

        header = text[: matches[0].start()] if matches else text
        opening = self._parse_header(header)

        segments: List[Dict] = []
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            seg = self._parse_segment(m.group(1), m.group(2), text[start:end])
            segments.append(seg)

        return {"opening": opening, "segments": segments}

    def _parse_header(self, header: str) -> Dict:
        lines = header.split("\n")
        range_tuple = None
        paras: List[str] = []
        buf: List[str] = []

        def flush():
            if buf:
                paras.append("".join(buf))
                buf.clear()

        for idx, raw in enumerate(lines):
            s = raw.strip()
            if idx == 0:
                # 第一行是標題（YYYY年M月D日 Tai師父…整理稿），略過
                continue
            if not s:
                flush()
                continue
            if TIME_LINE_RE.match(s):
                tm = TIME_RANGE_RE.search(s)
                if tm:
                    range_tuple = self._make_range(tm)
                continue
            if NOTE_LINE_RE.match(s):
                # 編者按（時間已依字幕校對…）—— 不納入內文
                continue
            buf.append(s)
        flush()
        return {"range": range_tuple, "paras": paras}

    def _parse_segment(self, number: str, heading_text: str, body: str) -> Dict:
        lines = body.split("\n")
        question: List[str] = []
        answer: List[str] = []
        range_tuple = None
        edited = ""
        mode = "question"
        cur: List[str] = []
        if heading_text.strip():
            cur.append(heading_text.strip())

        def flush():
            nonlocal cur
            if cur:
                (question if mode == "question" else answer).append("".join(cur))
            cur = []

        for raw in lines:
            s = raw.strip()
            if not s:
                flush()
                continue
            if TIME_LINE_RE.match(s):
                flush()
                tm = TIME_RANGE_RE.search(s)
                if tm:
                    range_tuple = self._make_range(tm)
                continue
            em = EDITED_RE.match(s)
            if em:
                flush()
                edited = em.group(1).strip()
                continue
            if PLAYED_RE.match(s):
                flush()
                continue
            am = ANSWER_RE.match(s)
            if am:
                flush()
                mode = "answer"
                rest = am.group(1).strip()
                if rest:
                    cur.append(rest)
                continue
            cur.append(s)
        flush()

        return {
            "number": number,
            "question": question,
            "answer": answer,
            "range": range_tuple,
            "edited": edited,
        }

    @staticmethod
    def _make_range(match: re.Match) -> Optional[Tuple[float, float, str]]:
        start = _timecode_to_seconds(match.group(1))
        end = _timecode_to_seconds(match.group(2))
        if start is None or end is None:
            return None
        label = f"{match.group(1).strip()} - {match.group(2).strip()}"
        return (start, end, label)

    # ------------------------------------------------------------------ #
    # 3. 段落 → HTML 區段（日期 + 來源 = h2）                               #
    # ------------------------------------------------------------------ #

    def build_section(
        self,
        text: str,
        year: int,
        month: int,
        day: int,
        source: str,
        audio_rel: str,
    ) -> Optional[Dict]:
        parsed = self.parse_text(text)
        opening = parsed["opening"]
        segments = parsed["segments"]
        if not segments and not opening["paras"]:
            return None

        h2_text = f"{year}年{month}月{day}日 {source}"
        anchor = self.id_generator.generate_heading_id(h2_text)
        blocks: List[str] = [f'<h2 id="{anchor}">{escape(h2_text)}</h2>']

        # 開場白（含播放鈕，但無校稿徽章）
        if opening["range"] or opening["paras"]:
            blocks.append(
                f'<div class="qa-meta-bar qa-meta-bar--opening">'
                f'{self._render_play(opening["range"], audio_rel)}</div>'
            )
            for p in opening["paras"]:
                blocks.append(f'<p class="qa-opening">{escape(p)}</p>')

        # 各答疑段落
        for seg in segments:
            blocks.append(self._render_meta_bar(seg, audio_rel))
            blocks.append(self._render_question(seg))
            answer_block = self._render_answer(seg)
            if answer_block:
                blocks.append(answer_block)

        return {
            "year": year,
            "month": month,
            "day": day,
            "source": source,
            "h2_text": h2_text,
            "anchor": anchor,
            "blocks": blocks,
        }

    def _render_play(self, range_tuple, audio_rel: str) -> str:
        if not range_tuple:
            return '<span class="qa-play qa-play--disabled" aria-disabled="true">▶</span>'
        start, end, label = range_tuple
        return (
            f'<button class="qa-play" type="button" '
            f'data-audio="{escape(audio_rel, quote=True)}" '
            f'data-start="{start:.3f}" data-end="{end:.3f}" '
            f'data-label="{escape(label, quote=True)}">'
            f'<span class="qa-play-icon">▶</span>'
            f'<span class="qa-play-label">{escape(label)}</span>'
            f"</button>"
        )

    def _render_meta_bar(self, seg: Dict, audio_rel: str) -> str:
        number = seg.get("number") or ""
        number_html = (
            f'<span class="qa-number">{escape(number)}.</span>' if number else ""
        )
        play = self._render_play(seg.get("range"), audio_rel)
        edited = seg.get("edited") or ""
        if edited:
            status = (
                f'<span class="qa-status qa-status--proofread">'
                f"{PROOFREAD_PLACEHOLDER} {escape(edited)}</span>"
            )
        else:
            status = (
                f'<span class="qa-status qa-status--ai">'
                f"{UNPROOFREAD_PLACEHOLDER}</span>"
            )
        return f'<div class="qa-meta-bar">{number_html}{play}{status}</div>'

    def _render_question(self, seg: Dict) -> str:
        paras = seg.get("question") or []
        joined = " ".join(paras)
        label = seg["range"][2] if seg.get("range") else ""
        qid = self.id_generator.generate_stable_qa_id("", joined, label, "question")
        text_divs = "\n".join(
            f'    <div class="question-text">{escape(p)}</div>' for p in paras
        )
        return f'<div class="question" id="{qid}">\n{text_divs}\n</div>'

    def _render_answer(self, seg: Dict) -> str:
        paras = seg.get("answer") or []
        if not paras:
            return ""
        answerer = Constants.ANSWERER_RAW_NAME
        joined = " ".join(paras)
        aid = self.id_generator.generate_stable_qa_id(answerer, joined, "", "answer")
        text_divs = "\n".join(
            f'    <div class="answer-text">{escape(p)}</div>' for p in paras
        )
        return (
            f'<div class="answer" id="{aid}">\n'
            f'    <div class="answer-meta">\n'
            f'        <span class="answerer">{escape(answerer)}</span>\n'
            f"    </div>\n"
            f"{text_divs}\n"
            f"</div>"
        )

    # ------------------------------------------------------------------ #
    # 4. 區段 → 依（年, 月）分章                                            #
    # ------------------------------------------------------------------ #

    def _sections_to_chapters(
        self, sections: List[Dict], start_index: int
    ) -> List[Chapter]:
        if not sections:
            return []

        by_month: Dict[Tuple[int, int], List[Dict]] = {}
        for sec in sections:
            by_month.setdefault((sec["year"], sec["month"]), []).append(sec)

        chapters: List[Chapter] = []
        for offset, key in enumerate(sorted(by_month.keys())):
            year, month = key
            index = start_index + 1 + offset
            month_sections = by_month[key]
            # 同月內依（日, 來源）排序：時間先後，官網先於微信公眾號
            month_sections.sort(
                key=lambda s: (s["day"], SOURCE_RANK.get(s["source"], 9))
            )

            title = f"{index:02d}{_year_to_cn(year)}年{MONTH_CN.get(month, f'{month}月')}"
            h1_anchor = self.id_generator.generate_heading_id(title)

            content_blocks: List[str] = [f'<h1 id="{h1_anchor}">{escape(title)}</h1>']
            toc_items: List[Tuple[int, str, str]] = []
            for sec in month_sections:
                content_blocks.extend(sec["blocks"])
                toc_items.append((2, sec["h2_text"], sec["anchor"]))

            chapter = Chapter(title=title, filename=f"{index:02d}.html", is_qa=True)
            finalize_chapter(chapter, content_blocks, toc_items, self.settings)
            chapters.append(chapter)

        return chapters
