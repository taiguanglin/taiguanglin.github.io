#!/usr/bin/env python3
"""Redistribute inherited frozen ``chapter_question_ids`` to resplit children.

apply_resplit.py splits a merged block (one poster's multiple numbered
sub-questions, frozen as ONE segment with ``chapter_question_ids=[A,B,…]`` and a
parallel ``chapter_indexes=[…]``) into one segment per sub-question.  Because the
whole list was copied onto each child, one ebook question id ends up on several
segments.

This pass fixes that: for every run of CONSECUTIVE segments sharing an identical
multi-qid list, each of the frozen qids is assigned to the child whose text best
matches it (q_text, fallback answer_text), using the reconstructed ebook
``questions.json`` as an optional text hint.  A child may carry zero, one, or
several qids — the frozen list sometimes encodes more sub-questions than the
resplit produced (a long 问题一 that the frozen map split into two qids), and the
hard guarantee is that NO frozen qid is ever lost.

The chapter index for each qid is taken from the frozen segment's own parallel
``chapter_indexes`` array — this pass never depends on ``questions.json`` existing
for every qid (39 frozen qids predate the reconstruction and would otherwise
KeyError).

Usage:
  .venv/bin/python redistribute_chapters.py            # dry-run report
  .venv/bin/python redistribute_chapters.py --apply    # write back
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


def norm(s: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "", (s or "").strip().lower())


def load_questions() -> dict:
    if not QUESTIONS.exists():
        return {}
    qs = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    return {q["question_id"]: q for q in qs}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    qmap = load_questions()  # optional text hint; may omit some frozen qids
    redistributed = 0
    unresolved = []

    for path in sorted(AUDIO_MAP2_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        touched = False
        for s in data.get("sessions") or []:
            segs = s.get("segments") or []
            i = 0
            while i < len(segs):
                cur = segs[i].get("chapter_question_ids") or []
                if len(cur) < 2:
                    i += 1
                    continue
                # find run of consecutive segments with identical list
                j = i
                while j + 1 < len(segs) and (segs[j + 1].get("chapter_question_ids") or []) == cur:
                    j += 1
                run = segs[i:j + 1]
                if len(run) < 2:
                    i = j + 1
                    continue

                # frozen qid -> chapter index (parallel arrays), authoritative.
                cur_idx = segs[i].get("chapter_indexes") or []
                qid_to_ch = {}
                for k, qid in enumerate(cur):
                    ch = cur_idx[k] if k < len(cur_idx) else None
                    qid_to_ch[qid] = ch

                # qid-centric: assign each qid to its best-matching child.
                # No qid is dropped; missing-text qids fall back positionally.
                bests: dict[str, tuple] = {}   # qid -> (score, seg)
                for pos, qid in enumerate(cur):
                    q = qmap.get(qid)
                    b_seg, b_score = None, -1.0
                    for seg in run:
                        nq = norm(seg.get("q_text") or "")
                        na = norm(seg.get("answer_text") or "")
                        if q:
                            r = max(
                                difflib.SequenceMatcher(None, nq, norm(q.get("q_text") or "")).ratio() if nq else 0.0,
                                difflib.SequenceMatcher(None, na[:300], norm(q.get("a_text") or "")[:300]).ratio() if na else 0.0,
                            )
                        else:
                            r = 0.0  # no text hint; positional below
                        if r > b_score:
                            b_score, b_seg = r, seg
                    if b_seg is None:
                        # no child at all (shouldn't happen) — positional
                        b_seg = run[min(pos, len(run) - 1)]
                    bests[qid] = (b_score, b_seg)

                # resolve ties / all-zero (missing text): assign positionally so
                # qids keep relative order and none is lost.
                if any(score <= 0.0 for score, _ in bests.values()):
                    for pos, qid in enumerate(cur):
                        seg = run[min(pos, len(run) - 1)]
                        bests[qid] = (bests[qid][0], seg)

                for seg in run:
                    seg["chapter_question_ids"] = []
                    seg["chapter_indexes"] = []
                for qid in cur:
                    score, seg = bests[qid]
                    seg["chapter_question_ids"].append(qid)
                    seg["chapter_indexes"].append(qid_to_ch.get(qid))

                redistributed += len(cur)
                touched = True
                i = j + 1
        if touched and args.apply:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"redistributed qids: {redistributed}")
    print(f"unresolved: {len(unresolved)}")
    for u in unresolved[:40]:
        print("  ", u)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())