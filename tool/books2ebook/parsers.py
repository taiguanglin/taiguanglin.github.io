"""各書籍的內容解析器：把 PDF 行轉成統一的區塊（block）串流。

區塊格式（dict）：
  {"kind": "h2"|"h3"|"h4", "text": ...}   標題（進入 TOC）
  {"kind": "para", "text": ...}           一般段落
  {"kind": "strong", "text": ...}         粗體段落
  {"kind": "quote", "text": ...}          引文（經文/詩句）
  {"kind": "label", "text": ...}          小標籤（譯文／注解），不進 TOC
  {"kind": "qa", "qa": {...}}             問答（僅《坐禅之问答录》）
  {"kind": "img", "xref":..., "page":...} 插圖（build 時解析成實際路徑）
"""

import re

_DOT_LEADER_RE = re.compile(r"\.{4,}\s*\d{0,4}\s*$")
_TIME_RE = re.compile(r"[（(](\d{4}-\d{1,2}-\d{1,2})[，,\s]+([\d:]{3,8})[)）]\s*$")
# 提問者暱稱：短、不含標點
_SPEAKER_RE = re.compile(r"^([^：，。？！；、\s()（）]{1,24})：")
_ANSWERER = "Taiguanglin"


def _clean(text):
    """去掉虛線引導與多餘空白；目錄點行直接丟棄（回傳 None）。"""
    if _DOT_LEADER_RE.search(text):
        return None
    text = text.replace("\t", " ")
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _join(a, b):
    """合併被 PDF 換行切斷的兩段文字。"""
    if not a:
        return b
    if re.search(r"[A-Za-z0-9,;:)」]$", a) and re.match(r"^[A-Za-z0-9(「]", b):
        return a + " " + b
    return a + b


class ParseContext:
    """單本書解析時的共同狀態。"""

    def __init__(self, lines_by_page, toc_pages, images_by_page,
                 merge_adjacent_headings=False):
        self.lines_by_page = lines_by_page
        self.toc_pages = toc_pages
        self.images_by_page = images_by_page
        self.blocks = []
        self.seen_xrefs = set()
        self.merge_adjacent_headings = merge_adjacent_headings
        self._last_was_heading_same_level = False

    def heading(self, level, text, space_join=False):
        text = _clean(text)
        if not text or re.fullmatch(r"\d{1,4}", text):
            return
        prev = self.blocks[-1] if self.blocks else None
        if (self.merge_adjacent_headings and self._last_was_heading_same_level
                and prev is not None and prev["kind"] == level):
            joiner = " " if space_join else ""
            prev["text"] = prev["text"] + joiner + text
            return
        self.blocks.append({"kind": level, "text": text})
        self._last_was_heading_same_level = True

    def append(self, kind, text=None, **extra):
        blk = {"kind": kind}
        if text is not None:
            blk["text"] = text
        blk.update(extra)
        self.blocks.append(blk)
        self._last_was_heading_same_level = False

    def append_quote_line(self, text):
        """引文行：連續引文合併為同一區塊（以換行分隔），例如一首詩。"""
        prev = self.blocks[-1] if self.blocks else None
        if prev is not None and prev["kind"] == "quote":
            prev["text"] = prev["text"] + "\n" + text
            return
        self.append("quote", text)

    def add_images_for_page(self, pno):
        for xref, w, h in self.images_by_page.get(pno, []):
            if xref in self.seen_xrefs:
                continue
            self.seen_xrefs.add(xref)
            self.append("img", xref=xref, page=pno, w=w, h=h)
            self._last_was_heading_same_level = False


# ---------------------------------------------------------------------- #
# 共用工具
# ---------------------------------------------------------------------- #

def _iter_pages(ctx, start_after_toc=True):
    for pno in sorted(ctx.lines_by_page):
        if start_after_toc and pno in ctx.toc_pages:
            continue
        yield pno, ctx.lines_by_page[pno]


def _is_indent_start(line, body_left, tol=6.0):
    """以縮排判斷是否為新段落開頭。"""
    return line.x0 > body_left + tol


def _split_qa_time(text):
    m = _TIME_RE.search(text)
    if not m:
        return text, None
    return text[: m.start()].strip(), "%s %s" % (m.group(1), m.group(2))


# ---------------------------------------------------------------------- #
# 01《坐禅》
# ---------------------------------------------------------------------- #

def parse_zuochan(ctx):
    body_left = None
    para = ""

    def flush():
        nonlocal para
        if para.strip():
            ctx.append("para", para.strip())
        para = ""

    for pno, ls in _iter_pages(ctx):
        for line in ls:
            t = _clean(line.text)
            if not t:
                continue
            f, s = line.font, line.size
            if f == "FZYANS_ZHONGJW" and s >= 15.5 and len(t) <= 2:
                continue  # 直式側欄（章名）
            if f == "FZYANS_DAJW" and s >= 15:
                flush()
                ctx.heading("h2", t)
            elif f == "FZYANS_ZHONGJW" and 13.5 <= s <= 14.5:
                flush()
                ctx.heading("h3", t)
            elif f == "FZYANS_XIANJW" and s <= 12.5:
                flush()
                ctx.heading("h4", t)
            elif f == "FZYANS_ZHONGJW" and 11.6 <= s <= 13.4:
                flush()
                if _H4_PAT.match(t):
                    ctx.heading("h4", t)
                else:
                    ctx.append_quote_line(t)
            elif f == "FZBYSK":
                if body_left is None:
                    body_left = line.x0
                else:
                    body_left = min(body_left, line.x0)
                if para.strip() and _is_indent_start(line, body_left):
                    flush()
                para = _join(para, t)
        ctx.add_images_for_page(pno)
    flush()
    return True


# ---------------------------------------------------------------------- #
# 02《坐禅之问答录》
# ---------------------------------------------------------------------- #

def parse_wendalu(ctx):
    para = ""
    qa = None
    qa_text = ""
    cont_left = None
    q_left = None

    def flush_para():
        nonlocal para
        if para.strip():
            ctx.append("para", para.strip())
        para = ""

    def flush_qa():
        nonlocal qa, qa_text
        if qa is not None and (qa.get("qtext") or qa_text.strip()):
            atext, atime = _split_qa_time(qa_text.strip())
            qa["atext"] = atext
            if atime:
                qa["atime"] = atime
            ctx.append("qa", qa=qa)
        qa, qa_text = None, ""

    for pno, ls in _iter_pages(ctx):
        for line in ls:
            t = _clean(line.text)
            if not t:
                continue
            f, s = line.font, line.size
            if f == "FZYANS_DAJW" and s >= 15:
                flush_para()
                flush_qa()
                ctx.heading("h2", t, space_join=True)
            elif f == "FZBYSK" and s <= 9.5:
                flush_para()
                m = _SPEAKER_RE.match(t)
                q_cont = line.x0 if (q_left is None or line.x0 < q_left) else q_left
                indented = line.x0 > q_cont + 4.0
                new_q_left = min(q_left, line.x0) if q_left is not None else line.x0
                if qa is None or (indented and m):
                    body = t[m.end():].strip() if m else t
                    body, qtime = _split_qa_time(body)
                    flush_qa()
                    qa = {
                        "questioner": m.group(1).strip() if m else "",
                        "qtext": body,
                    }
                    if qtime:
                        qa["qtime"] = qtime
                else:
                    body, _t2 = _split_qa_time(t)
                    qa["qtext"] = _join(qa.get("qtext", ""), body)
                q_left = new_q_left
                qa_text = ""
            elif f == "FZHTJW":
                if t.startswith(_ANSWERER + "："):
                    body = t[len(_ANSWERER) + 1:].strip()
                    if qa_text:
                        qa_text += "\n" + body
                    else:
                        flush_para()
                        if qa is None:
                            qa = {"questioner": "", "qtext": ""}
                        qa_text = body
                    cont_left = line.x0 if cont_left is None else min(cont_left, line.x0)
                elif qa is not None:
                    if cont_left is not None and line.x0 > cont_left + 4.0 \
                            and qa_text.strip():
                        qa_text += "\n"
                    qa_text = _join(qa_text, t)
                else:
                    if cont_left is not None and line.x0 > cont_left + 4.0 \
                            and para.strip():
                        flush_para()
                    if cont_left is None:
                        cont_left = line.x0
                    else:
                        cont_left = min(cont_left, line.x0)
                    para = _join(para, t)
            elif f == "FZYANS_ZHONGJW" and s >= 13.5:
                flush_para()
                flush_qa()
                ctx.heading("h2", t)
            else:
                continue
        ctx.add_images_for_page(pno)
    flush_para()
    flush_qa()
    return True


# ---------------------------------------------------------------------- #
# 03《坐禅2·次世代版终极佛法》
# ---------------------------------------------------------------------- #

_H4_PAT = re.compile(r"^（?\d+[）.、．]")
_SHORT_HEAD_MAX = 22


def _zuochan2_h4(t):
    if _H4_PAT.match(t):
        return True
    if len(t) <= _SHORT_HEAD_MAX and not re.search(r"[，。；：,；]$", t):
        return True
    return False


def parse_zuochan2(ctx):
    body_left = None
    para = ""

    def flush():
        nonlocal para
        if para.strip():
            ctx.append("para", para.strip())
        para = ""

    for pno, ls in _iter_pages(ctx):
        for line in ls:
            t = _clean(line.text)
            if not t:
                continue
            f, s = line.font, line.size
            if f == "FZYANS_ZHONGJW" and s <= 11.5:
                continue
            if f == "FZYANS_DAJW" and s >= 17:
                flush()
                ctx.heading("h2", t)
            elif f == "FZYANS_DAJW" and s >= 15:
                if re.match(r"^第\d+\s*节", t):
                    flush()
                    ctx.heading("h3", t)
            elif f == "FZYANS_ZHONGJW" and 13.5 <= s <= 14.5:
                flush()
                ctx.heading("h4", t)
            elif f == "FZYANS_ZHONGJW" and 12.5 <= s <= 13.4:
                flush()
                if _zuochan2_h4(t):
                    ctx.heading("h4", t)
                else:
                    ctx.append_quote_line(t)
            elif f == "FZBYSK":
                if body_left is None:
                    body_left = line.x0
                else:
                    body_left = min(body_left, line.x0)
                if para.strip() and _is_indent_start(line, body_left):
                    flush()
                para = _join(para, t)
        ctx.add_images_for_page(pno)
    flush()
    return True


# ---------------------------------------------------------------------- #
# 04 金刚经·心经讲记
# ---------------------------------------------------------------------- #

def parse_jingang(ctx):
    body_left = None
    para = ""
    quote = ""
    quote_left = None

    def flush():
        nonlocal para, quote, quote_left
        if para.strip():
            ctx.append("para", para.strip())
        if quote.strip():
            ctx.append("quote", quote.strip())
        para, quote = "", ""
        quote_left = None

    for pno, ls in _iter_pages(ctx):
        for line in ls:
            t = _clean(line.text)
            if not t:
                continue
            f, s = line.font, line.size
            if f in ("FZHJJW", "FZLTKHK"):
                continue
            if f == "FZYANS_DAJW" and s >= 15:
                flush()
                ctx.heading("h2", t)
            elif f == "FZLTHBJW":
                flush()
                ctx.append("label", t.rstrip("：:"))
            elif f == "FZSHJW":
                if para.strip():
                    flush()
                # 經文依原書縮排分段
                if quote_left is None:
                    quote_left = line.x0
                else:
                    quote_left = min(quote_left, line.x0)
                if quote.strip() and _is_indent_start(line, quote_left):
                    flush()
                quote = _join(quote, t)
            elif f == "FZHTJW":
                if quote.strip():
                    flush()
                if re.match(r"^\d{1,2}[.．]", t):
                    flush()
                if body_left is None:
                    body_left = line.x0
                else:
                    body_left = min(body_left, line.x0)
                if para.strip() and _is_indent_start(line, body_left):
                    flush()
                para = _join(para, t)
            elif f == "FZBYSK":
                if quote.strip():
                    flush()
                if body_left is None:
                    body_left = line.x0
                else:
                    body_left = min(body_left, line.x0)
                if para.strip() and _is_indent_start(line, body_left):
                    flush()
                para = _join(para, t)
        ctx.add_images_for_page(pno)
    flush()
    return True


# ---------------------------------------------------------------------- #
# 05 圆觉经讲记
# ---------------------------------------------------------------------- #

_LABEL_RE = re.compile(r"(译文|注解|解析|本章大义|原经文)[:：\s]*$")
_XJDU_RE = re.compile(r"^原文精读\s*\d*$")


def parse_yuanjue(ctx):
    para = ""
    quote = ""
    body_left = None
    quote_left = None

    def flush():
        nonlocal para, quote, quote_left
        if para.strip():
            ctx.append("para", para.strip())
        if quote.strip():
            ctx.append("quote", quote.strip())
        para, quote = "", ""
        quote_left = None

    for pno, ls in _iter_pages(ctx):
        for line in ls:
            t = _clean(line.text)
            if not t:
                continue
            f, s = line.font, line.size
            bold = f.startswith("MicrosoftYaHei-Bold")
            if s >= 17 and (f == "KaiTi" or bold):
                flush()
                ctx.heading("h2", t)
                body_left = None
            elif bold and _XJDU_RE.match(t):
                flush()
                ctx.heading("h3", t)
                body_left = None
            elif bold and _LABEL_RE.sub("", t).strip() == "":
                flush()
                label = _LABEL_RE.sub("", t).strip()
                ctx.append("label", label or t.rstrip("：:"))
                body_left = None
            elif f == "KaiTi":
                if para.strip():
                    flush()
                # 經文依原書縮排分段
                if quote_left is None:
                    quote_left = line.x0
                else:
                    quote_left = min(quote_left, line.x0)
                if quote.strip() and _is_indent_start(line, quote_left):
                    flush()
                quote = _join(quote, t)
            elif bold:
                flush()
                ctx.append("strong", t)
            else:
                if quote.strip():
                    flush()
                if re.match(r"^\d{1,2}[.．]", t):
                    flush()
                if body_left is None:
                    body_left = line.x0
                else:
                    body_left = min(body_left, line.x0)
                if para.strip() and _is_indent_start(line, body_left):
                    flush()
                para = _join(para, t)
        ctx.add_images_for_page(pno)
    flush()
    return True


PARSERS = {
    "zuochan": parse_zuochan,
    "wendalu": parse_wendalu,
    "zuochan2": parse_zuochan2,
    "jingang": parse_jingang,
    "yuanjue": parse_yuanjue,
}


def parse_book(parser_key, lines_by_page, toc_pages, images_by_page):
    merge = parser_key == "wendalu"
    ctx = ParseContext(lines_by_page, toc_pages, images_by_page,
                       merge_adjacent_headings=merge)
    ok = PARSERS[parser_key](ctx)
    return ctx.blocks if ok else []
