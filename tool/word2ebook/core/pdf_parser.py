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

# Page counters appear in two forms in the source PDFs:
#   * ``1409 / 2379`` — absolute page within the big merged book (most days)
#   * ``39``          — bare per-session counter at the bottom (e.g. 2025-06-12
#                       and some Nov–Mar stretches). These sit between the last
#                       body line of page N and the first line of page N+1, so
#                       if kept they glue into words (菩 + 39 + 萨 → 菩39萨).
PAGE_RE = re.compile(r"^(?:\d+\s*/\s*\d+|\d{1,4})$")
# Year token allows OCR CJK digits (Tai师父202六年2月7日).
DAY_RE = re.compile(
    r"Tai\s*师父\s*(20[\d零〇一二三四五六七八九]{2})\s*年\s*"
    r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号號]"
)
_YEAR_DIGIT = str.maketrans("零〇一二三四五六七八九", "00123456789")
TODAY_IS_DATE_RE = re.compile(
    r"今天是\s*(?:(20[\d零〇一二三四五六七八九]{2})\s*年\s*)?"
    r"(\d{1,2})\s*月\s*(\d{1,2})\s*[号日號]"
)
SHIFU_RE = re.compile(r"^师父说[：:]")
# 「Taiguanglin：」為回答標記；少數 PDF 抽字遺失冒號（2025-08-08 官网 3、/4、），
# 僅剩裸「Taiguanglin」獨立一行，同樣視為回答標記。
ANSWER_RE = re.compile(r"^Taiguanglin(?:[：:]|\s*$)")
_ANSWER_STRIP_RE = re.compile(r"^Taiguanglin(?:[：:]\s*|\s*$)")
# 提問者時間：貼吧多為「YYYY-MM-DD HH:MM」；微信公眾號後台常見「HH:MM:SS」
# （2025-11-10 / 11-11），兩者皆須辨識，否則整段會被併進開場 <p>。
QTIME_RE = re.compile(
    r"^(?P<name>.{1,40}?)[：:]\s*(?P<time>"
    r"(?:20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}"
    r"|\d{1,2}:\d{2}(?::\d{2})?)"
    r")\s*$"
)
# Trailing `：，` is a missing timestamp (2026-01-06 微信「莲舟曲：，」).
NAMECOLON_RE = re.compile(r"^(?P<name>.{1,40}?)[：:]\s*[，,、.。；;]?\s*$")
# 貼吧偶發「名字 時間」（空格分隔、無冒號；2025-07-07 貼吧用户_58NtK16）。
QTIME_SPACE_RE = re.compile(
    r"^(?P<name>.{1,40}?)\s+(?P<time>"
    r"(?:20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}"
    r"|\d{1,2}:\d{2}(?::\d{2})?)"
    r")\s*$"
)
# 微信暱稱偶發以 !／！ 收尾（如「咩咩!」），無冒號
NAMEBANG_RE = re.compile(r"^(?P<name>.{1,40}?)[!！]\s*$")
BARETIME_RE = re.compile(
    r"^(?:20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}"
    r"|\d{1,2}:\d{2}(?::\d{2})?)$"
)
# Arabic 1、 / 问题2、, Chinese 问题二、, and bare 一、…九、 (not 十、 —
# that is often a wrapped「二十、三十分钟」). 2026-02-02 官网 guangTz Q2 is 二、;
# 2025-12-11 微信 缘起尘微 Q2 is 问题二、.
# Do not treat Tai's answer enumerators「第一，」「第二，」as question openers:
# optional「第」+ Chinese numeral + fullwidth comma is spoken listing, not 一、.
NUM_RE = re.compile(
    r"^(?:"
    r"(?:问题|問題|问|問)?\s*\d+\s*[、.，,)）]"
    r"|(?:问题|問題|问|問)\s*[一二三四五六七八九]\s*[、.]"
    r"|(?:问题|問題|问|問)\s*[一二三四五六七八九十\d]+\s*[：:]"
    r"|[一二三四五六七八九]\s*[、.]"
    r"|第[一二三四五六七八九十百\d]+[、.]"
    r")"
)
# Tai/PDF restatement of a later sub-question dumped into the previous answer
# (2026-02-02 枫红：「第二个问题是，腰容易塌…」). Distinct from Tai answering
# 「第二个问题，…」 / 「第二个问题脑梗…」(no 是，).
SUBQ_RESTATE_RE = re.compile(
    r"^第[二三四五六七八九十百\d]+个问题是[，,]"
)
# Same dump without「是，」: 「第二个问题，看了您的书后…」(一缕思情),
# 「第二个问题 家族里面…」(Yue), 「二是关于锻炼」(guangtz), 「②能否先度…」.
# Ambiguous vs Tai answering「第二个问题，福报够…」— only split when the
# current answer already has body and the next opener is Taiguanglin.
AMBIGUOUS_SUBQ_RE = re.compile(
    r"^(?:"
    r"第[二三四五六七八九十百\d]+个问题(?:[，,、]|\s+|(?=[\u4e00-\u9fff]))"
    r"|[一二三四五六七八九]是"
    r"|[①②③④⑤⑥⑦⑧⑨⑩]"
    r")"
)
# Unnumbered question body dumped into the previous answer (2025-11-10 官网):
# 觉非「最后一个不是问题…加持力」、牧羊少年「第二件事情…被人打断」、
# 彩虹糖「另外想请教师父，闭关…」、yuanjue777「还有我现在刚开始练盘腿」。
# Same split guard as AMBIGUOUS_SUBQ: only when the current answer already has
# body and the next opener is Taiguanglin.
DUMPED_FOLLOWUP_BODY_RE = re.compile(
    r"^(?:"
    r"最后一个不是问题"
    r"|第二件事情"
    r"|另外想请教师父"
    r"|还有我现在"
    r")"
)
# 音檔有問答但 PDF 未收錄原提問文字（2025-06-09「答案同上」／06-10「未找到原提问」）。
MISSING_Q_MARKER_RE = re.compile(r"^(?:未找到原提[问問]|原[问問]题未收录|原問題未收錄)")
ANSWER_SAME_AS_ABOVE_RE = re.compile(r"^下一个问题[，,]?\s*答案(?:还是和上边|還是和上邊|同上)")
# Wrapped nickname fragment like「(十念)：」after「言午」(2025-07-08 微信).
# preclean strips the leading 「(」, leaving「十念)：」.
WRAPPED_NAME_FRAGMENT_RE = re.compile(r"^[^\s：:]{1,8}[）)][：:]\s*$")
CIRCLED_OPEN_RE = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩]")
SEP_RE = re.compile(r"^[—\-－_]{6,}$")
LEAD_DASH_RE = re.compile(r"^([—\-－]{6,})(.*)$")
LONE_COLON_RE = re.compile(r"^[：:]\s*$")
# Separator then ``：师父好…`` on one line (2026-03-03 微信 月亮).
LEADING_COLON_BODY_RE = re.compile(r"^[：:]\s*(?P<body>.+)$")
# Greeting-shaped labels must not be read as nicknames when splitting
# ``顶礼Tai师父：正文``.
GREETING_NAME_RE = re.compile(
    r"^(?:顶礼|师父好|师父您好|师父吉祥|请问|感恩|Tai师父|Tai师)"
)
# Nameless post after a separator (2026-03-03 / 03-07 微信 Ｃｑｙ).
QBODY_OPEN_RE = re.compile(
    r"^(?:顶礼|师父好|师父您好|师父吉祥|Tai师父好|Tai师好|"
    r"Tai师父[，,！!]|"
    r"请问|感恩师父|感恩Tai)"
)
# Recover empty questioner from Tai's following opening.
# Do not treat topic restatements (「要看前世和未来」) as nicknames.
NEXT_Q_NAME_RE = re.compile(
    r"^(?:还有)?下一个问题[，,]?\s*"
    r"(?:第?\d+楼[，,]?\s*)?"
    r"(?P<name>.+?)"
    r"(?:[，,]|这位|这个是)"
)
TOPIC_RECOVERED_NAME_RE = re.compile(
    r"^(?:要看|要问|如何|怎么|怎样|关于|是否|如果|因为|修到|"
    r"想问|这是|这个|那个|就是|未来|前世)"
)
# PDF Symbol／裝飾字型常被抽成純 ASCII 標點行（「" # $ % & … +：」）
PDF_SYMBOL_JUNK_RE = re.compile(
    r"""^[\s\"#\$%&'\(\)\*\+,\-\./:;<=>\?@\[\\\]\^_`\{\|\}~！：]+$"""
)
# 符號字型殘渣黏在下一句開頭（2025-12-11 微信咩咩回答：「+，请问一下读…」）
LEADING_PDF_SYMBOL_JUNK_RE = re.compile(
    r"""^[\s\"#\$%&'\(\)\*\+,\-\./:;<=>\?@\[\\\]\^_`\{\|\}~！：，、]+"""
)

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


def _parse_year_token(token: str) -> int:
    """``2026`` or OCR ``202六`` → 2026."""
    return int(token.translate(_YEAR_DIGIT))


def _date_from_day_match(m: re.Match) -> Tuple[int, int, int]:
    return (_parse_year_token(m.group(1)), int(m.group(2)), int(m.group(3)))


def _parse_session_date(
    text: str, default_year: Optional[int]
) -> Optional[Tuple[int, int, int]]:
    """Date at the first「今天是…M月D号」in an opening blob (not later 到了7月8号)."""
    m = TODAY_IS_DATE_RE.search(_normalize_spaces(text or ""))
    if not m:
        return None
    if m.group(1):
        year = _parse_year_token(m.group(1))
    elif default_year is not None:
        year = default_year
    else:
        return None
    return (year, int(m.group(2)), int(m.group(3)))


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
    return _plausible_questioner_label(s)


def _strip_questioner_label(s: str) -> str:
    """去掉暱稱尾端的 ：/!／空白。"""
    return re.sub(r"[!！：:\s]+$", "", (s or "").strip())


def _is_ellipsis_questioner_name(s: str) -> bool:
    """Nickname that is only dots / ideographic periods.

    ``。。`` is 2026-02-02 官网 23楼; a single ``。`` is 2026-02-05 微信
    (Tai:「这个人的名字是句号」).
    """
    core = _strip_questioner_label(s)
    return bool(re.fullmatch(r"[。．]+", core or ""))


def _is_digit_questioner_name(s: str) -> bool:
    """Numeric nickname such as ``13020466664`` or ``57`` (57楼), not ``1、``."""
    core = _strip_questioner_label(s)
    return bool(re.fullmatch(r"\d{2,16}", core or ""))


def _plausible_questioner_label(s: str) -> bool:
    """是否像提問者標籤（可無冒號，或尾隨 !／！）。

    例：``咩咩``、``咩咩!``、``无明萤火：`` 的 name 部分。
    """
    core = _strip_questioner_label(s)
    if not core or len(core) > 16:
        return False
    if ANSWER_RE.match(s) or s.startswith("师父说") or NUM_RE.match(s):
        return False
    if _is_ellipsis_questioner_name(s) or _is_digit_questioner_name(s):
        return True
    # 句子標點（不含 !，因暱稱可用 !）
    if re.search(r"[。？，；,;]", core):
        return False
    # 至少要有漢字或字母（含全形 Ｃｑｙ），排除純符號
    if not re.search(r"[\u4e00-\u9fffA-Za-z\uFF21-\uFF3A\uFF41-\uFF5A]", core):
        return False
    return True


def _looks_like_question_body(text: str) -> bool:
    """Indented post after a separator that lost its nickname line."""
    t = (text or "").strip()
    if not t or t.startswith("今天是") or t.startswith("师父说"):
        return False
    if ANSWER_RE.match(t) or SEP_RE.match(t):
        return False
    return bool(QBODY_OPEN_RE.match(t))


def _split_glued_name_body(text: str):
    """``名字：正文`` on one line (2025-11-13 官网 我空法空空亦空).

    Returns ``(name, body)`` or ``None``. Timestamp lines and name-only
    ``名字：`` / ``名字：，`` stay with QTIME / NAMECOLON.
    """
    t = (text or "").strip()
    if not t or QTIME_RE.match(t) or NAMECOLON_RE.match(t):
        return None
    if ANSWER_RE.match(t) or t.startswith("师父说"):
        return None
    m = re.match(r"^(?P<name>.{1,40}?)[：:]\s*(?P<body>.+)$", t)
    if not m:
        return None
    name = _normalize_spaces(m.group("name"))
    body = re.sub(r"^[，,、.。；;]+", "", (m.group("body") or "").strip()).strip()
    if not name or not body or BARETIME_RE.match(body):
        return None
    if GREETING_NAME_RE.match(name) or not _plausible_questioner_label(name):
        return None
    if "师父说" in name or "音频" in name or "（" in name or "(" in name:
        return None
    if body.startswith("今天是"):
        return None
    if not re.search(r"[\u4e00-\u9fffA-Za-z]", body):
        return None
    return name, body


def _plausible_recovered_name(name: str) -> bool:
    n = _normalize_spaces(name or "")
    if not n or len(n) > 16:
        return False
    if n.startswith(("就是", "你的", "这个", "那位", "这位")):
        return False
    if GREETING_NAME_RE.match(n) or TOPIC_RECOVERED_NAME_RE.match(n):
        return False
    if "师父说" in n or "音频" in n or "（" in n or "(" in n:
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z\uFF21-\uFF3A\uFF41-\uFF5A]", n))


def _recover_questioner_from_following_answer(
    lines: List[Tuple[float, str]], i: int
) -> str:
    """Peek the next ``Taiguanglin：`` opening for a named 下一个问题 cue."""
    opening = ""
    for j in range(i + 1, min(i + 80, len(lines))):
        t = lines[j][1]
        if SEP_RE.match(t) or DAY_RE.search(t):
            break
        if not ANSWER_RE.match(t):
            continue
        after = _ANSWER_STRIP_RE.sub("", t)
        parts = [after]
        for k in range(j + 1, min(j + 20, len(lines))):
            t2 = lines[k][1]
            if _is_structural_line(t2) or ANSWER_RE.match(t2):
                break
            parts.append(t2)
        opening = _normalize_spaces("".join(parts))
        break
    if not opening:
        return ""
    m = NEXT_Q_NAME_RE.match(opening)
    if not m:
        return ""
    name = _normalize_spaces(m.group("name") or "")
    return name if _plausible_recovered_name(name) else ""


def _strip_leading_pdf_symbol_junk(text: str) -> str:
    """去掉行首的 PDF Symbol 殘渣，留下後面的正文。

    純標點行由 ``_is_pdf_symbol_junk`` 丟棄；這裡處理「+，请问一下…」這類
    殘渣已經黏上漢字的行。編號子問題（``1、`` / ``问题二、``）不動。
    """
    t = (text or "").strip()
    if not t:
        return t
    if (
        NUM_RE.match(t)
        or SUBQ_RESTATE_RE.match(t)
        or AMBIGUOUS_SUBQ_RE.match(t)
        or DUMPED_FOLLOWUP_BODY_RE.match(t)
    ):
        return t
    # 負數／正數的符號（如 -273.15）不是 PDF Symbol 殘渣，不可剝除。
    if re.match(r"^[-−+]\s*\d", t):
        return t
    stripped = LEADING_PDF_SYMBOL_JUNK_RE.sub("", t, count=1).strip()
    if stripped and stripped != t and re.search(r"[\u4e00-\u9fffA-Za-z]", stripped):
        return stripped
    return t


def _is_pdf_symbol_junk(text: str) -> bool:
    """PDF 裝飾／Symbol 字型抽出的純標點行（應丟棄）。

    單獨的 ``：`` 要保留（供「M」+「：」重組成提問者）；``+：`` 這類
    無漢字/字母的假冒號行則丟棄。
    """
    t = (text or "").strip()
    if not t:
        return False
    if LONE_COLON_RE.match(t):
        return False
    if PDF_SYMBOL_JUNK_RE.match(t) and not (
        _is_ellipsis_questioner_name(t) or _is_digit_questioner_name(t)
    ):
        return True
    m = NAMECOLON_RE.match(t)
    if m and not re.search(r"[\u4e00-\u9fffA-Za-z]", m.group("name") or ""):
        if _is_ellipsis_questioner_name(t) or _is_digit_questioner_name(t):
            return False
        return True
    return False


def _is_emoji_or_symbol_name(name: str) -> bool:
    """QTIME 抽出的 name 是否像 emoji／符號（應改用上一行顯示名）。"""
    core = _strip_questioner_label(name)
    if not core:
        return True
    # 沒有兩個以上連續漢字/字母 → 多半是 emoji 或單符號
    if re.search(r"[\u4e00-\u9fffA-Za-z]{2,}", core):
        return False
    return True


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
    if m and _plausible_questioner_label(m.group("name")):
        return True
    bang = NAMEBANG_RE.match(nxt)
    if bang and _plausible_questioner_label(bang.group("name")):
        return True
    if LONE_COLON_RE.match(nxt) or LEADING_COLON_BODY_RE.match(nxt):
        return True
    if _looks_like_question_body(nxt) or _split_glued_name_body(nxt):
        return True
    return _plausible_questioner_label(nxt)


def _is_subquestion_line(text: str) -> bool:
    """Numbered sub-question opener: ``1、`` / ``二、`` / ``问题二、`` / ``第二个问题是，`` / dumped ``第二个问题，``."""
    t = (text or "").strip()
    return bool(
        NUM_RE.match(t) or SUBQ_RESTATE_RE.match(t) or AMBIGUOUS_SUBQ_RE.match(t)
    )


def _is_ambiguous_dumped_subq(text: str) -> bool:
    """Dumped Q2 without a unique marker (not ``1、`` / ``第二个问题是，``)."""
    t = (text or "").strip()
    if NUM_RE.match(t) or SUBQ_RESTATE_RE.match(t):
        return False
    return bool(AMBIGUOUS_SUBQ_RE.match(t))


def _is_dumped_followup_body(text: str) -> bool:
    """Unnumbered dumped question body (加持力 / 被人打断 / 闭关 / 盘腿)."""
    return bool(DUMPED_FOLLOWUP_BODY_RE.match((text or "").strip()))


def _dumped_nameless_question_para(
    lines: List[Tuple[float, str]], i: int
) -> Optional[str]:
    """Full paragraph (line + wrapped continuation) if it reads as a nameless
    question dumped into the previous answer, else ``None``.

    2025-07-07 微信 腹股沟 spans 3 lines with ？ on the last wrapped line, so
    the ？-ending check must run on the joined paragraph, not the raw line.
    """
    t0 = (lines[i][1] or "").strip()
    if not t0:
        return None
    if _is_structural_line(t0) or _is_subquestion_line(t0):
        return None
    parts = [lines[i][1]]
    for j in range(i + 1, min(i + 40, len(lines))):
        x0, t = lines[j]
        if _is_img_marker(t):
            continue
        if (
            x0 > INDENT_THRESHOLD
            or ANSWER_RE.match(t)
            or _is_structural_line(t)
            or _is_subquestion_line(t)
        ):
            break
        parts.append(t)
    para = "".join(parts).strip()
    if not re.search(r"[？?]\s*$", para):
        return None
    return para


def _nameless_question_followed_by_answer(
    lines: List[Tuple[float, str]], i: int
) -> bool:
    """True when a nameless ？-line inside an answer is followed only by
    wrapped continuation lines and then ``Taiguanglin：`` (its own answer).

    Any new indented paragraph in between (another dumped question body,
    another questioner…) means this ？-line is ordinary answer rhetoric and
    must stay inside the answer (2025-11-10 官网 觉非加持力 dump; 12-08
    TaiZhuYue ①②③ list follow-up).
    """
    for j in range(i + 1, min(i + 50, len(lines))):
        x0, t = lines[j]
        if _is_img_marker(t):
            continue
        if ANSWER_RE.match(t):
            return True
        if x0 > INDENT_THRESHOLD:
            return False
        if _is_structural_line(t) or _is_subquestion_line(t):
            return False
    return False


def _following_is_answerer(lines: List[Tuple[float, str]], i: int) -> bool:
    """True when the next structural opener after ``lines[i]`` is ``Taiguanglin：``.

    Wrapped body of a dumped question is skipped. Another numbered opener,
    separator, or new questioner means this line is not a swallowed turn.
    """
    for j in range(i + 1, min(i + 50, len(lines))):
        t = lines[j][1]
        if _is_img_marker(t):
            continue
        if ANSWER_RE.match(t):
            return True
        if _is_structural_line(t) or _is_subquestion_line(t):
            return False
    return False


def _answer_expects_wrap(state: Dict) -> bool:
    """Current answer's last fragment does not end a sentence (line-wrap)."""
    card = state.get("card")
    if not card or card.get("kind") != "answer":
        return False
    buf = "".join(state.get("para") or [])
    if buf:
        return not _ends_sentence(buf)
    paras = _text_paras_only(card.get("paras") or [])
    return bool(paras) and not _ends_sentence(paras[-1])


def _answer_has_circled_para(card: Dict, state: Dict) -> bool:
    """True if this answer already contains a ①②③ listing paragraph."""
    paras = list(card.get("paras") or [])
    buf = "".join(state.get("para") or [])
    if buf:
        paras = paras + [buf]
    for p in paras:
        if _is_img_marker(p):
            continue
        if CIRCLED_OPEN_RE.match((p or "").strip()):
            return True
    return False


def _should_split_ambiguous_subq(
    state: Dict, lines: List[Tuple[float, str]], i: int
) -> bool:
    """Split dumped Q2 out of an answer only when Tai's Q1 answer already started
    and a new ``Taiguanglin：`` follows this paragraph (the real Q2 answer).

    Circled ``③`` at the end of a ①②③ list (2025-12-08 TaiZhuYue) is followed
    by more question body then ``Taiguanglin：`` — keep it in the answer.
    """
    card = state.get("card")
    if not card or card.get("kind") != "answer":
        return True
    has_body = bool(_text_paras_only(card.get("paras") or [])) or bool(
        state.get("para")
    )
    if not has_body:
        return False
    text = (lines[i][1] if i < len(lines) else "") or ""
    if CIRCLED_OPEN_RE.match(text.strip()) and _answer_has_circled_para(card, state):
        return False
    return _following_is_answerer(lines, i)


def _is_img_marker(text: str) -> bool:
    return text.startswith(IMG_MARKER_PREFIX)


def _img_marker_path(text: str) -> str:
    return text[len(IMG_MARKER_PREFIX):]


def make_img_marker(relative_path: str) -> str:
    """測試／抽取共用的圖片標記字串。"""
    return f"{IMG_MARKER_PREFIX}{relative_path}"


def _is_glyph_fragment(text: str) -> bool:
    """是否為「垂直排／逐字抽出」造成的極短片段（單字或字+標點）。

    PDF 在圖片旁常把「師父您。感恩師父。」拆成一字一行；合併後才不會變成
    一堆 ``<p>师</p><p>父</p>…``。
    """
    t = (text or "").strip()
    if not t or len(t) > 2:
        return False
    if NUM_RE.match(t) or ANSWER_RE.match(t) or SEP_RE.match(t):
        return False
    if _is_pdf_symbol_junk(t):
        return False
    if NAMECOLON_RE.match(t) or NAMEBANG_RE.match(t) or LONE_COLON_RE.match(t) or QTIME_RE.match(t):
        return False
    return bool(
        re.fullmatch(
            r"[\u4e00-\u9fffA-Za-z0-9。？！，、；：…—\-·\.!?,;:\"'“”‘’（）()\[\]【】]{1,2}",
            t,
        )
    )


def _ends_sentence(text: str) -> bool:
    s = (text or "").rstrip()
    return bool(s) and s[-1] in "。？！…!?」』\""


def _text_paras_only(paras: List[str]) -> List[str]:
    return [p for p in paras if not _is_img_marker(p)]


def _coalesce_card_paras(paras: List[str]) -> List[str]:
    """合併「被圖片打斷」的未完成句子；圖片改掛在合併後文字之後。

    例：``['…稍', IMG, '微带点…吗?']`` → ``['…稍微带点…吗?', IMG]``

    沒有圖片夾在中間時，不合併相鄰文字段（縮排造成的正常分段要保留）。
    """
    if not paras:
        return paras
    out: List[str] = []
    i = 0
    n = len(paras)
    while i < n:
        if _is_img_marker(paras[i]):
            out.append(paras[i])
            i += 1
            continue
        text = paras[i]
        i += 1
        pending_imgs: List[str] = []
        while i < n:
            if _is_img_marker(paras[i]):
                pending_imgs.append(paras[i])
                i += 1
                continue
            # 沒夾圖片 → 保留原本段落邊界
            if not pending_imgs:
                break
            nxt = paras[i]
            if NUM_RE.match(nxt):
                break
            # 完整句後接一般新段 → 保留順序（文字、圖、下一段）
            if _ends_sentence(text) and not _is_glyph_fragment(nxt):
                break
            text += nxt
            i += 1
        out.append(text)
        out.extend(pending_imgs)
    return out


def _render_content_piece(piece: str, *, text_tag: str) -> str:
    """卡片內一段：一般文字 → ``text_tag``；圖片標記 → ``<img>``。"""
    if _is_img_marker(piece):
        rel = _img_marker_path(piece)
        return f'<img src="{rel}" alt="Image">'
    return f"<{text_tag}>{piece}</{text_tag}>"


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
    if NAMEBANG_RE.match(text) or LONE_COLON_RE.match(text):
        return True
    if _split_glued_name_body(text) or LEADING_COLON_BODY_RE.match(text):
        return True
    if DAY_RE.search(text):
        return True
    return False


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
            if _is_pdf_symbol_junk(t):
                continue
            t = _strip_leading_pdf_symbol_junk(t)
            if not t or _is_pdf_symbol_junk(t):
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

        # 階段 4：合併「一字一行」的垂直／碎片段（常見於圖片旁的 OCR 抽出）
        return self._merge_glyph_fragments(result)

    def _merge_glyph_fragments(
        self, lines: List[Tuple[float, str]]
    ) -> List[Tuple[float, str]]:
        """把連續極短行併成一行，避免卡片內出現 ``<p>师</p><p>父</p>…``。"""
        out: List[Tuple[float, str]] = []
        buf_x: Optional[float] = None
        buf: List[str] = []

        def flush() -> None:
            nonlocal buf_x, buf
            if buf:
                out.append((buf_x if buf_x is not None else 0.0, "".join(buf)))
            buf_x = None
            buf = []

        for x0, t in lines:
            if _is_img_marker(t) or _is_structural_line(t):
                flush()
                out.append((x0, t))
                continue
            if _is_glyph_fragment(t):
                if buf_x is None:
                    buf_x = x0
                buf.append(t)
                continue
            flush()
            out.append((x0, t))
        flush()
        return out

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
            card["paras"] = _coalesce_card_paras(card["paras"])
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

            # 圖片：留在當前卡片內（不結束卡片），避免後半句變成卡片外的孤立 <p>
            if _is_img_marker(text):
                ensure_section()
                if state["card"] is not None:
                    finish_para()
                    state["card"]["paras"].append(text)
                elif state["section"] is not None:
                    rel = _img_marker_path(text)
                    state["section"]["blocks"].append(
                        f'<img src="{rel}" alt="Image">'
                    )
                i += 1
                continue

            indented = x0 > INDENT_THRESHOLD

            # 新的一天（同一日期的續錄音訊不重設來源，避免被誤標成贴吧）
            # Header may be glued onto the previous closing sentence.
            m_day = DAY_RE.search(text)
            if m_day:
                before = text[: m_day.start()].strip()
                if before:
                    add_line(before, indented)
                finish_card()
                new_date = _date_from_day_match(m_day)
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
            # 日期變了也要切開（2026-02-07 黏在 2/6 段落下、沒有獨立 Tai 日標）。
            if re.match(r"^今天是", text):
                blob_parts = [text]
                j = i + 1
                while j < n_lines:
                    _x1, t1 = lines[j]
                    if _is_structural_line(t1):
                        break
                    blob_parts.append(t1)
                    j += 1
                blob = "".join(blob_parts)
                default_year = state["date"][0] if state["date"] else None
                parsed = _parse_session_date(blob, default_year)
                detected = _detect_source_from_shifu(blob)
                date_changed = parsed is not None and parsed != state["date"]
                source_switch = detected is not None and detected != state["source"]
                opening_slot = state["card"] is None or state["card"]["kind"] in (
                    "answer",
                    "paragraph",
                )
                use_as_opening = (
                    state["card"] is None
                    and state["questioner"] is None
                    and parsed is not None
                ) or (opening_slot and detected is not None and (date_changed or source_switch))
                if use_as_opening:
                    finish_card()
                    if date_changed:
                        state["date"] = parsed
                        if detected is None:
                            state["source"] = SOURCE_TIEBA
                        state["questioner"] = None
                        state["qtime"] = None
                    if detected is not None:
                        state["source"] = detected
                    elif state["source"] == SOURCE_TIEBA and not any(
                        s["date"] == state["date"] for s in sections
                    ):
                        state["source"] = SOURCE_GUANWANG
                    start_card("paragraph")
                    # 與「师父说」開場相同：允許緊接的無時間提問者（如 winnie：）成卡，
                    # 否則會被併進開場 <p>（2025-11-15 官网）。
                    state["card"]["shifu"] = True
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
                default_year = state["date"][0] if state["date"] else None
                parsed = _parse_session_date(blob, default_year)
                if parsed is not None and parsed != state["date"]:
                    state["date"] = parsed
                    state["source"] = SOURCE_TIEBA
                    state["questioner"] = None
                    state["qtime"] = None
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
                after = _ANSWER_STRIP_RE.sub("", text)
                start_card("answer")
                if after:
                    add_line(after, indented=True)
                i += 1
                continue

            # 「（贴下回复）」：貼吧「樓下回覆」標記，接在回答尾端（保留於回答文字），
            # 其後是下一位提問者（如 2025-07-08 貼吧 心画世间 回答後接 净红）。
            if text in ("（贴下回复）", "（貼下回復）", "贴下回复", "貼下回復"):
                if state["card"] is not None and state["card"]["kind"] == "answer":
                    add_line(text, indented=False)
                finish_card()
                i += 1
                continue

            # 音檔有問答但 PDF 未收錄原提問文字：切出佔位問題卡（2025-06 貼吧）。
            if MISSING_Q_MARKER_RE.match(text):
                start_card("question", "", "")
                add_line(text, indented=True)
                i += 1
                continue
            if ANSWER_SAME_AS_ABOVE_RE.match(text):
                start_card("question", "", "")
                add_line("（原问题未收录，答案为「和上边一样」）", indented=True)
                start_card("answer")
                add_line(text, indented=True)
                i += 1
                continue

            # 折行名字的殘片（如「言午」之後的「(十念)：」），丟棄避免併入問題正文。
            if (
                WRAPPED_NAME_FRAGMENT_RE.match(text)
                and state["card"] is not None
                and state["card"]["kind"] == "question"
                and not _text_paras_only(state["card"].get("paras") or [])
            ):
                i += 1
                continue

            # 提問者（人名 + 時間）
            qm = QTIME_RE.match(text)
            if not qm:
                qm = QTIME_SPACE_RE.match(text)
            if qm:
                name = _normalize_spaces(qm.group("name"))
                qtime = qm.group("time").strip()
                # 貼吧「XXX 发表于 time」是樓層標頭而非提問者（提問者已由前一行
                # 「名字：」設定），應視為問題正文的開頭段落。
                if "发表于" in name or "發表於" in name:
                    add_line(text, indented)
                    i += 1
                    continue
                card = state["card"]
                # 上一張若是單行顯示名段落（如「咩咩」），而本行 name 是 emoji
                if (
                    card
                    and card["kind"] == "paragraph"
                    and len(card.get("paras") or []) == 1
                    and _plausible_questioner_label(card["paras"][0])
                    and _is_emoji_or_symbol_name(name)
                ):
                    name = _strip_questioner_label(card["paras"][0])
                    state["card"] = None
                # 或：已用純暱稱開了空問題卡，本行是 emoji+時間 → 只補時間
                elif (
                    card
                    and card["kind"] == "question"
                    and not (card.get("paras"))
                    and card.get("name")
                    and _is_emoji_or_symbol_name(name)
                ):
                    state["qtime"] = qtime
                    card["time"] = qtime
                    i += 1
                    continue
                state["questioner"] = name
                state["qtime"] = qtime
                start_card("question", state["questioner"], state["qtime"])
                i += 1
                continue

            # 提問者（人名，無時間）：很多貼吧/公眾號的留言沒有時間戳，
            # 名字上方一定有分隔線（→ card 為 None），或緊接在來源開場之後
            # （→ card 為「师父说」／裸「今天是」開場段落，shifu=True）。
            # 亦接受尾隨 !／！ 或純暱稱（「咩咩!」「咩咩」）。
            # 其餘以冒號結尾的行（例如句子中的「想請教三個問題：」）發生在
            # 問題/回答卡片內，視為內文延續，不誤判。
            if x0 < INDENT_THRESHOLD and not indented:
                nc = NAMECOLON_RE.match(text)
                bang = NAMEBANG_RE.match(text)
                lone = LONE_COLON_RE.match(text)
                bare = (
                    not nc and not bang and not lone
                    and _plausible_questioner_label(text)
                )
                if nc or bang or lone or bare:
                    card = state["card"]
                    is_section_intro = card is None or (
                        card["kind"] == "paragraph" and card.get("shifu")
                    )
                    # 微信常無分隔線：上一段回答結束後直接接下一暱稱
                    is_after_answer = card is not None and card["kind"] == "answer"
                    # 回答未結束的折行（「祝大家一路顺风，回」+「家过年开心！」）
                    # 不可當成新暱稱。
                    if (
                        is_after_answer
                        and not indented
                        and _answer_expects_wrap(state)
                    ):
                        pass
                    elif is_section_intro or is_after_answer:
                        if nc:
                            name = _normalize_spaces(nc.group("name"))
                        elif bang:
                            name = _normalize_spaces(bang.group("name"))
                        elif bare:
                            name = _normalize_spaces(_strip_questioner_label(text))
                        else:
                            name = ""
                        if name or lone:
                            if not name:
                                name = _recover_questioner_from_following_answer(
                                    lines, i
                                )
                            state["questioner"] = name
                            state["qtime"] = ""
                            start_card("question", name, "")
                            i += 1
                            continue

            # 分隔線後暱稱列缺失：縮排正文 / 裸「：」+正文 / 「名字：正文」黏在一行。
            # 不讀 audio_map；能從下一則 Tai 回答開頭取回暱稱則填上，否則空名。
            if state["card"] is None:
                # 極少數 PDF 會把「提問者：」也縮排（2025-08-07 薛祖宜）。
                # 此時沒有上一張卡片可作為內文，因此冒號結尾的單純暱稱應視為提問者。
                nc = NAMECOLON_RE.match(text)
                if nc and _plausible_questioner_label(nc.group("name")):
                    name = _normalize_spaces(nc.group("name"))
                    state["questioner"] = name
                    state["qtime"] = ""
                    start_card("question", name, "")
                    i += 1
                    continue
                glued = _split_glued_name_body(text)
                lead = LEADING_COLON_BODY_RE.match(text)
                if glued:
                    name, body = glued
                    state["questioner"] = name
                    state["qtime"] = ""
                    start_card("question", name, "")
                    add_line(body, indented=True)
                    i += 1
                    continue
                if LONE_COLON_RE.match(text):
                    name = _recover_questioner_from_following_answer(lines, i)
                    state["questioner"] = name
                    state["qtime"] = ""
                    start_card("question", name, "")
                    i += 1
                    continue
                if lead:
                    name = _recover_questioner_from_following_answer(lines, i)
                    state["questioner"] = name
                    state["qtime"] = ""
                    start_card("question", name, "")
                    add_line(lead.group("body").strip(), indented=True)
                    i += 1
                    continue
                if _looks_like_question_body(text):
                    name = _recover_questioner_from_following_answer(lines, i)
                    state["questioner"] = name
                    state["qtime"] = ""
                    start_card("question", name, "")
                    add_line(text, indented=True)
                    i += 1
                    continue

            # 編號子問題（阿拉伯數字、中文數字、或「第二个问题是，」複述）
            # 非縮排行若為回答未結束的折行（如「六、七秒」＝六到七秒），不可誤判成子問題。
            if _is_subquestion_line(text) and (
                indented
                or (
                    state["card"] is not None
                    and state["card"]["kind"] == "answer"
                    and not _answer_expects_wrap(state)
                )
            ):
                card = state["card"]
                if card is not None and card["kind"] == "question":
                    # 同一位提問者「連續」的編號子問題（中間沒有師父回答／分隔線／
                    # 新提問者）視為同一個多段式問題，併進同一張問題卡片；每個編號各自
                    # 成段（question-text）。引言（如「頂禮師父／續問：」）也留在同卡。
                    add_line(text, indented=True)
                    card["numbered"] = True
                    i += 1
                    continue
                # 編號問題出現在回答／敘述段落之後或尚無卡片 → 是新的一輪提問。
                # 「第二个问题，…」「二是…」「②…」與師父回答開頭同形，只在
                # 上一則回答已有正文、且下一個結構行是 Taiguanglin 時切開。
                if (
                    card is not None
                    and card["kind"] == "answer"
                    and _is_ambiguous_dumped_subq(text)
                    and not _should_split_ambiguous_subq(state, lines, i)
                ):
                    pass
                else:
                    start_card("question", state["questioner"], state["qtime"])
                    add_line(text, indented=True)
                    state["card"]["numbered"] = True
                    i += 1
                    continue

            # 無編號、被塞進上一則回答的後續提問正文（加持力／被人打斷／閉關／盤腿）
            if (
                _is_dumped_followup_body(text)
                and state["card"] is not None
                and state["card"]["kind"] == "answer"
                and _should_split_ambiguous_subq(state, lines, i)
            ):
                start_card("question", state["questioner"], state["qtime"])
                add_line(text, indented=True)
                i += 1
                continue

            # Tai 複述提問（「昨天还有人问…？」）後，以未標記的回答直接接續
            # （無新的 Taiguanglin 標記）。—— 這其實是同一則答案的延續（師父以
            # 「昨天还有人问」起頭自問自答），不是新提問，故不切卡，留在原答案內。

            # 無暱稱、以問號結尾的匿名提問正文（2025-07 腹股溝／李光耀／中東核戰…
            # 被併進上一則回答）。PDF 中該段之後緊接 Taiguanglin 回答 → 切為新問題卡。
            # 圈號 ①②③ 清單後的追問、以及其後還有其他問題行的 ？-段，留在原回答。
            card = state["card"]
            if (
                _dumped_nameless_question_para(lines, i)
                and card is not None
                and card["kind"] == "answer"
                and (
                    bool(_text_paras_only(card.get("paras") or []))
                    or bool(state.get("para"))
                )
                and not _answer_has_circled_para(card, state)
                and _nameless_question_followed_by_answer(lines, i)
            ):
                # 匿名／被併進回答的提問，提問者空白時「往上追溯」到
                # 上一個有名字的提問者（此段即為該提問者的後續問題）。
                start_card("question", state["questioner"] or "", "")
                add_line(text, indented=True)
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

        text_paras = _text_paras_only(paras)

        if kind == "paragraph":
            return "\n".join(
                _render_content_piece(p, text_tag="p") for p in paras
            )

        if kind == "question":
            name = card["name"] or ""
            time = card["time"] or ""
            joined = " ".join(text_paras)
            qid = self.id_generator.generate_stable_qa_id(name, joined, time, "question")
            time_html = f'<span class="question-time">{time}</span>' if time else ""
            pieces = []
            for p in paras:
                if _is_img_marker(p):
                    pieces.append(f'    <img src="{_img_marker_path(p)}" alt="Image">')
                else:
                    pieces.append(f'    <div class="question-text">{p}</div>')
            text_divs = "\n".join(pieces)
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
            joined = " ".join(text_paras)
            aid = self.id_generator.generate_stable_qa_id(answerer, joined, "", "answer")
            pieces = []
            for p in paras:
                if _is_img_marker(p):
                    pieces.append(f'    <img src="{_img_marker_path(p)}" alt="Image">')
                else:
                    pieces.append(f'    <div class="answer-text">{p}</div>')
            text_divs = "\n".join(pieces)
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
