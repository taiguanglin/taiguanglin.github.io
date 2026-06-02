#!/usr/bin/env python3
"""Collapse the blank line(s) directly after the answer label.

Old format:
    Taiguanglin：

    答案文字...

New format:
    Taiguanglin：
    答案文字...

Only blank lines immediately following the label are removed; blank lines
between answer paragraphs are preserved.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QA_DIR = ROOT / "qa"
ANSWER_LABEL = "Taiguanglin："

# Match the label line, then one or more blank lines, capturing nothing else.
PATTERN = re.compile(r"^(Taiguanglin[:：])[ \t]*\n(?:[ \t]*\n)+", re.M)


def reformat(text: str) -> str:
    return PATTERN.sub(lambda m: f"{m.group(1)}\n", text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", help="qa txt files; defaults to all qa/*.txt")
    parser.add_argument("--apply", action="store_true", help="write changes")
    args = parser.parse_args(argv)

    files = (
        [Path(p) if Path(p).is_absolute() else ROOT / p for p in args.paths]
        if args.paths
        else sorted(QA_DIR.glob("*.txt"))
    )

    changed = 0
    for path in files:
        original = path.read_text(encoding="utf-8")
        updated = reformat(original)
        if updated != original:
            changed += 1
            if args.apply:
                path.write_text(updated, encoding="utf-8")
            print(f"{'updated' if args.apply else 'would update'}\t{path.name}")
    print(f"files={len(files)} changed={changed} apply={args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
