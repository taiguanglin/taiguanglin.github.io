#!/usr/bin/env python3
"""Scan all qa/*.txt and report how many segments realign could not match.

For each file, runs realign.py in report mode and counts the segments that were
left at their original value ("保留原值"), i.e. questions whose audio the SRT
reference does not contain. High counts flag files needing manual review.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
QA = REPO / "qa"
REALIGN = Path(__file__).resolve().parent / "realign.py"


def heading_count(path: Path) -> int:
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines()
               if ln.startswith("### "))


def main() -> int:
    rows = []
    files = sorted(QA.glob("*.txt"))
    for f in files:
        out = subprocess.run(
            [sys.executable, str(REALIGN), str(f)],
            capture_output=True, text=True,
        )
        blob = out.stdout + out.stderr
        unmatched = blob.count("保留原值")
        total = heading_count(f)
        if unmatched:
            rows.append((unmatched, total, f.name))
    rows.sort(reverse=True)
    print(f"scanned {len(files)} files; {len(rows)} have unmatched segments\n")
    print(f"{'unmatched/total':>16}  file")
    for un, total, name in rows:
        print(f"{un:>7}/{total:<7}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
