#!/usr/bin/env python3
"""講經系列 PDF 組裝：合併 + 檔首可點擊 TOC（含頁數）。

產出到 books/：
  - 感恩与讲经：單一 PDF，補檔首 TOC（含頁數）
  - 四十二章經：原 PDF 已含目錄 → 直接複製，不再加 TOC（避免兩份目錄）
  - 楞伽經：原 PDF 已含目錄 → 直接複製，不再加 TOC
  - 六祖壇經：兩 PDF 合併 → 新增檔首 TOC（含頁數）
  - 楞嚴經：21 個 docx→PDF→合併 → 新增檔首 TOC（含頁數）

TOC 條目以「標題 …… 頁碼」呈現，文字右側附實際頁碼；同時以 internal link
跳轉到正確頁 + set_toc 建立 PDF 大綱（bookmarks）。
"""
import os
import re
import shutil
import subprocess
import time

try:
    import pymupdf
except ImportError:  # PyMuPDF < 1.24 only exposes the legacy module name.
    import fitz as pymupdf

SRC = os.path.expanduser("~/Downloads")
BOOKSDIR = "/Users/paul/tai/taiguanglin.github.io/books"
TITLE_FONT = "china-s"  # 內建 CJK 簡體字型

TOC_TITLE_SIZE = 17
TOC_ENTRY_SIZE = 11
TOC_MARGIN = 70
TOC_GAP = 6
TOC_FIRST_ENTRY_Y = 102
TOC_LINE_HEIGHT = 21
TOC_BOTTOM_MARGIN = 60

# 正文頁碼：置中於頁尾，數字用 Helvetica（books2ebook 依此字型濾掉頁碼行）。
PAGE_NUM_FONT = "helv"
PAGE_NUM_SIZE = 9
PAGE_NUM_FROM_BOTTOM = 30
_DIGITS_ONLY_RE = re.compile(r"^\d{1,4}$")

LENGQIE_STARTS = {1:5,2:16,3:29,4:41,5:54,6:69,7:89,8:101,9:112,10:124,
    11:138,12:151,13:166,14:182,15:197,16:210,17:224,18:240,19:253,20:267,
    21:280,22:292,23:307,24:321,25:334,26:349,27:366,28:382,29:395,30:408,
    31:423,32:437,33:450,34:466,35:480,36:492,37:505,38:518,39:534,40:547,
    41:559,42:571}
SISHIER_STARTS = {1:3,2:16,3:29,4:42,5:54,6:66,7:87,8:99,9:113,10:125,
    11:139,12:151,13:165,14:180}
TANJING1_STARTS = {1:1,2:16,3:27,4:40,5:55,6:68,7:81,8:94,9:108,10:121,
    11:134,12:147,13:165,14:179,15:191,16:205,17:220,18:238}
TANJING2_STARTS = {19:1,20:16,21:33,22:47,23:61,24:83,25:98,26:113,27:128}


def normalize_pdf_page_size_in_place(path, target_rect):
    """把 PDF 每頁統一成 target_rect 尺寸，原子取代來源檔。"""
    src = pymupdf.open(path)
    target_size = (target_rect.width, target_rect.height)
    changed = False
    for page in src:
        changed = fit_page_content_to_size(page, target_rect) or changed
    if not changed:
        src.close()
        return False

    tmp_path = path + ".normalized.tmp.pdf"
    src.save(tmp_path, garbage=4, deflate=True)
    src.close()
    os.replace(tmp_path, path)
    print("🔧 已統一來源頁面尺寸：%s" % path)
    return True


def content_bbox(page):
    """頁面上實際有內容（文字/繪圖/圖片）的範圍，找不到時回 None。"""
    bbox = None
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", ()):
            for span in line["spans"]:
                if not span["text"].strip():
                    continue
                rect = pymupdf.Rect(span["bbox"])
                bbox = rect if bbox is None else bbox | rect
    for drawing in page.get_drawings():
        rect = pymupdf.Rect(drawing["rect"])
        if not rect.is_empty:
            bbox = rect if bbox is None else bbox | rect
    for image in page.get_images(full=True):
        for rect in page.get_image_rects(image[0]):
            bbox = rect if bbox is None else bbox | rect
    return bbox


def fit_page_content_to_size(page, target_rect):
    """直接變換頁面內容流，保留可擷取文字結構與行序。

    只有在內容超出目標頁面時才縮小；否則維持原始字級與版心位置，僅裁掉多餘
    留白，避免統一尺寸後版面被整體縮小、四周空白變大。
    """
    source_rect = page.rect
    target_width, target_height = target_rect.width, target_rect.height
    if (
        abs(source_rect.width - target_width) < 0.01
        and abs(source_rect.height - target_height) < 0.01
    ):
        return False

    bbox = content_bbox(page)
    if bbox is None or bbox.is_empty:
        scale = min(target_width / source_rect.width,
                    target_height / source_rect.height)
        left = (target_width - source_rect.width * scale) / 2
        top = (target_height - source_rect.height * scale) / 2
    else:
        scale = min(1.0, target_width / bbox.width, target_height / bbox.height)
        left = bbox.x0 * scale
        top = bbox.y0 * scale
        if left < 0 or left + bbox.width * scale > target_width:
            left = (target_width - bbox.width * scale) / 2
        if top < 0 or top + bbox.height * scale > target_height:
            top = (target_height - bbox.height * scale) / 2
        # 內容流用左下原點，故先換算成目標頁面的位移量。
        left -= bbox.x0 * scale
        top = target_height - top - scale * (source_rect.height - bbox.y0)

    matrix = ("%g 0 0 %g %g %g cm\n" % (scale, scale, left, top)).encode("ascii")
    doc = page.parent
    for xref in page.get_contents():
        stream = doc.xref_stream(xref)
        doc.update_stream(xref, b"q\n" + matrix + stream + b"\nQ\n")
    page.set_mediabox(pymupdf.Rect(0, 0, target_width, target_height))
    return True


def insert_pdf_with_page_size(out, src, target_rect):
    """加入 PDF 後統一頁面尺寸，保留來源文字內容流。"""
    first_inserted = out.page_count
    out.insert_pdf(src)
    for page_number in range(first_inserted, out.page_count):
        fit_page_content_to_size(out[page_number], target_rect)


def text_width(text, fontsize):
    """TITLE_FONT 為等寬全形 CJK 字型，點與數字同樣佔一個字寬。"""
    return pymupdf.get_text_length(text, fontname=TITLE_FONT, fontsize=fontsize)


def toc_entries_per_page(page_height):
    usable = page_height - TOC_BOTTOM_MARGIN - TOC_FIRST_ENTRY_Y
    return max(1, int(usable // TOC_LINE_HEIGHT) + 1)


def toc_page_count(entry_count, page_height):
    per_page = toc_entries_per_page(page_height)
    return max(1, -(-entry_count // per_page))


def clear_source_page_numbers(doc, skip):
    """移除來源殘留的頁碼（楞嚴各講 docx 各自從 1 起算），避免與統一頁碼並存。"""
    removed = 0
    for index in range(skip, doc.page_count):
        page = doc[index]
        found = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", ()):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                if not _DIGITS_ONLY_RE.match(text):
                    continue
                if max(s["size"] for s in spans) >= 11.5:
                    continue
                if line["bbox"][1] < page.rect.height * 0.85:
                    continue
                found.append(pymupdf.Rect(line["bbox"]))
        if not found:
            continue
        for rect in found:
            page.add_redact_annot(rect)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        removed += len(found)
    return removed


def stamp_page_numbers(doc, skip):
    """在正文頁尾置中標上實體頁碼；TOC 頁本身不標。"""
    for index in range(skip, doc.page_count):
        page = doc[index]
        number = str(index + 1)
        width = pymupdf.get_text_length(number, fontname=PAGE_NUM_FONT,
                                        fontsize=PAGE_NUM_SIZE)
        page.insert_text(
            ((page.rect.width - width) / 2,
             page.rect.height - PAGE_NUM_FROM_BOTTOM),
            number, fontsize=PAGE_NUM_SIZE, fontname=PAGE_NUM_FONT)


def write_toc_links(out, toc_entries, title, page_size=(595, 842)):
    """toc_entries: [(text, target_page_1based)]。在最前插 TOC 頁、寫「標題 …… 頁碼」、
    加 internal link。target_page_1based 為最終輸出頁碼（已含 TOC 頁數）。"""
    page_width, page_height = page_size
    toc_num = toc_page_count(len(toc_entries), page_height)
    for _ in range(toc_num):
        out.insert_page(0, width=page_width, height=page_height)

    number_right = page_width - TOC_MARGIN
    dot_width = text_width(".", TOC_ENTRY_SIZE)
    pidx = 0
    page = out[0]
    page.insert_text(((page_width - text_width(title, TOC_TITLE_SIZE)) / 2, 60),
                     title, fontsize=TOC_TITLE_SIZE, fontname=TITLE_FONT)
    y = TOC_FIRST_ENTRY_Y
    for text, target in toc_entries:
        if y > page_height - TOC_BOTTOM_MARGIN:
            pidx += 1
            page = out[pidx]
            y = 50
        # 標題（左）+ 虛線引導 + 頁碼（右對齊）；點數由實際文字寬度推算，
        # 否則等寬全形的點會蓋掉頁碼。
        number = str(target)
        number_x = number_right - text_width(number, TOC_ENTRY_SIZE)
        dots_x = TOC_MARGIN + text_width(text, TOC_ENTRY_SIZE) + TOC_GAP
        dot_count = max(0, int((number_x - TOC_GAP - dots_x) // dot_width))
        page.insert_text((TOC_MARGIN, y), text,
                         fontsize=TOC_ENTRY_SIZE, fontname=TITLE_FONT)
        if dot_count:
            page.insert_text((dots_x, y), "." * dot_count,
                             fontsize=TOC_ENTRY_SIZE, fontname=TITLE_FONT)
        page.insert_text((number_x, y), number,
                         fontsize=TOC_ENTRY_SIZE, fontname=TITLE_FONT)
        rect = pymupdf.Rect(TOC_MARGIN, y - TOC_ENTRY_SIZE, number_right, y + 2)
        page.insert_link({
            "kind": pymupdf.LINK_GOTO,
            "from": rect,
            "page": target - 1,
            "to": pymupdf.Point(0, 0),
        })
        y += TOC_LINE_HEIGHT


def build_single(entry_texts, srcdoc_path, out_pdf, title):
    """entry_texts: [(text, src_page_1based)]。TOC + 內容。"""
    src = pymupdf.open(srcdoc_path)
    body_rect = src[0].rect
    toc_num = toc_page_count(len(entry_texts), body_rect.height)
    toc_entries = [(t, toc_num + sp) for t, sp in entry_texts]
    out = pymupdf.open()
    out.insert_pdf(src)
    write_toc_links(out, toc_entries, title,
                    page_size=(body_rect.width, body_rect.height))
    clear_source_page_numbers(out, toc_num)
    stamp_page_numbers(out, toc_num)
    out.set_toc([[1, t, target] for t, target in toc_entries])
    out.save(out_pdf)
    out.close(); src.close()
    n = pymupdf.open(out_pdf).page_count
    pymupdf.open(out_pdf).close()
    print("✅ %s (%d pages)" % (os.path.basename(out_pdf), n))


def copy_original(src, out_pdf):
    """原 PDF 已含目錄 → 直接複製，不新增 TOC。"""
    shutil.copyfile(src, out_pdf)
    n = pymupdf.open(out_pdf).page_count
    print("✅ %s (%d pages, 保留原目錄)" % (os.path.basename(out_pdf), n))


def build_tanjing(out_pdf):
    p1 = os.path.join(SRC, "Tai师父讲《六祖坛经》/文本/Tai师父讲经·坛经（1-18）.pdf")
    p2 = os.path.join(SRC, "Tai师父讲《六祖坛经》/文本/Tai师父讲坛经（19-27）.pdf")
    src1 = pymupdf.open(p1)
    target_rect = src1[0].rect
    normalize_pdf_page_size_in_place(p2, target_rect)
    src2 = pymupdf.open(p2)
    n1 = src1.page_count
    entries = [("《六祖坛经》第%d讲" % n, sp) for n, sp in sorted(TANJING1_STARTS.items())]
    entries += [("《六祖坛经》第%d讲" % n, n1 + sp) for n, sp in sorted(TANJING2_STARTS.items())]
    toc_num = toc_page_count(len(entries), target_rect.height)
    toc_entries = [(t, toc_num + sp) for t, sp in entries]
    out = pymupdf.open()
    insert_pdf_with_page_size(out, src1, target_rect)
    insert_pdf_with_page_size(out, src2, target_rect)
    write_toc_links(
        out, toc_entries, "Tai师父讲《六祖坛经》",
        page_size=(target_rect.width, target_rect.height),
    )
    clear_source_page_numbers(out, toc_num)
    stamp_page_numbers(out, toc_num)
    out.set_toc([[1, t, target] for t, target in toc_entries])
    out.save(out_pdf)
    out.close(); src1.close(); src2.close()
    print("✅ %s (%d pages)" % (os.path.basename(out_pdf), pymupdf.open(out_pdf).page_count))


def word_to_pdf(docx_path, out_path):
    """Microsoft Word (AppleScript) → PDF。寫成 .applescript 再執行。"""
    script = (
        'tell application "Microsoft Word"\n'
        '  open POSIX file "%s"\n' % docx_path +
        '  delay 1\n'
        '  set d to active document\n'
        '  save as d file name "%s" file format format PDF\n' % out_path +
        '  close d saving no\n'
        'end tell\n'
    )
    tmp_script = "/tmp/_word2pdf.applescript"
    with open(tmp_script, "w", encoding="utf-8") as f:
        f.write(script)
    try:
        subprocess.run(["osascript", tmp_script], check=True, timeout=60)
    except subprocess.CalledProcessError:
        subprocess.run(["killall", "Microsoft Word"], check=False)
        time.sleep(2)
        subprocess.run(["osascript", tmp_script], check=True, timeout=60)


def build_lengyan(out_pdf):
    txtdir = os.path.join(SRC, "Tai师父讲《楞严经》(未完)/文本(更新到21,未講完)")
    tmpdir = "/tmp/lengyan_pdf"
    os.makedirs(tmpdir, exist_ok=True)
    pdfs = []
    for n in range(1, 22):
        doc = os.path.join(txtdir, "【校对稿】楞严经（%d）.docx" % n)
        if not os.path.exists(doc):
            doc = os.path.join(txtdir, "【校对稿】楞严经（%d）.doc" % n)
        tmp = os.path.join(tmpdir, "%02d.pdf" % n)
        if not os.path.exists(tmp):
            word_to_pdf(doc, tmp)
            print("   docx→pdf %02d" % n)
        pdfs.append(tmp)

    merged = pymupdf.open()
    starts = []
    acc = 0
    for n, tmp in enumerate(pdfs, 1):
        d = pymupdf.open(tmp)
        starts.append((n, acc + 1))
        merged.insert_pdf(d)
        acc += d.page_count
        d.close()
    body_rect = merged[0].rect
    toc_num = toc_page_count(len(starts), body_rect.height)
    toc_entries = [("《楞严经》第%d讲" % n, toc_num + sp) for n, sp in starts]
    out = pymupdf.open()
    out.insert_pdf(merged)
    write_toc_links(out, toc_entries, "Tai师父讲《楞严经》(未完)",
                    page_size=(body_rect.width, body_rect.height))
    clear_source_page_numbers(out, toc_num)
    stamp_page_numbers(out, toc_num)
    out.set_toc([[1, t, target] for t, target in toc_entries])
    out.save(out_pdf)
    out.close(); merged.close()
    print("✅ %s (%d pages)" % (os.path.basename(out_pdf), pymupdf.open(out_pdf).page_count))


def main():
    os.makedirs(BOOKSDIR, exist_ok=True)

    # 感恩与讲经：補 TOC（單一講，頁數 2）
    g = os.path.join(SRC, "2024年4月14日Tai师父讲经 · 感恩与讲经（群文件版）.pdf")
    build_single([("感恩与讲经", 1)], g,
                 os.path.join(BOOKSDIR, "感恩与讲经（2024年4月14日）.pdf"),
                 "感恩与讲经")

    # 四十二章經：原 PDF 已含目錄 → 直接複製
    s = os.path.join(SRC, "Tai师父讲《四十二章经》/文本/2024年Tai师父讲 《四十二章经》（群文件版）24-12-15.pdf")
    copy_original(s, os.path.join(BOOKSDIR, "06 Tai师父讲《四十二章经》.pdf"))

    # 楞伽經：原 PDF 已含目錄 → 直接複製
    l = os.path.join(SRC, "Tai师父讲《楞伽经》/楞伽经文字（1-42）/2024-2025Tai师父讲《楞伽经》（群文件版）-25.8.6.pdf")
    copy_original(l, os.path.join(BOOKSDIR, "07 Tai师父讲《楞伽经》.pdf"))

    build_tanjing(os.path.join(BOOKSDIR, "08 Tai师父讲《六祖坛经》.pdf"))
    build_lengyan(os.path.join(BOOKSDIR, "09 Tai师父讲《楞严经》(未完).pdf"))


if __name__ == "__main__":
    main()