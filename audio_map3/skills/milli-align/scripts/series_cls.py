#!/usr/bin/env python3
"""series_cls — 泛化 ebook cls 載入（milli-align skill §7.2 支援）.

`align_lengqie.load_ebook_cls()` 只吃 ebook/08.html（楞伽经( 樣式）。
本模組提供所有講經系列的同款 cls map：{lecture_no(str): [{"pid","cls"}…]}。
lengqie 仍走原路徑（golden 不可侵犯：行為 byte-level 等價）。

用法：
  from series_cls import lecture_cls
  cmap = lecture_cls("liuzutanjing", 5)   # {pid: cls}
"""
from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

# series → (ebook html, basename 樣式)
SERIES_BOOKS = {
    "ganen": ("04.html", r"感恩经\((\d+)\)"),
    "sishierzhang": ("07.html", r"四十二章经\((\d+)\)"),
    "lengqie": ("08.html", r"楞伽经\((\d+)\)"),
    "liuzutanjing": ("09.html", r"六祖坛经\((\d+)\)"),
    "lengyanjing": ("10.html", r"楞严经\((\d+)\)"),
}


def load_ebook_cls_series(series):
    """與 align_lengqie.load_ebook_cls 同款：{lecture_no: [{"pid","cls"}…]}。"""
    book, pat = SERIES_BOOKS[series]
    html = (ROOT / "ebook" / book).read_text(encoding="utf-8")
    marks = list(re.finditer(r'<h2 id="[^"]*">(.*?)</h2>', html, re.S))
    out = {}
    for i, m in enumerate(marks):
        am = re.search(r'data-audio="([^"]+)"', m.group(1))
        if not am:
            continue
        base = urllib.parse.unquote(am.group(1)).rsplit("/", 1)[-1]
        base = re.sub(r"\.opus$", "", base)
        mn = re.search(pat, base)
        if not mn:
            continue
        body = html[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(html)]
        cls = []
        for b in re.finditer(r"<(p|div)\b([^>]*)>(.*?)</\1>", body, re.S):
            cm = re.search(r'class="([^"]*)"', b.group(2))
            pm = re.search(r'id="(p-s[0-9a-f]+)"', b.group(2))
            if not pm or not cm or "para-block" not in cm.group(1).split():
                continue
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", b.group(3))).strip()
            if txt:
                cls.append({"pid": pm.group(1),
                            "cls": ("SUTRA" if "sutra-text" in cm.group(1) else "COMM")})
        out[mn.group(1)] = cls
    return out


def lecture_cls(series, ln):
    """供 milli_audit.lecture_cls 委派：回 {pid: cls}，缺講次回 {}。"""
    try:
        return {c["pid"]: c["cls"] for c in load_ebook_cls_series(series)[str(ln)]}
    except (KeyError, FileNotFoundError):
        return {}


def para_count(series, ln):
    try:
        return len(load_ebook_cls_series(series)[str(ln)])
    except (KeyError, FileNotFoundError):
        return -1


if __name__ == "__main__":
    import json as _json
    for s in sorted(SERIES_BOOKS):
        m = load_ebook_cls_series(s)
        n_para = sum(len(v) for v in m.values())
        n_sutra = sum(1 for v in m.values() for c in v if c["cls"] == "SUTRA")
        print(f"{s}: {len(m)} lectures, {n_para} paras (SUTRA {n_sutra})")
