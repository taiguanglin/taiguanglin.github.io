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
import unicodedata

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
    # 康熙部首（U+2F00–U+2FDF）是 PDF 楷體抽取出的異體碼位（如 ⼆→二、⾳→音），
    # 逐一 NFKC 正規化回通用漢字；其餘字元不動。
    out = []
    for ch in text:
        cp = ord(ch)
        out.append(unicodedata.normalize("NFKC", ch) if 0x2F00 <= cp <= 0x2FDF else ch)
    return "".join(out).strip()


def _join(a, b):
    """合併被 PDF 換行切斷的兩段文字。"""
    if not a:
        return b
    if re.search(r"[A-Za-z0-9,;:)」]$", a) and re.match(r"^[A-Za-z0-9(「]", b):
        return a + " " + b
    return a + b


# 下一行看起來像「新的一條標題」而非上一條的換行續寫。
_NEW_HEADING_RE = re.compile(
    r"^(?:"
    r"第\s*\d+\s*[章节篇講讲]|"
    r"第[一二三四五六七八九十百零〇]+\s*[章节篇講讲]|"
    r"[（(]?\d+[）.、．]|"
    r"[（(]\d+[）)]|"
    r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]|"
    r"原文精读"
    r")"
)
# 「总 论」「序 言」這類標題字距拉開的兩個（以上）單字
_LETTERSPACED_RE = re.compile(
    r"(?:(?<=\s)|^)[\u4e00-\u9fff](?: [\u4e00-\u9fff])+(?=\s|$)"
)


def _is_new_heading_start(text):
    return bool(_NEW_HEADING_RE.match(text.strip()))


def _should_merge_heading(prev_text, next_text):
    """緊接的同級標題要不要併成同一條。

    一般：次行不像新條目（例如「尘不」+「可出」）就合併。
    若次行開頭是「（N）」這種子項編號，視為下一條標題，不合併，
    以免把「1. 传承」與其第一個子項「（1）佛经」黏成同一條。
    """
    nxt = next_text.strip()
    if _is_new_heading_start(nxt):
        return False
    return True


def _normalize_heading_text(text):
    """還原 PDF 標題常見的字距與中英黏連。"""
    text = _LETTERSPACED_RE.sub(lambda m: m.group(0).replace(" ", ""), text)
    # 「第01 节」字距來自原書標題排版，顯示為「第01节」
    text = re.sub(r"(第\d+)\s+([章节篇講讲])", r"\1\2", text)
    text = re.sub(r"([\u4e00-\u9fff])([A-Za-z])", r"\1 \2", text)
    text = re.sub(r"([A-Za-z])([\u4e00-\u9fff])", r"\1 \2", text)
    return text


class ParseContext:
    """單本書解析時的共同狀態。"""

    def __init__(self, lines_by_page, toc_pages, images_by_page):
        self.lines_by_page = lines_by_page
        self.toc_pages = toc_pages
        self.images_by_page = images_by_page
        self.blocks = []
        self.seen_xrefs = set()
        self._last_was_heading = False

    def heading(self, level, text, space_join=False):
        text = _clean(text)
        if not text or re.fullmatch(r"\d{1,4}", text):
            return
        text = _normalize_heading_text(text)
        prev = self.blocks[-1] if self.blocks else None
        # 同級標題緊接出現、且次行不像新條目 → PDF 把同一標題切成兩行
        if (self._last_was_heading and prev is not None and prev["kind"] == level
                and _should_merge_heading(prev["text"], text)):
            if space_join:
                prev["text"] = _normalize_heading_text(prev["text"] + " " + text)
            else:
                prev["text"] = _normalize_heading_text(_join(prev["text"], text))
            return
        self.blocks.append({"kind": level, "text": text})
        self._last_was_heading = True

    def append(self, kind, text=None, **extra):
        blk = {"kind": kind}
        if text is not None:
            blk["text"] = text
        blk.update(extra)
        self.blocks.append(blk)
        self._last_was_heading = False

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
            self._last_was_heading = False


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
# 「（1）佛经」「(2) 僧团」這種括號編號子項，比「1. 传承」深一層。
_H5_PAT = re.compile(r"^[（(]\d+[）)]")
# 「Ⅰ）恩惠」「Ⅱ）权威」這種羅馬數字子項，又比括號編號子項（（1）…）深一層。
_H6_PAT = re.compile(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+[）)]")
_SHORT_HEAD_MAX = 22


def _zuochan2_h4(t):
    if _H4_PAT.match(t):
        return True
    if len(t) <= _SHORT_HEAD_MAX and not re.search(r"[，。；：,；]$", t):
        return True
    return False


def _zuochan2_h5(t):
    """括號編號子項（（1）…／(2)…）→ h5。"""
    return bool(_H5_PAT.match(t))


def _zuochan2_h6(t):
    """羅馬數字子項（Ⅰ）…／Ⅱ）…）→ h6。"""
    return bool(_H6_PAT.match(t))


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
                if _zuochan2_h6(t):
                    ctx.heading("h6", t)
                elif _zuochan2_h5(t):
                    ctx.heading("h5", t)
                elif _zuochan2_h4(t):
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
# ---------------------------------------------------------------------- #
# 講經系列（06 四十二章 / 07 楞伽 / 08 六祖壇經 / 09 楞嚴 / 感恩）
# ---------------------------------------------------------------------- #
# 這些書皆以「講次（期）」為章節，每講對應一把音檔。講次標題的字型
# 統一比正文大（≥15.5），且匹配 "<經名>（N）"；正文約 13.9–14.1。
# 標題可能字距拉開（「楞 伽 经（42）」）或拆成兩行（壇經的「坛」＋
# 「经（1）」），故先累積 ≥15.5 的連續大字行、去空白後再合併比對。
# 講次編號可能是阿拉伯數字或中文數字（楞嚴 12–21 用「十二」…）。
#
# 原經文用楷體（KaiTi / HYKaiTiKW）排，對應既有書籍的 quote 區塊
# （`.sutra-text`）；正文段落依首行縮排切分；頁碼（小字）與「时间/
# 完整音频」metadata 行直接略過。

_CN_NUM = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,
           "十":10,"十一":11,"十二":12,"十三":13,"十四":14,"十五":15,
           "十六":16,"十七":17,"十八":18,"十九":19,"二十":20,"二十一":21,
           "二十二":22,"二十三":23,"二十四":24,"二十五":25,"二十六":26,
           "二十七":27,"二十八":28,"二十九":29,"三十":30,"三十一":31,
           "三十二":32,"三十三":33,"三十四":34,"三十五":35,"三十六":36,
           "三十七":37,"三十八":38,"三十九":39,"四十":40,"四十一":41,
           "四十二":42}

_JIANGJING_LECTURE_RE = re.compile(
    r"^(?:四十二章经|楞伽经|坛经|楞严经)\s*[（(]\s*(\d+|[一二三四五六七八九十百]+)\s*[)）]"
)
# 四十二章經 的章級標題：「第X章<名>」（標題字型較大 ≥15.5；14.1 的
# 「第X章…」重複行實為正文句首，應視為段落）。
_SISHIER_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百零〇\d]+章")
_SISHIER_CH_TITLE_MAX = 20
# 品名標題（原經文的品節，楷體且字型較大，如「断食肉品第八」→ h3 導覽）
_PINRE = re.compile(r"^[^，。；：]{2,20}[品第][一二三四五六七八九十百零〇\d之]+$")
# 略過的 metadata 行。「音」在部分 PDF 被抽成康熙部首 ⾳(U+2FB3)，故完整音頻用
# 「完整」＋任意一字元（音/⾳）＋「频请关注」寬鬆比對。
_META_RE = re.compile(r"^(时间[：:]|完整.频请关注)")

# 各書楷體（原經文）字型集合
_SUTRA_FONTS_STD = {"KaiTi", "HYKaiTiKW", "PingFangSC-Semibold", "STKaiti"}
# 正文（解說）字型集合
_BODY_FONTS_STD = {"MicrosoftYaHei", "HYQiHei-EES", "HYQiHeiKW-EES",
                   "HYQiHeiKW-HES", "PingFangSC-Regular", "DengXian-Regular"}
# 中性字型（數字/西文/標點，不算楷也不算黑）：只認 Times*/Helvetica/Arial 等，
# 用於行內拆分的「空」字型，不觸發楷↔黑切分。
_NEUTRAL_FONTS = {"TimesNewRomanPSMT", "TimesNewRomanPS-BoldMT",
                  "Helvetica", "Arial", "Courier", "Times-Roman",
                  "TimesNewRomanPS-ItalicMT"}


def _font_class(f):
    """把字型歸類為 sutra / body / neutral 三類，供行內拆分。"""
    if f in _SUTRA_FONTS_STD:
        return "sutra"
    if f in _BODY_FONTS_STD:
        return "body"
    # 已知中性字型（數字/西文）之外，非楷字型一律先視為 body（楷體才是原經文）。
    return "neutral"


def _de_space(text):
    """去掉字距拉開標題的內部空白（如「楞 伽 经（42）」→「楞伽经（42）」）。"""
    return re.sub(r"\s+", "", text)


def _lecture_int(num_text):
    """把講次（阿拉伯/中文數字）轉成 int（不可轉則回原字串）。"""
    num_text = num_text.strip()
    if num_text.isdigit():
        return int(num_text)
    return _CN_NUM.get(num_text, num_text)


def _is_page_number_line(line, text):
    """小字純數字（頁碼）。新書頁碼用 MicrosoftYaHei / Times 等字型，extract.py
    的 is_page_number 只認 Helvetica/Arial，故此處以「字型 < 11.5 且純數字」補抓。"""
    return line.size < 11.5 and re.fullmatch(r"\d{1,4}", text.strip())


_HANZI_RE = re.compile(r"[\u4e00-\u9fff]")
_ALNUM_RE = re.compile(r"[0-9A-Za-z]")
# 前導（開）引號/括號：語義上「開啟」後面的引述，應併入後段。
_OPEN_QUOTE_CHARS = set('“‘「『（(【[')


def _is_open_quote_only(text):
    """純標點 span 是否只含「開引號/開括號」字元（如單獨的「“」）。"""
    t = text.strip()
    return bool(t) and all(c in _OPEN_QUOTE_CHARS for c in t)


def _is_punct_only(text):
    """回傳該 span 是否「只含標點符號」（無漢字/西文字母/數字）。

    用於行內拆分：PDF 抽取時，句尾標點有時被單獨用楷體（KaiTi）或黑體
    排出（如「…一时，」的逗號用 KaiTi）。這類純標點 span 不該觸發楷↔黑
    切分、更不該獨立成段，應併入相鄰的文字段（與中性字型同待遇）。
    """
    t = text.strip()
    if not t:
        return False
    return not (_HANZI_RE.search(t) or _ALNUM_RE.search(t))


def _has_inline_sutra_body_mix(line):
    """判斷一行是否「經文（楷體）與講解（黑體）緊連混排」。

    講經系列（如楞伽）中，講解者常於一句白話裡引述原經文，且經文
    引用與講解文字被排在**同一個視覺行**（楷體 span 與黑體 span 交
    替出現，兩者都含漢字）。這種經文引用前後都不滿足「獨立成段（前後
    都是換行）」的條件，不應被拆成獨立的經文區塊；反觀純粹的標點符號
    用黑體（如「藏识大海境界风动，转识浪起，」的句尾逗號）不算混排。

    回傳 True 表示該行是「經文緊連講解」，應整行歸入講解正文。
    """
    body_hanzi = any(_HANZI_RE.search(sp[0]) for sp in line.spans
                     if sp[1] in _BODY_FONTS_STD)
    sutra_hanzi = any(_HANZI_RE.search(sp[0]) for sp in line.spans
                      if sp[1] in _SUTRA_FONTS_STD)
    return body_hanzi and sutra_hanzi


def _split_mixed_line(line):
    """把一行內「楷(經文)/黑(解說)」混排的 PDF 行切成多個子行。

    楞嚴 docx 轉 PDF 後，經文結尾 + 解說開頭常被合併到同一視覺行。行內
    的數字/西文常落在 TimesNewRoman 等字型（如「坛经（6）」的「6」），
    這些中性字型只併入相鄰段，不觸發切分；只有楷↔黑字型交界才切。
    """
    spans = line.spans
    if not spans or len(spans) < 2:
        return [line]
    from collections import namedtuple
    Sub = namedtuple("SubLine", ["text", "font", "size", "fonts",
                                 "page", "x0", "y0", "block_id", "spans"])

    def _mk(stxt, sfont):
        use_font = sfont if sfont and sfont not in _NEUTRAL_FONTS else line.font
        return Sub(text=stxt, font=use_font, size=line.size, fonts=(use_font,),
                   page=line.page, x0=line.x0, y0=line.y0,
                   block_id=line.block_id, spans=((stxt, use_font, line.size),))

    # 依字型 class 合併相鄰 span；中性 span 併入「後續」有 class 的段
    # （若開頭就中性，併入下一段；若結尾中性，併入上一段）。
    segments = []  # list of [text, class, first_real_font]
    cur_text = ""
    cur_cls = None
    cur_font = None
    for txt, f, sz in spans:
        cls = _font_class(f)
        if not txt.strip():
            # 空白 span：先併入當前段（若無則保留到下一段）
            cur_text += txt
            continue
        if cls == "neutral":
            # 中性字型：併入當前段（若無則暫時累積，稍後併入下一段）
            cur_text += txt
            if cur_font is None:
                cur_font = f
            continue
        if _is_punct_only(txt):
            # 純標點 span。 開引號（如單獨的「“」）是「前導」標點，併入**後段**
            # （後方經文/講解的引述開頭）；閉標點/句讀（逗號、句號、閉引號等）
            # 是「結尾」標點，段中則併入**前段**。
            if _is_open_quote_only(txt):
                # 開引號：併入當前累積、不設 cur_cls/cur_font；下一個實質文字
                # 確定段 class 時，開引號自然落在該段開頭。
                cur_text += txt
                continue
            if cur_cls is not None:
                # 段中閉標點/句讀（如講解裡的楷體逗號「，」）：併入前段，不觸發
                # 切分、不改段字型，避免拆出孤立的 quote/para。
                cur_text += txt
                continue
            # 段首閉標點（跨行的經文尾句號「。」等）：走下方正常 class 切分，
            # 靠主流程 _join 把它併回上一行的經文。
        if cur_cls is None or cls == cur_cls:
            cur_text += txt
            cur_cls = cls
            if cur_font is None:
                cur_font = f
        else:
            segments.append((cur_text, cur_cls, cur_font))
            cur_text = txt
            cur_cls = cls
            cur_font = f
    if cur_cls is not None:
        segments.append((cur_text, cur_cls, cur_font))
    # 若只剩一段或沒有楷↔黑交界，本不需切分，但該段可能含有純標點 span（其
    # 字型不反映段內文字），故仍需依 cur_font 構造 SubLine 校正 font，避免
    # 原行首 span 的楷體標點把整段講解誤判成經文。
    if len(segments) < 2:
        if not segments:
            return [line]
        stxt, scls, sfont = segments[0]
        if _mk(stxt, sfont).font == line.font and not _is_punct_only(stxt.strip()):
            return [line]
        return [_mk(stxt, sfont)]
    classes = [c for _, c, _ in segments]
    if not (("sutra" in classes) and ("body" in classes)):
        if not segments:
            return [line]
        stxt, scls, sfont = segments[0]
        if _mk(stxt, sfont).font == line.font and not _is_punct_only(stxt.strip()):
            return [line]
        return [_mk(stxt, sfont)]
    subs = []
    for stxt, scls, sfont in segments:
        stxt_clean = stxt.strip()
        if not stxt_clean:
            continue
        subs.append(_mk(stxt, sfont))
    return subs or [line]


def _parse_jiangjing(ctx, with_chapters=False, inline_sutra_to_body=False):
    """講經系列通用解析：h2=講次（含音檔）、h3=章/品、quote=楷體原經文、
    para=正文段落（依縮排切分）。

    ``inline_sutra_to_body``：講解文字中**引述**原經文（楷體）且與講解
    緊連在同一視覺行時，整行歸入講解正文（para），不拆成獨立經文區塊。
    只有「前後都是換行、獨立成段」的原經文才分段為 quote。楞伽（lengqie）
    開此選項；楞嚴（lengyanjing）因 docx 轉 PDF 後「經文結尾 + 解說開頭」
    黏同行，仍需行內拆分，維持舊行為。
    """

    para = ""
    quote = ""
    body_left = None
    quote_left = None
    title_buf = []
    # 講解引述經文的「連續流」狀態：講解文字中引述的原經文（楷體）緊連
    # 講解、前後無換行/段落分隔時，這些楷體片段（含跨行的純楷體續行）應
    # 整段併入講解正文，而非拆成獨立 quote。縮排行（新段落）會結束該狀態。
    inline_cite = False

    def flush():
        nonlocal para, quote, quote_left, body_left, inline_cite
        if para.strip():
            ctx.append("para", para.strip())
        if quote.strip():
            ctx.append("quote", quote.strip())
        para, quote = "", ""
        quote_left = None
        body_left = None
        inline_cite = False

    def flush_title():
        nonlocal title_buf, para, body_left
        if not title_buf:
            return
        ds = _de_space("".join(title_buf))
        m = _JIANGJING_LECTURE_RE.match(ds)
        if m:
            n = _lecture_int(m.group(1))
            if isinstance(n, int):
                ds = re.sub(r"([（(])\s*[一二三四五六七八九十百]+\s*([)）])",
                            lambda mm: "%s%d%s" % (mm.group(1), n, mm.group(2)), ds)
            ctx.append("h2", ds, lecture=n)
        else:
            # 誤判為標題的大字（封面/單字），回灌為正文
            body_left = None
            para = _join(para, "".join(title_buf))
        title_buf = []

    for pno, ls in _iter_pages(ctx):
        for line in ls:
            t = _clean(line.text)
            if not t:
                continue
            # 講解引述經文、經文與講解緊連同行（楷+黑漢字混排）→ 整行併入正文，
            # 不拆成獨立經文；否則經文引用會錯斷成 quote 而切開講解。並進入
            # 「引述流」狀態，讓其後緊接的純楷體續行也併入講解。
            if inline_sutra_to_body and _has_inline_sutra_body_mix(line):
                if title_buf:
                    flush_title()
                if quote.strip():
                    flush()
                ds = _de_space(t)
                if _is_page_number_line(line, t) or _META_RE.match(ds):
                    continue
                if body_left is None:
                    body_left = line.x0
                else:
                    body_left = min(body_left, line.x0)
                if para.strip() and _is_indent_start(line, body_left):
                    flush()
                    # flush 會重置 body_left，此處重新錨定為本行縮排量，
                    # 使後續緊連的楷體引述續行（頂格）能被正確判為「非縮排」。
                    body_left = line.x0
                para = _join(para, t)
                # 引述流狀態：此行（無論縮排與否）都引述了經文並緊連講解，
                # 故在 flush 之後才設 True，讓其後的純楷體續行也併入講解。
                inline_cite = True
                continue
            # 行內楷/黑混排拆分（楞嚴 docx 轉 PDF 後的常見問題）：
            # 把同一行裡不同字型的相鄰 span 切成多個子行，後續主流程逐個處理。
            sub_lines = _split_mixed_line(line)
            for sub in sub_lines:
                t = _clean(sub.text)
                if not t:
                    continue
                line = sub
                ds = _de_space(t)
                # 頁碼 / metadata 行
                if _is_page_number_line(line, t):
                    continue
                if _META_RE.match(ds):
                    continue
                s = line.size
                f = line.font
                is_sutra = f in _SUTRA_FONTS_STD
                # 1. 講次標題（直接匹配，例如「楞伽经（1）」整行）— 不限字型
                if s >= 15.5 and _JIANGJING_LECTURE_RE.match(ds):
                    flush_title()
                    flush()
                    m = _JIANGJING_LECTURE_RE.match(ds)
                    n = _lecture_int(m.group(1))
                    if isinstance(n, int):
                        ds = re.sub(r"([（(])\s*[一二三四五六七八九十百]+\s*([)）])",
                                    lambda mm: "%s%d%s" % (mm.group(1), n, mm.group(2)), ds)
                    ctx.append("h2", ds, lecture=n)
                    continue
                # 2. 楷體大字 = 品/卷名標題（KaiTi ≥15.5，如「断食肉品第八」「卷一」「卷二」）。
                #    四十二章 的「经序/序分」楷體大字實為正文標題的重複渲染，交由步驟 3
                #    以正文大字處理，此處不重複視為 h3。
                if is_sutra and s >= 15.5 and not with_chapters:
                    flush_title()
                    flush()
                    ctx.heading("h3", ds)
                    continue
                # 3. 章/節標題（四十二章「第X章」「前言」「经序」「序分」等，正文大字）
                if (not is_sutra and s >= 15.5 and with_chapters
                        and (_SISHIER_CHAPTER_RE.match(ds) or ds in {"前言", "经序", "序分"})
                        and len(ds) <= _SISHIER_CH_TITLE_MAX):
                    flush_title()
                    flush()
                    ctx.heading("h3", ds)
                    continue
                # 4. 其餘大字行 → 累積（供拆成多行的講次標題，如壇經「坛」＋「经（1）」）
                if s >= 15.5 and not is_sutra:
                    flush()
                    title_buf.append(ds)
                    continue
                if title_buf:
                    flush_title()
                # 5. 楷體 = 原經文（quote）
                if is_sutra:
                    # 四十二章 的「经序/序分」楷體行是章節標題的裝飾性重複（右側邊），略過
                    if with_chapters and ds in {"经序", "序分", "前言"}:
                        continue
                    # 引述流中的頂格楷體 = 講解引述經文的跨行續行（前一行是
                    # 楷/黑混排或引述續行），緊連講解、無段落分隔 → 併入講解。
                    if (inline_sutra_to_body and inline_cite and body_left is not None
                            and not _is_indent_start(line, body_left)):
                        para = _join(para, t)
                        continue
                    if para.strip():
                        flush()
                    if quote_left is None:
                        quote_left = line.x0
                    else:
                        quote_left = min(quote_left, line.x0)
                    if quote.strip() and _is_indent_start(line, quote_left):
                        flush()
                    quote = _join(quote, t)
                    continue
                # 6. 正文段落
                inline_cite = False
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
    flush_title()
    flush()
    # 後處理：四十二章 的章標題（h3）與下一講的講次標題（h2）印在同一行
    # （章名居左、講次居右），PDF 抽出時章名先於講次，導致章（h3）緊接在
    # 講次（h2）之前、名下內容為 0。把這種「h3 緊接 h2 且中間無內容」的
    # 成對順序對調，讓講次當父、章當子。
    out = []
    i = 0
    n = len(ctx.blocks)
    while i < n:
        b = ctx.blocks[i]
        if (b["kind"] == "h3" and i + 1 < n and ctx.blocks[i + 1]["kind"] == "h2"):
            out.append(ctx.blocks[i + 1])
            out.append(b)
            i += 2
        else:
            out.append(b)
            i += 1
    ctx.blocks = out
    return True


def parse_lengqie(ctx):
    return _parse_jiangjing(ctx, inline_sutra_to_body=True)


def parse_liuzutanjing(ctx):
    return _parse_jiangjing(ctx)


def parse_lengyanjing(ctx):
    return _parse_jiangjing(ctx)


def parse_sishierzhang(ctx):
    return _parse_jiangjing(ctx, with_chapters=True)


def parse_ganen(ctx):
    """感恩与讲经：單一講次（無編號），封面標題為 h2，無楷體原經文。"""
    para = ""
    body_left = None
    first_heading = False

    def flush():
        nonlocal para, body_left
        if para.strip():
            ctx.append("para", para.strip())
        para = ""
        body_left = None

    for pno, ls in _iter_pages(ctx):
        for line in ls:
            t = _clean(line.text)
            if not t:
                continue
            ds = _de_space(t)
            if _is_page_number_line(line, t):
                continue
            if re.match(r"^时间[：:]", ds) or ds.startswith("完整音频"):
                continue
            s = line.size
            # 封面標題「感 恩 与 讲 经」僅出現一次
            if ds == "感恩与讲经" and s >= 15.5 and not first_heading:
                flush()
                ctx.append("h2", "感恩与讲经", lecture=1)
                first_heading = True
                continue
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
    "ganen": parse_ganen,
    "sishierzhang": parse_sishierzhang,
    "lengqie": parse_lengqie,
    "liuzutanjing": parse_liuzutanjing,
    "lengyanjing": parse_lengyanjing,
}


def parse_book(parser_key, lines_by_page, toc_pages, images_by_page):
    ctx = ParseContext(lines_by_page, toc_pages, images_by_page)
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
