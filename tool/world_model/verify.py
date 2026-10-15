#!/usr/bin/env python3
"""Verify the compilation against the original site HTML.

Checks, per emitted entry:
  1. every content block appears verbatim in the referenced HTML file
  2. the anchor id exists in that HTML file
"""
import json
import os
import re
import sys
import html as html_mod
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BUILD = os.path.join(HERE, "build")
MD = os.path.join(BUILD, "world_model_source.md")
JSONL = os.path.join(BUILD, "world_model_source.jsonl")


class Text(HTMLParser):
    """Collect all visible text of a document, and all element ids."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.chunks = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "br":
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.chunks.append(data)


def norm(s):
    return re.sub(r"\s+", "", s)


def main():
    if len(sys.argv) > 1 and sys.argv[1] not in ("source", "spec"):
        print("usage: verify.py [source|spec]")
        return 2
    which = sys.argv[1] if len(sys.argv) > 1 else "source"
    stem = "world_model_source" if which == "source" else "world_model_spec"
    rows = [json.loads(l) for l in open(os.path.join(BUILD, stem + ".jsonl"), encoding="utf-8")]

    cache = {}
    def doc_for(corpus, f):
        key = (corpus, f)
        if key not in cache:
            sub = "wenda2_ebook" if corpus == "問答錄2" else "ebook"
            path = os.path.join(ROOT, sub, f)
            if not os.path.exists(path):
                cache[key] = None
                return None
            t = Text()
            t.feed(open(path, encoding="utf-8").read())
            t.close()
            cache[key] = (t.ids, norm("".join(t.chunks)))
        return cache[key]

    bad_text = []
    bad_anchor = []
    checked = 0
    for r in rows:
        d = doc_for(r["corpus"], r["file"])
        if d is None:
            print("MISSING FILE", r["corpus"], r["file"])
            return 1
        ids, hay = d
        if r["anchor"] not in ids:
            bad_anchor.append((r["theme"], r["file"], r["anchor"]))
        for line in r["text"].split("\n"):
            t = norm(line)
            if len(t) < 20:
                continue
            checked += 1
            if t not in hay:
                bad_text.append((r["theme"], r["file"], r["anchor"], t[:70]))

    print(f"[{which}] entries          : {len(rows)}")
    print(f"content lines checked: {checked}")
    print(f"anchors not found  : {len(bad_anchor)}")
    print(f"lines not verbatim : {len(bad_text)}")
    for x in bad_anchor[:10]:
        print("  BAD ANCHOR", x)
    for x in bad_text[:10]:
        print("  BAD TEXT", x)
    return 0 if not bad_text and not bad_anchor else 1


if __name__ == "__main__":
    sys.exit(main())