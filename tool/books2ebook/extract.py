"""PDF 文字擷取：把每頁拆成帶字型資訊的行，並偵測目錄頁與插圖。"""

import re

import pymupdf

# 目錄頁的虛線引導（例如 「第01节 终极佛法.........................13」）
_DOT_LEADER_RE = re.compile(r"\.{5,}\s*\d{0,4}\s*$")
# 頁碼行：純數字，通常用西文字型
_PAGE_NUM_RE = re.compile(r"^\s*\d{1,4}\s*$")


class Line:
    """PDF 上的一個視覺行。

    ``font`` 是首個 span 的字型（多數解析器只需要它）；``fonts`` 保留整行用
    到的所有字型，供需要分辨「整行同一字型」與「行內換字型」的解析器使用
    （例如《金刚经》解析裡的重引經文 vs 名相注釋詞頭）。
    """

    __slots__ = ("text", "size", "font", "fonts", "page", "x0", "y0", "block_id")

    def __init__(self, text, size, font, page, x0=0.0, y0=0.0, block_id=0,
                 fonts=None):
        self.text = text
        self.size = size
        self.font = font
        self.fonts = tuple(fonts) if fonts else (font,)
        self.page = page
        self.x0 = x0
        self.y0 = y0
        self.block_id = block_id

    @property
    def is_page_number(self):
        return _PAGE_NUM_RE.match(self.text) and self.font.startswith(
            ("Helvetica", "Arial")
        )

    def __repr__(self):  # pragma: no cover - debug helper
        return "Line(p%d %.1f %s %r)" % (self.page, self.size, self.font, self.text[:30])


def extract_lines(pdf_path, skip_pages=0):
    """回傳 (lines_by_page, images_by_page)。

    lines_by_page : {page_no: [Line, ...]}（page_no 從 1 起）
    images_by_page: {page_no: [(xref, w, h), ...]} 已去除封面/側欄裝飾
    """
    doc = pymupdf.open(pdf_path)
    lines = {}
    images = {}
    for i, page in enumerate(doc):
        pno = i + 1
        if pno <= skip_pages:
            continue
        page_lines = []
        raw = page.get_text("dict")
        for b_idx, block in enumerate(raw["blocks"]):
            if block.get("type") != 0:
                continue
            for ln in block["lines"]:
                spans = [s for s in ln["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                size = round(max(s["size"] for s in spans), 1)
                fonts = tuple(dict.fromkeys(
                    s["font"].split("--")[0] for s in spans))
                font = fonts[0]
                x0 = min(s["bbox"][0] for s in spans)
                y0 = ln["bbox"][1]
                line = Line(text, size, font, pno, x0, y0, b_idx, fonts)
                if line.is_page_number:
                    continue
                page_lines.append(line)
        if page_lines:
            lines[pno] = page_lines
        imgs = []
        for im in page.get_images(full=True):
            xref, w, h = im[0], im[2], im[3]
            # 過濾小裝飾圖與直式側欄圖（細長），保留真正的插圖
            if w < 200 or h < 200:
                continue
            if max(w, h) / float(min(w, h)) > 3.0:
                continue
            imgs.append((xref, w, h))
        if imgs:
            images[pno] = imgs
    doc.close()
    return lines, images


def find_toc_pages(lines_by_page, min_dots=8):
    """偵測書前目錄頁。

    目錄頁 = 含多條虛線引導行的頁面；只取「連續區段」——從第一個
    出現虛線行的頁面開始，往後延伸到不再出現為止。書中間的隔頁
    （部分章節的小目錄）因為前面已有內文，不會被誤判。
    """
    pages_in_order = sorted(lines_by_page)
    toc_pages = set()
    run_started = False
    for pno in pages_in_order:
        ls = lines_by_page[pno]
        dots = sum(1 for l in ls if _DOT_LEADER_RE.search(l.text))
        has_title = any(re.match(r"^目\s*录?$", l.text) for l in ls)
        is_toc = dots >= min_dots or (has_title and dots >= 1)
        if is_toc:
            run_started = True
            toc_pages.add(pno)
        elif run_started:
            # 目錄區段結束後就不再標記（之後的虛線行視為裝飾）
            break
    return toc_pages


def extract_image(pdf_path, xref, out_path_base):
    """把指定 xref 的圖片匯出；回傳實際寫入路徑或 None。"""
    doc = pymupdf.open(pdf_path)
    try:
        info = doc.extract_image(xref)
        path = "%s.%s" % (out_path_base, info["ext"])
        with open(path, "wb") as f:
            f.write(info["image"])
        return path
    except Exception:
        return None
    finally:
        doc.close()
