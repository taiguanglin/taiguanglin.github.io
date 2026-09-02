#!/usr/bin/env python3
"""Guarantee zero loss of frozen ``chapter_question_ids`` across the resplit.

apply_resplit + redistribution preserve most of the frozen mapping, but a
handful of frozen qids (concentrated in the manually-reviewed-poor 2024-02/03
months) can drop when a frozen single-qid segment's text is re-aligned.  This
pass compares the resplit output against git HEAD and, for any frozen qid that
no longer appears anywhere, re-attaches it to the resplit segment whose
answer_text/q_text best matches its ORIGINAL frozen segment's answer_text.

Usage:
  .venv/bin/python reconcile_qids.py            # dry-run report
  .venv/bin/python reconcile_qids.py --apply    # write back
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"
RNOTES = "resplit: follow-up Q&A separated (極樂是我家-style merged block)"


def norm(s: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "", (s or "").strip().lower())


def git_show(path: str) -> dict:
    out = subprocess.run(["git", "show", f"HEAD:{path}"],
                         capture_output=True, text=True).stdout
    return json.loads(out) if out else {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    # 1) collect frozen qid -> original segment text (from git HEAD)
    frozen: dict[str, dict] = {}
    for path in sorted(AUDIO_MAP2_DIR.glob("*.json")):
        rel = path.relative_to(ROOT).as_posix()
        do = git_show(rel)
        for s in do.get("sessions") or []:
            for g in s.get("segments") or []:
                for qid in (g.get("chapter_question_ids") or []):
                    frozen[qid] = {
                        "a_text": g.get("answer_text") or "",
                        "q_text": g.get("q_text") or "",
                        "ch": g.get("chapter_indexes") or [],
                    }

    # 2) collect which qids remain in the resplit output, and index new segments
    new_qids: set = set()
    new_segs: list[tuple] = []  # (path, data, session, seg)
    for path in sorted(AUDIO_MAP2_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for s in data.get("sessions") or []:
            for g in s.get("segments") or []:
                for qid in (g.get("chapter_question_ids") or []):
                    new_qids.add(qid)
                new_segs.append((path, data, s, g))

    lost = {q: v for q, v in frozen.items() if q not in new_qids}
    print(f"frozen qids: {len(frozen)}; lost in resplit: {len(lost)}")

    # 3) re-attach each lost qid to its best-matching new segment
    reattached = 0
    for qid, f in lost.items():
        fa = norm(f["a_text"])
        fq = norm(f["q_text"])
        best_score, best_seg = -1.0, None
        for path, data, s, g in new_segs:
            na = norm(g.get("answer_text") or "")
            nq = norm(g.get("q_text") or "")
            # prefer answer overlap (more distinctive)
            score = 0.0
            if fa and na:
                import difflib
                score = max(score, difflib.SequenceMatcher(None, fa[:400], na[:400]).ratio())
            if fq and nq:
                import difflib
                score = max(score, difflib.SequenceMatcher(None, fq, nq).ratio())
            if score > best_score:
                best_score, best_seg = score, (path, data, s, g)
        if best_seg and best_score >= 0.15:
            path, data, s, g = best_seg
            ch = f["ch"]
            g.setdefault("chapter_question_ids", [])
            g.setdefault("chapter_indexes", [])
            if qid not in g["chapter_question_ids"]:
                g["chapter_question_ids"].append(qid)
                g["chapter_indexes"].append(ch[0] if ch else None)
                reattached += 1
                # append a note marking reconciliation
                note = g.get("notes") or ""
                if "reconciled" not in note:
                    g["notes"] = (note + " ; reconciled:qid").strip(" ;")
                if args.apply:
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"reattached: {reattached}; still lost: {len(lost) - reattached}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())