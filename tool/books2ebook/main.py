"""books2ebook — 把 books/ 底下的五本 PDF 轉成與 wenda2_ebook 同風格的靜態電子書。

用法：
    python3 main.py [--books-dir DIR] [--out DIR] [--single N]

預設讀取 repo 的 books/，輸出到 repo 的 ebook/。
"""

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import extract
import parsers
import html_generator
import search_index


def _load_i18n_processor():
    """直接載入共用轉換模組，避開兩個工具各自的 ``config`` 套件名稱衝突。"""
    path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "word2ebook", "utils", "i18n_utils.py"
    ))
    spec = importlib.util.spec_from_file_location("_shared_taiwan_i18n", path)
    if spec is None or spec.loader is None:
        raise ImportError("無法載入共用台灣正體轉換器：%s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.I18nProcessor()


_TAIWAN_CHINESE = _load_i18n_processor()
_HTML_TAG_RE = re.compile(r"(<[^>]*>)", re.DOTALL)
_HTML_RAW_BLOCK_RE = re.compile(
    r"(<(?:script|style)\b[^>]*>.*?</(?:script|style)\s*>)",
    re.IGNORECASE | re.DOTALL,
)
# 標籤內「可能含中文、需要轉繁」的屬性（alt/title/placeholder/aria-label/data-label/
# meta content——SEO description、og:title、og:site_name 等內文跟著轉繁）。
# 值用單引號或雙引號包住皆可比對。
_HTML_ATTR_RE = re.compile(
    r"""\b(alt|title|placeholder|aria-label|data-label|content)\s*=\s*(")(.*?)\2""",
    re.DOTALL,
)


def _convert_s2t(text):
    """轉成台灣常用正體，與 wenda2_ebook 共用同一套規則。"""
    return _TAIWAN_CHINESE.to_traditional(text)


def _convert_tag_attrs(tag):
    """轉換標籤內指定屬性的中文（alt/title/placeholder 等），其餘原樣保留。"""
    return _HTML_ATTR_RE.sub(
        lambda m: '%s=%s%s%s' % (
            m.group(1), m.group(2), _convert_s2t(m.group(3)), m.group(2)),
        tag,
    )


def convert_html_to_trad(html):
    """只轉換 HTML 文字節點與可含中文的屬性值，保留標籤、URL 及 script/style 原文。"""
    converted = []
    for raw_or_html in _HTML_RAW_BLOCK_RE.split(html):
        if not raw_or_html:
            continue
        if _HTML_RAW_BLOCK_RE.fullmatch(raw_or_html):
            converted.append(raw_or_html)
            continue
        converted.extend(
            _convert_tag_attrs(part) if part.startswith("<") else _convert_s2t(part)
            for part in _HTML_TAG_RE.split(raw_or_html)
            if part
        )
    return "".join(converted)


def convert_items_to_trad(items):
    out = []
    for it in items:
        new = dict(it)
        for key in ("title", "content"):
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


def _load_w2e_static_assets():
    """載入 word2ebook 的 StaticAssetsManager（CSS/JS 模組串接的單一真相來源）。

    與 _load_i18n_processor 同樣以 spec_from_file_location 載入，避免兩個
    工具各自的 ``config`` 模組名稱衝突。
    """
    path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "word2ebook", "templates", "static_assets.py"
    ))
    spec = importlib.util.spec_from_file_location("_w2e_static_assets", path)
    if spec is None or spec.loader is None:
        raise ImportError("無法載入 word2ebook StaticAssetsManager：%s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verify_shared_assets():
    """確認共用資產存在於 wenda2_ebook，且沒有落後於 word2ebook SoT。"""
    missing = [p for p in config.SHARED_ASSET_FILES
               if not os.path.exists(os.path.join(config.SHARED_ASSETS_DIR, p))]
    if missing:
        raise SystemExit(
            "❌ ebook 共用的 wenda2_ebook 資產不存在：%s\n"
            "   請先在 tool/word2ebook 執行 gen_all.py 重建 wenda2_ebook。"
            % "、".join(missing)
        )
    sam = _load_w2e_static_assets().StaticAssetsManager()
    stale = []
    for rel, content in (("css/style.css", sam.get_full_css_content()),
                         ("js/script.js", sam.get_full_js_content())):
        with open(os.path.join(config.SHARED_ASSETS_DIR, rel), encoding="utf-8") as f:
            if f.read() != content:
                stale.append(rel)
    if stale:
        print("⚠️  wenda2_ebook 共用資產落後 word2ebook SoT：%s" % "、".join(stale))
        print("   建議先重建 wenda2_ebook（tool/word2ebook/gen_all.py），"
              "否則 ebook 會沿用舊樣式/行為。")
    else:
        print("🔗 共用資產：%s（與 word2ebook SoT 同步，不再輸出第二份）"
              % config.SHARED_ASSETS_BASE)


def copy_assets(out_dir):
    """鋪設 ebook 資產：共用者引用 wenda2_ebook，專屬者留在 ebook/assets/。

    不再輸出第二份（HTML 以 config.SHARED_ASSETS_BASE 的絕對路徑引用）：
    style.css、script.js、i18n-text.js、minisearch.min.js、search-cache.js、
    jieba_rs_wasm.js、jieba_rs_wasm_bg.wasm（清單見 config.SHARED_ASSET_FILES）。

    仍留在 ebook/assets/（ebook 專屬）：
    - assets/css/books.css    ← 本工具自有的附加樣式
    - assets/js/w2e-config.js ← ebook 全書搜尋範圍（取代舊字串 patch）
    - assets/img/bN/          ← 書內插圖（export_images() 產生）
    """
    dst = os.path.join(out_dir, "assets")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(os.path.join(dst, "css"))
    os.makedirs(os.path.join(dst, "js"))

    _verify_shared_assets()

    # ebook 專用執行期設定：預設搜尋範圍涵蓋 內容/標題（01d-search-perform 讀取）
    scope_js = (
        "// 由 books2ebook 生成——ebook 全書搜尋預設範圍（需在 script.js 前載入）\n"
        "window.W2E_SEARCH_SCOPE_TYPES = %s;\n"
        % json.dumps(config.EBOOK_SEARCH_SCOPE_TYPES)
    )
    with open(os.path.join(dst, "js", "w2e-config.js"), "w", encoding="utf-8") as f:
        f.write(scope_js)
    print("🩹 搜尋範圍設定：assets/js/w2e-config.js（取代舊字串 patch）")

    # 附加樣式
    extra_css = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "books.css")
    if os.path.exists(extra_css):
        shutil.copy(extra_css, os.path.join(dst, "css", "books.css"))

    # favicon（沿用既有來源；favicon 內容穩定，非本流程的風險點）
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
            prev_book=prev_bc, next_book=next_bc, out_dir=out_dir)
        with open(os.path.join(out_dir, bc.filename), "w", encoding="utf-8") as f:
            f.write(html_s)
        # 繁版：以 is_trad=True 產生 _trad 連結，再用 OpenCC 轉換文字
        html_t, items_t = html_generator.render_chapter(
            bc, blocks, imap, is_trad=True,
            prev_book=prev_bc, next_book=next_bc, out_dir=out_dir)
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
