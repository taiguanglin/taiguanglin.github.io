#!/usr/bin/env python3
"""Content-aware audio_map realign (下一个问题 + paragraph content check).

Prevents cascade drift: each primary segment must score well against the SRT
window after its chosen onset; weak next_q hits are skipped in favour of
content match. Adaptive lead-in per audio_map/AGENTS.md.

Default scope: 2025-07-07-tieba + all sessions with date >= 2025-07-08.
Skips earlier proofread sessions including 2025-07-07-wechat (use
--session + --keep-through for suffix repair).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

from common import (
    MAP_DIR,
    get_converter,
    normalize,
    parse_srt,
    parse_srt_raw,
    range_fields,
    spoken_name_variants,
    srt_preview,
)
from realign_half_second import (
    _is_followup_seg,
    answer_chars,
    collect_next_q_anchors,
    match_text_onset,
    score_seg_at_window,
    start_from_onset,
)

SKIP_SESSION_IDS = {
    "2025-06-12-wechat",
    "2025-06-12-tieba",
    "2025-06-13-wechat",
    # Suffix-proofread separately (keep user start through N)
    "2025-07-07-wechat",
}


def _cue_at(cues_norm, t: float) -> int:
    best_i, best_d = 0, 1e18
    for i, (st, _, _) in enumerate(cues_norm):
        d = abs(st - t)
        if d < best_d:
            best_d, best_i = d, i
    return best_i


def _content_score(seg, cues_norm, onset_t: float, converter) -> float:
    ci = _cue_at(cues_norm, onset_t)
    # Prefer window just after transition / at onset
    return max(
        score_seg_at_window(seg, cues_norm, ci, converter),
        score_seg_at_window(seg, cues_norm, min(ci + 1, len(cues_norm) - 1), converter),
    )


def assign_onsets(
    segs,
    cues_norm,
    cues_raw,
    converter,
    audio_end: float,
    fixed_starts: Optional[dict] = None,
):
    """fixed_starts: {segment_index: absolute_start_seconds} kept as-is (no lead redo)."""
    fixed_starts = {int(k): float(v) for k, v in (fixed_starts or {}).items()}
    n = len(segs)
    anchors = collect_next_q_anchors(cues_raw, cues_norm)
    followup = [
        _is_followup_seg(segs[i], segs[i - 1] if i else None) for i in range(n)
    ]
    onsets: List[Optional[float]] = [None] * n
    methods: List[str] = [""] * n
    scores_out: List[float] = [0.0] * n

    for i, seg in enumerate(segs):
        idx = int(seg.get("index") or i + 1)
        if idx in fixed_starts:
            onsets[i] = fixed_starts[idx]
            methods[i] = "keep-user-start"
            scores_out[i] = _content_score(seg, cues_norm, onsets[i], converter)

    a_ptr = 0
    prev_t = 0.0
    for o in onsets:
        if o is not None:
            prev_t = max(prev_t, float(o))
    while a_ptr < len(anchors) and anchors[a_ptr][0] < prev_t + 0.2:
        a_ptr += 1

    primary_idxs = [i for i in range(n) if not followup[i]]

    for pi, i in enumerate(primary_idxs):
        if methods[i] == "keep-user-start":
            prev_t = float(onsets[i])  # type: ignore
            while a_ptr < len(anchors) and anchors[a_ptr][0] < prev_t + 0.2:
                a_ptr += 1
            continue

        seg = segs[i]
        is_first = pi == 0 and all(
            methods[j] != "keep-user-start" for j in primary_idxs[: pi + 1]
        )

        if is_first:
            hit = match_text_onset(
                seg, cues_norm, 0, converter, prefer_answer=False, min_onset=0.0
            )
            if hit:
                onsets[i], methods[i] = hit[0], hit[2]
                scores_out[i] = _content_score(seg, cues_norm, hit[0], converter)
            else:
                onsets[i], methods[i] = 0.0, "start"
                scores_out[i] = 0.0
            prev_t = float(onsets[i])
            continue

        # Rank next_q anchors ahead of prev_t (lookahead + content score)
        cands = []
        for ai in range(a_ptr, len(anchors)):
            xia_t, cue_i, _k = anchors[ai]
            if xia_t < prev_t + 0.25:
                continue
            sc = score_seg_at_window(
                seg, cues_norm, min(cue_i + 1, len(cues_norm) - 1), converter
            )
            sc += 0.35 * score_seg_at_window(seg, cues_norm, cue_i, converter)
            cands.append((sc, xia_t, cue_i, ai))
            if len(cands) >= 8:
                break

        # Prefer later anchors when early next_q is a weak / off-topic hit
        # (SRT-only digressions not in PDF must be skipped to avoid cascade drift).
        best = None
        if cands:
            ranked = sorted(cands, key=lambda x: (-x[0], x[1]))
            best = ranked[0]
            if len(ranked) >= 2 and ranked[0][0] < 40:
                for alt in ranked[1:4]:
                    if alt[0] >= ranked[0][0] + 18 and alt[0] >= 36:
                        best = alt
                        break
                    if ranked[0][0] < 28 and alt[0] >= 45 and alt[1] - ranked[0][1] < 180:
                        best = alt
                        break
            # Prefer nearer next_q when a distant hit only wins on shared name tokens
            if best and prev_t > 0:
                near = [
                    c
                    for c in cands
                    if c[1] - prev_t <= 150 and c[0] >= 24
                ]
                if near:
                    near_best = max(near, key=lambda x: x[0])
                    if best[1] - prev_t > 150 and near_best[0] >= best[0] - 25:
                        best = near_best

        content = match_text_onset(
            seg,
            cues_norm,
            _cue_at(cues_norm, prev_t) + 1,
            converter,
            prefer_answer=False,
            min_onset=prev_t + 0.2,
        )
        content_sc = (
            _content_score(seg, cues_norm, content[0], converter) if content else -1.0
        )

        use_nq = best is not None and best[0] >= 26
        if use_nq and content and content_sc >= 40 and content[0] >= prev_t + 0.3:
            dist_nq = best[1] - prev_t
            dist_c = content[0] - prev_t
            # Nearby strong content beats a distant next_q (name collision later)
            if dist_c <= 120 and dist_nq > max(dist_c + 45, 90):
                use_nq = False
            elif content_sc >= best[0] + 12:
                use_nq = False
            elif content_sc >= best[0] + 8 and dist_c + 30 < dist_nq:
                use_nq = False
        if use_nq and best[0] < 22:
            use_nq = False
        if use_nq and content and best[0] < 30 and content_sc >= 45:
            use_nq = False
        # Reject next_q if content match is clearly better-aligned topic
        if use_nq and content and content_sc >= 50 and best[0] < 38:
            if abs(content[0] - best[1]) > 8:
                use_nq = False

        if use_nq:
            onsets[i] = best[1]
            methods[i] = "next_q"
            scores_out[i] = best[0]
            a_ptr = best[3] + 1
        elif content and content[0] >= prev_t + 0.15:
            onsets[i] = content[0]
            methods[i] = content[2]
            scores_out[i] = content_sc
            while a_ptr < len(anchors) and anchors[a_ptr][0] < onsets[i] - 0.4:
                a_ptr += 1
        else:
            onsets[i] = None
            methods[i] = "missing"
            scores_out[i] = 0.0

        if onsets[i] is not None:
            prev_t = float(onsets[i])

    # Follow-up runs: content refine inside [parent, next_primary)
    i = 0
    while i < n:
        if not followup[i] or onsets[i] is not None:
            i += 1
            continue
        j = i
        while j < n and followup[j] and onsets[j] is None:
            j += 1
        parent = i - 1
        while parent >= 0 and followup[parent]:
            parent -= 1
        t0 = float(onsets[parent]) if parent >= 0 and onsets[parent] is not None else 0.0
        nxt = j
        while nxt < n and onsets[nxt] is None:
            nxt += 1
        t1 = float(onsets[nxt]) if nxt < n and onsets[nxt] is not None else audio_end

        body = list(range(parent, j)) if parent >= 0 else list(range(i, j))
        if parent >= 0 and onsets[parent] is not None:
            weights = [max(answer_chars(segs[k]), 30) for k in body]
            total = sum(weights) or 1
            acc = weights[0]
            for k in range(i, j):
                onsets[k] = t0 + (t1 - t0) * acc / total
                methods[k] = "followup-split"
                scores_out[k] = 0.0
                acc += max(answer_chars(segs[k]), 30)
            for k in range(i, j):
                slot_lo = float(onsets[k])  # type: ignore
                slot_hi = float(onsets[k + 1]) if k + 1 < j else t1  # type: ignore
                ans = segs[k].get("answer_text") or ""
                # Prefer spoken 下一个问题 / 第N个问题 when PDF answer is introduced that way
                spoken_lead = None
                if "下一个问题" in ans[:12] or ans.startswith("下一个问题"):
                    spoken_lead = "下一个问题"
                else:
                    m = re.match(r"第[一二三四五六七八九十\d]+个问题", ans[:12])
                    if m:
                        spoken_lead = m.group(0)
                if spoken_lead:
                    best_a = None
                    for ci, (st, en, raw) in enumerate(cues_raw):
                        if st < t0 + 0.3 or st >= t1 - 0.5:
                            continue
                        if spoken_lead not in raw and normalize(spoken_lead, converter) not in normalize(
                            raw, converter
                        ):
                            # loose: 第二个问题 vs 第二问题
                            if spoken_lead[:2] == "第" and "问题" in raw and "第" in raw:
                                pass
                            else:
                                continue
                        sc = score_seg_at_window(
                            segs[k],
                            cues_norm,
                            min(ci + 1, len(cues_norm) - 1),
                            converter,
                        )
                        # Prefer earlier spoken lead in the parent window
                        score = sc + max(0, 40 - (st - t0) * 0.05)
                        if best_a is None or score > best_a[0]:
                            best_a = (score, st, sc)
                    if best_a and best_a[2] >= 18:
                        onsets[k] = best_a[1]
                        methods[k] = "followup-spoken-lead"
                        scores_out[k] = best_a[2]
                        continue
                if "下一个问题" in ans[:12] or ans.startswith("下一个问题"):
                    best_a = None
                    for xia_t, cue_i, _ in anchors:
                        if t0 + 0.5 <= xia_t < t1 - 0.5:
                            sc = score_seg_at_window(
                                segs[k],
                                cues_norm,
                                min(cue_i + 1, len(cues_norm) - 1),
                                converter,
                            )
                            if best_a is None or sc > best_a[0]:
                                best_a = (sc, xia_t)
                    if best_a and best_a[0] >= 20:
                        onsets[k] = best_a[1]
                        methods[k] = "followup-next_q"
                        scores_out[k] = best_a[0]
                        continue
                if slot_hi - slot_lo < 2.5:
                    continue
                hit = match_text_onset(
                    segs[k],
                    cues_norm,
                    _cue_at(cues_norm, max(t0, slot_lo - 25)),
                    converter,
                    prefer_answer=True,
                    min_onset=t0 + 0.5,
                )
                if hit and t0 + 0.5 <= hit[0] <= t1 - 0.8:
                    # keep if inside this followup's share of the window roughly
                    onsets[k] = hit[0]
                    methods[k] = "followup-answer"
                    scores_out[k] = _content_score(segs[k], cues_norm, hit[0], converter)
        i = j

    # Interpolate remaining holes by char weight
    known = [i for i, o in enumerate(onsets) if o is not None]
    if not known:
        for i in range(n):
            onsets[i] = audio_end * i / max(n, 1)
            methods[i] = "even"
        known = list(range(n))

    def _fill(a: int, b: int, t0: float, t1: float) -> None:
        idxs = list(range(a + 1, b))
        if not idxs:
            return
        body = list(range(a, b))
        weights = [max(answer_chars(segs[k]), 25) for k in body]
        total = sum(weights) or 1
        acc = weights[0]
        for k in idxs:
            onsets[k] = t0 + (t1 - t0) * acc / total
            methods[k] = "interpolated"
            acc += max(answer_chars(segs[k]), 25)

    if known[0] > 0:
        t1 = float(onsets[known[0]])  # type: ignore
        weights = [max(answer_chars(segs[k]), 25) for k in range(known[0] + 1)]
        total = sum(weights) or 1
        acc = 0.0
        for k in range(known[0]):
            onsets[k] = t1 * acc / total
            methods[k] = "interpolated"
            acc += weights[k]
    for a, b in zip(known, known[1:]):
        if b > a + 1:
            _fill(a, b, float(onsets[a]), float(onsets[b]))  # type: ignore
    if known[-1] < n - 1:
        _fill(known[-1], n, float(onsets[known[-1]]), audio_end)  # type: ignore

    # Content repair: weak primary → rematch inside (prev, next)
    for i in primary_idxs:
        if methods[i] == "keep-user-start":
            continue
        if methods[i].startswith("next_q") and scores_out[i] >= 28:
            continue
        if scores_out[i] >= 40:
            continue
        lo = float(onsets[i - 1]) + 0.4 if i and onsets[i - 1] is not None else 0.0  # type: ignore
        hi = float(onsets[i + 1]) - 0.3 if i + 1 < n and onsets[i + 1] is not None else audio_end  # type: ignore
        if hi - lo < 3.0:
            continue
        hit = match_text_onset(
            segs[i],
            cues_norm,
            _cue_at(cues_norm, lo),
            converter,
            prefer_answer=True,
            min_onset=lo,
        )
        if hit and lo <= hit[0] <= hi - 1.0:
            sc = _content_score(segs[i], cues_norm, hit[0], converter)
            if sc >= max(scores_out[i] + 12, 32):
                onsets[i] = hit[0]
                methods[i] = f"repair-{hit[2]}"
                scores_out[i] = sc

    # Monotonic onsets (never move keep-user-start backwards/forwards)
    out = [float(o if o is not None else 0.0) for o in onsets]
    for i in range(1, n):
        if methods[i] == "keep-user-start":
            continue
        if out[i] <= out[i - 1]:
            out[i] = out[i - 1] + 0.15
            methods[i] += "+mono"
    # Ensure keep-user-start still monotonic vs neighbors by moving non-kept
    for i in range(n):
        if methods[i] != "keep-user-start":
            continue
        if i and out[i] <= out[i - 1]:
            out[i - 1] = out[i] - 0.15
            if methods[i - 1] != "keep-user-start":
                methods[i - 1] += "+mono"
        if i + 1 < n and out[i + 1] <= out[i] and methods[i + 1] != "keep-user-start":
            out[i + 1] = out[i] + 0.15
            methods[i + 1] += "+mono"

    def _solid(idx: int) -> bool:
        m = methods[idx] or ""
        if m == "keep-user-start":
            return True
        if m.startswith("next_q"):
            return scores_out[idx] >= 32
        if m.startswith("name") or m.startswith("answer") or m.startswith("repair"):
            return scores_out[idx] >= 38
        return False

    # Collapse repair between solid anchors (char-weight redistribute)
    def _ends(idx: int) -> float:
        return out[idx + 1] if idx + 1 < n else audio_end

    def _collapse_count() -> int:
        c = 0
        for j in range(n):
            gap = _ends(j) - out[j]
            if gap < 2.0 and answer_chars(segs[j]) > 60:
                c += 1
        return c

    i = 0
    while i < n:
        gap = _ends(i) - out[i]
        chars = answer_chars(segs[i])
        if not (gap < 2.0 and chars > 60):
            i += 1
            continue
        left = i
        while left > 0 and not _solid(left):
            left -= 1
        right_bound = i
        while right_bound + 1 < n and not _solid(right_bound + 1):
            right_bound += 1
        nxt_solid = None
        for t in range(right_bound + 1, n):
            if _solid(t):
                nxt_solid = t
                break
        left_t = out[left]
        right_t = out[nxt_solid] if nxt_solid is not None else audio_end
        first = left + 1 if _solid(left) else left
        last = (nxt_solid - 1) if nxt_solid is not None else n - 1
        idxs = [t for t in range(first, last + 1) if not _solid(t)]
        if not idxs or right_t - left_t < 6.0:
            i = last + 1
            continue
        if _solid(left):
            w_left = max(answer_chars(segs[left]), 40)
            weights = [max(answer_chars(segs[t]), 40) for t in idxs]
            total_w = w_left + sum(weights) or 1
            cursor = left_t + (right_t - left_t) * w_left / total_w
        else:
            weights = [max(answer_chars(segs[t]), 40) for t in idxs]
            total_w = sum(weights) or 1
            cursor = left_t
            out[idxs[0]] = left_t
            methods[idxs[0]] = "charsplit"
            weights, idxs = weights[1:], idxs[1:]
            total_w = sum(weights) or 1
            if not idxs:
                i = last + 1
                continue
        span = right_t - cursor
        if span < 2.0:
            i = last + 1
            continue
        acc = 0.0
        for ti, t in enumerate(idxs):
            out[t] = cursor + span * acc / total_w
            methods[t] = "charsplit"
            scores_out[t] = _content_score(segs[t], cues_norm, out[t], converter)
            acc += weights[ti]
        i = last + 1

    # If still many collapses (anchors << segs), force full char-weight layout
    # while snapping primaries to nearby next_q when content score allows.
    # Skip this path when any starts are user-fixed (would clobber the suffix repair).
    has_fixed = any(m == "keep-user-start" for m in methods)
    if not has_fixed and (_collapse_count() >= 4 or (n >= 20 and len(anchors) * 2 < n)):
        weights = [max(answer_chars(s), 40) for s in segs]
        total_w = sum(weights) or 1
        prop = []
        acc = 0.0
        for w in weights:
            prop.append(audio_end * acc / total_w)
            acc += w
        # Snap non-followup segs to nearest unused next_q within 50s if content ok
        used = set()
        for i, seg in enumerate(segs):
            if followup[i] or i == 0:
                continue
            best = None
            for ai, (xia_t, cue_i, _) in enumerate(anchors):
                if ai in used:
                    continue
                if abs(xia_t - prop[i]) > 50:
                    continue
                sc = score_seg_at_window(
                    seg, cues_norm, min(cue_i + 1, len(cues_norm) - 1), converter
                )
                if best is None or sc > best[0]:
                    best = (sc, xia_t, ai)
            if best and best[0] >= 24:
                prop[i] = best[1]
                methods[i] = "next_q+prop"
                scores_out[i] = best[0]
                used.add(best[2])
        # Mono + re-proportion between snapped solids
        for i in range(1, n):
            if prop[i] <= prop[i - 1]:
                prop[i] = prop[i - 1] + 0.05
        solids = [0] + [
            i for i in range(1, n) if methods[i].startswith("next_q")
        ]
        solids = sorted(set(solids))
        for a, b in zip(solids, solids[1:] + [n]):
            if b <= a + 1:
                continue
            t0, t1 = prop[a], (prop[b] if b < n else audio_end)
            body = list(range(a, b))
            ws = [max(answer_chars(segs[k]), 40) for k in body]
            tot = sum(ws) or 1
            acc = ws[0]
            for k in range(a + 1, b):
                prop[k] = t0 + (t1 - t0) * acc / tot
                if not methods[k].startswith("next_q"):
                    methods[k] = "prop-split"
                acc += max(answer_chars(segs[k]), 40)
        if solids and solids[-1] < n - 1:
            a = solids[-1]
            t0, t1 = prop[a], audio_end
            body = list(range(a, n))
            ws = [max(answer_chars(segs[k]), 40) for k in body]
            tot = sum(ws) or 1
            acc = ws[0]
            for k in range(a + 1, n):
                prop[k] = t0 + (t1 - t0) * acc / tot
                methods[k] = "prop-split"
                acc += max(answer_chars(segs[k]), 40)
        out = prop
        for i in range(n):
            scores_out[i] = _content_score(segs[i], cues_norm, out[i], converter)

    for i in range(1, n):
        if methods[i] == "keep-user-start":
            continue
        if out[i] <= out[i - 1]:
            out[i] = out[i - 1] + 0.05
            if "mono" not in methods[i]:
                methods[i] += "+mono"

    # Adaptive lead → starts (fixed starts keep absolute value)
    starts = []
    floor = 0.0
    leads = []
    for i, onset in enumerate(out):
        if methods[i] == "keep-user-start":
            st = round(float(onset), 3)
            lead, gap = 0.0, 0.0
        else:
            st, lead, gap = start_from_onset(onset, cues_raw, floor=floor)
        starts.append(st)
        leads.append((lead, gap, onset))
        floor = st + 0.05

    for i in range(1, n):
        if methods[i] == "keep-user-start":
            continue
        if starts[i] <= starts[i - 1]:
            starts[i] = round(starts[i - 1] + 0.05, 3)

    return starts, methods, scores_out, leads, len(anchors)


def verify_content(segs, starts, cues_norm, converter) -> List[str]:
    warns = []
    audio_end = cues_norm[-1][1] if cues_norm else 0.0
    for i, seg in enumerate(segs):
        st = starts[i]
        en = starts[i + 1] if i + 1 < len(starts) else audio_end
        if en <= st:
            warns.append(f"#{seg.get('index')} end<=start")
        sc = _content_score(seg, cues_norm, st, converter)
        chars = answer_chars(seg)
        dur = en - st
        if dur < 1.5 and chars > 80:
            warns.append(f"#{seg.get('index')} collapse dur={dur:.2f} chars={chars}")
        # Weak content only for non-tiny answers
        if chars > 40 and sc < 12 and not (seg.get("answer_text") or "").startswith("下一个问题"):
            # follow-ups / short may score low
            q = (seg.get("q_text") or "")[:20]
            if not re.match(r"^[2-9]", q.strip()):
                warns.append(f"#{seg.get('index')} weak-content score={sc:.1f}")
    return warns


def realign_session(
    session: dict,
    converter,
    keep_through: Optional[int] = None,
) -> Tuple[dict, dict]:
    srt = Path(session.get("srt_file") or "")
    if not srt.exists():
        return session, {"error": "no_srt"}
    cues_norm = parse_srt(srt, converter)
    cues_raw = parse_srt_raw(srt)
    if not cues_norm:
        return session, {"error": "empty_srt"}

    audio_end = float(cues_norm[-1][1])
    segs = session.get("segments") or []
    fixed_starts = None
    if keep_through is not None:
        fixed_starts = {}
        for seg in segs:
            idx = int(seg.get("index") or 0)
            if idx <= keep_through and seg.get("start") is not None:
                fixed_starts[idx] = float(seg["start"])
    starts, methods, scores, leads, n_anchors = assign_onsets(
        segs, cues_norm, cues_raw, converter, audio_end, fixed_starts=fixed_starts
    )

    new_segs = []
    stats = {
        "segs": len(segs),
        "anchors": n_anchors,
        "next_q": 0,
        "content": 0,
        "other": 0,
        "weak": 0,
        "kept": 0,
    }
    for i, seg in enumerate(segs):
        if seg.get("locked"):
            new_segs.append(dict(seg))
            continue
        start = round(starts[i], 3)
        end = round(starts[i + 1], 3) if i + 1 < len(starts) else round(audio_end, 3)
        if end <= start:
            end = round(start + 0.5, 3)
        method = methods[i]
        lead, gap, onset = leads[i]
        if method == "keep-user-start":
            stats["kept"] += 1
        elif method.startswith("next_q"):
            stats["next_q"] += 1
        elif method in ("name", "answer", "question", "repair-name", "repair-answer", "repair-question"):
            stats["content"] += 1
        else:
            stats["other"] += 1
        if scores[i] < 15:
            stats["weak"] += 1
        note = (
            f"leadin:{method}|lead={lead:.2f}|gap={gap:.2f}"
            f"|onset={onset:.3f}|cscore={scores[i]:.1f}"
        )
        fields = range_fields(
            start,
            end,
            0.93 if method.startswith("next_q") or method == "keep-user-start" else 0.82,
            "manual",
            srt_preview(cues_raw, start, end),
        )
        fields["notes"] = note
        new_segs.append({**seg, **fields})

    opening = dict(session.get("opening") or {})
    intro = normalize("今天是", converter)
    op_start = float(opening.get("start") or 0.0)
    for st, _, t in cues_norm[:50]:
        if intro[:3] in t or "今天是" in t:
            op_start, op_lead, op_gap = start_from_onset(st, cues_raw, floor=0.0)
            opening["notes"] = f"leadin:opening|lead={op_lead:.2f}|gap={op_gap:.2f}"
            break
    first = new_segs[0]["start"] if new_segs else audio_end
    opening.update(
        range_fields(
            round(op_start, 3),
            round(float(first), 3),
            0.85,
            "manual",
            srt_preview(cues_raw, op_start, first),
        )
    )
    for k in ("text", "text_preview"):
        if session.get("opening") and k in session["opening"]:
            opening[k] = session["opening"][k]

    warns = verify_content(segs, starts, cues_norm, converter)
    stats["warns"] = len(warns)
    stats["warn_list"] = warns
    return {**session, "segments": new_segs, "opening": opening, "srt_file": str(srt)}, stats


def session_selected(session: dict, args) -> bool:
    sid = session["session_id"]
    if args.session:
        return sid in args.session
    if sid in SKIP_SESSION_IDS:
        return False
    if sid == "2025-07-07-tieba":
        return True
    return session.get("date", "") >= args.from_date


def count_collapses(session: dict) -> int:
    n = 0
    prev = -1.0
    for seg in session.get("segments") or []:
        st, en = seg.get("start"), seg.get("end")
        if st is None or en is None:
            n += 1
            continue
        if st < prev - 0.01 or en - st < 1.5 and answer_chars(seg) > 80:
            n += 1
        prev = float(st)
    return n


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", default="2025-07-08")
    parser.add_argument("--month", action="append")
    parser.add_argument("--session", action="append")
    parser.add_argument(
        "--keep-through",
        type=int,
        default=None,
        help="Keep segment starts with index <= N (requires --session)",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Write even if new alignment has more collapses than current",
    )
    args = parser.parse_args(argv)

    converter = get_converter()
    months = args.month or [
        "2025-06", "2025-07", "2025-08", "2025-09",
        "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
    ]

    grand = {"sessions": 0, "warn": 0, "weak_sessions": 0, "kept_old": 0}

    for month in months:
        path = MAP_DIR / f"{month}.json"
        if not path.exists():
            print(f"[{month}] missing")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        new_sessions = []
        month_n = 0
        for session in data.get("sessions") or []:
            if not session_selected(session, args):
                new_sessions.append(session)
                continue
            old_c = count_collapses(session)
            keep_through = args.keep_through if args.session else None
            aligned, stats = realign_session(
                session, converter, keep_through=keep_through
            )
            if "error" in stats:
                print(f"  {session['session_id']}: ERROR {stats['error']}")
                new_sessions.append(session)
                continue
            warns = stats.get("warn_list") or []
            new_c = count_collapses(aligned)
            keep_old = (not args.force) and new_c > old_c + 1
            tag = "KEEP-OLD" if keep_old else "OK"
            print(
                f"  {session['session_id']}: segs={stats['segs']} anchors={stats['anchors']} "
                f"next_q={stats['next_q']} content={stats['content']} other={stats['other']} "
                f"kept={stats.get('kept', 0)} weak_cscore={stats['weak']} warns={len(warns)} "
                f"collapse {old_c}->{new_c} [{tag}]"
            )
            for w in warns[:8]:
                print(f"    ! {w}")
            if len(warns) > 8:
                print(f"    ! ... +{len(warns) - 8} more")
            grand["sessions"] += 1
            grand["warn"] += 0 if keep_old else len(warns)
            if (0 if keep_old else len(warns)) >= 3:
                grand["weak_sessions"] += 1
            if keep_old:
                grand["kept_old"] += 1
                new_sessions.append(session)
            else:
                month_n += 1
                new_sessions.append(aligned)

        data["sessions"] = new_sessions
        if args.apply and month_n:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[{month}] wrote {path} ({month_n} sessions)")
        else:
            print(f"[{month}] done ({month_n} sessions, dry-run={not args.apply})")

    print(
        f"TOTAL sessions={grand['sessions']} warns={grand['warn']} "
        f"sessions_with_3+_warns={grand['weak_sessions']} kept_old={grand['kept_old']}"
    )
    if not args.apply:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
