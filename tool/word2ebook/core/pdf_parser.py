"""PDF 答疑解析器

把「每月答疑合併 PDF」解析成多個按「月份」分章的 ``Chapter``，每個月份章節
下以「日期 + 來源」作為第二層目錄（h2），底下是一問一答的卡片，版型與
``DocumentParser``（Word）產生的結果一致，並共用 ``chapter_finalizer``。

設計重點
--------
* **可測試**：與 PyMuPDF 相關的只有 :meth:`_extract_lines`（回傳 ``(x0, text)``
  行清單）。核心解析 :meth:`parse_lines` 是純函式，測試可直接餵入行清單。
* **可擴充**：來源（貼吧/微信公眾號/官網…）、月份名稱、起始章節編號都可調整，
  之後要把 ``qa/`` 資料夾的內容接進來時，只要產出相同形狀的 ``Chapter`` 即可。

PDF 行的版面特徵（由 PyMuPDF 的 x 座標得到）
* x0 ≈ 118：段落「首行」（有縮排）→ 視為新段落起點
* x0 ≈ 90 ：換行延續行（無縮排）→ 接到上一段落
* 提問者行、``Taiguanglin：``、分隔線雖然也在 x0 ≈ 90，但以正則辨識
"""

import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict

from models.document_models import Chapter
from utils.text_utils import TextProcessor, IDGenerator
from config.settings import Settings, Constants
from core.chapter_finalizer import finalize_chapter


# ---------------------------------------------------------------------------
# 常量 / 正則
# ---------------------------------------------------------------------------

INDENT_THRESHOLD = 104.0  # x0 大於此值視為「縮排首行」（118 vs 90 的中間值）

FOOTER_TEXT = "完整音频请关注微信公众号"

PAGE_RE = re.compile(r"^\d+\s*/\s*\d+$")
DAY_RE = re.compile(r"Tai\s*师父\s*(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号號]")
SHIFU_RE = re.compile(r"^师父说[：:]")
ANSWER_RE = re.compile(r"^Taiguanglin[：:]")
QTIME_RE = re.compile(
    r"^(?P<name>.{1,40}?)[：:]\s*(?P<time>20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2})\s*$"
)
NAMECOLON_RE = re.compile(r"^(?P<name>.{1,40}?)[：:]\s*$")
BARETIME_RE = re.compile(r"^20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}$")
NUM_RE = re.compile(r"^(问题|問題|问|問|第)?\s*\d+\s*[、.，,)）]")
SEP_RE = re.compile(r"^[—\-－_]{6,}$")
LEAD_DASH_RE = re.compile(r"^([—\-－]{6,})(.*)$")
LONE_COLON_RE = re.compile(r"^[：:]\s*$")

# 來源標籤（簡體；繁體版由 opencc 轉換，與 qa/ 資料夾的「貼吧/微信公眾號/官網」對應）
SOURCE_TIEBA = "贴吧"
SOURCE_WEIXIN = "微信公众号"
SOURCE_RANK = {SOURCE_TIEBA: 0, SOURCE_WEIXIN: 1}

MONTH_CN = {
    1: "一月", 2: "二月", 3: "三月", 4: "四月", 5: "五月", 6: "六月",
    7: "七月", 8: "八月", 9: "九月", 10: "十月", 11: "十一月", 12: "十二月",
}
_DIGIT_CN = "〇一二三四五六七八九"

# 移除與中文字相鄰的空白（PDF 中 CJK 與 ASCII 之間的排版空格）
_SPACE_AFTER_CJK = re.compile(r"(?<=[\u4e00-\u9fff])\s+")
_SPACE_BEFORE_CJK = re.compile(r"\s+(?=[\u4e00-\u9fff])")


def _year_to_cn(year: int) -> str:
    """2025 → 二〇二五"""
    return "".join(_DIGIT_CN[int(d)] for d in str(year))


def _normalize_spaces(text: str) -> str:
    """移除 CJK 字元相鄰的排版空格，並壓縮多餘空白。"""
    text = _SPACE_AFTER_CJK.sub("", text)
    text = _SPACE_BEFORE_CJK.sub("", text)
    return text.strip()


def _is_name_tail(s: str) -> bool:
    """``s`` 是否為「被折行的提問者名字」後半段（以冒號收尾，可帶時間）。

    例如分隔線上黏著「白瀑」、下一行是「印龙：2025-08-05 10:34」或「柿：」，
    後半段即為 name tail，應與前半段合併成完整提問者。排除 ``Taiguanglin：``、
    ``师父说：`` 這類標記行。
    """
    if not s or ANSWER_RE.match(s) or s.startswith("师父说"):
        return False
    return bool(QTIME_RE.match(s) or NAMECOLON_RE.match(s))


def _plausible_lone_name(s: str) -> bool:
    """黏在分隔線後、且下一行非 name tail 時，``s`` 是否像「無冒號的提問者名」。

    分隔線之後必為提問者，但少數名字抽取時遺失了冒號（例如「洋」後面直接接
    問題內容）。此時補上冒號當成無時間提問者。以長度與標點排除句子/標記。
    """
    if not s or len(s) > 16:
        return False
    if ANSWER_RE.match(s) or s.startswith("师父说") or NUM_RE.match(s):
        return False
    return not re.search(r"[。？！，；,.?!;：:]", s)


def _is_boundary_after_sep(nxt: str) -> bool:
    """分隔線之後的 ``nxt`` 是否為「新提問者／結構標記」（→ 該分隔線是真正分界）。

    用於判斷縮排分隔線：若其後是內文（非提問者），代表這是使用者在自己問題裡
    畫的分隔線，應丟棄而非斷開卡片。
    """
    if not nxt:
        return False
    if SHIFU_RE.match(nxt) or ANSWER_RE.match(nxt) or DAY_RE.search(nxt):
        return True
    if QTIME_RE.match(nxt):
        return True
    m = NAMECOLON_RE.match(nxt)
    return bool(m and _plausible_lone_name(_normalize_spaces(m.group("name"))))


class PDFParser:
    """PDF 答疑解析器。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.text_processor = TextProcessor(settings)
        self.id_generator = IDGenerator(settings)

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def parse(self, pdf_path: Path, start_index: int = 12) -> List[Chapter]:
        """解析 PDF，回傳依月份分章的 ``Chapter`` 清單。

        Args:
            pdf_path: PDF 路徑
            start_index: 既有章節數（章節編號從 ``start_index + 1`` 開始，
                例如 12 → 第一個月份章節為 13）
        """
        lines = self._extract_lines(Path(pdf_path))
        return self.parse_lines(lines, start_index=start_index)

    def parse_lines(
        self, lines: List[Tuple[float, str]], start_index: int = 12
    ) -> List[Chapter]:
        """核心解析（純函式，便於測試）。

        Args:
            lines: ``(x0, text)`` 行清單（已含版面 x 座標）
            start_index: 既有章節數
        """
        cleaned = self._preclean(lines)
        sections = self._build_sections(cleaned)
        return self._sections_to_chapters(sections, start_index)

    # ------------------------------------------------------------------ #
    # 1. PyMuPDF 文字抽取（唯一依賴 fitz 的部分）                          #
    # ------------------------------------------------------------------ #

    def _extract_lines(self, pdf_path: Path) -> List[Tuple[float, str]]:
        import fitz  # 延遲匯入，讓不跑 PDF 的測試不需要安裝 PyMuPDF

        doc = fitz.open(pdf_path)
        out: List[Tuple[float, str]] = []
        for page in doc:
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                for ln in block.get("lines", []):
                    spans = ln.get("spans", [])
                    if not spans:
                        continue
                    text = "".join(s.get("text", "") for s in spans).strip()
                    if not text:
                        continue
                    x0 = round(ln["bbox"][0], 1)
                    out.append((x0, text))
        doc.close()
        return out

    # ------------------------------------------------------------------ #
    # 2. 行清理：移除頁碼/頁尾、拆分黏住的分隔線、合併「人名：」+「時間」    #
    # ------------------------------------------------------------------ #

    def _preclean(self, lines: List[Tuple[float, str]]) -> List[Tuple[float, str]]:
        # 階段 0：移除頁碼／頁尾／空行
        clean: List[Tuple[float, str]] = []
        for x0, raw in lines:
            t = raw.strip()
            if not t or PAGE_RE.match(t) or FOOTER_TEXT in t:
                continue
            clean.append((x0, t))

        # 階段 1：拆出黏在行首的長分隔線（例如「———…———紫蘇：」），並把
        # 「被分隔線擠到上一行」的提問者名字重新接回來。版面上分隔線之後一定
        # 是提問者，名字較長時會折行成「———…———白瀑」+「印龙：2025-…」或
        # 「———…———西瓜」+「柿：」，必須合併成完整提問者，否則前半段會變成
        # 孤立段落、後半段被誤判成另一個提問者。
        stage1: List[Tuple[float, str]] = []
        i = 0
        n = len(clean)
        while i < n:
            x0, t = clean[i]
            m = LEAD_DASH_RE.match(t)
            if not m:
                stage1.append((x0, t))
                i += 1
                continue
            stage1.append((x0, m.group(1)))  # 分隔線本身
            rest = m.group(2).strip()
            if not rest:
                i += 1
                continue
            if rest.endswith(("：", ":")):
                # 完整「人名：」黏在分隔線上 → 原樣保留（stage2 可能再併純時間）
                stage1.append((x0, rest))
                i += 1
                continue
            nxt = clean[i + 1][1].strip() if i + 1 < n else ""
            if _is_name_tail(nxt):
                # 折行名字前半段 + 後半段（白瀑 + 印龙：time → 白瀑印龙：time）
                stage1.append((x0, rest + nxt))
                i += 2
                continue
            if _plausible_lone_name(rest):
                # 名字遺失冒號（洋 → 洋：）→ 當成無時間提問者
                stage1.append((x0, rest + "："))
                i += 1
                continue
            stage1.append((x0, rest))
            i += 1

        # 階段 1.5：合併「人名」+ 單獨一行的冒號。短名提問者行（如「M」「奔跑吧
        # 兄弟」）會被左右對齊把冒號擠到行尾、甚至獨立成一行「：」，造成名字與冒號
        # 分離。把它們接回成「人名：」。
        stageL: List[Tuple[float, str]] = []
        i = 0
        while i < len(stage1):
            x0, t = stage1[i]
            if (
                i + 1 < len(stage1)
                and LONE_COLON_RE.match(stage1[i + 1][1])
                and _plausible_lone_name(_normalize_spaces(t))
            ):
                stageL.append((x0, t + "："))
                i += 2
                continue
            stageL.append((x0, t))
            i += 1

        # 階段 2：合併「人名：」（單獨一行、無時間）+ 下一行純時間
        merged: List[Tuple[float, str]] = []
        i = 0
        while i < len(stageL):
            x0, t = stageL[i]
            if (
                i + 1 < len(stageL)
                and NAMECOLON_RE.match(t)
                and not t.startswith("师父说")
                and not ANSWER_RE.match(t)
                and BARETIME_RE.match(stageL[i + 1][1])
            ):
                merged.append((x0, t + stageL[i + 1][1]))
                i += 2
                continue
            merged.append((x0, t))
            i += 1

        # 階段 3：丟棄「問題內部」的縮排分隔線。真正用來分隔提問者的分隔線在
        # 左邊界（x0≈90）；少數使用者會在自己的問題裡畫一條線（x0≈118 縮排），
        # 若其後不是新提問者就視為內文裝飾，丟棄以免把同一個問題切開。
        result: List[Tuple[float, str]] = []
        for i, (x0, t) in enumerate(merged):
            if SEP_RE.match(t) and x0 >= INDENT_THRESHOLD:
                nxt = merged[i + 1][1] if i + 1 < len(merged) else ""
                if not _is_boundary_after_sep(nxt):
                    continue
            result.append((x0, t))
        return result

    # ------------------------------------------------------------------ #
    # 3. 狀態機：行 → 段落 → 卡片 → 區段（日期+來源）                       #
    # ------------------------------------------------------------------ #

    def _build_sections(self, lines: List[Tuple[float, str]]) -> List[Dict]:
        sections: List[Dict] = []

        state = {
            "date": None,            # (year, month, day)
            "source": SOURCE_TIEBA,  # 每天預設先從貼吧開始
            "questioner": None,
            "qtime": None,
            "section": None,         # 目前區段 dict
            "card": None,            # 目前卡片 dict
            "para": None,            # 目前段落（fragment 清單）
        }

        def finish_para():
            if state["para"]:
                text = _normalize_spaces("".join(state["para"]))
                if text and state["card"] is not None:
                    state["card"]["paras"].append(text)
            state["para"] = None

        def finish_card():
            finish_para()
            card = state["card"]
            state["card"] = None
            if not card or not card["paras"]:
                return
            block = self._render_card(card)
            if block and state["section"] is not None:
                state["section"]["blocks"].append(block)

        def ensure_section():
            key = (state["date"], state["source"])
            if state["date"] is None:
                return
            if state["section"] is not None and state["section"]["key"] == key:
                return
            year, month, day = state["date"]
            h2_text = f"{year}年{month}月{day}日 {state['source']}"
            anchor = self.id_generator.generate_heading_id(h2_text)
            section = {
                "key": key,
                "date": state["date"],
                "source": state["source"],
                "h2_text": h2_text,
                "anchor": anchor,
                "blocks": [f'<h2 id="{anchor}">{h2_text}</h2>'],
            }
            sections.append(section)
            state["section"] = section

        def start_card(kind, name=None, time=None):
            finish_card()
            ensure_section()
            state["card"] = {
                "kind": kind, "name": name, "time": time, "paras": [],
                "numbered": False, "shifu": False,
            }

        def add_line(text, indented):
            if state["card"] is None:
                start_card("paragraph")
            if indented or state["para"] is None:
                finish_para()
                state["para"] = [text]
            else:
                state["para"].append(text)

        for x0, text in lines:
            indented = x0 > INDENT_THRESHOLD

            # 新的一天
            if text.startswith("Tai"):
                m = DAY_RE.search(text)
                if m:
                    finish_card()
                    state["date"] = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    state["source"] = SOURCE_TIEBA
                    state["questioner"] = None
                    state["qtime"] = None
                    continue

            # 分隔線（黏住的已在 preclean 拆出）
            if SEP_RE.match(text):
                finish_card()
                continue

            # 師父說（敘述 + 來源切換訊號）
            if SHIFU_RE.match(text):
                if "公众号" in text or "微信" in text:
                    state["source"] = SOURCE_WEIXIN
                content = re.sub(r"^师父说[：:]\s*", "", text)
                start_card("paragraph")
                state["card"]["shifu"] = True
                add_line(content, indented=True)
                continue

            # 回答
            if ANSWER_RE.match(text):
                after = re.sub(r"^Taiguanglin[：:]\s*", "", text)
                start_card("answer")
                if after:
                    add_line(after, indented=True)
                continue

            # 提問者（人名 + 時間）
            qm = QTIME_RE.match(text)
            if qm:
                state["questioner"] = _normalize_spaces(qm.group("name"))
                state["qtime"] = qm.group("time").strip()
                start_card("question", state["questioner"], state["qtime"])
                continue

            # 提問者（人名，無時間）：很多貼吧/公眾號的留言沒有時間戳，
            # 名字上方一定有分隔線（→ card 為 None），或緊接在師父說的來源
            # 開場之後（→ card 為師父說段落）。其餘以冒號結尾的行（例如句子中的
            # 「想請教三個問題：」）發生在問題/回答卡片內，視為內文延續，不誤判。
            if x0 < INDENT_THRESHOLD and not indented:
                nc = NAMECOLON_RE.match(text)
                lone = LONE_COLON_RE.match(text)
                if nc or lone:
                    card = state["card"]
                    is_section_intro = card is None or (
                        card["kind"] == "paragraph" and card.get("shifu")
                    )
                    if is_section_intro:
                        # 提問者名字偶爾完全抽取不到，只剩一個冒號 → 無名提問者
                        name = _normalize_spaces(nc.group("name")) if nc else ""
                        if name or lone:
                            state["questioner"] = name
                            state["qtime"] = ""
                            start_card("question", name, "")
                            continue

            # 編號子問題
            if indented and NUM_RE.match(text):
                card = state["card"]
                if card is not None and card["kind"] == "question":
                    # 同一位提問者「連續」的編號子問題（中間沒有師父回答／分隔線／
                    # 新提問者）視為同一個多段式問題，併進同一張問題卡片；每個編號各自
                    # 成段（question-text）。引言（如「頂禮師父／續問：」）也留在同卡。
                    add_line(text, indented=True)
                    card["numbered"] = True
                else:
                    # 編號問題出現在回答／敘述段落之後或尚無卡片 → 是新的一輪提問，
                    # 沿用同一提問者另開新卡片。
                    start_card("question", state["questioner"], state["qtime"])
                    add_line(text, indented=True)
                    state["card"]["numbered"] = True
                continue

            # 一般內文（縮排=新段落；否則接續）
            add_line(text, indented)

        finish_card()
        return sections

    def _render_card(self, card: Dict) -> str:
        kind = card["kind"]
        paras = card["paras"]
        if not paras:
            return ""

        if kind == "paragraph":
            return "\n".join(f"<p>{p}</p>" for p in paras)

        if kind == "question":
            name = card["name"] or ""
            time = card["time"] or ""
            joined = " ".join(paras)
            qid = self.id_generator.generate_stable_qa_id(name, joined, time, "question")
            time_html = f'<span class="question-time">{time}</span>' if time else ""
            text_divs = "\n".join(f'    <div class="question-text">{p}</div>' for p in paras)
            return (
                f'<div class="question" id="{qid}">\n'
                f'    <div class="question-meta">\n'
                f'        <span class="questioner">{name}</span>\n'
                f'        {time_html}\n'
                f'    </div>\n'
                f'{text_divs}\n'
                f'</div>'
            )

        if kind == "answer":
            answerer = Constants.ANSWERER_RAW_NAME
            joined = " ".join(paras)
            aid = self.id_generator.generate_stable_qa_id(answerer, joined, "", "answer")
            text_divs = "\n".join(f'    <div class="answer-text">{p}</div>' for p in paras)
            return (
                f'<div class="answer" id="{aid}">\n'
                f'    <div class="answer-meta">\n'
                f'        <span class="answerer">{answerer}</span>\n'
                f'        \n'
                f'    </div>\n'
                f'{text_divs}\n'
                f'</div>'
            )

        return ""

    # ------------------------------------------------------------------ #
    # 4. 區段 → 依月份分章                                                 #
    # ------------------------------------------------------------------ #

    def _sections_to_chapters(
        self, sections: List[Dict], start_index: int
    ) -> List[Chapter]:
        if not sections:
            return []

        # 依月份分組
        by_month: Dict[int, List[Dict]] = {}
        year = sections[0]["date"][0]
        for sec in sections:
            by_month.setdefault(sec["date"][1], []).append(sec)

        chapters: List[Chapter] = []
        for offset, month in enumerate(sorted(by_month.keys())):
            index = start_index + 1 + offset
            month_sections = by_month[month]
            # 同一月份內依（日期, 來源）排序，使閱讀順序為時間先後、貼吧先於公眾號
            month_sections.sort(key=lambda s: (s["date"], SOURCE_RANK.get(s["source"], 9)))

            title = f"{index:02d}{_year_to_cn(year)}年{MONTH_CN.get(month, f'{month}月')}"
            h1_anchor = self.id_generator.generate_heading_id(title)

            content_blocks: List[str] = [f'<h1 id="{h1_anchor}">{title}</h1>']
            toc_items: List[Tuple[int, str, str]] = []
            for sec in month_sections:
                content_blocks.extend(sec["blocks"])
                toc_items.append((2, sec["h2_text"], sec["anchor"]))

            chapter = Chapter(title=title, filename=f"{index:02d}.html")
            finalize_chapter(chapter, content_blocks, toc_items, self.settings)
            chapters.append(chapter)

        return chapters
