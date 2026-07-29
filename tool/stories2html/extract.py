#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 stories/ 底下的 PDF / DOCX / DOC / TXT 抽成結構化 JSON（區塊清單）。

輸出：
  tool/stories2html/build/<slug>.json   區塊清單
  stories/assets/img/<slug>/*.jpg|png   內文圖片

區塊型別：
  {"t": "h2"|"h3", "text": ...}
  {"t": "p", "text": ..., "quote": bool}
  {"t": "li", "text": ...}
  {"t": "img", "src": ..., "w": int, "h": int}
  {"t": "caption", "text": ...}
  {"t": "table", "rows": [[...]], "head": int}
"""
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from xml.etree import ElementTree as ET

import fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docs import DOCS  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build")
IMGROOT = os.path.join(ROOT, "stories", "assets", "img")

MAX_IMG_W = 1800
CJK = r"\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef"


# --------------------------------------------------------------------------
# 文字正規化
# --------------------------------------------------------------------------
def clean(s, pdf=False):
    """整理空白。

    PDF 抽字時，字體切換會在中文與英數字之間插入原文沒有的空白，必須清掉；
    Word／純文字檔的空白是作者自己打的，只做收斂與去除首尾的全角空白（縮排）。
    """
    s = s.replace("\u00a0", " ").replace("\ufeff", "")
    if pdf:
        s = s.replace("\u3000", "")
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"(?<=[0-9A-Za-z%）)」』】》])[ ]+(?=[" + CJK + r"])", "", s)
        s = re.sub(r"(?<=[" + CJK + r"])[ ]+(?=[0-9A-Za-z（(「『【《])", "", s)
        s = re.sub(r"(?<=[" + CJK + r"])[ ]+(?=[" + CJK + r"])", "", s)
        return s.strip()
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip().strip("\u3000").strip()


def join_lines(parts):
    out = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if not out:
            out = p
            continue
        a, b = out[-1], p[0]
        need_space = (a.isascii() and (a.isalnum() or a in ".,;:")) and (b.isascii() and b.isalnum())
        out += (" " if need_space else "") + p
    return clean(out, pdf=True)


# --------------------------------------------------------------------------
# 圖片
# --------------------------------------------------------------------------
def save_pixmap(pix, path):
    while pix.width > MAX_IMG_W:
        pix.shrink(1)
    if pix.alpha or pix.n == 1:
        pix.save(path[: path.rfind(".")] + ".png")
        return path[: path.rfind(".")] + ".png", pix.width, pix.height
    # 全頁掃描檔壓得重一點，其餘保留較高畫質
    pix.save(path, jpg_quality=76 if pix.width > 1200 else 85)
    return path, pix.width, pix.height


def webp_size(data):
    """WebP 沒有被 MuPDF 支援，自行讀出寬高（lossy VP8 / lossless VP8L / VP8X）。"""
    tag = data[12:16]
    if tag == b"VP8 ":
        w = int.from_bytes(data[26:28], "little") & 0x3FFF
        h = int.from_bytes(data[28:30], "little") & 0x3FFF
        return w, h
    if tag == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if tag == b"VP8X":
        return (int.from_bytes(data[24:27], "little") & 0xFFFFFF) + 1, \
               (int.from_bytes(data[27:30], "little") & 0xFFFFFF) + 1
    return 0, 0


def save_page_image(doc, page, rect, xref, transform, outdir, name):
    """輸出一張內文圖片。

    預設直接取出內嵌影像，畫質最好、檔案也最小。但 PDF 可能對影像套用
    旋轉或鏡射矩陣，此時取出的原圖方向和頁面上看到的不一樣，只能改用
    裁切重繪；解析度對齊原圖寬度，避免無謂放大。
    """
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, name + ".jpg")
    a, b, c, d = transform[:4]
    rotated = max(abs(b), abs(c)) > 1e-3 or a < 0 or d > 0

    if rotated:
        src_w = doc.extract_image(xref)["width"]
        dpi = max(72, min(400, round(min(src_w, MAX_IMG_W) / max(rect.width, 1) * 72)))
        pix = page.get_pixmap(clip=rect, dpi=dpi, alpha=False)
    else:
        pix = fitz.Pixmap(doc, xref)
        if pix.colorspace and pix.colorspace.name == "DeviceCMYK":
            pix = fitz.Pixmap(fitz.csRGB, pix)

    path, w, h = save_pixmap(pix, out)
    return {"src": os.path.basename(path), "w": w, "h": h}


def save_image_bytes(data, outdir, name):
    os.makedirs(outdir, exist_ok=True)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        path = os.path.join(outdir, name + ".webp")
        with open(path, "wb") as fh:
            fh.write(data)
        w, h = webp_size(data)
        return os.path.basename(path), w, h
    pix = fitz.Pixmap(data)
    if pix.colorspace and pix.colorspace.name == "DeviceCMYK":
        pix = fitz.Pixmap(fitz.csRGB, pix)
    path, w, h = save_pixmap(pix, os.path.join(outdir, name + ".jpg"))
    return os.path.basename(path), w, h


# --------------------------------------------------------------------------
# PDF 版面：閱讀順序與同行碎片合併
# --------------------------------------------------------------------------
def order_by_reading(raw, tol=8.0):
    """先依 y 排序，再把垂直位置相近的項目（同一行的左右兩欄、並排的圖）依 x 排序。"""
    raw.sort(key=lambda r: r["y"])
    out, i = [], 0
    while i < len(raw):
        j = i + 1
        while j < len(raw) and raw[j]["y"] - raw[i]["y"] < tol:
            j += 1
        group = sorted(raw[i:j], key=lambda r: r.get("x0", r["y"]))
        out.extend(group)
        i = j
    return out


def merge_same_line(raw, tol=4.0):
    """同一行被字體切換切成多段時（例如超連結），合併回一行。"""
    out = []
    for r in raw:
        if (r["kind"] == "line" and out and out[-1]["kind"] == "line"
                and abs(out[-1]["y"] - r["y"]) < tol
                and r["x0"] - out[-1]["x1"] < 3 * r["size"]):
            prev = out[-1]
            prev["text"] = prev["text"] + r["text"]
            prev["x1"] = max(prev["x1"], r["x1"])
            prev["size"] = max(prev["size"], r["size"])
            prev["fonts"] = prev["fonts"] | r["fonts"]
            continue
        out.append(r)
    return out


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def extract_pdf(cfg):
    src = os.path.join(ROOT, cfg["source"])
    lay = cfg.get("layout", {})
    indent_x = lay.get("indent_x")
    body_x = lay.get("body_x", 36)
    right = lay.get("right", 560)
    hmin = lay.get("heading_min_size", 99)
    skip_pages = set(lay.get("skip_pages", []))
    skip_res = [re.compile(r) for r in lay.get("skip_re", [])]
    head_res = [re.compile(r) for r in lay.get("heading_re", [])]
    head3_res = [re.compile(r) for r in lay.get("heading3_re", [])]
    quote_fonts = set(lay.get("quote_fonts", []))
    want_tables = lay.get("tables", False)

    # 某些頁（例如書名頁）版心與正文不同，可個別覆寫
    overrides = {int(k): v for k, v in lay.get("page_overrides", {}).items()}

    doc = fitz.open(src)
    outdir = os.path.join(IMGROOT, cfg["slug"])
    shutil.rmtree(outdir, ignore_errors=True)

    items = []          # 依閱讀順序的原始項目
    seen_xref = {}
    n_img = 0

    for pno in range(doc.page_count):
        if pno in skip_pages:
            continue
        page = doc[pno]
        ov = overrides.get(pno, {})
        p_ind = ov.get("indent_x", indent_x)
        p_bod = ov.get("body_x", body_x)
        p_rgt = ov.get("right", right)

        table_boxes = []
        if want_tables:
            for tab in page.find_tables().tables:
                table_boxes.append((fitz.Rect(tab.bbox), tab.extract()))

        raw = []
        info = page.get_text("dict")
        for blk in info["blocks"]:
            if blk["type"] == 1:
                raw.append({"kind": "img", "y": blk["bbox"][1], "bbox": blk["bbox"]})
                continue
            for ln in blk["lines"]:
                text = "".join(sp["text"] for sp in ln["spans"])
                if not text.strip():
                    continue
                raw.append({
                    "kind": "line", "y": ln["bbox"][1],
                    "x0": ln["bbox"][0], "x1": ln["bbox"][2],
                    "text": text,
                    "size": max(round(sp["size"], 1) for sp in ln["spans"]),
                    "fonts": {sp["font"] for sp in ln["spans"]},
                })
        for rect, rows in table_boxes:
            raw.append({"kind": "table", "y": rect.y0, "rows": rows})
        raw = order_by_reading(raw)
        raw = merge_same_line(raw)

        # 圖片 bbox -> xref
        xref_by_bbox = []
        for ii in page.get_image_info(xrefs=True):
            xref_by_bbox.append((fitz.Rect(ii["bbox"]), ii["xref"], ii["transform"]))

        for r in raw:
            if r["kind"] == "img":
                bb = fitz.Rect(r["bbox"])
                xref, trans, best = None, None, 0.0
                for rect, xr, tf in xref_by_bbox:
                    isect = rect & bb
                    inter = max(0.0, isect.width) * max(0.0, isect.height)
                    if inter > best:
                        best, xref, trans = inter, xr, tf
                if xref is None:
                    continue
                if xref in seen_xref:
                    items.append({"kind": "img", **seen_xref[xref]})
                    continue
                n_img += 1
                try:
                    meta = save_page_image(doc, page, bb, xref, trans, outdir, "%02d" % n_img)
                except Exception as exc:  # pragma: no cover
                    print("  ! 圖片轉檔失敗 xref=%s: %s" % (xref, exc))
                    continue
                seen_xref[xref] = meta
                items.append({"kind": "img", **meta})
                continue

            if r["kind"] == "table":
                items.append(r)
                continue

            if want_tables and any(fitz.Rect(b[0]).contains(fitz.Point(r["x0"] + 1, r["y"] + 1))
                                   for b in table_boxes):
                continue

            txt = clean(r["text"], pdf=True)
            if not txt or any(rx.match(txt) for rx in skip_res):
                continue
            items.append({
                "kind": "line", "text": txt, "x0": r["x0"], "x1": r["x1"],
                "size": r["size"], "fonts": r["fonts"], "page": pno,
                "ind": p_ind, "bod": p_bod, "rgt": p_rgt,
            })

    # ---- 把行合併成段落 ----
    blocks = []
    buf = []
    buf_quote = True
    prev = None

    def flush():
        nonlocal buf, buf_quote
        if buf:
            blocks.append({"t": "p", "text": join_lines(buf), "quote": bool(quote_fonts and buf_quote)})
        buf = []
        buf_quote = True

    for it in items:
        if it["kind"] != "line":
            flush()
            if it["kind"] == "img":
                blocks.append({"t": "img", "src": it["src"], "w": it["w"], "h": it["h"]})
            else:
                blocks.append({"t": "table", "rows": it["rows"]})
            prev = None
            continue

        txt = it["text"]
        if it["size"] >= hmin or any(rx.match(txt) for rx in head_res):
            flush()
            blocks.append({"t": "h2", "text": txt, "size": it["size"], "page": it["page"]})
            prev = None
            continue
        if any(rx.match(txt) for rx in head3_res):
            flush()
            blocks.append({"t": "h3", "text": txt, "page": it["page"]})
            prev = None
            continue

        # 以「圖N」開頭的短行，且不是正文的續行時，才算圖說
        if (re.match(r"^[图圖]\s*\d", txt) and len(txt) < 40
                and not buf and it["x0"] > it["bod"] + 30):
            flush()
            blocks.append({"t": "caption",
                           "text": re.sub(r"^([图圖])(\d+)(?=\S)", r"\1\2 ", txt)})
            prev = None
            continue

        if prev is None or prev["page"] != it["page"] and it["page"] in overrides:
            new_para = True
        elif it["ind"] is not None:
            new_para = it["x0"] >= it["ind"] - 3
        else:
            new_para = prev["x1"] < it["rgt"] - 1.6 * it["size"]

        if new_para:
            flush()
        buf.append(txt)
        buf_quote = buf_quote and bool(quote_fonts and it["fonts"] <= quote_fonts)
        prev = it

    flush()
    return blocks


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def extract_docx(cfg):
    src = os.path.join(ROOT, cfg["source"])
    zf = zipfile.ZipFile(src)
    outdir = os.path.join(IMGROOT, cfg["slug"])
    shutil.rmtree(outdir, ignore_errors=True)

    rels = {}
    if "word/_rels/document.xml.rels" in zf.namelist():
        for rel in ET.fromstring(zf.read("word/_rels/document.xml.rels")):
            rels[rel.get("Id")] = rel.get("Target")

    media = sorted(n for n in zf.namelist() if n.startswith("word/media/") and not n.endswith("/"))

    def media_for(embed):
        """關聯表可能損壞（例如 Target 為 ../NULL），此時按順序回退到 media 清單。"""
        target = rels.get(embed)
        if target:
            name = "word/" + target.lstrip("/")
            if name in zf.namelist():
                return name
        return media[len(saved)] if len(saved) < len(media) else None

    body = ET.fromstring(zf.read("word/document.xml")).find(W + "body")
    blocks = []
    saved = []
    n_img = 0

    for para in body.iter(W + "p"):
        pieces = []
        bold_all = True
        has_text = False
        for run in para.iter(W + "r"):
            rpr = run.find(W + "rPr")
            bold = rpr is not None and rpr.find(W + "b") is not None
            for node in run.iter():
                if node.tag == W + "t":
                    t = node.text or ""
                    if t.strip():
                        has_text = True
                        if not bold:
                            bold_all = False
                    pieces.append(t)
                elif node.tag == W + "br":
                    pieces.append("\n")
                elif node.tag == A + "blip":
                    entry = media_for(node.get(R + "embed"))
                    if entry:
                        n_img += 1
                        name, w, h = save_image_bytes(zf.read(entry), outdir, "%02d" % n_img)
                        saved.append(entry)
                        pieces.append("\x00IMG:%s:%d:%d\x00" % (name, w, h))
        text = "".join(pieces)
        for chunk in text.split("\x00"):
            if chunk.startswith("IMG:"):
                _, name, w, h = chunk.split(":")
                blocks.append({"t": "img", "src": name, "w": int(w), "h": int(h)})
            else:
                t = clean(chunk.replace("\n", ""))
                if t:
                    blocks.append({"t": "p", "text": t, "bold": bool(has_text and bold_all)})
    return blocks


# --------------------------------------------------------------------------
# DOC / TXT
# --------------------------------------------------------------------------
def extract_doc(cfg):
    src = os.path.join(ROOT, cfg["source"])
    tmp = os.path.join(BUILD, cfg["slug"] + ".doc.txt")
    subprocess.run(["textutil", "-convert", "txt", "-encoding", "UTF-8",
                    "-output", tmp, src], check=True)
    with open(tmp, encoding="utf-8") as fh:
        raw = fh.read()
    os.remove(tmp)
    return lines_to_blocks(raw)


def extract_txt(cfg):
    with open(os.path.join(ROOT, cfg["source"]), encoding="utf-8") as fh:
        return lines_to_blocks(fh.read())


def lines_to_blocks(raw):
    blocks = []
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        t = clean(line)
        if t:
            blocks.append({"t": "p", "text": t})
    return blocks


# --------------------------------------------------------------------------
def main():
    os.makedirs(BUILD, exist_ok=True)
    only = sys.argv[1:] or None
    for cfg in DOCS:
        if only and cfg["slug"] not in only:
            continue
        ext = os.path.splitext(cfg["source"])[1].lower()
        fn = {".pdf": extract_pdf, ".docx": extract_docx,
              ".doc": extract_doc, ".txt": extract_txt}[ext]
        blocks = fn(cfg)
        with open(os.path.join(BUILD, cfg["slug"] + ".json"), "w", encoding="utf-8") as fh:
            json.dump(blocks, fh, ensure_ascii=False, indent=1)
        kinds = {}
        for b in blocks:
            kinds[b["t"]] = kinds.get(b["t"], 0) + 1
        chars = sum(len(b.get("text", "")) for b in blocks)
        print("%-34s %-6s blocks=%-4d chars=%-7d %s" %
              (cfg["slug"], ext, len(blocks), chars, kinds))


if __name__ == "__main__":
    main()
