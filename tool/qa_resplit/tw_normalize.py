#!/usr/bin/env python3
"""Normalise qa/*.txt to Taiwan-standard Traditional character forms.

Uses OpenCC `t2tw` (TWVariants), which maps non-Taiwan traditional variants to
the Taiwan MOE standard form. This is character-level only (no vocabulary
localisation), e.g.:
    喫→吃  纔→才  裏→裡  爲→為  着→著  羣→群  泄→洩  牀→床  癡→痴
    麪→麵  啓→啟  衆→眾  峯→峰  祕→秘  鉢→缽 ...

Usage: python3 tw_normalize.py [--apply] qa/*.txt
Without --apply, prints how many characters would change per file.
"""
import argparse
import sys
from pathlib import Path

try:
    from opencc import OpenCC
    _T2TW = OpenCC("t2tw")
except Exception:  # pragma: no cover
    _T2TW = None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    if _T2TW is None:
        print("error: OpenCC not available", file=sys.stderr)
        return 1

    grand = 0
    for p in args.paths:
        path = Path(p)
        text = path.read_text(encoding="utf-8")
        conv = _T2TW.convert(text)
        changed = sum(1 for a, b in zip(text, conv) if a != b) if len(text) == len(conv) else -1
        grand += max(changed, 0)
        if args.apply:
            if conv != text:
                path.write_text(conv, encoding="utf-8")
                print(f"applied {changed:>5}  {path.name}")
        elif changed:
            print(f"would change {changed:>5}  {path.name}")
    print(f"total char changes: {grand}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
