#!/usr/bin/env python3
"""Re-split chronological audio_map2 JSONs using the corrected follow-up-question
logic (_is_followup_question in build_maps.py), WITHOUT discarding the curated
state (start/end, start_label/end_label, confidence, status, notes, srt_preview,
meta.lastPlayed, chapter_question_ids, chapter_indexes).

Strategy: content-based carry-over.

  1. Re-run the Word parser (`parse_docx`) with the *new* `_block_to_chunk` to
     produce the new textual segment list for every month/session (text only).
  2. For every new segment, find its old counterpart by matching normalized
     `q_text` (exact) first, then by containment inside an old segment's
     `answer_text` (the multi-Q&A-merge case: the follow-up question's text was
     glued into the previous answer), then fuzzy fallback.
  3. Copy the old segment's curated fields across. A new segment that matches
     exactly one old segment inherits its time range / meta / chapter links.
  4. Newly-split-away sub-questions (no old counterpart) get:
       - inherited time = parent segment's range (they were one spoken unit),
       - inherited chapter_question_ids only where the parent's answer text
         clearly contained the sub-question (otherwise left for link step),
       - status="manual"/confidence=1.0 with a "resplit" note.
  5. Re-number indexes / stable_key / question_id / previews consistently.
  6. Write back ONLY changed months (preserving indent=2 as in the existing
     JSONs), then print a per-month report.

Usage:
  .venv/bin/python apply_resplit.py            # dry-run report only
  .venv/bin/python apply_resplit.py --apply    # write back
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import build_maps as bm
from build_maps import DOCX_PATH, DEFAULT_SRT_ROOT, Chunk, Part, WordSession  # noqa

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"


def norm(s: str) -> str:
    s = s if isinstance(s, str) else ""
    s = s.replace("\ufeff", "").replace("\xa0", " ")
    # strip Word field artifacts and whitespace, keep CJK + alnum
    import re
    s = re.sub(r"_x[0-9A-Fa-f]{4}_", "", s)
    return s.strip().lower()


def norm_key(s: str) -> str:
    """Aggressive normalizer for matching: drop all non-CJK/alnum."""
    import re
    return re.sub(r"[^\w\u4e00-\u9fff]", "", norm(s))


def fmt_label(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{int(s):02d}.{int(round((s - int(s)) * 1000)):03d}"


def question_id(sid: str, index: int, q_text: str) -> str:
    h = hashlib.sha1(f"{sid}#{index}#{q_text[:80]}".encode()).hexdigest()[:12]
    return f"question-{h}"


def build_new_sessions() -> Dict[str, dict]:
    """Return {session_id: {'segments': [text-only segment dicts in order]}}.

    Mirrors build_session_payload()'s sid + source-split logic and
    align_part()'s text segmentation + empty-question fold, but produces
    *text-only* segments (no align)."""
    sessions = bm.parse_docx(DOCX_PATH)
    out: Dict[str, dict] = {}

    def seg_texts(chunks: List[Chunk]) -> List[dict]:
        segs = []
        for ch in chunks:
            for g in ch.groups:
                q_text = "\n".join(g.q_paras).strip()
                a_text = "\n\n".join(g.a_paras).strip()
                segs.append({
                    "questioner": ch.name,
                    "question_time": ch.question_time,
                    "q_text": q_text,
                    "answer_text": a_text,
                })
        # fold consecutive groups with empty question (same questioner)
        merged = []
        for seg in segs:
            if merged and not seg["q_text"] and (
                not seg["questioner"] or seg["questioner"] == merged[-1]["questioner"]
            ):
                if seg["answer_text"]:
                    merged[-1]["answer_text"] = (
                        (merged[-1]["answer_text"] + "\n\n" + seg["answer_text"]).strip()
                    )
                continue
            merged.append(seg)
        return merged

    for sess in sessions:
        if sess.kind != "qa":
            continue
        date = f"{sess.year:04d}-{sess.month:02d}-{sess.day:02d}"
        for part in sess.parts:
            slug = {"main": "main", "贴吧": "tieba", "微信公众号": "wechat"}.get(part.source, "src")
            sid = f"{date}-{slug}"
            # combined-timeline fallback (same as build_session_payload)
            if len(sess.parts) == 1 and part.source in ("贴吧", "微信公众号"):
                mt = bm.resolve_media(sess.year, sess.month, sess.day, "贴吧")
                mw = bm.resolve_media(sess.year, sess.month, sess.day, "微信公众号")
                if mt["kind"] != "none" and mw["kind"] != "none":
                    sid = f"{date}-main"
            out[sid] = {"segments": seg_texts(part.chunks)}
    return out


def load_old() -> Dict[str, dict]:
    """{session_id: full session dict} from current audio_map2/*.json."""
    sessions: Dict[str, dict] = {}
    for path in sorted(AUDIO_MAP2_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for s in data.get("sessions") or []:
            sessions[s["session_id"]] = s
    return sessions


def build_old_index(old_sessions: Dict[str, dict]) -> Dict[str, List[dict]]:
    """index: norm_key(q_text) -> list of old segments (across all sessions)."""
    idx: Dict[str, List[dict]] = defaultdict(list)
    for sid, sess in old_sessions.items():
        for seg in sess.get("segments") or []:
            k = norm_key(seg.get("q_text") or "")
            if k:
                idx[k].append((sid, seg))
    return idx


RNOTES = "resplit: follow-up Q&A separated (極樂是我家-style merged block)"


def carry_over(
    new_sessions: Dict[str, dict],
    old_sessions: Dict[str, dict],
    qidx: Dict[str, List[dict]],
) -> Tuple[Dict[str, dict], Dict[str, int]]:
    """Produce new sessions with curated fields carried over.

    Returns (output_sessions, stats).
    """
    stats: Dict[str, int] = {"exact": 0, "containment": 0, "fuzzy": 0, "emptyq": 0, "orphan": 0}

    out_sessions: Dict[str, dict] = {}
    skipped_structural: List[str] = []
    for sid, ns in sorted(new_sessions.items()):
        old = old_sessions.get(sid)
        if old is None:
            # structural divergence (e.g. 2025-03-12 combined timeline, or
            # 2025-06/07 which have no baseline) — don't fabricate curation.
            skipped_structural.append(sid)
            continue
        old_segs = old.get("segments") or []
        # precompute old normalized (q, a) and full text for containment
        old_keys = []
        for oseg in old_segs:
            oq = norm_key(oseg.get("q_text") or "")
            oa = norm_key(oseg.get("answer_text") or "")
            old_keys.append((oseg, oq, oa))
        # queue of old fully-empty segments for positional matching (a fully
        # empty segment has nothing to content-match on, but it existed as an
        # empty card in the old JSON and should be preserved in order).
        old_empties = [oseg for oseg in old_segs
                       if not (oseg.get("q_text") or "").strip()
                       and not (oseg.get("answer_text") or "").strip()]

        new_segs = []
        for nseg in ns["segments"]:
            nq = norm_key(nseg.get("q_text") or "")
            na = norm_key(nseg.get("answer_text") or "")

            # 0) fully-empty segment: pop the next old empty segment positionally
            match = None
            how = ""
            if not nq and not na:
                if old_empties:
                    match = old_empties.pop(0)
                    how = "empty-pos"

            # 1) exact q_text match (unique win)
            if match is None and nq:
                cands = [(sid2, seg) for sid2, seg in qidx.get(nq, []) if sid2 == sid]
                if len(cands) == 1:
                    match = cands[0][1]
                    how = "exact"
                elif len(cands) > 1:
                    # disambiguate by answer overlap
                    best = None
                    bs = 0.0
                    for _s2, seg in cands:
                        r = difflib.SequenceMatcher(None, na, norm_key(seg.get("answer_text") or "")).ratio()
                        if r > bs:
                            bs, best = r, seg
                    match = best
                    how = "exact+ans"

            # 2) containment: nq appears inside an old segment's answer_text
            if match is None and nq:
                for oseg, oq, oa in old_keys:
                    if oa and (nq in oa or (len(nq) >= 20 and nq[:20] in oa)):
                        match = oseg
                        how = "containment"
                        break

            # 3) fuzzy q_text within session
            if match is None and nq:
                scored = []
                for oseg, oq, oa in old_keys:
                    if not oq:
                        continue
                    r = difflib.SequenceMatcher(None, nq, oq).ratio()
                    if r >= 0.85:
                        scored.append((r, oseg))
                if scored:
                    scored.sort(key=lambda x: -x[0])
                    match = scored[0][1]
                    how = "fuzzy"

            # 4) empty-q "answer continuation" segment: match an old EMPTY-q
            #    segment by answer_text (both carry only the answer; the question
            #    text is absent from the Word source).  Without this, such
            #    segments would be falsely flagged as newly-split orphans.
            if match is None and not nq and na:
                best = None
                bs = 0.0
                for oseg, oq, oa in old_keys:
                    if oq:
                        continue
                    r = difflib.SequenceMatcher(None, na, oa).ratio()
                    if r > bs:
                        bs, best = r, oseg
                if best is not None and bs >= 0.8:
                    match = best
                    how = "emptyq"

            outseg = dict(nseg)  # questioner, question_time, q_text, answer_text
            if match is not None:
                base = how.split("+")[0]
                stats[base if base in stats else "exact"] += 1
                # copy curated fields
                for k in ("start", "end", "start_label", "end_label",
                          "confidence", "status", "notes", "srt_preview",
                          "chapter_question_ids", "chapter_indexes", "meta"):
                    if k in match:
                        outseg[k] = match[k]
            else:
                stats["orphan"] += 1
                # newly split-away sub-question with no old counterpart.
                # Chapter links are deferred to link_chapters.py (content match);
                # time is inherited from the preceding sibling's range (they were
                # one spoken unit) and flagged so a reviewer can fine-tune.
                outseg["status"] = "manual"
                outseg["confidence"] = 1.0
                outseg["notes"] = RNOTES
                if new_segs:
                    prev = new_segs[-1]
                    for k in ("start", "end", "start_label", "end_label"):
                        if k in prev:
                            outseg[k] = prev[k]

            new_segs.append(outseg)

        # renumber + regenerate derived fields
        for i, seg in enumerate(new_segs, start=1):
            seg["index"] = i
            seg["question_id"] = question_id(sid, i, seg.get("q_text") or "")
            seg["stable_key"] = f"{sid}#{i}"
            qp = seg.get("q_text") or ""
            ap = seg.get("answer_text") or ""
            seg["q_preview"] = qp[:100] + ("…" if len(qp) > 100 else "")
            seg["answer_preview"] = ap[:160] + ("…" if len(ap) > 160 else "")
            # fix labels for segments whose start/end we copied (ensure consistency)
            if seg.get("start") is not None and seg.get("end") is not None:
                # keep original labels if they exist, else regenerate
                if "start_label" not in seg:
                    seg["start_label"] = fmt_label(seg["start"])
                if "end_label" not in seg:
                    seg["end_label"] = fmt_label(seg["end"])
            seg.pop("locked", None)

        # rebuild the session dict (preserve session-level fields from old if present)
        out_sessions[sid] = {
            "segments": new_segs,
            "_old": old,  # keep for writing step to merge session-level fields
        }
    return out_sessions, stats, skipped_structural


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-split audio_map2 without losing curation")
    ap.add_argument("--apply", action="store_true", help="write back changed JSONs")
    ap.add_argument("--month", action="append", help="restrict to YYYY-MM (repeatable)")
    args = ap.parse_args()

    print("parsing docx with corrected splitter...")
    new_sessions = build_new_sessions()
    old_sessions = load_old()
    qidx = build_old_index(old_sessions)

    out_sessions, stats, skipped_structural = carry_over(new_sessions, old_sessions, qidx)

    print(f"\nmatch stats: {stats}")
    if skipped_structural:
        print(f"\n⚠ skipped ({len(skipped_structural)} structurally-divergent sessions, no baseline):")
        for sid in skipped_structural:
            print(f"   {sid}")

    # per-month report: old segments vs new segments
    from collections import Counter
    old_by_month = Counter()
    new_by_month = Counter()
    for sid, sess in old_sessions.items():
        old_by_month[sid[:7]] += len(sess.get("segments") or [])
    for sid, ns in new_sessions.items():
        new_by_month[sid[:7]] += len(ns["segments"])

    print("\nmonth       old   new   diff")
    for m in sorted(set(old_by_month) | set(new_by_month)):
        flag = " <-- CHANGED" if old_by_month[m] != new_by_month[m] else ""
        print(f"{m}   {old_by_month[m]:5d} {new_by_month[m]:5d}  {new_by_month[m]-old_by_month[m]:+d}{flag}")

    if args.apply:
        changed = 0
        # group output by month, rebuild full month doc reusing old month-level fields
        months = sorted(set(sid[:7] for sid in out_sessions))
        for m in months:
            if args.month and m not in args.month:
                continue
            path = AUDIO_MAP2_DIR / f"{m}.json"
            if not path.exists():
                print(f"⚠ skip {m}: no existing JSON")
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            # map session_id -> old session (to preserve session-level fields)
            oldmap = {s["session_id"]: s for s in data["sessions"]}
            new_month_segs_changed = False
            for sid in sorted(out_sessions):
                if sid[:7] != m:
                    continue
                if sid not in oldmap:
                    continue
                ns = out_sessions[sid]
                old = oldmap[sid]
                old_segments = old.get("segments") or []
                new_segments = ns["segments"]
                # compare segment count/text to decide if changed
                if len(old_segments) != len(new_segments):
                    new_month_segs_changed = True
                    break
                # also compare q_text seq
                for a, b in zip(old_segments, new_segments):
                    if (a.get("q_text") or "") != (b.get("q_text") or ""):
                        new_month_segs_changed = True
                        break
                if new_month_segs_changed:
                    break
            if not new_month_segs_changed:
                print(f"  {m}: unchanged, skip")
                continue
            # apply
            for s in data["sessions"]:
                sid = s["session_id"]
                if sid in out_sessions and sid[:7] == m:
                    s["segments"] = out_sessions[sid]["segments"]
            data.pop("version_marker", None)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
            print(f"  {m}: written ({new_by_month[m]} segments)")
        print(f"\nchanged months: {changed}")
    else:
        print("\n(dry-run; pass --apply to write)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())