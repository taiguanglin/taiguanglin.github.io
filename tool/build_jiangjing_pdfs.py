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
import shutil
import subprocess
import time

import pymupdf

SRC = os.path.expanduser("~/Downloads")
BOOKSDIR = "/Users/paul/tai/taiguanglin.github.io/books"
TITLE_FONT = "china-s"  # 內建 CJK 簡體字型

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


def write_toc_links(out, toc_entries, title):
    """toc_entries: [(text, target_page_1based)]。在最前插 TOC 頁、寫「標題 …… 頁碼」、
    加 internal link。target_page_1based 為最終輸出頁碼（已含 TOC 頁數）。"""
    toc_num = max(1, (len(toc_entries) + 36) // 36)
    for _ in range(toc_num):
        out.insert_page(0, width=595, height=842)

    y = 60
    pidx = 0
    page = out[0]
    page.insert_text((210, y), title, fontsize=17, fontname=TITLE_FONT)
    y += 42
    for text, target in toc_entries:
        if y > 800:
            pidx += 1
            page = out[pidx]
            y = 50
        # 標題（左）+ 虛線引導 + 頁碼（右）
        title_text = "%s %s" % (text, "." * max(3, 42 - len(text) * 1))
        page.insert_text((70, y), title_text, fontsize=11, fontname=TITLE_FONT)
        page.insert_text((500, y), str(target), fontsize=11, fontname=TITLE_FONT)
        rect = pymupdf.Rect(70, y - 11, 520, y + 2)
        page.insert_link({
            "kind": pymupdf.LINK_GOTO,
            "from": rect,
            "page": target - 1,
            "to": pymupdf.Point(0, 0),
        })
        y += 21


def build_single(entry_texts, srcdoc_path, out_pdf, title):
    """entry_texts: [(text, src_page_1based)]。TOC + 內容。"""
    src = pymupdf.open(srcdoc_path)
    toc_num = max(1, (len(entry_texts) + 36) // 36)
    toc_entries = [(t, toc_num + sp) for t, sp in entry_texts]
    out = pymupdf.open()
    out.insert_pdf(src)
    write_toc_links(out, toc_entries, title)
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
    src2 = pymupdf.open(p2)
    n1 = src1.page_count
    entries = [("《六祖坛经》第%d讲" % n, sp) for n, sp in sorted(TANJING1_STARTS.items())]
    entries += [("《六祖坛经》第%d讲" % n, n1 + sp) for n, sp in sorted(TANJING2_STARTS.items())]
    toc_num = max(1, (len(entries) + 36) // 36)
    toc_entries = [(t, toc_num + sp) for t, sp in entries]
    out = pymupdf.open()
    out.insert_pdf(src1)
    out.insert_pdf(src2)
    write_toc_links(out, toc_entries, "Tai师父讲《六祖坛经》")
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
    toc_num = max(1, (len(starts) + 36) // 36)
    toc_entries = [("《楞严经》第%d讲（未完）" % n, toc_num + sp) for n, sp in starts]
    out = pymupdf.open()
    out.insert_pdf(merged)
    write_toc_links(out, toc_entries, "Tai师父讲《楞严经》(未完)")
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