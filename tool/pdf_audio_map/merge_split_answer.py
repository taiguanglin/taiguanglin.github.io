#!/usr/bin/env python3
"""Merge a wrongly-split PDF audio_map segment back into its predecessor.

This pipeline (data/audio_map/, chapters 13–21) splits the master's one
continuous answer into «question stub + answer remnant» in some cases (e.g.
2025-07-08 贴吧 咪了个喵xxx: the answer continuation「昨天还有人问…？」was
turned into a fake second question).  This merges segment ``drop_idx`` back
into ``keep_idx`` (append its q_text + answer_text onto keep's answer), deletes
it, renumbers 1..N, and regenerates ``stable_key`` with the rule from
``tool/pdf_audio_map/extract_sessions.py``:

    questioner|question_time|idx   if questioner and question_time
    section_id#idx                 otherwise

question_id is HTML-card-derived (not index-derived), so it is left untouched;
the surviving segment keeps its question_id.  start/end/meta.lastPlayed are
preserved (the merged segment's end is extended to cover the drop segment).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAP_DIR = REPO / "tool" / "word2ebook" / "data" / "audio_map"


def _stable_key(session: dict, seg: dict, idx: int) -> str:
    q = seg.get("questioner") or ""
    t = seg.get("question_time") or ""
    if q and t:
        return f"{q}|{t}|{idx}"
    sid = session.get("section_id") or session.get("session_id")
    return f"{sid}#{idx}"


def _fmt_ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def merge(session: dict, keep_idx: int, drop_idx: int) -> dict:
    segs = session["segments"]
    keep = next(g for g in segs if g["index"] == keep_idx)
    drop = next(g for g in segs if g["index"] == drop_idx)

    # extend answer: keep.answer + "\n\n" + drop.q_text + "\n\n" + drop.answer
    parts = []
    if (keep.get("answer_text") or "").strip():
        parts.append(keep["answer_text"].rstrip())
    if (drop.get("q_text") or "").strip():
        parts.append(drop["q_text"].strip())
    if (drop.get("answer_text") or "").strip():
        parts.append(drop["answer_text"].rstrip())
    keep["answer_text"] = "\n\n".join(parts)

    # preview
    keep["answer_preview"] = keep["answer_text"][:120]

    # time: extend end to drop's end
    if drop.get("end") is not None:
        keep["end"] = drop["end"]
        if isinstance(keep.get("end"), (int, float)):
            keep["end_label"] = _fmt_ts(float(keep["end"]))

    # notes
    keep["notes"] = (keep.get("notes") or "") + f"；已併入#{drop_idx}（原誤拆，答案延續）"

    # delete drop and renumber
    session["segments"] = [g for g in segs if g["index"] != drop_idx]
    for i, g in enumerate(session["segments"], start=1):
        g["index"] = i
        g["stable_key"] = _stable_key(session, g, i)
    return keep


def main() -> int:
    # 2025-07-08 贴吧: merge #2 (咪了个喵xxx「昨天还有人问…」) into #1.
    month = "2025-07"
    sid = "2025-07-08-tieba"
    data = json.loads((MAP_DIR / f"{month}.json").read_text(encoding="utf-8"))
    for s in data["sessions"]:
        if s["session_id"] == sid:
            keep = merge(s, 1, 2)
            print(f"Merged {sid} #2 -> #1")
            print(f"  q_text: {keep['q_text'][:50]!r}")
            print(f"  answer_text ends with: {keep['answer_text'][-60:]!r}")
            print(f"  start={keep['start']} end={keep['end']} qid={keep['question_id']}")
            print(f"  lastPlayed={keep.get('meta', {}).get('lastPlayed')!r}")
            break
    else:
        print(f"session {sid} not found")
        return 1

    out = MAP_DIR / f"{month}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())