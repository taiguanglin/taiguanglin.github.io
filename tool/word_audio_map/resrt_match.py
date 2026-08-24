#!/usr/bin/env python3
"""Re-match still-missing questions against RE-TRANSCRIBED SRTs.

For every missing segment whose first-answer-date session has a freshly
transcribed SRT under ``build/resrt/`` (same stem as the original), retry the
alignment against that transcript and patch the maps. Audio file / session
metadata come from the real inventory session so playback keeps working.

Usage:
    python3 resrt_match.py [--resrt-dir build/resrt]
                           [--t-accept 12] [--t-noname 13] [--t-review 9]
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

from wcommon import (  # noqa: E402
    BUILD_DIR,
    WORD_MAP_DIR,
    SessionStream,
    get_converter,
    inventory_sessions,
    load_questions,
    parse_srt,
    parse_srt_raw,
    range_fields,
    srt_preview,
)
from word_align import (  # noqa: E402
    ANSWER_SKIP_HEAD,
    annotate_questions,
    apply_near_patches,
    _cheap_prefilter,
    lcb,
    usable_name,
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resrt-dir", type=Path, default=BUILD_DIR / "resrt")
    ap.add_argument("--questions", type=Path, default=BUILD_DIR / "questions.json")
    ap.add_argument("--map-dir", type=Path, default=WORD_MAP_DIR)
    ap.add_argument("--t-accept", type=float, default=12.0)
    ap.add_argument("--t-noname", type=float, default=13.0)
    ap.add_argument("--t-review", type=float, default=9.0)
    args = ap.parse_args(argv)

    converter = get_converter()
    qs = load_questions(args.questions)
    by_key = {f"{q['chapter_index']:02d}#q{q['number']}": q for q in qs}
    sessions = inventory_sessions()
    dates = [s["date"] for s in sessions]
    by_date: Dict[str, List[dict]] = {}
    for s in sessions:
        by_date.setdefault(s["date"], []).append(s)

    # collect missing segments grouped by their FIRST answer date
    missing: Dict[str, List[Tuple[str, str]]] = {}  # date -> [(qid, stable_key)]
    busy: Dict[str, List[List[float]]] = {}
    for path in sorted(args.map_dir.glob("word-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for s in data.get("segments") or []:
            if s.get("start") is not None and s.get("session_id"):
                busy.setdefault(s["session_id"], []).append(
                    [float(s["start"]), float(s.get("end") or s["start"])]
                )
            if s.get("start") is None and not s.get("locked"):
                qd = s.get("question_date")
                if not qd:
                    continue
                i = bisect.bisect_left(dates, qd)
                if i < len(dates):
                    missing.setdefault(dates[i], []).append(
                        (s["question_id"], s["stable_key"])
                    )

    resrts = {p.stem: p for p in args.resrt_dir.glob("*.srt")}
    print(f"missing grouped on {len(missing)} first-dates; "
          f"{len(resrts)} re-transcribed SRTs available")

    # annotate needles for every question we may retry
    need_keys = {k for items in missing.values() for _, k in items}
    to_annotate = [q for k, q in by_key.items() if k in need_keys]
    annotate_questions(to_annotate, converter)

    total_auto = total_rev = 0
    all_patches: List[dict] = []
    for date, items in sorted(missing.items()):
        day_sessions = by_date.get(date) or []
        # try each same-day session's re-transcript if present
        for session in day_sessions:
            stem = session["stem"]
            rsrt = resrts.get(stem)
            if rsrt is None:
                continue
            cues = parse_srt(rsrt, converter)
            if not cues:
                continue
            raw = parse_srt_raw(rsrt)
            st = SessionStream(session, cues, converter, raw)
            stream = st.py
            batch: List[List[float]] = []
            n_auto = n_rev = 0
            for qid, stable_key in items:
                q = by_key.get(stable_key)
                if q is None:
                    continue
                np_, ap, qp = q["_np"], q["_ap"], q["_qp"]
                hit = None
                if len(np_) >= 3:
                    pos = 0
                    for _ in range(40):
                        i2 = stream.find(np_, pos)
                        if i2 < 0:
                            break
                        sc = _verify_local(stream, i2, ap, qp)
                        if sc >= args.t_accept:
                            hit = (sc, i2, "name+verify")
                            break
                        pos = i2 + max(len(np_), 1)
                needle = ap if len(ap) >= 20 else qp
                probe = (
                    needle[ANSWER_SKIP_HEAD:]
                    if len(needle) > ANSWER_SKIP_HEAD + 24
                    else needle
                )
                if hit is None and len(probe) >= 20 \
                        and _cheap_prefilter(stream, probe):
                    m = SequenceMatcher(None, stream, probe, autojunk=False) \
                        .find_longest_match(0, len(stream), 0, len(probe))
                    if m.size >= args.t_noname:
                        hit = (float(m.size), m.a, "answer-only")
                review_hit = None
                if hit is None and len(probe) >= 20 \
                        and _cheap_prefilter(stream, probe):
                    m = SequenceMatcher(None, stream, probe, autojunk=False) \
                        .find_longest_match(0, len(stream), 0, len(probe))
                    if m.size >= args.t_review:
                        review_hit = (float(m.size), m.a)

                def emit(char_pos, score, method, status):
                    start_t = st.cue_start_time(char_pos)
                    sid = session["session_id"]
                    existing = list(busy.get(sid) or ()) + list(batch)
                    for es, _ee in existing:
                        if es - 2.0 <= start_t < es + 75.0:
                            return False
                    later = [es for es, _ee in existing if es >= start_t]
                    end_t = min([start_t + 300.0, st.audio_end] + later)
                    if end_t <= start_t:
                        end_t = start_t + 30.0
                    fields = range_fields(
                        start_t, end_t, round(min(1.0, score / 60.0), 3),
                        status, srt_preview(st.raw_cues, start_t, end_t),
                    )
                    fields["notes"] = f"method=reasr({method})"
                    all_patches.append(
                        {
                            "question_id": qid,
                            "stable_key": stable_key,
                            **fields,
                            "session_id": sid,
                            "session_date": session["date"],
                            "source": session["source"],
                            "audio_file": session["audio_file"],
                            "srt_file": str(rsrt),
                        }
                    )
                    batch.append([start_t, end_t])
                    return True

                if hit is not None:
                    score, char_pos, method = hit
                    if emit(char_pos, score, method, "auto"):
                        n_auto += 1
                    continue
                if review_hit is not None:
                    score, char_pos = review_hit
                    if emit(char_pos, score, "reasr-review", "review"):
                        n_rev += 1
            total_auto += n_auto
            total_rev += n_rev
            if n_auto or n_rev:
                print(f"  {date} {session['source']}: "
                      f"auto={n_auto} review={n_rev}", flush=True)

        # refresh busy from patched state so later dates see earlier claims
        for p in all_patches:
            busy.setdefault(p["session_id"], []).append(
                [float(p["start"]), float(p.get("end") or p["start"])]
            )

    n_auto = sum(1 for p in all_patches if p.get("status") == "auto")
    n_rev = sum(1 for p in all_patches if p.get("status") == "review")
    print(f"TOTAL recovered: auto={n_auto} review={n_rev}")
    if all_patches:
        n = apply_near_patches(all_patches, args.map_dir)
        print(f"Done: {n} segment(s) written")
    return 0


def _verify_local(stream, pos, ap, qp) -> float:
    win = stream[pos : pos + 1400]
    score = 0.0
    if ap:
        score = lcb(win, ap)
    if qp:
        score = max(score, lcb(win, qp) * 0.9)
    return score


if __name__ == "__main__":
    raise SystemExit(main())
