#!/usr/bin/env python3
"""講經系列 PDF 組裝：合併 + 檔首可點擊 TOC。

產出到 books/：
  - 感恩与讲经（單一 PDF，補檔首 TOC）
  - 四十二章經（單一 PDF，補 TOC）
  - 楞伽經（單一 PDF，補 TOC）
  - 六祖壇經（兩 PDF 合併，補 TOC 對應合併後頁數）
  - 楞嚴經（21 個 docx→PDF→合併，補 TOC）

策略：
1. 先計算 TOC 頁數 toc_num（依條目數，每頁約 36 條；不足一頁也佔一頁）。
2. 新建輸出 doc → 先 insert_pdf(內容) → 再在前方插入 TOC 頁（複製頁面語意較繁，改為：
   新建 doc → 依序 insert 空白 TOC 頁 + insert_pdf(內容)，最後在 TOC 頁上填文字與 link）。
   因 insert_link 需目標頁存在，故「先 insert 內容、再寫 TOC 頁文字與連結」。

實際做法：
   out = open()
   out.insert_pdf(content_doc)              # content 先進來，頁 0..N-1
   然後用 out.insert_page(-1, width,height) 在「最前面」插 TOC 頁 → 覆蓋頁序
   （insert_page 在指定 index 插空白頁，會把後續往後推）
   最後對 TOC 頁（index 0..toc_num-1）寫文字 + insert_link（此時內容頁都在，頁碼有效）。
"""
import os
import re
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
    """toc_entries: [(text, target_page_1based)]。在 out 最前插 TOC 頁並寫文字+連結。
    target_page_1based 是「內容頁在最終輸出中的 1-based 頁碼」（TOC 頁數已算入）。
    """
    toc_num = max(1, (len(toc_entries) + 36) // 36)
    # 在最前面插入 toc_num 張空白頁
    for _ in range(toc_num):
        out.insert_page(0, width=595, height=842)

    # 寫 TOC 文字與連結（此時內容已在，頁碼 0-based = target-1）
    y = 60
    pidx = 0
    page = out[0]
    page.insert_text((220, y), title, fontsize=18, fontname=TITLE_FONT)
    y += 40
    for text, target in toc_entries:
        if y > 800:
            pidx += 1
            page = out[pidx]
            y = 50
        page.insert_text((70, y), text, fontsize=11, fontname=TITLE_FONT)
        rect = pymupdf.Rect(70, y - 11, 420, y + 2)
        page.insert_link({
            "kind": pymupdf.LINK_GOTO,
            "from": rect,
            "page": target - 1,
            "to": pymupdf.Point(0, 0),
        })
        y += 21


def build_single(entry_texts, srcdoc_path, out_pdf, title):
    """entry_texts: [(text, src_page_1based)]。"""
    src = pymupdf.open(srcdoc_path)
    toc_num = max(1, (len(entry_texts) + 36) // 36)
    # 目標頁（最終 1-based）= TOC 頁數 + 原始頁碼
    toc_entries = [(t, toc_num + sp) for t, sp in entry_texts]
    out = pymupdf.open()
    out.insert_pdf(src)
    write_toc_links(out, toc_entries, title)
    # 設定 PDF 大綱（bookmarks）
    outline = [[1, t, target] for t, target in toc_entries]
    out.set_toc(outline)
    out.save(out_pdf)
    out.close()
    src.close()
    print("✅ %s (%d pages)" % (os.path.basename(out_pdf), pymupdf.open(out_pdf).page_count))


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
    """用 Microsoft Word (AppleScript) 把 docx/doc 轉成 PDF。
    寫成 .applescript 檔，再用 osascript 執行（避免 -e 對中文路徑/全形括號轉義問題）。

    每次呼叫都用 Documents.Open（明確物件），結束後關閉，盡量不重用同一個 process 跨次。
    若 Connection is invalid 則先 killall Word 再重試一次。"""
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
        # Word 連線可能掉了，killall 重試一次
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

    g = os.path.join(SRC, "2024年4月14日Tai师父讲经 · 感恩与讲经（群文件版）.pdf")
    build_single([("感恩与讲经（2024年4月14日）", 1)], g,
                 os.path.join(BOOKSDIR, "感恩与讲经（2024年4月14日）.pdf"),
                 "感恩与讲经")

    s = os.path.join(SRC, "Tai师父讲《四十二章经》/文本/2024年Tai师父讲 《四十二章经》（群文件版）24-12-15.pdf")
    entries = [("《四十二章经》第%d讲" % n, sp) for n, sp in sorted(SISHIER_STARTS.items())]
    build_single(entries, s, os.path.join(BOOKSDIR, "06 Tai师父讲《四十二章经》.pdf"),
                 "Tai师父讲《四十二章经》")

    l = os.path.join(SRC, "Tai师父讲《楞伽经》/楞伽经文字（1-42）/2024-2025Tai师父讲《楞伽经》（群文件版）-25.8.6.pdf")
    entries = [("《楞伽经》第%d讲" % n, sp) for n, sp in sorted(LENGQIE_STARTS.items())]
    build_single(entries, l, os.path.join(BOOKSDIR, "07 Tai师父讲《楞伽经》.pdf"),
                 "Tai师父讲《楞伽经》")

    build_tanjing(os.path.join(BOOKSDIR, "08 Tai师父讲《六祖坛经》.pdf"))
    build_lengyan(os.path.join(BOOKSDIR, "09 Tai师父讲《楞严经》(未完).pdf"))


if __name__ == "__main__":
    main()