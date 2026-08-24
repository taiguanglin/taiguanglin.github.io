#!/usr/bin/env python3
"""Verify a built ebook against the word maps and the PDF-button baseline.

Checks (after `gen_all.py`):
1. Word chapters 01–12: every mapped segment with a range has exactly one
   `.qa-play` button in both simplified and traditional variants; questions
   without a range have none.
2. PDF chapters 13–21: button counts match `build/pdf_button_baseline.json`
   (zero regression).
3. Reports overall coverage.

Usage: python3 verify_build.py [--ebook-dir ../../wenda2_ebook]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

from wcommon import BUILD_DIR, WORD_MAP_DIR  # noqa: E402

BUTTON_RE = re.compile(r'<button class="qa-play"')
QUESTION_RE = re.compile(r'<div class="question" id="([^"]+)"')
# A meta bar whose close sits directly against the question div
BAR_TAIL_RE = re.compile(
    r'<div class="qa-meta-bar[^"]*"[^>]*>(?:(?!</div>).)*</div>\s*\Z', re.S
)


def chapter_buttons(html: str) -> dict:
    """Map question_id → number of buttons in an immediately-preceding bar."""
    out = {}
    for m in QUESTION_RE.finditer(html):
        tail = html[max(0, m.start() - 3000) : m.start()]
        n = 0
        bm = BAR_TAIL_RE.search(tail[-2500:])
        if bm:
            n = len(BUTTON_RE.findall(bm.group(0)))
        out[m.group(1)] = n
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ebook-dir", type=Path,
                    default=TOOL_DIR.parent.parent / "wenda2_ebook")
    args = ap.parse_args()

    problems = []

    # --- word chapters -----------------------------------------------------
    total_q = total_mapped = total_review = total_unconfirmed = 0
    problems = []
    for map_path in sorted(WORD_MAP_DIR.glob("word-*.json")):
        data = json.loads(map_path.read_text(encoding="utf-8"))
        ch = data["chapter"]
        segs = data.get("segments") or []

        def _confirmed(s):
            meta = s.get("meta") or {}
            return bool(meta.get("confirmed") or meta.get("lastPlayed"))

        mapped = {
            s["question_id"] for s in segs
            if s.get("start") is not None and s.get("status") == "auto"
            and _confirmed(s)
        }
        review = {s["question_id"] for s in segs if s.get("status") == "review"}
        # autos that are aligned but NOT yet proofread → buttonless by design
        unconf = sum(
            1 for s in segs
            if s.get("start") is not None and s.get("status") == "auto"
            and not _confirmed(s)
        )
        total_mapped += len(mapped)
        total_review += len(review)
        total_unconfirmed += unconf
        total_q += len(segs)
        for variant in (f"{ch}.html", f"{ch}_trad.html"):
            page = args.ebook_dir / variant
            if not page.exists():
                problems.append(f"missing built page: {page}")
                continue
            html = page.read_text(encoding="utf-8")
            buttons = chapter_buttons(html)
            expect = {}
            for qid in mapped:
                expect[qid] = 1
            for qid in review:
                expect.setdefault(qid, 0)
            for s in segs:
                qid = s["question_id"]
                want = expect.get(qid, 0)
                got = buttons.get(qid, -1)
                if got != want:
                    problems.append(
                        f"{variant} {qid}: expected {want} button(s), found {got}"
                    )
    print(f"Word chapters: {total_mapped}/{total_q} confirmed+buttoned "
          f"(+{total_review} review, +{total_unconfirmed} auto-unconfirmed; "
          f"both buttonless) = {(total_mapped / total_q if total_q else 0):.1%}")

    # --- pdf regression (word chapters legitimately differ from the old
    # zero-button baseline, so only PDF chapters are compared) --------------
    baseline_path = BUILD_DIR / "pdf_button_baseline.json"
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        for name, want in sorted(baseline.items()):
            ch = int(name[:2])
            if ch < 13:
                continue  # word chapter — buttons are new by design
            page = args.ebook_dir / name
            got = len(BUTTON_RE.findall(page.read_text(encoding="utf-8"))) \
                if page.exists() else -1
            mark = "✓" if got == want else "✗"
            if got != want:
                problems.append(f"{name}: baseline {want} buttons, now {got}")
            print(f"  {mark} {name}: {got} buttons (baseline {want})")

    if problems:
        print(f"\n❌ {len(problems)} problem(s):")
        for p in problems[:40]:
            print("  -", p)
        return 1
    print("\n✅ build verified: word buttons correct, PDF chapters unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
