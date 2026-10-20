#!/usr/bin/env python3
"""《圓覺經》PDF 一次性來源修訂：把「解析」裡**經文條目**的編號改成粗體。

為什麼要改原檔
--------------
《圓覺經》講記的「解析」段落在書面上把經文條目排成

    1. 一切障碍即究竟觉。      ← 編號用微軟正黑體「一般字型」，經文用「粗體」
    2. 得念失念无非解脱。

同一種排法在《圓覺經》全書有 188 處。這種「編號（一般字型）＋經文（粗體）」
的混排行讓抽取器無法判斷「經文條目」是一個**獨立的段落**——它與後面的講解
同縮排，於是被併成同一段：

    1. 一切障碍即究竟觉。在此处，“障碍”是妄想、分别、执着的统称……   ← 經文＋講解黏成一段

黏成一段的後果：該條經文沒有被輸出成經文區塊（`.sutra-text`），**「經文置頂」
對它完全失效**（讀者只會覺得「這本書的置頂有時有時沒有」）。其他 187 條
因為前一段剛好以續行縮排結尾，段落邊界碰巧切對了，才沒有出問題。

修訂內容
--------
把條目編號改成**與經文同粗體**（整條成為同一個粗體單元），與書中其他
「經文條目」的排法一致：

    **1.** 一切障碍即究竟觉。   ← 編號與經文同為粗體

- **文字內容完全不變**（抽出後逐字相同，只換字型）✓
- 只動字型資源與後續字元的 x 座標（粗體數字略寬 0.42pt，需把後面的「. 」
  跟著右移同樣距離，經文本身的位置不變）✓
- 名相注釋（「1. 无始：这是针对时间和因果轮回而言的……」——粗體詞頭在行中、
  其後接說明）**不在本工具的處理範圍**（粗體不在行尾 → 不是經文條目）✓

用法（會就地改寫 `books/05 TaiGuangLin禅师讲《圆觉经》最终版.pdf`）
------------------------------------------------------------
    python3 tool/fix_yuanjue_sutra_numbers.py            # 修訂
    python3 tool/fix_yuanjue_sutra_numbers.py --check    # 只檢查會改到哪些地方

修訂前請先備份或 `git stash`（PDF 是版控中的來源檔，改動會出現在 diff）。
工具本身可重複執行：已改過的條目（編號已是粗體）會被跳過 ✓。
"""

import argparse
import io
import re
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:  # PyMuPDF < 1.24 只有舊模組名
    import fitz as pymupdf

REPO_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = REPO_ROOT / "books" / "05 TaiGuangLin禅师讲《圆觉经》最终版.pdf"

REGULAR = "MicrosoftYaHei"        # 編號用的正黑體（一般字型）
BOLD = "MicrosoftYaHei-Bold"      # 經文用的粗體

# 文字操作子：整個 BT…ET 區塊（Tf 選字型、Tm 定位、TJ 顯示字串；
# 區塊中間可能夾 Tc（字元間距）等運算子，故以區塊為單位解析）
_BLOCK_RE = re.compile(r"BT\s*(?P<body>.*?)\s*ET", re.S)
_TF_RE = re.compile(r"/(?P<font>F\d+)\s+(?P<size>[\d.]+)\s+Tf")
_TM_RE = re.compile(r"1 0 0 1 (?P<x>[\d.]+) (?P<y>[\d.]+) Tm")
_TJ_RE = re.compile(r"\[(?P<str>[^\]]*)\]\s*TJ")
_TC_RE = re.compile(r"(?P<tc>-?[\d.]+)\s+Tc")
# 編號前綴：[(12)-3(.)10( )] 或獨立區塊 [(12)] + [(. )]
_NUM_RE = re.compile(r"^\((?P<num>\d{1,2})\)")


def _parse_text_ops(data):
    """把內容流拆成文字操作子 [{font, size, x, y, str, tc, raw}]。"""
    ops = []
    for m in _BLOCK_RE.finditer(data):
        body = m.group("body")
        fm, tm = _TF_RE.search(body), _TM_RE.search(body)
        jm = _TJ_RE.search(body)
        if not (fm and tm and jm):
            continue
        tcm = _TC_RE.search(body)
        ops.append({
            "font": fm.group("font"),
            "size": float(fm.group("size")),
            "x": float(tm.group("x")),
            "y": float(tm.group("y")),
            "str": jm.group("str"),
            "tc": tcm.group("tc") if tcm else None,
            "raw": m.group(0),
            "eol": "\r\n" if "\r\n" in m.group(0) else "\n",
        })
    return ops


def _page_font_map(page):
    """{資源名: 基礎字型名}（內容流用 /F1，抽取器用基礎字型名）✓"""
    out = {}
    for f in page.get_fonts(full=True):
        out[f[4]] = f[3].split("+")[-1]
    return out


def _type0_refs(page):
    """Type0（Identity-H）字型資源——不能用於 WinAnsi 編碼的文字。"""
    return set(f[4] for f in page.get_fonts(full=True) if f[2] == "Type0")


def _string_is_blank(s):
    """TJ 陣列的字串是否只有空白。"""
    return not s.replace("(", "").replace(")", "").strip()


def _advance_widths(doc, page):
    """{資源名: {字元碼: 寬度比例}}（以字型檔的 hmtx 取得，比例＝字寬/字身）✓"""
    widths = {}
    for f in page.get_fonts(full=True):
        xref, ref = f[0], f[4]
        try:
            _, _, _, buf = doc.extract_font(xref)
            from fontTools.ttLib import TTFont
            tt = TTFont(io.BytesIO(buf), fontNumber=0)
            cm = tt.getBestCmap()
            hmtx = tt["hmtx"]
            upem = tt["head"].unitsPerEm
            widths[ref] = {code: hmtx.metrics[gid][0] / float(upem)
                           for code, gid in cm.items()
                           if code < 256 and gid in hmtx.metrics}
        except Exception:
            continue
    return widths


def _make_block(font, size, x, y, s, tc=None, eol="\n"):
    """組出一個 BT…ET 文字區塊。"""
    lines = ["BT", "/%s %s Tf" % (font, size), "1 0 0 1 %s %s Tm" % (x, y),
             "0 g", "0 G"]
    if tc is not None:
        lines.append(" %s Tc" % tc)
    lines.append("[%s] TJ" % s)
    lines.append("ET")
    return eol.join(lines)


def _bold_simple_ref(doc, page):
    """此頁可用的「粗體簡單字型」資源名（TrueType + WinAnsi 編碼）。

    只有簡單字型能用 WinAnsi 編碼畫數字；Type0（Identity-H）的粗體字型
    沒有數字的 ToUnicode 映射，抽出的文字會變亂碼 → 不能用。
    """
    fonts = _page_font_map(page)
    type0 = _type0_refs(page)
    for ref, base in fonts.items():
        if base == BOLD and ref not in type0:
            return ref
    return None


def _ensure_bold_simple_ref(doc, page, donor_xref, name="F3"):
    """此頁若沒有粗體簡單字型，從 donor 頁把同一個字型資源掛過來。

    字型物件本身是全書共用的（同一個 xref），所以只是把資源名加到該頁的
    /Resources /Font 字典即可（不改字型資料、不重新內嵌）。
    """
    if _bold_simple_ref(doc, page):
        return True
    try:
        doc.xref_set_key(page.xref, "Resources/Font/%s" % name, "%d 0 R" % donor_xref)
    except Exception:
        # 退回：重建整個 /Font 字典
        old = doc.xref_get_key(page.xref, "Resources/Font")
        if old[0] != "dict":
            return False
        body = old[1]
        if name in body:
            return False
        new = body[:-2] + " /%s %d 0 R>>" % (name, donor_xref)
        doc.xref_set_key(page.xref, "Resources/Font", new)
    return _bold_simple_ref(doc, page) is not None


def _find_donor_bold_xref(doc):
    """找一個含「粗體簡單字型」的頁，回傳該字型字典的 xref。"""
    for pno in range(min(doc.page_count, 40)):
        page = doc[pno]
        ref = _bold_simple_ref(doc, page)
        if not ref:
            continue
        fonts = doc.xref_get_key(page.xref, "Resources/Font")
        if fonts[0] != "dict":
            continue
        m = re.search(r"/%s\s+(\d+)\s+0\s+R" % re.escape(ref), fonts[1])
        if m:
            return int(m.group(1))
    return None


def find_sutra_number_ops(doc, page):
    """回傳此頁「經文條目」編號操作子的清單。

    判準（與 books2ebook 的經文判定一致）：
    - 該行第一段是**一般字型**的編號前綴（「N」或「N. 」）；
    - 該行**最後一段非空白文字是粗體**（經文）→ 名相注釋的粗體詞頭在行中、
      其後還有一般字型的說明，故不會被誤判。
    """
    fonts = _page_font_map(page)
    data = doc.xref_stream(page.get_contents()[0]).decode("latin-1")
    ops = _parse_text_ops(data)
    if not ops:
        return []

    lines = {}
    for op in ops:
        lines.setdefault(op["y"], []).append(op)

    targets = []
    for y, group in lines.items():
        first = group[0]
        if fonts.get(first["font"]) != REGULAR:
            continue
        if not _NUM_RE.match(first["str"]):
            continue
        last = None
        for op in group:
            if not _string_is_blank(op["str"]):
                last = op
        if last is None or fonts.get(last["font"]) != BOLD:
            continue
        targets.append(first)
    return targets


def patch_page(doc, page, apply_changes, donor_xref=None):
    """把此頁的經文條目編號改成粗體。回傳 (修訂筆數, 修訂說明)。"""
    fonts = _page_font_map(page)
    widths = _advance_widths(doc, page)
    bold_ref = _bold_simple_ref(doc, page)
    if not bold_ref and donor_xref is not None:
        if not _ensure_bold_simple_ref(doc, page, donor_xref):
            return 0, []
        fonts = _page_font_map(page)
        widths = _advance_widths(doc, page)
        bold_ref = _bold_simple_ref(doc, page)
    if not bold_ref:
        return 0, []

    xref = page.get_contents()[0]
    data = doc.xref_stream(xref).decode("latin-1")
    edits = []
    n_lines = 0
    for op in find_sutra_number_ops(doc, page):
        n_lines += 1
        m = _NUM_RE.match(op["str"])
        num = m.group("num")
        rest = op["str"][m.end():]        # 同一 TJ 內的後半（"(. )" 之類）
        size, x = op["size"], op["x"]
        # 粗體數字略寬 → 「. 」要跟著右移相同距離（經文本身的位置不變）
        reg_w = widths.get(op["font"], {}).get(ord(num[0]), 0.0)
        bold_w = widths.get(bold_ref, {}).get(ord(num[0]), 0.0)
        shift = (bold_w - reg_w) * size
        if rest:
            # 形式 (a)：編號與「. 」在同一個 TJ → 拆成兩個區塊
            km = re.match(r"^(?P<kern>-?\d+)?(?P<rest>\(.*)$", rest)
            kern_shift = (float(km.group("kern")) / 1000.0 * size) if km.group("kern") else 0.0
            new_rest_x = x + reg_w * size + shift + kern_shift
            new = (_make_block(bold_ref, size, x, op["y"], "(%s)" % num,
                               op["tc"], op["eol"])
                   + op["eol"]
                   + _make_block(op["font"], size, round(new_rest_x, 2), op["y"],
                                 km.group("rest"), op["tc"], op["eol"]))
        else:
            # 形式 (b)：編號與「. 」是兩個區塊 → 換字型並把「. 」右移
            new = _make_block(bold_ref, size, x, op["y"], op["str"],
                              op["tc"], op["eol"])
            edits.append((op["raw"], new, num, "split" if False else "font"))
            # 「. 」區塊：位於同一行的下一個操作子
            for cand in _parse_text_ops(data):
                if cand["y"] == op["y"] and cand["x"] > op["x"] \
                        and fonts.get(cand["font"]) == REGULAR \
                        and cand["str"].lstrip("(").startswith("."):
                    new_dot = _make_block(cand["font"], cand["size"],
                                          round(cand["x"] + shift, 2), cand["y"],
                                          cand["str"], cand["tc"], cand["eol"])
                    edits.append((cand["raw"], new_dot, num, "dot"))
                    break
            continue
        edits.append((op["raw"], new, num, "split"))
    if not edits:
        return 0, []
    for old, new, _n, _k in edits:
        if old not in data:
            raise SystemExit("內容流比對失敗（操作子已改變？）")
        data = data.replace(old, new, 1)
    if apply_changes:
        doc.update_stream(xref, data.encode("latin-1"))
    return n_lines, edits


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", default=str(PDF_PATH))
    ap.add_argument("--check", action="store_true", help="只列出會被修訂的地方")
    args = ap.parse_args()

    path = Path(args.pdf)
    doc = pymupdf.open(path)
    donor = _find_donor_bold_xref(doc)
    if donor is None:
        raise SystemExit("找不到可用的粗體簡單字型（MicrosoftYaHei-Bold / WinAnsi）")
    total = 0
    pages = 0
    for pno in range(doc.page_count):
        page = doc[pno]
        n, _ = patch_page(doc, page, apply_changes=not args.check, donor_xref=donor)
        if n:
            total += n
            pages += 1
    if args.check:
        print("會修訂 %d 處（分佈於 %d 頁）" % (total, pages))
        doc.close()
        return
    if not total:
        print("沒有需要修訂的地方（可能已修訂過）")
        doc.close()
        return
    # 增量存檔（就地）：原檔的其餘位元組完全不動，只追加被修訂頁的新內容流
    # 與新 xref——對「來源檔」的改動最小。完整重寫雖可回收舊內容流，但會
    # 重編號全部 xref（改動面更大），故不採用。
    doc.save(str(path), incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    print("已修訂 %d 處（%d 頁）→ %s" % (total, pages, path))


if __name__ == "__main__":
    main()
