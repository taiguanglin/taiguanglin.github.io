#!/usr/bin/env python3
"""Realign audio_map segments with adaptive lead-in before spoken onset.

Rules:
1. When SRT has「下一个问题」(or ASR variants), the segment starts shortly
   before the character「下」(time interpolated within the cue).
2. Otherwise match the answer / questioner opening text; start shortly before
   that spoken onset.
3. Lead-in is NOT a fixed −0.5s: if the pause after the previous spoken cue is
   large enough, use 0.5s; if speech is nearly continuous, use 0.1–0.4s.
4. Ends = next segment start; last end = audio end.
5. Opening ends at segment 1 start.

Processes sessions with date >= --from-date (default 2025-06-12).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from common import (
    MAP_DIR,
    DEFAULT_SRT_ROOT,
    fmt_tc,
    get_converter,
    match_start,
    normalize,
    parse_srt,
    parse_srt_raw,
    range_fields,
    spoken_name_variants,
    srt_preview,
)


def adaptive_lead(gap: float) -> float:
    """Choose lead-in from pause length before the match onset.

    Large pause → 0.5s. Near-continuous speech → 0.1–0.4s.
    """
    if gap >= 0.55:
        return 0.5
    if gap >= 0.45:
        return 0.4
    if gap >= 0.35:
        return 0.3
    if gap >= 0.25:
        return 0.2
    if gap >= 0.15:
        return 0.15
    return 0.1


def prev_cue_end_before(cues_raw, onset: float) -> float:
    """End of the last cue that finishes before ``onset``."""
    prev_end = 0.0
    for st, en, _ in cues_raw:
        if st >= onset - 0.01:
            break
        if en <= onset + 0.02:
            prev_end = float(en)
        else:
            # onset lies inside this cue — previous spoken end is prior cue
            break
    return prev_end


def start_from_onset(
    onset: float,
    cues_raw,
    floor: float = 0.0,
) -> Tuple[float, float, float]:
    """Return (start, lead_used, gap) with adaptive pre-roll before onset."""
    prev_end = prev_cue_end_before(cues_raw, onset)
    gap = max(0.0, float(onset) - prev_end)
    lead = adaptive_lead(gap)
    start = float(onset) - lead
    # Never cut into previous spoken cue; stay in the pause (or just after it).
    start = max(start, prev_end, floor, 0.0)
    lead_used = max(0.0, float(onset) - start)
    return round(start, 3), round(lead_used, 3), round(gap, 3)

# Raw (unnormalized) patterns for locating「下」in cue text
NEXT_Q_RAW = re.compile(
    r"(那|我|好的?|嗯+|啊+)?"
    r"(下[一1]?个问题|下一個問題|下一个問題|下[一1]個問題|下个问题|下個問題)"
)

# Normalized forms (after PUNCT strip) for scanning
NEXT_Q_NORM_NEEDLES = [
    "下一个问题",
    "下个问题",
    "那下一个问题",
    "我下一个问题",
]


def answer_chars(seg: dict) -> int:
    t = seg.get("answer_text") or seg.get("answer_preview") or ""
    return len(re.sub(r"\s+", "", t))


def cue_char_time(cue_start: float, cue_end: float, text: str, char_index: int) -> float:
    """Interpolate time of a character within a cue."""
    n = max(len(text), 1)
    idx = max(0, min(char_index, n - 1))
    frac = idx / n
    return cue_start + (cue_end - cue_start) * frac


def _has_next_q_phrase(text: str) -> bool:
    """Strict: must contain 下…问题 as a transition phrase (not random 下)."""
    compact = re.sub(r"\s+", "", text or "")
    if NEXT_Q_RAW.search(compact):
        return True
    # normalized check on compact without relying on OpenCC here
    for pat in (
        "下一个问题", "下个问题", "下一個問題", "下個問題",
        "下一个問題", "下一個问题",
    ):
        if pat in compact:
            return True
    return False


def find_xia_time_in_cue(st: float, en: float, raw_text: str) -> Optional[float]:
    """If cue contains 下一个问题…, return time of「下」, else None."""
    compact = re.sub(r"\s+", "", raw_text or "")
    if not _has_next_q_phrase(compact):
        return None
    m = NEXT_Q_RAW.search(compact)
    if m:
        xia_pos = m.start() + m.group(0).find("下")
        if xia_pos >= 0:
            return cue_char_time(st, en, compact, xia_pos)
    for pat in ("下一个问题", "下个问题", "下一個問題", "下個問題", "下一个問題"):
        p = compact.find(pat)
        if p >= 0:
            return cue_char_time(st, en, compact, p)
    p = compact.find("下")
    if p >= 0:
        return cue_char_time(st, en, compact, p)
    return st


def collect_next_q_anchors(
    cues_raw: List[Tuple[float, float, str]],
    cues_norm: List[Tuple[float, float, str]],
) -> List[Tuple[float, int, str]]:
    """Return list of (xia_time, cue_idx, kind) for each true 下一个问题."""
    anchors = []
    for i, (st, en, raw) in enumerate(cues_raw):
        norm = cues_norm[i][2] if i < len(cues_norm) else normalize(raw)
        # Single cue
        xia = find_xia_time_in_cue(st, en, raw)
        # Split across two cues: e.g.「那」+「下一个问题」or「下一个」+「问题」
        if xia is None and i + 1 < len(cues_raw):
            st2, en2, raw2 = cues_raw[i + 1]
            merged = re.sub(r"\s+", "", raw + raw2)
            if _has_next_q_phrase(merged) or any(
                n in normalize(raw + raw2) for n in ("下一个问题", "下个问题")
            ):
                # Prefer the cue that contains 下
                if "下" in re.sub(r"\s+", "", raw) and (
                    "问题" in merged[merged.find("下") : merged.find("下") + 8]
                    or "問題" in merged[merged.find("下") : merged.find("下") + 8]
                ):
                    xia = find_xia_time_in_cue(st, en2, raw + raw2)
                elif "下" in re.sub(r"\s+", "", raw2):
                    xia = find_xia_time_in_cue(st2, en2, raw2)
                    if xia is not None:
                        anchors.append((xia, i + 1, "next_q"))
                        continue
                else:
                    xia = find_xia_time_in_cue(st, en2, raw + raw2)
        # Normalized fallback only if phrase clearly in this cue
        if xia is None and any(n in norm for n in ("下一个问题", "下个问题")):
            xia = find_xia_time_in_cue(st, en, raw) or st

        if xia is not None:
            anchors.append((xia, i, "next_q"))

    anchors.sort()
    out = []
    for a in anchors:
        if not out or a[0] - out[-1][0] >= 0.35:
            out.append(a)
    return out


def score_seg_at_window(
    seg: dict,
    cues_norm,
    cue_idx: int,
    converter,
) -> float:
    """How well answer/name matches SRT starting at cue_idx."""
    parts = []
    n = 0
    for j in range(cue_idx, min(len(cues_norm), cue_idx + 30)):
        parts.append(cues_norm[j][2])
        n += len(cues_norm[j][2])
        if n >= 140:
            break
    win = "".join(parts)
    score = 0.0
    answer = normalize(seg.get("answer_text") or seg.get("answer_preview") or "", converter)
    if answer:
        # trigram overlap
        if len(answer) >= 3 and len(win) >= 3:
            ta = {answer[i : i + 3] for i in range(min(100, len(answer) - 2))}
            tb = {win[i : i + 3] for i in range(len(win) - 2)}
            if ta:
                score += 100.0 * len(ta & tb) / len(ta)
        pref = answer[:8]
        if len(pref) >= 4 and pref[:4] in win:
            score += 30
    for name in spoken_name_variants(seg.get("questioner") or "", converter):
        if len(name) >= 2 and name in win:
            score += 45
            break
    return score


# Spoken primary vs follow-up (audio_map/AGENTS.md — segment identity).
_FLOOR_OPEN_RE = re.compile(
    r"^(?:下一个问题[，,\s]*)?(?:第[一二三四五六七八九十百零〇\d]+|\d+)楼"
)
_FOLLOWUP_OPEN_RE = re.compile(
    r"^(?:"
    r"第[二三四五六七八九十\d]+个问题"
    r"|第二个问题|第三个问题|第四个问题"
    r"|最后问"
    r"|下面的问题|下面说"
    r"|还有下一个问题|还有下面|还有第"
    r")"
)


def _is_followup_seg(seg: dict, prev_seg: Optional[dict] = None) -> bool:
    """True for same-person numbered/topic follow-ups (not a new floor).

    A spoken floor (「第N楼」/「下一个问题11楼…」) is always primary, even when
    ``q_text`` starts with ``2、``. Same questioner alone is NOT enough —
    e.g.「再问一个」is often preceded by a spoken「下一个问题」and must consume
    that anchor unless the answer itself is a follow-up opening.
    """
    q = (seg.get("q_text") or seg.get("q_preview") or "").strip()
    a = (seg.get("answer_text") or seg.get("answer_preview") or "").strip()
    if _FLOOR_OPEN_RE.match(a):
        return False
    if re.match(r"^[2-9２-９二三四五六七八九十]+[、.．\)]", q):
        return True
    if re.match(r"^[2-9２-９][\.．、]", q):
        return True
    if _FOLLOWUP_OPEN_RE.match(a):
        return True
    if (
        a.startswith("下一个问题")
        and prev_seg
        and (seg.get("questioner") or "")
        and seg.get("questioner") == prev_seg.get("questioner")
    ):
        return True
    return False


def match_text_onset(
    seg: dict,
    cues_norm,
    cursor_idx: int,
    converter,
    *,
    prefer_answer: bool = False,
    min_onset: float = 0.0,
) -> Optional[Tuple[float, int, str]]:
    """Match answer/name; return (onset_time, cue_idx, method)."""

    def _ok(res) -> bool:
        return res is not None and res[0] >= min_onset - 0.05

    answer = normalize(seg.get("answer_text") or seg.get("answer_preview") or "", converter)
    q = normalize(seg.get("q_text") or seg.get("q_preview") or "", converter)

    order = []
    if prefer_answer:
        order = ["answer", "question", "name"]
    else:
        order = ["name", "answer", "question"]

    for kind in order:
        if kind == "name" and not prefer_answer:
            for name in spoken_name_variants(seg.get("questioner") or "", converter):
                if len(name) < 2:
                    continue
                res = match_start(
                    cues_norm, cursor_idx, name, min_len=2, min_block=min(4, len(name)), max_scan=300
                )
                if _ok(res):
                    return res[0], res[1], "name"
        elif kind == "name" and prefer_answer:
            # follow-up: only use name if nothing else works (handled later)
            continue
        elif kind == "answer" and len(answer) >= 6:
            # Skip leading "下一个问题" echo in PDF answer text
            ans = answer
            for prefix in ("下一个问题", "下个问题"):
                if ans.startswith(prefix):
                    ans = ans[len(prefix) :]
                    break
            needle = ans[:90] if len(ans) >= 90 else ans
            if len(needle) >= 6:
                res = match_start(cues_norm, cursor_idx, needle, min_len=6, min_block=5, max_scan=360)
                if _ok(res):
                    return res[0], res[1], "answer"
        elif kind == "question" and len(q) >= 10:
            needle = q[4:50] if len(q) > 50 else q
            # strip leading numbering
            needle = re.sub(r"^[0-9一二三四五六七八九十]+", "", needle)
            if len(needle) >= 8:
                res = match_start(cues_norm, cursor_idx, needle, min_len=6, min_block=6, max_scan=360)
                if _ok(res):
                    return res[0], res[1], "question"

    if prefer_answer:
        for name in spoken_name_variants(seg.get("questioner") or "", converter):
            if len(name) < 2:
                continue
            res = match_start(
                cues_norm, cursor_idx, name, min_len=2, min_block=min(4, len(name)), max_scan=300
            )
            if _ok(res):
                return res[0], res[1], "name"

    if len(answer) >= 10:
        ans = answer
        for prefix in ("下一个问题", "下个问题"):
            if ans.startswith(prefix):
                ans = ans[len(prefix) :]
                break
        res = match_start(cues_norm, 0, ans[:90], min_len=10, min_block=8, max_scan=len(cues_norm))
        if _ok(res):
            return res[0], res[1], "answer_global"
    return None


def _cue_idx_at_time(cues_norm, t: float) -> int:
    for i, (st, en, _) in enumerate(cues_norm):
        if en >= t:
            return i
    return max(0, len(cues_norm) - 1)


def assign_starts(
    segs: list,
    anchors: List[Tuple[float, int, str]],
    cues_norm,
    cues_raw,
    converter,
    audio_end: float,
) -> Tuple[List[float], List[str]]:
    """Assign starts: 下一个问题→「下」−adaptive; else text onset −adaptive."""
    n = len(segs)
    starts: List[Optional[float]] = [None] * n
    methods: List[str] = [""] * n

    followup_flags = [
        _is_followup_seg(segs[i], segs[i - 1] if i else None) for i in range(n)
    ]
    primary = [i for i in range(n) if not followup_flags[i]]

    def _score_at(seg_i: int, cue_i: int) -> float:
        sc = score_seg_at_window(
            segs[seg_i], cues_norm, min(cue_i + 1, len(cues_norm) - 1), converter
        )
        sc += score_seg_at_window(segs[seg_i], cues_norm, cue_i, converter) * 0.35
        return sc

    def _onset_start(onset: float, floor: float, tag: str) -> Tuple[float, str]:
        st, lead, gap = start_from_onset(onset, cues_raw, floor=floor)
        return st, f"{tag}|lead={lead:.2f}|gap={gap:.2f}"

    # Pass 1a: first primary by name/answer with adaptive lead-in
    if primary:
        i0 = primary[0]
        hit = match_text_onset(segs[i0], cues_norm, 0, converter, prefer_answer=False, min_onset=0.0)
        if hit:
            starts[i0], methods[i0] = _onset_start(hit[0], 0.0, hit[2])
        else:
            starts[i0] = 0.0
            methods[i0] = "missing"

    # Pass 1b: sequential — each primary after #1 consumes the next 下一个问题.
    # Extra primaries (no remaining anchors) fall through to text/interpolate.
    a_ptr = 0
    for pi in range(1, len(primary)):
        if a_ptr >= len(anchors):
            break
        i = primary[pi]
        min_t = 0.0
        for j in range(i - 1, -1, -1):
            if starts[j] is not None:
                min_t = float(starts[j]) + 0.4
                break
        while a_ptr < len(anchors) and anchors[a_ptr][0] < min_t - 0.2:
            a_ptr += 1
        if a_ptr >= len(anchors):
            break
        xia_t, cue_i, _k = anchors[a_ptr]
        # One-step peek: skip a false-positive / early anchor if the next one
        # matches this segment much better (and current score is weak).
        sc = _score_at(i, cue_i)
        if a_ptr + 1 < len(anchors) and sc < 40:
            xia2, cue2, _ = anchors[a_ptr + 1]
            if 0 < xia2 - xia_t < 60:
                sc2 = _score_at(i, cue2)
                if sc2 >= max(sc + 25, 42):
                    a_ptr += 1
                    xia_t, cue_i = xia2, cue2
        st, meth = _onset_start(xia_t, max(0.0, min_t - 0.4), "next_q")
        starts[i] = st
        methods[i] = meth
        a_ptr += 1

    # Pass 2a: numbered followup runs → char-split between surrounding primaries
    # (they share one 下一个问题 and must not all pile on the next next_q)
    i = 0
    while i < n:
        if not followup_flags[i] or starts[i] is not None:
            i += 1
            continue
        j = i
        while j < n and followup_flags[j] and starts[j] is None:
            j += 1
        # parent = last primary before i
        parent = i - 1
        while parent >= 0 and followup_flags[parent]:
            parent -= 1
        nxt = j  # next primary (or n)
        while nxt < n and starts[nxt] is None and followup_flags[nxt]:
            nxt += 1
        t0 = float(starts[parent]) if parent >= 0 and starts[parent] is not None else 0.0
        if nxt < n and starts[nxt] is not None:
            t1 = float(starts[nxt])
        else:
            t1 = audio_end
        # Split parent..followups across [t0, t1) by chars; keep parent start
        body = list(range(parent, j)) if parent >= 0 else list(range(i, j))
        if parent >= 0 and starts[parent] is not None:
            weights = [max(answer_chars(segs[k]), 30) for k in body]
            total = sum(weights) or 1
            acc = weights[0]
            for k in range(i, j):
                starts[k] = t0 + (t1 - t0) * acc / total
                methods[k] = "followup-split"
                acc += max(answer_chars(segs[k]), 30)
            # Refine each followup with answer onset − adaptive lead inside its slot
            for k in range(i, j):
                slot_lo = float(starts[k])  # type: ignore
                slot_hi = float(starts[k + 1]) if k + 1 < j else t1  # type: ignore
                if slot_hi - slot_lo < 3.0:
                    continue
                c0 = _cue_idx_at_time(cues_norm, slot_lo)
                hit = match_text_onset(
                    segs[k], cues_norm, c0, converter, prefer_answer=True, min_onset=slot_lo
                )
                if not hit:
                    continue
                st, meth = _onset_start(hit[0], slot_lo + 0.3, "followup-answer")
                if st <= slot_hi - 1.0:
                    starts[k] = st
                    methods[k] = meth
        i = j

    # Pass 2b: remaining missing primaries with text onset − 0.5
    for i in range(n):
        if starts[i] is not None:
            continue
        lo = 0.0
        hi = audio_end
        for j in range(i - 1, -1, -1):
            if starts[j] is not None:
                lo = float(starts[j]) + 0.25
                break
        for j in range(i + 1, n):
            if starts[j] is not None:
                hi = float(starts[j]) - 0.1
                break
        c0 = _cue_idx_at_time(cues_norm, lo)
        hit = match_text_onset(
            segs[i],
            cues_norm,
            c0,
            converter,
            prefer_answer=False,
            min_onset=lo,
        )
        if hit and hit[0] <= hi + 5:
            st, meth = _onset_start(hit[0], lo, hit[2])
            if hi - lo > 1:
                st = min(st, hi - 0.5)
            starts[i] = max(lo, st)
            methods[i] = meth
        else:
            starts[i] = None
            methods[i] = "missing"

    # Interpolate missing by answer-char weights (not even split)
    def _char_interp(i0: int, i1: int, t0: float, t1: float) -> None:
        """Fill starts (i0, i1) exclusively between t0 and t1."""
        idxs = list(range(i0 + 1, i1))
        if not idxs:
            return
        # weights for segments i0..i1-1 (who occupy the span)
        body = list(range(i0, i1))
        weights = [max(answer_chars(segs[k]), 25) for k in body]
        total = sum(weights) or 1
        acc = weights[0]
        for k in idxs:
            # start of seg k = t0 + span * (weight of segs before k) / total
            starts[k] = t0 + (t1 - t0) * acc / total
            methods[k] = "interpolated"
            acc += max(answer_chars(segs[k]), 25)

    known = [i for i, s in enumerate(starts) if s is not None]
    if not known:
        for i in range(n):
            starts[i] = audio_end * i / max(n, 1)
            methods[i] = "even-split"
        known = list(range(n))

    if known[0] > 0:
        t1 = float(starts[known[0]])  # type: ignore
        # invent a virtual start at 0 for weighting
        weights = [max(answer_chars(segs[k]), 25) for k in range(known[0] + 1)]
        total = sum(weights) or 1
        acc = 0.0
        for k in range(known[0]):
            starts[k] = t1 * acc / total
            methods[k] = "interpolated"
            acc += weights[k]
    for a, b in zip(known, known[1:]):
        if b == a + 1:
            continue
        _char_interp(a, b, float(starts[a]), float(starts[b]))  # type: ignore
    if known[-1] < n - 1:
        t0 = float(starts[known[-1]])  # type: ignore
        _char_interp(known[-1], n, t0, audio_end)
        # _char_interp fills (known[-1], n) i.e. known[-1]+1 .. n-1 — good

    out = [float(s) if s is not None else 0.0 for s in starts]

    def _anchored(idx: int) -> bool:
        m = methods[idx] or ""
        return (
            m.startswith("next_q")
            or m.startswith("name")
            or m.startswith("answer")
            or m.startswith("question")
        )

    # Per-seg answer re-match when collapsed and NOT a solid next_q / followup-split
    for i in range(n):
        if methods[i].startswith("next_q") or methods[i].startswith("followup"):
            continue
        st = out[i]
        en = out[i + 1] if i + 1 < n else audio_end
        dur = en - st
        chars = answer_chars(segs[i])
        if dur >= 3.5 or chars < 60:
            continue
        lo = out[i - 1] + 0.5 if i else 0.0
        hi = out[i + 1] if i + 1 < n else audio_end
        # Don't jump onto the next segment's doorstep
        c0 = _cue_idx_at_time(cues_norm, lo)
        hit = match_text_onset(
            segs[i], cues_norm, c0, converter, prefer_answer=True, min_onset=lo
        )
        if hit and lo <= hit[0] <= hi - 2.0:
            new_st, meth = _onset_start(hit[0], lo, "answer-repair")
            if new_st > st + 0.8 and new_st < hi - 2.0:
                out[i] = new_st
                methods[i] = meth

    # Cluster repair only for non-anchored collapsed runs between anchored bounds
    MIN_GAP = 1.2

    def _ends(idx: int) -> float:
        return out[idx + 1] if idx + 1 < n else audio_end

    i = 0
    while i < n:
        gap = _ends(i) - out[i]
        chars = answer_chars(segs[i])
        if not (gap < MIN_GAP and chars > 80 and not methods[i].startswith("next_q")):
            i += 1
            continue
        # Find surrounding anchored boundaries
        left_i = i
        while left_i > 0 and not _anchored(left_i):
            left_i -= 1
        right_i = i
        while right_i + 1 < n and not _anchored(right_i + 1):
            right_i += 1
        # Redistribute only the unanchored segs strictly inside (left_i, right_bound)
        # Keep left_i start fixed if anchored; right bound = start of next anchored or audio_end
        left = out[left_i]
        # segs to move: from left_i+1 if left anchored else left_i, through right_i
        first = left_i + 1 if _anchored(left_i) else left_i
        # right edge
        nxt_anch = None
        for t in range(right_i + 1, n):
            if _anchored(t):
                nxt_anch = t
                break
        right = out[nxt_anch] if nxt_anch is not None else audio_end
        last = (nxt_anch - 1) if nxt_anch is not None else n - 1
        if first > last or right - left < 6.0:
            i = last + 1
            continue
        # Only rewrite unanchored indices in [first, last]
        idxs = [t for t in range(first, last + 1) if not _anchored(t)]
        if len(idxs) < 1:
            i = last + 1
            continue
        # Include the span after left through right; place idxs by char weight
        # If first was left_i+1, left edge is left (anchored start)
        span_left = left if _anchored(left_i) else out[first]
        weights = [max(answer_chars(segs[t]), 40) for t in idxs]
        # Also reserve weight for the anchored left segment's remaining content
        if _anchored(left_i):
            w_left = max(answer_chars(segs[left_i]), 40)
            total_w = w_left + sum(weights)
            cursor = span_left + (right - span_left) * w_left / total_w
        else:
            total_w = sum(weights) or 1
            cursor = span_left
            # first idx keeps relative position via weights from start
            out[idxs[0]] = span_left
            methods[idxs[0]] = "charsplit"
            weights = weights[1:]
            idxs = idxs[1:]
            total_w = sum(weights) or 1
            if not idxs:
                i = last + 1
                continue
        span = right - cursor
        if span < 3.0:
            i = last + 1
            continue
        acc = 0.0
        for ti, t in enumerate(idxs):
            out[t] = cursor + span * acc / total_w
            methods[t] = "charsplit"
            acc += weights[ti]
        i = last + 1

    # Enforce monotonic with small epsilon only as last resort
    final = []
    for i, v in enumerate(out):
        if final and v <= final[-1]:
            v = final[-1] + 0.05
            if "mono" not in methods[i]:
                methods[i] += "+mono"
        final.append(v)
    return final, methods


def realign_session(session: dict, converter) -> Tuple[dict, dict]:
    srt = Path(session.get("srt_file") or "")
    if not srt.exists():
        return session, {"error": "no_srt"}
    cues_norm = parse_srt(srt, converter)
    cues_raw = parse_srt_raw(srt)
    if not cues_norm:
        return session, {"error": "empty_srt"}

    audio_end = cues_norm[-1][1]
    segs = session.get("segments") or []
    anchors = collect_next_q_anchors(cues_raw, cues_norm)
    starts, methods = assign_starts(segs, anchors, cues_norm, cues_raw, converter, audio_end)

    new_segs = []
    stats = {
        "next_q": 0,
        "text": 0,
        "interpolated": 0,
        "anchors": len(anchors),
        "segs": len(segs),
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
        if method.startswith("next_q"):
            stats["next_q"] += 1
        elif "interpolated" in method or method == "even-split":
            stats["interpolated"] += 1
        else:
            stats["text"] += 1
        preview = srt_preview(cues_raw, start, end)
        fields = range_fields(start, end, 0.92 if "next_q" in method else 0.8, "manual", preview)
        fields["notes"] = f"leadin:{method}"
        new_segs.append({**seg, **fields})

    # Opening
    opening = dict(session.get("opening") or {})
    intro = normalize("今天是", converter)
    op_start = 0.0
    op_note = "leadin:opening"
    for st, _, t in cues_norm[:50]:
        if intro[:3] in t or "今天是" in t:
            op_start, op_lead, op_gap = start_from_onset(st, cues_raw, floor=0.0)
            op_note = f"leadin:opening|lead={op_lead:.2f}|gap={op_gap:.2f}"
            break
    first = new_segs[0]["start"] if new_segs else audio_end
    opening.update(
        range_fields(round(op_start, 3), round(float(first), 3), 0.85, "manual", srt_preview(cues_raw, op_start, first))
    )
    opening["notes"] = op_note
    # preserve text fields
    for k in ("text", "text_preview"):
        if session.get("opening") and k in session["opening"]:
            opening[k] = session["opening"][k]

    return {**session, "segments": new_segs, "opening": opening, "srt_file": str(srt)}, stats


def adjust_session_leadin(session: dict, converter) -> Tuple[dict, dict]:
    """Re-apply adaptive lead-in on existing boundaries (keep structure).

    For each segment, recover the spoken onset near the current start
    (「下一个问题」→「下」, else answer/name text, else start+0.5 from prior
    hard pre-roll), then set start = onset − adaptive_lead(gap).
    """
    srt = Path(session.get("srt_file") or "")
    if not srt.exists():
        return session, {"error": "no_srt"}
    cues_norm = parse_srt(srt, converter)
    cues_raw = parse_srt_raw(srt)
    if not cues_norm:
        return session, {"error": "empty_srt"}

    audio_end = float(cues_norm[-1][1])
    segs = session.get("segments") or []
    anchors = collect_next_q_anchors(cues_raw, cues_norm)
    stats = {"next_q": 0, "text": 0, "fallback": 0, "segs": len(segs), "anchors": len(anchors)}

    onsets: List[Tuple[float, str]] = []
    for i, seg in enumerate(segs):
        old = float(seg.get("start") or 0.0)
        nxt = float(segs[i + 1]["start"]) if i + 1 < len(segs) else audio_end
        notes = seg.get("notes") or ""
        onset = None
        via = "fallback"

        # 1) Prefer 下一个问题「下」near current start
        best_a = None
        for xia_t, _ci, _k in anchors:
            if old - 0.4 <= xia_t <= old + 2.2:
                # Prefer onset just after old start (typical hard −0.5 → onset≈old+0.5)
                score = -abs(xia_t - (old + 0.45))
                if best_a is None or score > best_a[0]:
                    best_a = (score, xia_t)
        if best_a is not None and ("next_q" in notes or best_a[1] <= old + 1.2):
            onset, via = best_a[1], "next_q"

        # 2) Content onset near start
        if onset is None:
            c0 = _cue_idx_at_time(cues_norm, max(0.0, old - 0.2))
            hit = match_text_onset(
                seg, cues_norm, c0, converter, prefer_answer=True, min_onset=max(0.0, old - 0.2)
            )
            if hit and old - 0.3 <= hit[0] <= min(nxt - 0.5, old + 3.0):
                onset, via = hit[0], hit[2]

        # 3) Fallback: prior maps used hard −0.5s
        if onset is None:
            onset = min(old + 0.5, (old + nxt) / 2 if nxt > old else old + 0.2)
            via = "fallback"

        onsets.append((float(onset), via))

    new_starts = []
    floor = 0.0
    methods = []
    for i, (onset, via) in enumerate(onsets):
        old = float(segs[i].get("start") or 0.0)
        nxt_onset = onsets[i + 1][0] if i + 1 < len(onsets) else audio_end
        st, lead, gap = start_from_onset(onset, cues_raw, floor=floor)
        # Keep structure: do not jump far from existing boundary
        st = max(old - 0.2, min(st, old + 0.55))
        st = max(floor, st)
        # Never cross next onset
        if st >= nxt_onset - 0.05:
            st = max(floor, min(old, nxt_onset - 0.15))
        new_starts.append(round(st, 3))
        methods.append(f"{via}|lead={lead:.2f}|gap={gap:.2f}")
        if via == "next_q":
            stats["next_q"] += 1
        elif via == "fallback":
            stats["fallback"] += 1
        else:
            stats["text"] += 1
        floor = new_starts[-1] + 0.05

    for i in range(1, len(new_starts)):
        if new_starts[i] <= new_starts[i - 1]:
            new_starts[i] = round(new_starts[i - 1] + 0.05, 3)

    # If adaptive lead would create a new collapse/absurd rate, keep old start.
    def _bad(st: float, en: float, seg: dict) -> bool:
        dur = en - st
        chars = answer_chars(seg)
        if dur <= 0.05:
            return True
        if dur < 2 and chars > 80:
            return True
        if chars > 60 and chars / dur > 30:
            return True
        return False

    for i, seg in enumerate(segs):
        old_st = float(seg.get("start") or 0.0)
        old_en = float(seg.get("end") or audio_end)
        new_st = new_starts[i]
        new_en = new_starts[i + 1] if i + 1 < len(new_starts) else audio_end
        if _bad(new_st, new_en, seg) and not _bad(old_st, old_en, seg):
            # Neighbor start moved earlier (more lead) — restore it first
            if i + 1 < len(new_starts):
                old_next = float(segs[i + 1].get("start") or new_starts[i + 1])
                if new_starts[i + 1] + 0.01 < old_next:
                    new_starts[i + 1] = round(old_next, 3)
                    methods[i + 1] = methods[i + 1] + "|keep-old"
                    new_en = new_starts[i + 1]
            if _bad(new_starts[i], new_en, seg):
                new_starts[i] = round(old_st, 3)
                methods[i] = methods[i] + "|keep-old"
    for i in range(1, len(new_starts)):
        if new_starts[i] <= new_starts[i - 1]:
            new_starts[i] = round(new_starts[i - 1] + 0.05, 3)

    new_segs = []
    for i, seg in enumerate(segs):
        if seg.get("locked"):
            new_segs.append(dict(seg))
            continue
        start = new_starts[i]
        end = new_starts[i + 1] if i + 1 < len(new_starts) else round(audio_end, 3)
        if end <= start:
            end = round(start + 0.5, 3)
        preview = srt_preview(cues_raw, start, end)
        fields = range_fields(
            start, end, 0.92 if methods[i].startswith("next_q") else 0.85, "manual", preview
        )
        fields["notes"] = f"leadin:{methods[i]}"
        new_segs.append({**seg, **fields})

    opening = dict(session.get("opening") or {})
    intro = normalize("今天是", converter)
    op_start = float(opening.get("start") or 0.0)
    op_note = "leadin:opening"
    for st, _, t in cues_norm[:50]:
        if intro[:3] in t or "今天是" in t:
            op_start, op_lead, op_gap = start_from_onset(st, cues_raw, floor=0.0)
            op_note = f"leadin:opening|lead={op_lead:.2f}|gap={op_gap:.2f}"
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
    opening["notes"] = op_note
    for k in ("text", "text_preview"):
        if session.get("opening") and k in session["opening"]:
            opening[k] = session["opening"][k]

    return {**session, "segments": new_segs, "opening": opening, "srt_file": str(srt)}, stats


def verify_session(session: dict, converter) -> List[str]:
    """Return human-readable warnings for a session."""
    warnings = []
    srt = Path(session.get("srt_file") or "")
    if not srt.exists():
        return ["NO_SRT"]
    cues_raw = parse_srt_raw(srt)
    cues_norm = parse_srt(srt, converter)
    segs = session.get("segments") or []
    prev = -1.0
    for seg in segs:
        st, en = seg.get("start"), seg.get("end")
        if st is None or en is None:
            warnings.append(f"#{seg['index']} missing times")
            continue
        if st < prev - 0.01:
            warnings.append(f"#{seg['index']} non-monotonic ({st} < {prev})")
        if en <= st:
            warnings.append(f"#{seg['index']} end<=start")
        dur = en - st
        chars = answer_chars(seg)
        cps = chars / dur if dur > 0.05 else 999
        if dur < 2 and chars > 80:
            warnings.append(f"#{seg['index']} collapse dur={dur:.2f} chars={chars}")
        if cps > 30 and chars > 60:
            warnings.append(f"#{seg['index']} absurd cps={cps:.1f}")
        # Check next_q method: SRT near start should have 下
        notes = seg.get("notes") or ""
        if "next_q" in notes:
            # Include overlapping cues (long cues may start before st)
            window = "".join(
                t
                for (cs, ce, t) in cues_raw
                if ce >= st - 0.1 and cs <= st + 2.5
            )
            if "下" not in window and "下" not in normalize(window, converter):
                warnings.append(f"#{seg['index']} next_q but no 下 near start")
        prev = st
    return warnings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", default="2025-06-12")
    parser.add_argument("--month", action="append")
    parser.add_argument("--session", action="append")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--adjust-leadin",
        action="store_true",
        help="Keep existing boundaries; only re-apply adaptive lead-in before onset",
    )
    args = parser.parse_args(argv)

    converter = get_converter()
    months = args.month or [
        "2025-06", "2025-07", "2025-08", "2025-09",
        "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
    ]

    grand = {"sessions": 0, "next_q": 0, "text": 0, "interpolated": 0, "fallback": 0, "warn": 0}

    for month in months:
        path = MAP_DIR / f"{month}.json"
        if not path.exists():
            print(f"[{month}] missing")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        new_sessions = []
        for session in data.get("sessions") or []:
            if session.get("date", "") < args.from_date:
                new_sessions.append(session)
                continue
            if args.session and session["session_id"] not in args.session:
                new_sessions.append(session)
                continue

            if args.verify_only:
                warns = verify_session(session, converter)
                print(f"  {session['session_id']}: warns={len(warns)}")
                for w in warns[:12]:
                    print(f"    ! {w}")
                new_sessions.append(session)
                grand["warn"] += len(warns)
                grand["sessions"] += 1
                continue

            if args.adjust_leadin:
                aligned, stats = adjust_session_leadin(session, converter)
            else:
                aligned, stats = realign_session(session, converter)
            if "error" in stats:
                print(f"  {session['session_id']}: ERROR {stats['error']}")
                new_sessions.append(session)
                continue
            warns = verify_session(aligned, converter)
            interp = stats.get("interpolated", stats.get("fallback", 0))
            print(
                f"  {session['session_id']}: segs={stats['segs']} anchors={stats['anchors']} "
                f"next_q={stats['next_q']} text={stats['text']} "
                f"other={interp} warns={len(warns)}"
            )
            for w in warns[:8]:
                print(f"    ! {w}")
            if len(warns) > 8:
                print(f"    ! ... +{len(warns) - 8} more")
            grand["sessions"] += 1
            grand["next_q"] += stats["next_q"]
            grand["text"] += stats["text"]
            grand["interpolated"] += stats.get("interpolated", 0)
            grand["fallback"] += stats.get("fallback", 0)
            grand["warn"] += len(warns)
            new_sessions.append(aligned)

        data["sessions"] = new_sessions
        if args.apply and not args.verify_only:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[{month}] wrote {path}")
        else:
            print(f"[{month}] done (dry-run)")

    print(
        f"TOTAL sessions={grand['sessions']} next_q={grand['next_q']} "
        f"text={grand['text']} interp={grand['interpolated']} "
        f"fallback={grand['fallback']} warns={grand['warn']}"
    )
    if not args.apply and not args.verify_only:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
