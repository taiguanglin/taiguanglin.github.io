#!/usr/bin/env python3
"""Shared char-stream locator for chrono-docx alignment (Phase 2 & 3).

Instead of comparing needles against individual SRT cues (ratio ceiling too
low for long needles), we run ``difflib.SequenceMatcher.find_longest_match``
of a probe against the WHOLE session pinyin string with a moving lower bound
— one matcher per probe, O(len_probe × remaining_stream) per call, and the
longest-common-block metric is immune to ASR homophone noise.
"""
from __future__ import annotations

import sys
from difflib import SequenceMatcher
from pathlib import Path

TOOL = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL))
sys.path.insert(0, str(TOOL.parent / "pdf_audio_map"))

from wcommon import get_converter, py_norm, StreamCache  # noqa: E402
from common import spoken_name_variants  # noqa: E402


class StreamIndex:
    """Session pinyin string + cached SequenceMatchers per probe."""

    def __init__(self, srt_file: str, cache: StreamCache):
        self.ss = cache.stream(srt_file)
        self.srt_file = srt_file
        self.S = self.ss.py
        self._sm: dict = {}

    def sm(self, probe: str) -> SequenceMatcher:
        m = self._sm.get(probe)
        if m is None:
            m = SequenceMatcher(None, probe, self.S, autojunk=False)
            self._sm[probe] = m
        return m


def make_probes(block: dict, conv) -> list:
    """Pinyin probes for one docx block: spoken name + answer/question chunks."""
    probes = []
    name = (block.get("asker_raw") or "").strip()
    if name and 2 <= len(name) <= 25:
        for v in spoken_name_variants(name, conv):
            pv = py_norm(v, conv)
            if len(pv) >= 3:
                probes.append(pv)
    a = block.get("a_text") or ""
    q = block.get("q_text") or ""
    for src, size in ((a, 32), (q, 26)):
        t = py_norm(src, conv)
        if len(t) >= size:
            probes.append(t[:size])
            if len(t) >= size * 2 + 20:
                probes.append(t[-size:])
        elif t:
            probes.append(t)
    # de-dup, keep order
    seen, out = set(), []
    for p in probes:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def locate_ordered(idx: StreamIndex, probes_per_block: list, conv,
                   meta: list = None, min_lcb: int = 13,
                   name_bonus: int = 6) -> list:
    """Ordered greedy location of every block's probes in the stream.

    Monotone forward-only: a block is accepted only if its best probe match
    lies at/after the current cursor with ``lcb >= min_lcb`` (minus a bonus
    when an asker-name probe lands near the candidate - spoken names are the
    strongest disambiguator against formulaic religious phrases). Rejected
    blocks never move the cursor. Returns [{pos, lcb, named}] per block."""
    S_len = len(idx.S)
    cursor = 0
    results = []
    for bi, probes in enumerate(probes_per_block):
        asker = meta[bi] if meta else ""
        name_probes = []
        if asker and 2 <= len(asker) <= 25:
            for v in spoken_name_variants(asker, None):
                pv = py_norm(v, conv)
                if len(pv) >= 3:
                    name_probes.append(pv)

        best = None  # (lcb, pos)
        for p in probes:
            if not p:
                continue
            m = idx.sm(p)
            mb = m.find_longest_match(0, len(p), cursor, S_len)
            if best is None or mb.size > best[0]:
                best = (mb.size, mb.b)
        named = False
        pos, lcb = None, 0
        if best and best[0] > 0:
            pos_cand = best[1]
            eff = best[0]
            if name_probes:
                lo = max(cursor, pos_cand - 70)
                hi = min(S_len, pos_cand + max(len(n) for n in name_probes) + 70)
                for np_ in name_probes:
                    nm = idx.sm(np_)
                    if nm.find_longest_match(0, len(np_), lo, hi).size >= max(3, len(np_) - 2):
                        named = True
                        break
            if named:
                eff += name_bonus
            if eff >= min_lcb:
                pos, lcb = pos_cand, best[0]
        assert pos is None or pos <= S_len
        results.append({"pos": pos, "lcb": lcb, "named": named})
        if pos is not None:
            cursor = pos
    return results


def _candidates(idx: StreamIndex, probes: list, conv, asker: str,
                top_k: int = 14, floor: int = 9):
    """Candidate (pos, lcb) list for one block from all probe occurrences."""
    S_len = len(idx.S)
    cands: dict = {}
    name_probes = []
    if asker and 2 <= len(asker) <= 25:
        for v in spoken_name_variants(asker, None):
            pv = py_norm(v, conv)
            if len(pv) >= 3:
                name_probes.append(pv)
    for p in probes:
        if not p or len(p) < 6:
            continue
        m = idx.sm(p)
        for mb in m.get_matching_blocks():
            if mb.size == 0:
                continue
            if mb.size >= (floor if not p.isdigit() else floor + 4):
                old = cands.get(mb.b)
                if old is None or mb.size > old:
                    cands[mb.b] = mb.size
    out = []
    for pos, size in cands.items():
        named = False
        if name_probes:
            lo, hi = max(0, pos - 70), min(S_len, pos + 90)
            for np_ in name_probes:
                nm = idx.sm(np_)
                if nm.find_longest_match(0, len(np_), lo, hi).size >= max(3, len(np_) - 2):
                    named = True
                    break
        out.append((pos, size + (6 if named else 0)))
    out.sort(key=lambda t: -t[1])
    return out[:top_k]


def locate_dp(idx: StreamIndex, probes_per_block: list, conv,
              meta: list = None, skip_penalty: float = 7.0,
              min_gap: int = 5):
    """Monotone assignment maximising total evidence (DP over candidates).

    Returns [{pos, lcb}] with pos=None for blocks left unassigned."""
    n = len(probes_per_block)
    meta = meta or [""] * n
    C = [_candidates(idx, probes_per_block[i], conv, meta[i])
         for i in range(n)]
    NEG = float("-inf")
    # dp[j] = (best_score, prev_j, action) while scanning blocks; state = chosen
    # candidate index of previous block (-1 = skipped)
    dp = {(-1): (0.0, None)}          # block0 layer filled below
    layers = []
    # initialise layer for block 0
    cur = {}
    cur[-1] = (0.0, None)             # skip block 0
    for j, (pos, sc) in enumerate(C[0]):
        cur[j] = (sc, ("assign", -1))
    layers.append(cur)
    for i in range(1, n):
        prev_layer = layers[-1]
        cur = {}
        # skip this block
        best_prev = max((v[0], k) for k, v in prev_layer.items())
        cur[-1] = (best_prev[0] - 0.5, ("skip", best_prev[1]))
        Ci = C[i]
        for j, (pos, sc) in enumerate(Ci):
            best = NEG
            barg = None
            for pj, pv in prev_layer.items():
                if pj == -1:
                    base = pv[0]
                    ppos = None
                else:
                    ppos = C[i - 1][pj][0]
                    if ppos is not None and pos < ppos + min_gap:
                        continue
                    base = pv[0]
                if base > best:
                    best = base
                    barg = pj
            if best > NEG:
                cur[j] = (best + sc, ("assign", barg))
        # carry skip forward
        layers.append(cur)
    # traceback from best final state
    last = layers[-1]
    score, j = max((v[0], k) for k, v in last.items())
    path = [j]
    act = last[j][1] if last[j][1] else ("skip", None)
    acts = [act]
    for i in range(n - 1, 0, -1):
        act = layers[i].get(path[0], (0, ("skip", None)))[1] or ("skip", None)
        pj = act[1]
        path.insert(0, pj)
    results = []
    for i in range(n):
        j = path[i]
        if j is None or j == -1:
            results.append({"pos": None, "lcb": 0})
        else:
            pos, sc = C[i][j]
            results.append({"pos": pos, "lcb": sc})
    return results
