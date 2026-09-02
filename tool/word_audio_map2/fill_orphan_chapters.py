#!/usr/bin/env python3
"""Fill chapter_question_ids / chapter_indexes for the newly-split "resplit"
orphan segments produced by apply_resplit.py, by content-matching their q_text
(and fallback answer_text) against the reconstructed ebook questions.json.

Only touches segments whose `notes` contains the resplit marker AND that lack
``chapter_question_ids`` — never overwrites the frozen mapping carried over by
apply_resplit.py.

Usage:
  .venv/bin/python fill_orphan_chapters.py            # dry-run report
  .venv/bin/python fill_orphan_chapters.py --apply    # write back
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"
QUESTIONS = ROOT / "tool" / "word_audio_map2" / "build" / "questions.json"
RNOTES = "resplit: follow-up Q&A separated (極樂是我家-style merged block)"


def norm(s: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "", (s or "").strip().lower())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    by_nq = {}
    for q in questions:
        by_nq.setdefault(norm(q["q_text"]), []).append(q)

    filled = 0
    unfilled = []
    for path in sorted(AUDIO_MAP2_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        touched = False
        for s in data.get("sessions") or []:
            for g in s.get("segments") or []:
                notes = g.get("notes") or ""
                if RNOTES not in notes:
                    continue
                if g.get("chapter_question_ids"):
                    continue
                q_text = g.get("q_text") or ""
                a_text = g.get("answer_text") or ""
                nq = norm(q_text)

                # 1) exact q_text
                cand = None
                how = ""
                if nq and by_nq.get(nq):
                    cand = by_nq[nq]
                    how = "q_exact"
                # 2) fuzzy q_text >= 0.8
                if cand is None and nq:
                    best, bs = None, 0.0
                    for q in questions:
                        nqq = norm(q["q_text"])
                        if not nqq:
                            continue
                        r = difflib.SequenceMatcher(None, nq, nqq).ratio()
                        if r > bs:
                            bs, best, cand_q = r, q, [q]
                    if best is not None and bs >= 0.8:
                        cand = cand_q
                        how = f"q_fuzzy({bs:.2f})"
                    else:
                        # 3) answer_text >= 0.85
                        na = norm(a_text)
                        if na:
                            best, bs = None, 0.0
                            for q in questions:
                                nxa = norm(q["a_text"])
                                if not nxa:
                                    continue
                                r = difflib.SequenceMatcher(None, na[:400], nxa).ratio()
                                if r > bs:
                                    bs, best, cand_q = r, q, [q]
                            if best is not None and bs >= 0.85:
                                cand = cand_q
                                how = f"a_fuzzy({bs:.2f})"

                if cand:
                    g["chapter_question_ids"] = [q["question_id"] for q in cand]
                    g["chapter_indexes"] = [q["chapter_index"] for q in cand]
                    g["_chapter_fill"] = how
                    filled += 1
                    touched = True
                else:
                    unfilled.append((path.stem, s["session_id"], g.get("index"),
                                     q_text[:40].replace("\n", " ")))
        if touched and args.apply:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"filled: {filled}")
    print(f"unfilled: {len(unfilled)}")
    for u in unfilled:
        print("  UNFILLED", u)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())