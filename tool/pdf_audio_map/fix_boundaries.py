#!/usr/bin/env python3
"""Re-boundary audio_map segments using SRT「下一个问题」anchors + content match.

For each session, find transition cues and score every (segment, candidate)
pair by answer/questioner overlap with the following SRT window, then pick a
strictly ordered assignment (DP). Writes start/end + labels; marks status
``manual`` when a segment was previously bad or newly changed a lot.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from common import (
    DEFAULT_SRT_ROOT,
    MAP_DIR,
    get_converter,
    normalize,
    parse_srt,
    parse_srt_raw,
    range_fields,
    spoken_name_variants,
    srt_preview,
)
TRANS_RE = re.compile(
    r"下[一1]个问题|下一個問題|下一个問題|下[一1]個問題|"
    r"我下[一1]个问题|那下[一1]个问题"
)

# Target speaking rate for Chinese Q&A answers (chars / second)
TARGET_CPS = 3.7


def fmt_tc(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    whole = int(s)
    ms = int(round((s - whole) * 1000))
    if ms == 1000:
        whole += 1
        ms = 0
        if whole == 60:
            whole = 0
            m += 1
            if m == 60:
                m = 0
                h += 1
    return f"{h:02d}:{m:02d}:{whole:02d}.{ms:03d}"


def answer_chars(seg: dict) -> int:
    text = seg.get("answer_text") or seg.get("answer_preview") or ""
    return len(re.sub(r"\s+", "", text))


def is_bad_segment(seg: dict) -> bool:
    """True collapse / absurd rate — not merely faster-than-ideal speech."""
    start, end = seg.get("start"), seg.get("end")
    if start is None or end is None or seg.get("status") == "missing":
        return True
    dur = end - start
    chars = answer_chars(seg)
    if dur <= 0.15 and chars > 10:
        return True
    if dur < 3.0 and chars > 100:
        return True
    if dur < 8.0 and chars > 400:
        return True
    cps = chars / dur if dur > 0 else 999
    if cps > 25 and chars > 60:
        return True
    return False


def session_needs_fix(session: dict) -> bool:
    segs = session.get("segments") or []
    if not segs:
        return False
    bad = sum(1 for s in segs if is_bad_segment(s))
    if bad >= 1:
        return True
    # Also fix if many very uneven neighbors (optional)
    return False


def find_transitions(cues_norm: List[Tuple[float, float, str]]) -> List[int]:
    idxs = []
    for i, (_, _, t) in enumerate(cues_norm):
        blob = t
        if i + 1 < len(cues_norm):
            blob += cues_norm[i + 1][2]
        if TRANS_RE.search(blob):
            idxs.append(i)
    return idxs


def window_text(cues_norm, start_idx: int, max_chars: int = 140) -> str:
    parts = []
    n = 0
    for j in range(start_idx, min(len(cues_norm), start_idx + 40)):
        parts.append(cues_norm[j][2])
        n += len(cues_norm[j][2])
        if n >= max_chars:
            break
    return "".join(parts)


def overlap_score(a: str, b: str) -> float:
    """Cheap char-overlap score (0–100-ish)."""
    if not a or not b:
        return 0.0
    # Use longest common substring length via set of trigrams
    if len(a) < 3 or len(b) < 3:
        return 10.0 if a[:2] in b else 0.0
    ta = {a[i : i + 3] for i in range(len(a) - 2)}
    tb = {b[i : i + 3] for i in range(len(b) - 2)}
    if not ta:
        return 0.0
    inter = len(ta & tb)
    return 100.0 * inter / max(len(ta), 1)


def score_at(
    seg: dict,
    cues_norm,
    cue_idx: int,
    converter,
    is_transition: bool,
) -> float:
    win = window_text(cues_norm, cue_idx, 160)
    answer = normalize(seg.get("answer_text") or seg.get("answer_preview") or "", converter)
    q = normalize(seg.get("q_text") or seg.get("q_preview") or "", converter)
    score = 0.0
    if answer:
        score += overlap_score(answer[:120], win)
        # prefix boost
        pref = answer[:12]
        if len(pref) >= 4 and pref[:4] in win:
            score += 25
        elif len(pref) >= 6 and pref[:6] in win:
            score += 35
    if q:
        # question body sometimes spoken before answer
        score += 0.35 * overlap_score(q[:80], win)
    for name in spoken_name_variants(seg.get("questioner") or "", converter):
        if len(name) >= 2 and name in win:
            score += 40
            break
    if is_transition:
        score += 12
    return score


def nearest_cue(cues_norm, t: float) -> int:
    best_i = 0
    best_d = 1e18
    for i, (st, _, _) in enumerate(cues_norm):
        d = abs(st - t)
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def candidate_indices(
    cues_norm,
    transitions: List[int],
    n_segs: int,
    audio_end: float,
) -> List[int]:
    """Transitions + proportional grid + early cues for Q1."""
    cand = set(transitions)
    grid_n = max(n_segs * 2, 16)
    for k in range(grid_n):
        t = audio_end * k / grid_n
        cand.add(nearest_cue(cues_norm, t))
    for i in range(min(20, len(cues_norm))):
        cand.add(i)
    return sorted(cand)


def dp_assign(
    scores: List[List[float]],
    cand_times: List[float],
) -> List[Optional[int]]:
    """scores[seg][cand] → pick increasing cand indices maximizing sum."""
    n = len(scores)
    m = len(scores[0]) if n else 0
    if n == 0 or m == 0:
        return []
    NEG = -1e18
    # dp[i][j] = best score using first i segments, last cand = j
    dp = [[NEG] * m for _ in range(n)]
    prev = [[-1] * m for _ in range(n)]
    for j in range(m):
        dp[0][j] = scores[0][j]
    for i in range(1, n):
        best_before = NEG
        best_j = -1
        # rolling max of dp[i-1][0..j-1]
        roll_val = NEG
        roll_idx = -1
        for j in range(m):
            if j > 0 and dp[i - 1][j - 1] > roll_val:
                roll_val = dp[i - 1][j - 1]
                roll_idx = j - 1
            if roll_val <= NEG / 2:
                continue
            val = roll_val + scores[i][j]
            # soft preference: later segment later in time (already enforced)
            # penalize tiny gaps when answer is long
            dp[i][j] = val
            prev[i][j] = roll_idx
    # pick best end
    end_j = max(range(m), key=lambda j: dp[n - 1][j])
    if dp[n - 1][end_j] <= NEG / 2:
        return [None] * n
    path = [None] * n
    j = end_j
    for i in range(n - 1, -1, -1):
        path[i] = j
        j = prev[i][j]
    return path  # type: ignore[return-value]


def realign_session(session: dict, converter, srt_root: Path) -> Tuple[dict, dict]:
    """Return (new_session, stats)."""
    srt = Path(session.get("srt_file") or "")
    if not srt.exists():
        stem = (session.get("audio_file") or "").replace(".opus", "")
        srt = srt_root / f"{stem[:4]}答疑音頻" / f"{stem}.srt"
    if not srt.exists():
        return session, {"skipped": "no_srt"}

    cues_norm = parse_srt(srt, converter)
    cues_raw = parse_srt_raw(srt)
    if not cues_norm:
        return session, {"skipped": "empty_srt"}

    segs = session.get("segments") or []
    if not segs:
        return session, {"skipped": "no_segs"}

    audio_end = cues_norm[-1][1]
    transitions = find_transitions(cues_norm)
    cands = candidate_indices(cues_norm, transitions, len(segs), audio_end)
    trans_set = set(transitions)

    scores = []
    for seg in segs:
        row = []
        for ci in cands:
            row.append(
                score_at(seg, cues_norm, ci, converter, ci in trans_set)
            )
        scores.append(row)

    # Expected duration penalty: prefer spacing proportional to answer length
    chars = [max(20, answer_chars(s)) for s in segs]
    total_c = sum(chars) or 1
    # After DP path chosen we refine; first get path
    path = dp_assign(scores, [cues_norm[c][0] for c in cands])
    if not path or any(p is None for p in path):
        return session, {"skipped": "dp_failed"}

    starts = [cues_norm[cands[p]][0] for p in path]  # type: ignore[index]

    # Enforce expected minimum gaps using char weights (don't shrink known good gaps much)
    # Redistribute if gap too small for content
    for i in range(len(starts) - 1):
        need = chars[i] / TARGET_CPS
        gap = starts[i + 1] - starts[i]
        if gap < need * 0.35 and need > 20:
            # push following starts forward if room
            deficit = need * 0.5 - gap
            for j in range(i + 1, len(starts)):
                room = (starts[j + 1] - starts[j]) if j + 1 < len(starts) else (audio_end - starts[j])
                shift = min(deficit, max(0, room - 5))
                if shift > 0.05:
                    starts[j] += shift
                    deficit -= shift
                if deficit <= 0.05:
                    break

    # Monotonic
    for i in range(1, len(starts)):
        if starts[i] <= starts[i - 1]:
            starts[i] = starts[i - 1] + 0.2

    new_segs = []
    fixed = 0
    kept_locked = 0
    for i, seg in enumerate(segs):
        if seg.get("locked") and seg.get("start") is not None and not is_bad_segment(seg):
            # keep locked good segments; still may need end snap later
            new_segs.append(dict(seg))
            kept_locked += 1
            continue
        start = round(starts[i], 3)
        end = round(starts[i + 1], 3) if i + 1 < len(starts) else round(audio_end, 3)
        if end <= start:
            end = round(start + 0.5, 3)
        preview = srt_preview(cues_raw, start, end)
        was_bad = is_bad_segment(seg)
        old_start = seg.get("start")
        changed = old_start is None or abs(old_start - start) > 0.35 or was_bad
        fields = range_fields(start, end, 0.9 if changed else (seg.get("confidence") or 0.7), "manual" if changed or was_bad else (seg.get("status") or "auto"), preview)
        if changed or was_bad:
            fields["status"] = "manual"
            fields["notes"] = "boundary-fix-20260731"
            fixed += 1
        else:
            fields["notes"] = seg.get("notes") or ""
            fields["status"] = seg.get("status") or "auto"
            fields["locked"] = seg.get("locked", False)
        merged = {**seg, **fields}
        # preserve lock flag
        if seg.get("locked"):
            merged["locked"] = True
        new_segs.append(merged)

    # Re-snap ends to next starts for continuity (including locked kept)
    for i in range(len(new_segs) - 1):
        nxt = new_segs[i + 1]["start"]
        if nxt is not None and new_segs[i].get("end") != nxt:
            # don't break locked unless bad
            if new_segs[i].get("locked") and not is_bad_segment(new_segs[i]):
                pass
            new_segs[i]["end"] = round(float(nxt), 3)
            new_segs[i]["end_label"] = fmt_tc(float(nxt))
    if new_segs:
        closing = session.get("closing")
        if (
            closing
            and closing.get("start") is not None
            and closing.get("status") != "missing"
        ):
            cl_start = float(closing["start"])
            new_segs[-1]["end"] = round(cl_start, 3)
            new_segs[-1]["end_label"] = fmt_tc(cl_start)
            closing = dict(closing)
            closing["end"] = round(audio_end, 3)
            closing["end_label"] = fmt_tc(audio_end)
            if closing.get("status") == "missing":
                closing["status"] = "manual"
        else:
            new_segs[-1]["end"] = round(audio_end, 3)
            new_segs[-1]["end_label"] = fmt_tc(audio_end)
            closing = session.get("closing")
    else:
        closing = session.get("closing")

    # Opening end → first segment start
    opening = session.get("opening")
    if opening and new_segs:
        op = dict(opening)
        first = new_segs[0]["start"]
        if op.get("start") is None:
            op_start = 0.0
            intro = normalize("今天是", converter)
            # light search in first 40 cues
            for st, _, t in cues_norm[:40]:
                if intro[:3] in t or "今天是" in t:
                    op_start = st
                    break
            op["start"] = round(op_start, 3)
            op["start_label"] = fmt_tc(op_start)
        op["end"] = round(float(first), 3)
        op["end_label"] = fmt_tc(float(first))
        if op.get("status") == "missing" or op.get("end") is None:
            op["status"] = "manual"
        opening = op

    out = {
        **session,
        "segments": new_segs,
        "opening": opening,
        "closing": closing,
        "srt_file": str(srt),
    }
    return out, {
        "fixed": fixed,
        "kept_locked": kept_locked,
        "transitions": len(transitions),
        "segs": len(segs),
    }


def count_bad(payload: dict) -> int:
    n = 0
    for s in payload.get("sessions") or []:
        for seg in s.get("segments") or []:
            if is_bad_segment(seg):
                n += 1
        op = s.get("opening")
        if op and (op.get("start") is None or op.get("end") is None):
            n += 1
    return n


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Fix audio_map boundaries via SRT anchors")
    parser.add_argument("--month", action="append", help="YYYY-MM (repeatable)")
    parser.add_argument("--session", action="append", help="session_id filter (repeatable)")
    parser.add_argument("--srt-root", type=Path, default=DEFAULT_SRT_ROOT)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force-all", action="store_true", help="Realign every session, not only bad ones")
    args = parser.parse_args(argv)

    converter = get_converter()
    months = args.month or [
        "2025-06", "2025-07", "2025-08", "2025-09",
        "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
    ]

    total_fixed = 0
    total_bad_before = 0
    total_bad_after = 0

    for month in months:
        path = MAP_DIR / f"{month}.json"
        if not path.exists():
            print(f"[{month}] missing {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        bad_before = count_bad(data)
        total_bad_before += bad_before
        new_sessions = []
        month_fixed = 0
        for session in data.get("sessions") or []:
            sid = session["session_id"]
            if args.session and sid not in args.session:
                new_sessions.append(session)
                continue
            if not args.force_all and not session_needs_fix(session):
                new_sessions.append(session)
                continue
            aligned, stats = realign_session(session, converter, args.srt_root)
            if "skipped" in stats:
                print(f"  {sid}: skip ({stats['skipped']})")
                new_sessions.append(session)
                continue
            month_fixed += stats.get("fixed", 0)
            print(
                f"  {sid}: fixed={stats.get('fixed')} segs={stats.get('segs')} "
                f"transitions={stats.get('transitions')} locked_kept={stats.get('kept_locked')}"
            )
            new_sessions.append(aligned)
        data["sessions"] = new_sessions
        bad_after = count_bad(data)
        total_bad_after += bad_after
        total_fixed += month_fixed
        print(f"[{month}] bad {bad_before} → {bad_after} (touched segs≈{month_fixed})")
        if args.apply:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"  wrote {path}")

    print(f"TOTAL fixed≈{total_fixed} bad {total_bad_before} → {total_bad_after}")
    if not args.apply:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
