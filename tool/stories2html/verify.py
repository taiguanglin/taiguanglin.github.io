#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""比對原始檔與產出的 HTML，確認沒有漏字。

把兩邊的文字都去掉所有空白後逐字比對，列出只在其中一邊出現的片段。
"""
import os
import re
import subprocess
import sys
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

import fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docs import DOCS  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ArticleText(HTMLParser):
    """只取 <article class="story-article"> 內的文字。"""

    VOID = {"img", "br", "hr", "input", "meta", "link", "source", "col", "area"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "article" and "story-article" in (dict(attrs).get("class") or ""):
            self.depth = 1
        elif self.depth and tag not in self.VOID:
            self.depth += 1

    def handle_endtag(self, tag):
        if self.depth and tag not in self.VOID:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def squash(s):
    s = re.sub(r"\s+", "", s)
    # 抽字時常見的等價字形差異，不視為漏字
    for a, b in (("（", "("), ("）", ")"), ("，", ","), ("：", ":"), ("；", ";"),
                 ("？", "?"), ("！", "!"), ("～", "~"), ("－", "-"), ("—", "-"),
                 ("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'), ("…", "."),
                 ("　", ""), ("\u200b", ""), ("·", "."), ("﹒", ".")):
        s = s.replace(a, b)
    return s


def source_text(cfg):
    path = os.path.join(ROOT, cfg["source"])
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        doc = fitz.open(path)
        lay = cfg.get("layout", {})
        skip = set(lay.get("skip_pages", []))
        drop = [re.compile(r) for r in lay.get("skip_re", [])]
        lines = []
        for i, page in enumerate(doc):
            if i in skip:
                continue
            for line in page.get_text().split("\n"):
                # 頁碼／書眉不算內文
                if any(rx.match(line.strip()) for rx in drop):
                    continue
                lines.append(line)
        return "\n".join(lines)
    if ext == ".docx":
        root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
        return "\n".join("".join(t.text or "" for t in p.iter(W + "t"))
                         for p in root.iter(W + "p"))
    if ext == ".doc":
        return subprocess.run(["textutil", "-convert", "txt", "-stdout", path],
                              capture_output=True, check=True).stdout.decode("utf-8")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def diff_report(src, out, label):
    import collections
    import difflib

    # 不論順序的字元清單比對：抓「有沒有掉字」，不受表格重排等影響
    lost = collections.Counter(src) - collections.Counter(out)
    if lost:
        print("%-32s ⚠ 不論順序仍缺字：%s" % (label, dict(lost.most_common(12))))

    sm = difflib.SequenceMatcher(None, src, out, autojunk=False)
    missing, added = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("delete", "replace") and (i2 - i1):
            missing.append((i1, src[i1:i2]))
        if tag in ("insert", "replace") and (j2 - j1):
            added.append((j1, out[j1:j2]))
    print("%-32s 原始=%-7d 產出=%-7d 缺=%-5d 多=%-5d" %
          (label, len(src), len(out), sum(len(m[1]) for m in missing),
           sum(len(a[1]) for a in added)))
    for pos, frag in missing:
        if frag.strip():
            print("   缺 @%-6d %r  ⟨前後：%s⟩" % (pos, frag[:90], src[max(0, pos - 18):pos + 24]))
    for pos, frag in added:
        if frag.strip():
            print("   多 @%-6d %r" % (pos, frag[:90]))


def main():
    only = sys.argv[1:] or None
    for cfg in DOCS:
        if only and cfg["slug"] not in only:
            continue
        html_path = os.path.join(ROOT, "stories", cfg["slug"] + ".html")
        if not os.path.exists(html_path):
            print("%-32s (尚未產生 HTML)" % cfg["slug"])
            continue
        parser = ArticleText()
        with open(html_path, encoding="utf-8") as fh:
            parser.feed(fh.read())
        diff_report(squash(source_text(cfg)), squash("".join(parser.parts)), cfg["slug"])


if __name__ == "__main__":
    main()
