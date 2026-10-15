#!/usr/bin/env python3
"""Single-pass extraction of clean text corpus from generated ebook HTML.

Produces corpus.jsonl: one record per content block, in document order, with
full heading context (h1..h5 path), anchor id, and QA metadata.
"""
import re
import json
import os
import glob
from html.parser import HTMLParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "corpus.jsonl")

HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
BLOCK_CLASSES = {
    "para-block": "para",
    "question-text": "question",
    "answer-text": "answer",
    "content-text": "content",
    "speech": "para",
}
META_CLASSES = ("questioner", "answerer", "question-time", "questioner-time")


class Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events = []      # ordered list of ("heading", level, text, id) / ("block", rec)
        self.heading_stack = []
        self.cur = None       # dict(kind,id,parts,meta)
        self.skip_depth = 0
        self.qa_meta = {}     # accumulate asker/time seen inside current qa-pair
        self._last_container_id = ""
        self._meta_target = None
        self._meta_depth = 0

    # -- internal ------------------------------------------------------
    def _start_block(self, kind, bid):
        self._close_block()
        self.cur = {"kind": kind, "id": bid or "", "parts": []}

    def _close_block(self):
        if self.cur is None or self.cur["kind"] == "_heading":
            return
        raw = "".join(self.cur["parts"])
        txt = re.sub(r"[ \t\u3000]+", " ", raw)
        txt = re.sub(r" *\n *", "\n", txt)
        txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
        if txt:
            self.cur["text"] = txt
            self.cur["meta"] = {k: v.strip() for k, v in self.qa_meta.items()}
            self.events.append(("block", dict(self.cur)))
        self.cur = None

    # -- HTMLParser API ------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.skip_depth += 1
            return
        if tag in HEADING_TAGS:
            self._close_block()
            self.cur = {"kind": "_heading", "level": HEADING_TAGS[tag],
                        "id": a.get("id", ""), "parts": []}
            return
        if tag == "article":
            self._close_block()
            self.qa_meta = {}
            self._meta_target = None
            return
        if tag in ("p", "div", "span", "li", "blockquote"):
            cls = (a.get("class") or "").split()
            kind = None
            for c in cls:
                if c in BLOCK_CLASSES:
                    kind = BLOCK_CLASSES[c]
            if kind is None and tag == "p":
                kind = "content"     # bare <p id="content-..."> blocks in 問答錄2
            if kind:
                bid = a.get("id") or self._last_container_id
                self._start_block(kind, bid)
                return
            if a.get("id"):
                self._last_container_id = a["id"]
            for c in cls:
                if c in META_CLASSES:
                    self.qa_meta[c] = ""
                    self._meta_target = c
                    self._meta_depth = 0
            return
        if tag == "br" and self.cur is not None:
            self.cur["parts"].append("\n")

    def handle_endtag(self, tag):
        if self._meta_target is not None and tag in ("span", "div"):
            self._meta_depth += 1
            if self._meta_depth >= 2:
                self._meta_target = None
                self._meta_depth = 0
        if tag in ("script", "style"):
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if tag in HEADING_TAGS:
            if self.cur is not None and self.cur["kind"] == "_heading":
                raw = "".join(self.cur["parts"])
                txt = re.sub(r"\s+", " ", raw).strip()
                txt = re.sub(r"\(\d+\)\s*$", "", txt).strip()
                lvl = self.cur["level"]
                hid = self.cur["id"]
                self.cur = None
                while self.heading_stack and self.heading_stack[-1][0] >= lvl:
                    self.heading_stack.pop()
                self.heading_stack.append((lvl, txt, hid))
                self.events.append(("heading", lvl, txt, hid))
            return
        if tag in ("p", "article", "div", "span", "li", "blockquote"):
            self._close_block()

    def handle_data(self, data):
        if self.skip_depth or self.cur is None:
            if self.skip_depth == 0 and self._meta_target is not None:
                self.qa_meta[self._meta_target] = \
                    self.qa_meta.get(self._meta_target, "") + data
            return
        self.cur["parts"].append(data)

    def close(self):
        super().close()
        self._close_block()


def section_path(doc, upto_idx):
    """Reconstruct heading path for a given event index."""
    stack = []
    for i, ev in enumerate(doc.events):
        if ev[0] == "heading":
            lvl = ev[1]
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            stack.append((lvl, ev[2], ev[3]))
        elif i == upto_idx:
            return list(stack)
    return list(stack)


def parse(path):
    src = open(path, encoding="utf-8").read()
    i = src.find("<main")
    body = src[i:] if i >= 0 else src
    j = body.find("</main>")
    if j >= 0:
        body = body[:j]
    d = Doc()
    d.feed(body)
    d.close()
    return d


BOOK_TITLE = {
    "01": "01《坐禪》", "02": "02《坐禪之問答錄》",
    "03": "03《坐禪2·次世代版終極佛法》",
    "04": "04《次世代版終極佛法·講金剛經心經》",
    "05": "05《圓覺經》", "06": "06《四十二章經》",
    "07": "07《楞伽經》", "08": "08《六祖壇經》",
    "09": "09《楞嚴經》(未完)", "10": "10《感恩與講經》",
}


def main():
    records = []
    targets = []
    for p in sorted(glob.glob(os.path.join(ROOT, "wenda2_ebook", "[0-9][0-9]_trad.html"))):
        targets.append(("問答錄2", p))
    for p in sorted(glob.glob(os.path.join(ROOT, "ebook", "[0-9][0-9]_trad.html"))):
        targets.append(("九本書", p))

    for corpus, path in targets:
        fname = os.path.basename(path)
        num = fname[:2]
        d = parse(path)
        stack = []
        for i, ev in enumerate(d.events):
            if ev[0] == "heading":
                lvl, txt, hid = ev[1], ev[2], ev[3]
                while stack and stack[-1][0] >= lvl:
                    stack.pop()
                stack.append((lvl, txt, hid))
            else:
                rec = dict(ev[1])
                path_titles = [t for (_l, t, _i) in stack]
                h1 = next((t for (l, t, _i) in stack if l == 1), "")
                if corpus == "問答錄2":
                    book = h1 or f"問答錄2 {num}"
                else:
                    book = h1 or num
                records.append({
                    "corpus": corpus,
                    "file": fname,
                    "book": book,
                    "section": path_titles,
                    "kind": rec["kind"],
                    "anchor": rec["id"],
                    "meta": rec.get("meta", {}),
                    "text": rec["text"],
                })

    with open(OUT, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    import collections
    print("records:", len(records))
    print(collections.Counter((r["corpus"], r["kind"]) for r in records))
    tot = sum(len(r["text"]) for r in records)
    print("total chars:", tot)


if __name__ == "__main__":
    main()