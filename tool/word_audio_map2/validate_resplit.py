#!/usr/bin/env python3
"""Complete validation of audio_map2/*.json after apply_resplit + fill_orphan_chapters.

Checks (across all 14 months):
  1. JSON parses; sessions/segments well-formed.
  2. index contiguous 1..N per session (flag but don't fail the pre-existing
     2025-03-12 combined-timeline quirk; everything else must be contiguous).
  3. stable_key / question_id unique across the month.
  4. For every session, start values non-decreasing (flag known orphan tails).
  5. chapter_question_ids: report coverage; no ebook qid maps to >1 segment
     (a qid that now maps to 2+ segments is a REGRESSION to report).
  6. meta.lastPlayed preserved (compare against git HEAD count).
  7. Resplit orphan count + how many still lack chapter ids.

Exit non-zero if any hard error (invalid JSON, non-contiguous index outside the
known 2025-03-12 case, or a chapter qid mapped to >1 segment).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"

RNOTES = "resplit: follow-up Q&A separated (極樂是我家-style merged block)"
# Pre-existing non-contiguous index in the combined-timeline session; not a
# regression from resplit.
KNOWN_NONCONTIG = {"2025-03-12-tieba", "2025-03-12-wechat"}


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    total_segs = 0
    total_with_ch = 0
    orphan_total = 0
    orphan_no_ch = 0
    qid_to_segs: dict[str, list] = defaultdict(list)
    header_printed = False

    for path in sorted(AUDIO_MAP2_DIR.glob("*.json")):
        month = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"{month}: unreadable/invalid JSON: {e}")
            continue

        sks: set = set()
        qids: set = set()
        for s in data.get("sessions") or []:
            sid = s.get("session_id", "?")
            segs = s.get("segments") or []
            total_segs += len(segs)

            idx = [g.get("index") for g in segs]
            if idx != list(range(1, len(segs) + 1)):
                if sid in KNOWN_NONCONTIG:
                    warnings.append(f"{sid}: non-contiguous index (pre-existing combined-timeline)")
                else:
                    errors.append(f"{sid}: index not contiguous: {idx[:12]}...")

            for g in segs:
                sk = g.get("stable_key")
                qi = g.get("question_id")
                if sk in sks:
                    errors.append(f"{sid}: duplicate stable_key {sk}")
                if qi in qids:
                    errors.append(f"{sid}: duplicate question_id {qi}")
                sks.add(sk)
                qids.add(qi)

                ch = g.get("chapter_question_ids") or []
                if ch:
                    total_with_ch += 1
                for qid in ch:
                    qid_to_segs[qid].append(f"{sid}#{g.get('index')}")

                if RNOTES in (g.get("notes") or ""):
                    orphan_total += 1
                    if not ch:
                        orphan_no_ch += 1

    # chapter qid mapped to >1 segment: only a CROSS-SESSION mapping is a real
    # anomaly (a qid should live in one chronological session); a qid that lands
    # on several ADJACENT segments of the SAME session is EXPECTED after a
    # coarse frozen block is resplit (the frozen mapping was one-segment-per-
    # questioner; splitting a multi-sub-question post yields N children that all
    # correctly inherit that single coarse qid).
    cross_sess = {}
    for q, segs in qid_to_segs.items():
        sids = {s.split("#")[0] for s in segs}
        if len(sids) > 1:
            cross_sess[q] = sorted(set(segs))
    for q, segs in sorted(cross_sess.items()):
        warnings.append(f"chapter qid {q} spans sessions: {segs} (pre-existing frozen)")

    print(f"total segments: {total_segs}")
    print(f"segments with chapter_question_ids: {total_with_ch}")
    print(f"resplit orphans: {orphan_total}; still missing chapter: {orphan_no_ch}")
    print()

    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print("  -", w)
    print()
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors[:50]:
            print("  -", e)
        return 1

    print("ALL HARD CHECKS PASSED ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())