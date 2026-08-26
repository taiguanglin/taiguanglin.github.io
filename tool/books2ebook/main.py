"""books2ebook — 把 books/ 底下的五本 PDF 轉成與 wenda2_ebook 同風格的靜態電子書。

用法：
    python3 main.py [--books-dir DIR] [--out DIR] [--single N]

預設讀取 repo 的 books/，輸出到 repo 的 ebook/。
"""

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import extract
import parsers
import html_generator
import search_index


def _convert_s2t(text):
    from opencc import OpenCC
    if not hasattr(_convert_s2t, "_cc"):
        _convert_s2t._cc = OpenCC("s2t")
    return _convert_s2t._cc.convert(text)


def convert_html_to_trad(html):
    """把簡體 HTML 轉成繁體（標籤/屬性內的 ASCII 不受影響）。"""
    return _convert_s2t(html)


def convert_items_to_trad(items):
    out = []
    for it in items:
        new = dict(it)
        for key in ("title", "content", "context"):
            if key in new and new[key]:
                new[key] = _convert_s2t(new[key])
        out.append(new)
    return out


def parse_books(books_dir):
    """解析所有書 → [{config, blocks}]"""
    result = []
    for bc in config.BOOKS:
        pdf = os.path.join(books_dir, bc.pdf)
        if not os.path.exists(pdf):
            raise SystemExit("找不到 PDF：%s" % pdf)
        print("📖 解析 %s ..." % bc.title)
        lines, images = extract.extract_lines(pdf, skip_pages=bc.skip_pages)
        toc_pages = extract.find_toc_pages(lines)
        blocks = parsers.parse_book(bc.parser, lines, toc_pages, images)
        blocks = html_generator.annotate(blocks)
        n_qa = sum(1 for b in blocks if b["kind"] == "qa")
        print("   ✅ %d 個區塊（問答 %d）" % (len(blocks), n_qa))
        result.append({"config": bc, "blocks": blocks})
    return result


def export_images(books_meta, books_dir, out_dir):
    """把各書插圖匯出到 assets/img/，回傳 {book_number: {xref: rel_src}}。"""
    img_root = os.path.join(out_dir, "assets", "img")
    maps = {}
    for bm in books_meta:
        bc = bm["config"]
        pdf = os.path.join(books_dir, bc.pdf)
        book_dir = os.path.join(img_root, "b%d" % bc.number)
        xref_map = {}
        for b in bm["blocks"]:
            if b["kind"] != "img":
                continue
            xref = b["xref"]
            if xref in xref_map:
                continue
            os.makedirs(book_dir, exist_ok=True)
            base = os.path.join(book_dir, "img_%d" % xref)
            rel_base = "assets/img/b%d/img_%d" % (bc.number, xref)
            dest = None
            for ext in ("png", "jpeg", "jpg", "gif", "webp"):
                cand = base + "." + ext
                if os.path.exists(cand):
                    dest = cand
                    break
            if not dest:
                saved = extract.extract_image(pdf, xref, base)
                if saved:
                    dest = saved
                    print("   🖼 %s" % saved)
                else:
                    print("   ⚠️ 圖片匯出失敗：xref=%d（%s）" % (xref, bc.title))
                    continue
            xref_map[xref] = os.path.relpath(dest, out_dir).replace(os.sep, "/")
        maps[bc.number] = xref_map
    return maps


def copy_assets(out_dir):
    """沿用 wenda2_ebook 的 CSS/JS 資產，加上本工具附加的 books.css。"""
    src = config.STYLE_ASSETS_SRC
    dst = os.path.join(out_dir, "assets")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    # 附加樣式
    extra_css = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "books.css")
    if os.path.exists(extra_css):
        shutil.copy(extra_css, os.path.join(dst, "css", "books.css"))

    # 讓「内容 / 标题」類型的搜尋結果在預設範圍也可見
    script_path = os.path.join(dst, "js", "script.js")
    with open(script_path, "r", encoding="utf-8") as f:
        js = f.read()
    patches = [
        # 搜尋範圍：預設「全部」也要涵蓋 content / heading
        (": ['question', 'answer'];",
         ": ['question', 'answer', 'content', 'heading'];",
         "已調整搜尋範圍過濾"),
        # 首頁目錄預設顯示第 1 層（章節頁維持第 3 層）
        ("const defaultLevel = isChapterPage ? '3' : '2';",
         "const defaultLevel = isChapterPage ? '3' : '1';",
         "首頁目錄預設第 1 層"),
    ]
    for old, new, label in patches:
        if js.count(old) == 1:
            js = js.replace(old, new)
            print("🩹 %s（ebook 專用副本）" % label)
        elif new in js:
            pass
        else:
            print("⚠️ 找不到待 patch 字串：%s" % label)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(js)

    # favicon
    favicon_src = os.path.join(config.REPO_ROOT, "wenda2_ebook", "favicon.ico")
    if os.path.exists(favicon_src):
        shutil.copy(favicon_src, os.path.join(out_dir, "favicon.ico"))


def build(books_dir=None, out_dir=None):
    books_dir = books_dir or config.DEFAULT_BOOKS_DIR
    out_dir = out_dir or config.DEFAULT_OUTPUT_DIR

    os.makedirs(out_dir, exist_ok=True)
    # 先鋪資產（會重建 assets/），再匯出插圖，避免被清掉
    copy_assets(out_dir)
    books_meta = parse_books(books_dir)
    print("🖼 匯出插圖 ...")
    image_maps = export_images(books_meta, books_dir, out_dir)

    source_pdfs = [bc.pdf for bc in config.BOOKS]

    all_items = {"simp": [], "trad": []}
    for i, bm in enumerate(books_meta):
        bc = bm["config"]
        blocks = bm["blocks"]
        prev_bc = books_meta[i - 1]["config"] if i > 0 else None
        next_bc = books_meta[i + 1]["config"] if i + 1 < len(books_meta) else None
        imap = image_maps.get(bc.number, {})

        html_s, items_s = html_generator.render_chapter(
            bc, blocks, imap, is_trad=False,
            prev_book=prev_bc, next_book=next_bc)
        with open(os.path.join(out_dir, bc.filename), "w", encoding="utf-8") as f:
            f.write(html_s)
        # 繁版：以 is_trad=True 產生 _trad 連結，再用 OpenCC 轉換文字
        html_t, items_t = html_generator.render_chapter(
            bc, blocks, imap, is_trad=True,
            prev_book=prev_bc, next_book=next_bc)
        with open(os.path.join(out_dir, bc.filename_trad), "w", encoding="utf-8") as f:
            f.write(convert_html_to_trad(html_t))
        all_items["simp"].extend(items_s)
        all_items["trad"].extend(convert_items_to_trad(items_t))
        print("✅ %s → %s / %s" % (bc.title, bc.filename, bc.filename_trad))

    idx_s = html_generator.render_index(books_meta, source_pdfs, is_trad=False)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(idx_s)
    idx_t = html_generator.render_index(books_meta, source_pdfs, is_trad=True)
    with open(os.path.join(out_dir, "index_trad.html"), "w", encoding="utf-8") as f:
        f.write(convert_html_to_trad(idx_t))


    p1 = search_index.write_search_index(out_dir, all_items["simp"], is_trad=False)
    p2 = search_index.write_search_index(out_dir, all_items["trad"], is_trad=True)
    print("🔍 搜尋索引：%d / %d 筆" % (len(all_items["simp"]), len(all_items["trad"])))
    print("🎉 完成！輸出目錄：%s" % out_dir)


def main():
    ap = argparse.ArgumentParser(description="books PDF → static ebook")
    ap.add_argument("--books-dir", default=config.DEFAULT_BOOKS_DIR)
    ap.add_argument("--out", default=config.DEFAULT_OUTPUT_DIR)
    args = ap.parse_args()
    build(args.books_dir, args.out)


if __name__ == "__main__":
    main()
