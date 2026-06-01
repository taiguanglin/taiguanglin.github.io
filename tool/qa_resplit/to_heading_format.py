#!/usr/bin/env python3
"""Convert qa/*.txt to "format A": the question lives in the ### heading.

Transform per segment:
  ### N. <generated title>            ### N. <cleaned question>
  時間：...                            時間：...
  最後播放：                           最後播放：
  最後編輯：               =====>      最後編輯：
  提問： [網友：X] <question>           Taiguanglin：
  Taiguanglin：                        <answer>
  <answer>

- The standalone 提問 line is removed; its text (minus any [網友：…] / [樓主…]
  attribution and leading punctuation) becomes the heading.
- Everything is converted Simplified -> Traditional with OpenCC s2t
  (characters only; vocabulary is left untouched).

Usage: python3 to_heading_format.py [--apply] qa/*.txt
Without --apply it prints a per-file summary and the first 2 segments' diff.
"""
import argparse
import re
import sys
from pathlib import Path

try:
    from opencc import OpenCC
    _S2T = OpenCC("s2t")
except Exception:  # pragma: no cover
    _S2T = None

HEADING_RE = re.compile(r"^###\s+(\d+)\.\s*(.*?)\s*$", re.M)
QUESTION_LINE_RE = re.compile(r"^[ \t]*(?:提問|追加問題)[:：][ \t]*.*(?:\r?\n)?", re.M)
QUESTION_TEXT_RE = re.compile(r"^[ \t]*(?:提問|追加問題)[:：][ \t]*(.*)$", re.M)
ATTR_RE = re.compile(r"^\s*\[[^\]]*\][ \t　]*")
LEAD_PUNCT_RE = re.compile(r"^[\s，,、。．.；;：:！!？?～~—\-…　]+")


def s2t(text: str) -> str:
    return _S2T.convert(text) if _S2T else text


def clean_question(q: str, fallback: str) -> str:
    q = q.strip()
    # Strip a leading attribution bracket, possibly repeated.
    while True:
        nq = ATTR_RE.sub("", q)
        if nq == q:
            break
        q = nq.strip()
    q = LEAD_PUNCT_RE.sub("", q)
    q = re.sub(r"[ \t]+", " ", q).strip()
    return q if q else fallback.strip()


def transform_block(block: str) -> str:
    hm = HEADING_RE.search(block)
    if not hm:
        return block
    number, old_title = hm.group(1), hm.group(2)
    qm = QUESTION_TEXT_RE.search(block)
    question = qm.group(1) if qm else ""
    new_title = clean_question(question, old_title)

    # Replace the heading's title text.
    heading_line = block[hm.start():hm.end()]
    new_heading = f"### {number}. {new_title}"
    block = block[:hm.start()] + new_heading + block[hm.end():]

    # Remove the standalone 提問 line (with its newline).
    block = QUESTION_LINE_RE.sub("", block, count=1)
    return block


def transform_text(text: str) -> str:
    headings = list(HEADING_RE.finditer(text))
    if not headings:
        return s2t(text)
    out = [text[: headings[0].start()]]
    for i, h in enumerate(headings):
        start = h.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        out.append(transform_block(text[start:end]))
    return s2t("".join(out))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    if _S2T is None:
        print("warning: OpenCC not available; characters will NOT be converted", file=sys.stderr)

    for p in args.paths:
        path = Path(p)
        text = path.read_text(encoding="utf-8")
        new = transform_text(text)
        n_seg = len(HEADING_RE.findall(text))
        n_q = len(QUESTION_LINE_RE.findall(new))
        changed = new != text
        if args.apply:
            if changed:
                path.write_text(new, encoding="utf-8")
            print(f"{'applied' if changed else 'nochange'}: {path.name} segments={n_seg} leftover_提問={n_q}")
        else:
            print(f"=== {path.name} === segments={n_seg} leftover_提問={n_q} changed={changed}")
            hs = list(HEADING_RE.finditer(new))
            for h in hs[:2]:
                s = h.start()
                e = hs[hs.index(h) + 1].start() if hs.index(h) + 1 < len(hs) else len(new)
                print(new[s:e].rstrip()[:600])
                print("---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
