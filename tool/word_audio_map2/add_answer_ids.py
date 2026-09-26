#!/usr/bin/env python3
"""Add ``chapter_answer_ids`` to every audio_map2 segment, parallel to
``chapter_question_ids`` (each question id maps to its HTML answer id via
``build/answer_map.json``).

Idempotent: only adds/replaces the ``chapter_answer_ids`` field; never touches
q_text / answer_text / start / end / status / meta.lastPlayed / notes.  Existing
``answer-…`` ids that the segment's ``chapter_question_ids`` cannot produce are
**kept** — those are answer-only links written by ``link_image_blocks.py`` for
ebook blocks that have no question div (圖片題 / 「問題丟失」), and a merged
segment can carry both kinds at once.

Usage:
  .venv/bin/python add_answer_ids.py          # dry-run: report counts
  .venv/bin/python add_answer_ids.py --apply  # write JSONs back
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"
ANSWER_MAP = Path(__file__).resolve().parent / "build" / "answer_map.json"


def add_answer_ids(data: dict, amap: dict) -> dict:
    """Return summary counts; mutate data in place."""
    added = missing = total_qids = kept_answer_only = 0
    for sess in data.get("sessions") or []:
        for seg in sess.get("segments") or []:
            qids = seg.get("chapter_question_ids") or []
            aids = []
            hit_missing = False
            for qid in qids:
                total_qids += 1
                aid = amap.get(qid)
                if aid:
                    aids.append(aid)
                    added += 1
                else:
                    hit_missing = True
                    missing += 1
            # Answer blocks that have no question div of their own (圖片題 /
            # 「問題丟失」block) are linked by link_image_blocks.py with
            # chapter_answer_ids only — there is no qid to derive them from, so
            # keep any existing answer-… id that this segment's qids do not
            # produce.  A merged segment can carry both kinds at once.
            derived = set(aids)
            kept = [a for a in (seg.get("chapter_answer_ids") or [])
                    if a.startswith("answer-") and a not in derived]
            kept_answer_only += len(kept)
            aids = aids + kept
            if aids:
                seg["chapter_answer_ids"] = aids
            else:
                seg.pop("chapter_answer_ids", None)
            # mark segments missing an answer id for targeted review
            if hit_missing and qids:
                note = seg.get("notes") or ""
                if "缺 answer 對應" not in note:
                    seg["notes"] = (note + " | html-resplit: 缺 HTML answer 對應，待人工確認").strip(" |")
    return {"added": added, "missing": missing, "total_qids": total_qids,
            "kept_answer_only": kept_answer_only}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--month", action="append", help="YYYY-MM (repeatable)")
    args = ap.parse_args()

    amap = json.loads(ANSWER_MAP.read_text(encoding="utf-8"))
    print(f"loaded answer map: {len(amap)} pairs")

    months = args.month or sorted(p.stem for p in AUDIO_MAP2_DIR.glob("????-??.json"))
    for m in months:
        path = AUDIO_MAP2_DIR / f"{m}.json"
        if not path.exists():
            print(f"!! {m}: no JSON")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        # snapshot the relevant field to detect change
        before = json.dumps([
            (s.get("session_id"), g.get("chapter_answer_ids"))
            for s in data["sessions"] for g in s["segments"]
        ], ensure_ascii=False)
        summary = add_answer_ids(data, amap)
        after = json.dumps([
            (s.get("session_id"), g.get("chapter_answer_ids"))
            for s in data["sessions"] for g in s["segments"]
        ], ensure_ascii=False)
        changed = before != after
        print(f"{m}: qids={summary['total_qids']} answer-linked={summary['added']} "
              f"missing-answer={summary['missing']} changed={changed}")
        if args.apply and changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
            print(f"  {m}: WRITTEN")
    if not args.apply:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())