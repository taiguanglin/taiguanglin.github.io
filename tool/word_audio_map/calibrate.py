#!/usr/bin/env python3
"""Fine-grained boundary calibration for Word-chapter audio maps (v2).

Every onset is sub-cue fractional:
- 「下一個問題」marker: char-interpolated inside its raw cue;
- name anchor: **pinyin** occurrence per cue (homophone names anchor too);
- answer/question anchor: LCB-block start on the session pinyin stream;
- adaptive lead-in from the pause before onset (0.5s…0.1s, never cutting
  previous speech); end_i = start_{i+1}; locked/manual untouched;
  per-segment correction clamped to ±CAL_LIMIT seconds around the current
  boundary (this is *calibration*, not re-matching), so repeated runs
  converge.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TOOL_DIR = Path(__file__).resolve().parent
PDF_TOOL_DIR = TOOL_DIR.parent / "pdf_audio_map"
for p in (str(TOOL_DIR), str(PDF_TOOL_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from realign_half_second import (  # noqa: E402
    adaptive_lead,
    find_xia_time_in_cue,
    prev_cue_end_before,
)
from wcommon import (  # noqa: E402
    WORD_MAP_DIR,
    SessionStream,
    get_converter,
    inventory_sessions,
    load_questions,
    parse_srt,
    parse_srt_raw,
    py_norm,
    spoken_name_variants,
)

CAL_LIMIT = 30.0          # max correction around the existing boundary
MIN_SHIFT = 0.05          # idempotence guard
SEARCH_BACK = 45.0        # search span before the current boundary
SEARCH_FWD = 45.0         # …and after it (never past next boundary)


def _label(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _strip_old_cal(notes: str) -> str:
    return (notes or "").split(";cal")[0].split(";cal2")[0]


def usable_name_local(raw: str) -> str:
    name = re.sub(r"\s*\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\s*", " ", raw or "")
    name = re.sub(r"\s*\d{1,2}:\d{2}(?::\d{2})?\s*", " ", name)
    return name.strip()


class SessionCtx:
    def __init__(self, session: dict, converter):
        self.session = session
        path = Path(session["srt_file"])
        self.cues_raw = parse_srt_raw(path) if path.exists() else []
        cues = parse_srt(path, converter) if path.exists() else []
        self.ss = SessionStream(session, cues, converter, self.cues_raw)
        self.dur = max(self.audio_end, 1e-6)
        self.stream_len = len(self.ss.py)

    @property
    def ok(self):
        return bool(self.ss.cues)

    @property
    def audio_end(self):
        return self.ss.audio_end

    def char_at_time(self, t: float) -> int:
        """Char position for time t via its containing cue (exact)."""
        spans = self.ss.cue_spans
        best = None
        for ci, (st_cue, en_cue, _b) in enumerate(self.ss.cues):
            if st_cue <= t < en_cue:
                sc, ln = spans[ci]
                frac = (t - st_cue) / max(en_cue - st_cue, 1e-6)
                return max(0, min(int(sc + ln * frac), self.stream_len - 1))
            if st_cue <= t:
                best = ci
        if best is not None:
            sc, ln = spans[best]
            return max(0, min(sc + max(ln - 1, 0), self.stream_len - 1))
        return 0

    def markers_in(self, lo: int, hi: int) -> List[float]:
        """All「下一個問題」onset times with their「下」inside [lo,hi)."""
        out = []
        for ci, (st_ch, ln_ch) in enumerate(self.ss.cue_spans):
            if st_ch + ln_ch <= lo or st_ch >= hi:
                continue
            if ci >= len(self.cues_raw):
                continue
            rst, ren, rbody = self.cues_raw[ci]
            t = find_xia_time_in_cue(rst, ren, rbody)
            if t is not None:
                out.append(t)
        return out

    def name_positions(self, lo: int, hi: int, variants: List[str]) -> List[int]:
        win = self.ss.py[lo:hi]
        pos = []
        for v in variants:
            if len(v) < 2:
                continue
            start = 0
            while True:
                i = win.find(v, start)
                if i < 0:
                    break
                pos.append(lo + i)
                start = i + 1
        return sorted(pos)

    def block_position(self, probe: str, lo: int, hi: int,
                       min_size: int) -> Optional[int]:
        if len(probe) < min_size or hi <= lo:
            return None
        win = self.ss.py[lo:hi]
        m = SequenceMatcher(None, win, probe, autojunk=False).find_longest_match(
            0, len(win), 0, len(probe)
        )
        if m.size < min_size:
            return None
        return lo + m.a


ANSWER_SKIP = 16


def refine_session(session: dict, segs: List[dict], qlist_by_key: Dict[str, dict],
                   converter) -> Tuple[int, float, int]:
    ctx = SessionCtx(session, converter)
    if not ctx.ok:
        return 0, 0.0, 0
    ss = ctx.ss

    segs_sorted = sorted(
        [s for s in segs if s.get("start") is not None], key=lambda s: s["start"]
    )
    calibrated = total_shift = big = 0
    prev_start = 0.0

    for i, seg in enumerate(segs_sorted):
        if seg.get("locked") or seg.get("status") == "manual":
            prev_start = float(seg["start"])
            continue
        cur = float(seg["start"])
        next_start = (
            float(segs_sorted[i + 1]["start"]) if i + 1 < len(segs_sorted)
            else ctx.audio_end
        )

        lo_t = max(prev_start + 0.02, cur - SEARCH_BACK)
        hi_t = min(next_start - 0.05, cur + SEARCH_FWD)
        if hi_t <= lo_t:
            prev_start = cur
            continue
        lo = ctx.char_at_time(lo_t)
        hi = max(ctx.char_at_time(hi_t), lo + 1)

        q = qlist_by_key.get(seg.get("stable_key") or "") or {}
        variants = spoken_name_variants(
            usable_name_local(seg.get("questioner") or ""), converter
        )
        ap_full = py_norm(q.get("a_text") or "", converter)
        qp_full = py_norm(q.get("q_text") or "", converter)

        target = ctx.char_at_time(cur)

        # ---- collect candidates: (priority, dist_to_target, time, method)
        cand: List[Tuple[int, float, float, str]] = []

        for t in ctx.markers_in(lo, hi):
            cand.append((0, abs(t - cur), t, "marker"))

        if any(len(v) >= 2 for v in variants):
            for pos in ctx.name_positions(lo, hi, variants):
                t = ss.frac_time(pos)
                cand.append((1, abs(pos - target), t, "name"))

        probe = (
            ap_full[ANSWER_SKIP] if len(ap_full) > ANSWER_SKIP + 24
            else (ap_full if len(ap_full) >= 20 else "")
        )
        if len(probe) >= 20:
            bp = ctx.block_position(probe, lo, hi, min_size=9)
            if bp is not None:
                cand.append((2, abs(bp - target), ss.frac_time(bp), f"ans"))
        if len(qp_full) >= 20:
            qp_pos = ctx.block_position(qp_full[:100], lo, hi, min_size=10)
            if qp_pos is not None:
                cand.append((2, abs(qp_pos - target), ss.frac_time(qp_pos), "q"))

        if not cand:
            prev_start = cur
            continue

        cand.sort(key=lambda c: (c[0], c[1]))
        _prio, _dist, onset, method = cand[0]

        new_start, lead_used, gap = _apply_onset(onset, ctx.cues_raw,
                                                 prev_start + 0.02)
        if abs(new_start - cur) > CAL_LIMIT:
            prev_start = cur
            continue
        if new_start >= next_start - 0.3:
            new_start = max(prev_start + 0.02, min(new_start, next_start - 0.3))
        if new_start <= prev_start:
            prev_start = cur
            continue

        shift = abs(new_start - cur)
        if shift >= MIN_SHIFT:
            seg["start"] = round(new_start, 3)
            seg["start_label"] = _label(new_start)
            base = _strip_old_cal(seg.get("notes"))
            seg["notes"] = f"{base};cal2({method},lead={lead_used})"
            calibrated += 1
            total_shift += shift
            if shift > 1.5:
                big += 1
        prev_start = float(seg["start"])

    # chain ends
    for i, seg in enumerate(segs_sorted):
        if seg.get("locked") or seg.get("status") == "manual":
            continue
        nxt = (
            float(segs_sorted[i + 1]["start"]) if i + 1 < len(segs_sorted)
            else round(ctx.audio_end, 3)
        )
        if seg.get("end") != round(nxt, 3):
            seg["end"] = round(float(nxt), 3)
            seg["end_label"] = _label(float(nxt))

    return calibrated, total_shift, big


def _apply_onset(onset: float, cues_raw, floor: float):
    prev_end = prev_cue_end_before(cues_raw, onset)
    gap = max(0.0, float(onset) - prev_end)
    lead = adaptive_lead(gap)
    start = max(float(onset) - lead, prev_end, floor, 0.0)
    return round(start, 3), round(max(0.0, float(onset) - start), 3), round(gap, 3)


def main(argv=None) -> int:
    global CAL_LIMIT
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map-dir", type=Path, default=WORD_MAP_DIR)
    ap.add_argument("--questions", type=Path,
                    default=TOOL_DIR / "build" / "questions.json")
    ap.add_argument("--limit", type=int, default=CAL_LIMIT,
                    help="max correction per segment (seconds)")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    CAL_LIMIT = float(args.limit)

    converter = get_converter()
    maps: Dict[str, dict] = {}
    for path in sorted(args.map_dir.glob("word-*.json")):
        maps[path.name] = json.loads(path.read_text(encoding="utf-8"))
    qlist = load_questions(args.questions)
    qlist_by_key = {f"{q['chapter_index']:02d}#q{q['number']}": q for q in qlist}
    sessions = inventory_sessions()
    by_sid: Dict[str, dict] = {}
    for s in sessions:
        by_sid.setdefault(s["session_id"], s)

    grouped: Dict[str, List[Tuple[str, dict]]] = {}
    for fname, data in maps.items():
        for seg in data.get("segments") or []:
            sid = seg.get("session_id")
            if sid and seg.get("start") is not None:
                grouped.setdefault(sid, []).append((fname, seg))

    tot_cal = tot_shift = tot_big = 0
    dirty = set()
    for sid, pairs in sorted(grouped.items()):
        session = by_sid.get(sid)
        if not session:
            continue
        segs = [seg for _, seg in pairs]
        fnames = {fn for fn, _ in pairs}
        c, shift, big = refine_session(session, segs, qlist_by_key, converter)
        if c:
            tot_cal += c
            tot_shift += shift
            tot_big += big
            dirty |= fnames
            print(f"  {sid}: calibrated={c} big={big}", flush=True)

    mean = tot_shift / tot_cal if tot_cal else 0.0
    print(f"TOTAL calibrated={tot_cal}  mean|shift|={mean:.2f}s  "
          f">1.5s={tot_big}  files={len(dirty)}")

    if args.apply and dirty:
        for n in dirty:
            (args.map_dir / n).write_text(
                json.dumps(maps[n], ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
            )
        print(f"written {len(dirty)} files → {args.map_dir}")
    elif not args.apply:
        print("(dry-run; pass --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
