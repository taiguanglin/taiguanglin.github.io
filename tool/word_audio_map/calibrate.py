#!/usr/bin/env python3
"""Fine-grained boundary calibration for Word-chapter audio maps.

For every mapped segment (auto + review, skipping locked/manual) re-derive the
precise spoken onset from the session SRT and apply the pdf_audio_map
alignment principles (audio_map/AGENTS.md):

1. prefer the spoken 「下一个问题」 transition — start just before「下」;
2. otherwise align to the spoken onset of name / answer / question text;
3. adaptive lead-in chosen from the pause before the onset (0.5s … 0.1s),
   never cutting into previous speech;
4. end_i = start_{i+1}; last end stays at audio end.

Onset times get intra-cue interpolation (fractional character position), which
is finer than the raw cue granularity the original alignment used.

Usage:
    python3 calibrate.py            # dry run, prints shift statistics
    python3 calibrate.py --apply    # write maps (locked/manual preserved)
"""

from __future__ import annotations

import argparse
import json
import sys
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
    match_text_onset,
    prev_cue_end_before,
)
from wcommon import (  # noqa: E402
    WORD_MAP_DIR,
    get_converter,
    inventory_sessions,
    load_questions,
    parse_srt,
    parse_srt_raw,
    spoken_name_variants,
)


def _load_all(map_dir: Path):
    out = {}
    for path in sorted(map_dir.glob("word-*.json")):
        out[path.name] = json.loads(path.read_text(encoding="utf-8"))
    return out


def _write_all(maps: Dict[str, dict], map_dir: Path) -> None:
    for name, data in maps.items():
        path = map_dir / name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")


def _norm_cue_texts(cues_raw):
    conv = get_converter()
    return [normalize_keep_len(st, en, body, conv) for st, en, body in cues_raw]


def normalize_keep_len(st, en, body, conv):
    """Normalize cue text while keeping a per-char time map back to raw."""
    from common import normalize as pdf_normalize

    n = pdf_normalize(body or "", conv)
    if not n:
        n = " "
    # proportional mapping norm index -> raw fraction
    return (st, en, n, len(body or ""))


def _name_time_in_cue(entry, name_variants):
    """Fractional-interpolated time when a name variant appears in this cue."""
    st, en, ntext, raw_len = entry
    for v in name_variants:
        if len(v) < 2:
            continue
        i = ntext.find(v)
        if i >= 0:
            frac = i / max(len(ntext), 1)
            return st + (en - st) * frac
    return None


def _xia_time_near(cues_raw, idx: int, radius: int = 1) -> Optional[float]:
    """Latest「下一个问题」onset among cues idx-radius…idx+radius."""
    best = None
    for j in range(max(0, idx - radius), min(len(cues_raw), idx + radius + 1)):
        st, en, body = cues_raw[j]
        t = find_xia_time_in_cue(st, en, body)
        if t is not None and (best is None or t > best):
            best = t
    return best


def calibrate_session(session: dict, segs: List[dict], qlist_by_key: Dict[str, dict],
                      converter) -> Tuple[int, float, int]:
    """Refine starts in-place. Returns (#calibrated, total_abs_shift, #big_shifts)."""
    srt_file = None
    for s in segs:
        if s.get("srt_file"):
            srt_file = s["srt_file"]
            break
    if not srt_file:
        return 0, 0.0, 0
    path = Path(srt_file)
    if not path.exists():
        return 0, 0.0, 0
    cues_raw = parse_srt_raw(path)
    cues_norm = parse_srt(path, converter)
    if not cues_raw:
        return 0, 0.0, 0
    audio_end = cues_raw[-1][1]

    segs_sorted = sorted(
        [s for s in segs if s.get("start") is not None], key=lambda s: s["start"]
    )
    calibrated = 0
    total_shift = 0.0
    big = 0
    cursor_idx = 0
    prev_start = 0.0

    for i, seg in enumerate(segs_sorted):
        if seg.get("locked") or seg.get("status") == "manual":
            prev_start = float(seg["start"])
            continue
        next_start = (
            float(segs_sorted[i + 1]["start"])
            if i + 1 < len(segs_sorted) else audio_end
        )
        q = qlist_by_key.get(seg.get("stable_key") or "")
        fake = {
            "questioner": seg.get("questioner") or (q or {}).get("questioner", ""),
            "answer_text": (q or {}).get("a_text", ""),
            "answer_preview": (q or {}).get("a_text", "")[:200],
            "q_text": (q or {}).get("q_text", ""),
            "q_preview": (q or {}).get("q_text", "")[:120],
        }
        cur = float(seg["start"])

        res = match_text_onset(
            fake, cues_norm, cursor_idx, converter, min_onset=prev_start
        )
        onset = None
        if res is not None:
            t_cue, idx, method = res
            if idx < cursor_idx:
                idx = cursor_idx
            # 1) prefer「下一个问题」marker near the matched cue. Homophone
            #    names often break the name anchor and let the answer-text
            #    match land mid-answer — so answer/question hits get a wide
            #    look-back radius to still find their spoken transition.
            radius = 12 if method in ("answer", "question", "answer_global") else 1
            t_xia = _xia_time_near(cues_raw, idx, radius)
            if t_xia is not None and abs(t_xia - cur) <= 30.0 and t_xia <= next_start - 0.3:
                onset = t_xia
                method += "+marker"
            else:
                # 2) intra-cue interpolation for name matches
                if method == "name":
                    variants = spoken_name_variants(fake["questioner"], converter)
                    t_name = _name_time_in_cue(cues_norm_entry(cues_raw, cues_norm, idx),
                                               variants)
                    if t_name is not None:
                        onset = t_name
                        method += "+intra"
                if onset is None:
                    onset = t_cue
            cursor_idx = max(cursor_idx, idx)

        if onset is None:
            prev_start = cur
            continue

        new_start, lead_used, gap = _start_from_onset_floor(
            onset, cues_raw, floor=prev_start + 0.02
        )
        if abs(new_start - cur) > 90.0:
            # implausible jump (mis-anchor): keep original boundary
            prev_start = cur
            continue
        if new_start >= next_start - 0.3:
            new_start = max(prev_start + 0.02, min(new_start, next_start - 0.3))
        if new_start <= prev_start:
            prev_start = cur
            continue

        shift = abs(new_start - cur)
        if shift >= 0.05:
            old_end = seg.get("end")
            seg["start"] = round(new_start, 3)
            seg["start_label"] = _label(new_start)
            note = f";cal(lead={lead_used},gap={gap},{method})"
            base_notes = (seg.get("notes") or "").split(";cal")[0]
            seg["notes"] = base_notes + note
            calibrated += 1
            total_shift += shift
            if shift > 1.5:
                big += 1
        prev_start = float(seg["start"])

    # chain ends: end_i = start_{i+1}; last keeps audio end
    for i, seg in enumerate(segs_sorted):
        if seg.get("locked") or seg.get("status") == "manual":
            continue
        if i + 1 < len(segs_sorted):
            nxt = segs_sorted[i + 1]["start"]
            if seg.get("end") != nxt and nxt is not None:
                seg["end"] = round(float(nxt), 3)
                seg["end_label"] = _label(float(nxt))
        else:
            if seg.get("end") != audio_end:
                seg["end"] = round(float(audio_end), 3)
                seg["end_label"] = _label(float(audio_end))
    return calibrated, total_shift, big


def cues_norm_entry(cues_raw, cues_norm, idx):
    if idx < len(cues_norm):
        st, en, ntext = cues_norm[idx]
        raw_body = ""
        # find matching raw cue by identical start/end times
        for rst, ren, rbody in cues_raw:
            if abs(rst - st) < 0.001 and abs(ren - en) < 0.001:
                raw_body = rbody
                break
        return (st, en, ntext, len(raw_body))
    return None


def _start_from_onset_floor(onset, cues_raw, floor):
    prev_end = prev_cue_end_before(cues_raw, onset)
    gap = max(0.0, float(onset) - prev_end)
    lead = adaptive_lead(gap)
    start = float(onset) - lead
    start = max(start, prev_end, floor, 0.0)
    return round(start, 3), round(max(0.0, float(onset) - start), 3), round(gap, 3)


def _label(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map-dir", type=Path, default=WORD_MAP_DIR)
    ap.add_argument("--questions", type=Path, default=TOOL_DIR / "build" / "questions.json")
    ap.add_argument("--apply", action="store_true", help="write calibrated maps")
    args = ap.parse_args(argv)

    converter = get_converter()
    maps = _load_all(args.map_dir)
    qlist = load_questions(args.questions)
    qlist_by_key = {
        f"{q['chapter_index']:02d}#q{q['number']}": q for q in qlist
    }
    sessions = inventory_sessions()
    by_sid: Dict[str, dict] = {}
    for s in sessions:
        by_sid.setdefault(s["session_id"], s)

    # group segments per session across all chapter files
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
        c, shift, big = calibrate_session(session, segs, qlist_by_key, converter)
        if c:
            tot_cal += c
            tot_shift += shift
            tot_big += big
            dirty |= fnames
            print(f"  {sid}: calibrated={c} big_shifts={big}", flush=True)

    print(f"TOTAL calibrated={tot_cal}  mean|shift|="
          f"{(tot_shift / tot_cal if tot_cal else 0):.2f}s  >1.5s shifts={tot_big}")
    print(f"files changed: {len(dirty)}")

    if args.apply:
        # refresh stats blocks untouched; just write back changed files
        _write_all({n: maps[n] for n in dirty}, args.map_dir)
        print(f"written {len(dirty)} files → {args.map_dir}")
    else:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
