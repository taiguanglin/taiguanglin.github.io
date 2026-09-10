#!/usr/bin/env python3
"""Add an ``html_verbatim`` flag to every audio_map2 segment (one field only,
idempotent, never touches text/times/lastPlayed/notes).

True  → the segment's q_text AND answer_text both exactly match its HTML block
        (after cosmetic normalization: t2s, 著→着, zero-width space, halfwidth
        →fullwidth punctuation).
False → the text differs (reworded question, sub-question grouping, or lexical
        variants like 薰/熏, 揹/背) — Word text is authoritative; the review UI
        shows "與 HTML 用字略異" so a human can eyeball it.

Usage:
  .venv/bin/python mark_html_diff.py            # dry-run
  .venv/bin/python mark_html_diff.py --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP2 = ROOT / "audio_map2"
TOOL = Path(__file__).resolve().parent
HTML_QA = json.loads((TOOL / "build" / "html_qa_simp.json").read_text(encoding="utf-8"))

HW2FW = str.maketrans({",": "，", ".": "。", "!": "！", "?": "？", ":": "：",
                       ";": "；", "(": "（", ")": "）", "[": "【", "]": "】"})
try:
    from opencc import OpenCC
    _CC = OpenCC("t2s")
except Exception:
    _CC = None


def norm(s: str) -> str:
    if not s:
        return ""
    if _CC is not None:
        s = _CC.convert(s)
    s = s.replace("著", "着").replace("\u200b", "")
    s = re.sub(r"\s+", "", s)
    return s.translate(HW2FW)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--month", action="append")
    args = ap.parse_args()

    months = args.month or sorted(p.stem for p in MAP2.glob("????-??.json"))
    for m in months:
        path = MAP2 / f"{m}.json"
        if not path.exists():
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        changed = 0
        for s in d.get("sessions") or []:
            for g in s.get("segments") or []:
                qids = g.get("chapter_question_ids") or []
                if len(qids) != 1:
                    val = None
                else:
                    h = HTML_QA.get(qids[0])
                    val = bool(h and norm(g.get("q_text") or "") == norm(h["q_text"])
                               and norm(g.get("answer_text") or "") == norm(h["a_text"]))
                if val is not None and g.get("html_verbatim") != val:
                    g["html_verbatim"] = val
                    changed += 1
                elif val is None:
                    g.pop("html_verbatim", None)
        print(f"{m}: html_verbatim set on {changed} segments")
        if args.apply and changed:
            path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", "utf-8")
            print(f"  {m}: WRITTEN")
    if not args.apply:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())