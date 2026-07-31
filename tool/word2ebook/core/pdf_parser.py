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
from utils.file_utils import ImageHandler
from config.settings import Settings, Constants
from core.chapter_finalizer import finalize_chapter


def _import_pymupdf():
    """匯入 PyMuPDF，回傳其模組物件。

    PyMuPDF 自 1.23.0 起同時以 ``pymupdf``（推薦）與 ``fitz`` 兩個名稱提供模組。
    我們優先匯入 ``pymupdf``，因為 PyPI 上另有一個與 PyMuPDF 無關、同樣叫 ``fitz``
    的套件（依賴 ``frontend``/``starlette``），若被誤裝會在 ``import fitz`` 時搶先載入
    並丟出 ``RuntimeError: Directory 'static/' does not exist``。改用 ``pymupdf``
    名稱可繞過此命名衝突；找不到時才退回 ``fitz`` 並給出明確的修正提示。
    """
    try:
        import pymupdf  # PyMuPDF >= 1.23.0 的正式模組名
        return pymupdf
    except ImportError:
        pass

    try:
        import fitz
    except ImportError as exc:
        raise ImportError(
            "需要 PyMuPDF 才能解析 PDF。請執行：pip install --upgrade PyMuPDF"
        ) from exc

    # 偵測「冒牌 fitz」：真正的 PyMuPDF 會有 open()/Document 屬性
    if not hasattr(fitz, "open"):
        raise ImportError(
            "匯入到的 'fitz' 不是 PyMuPDF（可能誤裝了同名的 'fitz' 套件）。"
            "請執行：pip uninstall -y fitz && pip install --upgrade PyMuPDF"
        )
    return fitz


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
SOURCE_GUANWANG = "官网"
SOURCE_WEIXIN = "微信公众号"
# 同一天：官网 / 贴吧 皆排在微信公众号之前
SOURCE_RANK = {SOURCE_GUANWANG: 0, SOURCE_TIEBA: 0, SOURCE_WEIXIN: 1}

# 行串流中的圖片標記（由 _extract_lines 寫入；parse_lines 可直接餵入以便測試）
IMG_MARKER_PREFIX = "__PDF_IMG__:"
# 兩邊皆小於此像素的圖視為 emoji/裝飾，丟棄
IMG_MIN_SIDE = 80

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


def _is_img_marker(text: str) -> bool:
    return text.startswith(IMG_MARKER_PREFIX)


def _detect_source_from_shifu(text: str) -> Optional[str]:
    """從師父說開場文推斷來源；無法判斷時回傳 None（維持現況）。

    規則重點：
    - 「微信公众号的问题」優於順帶提到的「贴吧的问题太多」（2025-07-07）
    - 「下边回答了，去公众号」不算切到微信（2025-08-04 贴吧开场）
    - 純收尾行（就回答到这里）不切源，避免空的贴吧段（2025-08-09）
    """
    # Explicit 「X的问题/答疑」labels — 微信 before 贴吧 so
    # 「…微信公众号的问题。因为贴吧的问题太多了」→ 微信
    if re.search(r"(微信\s*)?公众号的(问题|答疑)", text) or re.search(
        r"(微信\s*)?公眾號的(問題|答疑)", text
    ) or re.search(r"微信的(问题|答疑)", text):
        return SOURCE_WEIXIN
    if re.search(r"(先回答|继续回答|回答)\s*贴吧的(问题|答疑)", text) or re.search(
        r"(先回答|繼續回答|回答)\s*貼吧的(問題|答疑)", text
    ):
        return SOURCE_TIEBA
    if re.search(r"(先回答|继续回答|回答)\s*官网的(问题|答疑)", text) or re.search(
        r"(先回答|繼續回答|回答)\s*官網的(問題|答疑)", text
    ):
        return SOURCE_GUANWANG
    if re.search(r"官方网站", text[:120]):
        return SOURCE_GUANWANG

    # Pure wrap-up: keep current source (do not spawn empty sections)
    if re.search(
        r"(就回答到这[里裡]|回答就到这[里裡]|答疑就到这[里裡]|今天就回答到这[里裡])",
        text,
    ):
        return None

    has_tieba = "贴吧" in text or "貼吧" in text
    has_weixin = "公众号" in text or "微信公众" in text
    has_guanwang = "官网" in text or "官網" in text

    # Weak keywords: 贴吧 wins over incidental 公众号/微信 mention
    if has_tieba:
        return SOURCE_TIEBA
    if has_weixin:
        return SOURCE_WEIXIN
    if has_guanwang:
        return SOURCE_GUANWANG
    if re.search(r"\d+\s*楼", text):
        return SOURCE_GUANWANG
    return None


def _is_structural_line(text: str) -> bool:
    """是否為會打斷師父說開場折行的結構行。"""
    if _is_img_marker(text) or SEP_RE.match(text) or ANSWER_RE.match(text):
        return True
    if SHIFU_RE.match(text) or QTIME_RE.match(text) or NAMECOLON_RE.match(text):
        return True
    if text.startswith("Tai") and DAY_RE.search(text):
        return True
    if LONE_COLON_RE.match(text):
        return True
    return False


def _img_marker_path(text: str) -> str:
    return text[len(IMG_MARKER_PREFIX):]


def make_img_marker(relative_path: str) -> str:
    """測試／抽取共用的圖片標記字串。"""
    return f"{IMG_MARKER_PREFIX}{relative_path}"


class PDFParser:
    """PDF 答疑解析器。"""

    def __init__(self, settings: Settings, image_handler: Optional[ImageHandler] = None):
        self.settings = settings
        self.text_processor = TextProcessor(settings)
        self.id_generator = IDGenerator(settings)
        self.image_handler = image_handler

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
            lines: ``(x0, text)`` 行清單（已含版面 x 座標；圖片為
                ``(x0, "__PDF_IMG__:assets/images/…")`` 標記）
            start_index: 既有章節數
        """
        cleaned = self._preclean(lines)
        sections = self._build_sections(cleaned)
        return self._sections_to_chapters(sections, start_index)

    # ------------------------------------------------------------------ #
    # 1. PyMuPDF 文字 + 圖片抽取（唯一依賴 fitz 的部分）                   #
    # ------------------------------------------------------------------ #

    def _extract_lines(self, pdf_path: Path) -> List[Tuple[float, str]]:
        fitz = _import_pymupdf()  # 延遲匯入，讓不跑 PDF 的測試不需要安裝 PyMuPDF

        doc = fitz.open(pdf_path)
        out: List[Tuple[float, str]] = []
        # 同一 xref 可能在多頁重複出現（例如共用 emoji）；只寫檔一次
        xref_to_path: Dict[int, str] = {}

        for page in doc:
            items: List[Tuple[float, float, str]] = []  # (y0, x0, text_or_marker)

            data = page.get_text("dict")
            for block in data.get("blocks", []):
                if block.get("type") == 1:
                    # 圖片 block：以 bbox 對應 page.get_images 的 xref
                    continue
                for ln in block.get("lines", []):
                    spans = ln.get("spans", [])
                    if not spans:
                        continue
                    text = "".join(s.get("text", "") for s in spans).strip()
                    if not text:
                        continue
                    x0 = round(ln["bbox"][0], 1)
                    y0 = round(ln["bbox"][1], 1)
                    items.append((y0, x0, text))

            if self.image_handler is not None:
                for img in page.get_images(full=True):
                    xref = img[0]
                    try:
                        rects = page.get_image_rects(xref)
                    except Exception:
                        rects = []
                    if not rects:
                        # 無位置資訊則跳過（無法插入閱讀順序）
                        continue
                    # 取第一個出現位置
                    rect = rects[0]
                    w = abs(rect.width)
                    h = abs(rect.height)
                    # 過濾極小圖（emoji / 裝飾）；以顯示尺寸為準
                    if w < IMG_MIN_SIDE and h < IMG_MIN_SIDE:
                        continue
                    # 再以原始像素過濾一次（顯示被放大的小圖）
                    try:
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n - pix.alpha >= 4:  # CMYK → RGB
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        pw, ph = pix.width, pix.height
                        if pw < IMG_MIN_SIDE and ph < IMG_MIN_SIDE:
                            continue
                        if xref not in xref_to_path:
                            # 統一存 PNG
                            png_bytes = pix.tobytes("png")
                            xref_to_path[xref] = self.image_handler.save_image_bytes(png_bytes)
                        rel = xref_to_path[xref]
                        items.append((round(rect.y0, 1), round(rect.x0, 1), make_img_marker(rel)))
                    except Exception:
                        continue

            items.sort(key=lambda t: (t[0], t[1]))
            for _y, x0, payload in items:
                out.append((x0, payload))

        doc.close()
        return out

    # ------------------------------------------------------------------ #
    # 2. 行清理：移除頁碼/頁尾、拆分黏住的分隔線、合併「人名：」+「時間」    #
    # ------------------------------------------------------------------ #

    def _preclean(self, lines: List[Tuple[float, str]]) -> List[Tuple[float, str]]:
        # 階段 0：移除頁碼／頁尾／空行（圖片標記原樣保留）
        clean: List[Tuple[float, str]] = []
        for x0, raw in lines:
            t = raw.strip()
            if not t:
                continue
            if _is_img_marker(t):
                clean.append((x0, t))
                continue
            if PAGE_RE.match(t) or FOOTER_TEXT in t:
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
            if _is_img_marker(t):
                stage1.append((x0, t))
                i += 1
                continue
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
            if _is_img_marker(t):
                stageL.append((x0, t))
                i += 1
                continue
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
            if _is_img_marker(t):
                merged.append((x0, t))
                i += 1
                continue
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
            if _is_img_marker(t):
                result.append((x0, t))
                continue
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
            # 同一 (日期, 來源) 若先前已建過（來源切走又切回），接續該區段，避免重複 h2
            for sec in sections:
                if sec["key"] == key:
                    state["section"] = sec
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

        i = 0
        n_lines = len(lines)
        while i < n_lines:
            x0, text = lines[i]

            # 圖片：結束當前卡片後以獨立 block 插入（與 Word 一致）
            if _is_img_marker(text):
                finish_card()
                ensure_section()
                if state["section"] is not None:
                    rel = _img_marker_path(text)
                    state["section"]["blocks"].append(
                        f'<img src="{rel}" alt="Image">'
                    )
                i += 1
                continue

            indented = x0 > INDENT_THRESHOLD

            # 新的一天（同一日期的續錄音訊不重設來源，避免被誤標成贴吧）
            if text.startswith("Tai"):
                m = DAY_RE.search(text)
                if m:
                    finish_card()
                    new_date = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    if state["date"] != new_date:
                        state["source"] = SOURCE_TIEBA
                    state["date"] = new_date
                    state["questioner"] = None
                    state["qtime"] = None
                    i += 1
                    continue

            # 分隔線（黏住的已在 preclean 拆出）
            if SEP_RE.match(text):
                finish_card()
                i += 1
                continue

            # 無「师父说」前綴的開場（如 Nov 15：直接「今天是…先回答官网」）
            if (
                state["card"] is None
                and state["questioner"] is None
                and re.match(r"^今天是", text)
            ):
                blob_parts = [text]
                j = i + 1
                while j < n_lines:
                    _x1, t1 = lines[j]
                    if _is_structural_line(t1):
                        break
                    blob_parts.append(t1)
                    j += 1
                blob = "".join(blob_parts)
                detected = _detect_source_from_shifu(blob)
                if detected is not None:
                    state["source"] = detected
                elif state["source"] == SOURCE_TIEBA and not any(
                    s["date"] == state["date"] for s in sections
                ):
                    state["source"] = SOURCE_GUANWANG
                start_card("paragraph")
                add_line(blob, indented=True)
                i = j
                continue

            # 師父說（敘述 + 來源切換訊號）；開場常折行，先併後續延續行再判斷來源
            if SHIFU_RE.match(text):
                blob_parts = [text]
                j = i + 1
                while j < n_lines:
                    _x1, t1 = lines[j]
                    if _is_structural_line(t1):
                        break
                    blob_parts.append(t1)
                    j += 1
                blob = "".join(blob_parts)
                detected = _detect_source_from_shifu(blob)
                if detected is not None:
                    state["source"] = detected
                elif state["source"] == SOURCE_TIEBA and not any(
                    s["date"] == state["date"] for s in sections
                ):
                    # 當天第一段師父說未標來源（Nov–Mar 常見）→ 官网；
                    # Jun–Sep 開場會寫明「贴吧」，不會走到這裡。
                    state["source"] = SOURCE_GUANWANG
                content = re.sub(r"^师父说[：:]\s*", "", blob)
                start_card("paragraph")
                state["card"]["shifu"] = True
                add_line(content, indented=True)
                i = j
                continue

            # 回答
            if ANSWER_RE.match(text):
                after = re.sub(r"^Taiguanglin[：:]\s*", "", text)
                start_card("answer")
                if after:
                    add_line(after, indented=True)
                i += 1
                continue

            # 提問者（人名 + 時間）
            qm = QTIME_RE.match(text)
            if qm:
                state["questioner"] = _normalize_spaces(qm.group("name"))
                state["qtime"] = qm.group("time").strip()
                start_card("question", state["questioner"], state["qtime"])
                i += 1
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
                            i += 1
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
                i += 1
                continue

            # 一般內文（縮排=新段落；否則接續）
            add_line(text, indented)
            i += 1

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

        # 依 (年, 月) 分組（跨年度 PDF 如 2025-11～2026-03 必須分開）
        by_month: Dict[Tuple[int, int], List[Dict]] = {}
        for sec in sections:
            year, month, _day = sec["date"]
            by_month.setdefault((year, month), []).append(sec)

        chapters: List[Chapter] = []
        for offset, (year, month) in enumerate(sorted(by_month.keys())):
            index = start_index + 1 + offset
            month_sections = by_month[(year, month)]
            # 同一月份內依（日期, 來源）排序：時間先後；官网/贴吧 先於 微信公众号
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
