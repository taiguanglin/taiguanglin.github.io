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
# 師父貼文的開頭。原書排版並不一致：除了「Taiguanglin：」，還有多出空格的
# 「Taiguanglin ：」、誤植分號的「Taiguanglin；」，以及回覆特定網友的
# 「Taiguanglin@ 某某：」（此時 @某某 屬於內文，只吃掉署名）。
_ANSWER_LEAD_RE = re.compile(r"^%s\s*(?:[：:；;]\s*|(?=@))" % _ANSWERER)


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

    def append_strong_line(self, text):
        """粗體行：連續粗體合併為同一區塊（避免 PDF 換行切斷經文）。"""
        prev = self.blocks[-1] if self.blocks else None
        if prev is not None and prev["kind"] == "strong":
            prev["text"] = _join(prev["text"], text)
            return
        self.append("strong", text)

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
                lead = _ANSWER_LEAD_RE.match(t)
                if lead:
                    body = re.sub(r"^@\s+", "@", t[lead.end():].strip())
                    # 每則署名貼文在原書中各自獨立（各有發文時間），連續多則
                    # 時要各自成塊，不能併進上一則的回答。
                    if qa_text:
                        flush_qa()
                    else:
                        flush_para()
                    if qa is None:
                        qa = {"questioner": "", "qtext": ""}
                    qa_text = body
                    cont_left = line.x0 if cont_left is None else min(cont_left, line.x0)
                elif qa is not None:
                    if cont_left is not None and line.x0 > cont_left + 4.0 \
                            and qa_text.strip():
                        # 上一段已經以發文時間收尾 → 這裡是師父的下一則貼文
                        # （原書未再署名），同樣要獨立成塊。
                        if _TIME_RE.search(qa_text.rstrip()):
                            flush_qa()
                            qa = {"questioner": "", "qtext": ""}
                        else:
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

# 本書的字型分工：FZSHJW＝整段原經文、FZHTJW＝黑體強調、FZBYSK＝正文宋體。
_JG_SUTRA_FONT = "FZSHJW"
_JG_EMPH_FONT = "FZHTJW"
_JG_BODY_FONT = "FZBYSK"
_JG_LABEL_RE = re.compile(r"^(译文|注解|解析|本章大义)[：:]?$")
_JG_NUM_RE = re.compile(r"^\s*\d{1,2}[.．]\s*")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_JG_NGRAM = 4
_JG_MIN_RATIO = 0.6


def _cjk_only(text):
    return "".join(_CJK_RE.findall(text))


class _SutraCorpus:
    """全書原經文語料，用來判斷「解析」裡重引的句子是否真為經文。

    解析中的黑體段落有兩種：重引原經文（整段皆黑體），以及名相注釋的詞頭
    （詞頭後緊接宋體說明，如「阿修罗：我们可以理解为……」）。字型分工可先
    濾掉後者；剩下的仍混有少量白話講解（如「对于五眼有不同的解释。」、咒語
    的白話翻譯），故再與原經文比對。書中重引時偶有省字（原文「以音声求我」
    重引作「音声求我」）或異體字（著／着），因此用字元 n-gram 的重疊比例而
    非完全比對。
    """

    def __init__(self, texts):
        joined = _cjk_only("".join(texts))
        self._text = joined
        n = _JG_NGRAM
        self._grams = {joined[i:i + n] for i in range(len(joined) - n + 1)}

    def matches(self, text):
        probe = _cjk_only(_JG_NUM_RE.sub("", text))
        if not probe:
            return False
        n = _JG_NGRAM
        if len(probe) < n:
            return probe in self._text
        grams = [probe[i:i + n] for i in range(len(probe) - n + 1)]
        hit = sum(1 for g in grams if g in self._grams)
        return hit / len(grams) >= _JG_MIN_RATIO


def parse_jingang(ctx):
    corpus = _SutraCorpus([
        line.text for _pno, ls in _iter_pages(ctx) for line in ls
        if line.font == _JG_SUTRA_FONT
    ])

    body_left = None
    para = ""
    para_emph = False      # 段落首行為黑體
    para_has_body = False  # 段落中出現宋體 → 是名相注釋而非重引經文
    quote = ""
    quote_left = None

    def flush():
        nonlocal para, para_emph, para_has_body, quote, quote_left
        text = para.strip()
        if text:
            if para_emph and not para_has_body and _JG_LABEL_RE.match(text):
                ctx.append("label", text.rstrip("：:"))
            elif para_emph and not para_has_body and corpus.matches(text):
                ctx.append("strong", text)
            else:
                ctx.append("para", text)
        if quote.strip():
            ctx.append("quote", quote.strip())
        para, quote = "", ""
        para_emph, para_has_body = False, False
        quote_left = None

    def add_text_line(line, text, emph):
        """把正文/黑體行併入段落緩衝；是否為經文留到 flush 時整段判定。"""
        nonlocal body_left, para, para_emph, para_has_body
        if quote.strip():
            flush()
        if emph and _JG_NUM_RE.match(text):
            flush()
        body_left = line.x0 if body_left is None else min(body_left, line.x0)
        if para.strip() and _is_indent_start(line, body_left):
            flush()
        if not para:
            para_emph = emph
            para_has_body = False
        if not emph or _JG_BODY_FONT in line.fonts:
            para_has_body = True
        para = _join(para, text)

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
            elif f == _JG_SUTRA_FONT:
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
            elif f == _JG_EMPH_FONT:
                add_text_line(line, t, emph=True)
            elif f == _JG_BODY_FONT:
                add_text_line(line, t, emph=False)
        ctx.add_images_for_page(pno)
    flush()
    return True


# ---------------------------------------------------------------------- #
# 05 圆觉经讲记
# ---------------------------------------------------------------------- #

_LABEL_RE = re.compile(r"(译文|注解|解析|本章大义|原经文)[:：\s]*$")
_XJDU_RE = re.compile(r"^原文精读\s*\d*$")
# 解析內重引經文（編號 + 作/任/止/滅病）應為粗體且獨立成行
_SUTRA_NUM_RE = re.compile(r"^\d+\.\s*[一二三四]者.*病")
# 解析中「若诸菩萨...」類編號經文
_SUTRA_NUM_RE2 = re.compile(r"^\d+\.\s*若诸菩萨")
_SUTRA_KEYWORDS = ("若复有人作如是言", "彼圆觉性", "欲求圆觉", "离四病者", "若诸菩萨")


def parse_yuanjue(ctx):
    para = ""
    quote = ""
    body_left = None
    quote_left = None

    # 預先收集全書 KaiTi 經文語料，用於判斷解析中重引的經文句（即使首行為常規字體）
    _quote_corpus_parts = []
    for _pno, _ls in sorted(ctx.lines_by_page.items()):
        if _pno in ctx.toc_pages:
            continue
        for _line in _ls:
            if _line.font == "KaiTi":
                _ct = _clean(_line.text)
                if _ct:
                    _quote_corpus_parts.append(_ct)
    _quote_corpus = "".join(_quote_corpus_parts)

    def _is_quote_substring(txt: str) -> bool:
        # 去編號後，取前 15 字判斷是否出現在原經文語料中
        stripped = re.sub(r"^\d+\.\s*", "", txt).strip()
        if len(stripped) < 8:
            return False
        probe = stripped[:15]
        return probe in _quote_corpus

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
                if para.strip() or quote.strip():
                    flush()
                ctx.append_strong_line(t)
            else:
                # 譯文小標「1. 提问部分」「2. 佛答部分」應獨立成行，不與後續正文黏合
                if re.match(r"^\d+\.\s*(提问部分|佛答部分)\s*$", t):
                    if para.strip() or quote.strip():
                        flush()
                    ctx.append("para", t)
                    body_left = None
                    continue
                # 解析中重引經文：編號「1. 一者作病…」或「1. 若诸菩萨…」等雖為常規字體，仍應視為粗體經文獨立成行
                _is_sutra = _SUTRA_NUM_RE.match(t) is not None or _SUTRA_NUM_RE2.match(t) is not None
                if not _is_sutra and re.match(r"^\d+\.", t):
                    if any(kw in t for kw in _SUTRA_KEYWORDS):
                        _is_sutra = True
                    elif "若诸菩萨" in t or "此菩萨者" in t or "名单修" in t:
                        _is_sutra = True
                    elif _is_quote_substring(t):
                        _is_sutra = True
                    elif "若经夏首" in t or "至安居日" in t or "踞菩萨乘" in t:
                        _is_sutra = True
                # 無編號但為經文片段的連續行（例如「彼实华生处...」被誤切為常規時）亦視為經文
                if not _is_sutra and len(t) > 12 and _is_quote_substring(t):
                    # 若前一區塊已是編號經文的強行，後續常規片段應合併
                    prev = ctx.blocks[-1] if ctx.blocks else None
                    if prev and prev["kind"] == "strong" and _SUTRA_NUM_RE.match(prev["text"][:10]) is None:
                        # 檢查是否為同一經句的延續
                        if any(kw in t for kw in ("彼", "此", "皆", "亦", "故")):
                            _is_sutra = True
                if _is_sutra:
                    if para.strip() or quote.strip():
                        flush()
                    ctx.append_strong_line(t)
                    body_left = None
                    continue
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
    merge = parser_key in ("wendalu", "zuochan2")
    ctx = ParseContext(lines_by_page, toc_pages, images_by_page,
                       merge_adjacent_headings=merge)
    ok = PARSERS[parser_key](ctx)
    # 後處理：坐禅2 中「上半場第一個500年（公元前1000年」/「公元前500年)」等被 PDF 換行切成兩條同級標題，需合併且補「—」
    if parser_key == "zuochan2" and ok:
        merged = []
        for blk in ctx.blocks:
            if blk["kind"] in ("h2", "h3", "h4") and merged and merged[-1]["kind"] == blk["kind"]:
                prev = merged[-1]
                # 僅合併明顯斷裂的標題：前一條以「年」或「（」結尾，後一條以「公元」開頭
                if re.match(r".*?[（(]\s*$|.*年\s*$", prev["text"]) and re.match(r"^\s*公元", blk["text"]):
                    # 補上破折號避免「1000年公元前500年」黏連
                    joiner = "—" if not prev["text"].endswith("—") and not blk["text"].startswith("—") else ""
                    prev["text"] = prev["text"].rstrip(" \t") + joiner + blk["text"].lstrip(" \t")
                    # 合併計數（若有）
                    if "count" in prev and "count" in blk:
                        prev["count"] = prev.get("count", 0) + blk.get("count", 0)
                    continue
            merged.append(blk)
        ctx.blocks = merged
        # 修復已透過 heading 合併但缺少破折號的標題（例如「1000 年公元前500」→「1000 年—公元前500」）
        for blk in ctx.blocks:
            if blk["kind"] in ("h2", "h3", "h4") and "年公元" in blk["text"] and "年—公元" not in blk["text"]:
                blk["text"] = blk["text"].replace("年公元", "年—公元")
            # 修復「500年）」等缺失右括號完整性的細節（已在 PDF 中正確，此處僅保底）
            if blk["kind"] in ("h2", "h3", "h4") and blk["text"].endswith("年"):
                # 若標題以「年」結尾且包含「（」但無「）」，補齊（極少見，防禦性）
                if "（" in blk["text"] and "）" not in blk["text"]:
                    blk["text"] = blk["text"] + "）"
    return ctx.blocks if ok else []
