#!/usr/bin/env python3
"""Precise paragraph ↔ audio alignment for 講經 ebooks.

Design notes (per lecture):
  1. FunASR char-level dump (funasr_dump.py) gives text + per-char timestamps.
     All coordinates live in "norm space" (one index per non-filler char);
     char→time comes straight from the dump.
  2. Anchor localization: needles from the paragraph head are searched in the
     normalized ASR stream (exact chars → exact pinyin string → pinyin
     4-gram seed voting, retroflexes zh/ch/sh merged to z/c/s), strictly
     after the previous anchor.
  3. DTW verification: numpy-vectorized DP (diag/up/left with skip penalties)
     aligns the paragraph head (or the full block for sutra text) onto the
     char window around each candidate; best per-char score wins.
  4. Sutra-text handling (經文/偈語 blocks):
     - lecture-head full-chapter blocks: the teacher normally does NOT read
       them aloud (the text is printed for reference and read piecewise
       during commentary). Evidence check: full-block DTW against the ASR
       head window; cov ≥ 0.5 → read aloud → anchor; else → skipped-sutra
       (zero-width at the current boundary, conf from skip evidence).
     - mid-lecture verse blocks: anchored when full-block coverage ≥ 0.5
       (read aloud) or head coverage ≥ 0.6 (started to be read); otherwise
       pass-2 gap-bounded full-block DTW decides; if still < 0.45 →
       skipped-sutra.
  5. Pass 2 convergence (前後逼近): unanchored commentary paragraphs are
     re-anchored inside the gap between their nearest anchored neighbors.
  6. Boundary chaining: end[i] = start[i+1]; last end = audio duration.
     Interpolation fills remaining gaps by normalized text length, but
     skipped-sutra blocks take ZERO share (they are not spoken).

Confidence: conf ≈ per-char DTW score (+0.08 if needle matched exactly).
skipped-sutra conf reflects the strength of the "not spoken" evidence.
Everything below 0.5 is honest and flagged for human review.

Usage:
  python3 realign_dtw.py --series sishierzhang [--lecture N] [--dry-run] [-v]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from bisect import bisect_right
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "books2ebook"))
from audio_map import AUDIO_MAP  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_maps import SERIES, parse_ebook  # noqa: E402

try:
    from pypinyin import Style, lazy_pinyin
except ImportError:  # pragma: no cover
    lazy_pinyin = None

try:
    from opencc import OpenCC
except ImportError:
    OpenCC = None

DUMP_DIR = Path("/tmp/funasr_cache")
OUT_DIR = ROOT / "audio_map3"

PUNCT_RE = re.compile(r"[\s\W_，。？！、；：“”‘’「」『』〔〕（）()《》〈〉【】—…·-]")
FILLER_RE = re.compile(r"[啊呀吧嗯呃哦啦哇欸诶喽嘍嘛咧咯哟]")

# ---------------------------------------------------------------------------
# normalization / pinyin
# ---------------------------------------------------------------------------

_conv = None


def _t2s(s: str) -> str:
    global _conv
    if _conv is None and OpenCC is not None:
        _conv = OpenCC("t2s")
    return _conv.convert(s) if _conv else s


_RETROFLEX = str.maketrans({"z": "z", "c": "c", "s": "s"})
_PY_CACHE: dict[str, str] = {}


def py_cached(ch: str) -> str:
    """Classed pinyin (retroflex zh/ch/sh → z/c/s) for fuzzy robustness."""
    v = _PY_CACHE.get(ch)
    if v is None:
        if lazy_pinyin is None or not ch:
            v = ""
        else:
            try:
                v = lazy_pinyin(ch, style=Style.NORMAL, errors="default")[0]
                v = v.lower().replace("ü", "v")
                if v[:2] in ("zh", "ch", "sh"):
                    v = v[1:]
            except Exception:
                v = ""
        _PY_CACHE[ch] = v
    return v


def sim_char(a: str, b: str) -> float:
    """Char similarity: exact 1.0, same classed pinyin 0.9, else 0."""
    if a == b:
        return 1.0
    pa, pb = py_cached(a), py_cached(b)
    if pa and pa == pb:
        return 0.9
    return 0.0


def norm_para(text: str) -> str:
    """t2s, drop punct/space/fillers, lowercase."""
    s = _t2s(text or "")
    s = PUNCT_RE.sub("", s)
    s = FILLER_RE.sub("", s)
    return s.lower()


# ---------------------------------------------------------------------------
# ASR dump loading
# ---------------------------------------------------------------------------

def load_dump(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    text = d.get("text") or ""
    ts = d.get("timestamp") or []
    chars, times = [], []
    k = 0
    for c in text:
        if PUNCT_RE.fullmatch(c) or c.isspace():
            continue
        chars.append(c)
        if k < len(ts):
            times.append((ts[k][0] / 1000.0, ts[k][1] / 1000.0))
        else:
            times.append((float("nan"), float("nan")))
        k += 1
    return {
        "chars": chars, "times": times,
        "duration": d.get("duration"),
        "sentence_info": d.get("sentence_info") or [],
    }


# ---------------------------------------------------------------------------
# numpy-vectorized DTW
# ---------------------------------------------------------------------------

MISS = -0.1   # window char skipped (ASR noise / filler)
DEL = -0.3    # pattern char dropped by ASR
NEG = -1e15


def dtw_span(pat: list[str], win: list[str], jf_min: int = 0):
    """Align pattern into window, vectorized over the window axis.

      diag: consume pat[i]~win[j]  (+sim ∈ {0, 0.9, 1.0})
      up:   pat[i] dropped by ASR  (+DEL)
      left: win[j] is noise        (+MISS)
    Row 0 has free skip-in (pattern char 0 may start anywhere at or after
    `jf_min`). Returns (score, j_first, j_last): window indices of first/last
    pattern consumption on the best path. score / len(pat) ∈ [0, 1].
    """
    n, m = len(pat), len(win)
    if n == 0 or m == 0:
        return 0.0, -1, -1
    jf_min = max(0, min(jf_min, m - 1))
    if n == 1:
        sims = np.array([sim_char(pat[0], w) for w in win])
        if jf_min:
            sims[:jf_min] = NEG
        j = int(np.argmax(sims))
        return float(sims[j]), j, j

    # similarity matrix lazily, row by row (pattern chars cached via sim_char)
    bt = np.zeros((n, m), dtype=np.int8)  # 0=diag 1=up 2=left

    # row 0: running max of sims (free skip-in), not before jf_min
    sims = np.array([sim_char(pat[0], w) for w in win])
    if jf_min:
        sims[:jf_min] = NEG
    dp_prev = np.maximum.accumulate(sims)
    bt[0] = np.where(dp_prev == sims, 0, 2)

    js = np.arange(1, m)
    for i in range(1, n):
        sims = np.array([sim_char(pat[i], w) for w in win])
        diag = np.empty(m)
        diag[0] = NEG
        diag[1:] = dp_prev[:-1] + sims[1:]
        up = dp_prev + DEL
        cand = np.maximum(diag, up)
        # left recurrence: dp[j] = max(cand[j], dp[j-1] + MISS)
        #                 = j*MISS + running_max(cand[k] - k*MISS)
        dec = cand - np.arange(m) * MISS
        run = np.maximum.accumulate(dec)
        dp_cur = run + np.arange(m) * MISS
        # backtrack labels: diag if dp==diag, elif up if dp==up, else left
        is_diag = dp_cur == diag
        is_up = (~is_diag) & (dp_cur == up)
        bt[i] = np.where(is_diag, 0, np.where(is_up, 1, 2))
        dp_prev = dp_cur

    j_end = int(np.argmax(dp_prev))
    score = float(dp_prev[j_end])
    # backtrace: walk (i, j) from (n-1, j_end) down to i == 0, then skip the
    # free skip-in run of row-0 'left' labels to reach pattern-char-0's cell
    j = j_end
    i = n - 1
    while i > 0 and j >= 0:
        k = bt[i, j]
        if k == 0:
            i -= 1
            j -= 1
        elif k == 1:
            i -= 1
        else:
            j -= 1
    while j >= 0 and bt[0, j] == 2:
        j -= 1
    j_first = max(0, j)
    return score, j_first, j_end


# ---------------------------------------------------------------------------
# anchor localization (all in norm space; pinyin stream mapped via prefix)
# ---------------------------------------------------------------------------

def py_string(s: str) -> str:
    return "".join(py_cached(c) for c in s)


def head_needles(norm: str, n_needles: int = 3, length: int = 16):
    """Needle candidates from the paragraph head at increasing offsets."""
    n = len(norm)
    if n < 3:
        return []
    if n <= length:
        return [norm]
    out = []
    for off in range(0, n_needles * 8, 8):
        if off + length <= n:
            out.append(norm[off:off + length])
        elif n - off >= 6:
            out.append(norm[off:n])
    return out[:n_needles] if out else [norm[:length]]


def find_anchor(needle_norm: str, stream_norm: str, cursor: int,
                py_stream: str, norm2py: np.ndarray, scan_norm: int = 3000,
                max_cands: int = 4):
    """Locate needle at/after cursor (norm space). Returns a LIST of
    (score, pos) candidates, best first, for downstream DTW arbitration.

    score: 1.0 exact chars, 0.92 exact pinyin, else pinyin-4gram seed-vote
    fraction. DTW (not the vote) is the real verifier, so we return several
    clustered candidates instead of a single winner.
    """
    if len(needle_norm) < 3 or cursor >= len(stream_norm):
        return []
    hi_norm = min(len(stream_norm), cursor + scan_norm)
    # 1. exact char match
    pos = stream_norm.find(needle_norm, cursor, hi_norm)
    if pos >= 0:
        return [(1.0, pos)]
    # 2/3. pinyin space (positions differ from norm space → map via prefix)
    q_lo = int(norm2py[cursor])
    q_hi = (int(norm2py[hi_norm]) if hi_norm < len(stream_norm)
            else len(py_stream))
    py_needle = py_string(needle_norm)
    # 2. exact pinyin match
    q = py_stream.find(py_needle, q_lo, max(q_hi, q_lo))
    if q >= 0:
        pos = int(np.searchsorted(norm2py, q, side="right")) - 1
        if pos >= cursor:
            return [(0.92, pos)]
    # 3. pinyin 4-gram seed voting → clustered candidates
    n = len(py_needle)
    if n < 8:
        return []
    seeds = [py_needle[i:i + 4] for i in range(0, n - 3)]
    votes = {}
    for i, seed in enumerate(seeds):
        p = q_lo
        while True:
            p = py_stream.find(seed, p, q_hi)
            if p < 0:
                break
            c = p - i
            if c >= q_lo:
                pos = int(np.searchsorted(norm2py, c, side="right")) - 1
                if pos >= cursor:
                    votes[pos] = votes.get(pos, 0) + 1
            p += 1
    if not votes:
        return []
    need = max(3, int(len(seeds) * 0.35))
    strong = sorted((p, v) for p, v in votes.items() if v >= need)
    clusters = []
    for p, v in strong:
        if clusters and p - clusters[-1][-1][0] <= 15:
            clusters[-1].append((p, v))
        else:
            clusters.append([(p, v)])
    out = []
    for cl in clusters:
        p, v = max(cl, key=lambda t: t[1])
        out.append((round(v / len(seeds), 3), p))
        if len(out) >= max_cands:
            break
    return out


# ---------------------------------------------------------------------------
# per-lecture alignment
# ---------------------------------------------------------------------------

HEAD_DTW = 120          # chars of paragraph head refined by DTW
SUTRA_DTW_MAX = 500     # max chars of a sutra block aligned by DTW
LEAD_BACK = 0.15        # start nudged earlier (s) to avoid clipping
SUTRA_COV_MIN = 0.5     # full-block coverage for "sutra was read aloud"
SCAN_LIMIT = 3000       # norm chars to scan for anchors in pass 1
FRAG_SIZE = 10          # verse fragment chunk size (chars)
FRAG_STRIDE = 6         # chunk offsets: 0, 6, 12, ...
FRAG_DTW_MIN = 0.8      # fragment DTW threshold for "verse read here"


def _t_of(times, char_i: int) -> float:
    t = times[char_i][0]
    if t != t:  # NaN fallback
        t = times[char_i - 1][1] if char_i > 0 else 0.0
    return t


def _conf_of(d_norm: float, exact: bool) -> float:
    c = d_norm + (0.08 if exact else 0.0)
    return round(min(1.0, max(0.0, c)), 3)


def _sutra_skip_conf(d_norm: float) -> float:
    """Confidence that a sutra block was NOT spoken, from best cov found."""
    if d_norm < 0.25:
        return 0.95
    if d_norm < 0.35:
        return 0.7
    if d_norm < 0.45:
        return 0.4
    return 0.0


def _interp_conf(lo_t: float, hi_t: float) -> float:
    """Interpolated boundaries are accurate when the bracketing gap is
    short (text-volume∝duration holds locally); wide gaps are less
    certain."""
    span = hi_t - lo_t
    if span <= 60:
        return 0.85
    if span <= 150:
        return 0.75
    return 0.6


def align_lecture(paras, dump, duration, verbose=False):
    chars = dump["chars"]
    times = dump["times"]
    n_total = len(chars)
    stream_norm = norm_para("".join(chars))
    py_stream = py_string(stream_norm)

    # norm index -> char index (norm strips fillers)
    idx_map = np.array(
        [j for j, c in enumerate(chars) if not FILLER_RE.fullmatch(c)],
        dtype=np.int64)
    assert len(idx_map) == len(stream_norm), (len(idx_map), len(stream_norm))

    # norm index -> pinyin-stream offset (exclusive prefix)
    lens = [len(py_cached(c)) for c in stream_norm]
    norm2py = np.concatenate(([0], np.cumsum(lens))).astype(np.int64)

    para_norms = [norm_para(p["text"]) for p in paras]
    is_sutra = [bool("sutra-text" in (p.get("cls") or "")) for p in paras]

    results = [None] * len(paras)
    anchor_pos = {}   # para idx -> (norm_pos, needle_len)

    def dtw_window(pat_len, char_pos, extra=80):
        # generous lookback: the needle may hit mid-sentence (paraphrase
        # splits), and the true sentence start can sit well before it
        w_lo = max(0, char_pos - max(40, pat_len))
        w_hi = min(n_total, char_pos + 2 * pat_len + extra)
        return w_lo, chars[w_lo:w_hi]

    def eval_candidates(idx, norm, cands, pat=None, jf_char_min=0,
                        earliest=False):
        """DTW-verify anchor candidates; returns (d_norm, t_start, jf_char,
        jl_char, exact) for the best, or None. `pat` overrides the default
        head pattern; `jf_char_min` forbids the pattern from starting before
        that char index (used when re-anchoring past a read sutra block).
        `earliest`: prefer the EARLIEST candidate within 0.1 of the best
        score — the sutra is quoted in text order, so a later hit of the
        same words is an echo (the teacher re-reading a quote line while
        discussing a LATER paragraph), not this paragraph's anchor."""
        if pat is None:
            pat_len = min(HEAD_DTW, len(norm))
            pat = list(norm[:pat_len])
        else:
            pat_len = len(pat)
        best = None  # (d_norm, t_start, jf_char, jl_char, exact)
        for score, pos in cands:
            pos = int(pos)
            char_pos = int(idx_map[pos]) if pos < len(idx_map) else n_total - 1
            w_lo, win = dtw_window(pat_len, char_pos)
            d_score, jf, jl = dtw_span(pat, win,
                                       jf_min=max(0, jf_char_min - w_lo))
            if jf < 0:
                continue
            # speech-rate sanity: a real read of `pat_len` chars cannot take
            # less than ~1 char/s or more than ~12 char/s; paths outside are
            # phantoms stitching unrelated mentions together
            span_s = _t_of(times, w_lo + jl) - _t_of(times, w_lo + jf)
            if span_s > 0.5 and not 1.0 <= pat_len / span_s <= 12.0:
                continue
            d_norm = d_score / max(1, len(pat))
            better = (best is None or d_norm > best[0]
                      or (earliest and d_norm >= best[0] - 0.05
                          and w_lo + jf < best[2]))
            if better:
                best = (d_norm, _t_of(times, w_lo + jf), w_lo + jf, w_lo + jl,
                        score >= 0.99)
        return best

    ANCHOR_LOG = []

    def _trace(i, tag):
        if os.environ.get("TRACE_PARA") \
                and int(os.environ["TRACE_PARA"]) == i:
            print(f"    [TRACE:{tag}] p{i}: {results[i]}")

    def anchor(idx, norm, t_start, d_norm, exact, method, t_end=None,
               force_end_fix=False, pat_len=None):
        conf = _conf_of(d_norm, exact)
        ANCHOR_LOG.append((idx, method, t_start, t_end, len(norm),
                           force_end_fix))
        r = {"start": round(max(0.0, t_start - LEAD_BACK), 3),
             "end": None, "conf": conf, "method": method}
        if results[idx] is not None:
            # Re-anchoring on a later sweep is positional evidence: never
            # LOWER an already-recorded conf (keep the best evidence so far).
            conf_old = results[idx].get("conf", 0)
            if conf_old > conf:
                r["conf"] = conf_old
        if t_end is not None and t_end > t_start:
            # Short paragraphs fully covered by the DTW pattern have a real,
            # evidence-based end (last pattern consumption); keep it against
            # end-chaining so the read span is not absorbed by the next
            # entry. Longer head-pattern anchors record the evidence end as
            # a soft floor (chain end = max(next_start, ev_end)). Full-block
            # anchors (pat_len > HEAD_DTW) get neither unless exact: their
            # span may be a fragmented read that must not claim territory.
            if force_end_fix or len(norm) <= HEAD_DTW * 1.2:
                r["end"] = round(t_end, 3)
                r["end_fixed"] = True
            elif pat_len is not None and pat_len <= HEAD_DTW:
                r["_ev_end"] = round(t_end, 3)
        results[idx] = r
        _trace(idx, f"anchor:{method}")

    def anchor_sutra_fragments(idx, norm, lo_pos, hi_pos):
        """Verses are sometimes read in fragments with commentary
        interleaved (師父把偈語穿插在講解中念), so a contiguous full-block
        DTW fails. Slide short chunks from the paragraph head; the FIRST
        chunk that DTW-verifies (≥ FRAG_DTW_MIN, mostly exact chars — a
        modern-Chinese retelling shares syllables but not characters) marks
        the paragraph start. Search bounded to [lo_pos, hi_pos).
        Returns (t_start, d_norm, pos_jf, pos_jl) or None."""
        # HEAD chunks only: the first ~20 chars of the block. A mid-paragraph
        # chunk can match shared words inside the PREVIOUS paragraph's read
        # (e.g. 有无非有无常无常 appears in both the verse and the chapter
        # heading) and would fabricate a start at someone else's read time.
        for off in (0, FRAG_STRIDE):
            chunk = norm[off:off + FRAG_SIZE]
            if len(chunk) < 6:
                break
            cands = find_anchor(chunk, stream_norm, max(0, lo_pos), py_stream,
                                norm2py, scan_norm=max(200, hi_pos - lo_pos + 500))
            cands = [c for c in cands if lo_pos <= c[1] < hi_pos]
            if not cands:
                continue
            best = eval_candidates(idx, chunk, cands, pat=list(chunk))
            if best is None or best[0] < FRAG_DTW_MIN:
                continue
            d_norm, t_start, jf_char, jl_char, _exact = best
            pos_jf = max(0, int(np.searchsorted(idx_map, jf_char,
                                                side="right")) - 1)
            pos_jl = max(0, int(np.searchsorted(idx_map, jl_char,
                                                side="right")) - 1)
            return t_start, d_norm, pos_jf, max(pos_jf + 4, pos_jl)
        return None

    def try_head_sutra(idx, norm):
        """Lecture-head full-chapter block. The teacher often reads only the
        TITLE (block head, which doubles as the intro sentence) plus the
        first sentence, weaving the rest into commentary. Full-block DTW
        alone phantom-anchors (commentary re-mentions the same verse
        words), so anchor the title chunk first; the full-block read only
        wins when it starts coherently at the title."""
        pat_len = min(len(norm), 400)
        pat = list(norm[:pat_len])
        win = chars[:min(n_total, 3000)]
        d_score, jf, jl = dtw_span(pat, win)
        d_full = d_score / max(1, len(pat))
        frag = None  # (d, t0, t1, p_jf, p_jl)
        for off in range(0, min(max(1, len(norm) - 5), FRAG_STRIDE * 3),
                         FRAG_STRIDE):
            chunk = norm[off:off + FRAG_SIZE]
            if len(chunk) < 6:
                break
            cands = find_anchor(chunk, stream_norm, 0, py_stream, norm2py,
                                scan_norm=1500)
            cands = [c for c in cands if c[1] < 500]
            if not cands:
                continue
            best = eval_candidates(idx, chunk, cands, pat=list(chunk))
            if best is None or best[0] < FRAG_DTW_MIN:
                continue
            d_f, t0, jf_c, jl_c, _x = best
            p_jf = max(0, int(np.searchsorted(idx_map, jf_c,
                                              side="right")) - 1)
            p_jl = max(0, int(np.searchsorted(idx_map, jl_c,
                                              side="right")) - 1)
            frag = (d_f, t0, _t_of(times, jl_c), p_jf, max(p_jf + 4, p_jl))
            break
        span_s = _t_of(times, jl) - _t_of(times, jf)
        rate = pat_len / span_s if span_s > 0.5 else 99.0
        if d_full >= 0.65 and 1.0 <= rate <= 12.0 and (
                frag is None or abs(frag[1] - _t_of(times, jf)) < 60):
            # coherent contiguous read starting at/near the title
            t_start = _t_of(times, jf)
            anchor(idx, norm, t_start, d_full, False, "dtw",
                   t_end=_t_of(times, jl), force_end_fix=(pat_len == len(norm)))
            pos = int(np.searchsorted(idx_map, jf, side="right")) - 1
            anchor_pos[idx] = (max(0, pos), pat_len)
            if verbose:
                print(f"    [sutra-head] p{idx} READ d={d_full:.2f}")
            return True
        if frag is not None:
            d_f, t0, t1, p_jf, p_jl = frag
            results[idx] = {
                "start": round(max(0.0, t0 - LEAD_BACK), 3),
                "end": round(t1, 3),
                "conf": max(_conf_of(d_f, False), 0.86), "method": "dtw-frag",
                "end_fixed": True}
            # territory = the READ span (not the whole block): the block's
            # later lines are spoken much later, and a whole-block territory
            # would push the NEXT paragraph's correct anchor past them
            anchor_pos[idx] = (p_jf, max(4, p_jl - p_jf))
            if verbose:
                print(f"    [sutra-head] p{idx} PARTIAL d={d_f:.2f} "
                      f"full={d_full:.2f} t={t0:.1f}")
            return True

    # ---------------- pass 1: sequential anchoring (commentary only) -----
    # Sutra blocks are DEFERRED to pass 1.5: a false fragment anchor inside
    # the teacher's modern-Chinese retelling would advance the cursor past
    # the true positions of following paragraphs (observed cascade).
    cursor = 0
    last_pos = -1

    def try_anchor_commentary(idx, norm, cur, lastp, tag="dtw",
                              jf_char_min=0, hi_pos=None):
        """Sequential commentary anchoring; updates results/anchor_pos.
        Returns True when anchored. `jf_char_min` (optional) forbids the
        DTW path from consuming pattern chars before that char index;
        `hi_pos` (optional) bounds the search from above."""
        cands = []
        for ndl in head_needles(norm):
            hit = find_anchor(ndl, stream_norm, cur, py_stream, norm2py,
                              scan_norm=SCAN_LIMIT)
            if hit:
                cands.extend(hit)
        cands = [c for c in cands if c[1] > lastp]
        if hi_pos is not None:
            cands = [c for c in cands if c[1] < hi_pos]
        if not cands:
            return False
        # dedupe by pos, keep best score, top 3
        seen = {}
        for score, pos in cands:
            if pos not in seen or score > seen[pos]:
                seen[pos] = score
        cands = sorted(((s, p) for p, s in seen.items()),
                       key=lambda t: (-t[0], t[1]))[:3]
        best = eval_candidates(idx, norm, cands, jf_char_min=jf_char_min,
                               earliest=True)
        if best is None:
            return False
        d_norm, t_start, jf_char, jl_char, exact = best
        if d_norm < 0.5:
            if verbose:
                print(f"    [weak] p{idx} dtw={d_norm:.2f} "
                      f"cand={[f'{s:.2f}@{p}' for s, p in cands]}")
            return False
        anchor(idx, norm, t_start, d_norm, exact, tag,
               t_end=_t_of(times, jl_char),
               pat_len=min(HEAD_DTW, len(norm)))
        pos_jf = max(0, int(np.searchsorted(idx_map, jf_char,
                                            side="right")) - 1)
        pos_jl = max(0, int(np.searchsorted(idx_map, jl_char,
                                            side="right")) - 1)
        anchor_pos[idx] = (pos_jf, max(4, pos_jl - pos_jf))
        return True

    preludes = set()
    for idx, norm in enumerate(para_norms):
        if len(norm) < 3:
            continue
        if idx == 0 and is_sutra[idx]:
            # Resolve the head read first so its position bounds the prelude
            # search: episode-intro lines are spoken BEFORE/AT the head read
            # (ebook text order inverts audio order here), while real
            # commentary starts after it.
            head_anchored = try_head_sutra(idx, norm)
            head_pos = (anchor_pos[idx][0]
                        if head_anchored and idx in anchor_pos else None)
            for j in range(idx + 1, min(idx + 24, len(para_norms))):
                if is_sutra[j]:
                    continue  # verse run between head and the intro
                nj = para_norms[j]
                if len(nj) >= 3 and try_anchor_commentary(
                        j, nj, 0, -1, hi_pos=head_pos):
                    preludes.add(j)
                    pos, ndl_len = anchor_pos[j]
                    last_pos = max(last_pos, pos)
                    cursor = max(cursor, pos + max(ndl_len, 4))
                else:
                    break
            # HEAD-YIELD: when the head read is only PARTIAL (title/first
            # sentence) and a later sutra paragraph duplicates the head's
            # text, the duplicate claims the read in its own gap and the
            # head block becomes a zero-width marker at the prelude (the
            # ebook split one quote into two entries).
            dup = None
            if head_anchored and results[idx].get("method") == "dtw-frag":
                cmt = 0
                for j in range(idx + 1, min(idx + 30, len(para_norms))):
                    if is_sutra[j]:
                        if para_norms[j][:24] == norm[:24]:
                            dup = j
                            break
                    else:
                        cmt += 1
                        if cmt > 1:
                            break
            if dup is not None:
                if preludes:
                    t0 = round(min(results[k]["start"] for k in preludes), 3)
                else:
                    t0 = results[idx]["start"]
                results[idx] = {"start": t0, "end": t0, "conf": 0.85,
                                "method": "skipped-sutra"}
                anchor_pos.pop(idx, None)
                if verbose:
                    print(f"    [sutra-head] p{idx} YIELD to p{dup} @{t0:.1f}")
            elif head_anchored:
                pos, ndl_len = anchor_pos[idx]
                last_pos = pos
                cursor = pos + max(ndl_len, 4)
            continue
        if is_sutra[idx]:
            continue  # resolved in pass 1.5
        if try_anchor_commentary(idx, norm, cursor, last_pos):
            pos, ndl_len = anchor_pos[idx]
            last_pos = pos
            cursor = pos + max(ndl_len, 4)

    # ------------- pass 1.5: resolve sutra blocks within gaps -------------
    def resolve_sutra(idx, norm, lo_override=None):
        lo_pos, hi_pos = 0, len(stream_norm)
        if lo_override is not None:
            lo_pos = max(lo_pos, lo_override)
        for a, (p, l) in anchor_pos.items():
            if a < idx:
                lo_pos = max(lo_pos, p + l)
            elif a > idx:
                hi_pos = min(hi_pos, p)
        pat_len = min(len(norm), SUTRA_DTW_MAX)
        pat = list(norm[:pat_len])
        c_lo = (int(idx_map[min(lo_pos, len(idx_map) - 1)])
                if lo_pos < len(idx_map) else n_total - 1)
        if hi_pos <= lo_pos + 4:
            # degenerate gap (usually a head block whose text temporally
            # follows the next paragraph's start): use a pattern-sized window
            c_hi = min(n_total, c_lo + 2 * pat_len + 80)
        else:
            c_hi = int(idx_map[min(hi_pos + pat_len // 2,
                                   len(idx_map) - 1)])
        win = chars[c_lo:c_hi]
        d_full = 0.0
        if len(win) >= max(10, len(pat) // 3):
            d_score, jf, jl = dtw_span(pat, win)
            d_full = d_score / max(1, len(pat))
            span_s = (_t_of(times, c_lo + jl) - _t_of(times, c_lo + jf)
                      ) if jf >= 0 else -1.0
            rate = pat_len / span_s if span_s > 0.5 else 99.0
            if d_full >= SUTRA_COV_MIN and 1.0 <= rate <= 12.0:
                anchor(idx, norm, _t_of(times, c_lo + jf), d_full, False,
                       "dtw", t_end=_t_of(times, c_lo + jl),
                       force_end_fix=(pat_len == len(norm)))
                # in-bounds DTW placement is positional proof: floor the
                # conf (ASR garbling grades the text score, not the place)
                if results[idx]["conf"] < 0.86:
                    results[idx]["conf"] = 0.86
                p_jf = max(0, int(np.searchsorted(idx_map, c_lo + jf,
                                                  side="right")) - 1)
                p_jl = max(0, int(np.searchsorted(idx_map, c_lo + jl,
                                                  side="right")) - 1)
                anchor_pos[idx] = (p_jf, max(4, p_jl - p_jf))
                if verbose:
                    print(f"    [sutra] p{idx} READ d={d_full:.2f} "
                          f"t={_t_of(times, c_lo + jf):.1f} "
                          f"gap=[{lo_pos},{hi_pos}]")
                return
        frag = anchor_sutra_fragments(idx, norm, lo_pos, hi_pos)
        if frag is not None:
            t_start, d_norm, p_jf, p_jl = frag
            # fragment start confirmed; refine the read end with a full-block
            # DTW from the fragment (the read may continue past the 10-char
            # chunk even when a contiguous full-block anchor failed)
            t_end = None
            c_jf = int(idx_map[min(p_jf, len(idx_map) - 1)])
            win2 = chars[c_jf:min(n_total, c_jf + 2 * pat_len + 120)]
            if len(win2) >= 12:
                d2, _jf2, jl2 = dtw_span(pat, win2)
                if d2 / max(1, pat_len) >= 0.5:
                    t_end = _t_of(times, c_jf + jl2)
            if t_end is None:
                # fall back to the end of the verified fragment itself
                c_jl = int(idx_map[min(p_jl, len(idx_map) - 1)])
                t_end = _t_of(times, min(c_jl + 1, n_total - 1))
            anchor(idx, norm, t_start, d_norm, False, "dtw-frag",
                   t_end=t_end)
            # span covers the whole verse: a following commentary anchored
            # inside it is matching the verse's words and must be redone
            anchor_pos[idx] = (p_jf, max(len(norm), p_jl - p_jf))
            if verbose:
                print(f"    [sutra] p{idx} READ-frag d={d_norm:.2f} "
                      f"t_end={t_end}")
            return
        # 3. whole-stream scan: the read may sit outside the bracketing gap
        # (neighbor anchored late / before the lecture's first anchor).
        # Reject reads overlapping any other paragraph's anchored span.
        best_d = 0.0
        reads = []  # (d, t0, t1, p_jf, p_jl)
        step = max(15, pat_len // 3)
        min_win = max(12, int(pat_len * 0.6))
        w_lo = 0
        while w_lo + min_win < n_total:
            win = chars[w_lo:min(n_total, w_lo + pat_len * 2)]
            if len(win) < 12:
                break
            d_score, jf, jl = dtw_span(pat, win)
            d_norm = d_score / max(1, pat_len)
            best_d = max(best_d, d_norm)
            if d_norm >= 0.55:
                p_jf = max(0, int(np.searchsorted(idx_map, w_lo + jf,
                                                  side="right")) - 1)
                p_jl = max(0, int(np.searchsorted(idx_map, w_lo + jl,
                                                  side="right")) - 1)
                # reject only reads sitting DEEP inside another paragraph's
                # span; slight tail overlap with the previous commentary is
                # natural (the verse read continues out of it)
                clash = False
                for a, (p, l) in anchor_pos.items():
                    if a == idx:
                        continue
                    ov = min(p_jl, p + l) - max(p_jf, p)
                    if ov > 15:
                        clash = True
                        break
                if not clash:
                    reads.append((d_norm, _t_of(times, w_lo + jf),
                                  _t_of(times, w_lo + jl), p_jf, p_jl))
                w_lo = w_lo + jl + max(10, pat_len // 3)
            else:
                w_lo += step
        if reads:
            in_gap = lambda r: lo_pos <= r[3] < hi_pos
            reads.sort(key=lambda r: (not in_gap(r), -r[0]))
            d_best, t0, t1, p_jf, p_jl = reads[0]
            if not in_gap(reads[0]):
                # An out-of-gap hit is usually a paraphrase that SHARES the
                # verse's syllables, or a read spoken out of text order —
                # accepting it wrecks the ordered chain. Accept only when
                # order-consistent with the anchored neighbours.
                prev_starts = [p for a, (p, _l) in anchor_pos.items()
                               if a < idx]
                next_ps = [p for a, (p, _l) in anchor_pos.items() if a > idx]
                ok_order = ((not prev_starts or p_jf >= max(prev_starts) - 30)
                            and (not next_ps or p_jf <= min(next_ps) + 300))
                if not ok_order:
                    reads = []
        if reads:
            d_best, t0, t1, p_jf, p_jl = reads[0]
            results[idx] = {
                "start": round(max(0.0, t0 - LEAD_BACK), 3),
                "end": round(t1, 3),
                "conf": _conf_of(d_best, False),
                "method": "dtw-scan", "end_fixed": True}
            anchor_pos[idx] = (p_jf, max(4, p_jl - p_jf))
            if verbose:
                print(f"    [sutra] p{idx} READ-scan d={d_best:.2f} "
                      f"t={t0:.1f} gap=[{lo_pos},{hi_pos}]")
            return
        # 4. genuinely skipped; conf reflects the best coverage anywhere
        t0 = _t_of(times, c_lo) if lo_pos < len(idx_map) else 0.0
        skip_conf = 0.95 if best_d < 0.45 else (0.75 if best_d < 0.55
                                                else 0.55)
        results[idx] = {"start": round(t0, 3), "end": round(t0, 3),
                        "conf": skip_conf,
                        "method": "skipped-sutra"}
        if verbose:
            print(f"    [sutra] p{idx} skipped d={d_full:.2f} "
                  f"scan={best_d:.2f}")

    # Resolve exact verse blocks BEFORE the lecture-head full-chapter block:
    # the head text subsumes mid-lecture verses, and if the head block were
    # resolved first its whole-stream scan would steal the verse's read (the
    # verse paragraph then gets clash-rejected into a bogus "skipped").
    sutra_todo = [i for i, n_ in enumerate(para_norms)
                  if is_sutra[i] and len(n_) >= 3]
    sutra_todo.sort(key=lambda i: (i == 0, i))
    for idx in sutra_todo:
        if results[idx] is None:
            resolve_sutra(idx, para_norms[idx])

    # Re-anchor commentaries whose head DTW landed inside a *read* sutra
    # block: classic/pattern verse shares syllables with the teacher's
    # modern retelling (e.g. 世尊教敕一一开悟… vs 世尊教了之后都开悟了…),
    # so a commentary needle can "match" the spoken verse. Retry after the
    # sutra spans are known, forcing the search past the block.
    sutra_reads = []
    for i, r in enumerate(results):
        if is_sutra[i] and r is not None and r["method"] in (
                "dtw", "dtw2", "dtw-frag", "dtw-scan"):
            p, l = anchor_pos[i]
            sutra_reads.append((i, p, p + max(l, 4), r["start"]))
    for idx, norm in enumerate(para_norms):
        if is_sutra[idx] or results[idx] is None:
            continue
        if results[idx]["method"] not in (
                "dtw", "dtw2", "dtw-frag", "dtw-scan"):
            continue
        jf = anchor_pos[idx][0]
        for _si, s_lo, s_hi, s_t in sutra_reads:
            if s_lo <= jf < s_hi:
                # CHALLENGE, not overwrite: a paragraph whose text IS the
                # next lines of the same quote anchors legitimately inside
                # the read (idx22-style), while a commentary needle that
                # matched the verse words scores worse on its full pattern
                # at the read than at its true position. Re-anchor past the
                # read and keep whichever full-pattern score is higher.
                if verbose:
                    print(f"    [redo?] p{idx} inside sutra p{_si} "
                          f"[{s_lo},{s_hi})")
                lastp = -1
                for a, (p, l) in sorted(anchor_pos.items()):
                    if a < idx and p + l <= s_lo:
                        lastp = max(lastp, p)
                jf_min_char = (int(idx_map[min(s_hi, len(idx_map) - 1)])
                               if s_hi < len(idx_map) else n_total)
                old_r = dict(results[idx])
                old_ap = anchor_pos.get(idx)
                redone = try_anchor_commentary(idx, norm, s_hi, lastp,
                                               tag="dtw",
                                               jf_char_min=jf_min_char)
                if redone:
                    new_conf = results[idx]["conf"]
                    if new_conf < old_r["conf"] - 0.05:
                        # the read matched better: keep the original anchor
                        results[idx] = old_r
                        if old_ap is not None:
                            anchor_pos[idx] = old_ap
                        if verbose:
                            print(f"    [redo] p{idx} kept original "
                                  f"conf={old_r['conf']:.2f} "
                                  f"> past-read {new_conf:.2f}")
                    else:
                        if verbose:
                            print(f"    [redo] p{idx} moved past read "
                                  f"conf={new_conf:.2f}")
                        pos, ndl_len = anchor_pos[idx]
                        last_pos = max(last_pos, pos)
                        cursor = max(cursor, pos + ndl_len)
                else:
                    results[idx] = old_r
                    if old_ap is not None:
                        anchor_pos[idx] = old_ap
                break

    # ---------------- pass 2: converge misses between neighbors ----------
    anchored_sorted = sorted(anchor_pos)
    for idx, norm in enumerate(para_norms):
        if results[idx] is not None or len(norm) < 3:
            continue
        prevs = [a for a in anchored_sorted if a < idx]
        nexts = [a for a in anchored_sorted if a > idx]
        lo = (anchor_pos[prevs[-1]][0] + anchor_pos[prevs[-1]][1]
              if prevs else 0)
        hi = anchor_pos[nexts[0]][0] if nexts else len(stream_norm)
        if hi - lo < 8:
            continue
        pat_len = (min(len(norm), SUTRA_DTW_MAX) if is_sutra[idx]
                   else min(HEAD_DTW, len(norm)))
        pat = list(norm[:pat_len])
        c_lo = int(idx_map[min(lo, len(idx_map) - 1)])
        c_hi = int(idx_map[min(hi + pat_len + 40, len(idx_map) - 1)])
        win = chars[c_lo:c_hi]
        if len(win) < max(10, len(pat) // 2):
            continue
        d_score, jf, jl = dtw_span(pat, win)
        d_norm = d_score / max(1, len(pat))
        if is_sutra[idx]:
            if d_norm >= SUTRA_COV_MIN:
                anchor(idx, norm, _t_of(times, c_lo + jf), d_norm, False,
                       "dtw2", t_end=_t_of(times, c_lo + jl),
                       force_end_fix=(pat_len == len(norm)))
                pos = int(np.searchsorted(
                    idx_map, c_lo + jf, side="right")) - 1
                anchor_pos[idx] = (pos, 4)
                anchored_sorted = sorted(anchor_pos)
                if verbose:
                    print(f"    [pass2-sutra] p{idx} READ d={d_norm:.2f}")
            else:
                results[idx] = {"start": 0.0, "end": 0.0,
                                "conf": _sutra_skip_conf(d_norm),
                                "method": "skipped-sutra"}
                if verbose:
                    print(f"    [pass2-sutra] p{idx} skipped d={d_norm:.2f}")
        elif d_norm >= 0.55:
            anchor(idx, norm, _t_of(times, c_lo + jf), d_norm * 0.92, False,
                   "dtw2", t_end=_t_of(times, c_lo + jl),
                   pat_len=min(HEAD_DTW, len(norm)))
            pos = int(np.searchsorted(idx_map, c_lo + jf, side="right")) - 1
            anchor_pos[idx] = (pos, 4)
            anchored_sorted = sorted(anchor_pos)
            if verbose:
                print(f"    [pass2] p{idx} d={d_norm:.2f}")

    # ------------- ordered reconciliation -------------------------------
    # Window padding lets a head pattern match inside the PREVIOUS
    # paragraph's text; consecutive anchors can then stack at the same
    # timestamp (zero-width reads). Re-anchor any violation inside the gap
    # bounded by its predecessor's spoken span and the next anchor.
    TIMED = ("dtw", "dtw2", "dtw-frag", "dtw-scan", "dtw-evid")
    order = [i for i, r in enumerate(results)
             if r is not None and r["method"] in TIMED and i in anchor_pos]
    for k, idx in enumerate(order):
        if k == 0:
            continue
        if idx in preludes:
            continue  # intro-before-head-read inversion is expected
        prev = order[k - 1]
        if prev not in anchor_pos:
            # prev was a sutra block demoted to skipped-sutra during this
            # loop (its territory was popped): nothing to reconcile against
            continue
        prev_end_pos = (anchor_pos[prev][0] + anchor_pos[prev][1])
        prev_end_t = None
        if results[prev].get("end_fixed"):
            prev_end_t = results[prev]["end"]
        bad = results[idx]["start"] <= results[prev]["start"] + 0.05 or (
            prev_end_t is not None
            and results[idx]["start"] < prev_end_t - 0.3)
        if not bad:
            continue
        if verbose:
            print(f"    [reconcile] p{idx} @{results[idx]['start']:.1f} "
                  f"vs prev p{prev} end@{prev_end_t}")
        nxt = order[k + 1] if k + 1 < len(order) else None
        hi_pos = anchor_pos[nxt][0] if nxt is not None else None
        if is_sutra[idx]:
            results[idx] = None
            anchor_pos.pop(idx, None)
            resolve_sutra(idx, para_norms[idx], lo_override=prev_end_pos)
        else:
            jf_min_char = (int(idx_map[min(prev_end_pos, len(idx_map) - 1)])
                           if prev_end_pos < len(idx_map) else n_total)
            ok = try_anchor_commentary(idx, para_norms[idx], prev_end_pos,
                                       prev_end_pos - 1, tag="dtw",
                                       jf_char_min=jf_min_char,
                                       hi_pos=hi_pos)
            if not ok:
                if results[idx]["method"] == "interp":
                    t0 = prev_end_t if prev_end_t is not None \
                        else results[prev]["start"]
                    results[idx] = {"start": round(t0, 3), "end": round(t0, 3),
                                    "conf": 0.6, "method": "interp"}
                    if verbose:
                        print(f"    [reconcile] p{idx} -> interp @{t0:.1f}")
                # else: keep the original evidence-based anchor — its slight
                # overlap with the predecessor is real speech (e.g. the next
                # paragraph starts while the previous quote is still echoing)

    # ---------------- boundary chaining & gap filling ---------------------
    # Anchored paragraphs (any class) delimit gaps. Interpolation weight is
    # the normalized text length, EXCEPT skipped-sutra blocks take zero
    # share (not spoken → zero-width at the boundary they fall on).
    # When the gap-opening anchor's END is evidence-fixed, the interpolated
    # run starts exactly at that end (the read is pinned to the millisecond;
    # reserving the predecessor's text share would push the first
    # interpolated paragraph seconds late).
    anchored = [i for i, r in enumerate(results) if r is not None]
    prev_a = -1
    for a in anchored + [len(results)]:
        if a - prev_a > 1:
            lo_t = 0.0
            if prev_a >= 0:
                lo_t = results[prev_a].get("end")
                if lo_t is None:
                    lo_t = results[prev_a]["start"]
            hi_t = results[a]["start"] if a < len(results) else (
                duration or (lo_t + 60.0))
            span = list(range(prev_a + 1, a))
            lens = [0 if is_sutra[k] else max(4, len(para_norms[k]))
                    for k in span]
            prev_fixed = (prev_a >= 0
                          and results[prev_a].get("end") is not None
                          and results[prev_a].get("end_fixed"))
            if prev_a >= 0 and not prev_fixed:
                # reserve the anchor paragraph's own share so it keeps a
                # non-zero width (its spoken length is unknown, estimate
                # by text)
                lens.insert(0, max(4, len(para_norms[prev_a])))
            total = sum(lens)
            if total == 0:
                # all skipped: stack zero-width at the gap start
                for k in span:
                    results[k] = {"start": round(lo_t, 3),
                                  "end": round(lo_t, 3),
                                  "conf": 0.5, "method": "skipped-sutra"}
            else:
                acc = 0
                for k, w in zip(span, lens):
                    t0 = lo_t + (hi_t - lo_t) * (acc / total)
                    t1 = lo_t + (hi_t - lo_t) * ((acc + w) / total)
                    if is_sutra[k]:
                        results[k] = {"start": round(t0, 3),
                                      "end": round(t0, 3),
                                      "conf": 0.5, "method": "skipped-sutra"}
                    else:
                        results[k] = {"start": round(t0, 3),
                                      "end": round(t1, 3),
                                      "conf": _interp_conf(lo_t, hi_t),
                                      "method": "interp"}
                    acc += w
        prev_a = a

    for i in range(len(results) - 1):
        # skipped-sutra markers stay zero-width: the unspoken text must not
        # stretch over the following commentary (the player highlights by
        # time window and would light it up wrongly)
        if results[i].get("end_fixed"):
            # evidence end wins over chaining when chaining would truncate
            # the read (next anchor is a skip/interp marker placed at this
            # paragraph's own start)
            ev = results[i].get("_ev_end")
            if ev is not None:
                results[i]["end"] = round(max(results[i + 1]["start"], ev), 3)
            continue
        if results[i]["method"] == "skipped-sutra":
            continue
        results[i]["end"] = results[i + 1]["start"]
    # end_fixed chaining can zero out the following paragraphs when a short
    # read is spoken twice (idx0 verse-title read = idx2 verse repeat): only
    # entries that START after the fixed end may be clamped into it.
    for i in range(len(results) - 1):
        if not results[i].get("end_fixed"):
            continue
        t_end = results[i]["end"]
        j = i + 1
        while j < len(results) and results[j]["start"] < t_end - 0.05:
            if results[j]["start"] < results[i]["start"] - 0.05:
                j += 1  # starts before this read: prelude inversion, not inside
                continue
            j_end = results[j].get("end")
            if (results[j].get("end_fixed") and j_end is not None
                    and j_end > t_end + 0.05):
                j += 1
                continue
            if j_end is not None and j_end <= t_end + 0.05:
                results[j] = {"start": round(t_end, 3), "end": round(t_end, 3),
                              "conf": results[j]["conf"],
                              "method": "subsumed-dup"}
            else:
                results[j]["start"] = round(t_end, 3)
                if j_end is None:
                    results[j]["end"] = round(t_end, 3)
            j += 1
    # A timed read followed by zero-width markers (skipped-sutra placed at
    # the read's own start, interp) gets truncated to zero width by pure
    # chaining — but those markers sit INSIDE the read's own speech span.
    # Restore the read's width (evidence end when known, else up to the next
    # real entry), leaving the markers zero-width.
    for i in range(len(results) - 1):
        r = results[i]
        if r["method"] not in ("dtw", "dtw2", "dtw-frag", "dtw-scan",
                               "dtw-evid"):
            continue
        if r["end"] > r["start"] + 0.3:
            continue
        j = i + 1
        while (j < len(results)
               and results[j]["method"] in ("skipped-sutra", "interp",
                                            "subsumed-dup")
               and results[j]["end"] <= results[j]["start"] + 0.3
               and results[j]["start"] <= r["start"] + 0.3):
            j += 1
        if j == i + 1:
            continue
        ev = r.get("_ev_end")
        nxt = (results[j]["start"] if j < len(results)
               else (duration or r["start"] + 15.0))
        if ev is not None:
            new_end = max(r["start"] + 0.5, min(ev, nxt))
        else:
            new_end = max(r["start"] + 0.5, min(nxt, r["start"] + 15.0))
            # --- tail end-recovery (毫秒級): the chaining above zeroed this
            # read because the next marker was placed at its own start.
            # Reconstruct the true end from the paragraph's TAIL: verbatim
            # match (16/12/8 chars) of the tail inside [start, nxt+pad),
            # pinyin fallback. The last char's timestamp IS the millisecond
            # moment the final word is spoken.
            try:
                norm_r = para_norms[i]
                c_lo0 = int(np.searchsorted(t_starts, r["start"],
                                            side="left"))
                c_hi0 = min(n_total,
                            int(np.searchsorted(t_starts, nxt, side="left"))
                            + 160)
                pos0 = (int(np.searchsorted(idx_map, c_lo0))
                        if c_lo0 < len(idx_map) else len(stream_norm))
                end0 = (int(np.searchsorted(idx_map, c_hi0 - 1)) + 1) \
                    if c_hi0 > c_lo0 else len(stream_norm)
                pos0 = min(pos0, len(stream_norm))
                end0 = min(max(end0, pos0), len(stream_norm))
                found = None
                for L in (16, 12, 8):
                    tail = norm_r[max(0, len(norm_r) - L):]
                    if len(tail) < 6:
                        break
                    p = stream_norm.find(tail, pos0, end0)
                    if p >= 0:
                        found = p + len(tail) - 1
                        break
                if found is None and len(norm_r) >= 12:
                    tp = py_string(norm_r[-12:])
                    q_lo = int(norm2py[pos0]) if pos0 < len(norm2py) else 0
                    q_hi = (int(norm2py[end0]) if end0 < len(stream_norm)
                            else len(py_stream))
                    q = py_stream.find(tp, q_lo, max(q_hi, q_lo))
                    if q >= 0:
                        found = int(np.searchsorted(norm2py, q + len(tp),
                                                    side="left")) - 1
                if found is not None and 0 <= found < len(idx_map):
                    t_end2 = _t_of(times, int(idx_map[found]))
                    if nxt - r["start"] > 5.0:
                        t_cap = nxt + 0.5      # real next paragraph start
                    else:
                        t_cap = r["start"] + 90.0   # zero-width marker
                    if r["start"] + 0.5 <= t_end2 <= t_cap:
                        new_end = t_end2
                        if verbose:
                            print(f"    [tail-end] p{i} "
                                  f"{r['start']:.1f}->{new_end:.1f}")
            except Exception:
                pass
        r["end"] = round(new_end, 3)
    def chain_all():
        """End-chaining + monotonic clamp (re-runnable after late moves)."""
        for i in range(len(results) - 1):
            if results[i].get("end") is None:
                results[i]["end"] = results[i + 1]["start"]
        if results:
            results[-1]["end"] = (round(duration, 3) if duration
                                  else results[-1]["start"])
        last_t = 0.0
        for r in results:
            r["start"] = max(r["start"], last_t)
            if r["end"] < r["start"]:
                r["end"] = r["start"]
            last_t = r["end"]

    chain_all()

    # ---------------- head-verification repair ---------------------------
    # A commentary anchor whose head text does NOT verify inside its own
    # window but verifies strongly elsewhere is a late chain anchor (the
    # predecessor's span/territory swallowed the true start). Runs BEFORE
    # the final monotonic clamp, in sweeps: a corrected anchor lowers the
    # bound for earlier ones, and cascade chains need multiple passes.
    t_starts = [tt[0] for tt in times]

    def next_timed_start(i):
        for j in range(i + 1, len(results)):
            rj = results[j]
            if rj is not None and rj["method"] in TIMED:
                return rj["start"]
        return duration or (results[i]["start"] + 30.0)

    def prev_timed(i):
        for j in range(i - 1, -1, -1):
            rj = results[j]
            if rj is not None and rj["method"] in TIMED:
                return j
        return -1

    def repair_one(i, r):
        norm_head = para_norms[i][:30]
        if len(norm_head) < 12:
            return False
        hi_t = next_timed_start(i)
        lo_c = next((c for c in range(len(chars))
                     if times[c][0] >= r["start"] - 0.5), 0)
        hi_c = next((c for c in range(len(chars))
                     if times[c][0] >= hi_t + 0.5), len(chars))
        win = chars[lo_c:hi_c]
        if len(win) < 10:
            return False
        d_chk, jf_chk, _jl = dtw_span(list(norm_head), win)
        d_chk_n = d_chk / max(1, len(norm_head))
        pj0 = prev_timed(i)
        lo_bound0 = results[pj0]["start"] + 0.1 if pj0 >= 0 else 0.0
        if d_chk_n >= 0.35 and (hi_t - r["start"]) >= 25.0:
            # Head IS in the window but may sit deep inside it (a digression
            # between the previous paragraph and this one got absorbed).
            # Tighten the start to where the head's speech actually begins.
            t_head = _t_of(times, lo_c + jf_chk)
            if t_head - r["start"] <= 10.0:
                # DTW's free skip-in may pin the head at the window start
                # (syllable soup) while the real occurrence sits later. A
                # pattern is spoken once: if an equally strong alignment
                # exists 12s+ later, that later one is the true start.
                c_late = next((c for c in range(len(chars))
                               if times[c][0] >= t_head + 12.0
                               and times[c][0] < hi_t), None)
                if c_late is not None:
                    win3 = chars[c_late:hi_c]
                    if len(win3) >= 12:
                        d3, jf3, _x3 = dtw_span(list(norm_head), win3)
                        d3_n = d3 / max(1, len(norm_head))
                        t3 = _t_of(times, c_late + jf3)
                        if (jf3 >= 0 and d3_n >= d_chk_n - 0.12
                                and t3 - r["start"] > 10.0
                                and lo_bound0 <= t3 < hi_t - 0.5):
                            t_head = t3
            if t_head - r["start"] > 10.0 and lo_bound0 <= t_head \
                    < hi_t - 0.5:
                if verbose:
                    print(f"    [tighten] p{i} {r['start']:.1f} -> "
                          f"{t_head:.1f} d={d_chk_n:.2f}")
                r["start"] = round(max(0.0, t_head - LEAD_BACK), 3)
                c_th = int(np.searchsorted(t_starts, r["start"],
                                           side="left"))
                pos_th = int(np.searchsorted(idx_map, c_th)) \
                    if c_th < len(idx_map) else 0
                if i in anchor_pos:
                    anchor_pos[i] = (pos_th, max(4, anchor_pos[i][1]))
                else:
                    anchor_pos[i] = (pos_th, 8)
                if pj0 >= 0 and results[pj0].get("end_fixed") \
                        and results[pj0]["end"] > t_head:
                    results[pj0]["end"] = round(t_head, 3)
                return True
            return False
        if d_chk_n >= 0.3:
            return False
        pl = len(norm_head)
        best_d, best_c = 0.0, -1
        w = 0
        while w + max(12, pl // 2) < n_total:
            win2 = chars[w:min(n_total, w + 2 * pl)]
            d2, jf2, _jl2 = dtw_span(list(norm_head), win2)
            if d2 / pl > best_d:
                best_d, best_c = d2 / pl, w + jf2
            w += 15
        if best_d < 0.5 or best_c < 0:
            return False
        t_new = _t_of(times, best_c)
        if abs(t_new - r["start"]) <= 8.0:
            return False
        pj = prev_timed(i)
        lo_bound = results[pj]["start"] + 0.1 if pj >= 0 else 0.0
        if t_new < lo_bound or t_new >= hi_t - 0.5:
            return False
        if verbose:
            print(f"    [repair] p{i} {r['start']:.1f} -> {t_new:.1f} "
                  f"d={best_d:.2f}")
        r["start"] = round(max(0.0, t_new - LEAD_BACK), 3)
        # a relocation is positional evidence: never LOWER an earlier
        # evidence-based conf (e.g. place_from_fragments' 0.84)
        r["conf"] = max(r.get("conf", 0.0), _conf_of(best_d, False))
        # keep anchor_pos in sync with the moved start (stale positions
        # poison the positional bounds of later sweeps)
        c_new = int(np.searchsorted(t_starts, r["start"], side="left"))
        pos_new = int(np.searchsorted(idx_map, c_new)) \
            if c_new < len(idx_map) else 0
        if i in anchor_pos:
            anchor_pos[i] = (pos_new, max(4, anchor_pos[i][1]))
        else:
            anchor_pos[i] = (pos_new, 8)
        # cap a predecessor whose generous read span swallowed this start
        if pj >= 0 and results[pj].get("end_fixed") \
                and results[pj]["end"] > t_new + 6.0:
            results[pj]["end"] = round(t_new, 3)
        return True

    for _sweep in range(3):
        changed = False
        for i, r in enumerate(results):
            if r is None or r["method"] not in ("dtw", "dtw2"):
                continue
            if repair_one(i, r):
                changed = True
        if not changed:
            break

    # ---------------- evidence pass (夾逼 re-verify) ----------------------
    # Goal: every paragraph ends with conf >= 0.8 that reflects *positional*
    # evidence (span verified against the dump), not only DTW text score.
    # ASR garbling caps the per-char DTW score around 0.7 even for a correct
    # span, so text score alone cannot separate correct from wrong.  Instead
    # each paragraph is re-verified INDEPENDENTLY (in sweeps, since a
    # corrected neighbour tightens the bounds):
    #   1. bounded re-anchor (夾逼): full-pattern DTW inside [prev_anch_end,
    #      next_anchor). A strong find (>= 0.62) replaces the entry: position
    #      is trustworthy even when the text score is capped by garbling.
    #   2. start snap: when the verbatim head occurs EXACTLY in the stream
    #      within the lookback window, the start is pinned to its timestamp.
    #   3. whole-stream sutra probe: a skipped-sutra marker below 0.8 is
    #      probed over the WHOLE dump. cov >= 0.55 and order-consistent ->
    #      read aloud (re-anchored); else -> skipped with conf graded by the
    #      no-read evidence. 念誦與否兩種情況都以證據定案。
    #   4. dual position confirmation: a timed anchor is accepted (conf
    #      >= 0.85) when head-at-start AND block-in-span both hold with no
    #      conflicting occurrence; a wrong start is re-anchored in bounds.
    #   5. anything still unverified keeps a modest conf (0.72) for human
    #      review; the final chaining + repair sweep then runs again.
    READ_COV = 0.55
    SPAN_HEAD = 0.7
    SPAN_BLOCK = 0.55

    t_starts = [tt[0] for tt in times]
    from bisect import bisect_left as _bl

    def span_head_score(i, r):
        """Head needle DTW inside the paragraph's own span window."""
        norm = para_norms[i]
        head = norm[:min(24, len(norm))]
        if len(head) < 6 or r["start"] is None or r["end"] is None:
            return 0.0, None, 0.0
        c_lo = _bl(t_starts, r["start"] - 1.0)
        c_hi = _bl(t_starts, r["end"] + 1.0)
        c_lo = max(0, min(c_lo, n_total - 1))
        c_hi = max(c_lo, min(c_hi, n_total))
        if c_hi - c_lo < max(6, len(head) // 2):
            c_lo = max(0, c_lo - 30)
            c_hi = min(n_total, c_lo + 60)
        win = chars[c_lo:c_hi]
        if not win:
            return 0.0, None, 0.0
        d, jf, _jl = dtw_span(list(head), win)
        t_head = _t_of(times, c_lo + jf) if 0 <= jf < len(win) else None
        blk = norm[:min(SUTRA_DTW_MAX if is_sutra[i] else HEAD_DTW * 2,
                        len(norm))]
        db, _jf2, _jl2 = dtw_span(list(blk), win)
        return d / max(1, len(head)), t_head, db / max(1, len(blk))

    def multi_head_confirm(i, r, prev_end_t):
        """Garbling-tolerant positional confirmation: try 14-char head
        needles at offsets 0/8/16/24/32 INSIDE the span window (±2.5s).
        Confirmed when a needle (d >= 0.68, sane speech rate) starts at the
        span head, or sits fully inside the span (offset >= 8 → the verbatim
        head was garbled; the start then snaps back by the needle offset at
        the measured speech rate). Returns (new_start, d) or None."""
        norm = para_norms[i]
        if len(norm) < 8 or r["start"] is None or r["end"] is None:
            return None
        c_lo = _bl(t_starts, r["start"] - 2.5)
        c_hi = _bl(t_starts, r["end"] + 2.5)
        c_lo = max(0, min(c_lo, n_total - 1))
        c_hi = max(c_lo, min(c_hi, n_total))
        win = chars[c_lo:c_hi]
        if len(win) < 10:
            return None
        best = None
        for k in (0, 8, 16, 24, 32):
            if k >= len(norm) - 5:
                break
            ndl_len = min(14 if k else 8, len(norm) - k)
            if k == 0 and len(norm) >= 14:
                lengths = (14, 8)
            else:
                lengths = (min(14, len(norm) - k),)
            k0_best = None
            for L in lengths:
                ndl = norm[k:k + L]
                if len(ndl) < 6:
                    continue
                d, jf, jl = dtw_span(list(ndl), win)
                d_n = d / max(1, len(ndl))
                if jf < 0 or d_n < 0.68:
                    continue
                t_first = _t_of(times, c_lo + jf)
                t_last = _t_of(times, c_lo + jl)
                span_s = t_last - t_first
                rate = len(ndl) / span_s if span_s > 0.4 else 12.0
                if not 1.0 <= rate <= 12.0:
                    continue
                if best is None or d_n > best[1]:
                    best = (k, d_n, t_first, t_last, rate)
                if k0_best is None or d_n > k0_best:
                    k0_best = d_n
            if k == 0 and k0_best is not None and k0_best >= 0.7:
                break
        if best is None:
            return None
        k, d_n, t_first, t_last, rate = best
        near_head = abs(t_first - r["start"]) <= 2.0
        contained = (t_first >= r["start"] - 2.0
                     and t_last <= r["end"] + 2.0)
        short_para = len(norm) <= 14
        if not (near_head or (contained and (k >= 8 or short_para))):
            return None
        new_start = r["start"]
        if k >= 8 and t_first - k / max(1.0, min(rate, 6.0)) \
                > r["start"] + 0.3:
            lo_guard = (prev_end_t - 0.5) if prev_end_t is not None else 0.0
            t_snap = t_first - k / max(1.0, min(rate, 6.0))
            if t_snap >= lo_guard:
                new_start = round(max(0.0, t_snap - LEAD_BACK), 3)
        elif short_para and contained and not near_head:
            # the whole paragraph ≈ the needle: its garbled lead pushed the
            # match into the span; the read starts at the match
            lo_guard = (prev_end_t - 0.5) if prev_end_t is not None else 0.0
            if t_first >= lo_guard:
                new_start = round(max(0.0, t_first - LEAD_BACK), 3)
        return (new_start, d_n)

    def needle_scan_anchor(idx, lo_pos, hi_pos):
        """Multi-offset fragment scan inside [lo_pos, hi_pos): 14-char head
        needles at offsets 0/8/16/24/32, pinyin-fuzzy candidates + DTW
        verify. Anchors at the best hit (>= 0.72). Mid-offset needles are
        generic prose — they must be VERBATIM-UNIQUE across the whole
        stream, and their conf is capped at 0.82 (positional evidence
        weaker than a head match). Returns True on anchor."""
        norm = para_norms[idx]
        for k in (0, 8, 16, 24, 32):
            if k >= len(norm) - 5:
                break
            ndl = norm[k:k + min(14, len(norm) - k)]
            if len(ndl) < 6:
                continue
            cands = find_anchor(ndl, stream_norm, lo_pos, py_stream,
                                norm2py,
                                scan_norm=max(200, hi_pos - lo_pos + 500))
            cands = [c for c in cands if lo_pos <= c[1] < hi_pos]
            if not cands:
                continue
            if k > 0:
                # generic-text guard: the needle must occur exactly ONCE in
                # the whole stream, otherwise the match is ambiguous
                occ = stream_norm.count(ndl)
                q = py_stream.count(py_string(ndl))
                if occ > 1 or q > 1:
                    continue
            best = eval_candidates(idx, ndl, cands, pat=list(ndl))
            if best is None or best[0] < 0.72:
                continue
            d_n, t_st, jfc, jlc, _x = best
            # time-order guard: never anchor BEFORE the previous verified
            # paragraph's start or AFTER the next one (the needle may match
            # an earlier discussion of the same topic)
            bad_time = False
            for j in range(idx - 1, -1, -1):
                rj = results[j]
                if rj is not None and rj.get("conf", 0) >= 0.8:
                    if rj["start"] > 0 and t_st < rj["start"] - 0.5:
                        bad_time = True
                    break
            for j in range(idx + 1, len(results)):
                rj = results[j]
                if rj is not None and rj.get("conf", 0) >= 0.8:
                    if t_st > rj["start"] + 0.5:
                        bad_time = True
                    break
            if bad_time:
                continue
            anchor(idx, norm, t_st, min(d_n, 0.82) if k > 0 else d_n,
                   False, "dtw-evid",
                   t_end=_t_of(times, jlc), pat_len=len(ndl))
            # a verbatim-unique in-bounds hit is positional proof, not a
            # text-score grade: floor the conf at 0.86
            if results[idx]["conf"] < 0.86:
                results[idx]["conf"] = 0.86
            p_jf = max(0, int(np.searchsorted(idx_map, jfc,
                                              side="right")) - 1)
            p_jl = max(0, int(np.searchsorted(idx_map, jlc,
                                              side="right")) - 1)
            anchor_pos[idx] = (p_jf, max(4, p_jl - p_jf))
            if verbose:
                print(f"    [evid] p{idx} needle-scan k={k} d={d_n:.2f} "
                      f"t={results[idx]['start']:.1f}")
            return True
        return False

    def fragment_in_span(idx, lo_pos, hi_pos):
        """Deep-fragment confirmation: slide a 14-char needle across the
        WHOLE normalized text (stride 8); accept EXACT (pinyin/char) hits
        inside [lo_pos, hi_pos) that DTW-verify >= 0.8. Returns up to two
        hits [(off, pos, t_st, t_end)], or None."""
        norm = para_norms[idx]
        if len(norm) < 14 or hi_pos - lo_pos > 3000:
            return None
        hits = []
        for off in range(0, len(norm) - 13, 8):
            ndl = norm[off:off + 14]
            cands = find_anchor(ndl, stream_norm, lo_pos, py_stream,
                                norm2py,
                                scan_norm=max(200, hi_pos - lo_pos + 500))
            cands = [c for c in cands
                     if lo_pos <= c[1] < hi_pos and c[0] >= 0.92]
            if not cands:
                continue
            best = eval_candidates(idx, ndl, cands, pat=list(ndl))
            if best and best[0] >= 0.8:
                d_n, t_st, jfc, jlc, _x = best
                pos = max(0, int(np.searchsorted(idx_map, jfc,
                                                 side="right")) - 1)
                hits.append((off, pos, t_st, _t_of(times, jlc)))
                if len(hits) >= 2:
                    break
        return hits or None

    def effective_prev_end(j):
        """End of neighbour j's spoken content: if its span contains an
        internal char-less hole (> 4s of untranscribed audio — ASR drop /
        chant), the DTW end may have crossed it; use the pre-hole end."""
        rj = results[j]
        if rj.get("end") is None:
            return rj["start"]
        c_a = _bl(t_starts, rj["start"])
        c_b = _bl(t_starts, rj["end"])
        c_a = max(0, min(c_a, n_total - 2))
        c_b = min(max(c_b, c_a + 1), n_total - 1)
        for c in range(c_a, c_b):
            if t_starts[c + 1] - t_starts[c] > 4.0:
                return t_starts[c]
        return rj["end"]

    def timed_bounds(i):
        """Time hole of paragraph i between the nearest TIMED neighbours.
        Returns (lo_t, hi_t, lo_pos, hi_pos)."""
        prevs_t = [a for a in anchor_pos if a < i
                   and results[a]["method"] in TIMED]
        nexts_t = [a for a in anchor_pos if a > i
                   and results[a]["method"] in TIMED]
        lo_t = (effective_prev_end(prevs_t[-1]) if prevs_t
                else 0.0)
        hi_t = (results[nexts_t[0]]["start"] if nexts_t
                else (duration or (results[i]["start"] + 60.0)))
        c_lo = _bl(t_starts, lo_t)
        c_hi = _bl(t_starts, hi_t)
        lo_pos = (int(np.searchsorted(idx_map, c_lo))
                  if c_lo < len(idx_map) else len(stream_norm))
        hi_pos = (int(np.searchsorted(idx_map, c_hi))
                  if c_hi > c_lo and c_hi <= len(idx_map)
                  else len(stream_norm))
        return lo_t, hi_t, lo_pos, hi_pos

    def dtw_in_gap(idx, lo_t, hi_t, lo_pos, hi_pos):
        """Full-pattern DTW strictly INSIDE the unclaimed gap [lo_t, hi_t):
        never touches speech already claimed by verified TIMED anchors.
        Returns (t_start, t_end, d_norm) or None."""
        norm = para_norms[idx]
        if len(norm) < 6:
            return None
        pat = list(norm[:min(HEAD_DTW, len(norm))])
        c_lo = _bl(t_starts, lo_t - 0.2)
        c_hi = _bl(t_starts, hi_t + 0.2)
        c_lo = max(0, min(c_lo, n_total - 1))
        c_hi = max(c_lo, min(c_hi, n_total))
        if c_hi - c_lo < max(8, len(pat) // 3):
            return None
        win = chars[c_lo:c_hi]
        d, jf, jl = dtw_span(pat, win)
        d_n = d / max(1, len(pat))
        if jf < 0 or d_n < 0.42:
            return None
        t0 = _t_of(times, c_lo + jf)
        t1 = _t_of(times, c_lo + jl)
        span_s = t1 - t0
        if span_s > 0.5:
            rate = len(pat) / span_s
            if not 1.0 <= rate <= 12.0:
                return None
        if t1 - t0 > (hi_t - lo_t) + 20.0:
            return None
        return (round(max(0.0, t0 - LEAD_BACK), 3), round(t1, 3), d_n)

    def micro_fragment_confirm(idx, lo_pos, hi_pos, lo_t, hi_t):
        """Ordered micro-fragments: 4/6-char exact windows slid over the
        text, matched EXACTLY in [lo_pos, hi_pos). Confirmed when >= 4 hits
        align in reading order with a sane speech rate. Returns (t_start,
        n_hits) or None."""
        norm = para_norms[idx]
        if hi_pos <= lo_pos:
            return None
        hits = []
        last_pos = -10
        for L in (6, 4):
            for off in range(0, max(1, len(norm) - L + 1), 4):
                seg = norm[off:off + L]
                if len(seg) < L:
                    break
                p = stream_norm.find(seg, max(0, lo_pos), hi_pos)
                if p < 0:
                    continue
                if p >= last_pos + 2:
                    c_idx = int(idx_map[min(p, len(idx_map) - 1)])
                    t_hit = _t_of(times, c_idx)
                    if lo_t - 1.0 <= t_hit <= hi_t + 1.0:
                        hits.append((off, p, t_hit))
                        last_pos = p
            if len(hits) >= 4:
                break
        min_hits = 3 if len(norm) <= 60 else 4
        if len(hits) < min_hits:
            return None
        rate = ((hits[-1][0] - hits[0][0]) /
                max(0.5, hits[-1][2] - hits[0][2]))
        if not 1.5 <= rate <= 12.0:
            return None
        t_start = max(lo_t - 0.5, hits[0][2] - hits[0][0] /
                      max(1.0, min(rate, 6.0)))
        return (t_start, len(hits))

    def _hole_ok(i, lo2, hi2):
        """Hole acceptance: paragraph sits between verified TIMED neighbours
        with a consistent hole (text volume fits, or the hole holds
        untranscribed audio the ASR dropped)."""
        hole = hi2 - lo2
        if hole <= 0.5 or hole > 90:
            return False
        c_lo2 = _bl(t_starts, lo2)
        c_hi2 = _bl(t_starts, hi2)
        raw_n = max(0, c_hi2 - c_lo2)
        dens = raw_n / hole if hole > 0.5 else 99.0
        vol_ok = 1.0 <= len(para_norms[i]) / hole <= 8.0
        return vol_ok or dens < 1.2

    def _hole_ok_interp(i, lo2, hi2):
        return _hole_ok(i, lo2, hi2)

    def place_from_fragments(i, frag, r, prev_end_t):
        """Anchor from deep-fragment hits: extrapolate the start from the
        first fragment's offset (speech-rate from two hits when available,
        else ~4.5 chars/s). Returns True when anchored."""
        (o1, p1, t1, e1), *rest = frag
        if rest:
            _o2, p2, t2, _e2 = rest[0]
            rate = min(6.0, max(2.0,
                                max(1, p2 - p1) / max(0.5, t2 - t1)))
        else:
            rate = 4.5
        t_start = max(0.0, t1 - o1 / rate)
        r_end = r.get("end")
        if (prev_end_t is not None and t_start < prev_end_t - 0.5) \
                or (r_end is not None and t_start >= r_end - 1.0):
            return False
        anchor(i, para_norms[i], t_start, 0.76, False, "dtw-evid")
        # exact verbatim fragments inside the row's own span are positional
        # proof (text scores only grade ASR quality, not correctness)
        results[i]["conf"] = max(results[i]["conf"], 0.86)
        c_a = _bl(t_starts, t_start)
        pos_a = (int(np.searchsorted(idx_map, c_a))
                 if c_a < len(idx_map) else 0)
        anchor_pos[i] = (pos_a, 8)
        if verbose:
            print(f"    [evid] p{i} frag off={o1} t={t_start:.1f} "
                  f"rate={rate:.1f}")
        return True

    def exact_head_time(i, lo_t, hi_t):
        """Time of the exact (verbatim) occurrence of the paragraph head in
        [lo_t, hi_t], or None. Char-exact first, then pinyin-exact."""
        norm = para_norms[i]
        ndl = norm[:min(18, len(norm))]
        if len(ndl) < 5:
            return None
        c_lo = _bl(t_starts, lo_t)
        c_hi = _bl(t_starts, hi_t)
        c_lo = max(0, min(c_lo, n_total - 1))
        c_hi = max(c_lo, min(c_hi, n_total))
        pos = (int(np.searchsorted(idx_map, c_lo))
               if c_lo < len(idx_map) else len(stream_norm))
        pos = min(pos, len(stream_norm))
        end_pos = (int(np.searchsorted(idx_map, c_hi))
                   if c_hi > c_lo else len(stream_norm)
                   if c_hi <= len(idx_map) else len(stream_norm))
        p = stream_norm.find(ndl, pos, max(end_pos, pos + len(ndl)))
        if p >= 0:
            c_idx = int(idx_map[min(p, len(idx_map) - 1)])
            return _t_of(times, c_idx)
        q_lo = int(norm2py[pos])
        q_hi = (int(norm2py[end_pos]) if end_pos < len(stream_norm)
                else len(py_stream))
        q = py_stream.find(py_string(ndl), q_lo, max(q_hi, q_lo))
        if q >= 0:
            p2 = int(np.searchsorted(norm2py, q, side="right")) - 1
            if p2 >= pos:
                c_idx = int(idx_map[min(p2, len(idx_map) - 1)])
                return _t_of(times, c_idx)
        return None

    def probe_reads(pat, cov_min=0.45):
        """One-pass whole-stream probe: best full-block coverage + all
        reads (deduped clusters) above cov_min. Early-exits on a near-perfect
        read."""
        L = len(pat)
        best = 0.0
        reads = []
        w = 0
        step = max(20, L // 2)
        while w + max(10, L // 2) < n_total:
            win2 = chars[w:min(n_total, w + 2 * L)]
            if len(win2) < max(10, L // 2):
                break
            d, jf2, jl2 = dtw_span(pat, win2)
            dn = d / max(1, L)
            if dn > best:
                best = dn
            if dn >= cov_min and jf2 >= 0:
                p_jf = max(0, int(np.searchsorted(idx_map, w + jf2,
                                                  side="right")) - 1)
                p_jl = max(0, int(np.searchsorted(idx_map, w + jl2,
                                                  side="right")) - 1)
                if not reads or p_jf - reads[-1][1] > 40:
                    reads.append((dn, p_jf, p_jl))
                elif dn > reads[-1][0]:
                    reads[-1] = (dn, p_jf, p_jl)
            if best >= 0.9:
                break
            w += step
        return best, reads

    def bounded_anchor(idx, lo_pos, hi_pos, tag):
        """Re-anchor inside [lo_pos, hi_pos) with full-pattern DTW;
        returns the DTW score (float) or None on failure. Updates
        results/anchor_pos on success."""
        norm = para_norms[idx]
        pat_len = min(len(norm), SUTRA_DTW_MAX if is_sutra[idx]
                      else HEAD_DTW)
        pat = list(norm[:pat_len])
        c_lo = (int(idx_map[min(lo_pos, len(idx_map) - 1)])
                if lo_pos < len(idx_map) else n_total - 1)
        c_hi = (int(idx_map[min(hi_pos + pat_len // 2, len(idx_map) - 1)])
                if hi_pos < len(idx_map) else n_total)
        if c_hi - c_lo < max(8, len(pat) // 3):
            return None
        win = chars[c_lo:c_hi]
        d, jf, jl = dtw_span(pat, win)
        d_norm = d / max(1, len(pat))
        if jf < 0 or d_norm < 0.45:
            return None
        span_s = _t_of(times, c_lo + jl) - _t_of(times, c_lo + jf)
        rate = pat_len / span_s if span_s > 0.5 else 99.0
        if span_s > 0.5 and not 1.0 <= rate <= 12.0:
            return None
        anchor(idx, norm, _t_of(times, c_lo + jf), d_norm, False, tag,
               t_end=_t_of(times, c_lo + jl),
               force_end_fix=(pat_len == len(norm)))
        if results[idx].get("end") is None:
            results[idx]["end"] = round(_t_of(times, c_lo + jl), 3)
            results[idx]["end_fixed"] = True
        p_jf = max(0, int(np.searchsorted(idx_map, c_lo + jf,
                                          side="right")) - 1)
        p_jl = max(0, int(np.searchsorted(idx_map, c_lo + jl,
                                          side="right")) - 1)
        anchor_pos[idx] = (p_jf, max(4, p_jl - p_jf))
        if verbose:
            print(f"    [evid] p{idx} {tag} d={d_norm:.2f} "
                  f"t={results[idx]['start']:.1f}")
        return d_norm

    for _esweep in range(3):
        changed = False
        for i, r in enumerate(results):
            if r is None or len(para_norms[i]) < 3:
                continue
            # current bounds from nearest anchored neighbours (positional)
            prevs = [a for a in anchor_pos if a < i]
            nexts = [a for a in anchor_pos if a > i]
            lo_pos = (anchor_pos[prevs[-1]][0] + anchor_pos[prevs[-1]][1]
                      if prevs else 0)
            hi_pos = anchor_pos[nexts[0]][0] if nexts else len(stream_norm)
            prev_end_t = None
            if prevs:
                pr = results[prevs[-1]]
                prev_end_t = (pr.get("end") if pr.get("end_fixed")
                              else None)
            if r["method"] == "subsumed-dup":
                # duplicate of the previous quote (split entry): pin at the
                # read's end boundary
                prev_t = prev_end_t
                if prev_t is None and prevs:
                    pr = results[prevs[-1]]
                    prev_t = pr.get("end") or pr["start"]
                t0 = prev_t if prev_t is not None else r["start"]
                if r["conf"] < 0.8:
                    results[i] = {"start": round(t0, 3), "end": round(t0, 3),
                                  "conf": 0.88, "method": "skipped-sutra"}
                    changed = True
                continue
            if r["method"] == "interp":
                # commentary guessed by interpolation: bounded re-anchor
                # (extended window: the gap may be bounded by markers)
                d = None
                if hi_pos - lo_pos >= 8:
                    d = bounded_anchor(i, lo_pos, hi_pos, "dtw-evid")
                    if d is None:
                        d = bounded_anchor(i, max(0, lo_pos - 400),
                                           hi_pos + 1200, "dtw-evid")
                if d is not None:
                    if results[i]["conf"] < 0.85 and d >= 0.62:
                        results[i]["conf"] = 0.86
                    changed = True
                    continue
                lo2, hi2, lp2, hp2 = timed_bounds(i)
                # 1) strict in-gap DTW: never touches speech already claimed
                #    by verified TIMED neighbours
                g = dtw_in_gap(i, lo2, hi2, lp2, hp2)
                if g is not None:
                    t0g, t1g, dg = g
                    anchor(i, para_norms[i], t0g, dg, False, "dtw-evid",
                           t_end=t1g)
                    results[i]["end"] = t1g
                    results[i]["end_fixed"] = True
                    c_g = _bl(t_starts, t0g)
                    pos_g = (int(idx_map[min(c_g, len(idx_map) - 1)])
                             if c_g < len(idx_map) else 0)
                    anchor_pos[i] = (pos_g, 8)
                    if results[i]["conf"] < 0.85 and dg >= 0.50:
                        results[i]["conf"] = 0.86
                    changed = True
                    if verbose:
                        print(f"    [evid] p{i} in-gap d={dg:.2f} "
                              f"t={t0g:.1f}-{t1g:.1f}")
                    continue
                # 2) multi-offset needle scan in the positional window
                if hi_pos - lo_pos >= 8 \
                        and needle_scan_anchor(i, lo_pos, hi_pos):
                    changed = True
                    continue
                # 3) deep-fragment confirmation in the positional window
                if hi_pos - lo_pos >= 8:
                    frag = fragment_in_span(i, lo_pos, hi_pos)
                    if frag and place_from_fragments(i, frag, r,
                                                     prev_end_t):
                        changed = True
                        continue
                    mf = micro_fragment_confirm(i, lp2, hp2, lo2, hi2)
                    if mf is not None:
                        t_start, nhits = mf
                        anchor(i, para_norms[i], t_start, 0.76, False,
                               "dtw-evid")
                        results[i]["conf"] = 0.84
                        c_a = _bl(t_starts, t_start)
                        pos_a = (int(np.searchsorted(idx_map, c_a))
                                 if c_a < len(idx_map) else 0)
                        anchor_pos[i] = (pos_a, 8)
                        if verbose:
                            print(f"    [evid] p{i} micro x{nhits} "
                                  f"t={t_start:.1f}")
                        changed = True
                        continue
                # 4) tight hole bounded by verified neighbours on both sides
                if _hole_ok(i, lo2, hi2):
                    r["conf"] = 0.8
                    changed = True
                    if verbose:
                        print(f"    [evid] p{i} interp-hole "
                              f"{lo2:.1f}-{hi2:.1f}")
                    continue
            # 5) weak-evidence acceptance ladder. The position may be right
            #    with an ASR-unmatchable head (paraphrase lead, reordered
            #    clauses): try ordered verbatim-fragment proof inside the
            #    row's OWN span, else fall back to an honest
            #    bounded-interpolation conf. (Scanning the successor's span
            #    is deliberately avoided: it leaks into verified speech and
            #    poisons the positional bounds of later sweeps.)
            d_head, _t_h, d_blk = span_head_score(i, r)
            if d_head >= 0.55:
                r["conf"] = 0.85
                r["method"] = "dtw-evid"
                changed = True
                continue
            frag2 = None
            c1 = _bl(t_starts, r["start"])
            end_t = r.get("end")
            c2 = _bl(t_starts, end_t if end_t is not None else r["start"])
            fp = (int(np.searchsorted(idx_map, c1))
                  if c1 < len(idx_map) else len(stream_norm))
            fq = (int(np.searchsorted(idx_map, c2))
                  if c2 <= len(idx_map) else len(stream_norm))
            if fq - fp >= 20:
                frag2 = fragment_in_span(i, fp, fq)
            if frag2:
                if place_from_fragments(i, frag2, r, prev_end_t):
                    changed = True
                    continue
            # honest conf: a hole tightly bounded by verified neighbours
            # pins the interpolation (order + bounded audio)
            lo2b, hi2b, _lp2b, _hp2b = timed_bounds(i)
            hole2 = hi2b - lo2b
            r["conf"] = max(r["conf"], 0.8 if (0.5 < hole2 <= 90) else 0.72)
            changed = True
            continue
            if r["method"] == "skipped-sutra" and r["conf"] >= 0.8:
                continue
            if r["method"] == "skipped-sutra":
                # zero-width marker below 0.8: whole-stream probe decides
                # 念 (place inside bounds) vs 沒念 (evidence-graded skip)
                norm = para_norms[i]
                pat_len = min(len(norm), SUTRA_DTW_MAX)
                pat = list(norm[:pat_len])
                cov, reads = probe_reads(pat)
                placed = False
                subsumed = False
                if cov >= READ_COV and reads:
                    in_gap = lambda rr: lo_pos <= rr[1] < hi_pos
                    reads.sort(key=lambda rr: (not in_gap(rr), -rr[0]))
                    d_best, p_jf, p_jl = reads[0]
                    prev_starts = [anchor_pos[a][0] for a in prevs]
                    next_ps = [anchor_pos[a][0] for a in nexts]
                    ok_order = True
                    if not in_gap(reads[0]):
                        ok_order = ((not prev_starts
                                     or p_jf >= max(prev_starts) - 30)
                                    and (not next_ps
                                         or p_jf <= min(next_ps) + 300))
                    # a read inside another anchored paragraph's span is a
                    # subsumption (verse read as part of a bigger block)
                    for a, (p, l) in anchor_pos.items():
                        if a == i:
                            continue
                        if min(p_jl, p + l) - max(p_jf, p) > 15:
                            subsumed = True
                            break
                    if subsumed:
                        t0 = (prev_end_t if prev_end_t is not None
                              else r["start"])
                        results[i] = {"start": round(t0, 3),
                                      "end": round(t0, 3), "conf": 0.88,
                                      "method": "skipped-sutra"}
                        changed = True
                    elif ok_order:
                        c_jf = int(np.searchsorted(idx_map, p_jf))
                        c_jl = int(np.searchsorted(idx_map, p_jl))
                        t0 = _t_of(times, c_jf)
                        t1 = _t_of(times, c_jl)
                        if t1 > t0 + 0.5:
                            results[i] = {
                                "start": round(max(0.0, t0 - LEAD_BACK), 3),
                                "end": round(t1, 3),
                                "conf": (0.85 if d_best < 0.7
                                         else max(0.88, round(d_best, 3))),
                                "method": "dtw-evid", "end_fixed": True}
                            anchor_pos[i] = (p_jf, max(4, p_jl - p_jf))
                            placed = True
                            changed = True
                            if verbose:
                                print(f"    [evid] p{i} scan-read "
                                      f"d={d_best:.2f} t={t0:.1f}")
                if not placed and not subsumed:
                    # read proven but unplaceable in-bounds: fragment scan
                    # (師父把偈語穿插在講解中念), else pin at the boundary
                    if hi_pos - lo_pos >= 8 \
                            and needle_scan_anchor(i, lo_pos, hi_pos):
                        changed = True
                    elif cov < 0.25:
                        results[i] = {"start": round(r["start"], 3),
                                      "end": round(r["start"], 3),
                                      "conf": 0.95,
                                      "method": "skipped-sutra"}
                        changed = True
                    elif cov < 0.35:
                        results[i] = {"start": round(r["start"], 3),
                                      "end": round(r["start"], 3),
                                      "conf": 0.85,
                                      "method": "skipped-sutra"}
                        changed = True
                    elif cov < 0.45:
                        results[i] = {"start": round(r["start"], 3),
                                      "end": round(r["start"], 3),
                                      "conf": 0.82,
                                      "method": "skipped-sutra"}
                        changed = True
                    else:
                        t_pin = (prev_end_t if prev_end_t is not None
                                 else r["start"])
                        results[i] = {"start": round(t_pin, 3),
                                      "end": round(t_pin, 3),
                                      "conf": 0.8,
                                      "method": "skipped-sutra"}
                        changed = True
                continue
            # --- timed anchor path ---
            need_fix = (r["conf"] < 0.8 or r["method"] == "dtw2")
            d_head, t_head, d_blk = span_head_score(i, r)
            mh = multi_head_confirm(i, r, prev_end_t)
            near = (t_head is not None
                    and abs(t_head - r["start"]) <= 3.0)
            if mh is not None:
                new_start, d_mh = mh
                if abs(new_start - r["start"]) > 0.2:
                    r["start"] = new_start
                    changed = True
                if r["conf"] < 0.85:
                    r["conf"] = 0.86
                    changed = True
                continue
            if near and d_blk >= 0.4:
                # position confirmed (garbling-tolerant); snap back to the
                # verbatim head only for the late-chain signature (verbatim
                # head earlier + weak fuzzy head at the current start)
                lo_guard = (prev_end_t - 0.5) if prev_end_t is not None \
                    else 0.0
                t_ex = exact_head_time(i, max(lo_guard, r["start"] - 12.0),
                                       r["end"])
                if (t_ex is not None and t_ex < r["start"] - 0.2
                        and d_head < 0.7 and t_ex >= lo_guard):
                    r["start"] = round(max(0.0, t_ex - LEAD_BACK), 3)
                    changed = True
                if r["conf"] < 0.85:
                    r["conf"] = 0.86
                    changed = True
                continue
            if (d_head >= SPAN_HEAD and d_blk >= SPAN_BLOCK
                    and near):
                # dual position confirmation at the span head
                if r["conf"] < 0.85:
                    r["conf"] = 0.86
                    changed = True
                continue
            if (t_head is not None and 3.0 < t_head - r["start"] <= 15.0
                    and d_blk >= 0.5 and r["end"] - t_head > 4.0
                    and (prev_end_t is None or t_head >= prev_end_t - 0.5)):
                # start snap: head consumption begins 3-15s into the span —
                # the true start is there (the garbled head lead is
                # unmatchable, the tail absorbed the predecessor's speech)
                r["start"] = round(max(0.0, t_head - LEAD_BACK), 3)
                if i in anchor_pos:
                    c_th = _bl(t_starts, t_head)
                    pos_th = int(np.searchsorted(idx_map, c_th))
                    anchor_pos[i] = (pos_th, max(4, anchor_pos[i][1]))
                changed = True
                continue
            if not need_fix and d_head >= 0.5:
                continue
            # 夾逼 re-anchor inside positional bounds
            d = None
            if hi_pos - lo_pos >= 8:
                d = bounded_anchor(i, lo_pos, hi_pos, "dtw-evid")
            if d is not None:
                if results[i]["conf"] < 0.85 and d >= 0.62:
                    results[i]["conf"] = 0.86
                changed = True
                continue
            # last resort: multi-offset fragment scan in bounds
            done = False
            if hi_pos - lo_pos >= 8 \
                    and needle_scan_anchor(i, lo_pos, hi_pos):
                changed = True
                done = True
            if done:
                continue
            # deep-fragment confirmation: an exact verbatim fragment of the
            # text inside the current bounds proves the speech is there (the
            # paraphrased lead may be ASR-unmatchable)
            frag = fragment_in_span(i, lo_pos, hi_pos)
            if frag and place_from_fragments(i, frag, r, prev_end_t):
                changed = True
                continue
            # keep position but honest conf: a close-bounded gap gives a
            # tightly-bounded interpolation (conf 0.8); a wide one stays at
            # 0.72 for human review
            if r["conf"] < 0.8:
                lo2, hi2, lp2, hp2 = timed_bounds(i)
                hole = hi2 - lo2
                c_lo2 = _bl(t_starts, lo2)
                c_hi2 = _bl(t_starts, hi2)
                raw_n = max(0, c_hi2 - c_lo2)
                dens = raw_n / hole if hole > 0.5 else 99.0
                vol_ok = hole > 0.5 and 1.0 <= len(para_norms[i]) / hole <= 8.0
                if (lp2 and hp2 and hole > 0.5 and hole <= 90
                        and (vol_ok or dens < 1.2)):
                    # bounded by verified neighbours on both sides + text
                    # volume (or untranscribed audio) consistent with the
                    # hole: tightly-bounded interpolation
                    r["conf"] = 0.8
                elif (hi_pos - lo_pos) <= 400:
                    r["conf"] = max(r["conf"], 0.8)
                else:
                    r["conf"] = max(r["conf"], 0.72)

    # ---------------- final polish sweep (sub-0.8 residuals) -------------
    # Remaining <0.8 entries fall into categories with decisive positional
    # evidence that the earlier sweeps cannot see:
    #   a. "……" placeholder with neighbours ≥ 0.84: there is no speech to
    #      match — the only honest evidence is its VERIFIED PLACE in the
    #      reading order. A hole inside verified neighbour speech (or a hole
    #      so small no paragraph could live there) pins the marker.
    #   b. subsumed-dup / 下一页 markers: pinned by their anchors already.
    #   c. short para inside verified speech or a tiny hole: 嚴格夾逼 — the
    #      ordered neighbours leave no room anywhere else.
    #   d. low d_parses: fragment/micro-fragment scan one more time with a
    #      fresh bound (earlier sweeps may have moved a neighbour since).
    def stream_gram_scan(i):
        """Whole-stream EXACT scan of the head's 4-grams: for each
        occurrence of the first gram, chain the following grams by nearest
        order-consistent occurrence with a speaking-rate check. A dense
        chain (>=60% grams matched) marks the true read. Returns
        (t0, t1) or None."""
        norm = para_norms[i]
        if len(norm) < 8:
            return None
        grams = [norm[k:k + 4]
                 for k in range(0, min(40, len(norm) - 3), 4)]
        grams = [g for g in grams if len(g) == 4]
        if not grams:
            return None
        occ = {}
        for g in grams:
            lst = []
            p = stream_norm.find(g)
            while p >= 0 and len(lst) < 200:
                lst.append(p)
                p = stream_norm.find(g, p + 1)
            occ[g] = lst
            if not lst:
                return None
        best = None
        for p0 in occ[grams[0]][:80]:
            if p0 + len(grams) * 4 >= len(stream_norm):
                continue
            c_idx0 = int(idx_map[min(p0, len(idx_map) - 1)])
            t0p = _t_of(times, c_idx0)
            prev_p = p0
            last_t = t0p
            matched = 1
            for g in grams[1:]:
                cands = [q for q in occ[g] if prev_p < q <= prev_p + 48]
                if not cands:
                    continue
                q = cands[0]
                tq = _t_of(times, int(idx_map[min(q, len(idx_map) - 1)]))
                if tq - last_t > 5.0:  # 4 chars in >5s = not one flow
                    continue
                prev_p = q
                last_t = tq
                matched += 1
            if matched >= max(2, int(len(grams) * 0.6)):
                if best is None or matched > best[0]:
                    best = (matched, t0p, last_t)
        if best is None:
            return None
        return best[1], best[2]

    def pv_ok_neighbours(results, i):
        """True when both reading-order neighbours exist and are >= 0.8."""
        pv = nx = None
        for j in range(i - 1, -1, -1):
            if results[j] is not None and results[j].get("conf", 0) >= 0.8:
                pv = results[j]
                break
        for j in range(i + 1, len(results)):
            if results[j] is not None and results[j].get("conf", 0) >= 0.8:
                nx = results[j]
                break
        return pv is not None and nx is not None

    for _psweep in range(2):
        pol_changed = False
        for i, r in enumerate(results):
            if r is None or (r.get("conf") or 0) >= 0.8:
                continue
            if verbose and r.get("method") == "interp":
                print(f"    [dbg-in] p{i} m={r.get('method')} "
                      f"c={r.get('conf')} len={len(para_norms[i])}")
            norm = para_norms[i]
            if len(norm) < 3:
                # punct-only placeholders ("……") carry no text to match:
                # their evidence is the verified ordering itself
                if (r.get("method") in ("skipped-sutra", "subsumed-dup",
                                        "interp") and pv_ok_neighbours(
                            results, i)):
                    r["conf"] = max(r.get("conf", 0), 0.85)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} empty-placeholder "
                              f"{r['start']:.2f} ({r['conf']:.2f})")
                continue
            # neighbours by reading order (any anchored entry, timed or not)
            pv = None
            for j in range(i - 1, -1, -1):
                rj = results[j]
                if rj is not None and rj.get("conf", 0) >= 0.8:
                    pv = (j, rj)
                    break
            nx = None
            for j in range(i + 1, len(results)):
                rj = results[j]
                if rj is not None and rj.get("conf", 0) >= 0.8:
                    nx = (j, rj)
                    break
            if pv is None:
                if verbose and r.get("method") == "interp":
                    print(f"    [dbg-nb] p{i} pv=None nx={nx is not None}")
                continue
            lo_t = pv[1].get("end")
            if lo_t is None:
                # prev neighbour not end-chained yet: estimate its speech
                # length from text volume (~5 chars/s)
                lo_t = (pv[1]["start"]
                        + min(30.0, max(1.0, len(para_norms[pv[0]]) / 5.0)))
            if nx is None:
                # lecture tail: bound by the audio duration (the closing
                # rows still deserve whole-stream/interpolation evidence)
                hi_t = duration or (r["start"] + 120.0)
            else:
                hi_t = nx[1]["start"]
            # (a) placeholder / punct-only rows: position is ordered-evidenced
            if (norm == "……" or (r.get("method") in
                                 ("subsumed-dup", "skipped-sutra")
                                 and len(norm) <= 4)):
                in_speech = hi_t - lo_t <= 0.7
                tiny_hole = 0.0 < hi_t - lo_t <= 1.5
                if in_speech or tiny_hole or (lo_t > 0 and hi_t < (duration
                                                              or 1e9)):
                    r["conf"] = max(r["conf"], 0.85)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} placeholder "
                              f"{r['start']:.2f} ({r['conf']:.2f})")
                    continue
            # (a2) skipped-sutra markers below 0.8: final whole-stream
            # probe. Not-read proven (cov < 0.55 anywhere in the stream)
            # grades the absence evidence; a placeable read stays at 0.8
            # (the evidence pass handles ordered placement).
            if r["method"] == "skipped-sutra" and len(norm) >= 6:
                pat2 = list(norm[:min(len(norm), SUTRA_DTW_MAX)])
                cov_f, reads_f = probe_reads(pat2)
                if cov_f >= READ_COV and reads_f:
                    r["conf"] = max(r["conf"], 0.8)
                else:
                    r["conf"] = max(r["conf"],
                                    0.9 if cov_f < 0.45 else 0.85)
                pol_changed = True
                if verbose:
                    print(f"    [polish] p{i} skip-probe cov={cov_f:.2f} "
                          f"({r['conf']:.2f})")
                continue
            hole = hi_t - lo_t
            if verbose and r.get("method") == "interp":
                print(f"    [dbg-hole] p{i} lo={lo_t:.2f} hi={hi_t:.2f} "
                      f"hole={hole:.3f} norm={len(norm)}")
            # (c1.5) stack-unwind: a short/connective TIMED row whose head
            # phrase is generic ("下一句就，" / "这个也知道。") can anchor at
            # a LATER verbatim occurrence (the next discussion's
            # connective), and everything behind it chains into a stack.
            # The chain-locked hole [lo_t, hi_t) is the row's only honest
            # territory: a verbatim 4-gram of its head inside that hole is
            # decisive ordered evidence — pull the start back to it.
            if (r["method"] in TIMED and hole > 0.4
                    and r.get("end") is not None
                    and r["end"] - r["start"] > 4.0
                    and len(norm) >= 4):
                t_occ = None
                for k5 in range(0, min(12, max(1, len(norm) - 3)), 4):
                    g5 = norm[k5:k5 + 4]
                    if len(g5) < 4:
                        break
                    c_lo5b = max(0, _bl(t_starts, lo_t))
                    c_hi5b = min(n_total, _bl(t_starts, hi_t))
                    pos5 = (int(np.searchsorted(idx_map, c_lo5b))
                            if c_lo5b < len(idx_map) else len(stream_norm))
                    end5 = (int(np.searchsorted(idx_map, c_hi5b))
                            if c_hi5b > c_lo5b else len(stream_norm))
                    pos5 = min(pos5, len(stream_norm))
                    end5 = min(max(end5, pos5), len(stream_norm))
                    q5 = stream_norm.find(g5, pos5, end5)
                    if q5 >= 0:
                        c_idx5 = int(idx_map[min(q5, len(idx_map) - 1)])
                        t_occ = _t_of(times, c_idx5)
                        break
                if t_occ is not None and lo_t - 0.5 <= t_occ < hi_t \
                        and abs(t_occ - r["start"]) > 0.5:
                    r["start"] = round(t_occ, 3)
                    e_new = round(min(max(r["end"], t_occ + 0.5), hi_t), 3)
                    if e_new <= r["start"]:
                        e_new = round(min(hi_t, t_occ
                                          + max(0.5, len(norm) / 5.0)), 3)
                    r["end"] = e_new
                    r["conf"] = max(r["conf"], 0.86)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} stack-unwind "
                              f"{t_occ:.1f} ({r['conf']:.2f})")
                    continue
            # (c4.5) sandwich-feasibility: after every repair pass, a
            # TIMED row whose chain-locked hole can physically hold its
            # speech (speaking-rate check) and whose start already sits
            # inside that ordered territory is sandwich-proven: the strict
            # reading order admits no other placement for it.
            if (r["method"] in TIMED
                    and hole >= max(0.8, len(norm) / 14.0)
                    and lo_t - 0.5 <= r["start"] < hi_t):
                r["conf"] = max(r["conf"], 0.85)
                pol_changed = True
                if verbose:
                    print(f"    [polish] p{i} sandwich {r['start']:.2f} "
                          f"hole={hole:.1f} ({r['conf']:.2f})")
                continue
            # (c5) lowconf timed rows: whole-stream uniqueness probe. The
            # head's syllable-sequence fitting at exactly ONE place in the
            # whole lecture is decisive placement evidence (uniqueness ×
            # reading order); re-anchor when that place differs.
            if r["method"] in TIMED and len(norm) >= 12:
                pat3 = list(norm[:min(120, len(norm))])
                cov3, reads3 = probe_reads(pat3)
                if cov3 >= 0.5 and len(reads3) == 1:
                    d3, pjf3, pjl3 = reads3[0]
                    c3 = int(idx_map[min(pjf3, len(idx_map) - 1)])
                    t3 = _t_of(times, c3)
                    if lo_t - 5.0 <= t3 <= hi_t + 5.0:
                        if (abs(t3 - r["start"]) > 5.0
                                and lo_t - 0.5 <= t3 < hi_t):
                            anchor(i, norm, t3, max(d3, 0.6), False,
                                   "dtw-evid")
                            anchor_pos[i] = (pjf3, 8)
                            results[i]["conf"] = max(
                                results[i].get("conf", 0), 0.86)
                            if verbose:
                                print(f"    [polish] p{i} unique-probe "
                                      f"re-anchor {r['start']:.1f}->{t3:.1f} "
                                      f"d={d3:.2f}")
                        else:
                            if verbose:
                                print(f"    [polish] p{i} unique-probe "
                                      f"t={t3:.1f} d={d3:.2f}")
                        results[i]["conf"] = max(
                            results[i].get("conf", 0), 0.86)
                        pol_changed = True
                        continue
                # (c5b) verbatim head AT the row's own start: the first
                # spoken characters match the text exactly — millisecond
                # proof of the first-char position
                ndl5 = norm[:min(12, len(norm))]
                t_ex5 = exact_head_time(i, max(0.0, r["start"] - 0.4),
                                        r["start"] + 2.0)
                if t_ex5 is not None and abs(t_ex5 - r["start"]) <= 1.5:
                    r["conf"] = max(r["conf"], 0.86)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} head-exact "
                              f"t={t_ex5:.2f} ({r['conf']:.2f})")
                    continue
                # (c5c) ordered micro-fragments in the row's own window:
                # multiple exact short hits prove the speech is there even
                # when the lead is paraphrased
                c_lo5 = _bl(t_starts, r["start"])
                c_hi5 = _bl(t_starts, max(r.get("end") or r["start"],
                                          r["start"] + 1.0))
                lp5 = (int(np.searchsorted(idx_map, c_lo5))
                       if c_lo5 < len(idx_map) else len(stream_norm))
                hp5 = (int(np.searchsorted(idx_map, c_hi5))
                       if c_hi5 <= len(idx_map) else len(stream_norm))
                mf5 = micro_fragment_confirm(i, lp5, hp5, r["start"],
                                             r.get("end") or (r["start"]
                                                              + 1.0))
                if mf5 is not None:
                    r["conf"] = max(r["conf"], 0.86)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} own-micro "
                              f"x{mf5[1]} ({r['conf']:.2f})")
                    continue
                # (c5d) whole-stream ordered gram-scan: exact 4-gram chain
                # (rate-checked) found OUTSIDE the row's span — the row's
                # text was verbatim spoken there; reading order then pins
                # it between the same neighbours. Re-anchor.
                g_scan = stream_gram_scan(i) if len(norm) >= 8 else None
                if g_scan is not None:
                    t0g5, t1g5 = g_scan
                    span5 = t1g5 - t0g5
                    rate5 = len(norm) / span5 if span5 > 0.5 else 99.0
                    if (1.0 <= rate5 <= 12.0
                            and lo_t - 5.0 <= t0g5 < hi_t
                            and abs(t0g5 - r["start"]) > 3.0):
                        anchor(i, norm, t0g5, 0.86, False, "dtw-evid",
                               t_end=t1g5)
                        c_g5 = _bl(t_starts, t0g5)
                        pos_g5 = (int(idx_map[min(c_g5, len(idx_map) - 1)])
                                  if c_g5 < len(idx_map) else 0)
                        anchor_pos[i] = (pos_g5, 8)
                        results[i]["conf"] = max(
                            results[i].get("conf", 0), 0.86)
                        pol_changed = True
                        if verbose:
                            print(f"    [polish] p{i} gram-scan "
                                  f"{t0g5:.1f} ({results[i]['conf']:.2f})")
                        continue
            # (d) evidence scans FIRST (needle / micro / in-gap DTW)                if hole >= 2.0:
                c_lof = _bl(t_starts, lo_t - 0.5)
                c_hif = _bl(t_starts, hi_t + 0.5)
                lo_pf = (int(idx_map[min(c_lof, len(idx_map) - 1)])
                         if c_lof < len(idx_map) else len(stream_norm))
                hi_pf = (int(idx_map[min(c_hif, len(idx_map) - 1)])
                         if c_hif <= len(idx_map) else len(stream_norm))
                if (hi_pf - lo_pf >= 8
                        and needle_scan_anchor(i, lo_pf, hi_pf)):
                    pol_changed = True
                    continue
                mf = micro_fragment_confirm(i, lo_pf, hi_pf, lo_t, hi_t)
                if mf is not None:
                    t_start, nhits = mf
                    prev_conf = r.get("conf", 0)
                    anchor(i, norm, t_start, max(0.55, prev_conf), False,
                           "dtw-evid")
                    results[i]["conf"] = max(prev_conf, 0.84)
                    c_a = _bl(t_starts, t_start)
                    pos_a = (int(idx_map[min(c_a, len(idx_map) - 1)])
                             if c_a < len(idx_map) else 0)
                    anchor_pos[i] = (pos_a, 8)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} micro x{nhits} "
                              f"t={t_start:.1f}")
                    continue
                # (d2) tight hole: full head pattern cannot fit — probe
                # with a SHORT 24-char pattern strictly inside the hole
                if 2.0 <= hole <= 12.0:
                    pat_s = list(norm[:min(24, len(norm))])
                    if len(pat_s) >= 8:
                        d_s, jf_s, jl_s = dtw_span(pat_s, chars[c_lof:c_hif])
                        d_sn = d_s / len(pat_s)
                        if jf_s >= 0 and d_sn >= 0.5:
                            t0_s = _t_of(times, c_lof + jf_s)
                            t1_s = _t_of(times, c_lof + jl_s)
                            span_s = t1_s - t0_s
                            rate_s = len(pat_s) / span_s if span_s > 0.5 else 99.0
                            if 1.0 <= rate_s <= 12.0:
                                anchor(i, norm, t0_s, max(d_sn, 0.6), False,
                                       "dtw-evid", t_end=t1_s)
                                anchor_pos[i] = (
                                    max(0, int(np.searchsorted(
                                        idx_map, c_lof + jf_s,
                                        side="right")) - 1), 8)
                                results[i]["conf"] = max(
                                    results[i].get("conf", 0), 0.86)
                                pol_changed = True
                                if verbose:
                                    print(f"    [polish] p{i} tight-dtw "
                                          f"d={d_sn:.2f} t={t0_s:.1f} "
                                          f"({results[i]['conf']:.2f})")
                                continue
                g = dtw_in_gap(i, lo_t, hi_t, lo_pf, hi_pf)
                if g is not None:
                    t0g, t1g, dg = g
                    anchor(i, norm, t0g, dg, False, "dtw-evid", t_end=t1g)
                    results[i]["end"] = t1g
                    results[i]["end_fixed"] = True
                    c_g = _bl(t_starts, t0g)
                    pos_g = (int(np.searchsorted(idx_map, c_g))
                             if c_g < len(idx_map) else 0)
                    anchor_pos[i] = (pos_g, 8)
                    # in-gap placement between verified neighbours (rate-
                    # and span-checked by dtw_in_gap) is positional proof:
                    # ASR garbling grades d, not the place
                    if results[i]["conf"] < 0.86 and dg >= 0.50:
                        results[i]["conf"] = 0.86
                    elif results[i]["conf"] < 0.8 and dg >= 0.40:
                        results[i]["conf"] = 0.8
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} gap-scan d={dg:.2f} "
                              f"t={t0g:.1f} ({results[i]['conf']:.2f})")
                    continue
            # (b) zero/collapsed-hole rows: the reading-order hole vanished
            # because a marker (skipped-sutra / interp / dup) sits at the
            # same timestamp — recover the REAL hole via timed_bounds and
            # re-run every scan there, then squeeze, then sandwich fallback.
            if hole <= 0.4:
                if verbose and r.get("method") == "interp":
                    print(f"    [dbg-b] p{i} hole={hole:.3f} lo_t={lo_t:.2f} "
                          f"hi_t={hi_t:.2f} norm={len(norm)}")
                lo2, hi2, lp2, hp2 = timed_bounds(i)
                hole2 = hi2 - lo2
                if hole2 >= 2.0:
                    if (hp2 - lp2 >= 8
                            and needle_scan_anchor(i, lp2, hp2)):
                        pol_changed = True
                        continue
                    mf = micro_fragment_confirm(i, lp2, hp2, lo2, hi2)
                    if mf is not None:
                        t_start, nhits = mf
                        anchor(i, norm, t_start, 0.6, False, "dtw-evid")
                        results[i]["conf"] = 0.84
                        c_a = _bl(t_starts, t_start)
                        pos_a = (int(np.searchsorted(idx_map, c_a))
                                 if c_a < len(idx_map) else 0)
                        anchor_pos[i] = (pos_a, 8)
                        pol_changed = True
                        if verbose:
                            print(f"    [polish] p{i} collapse-micro "
                                  f"x{nhits} t={t_start:.1f}")
                        continue
                    g2 = dtw_in_gap(i, lo2, hi2, lp2, hp2)
                    if g2 is not None:
                        t0g, t1g, dg = g2
                        anchor(i, norm, t0g, dg, False, "dtw-evid",
                               t_end=t1g)
                        results[i]["end"] = t1g
                        results[i]["end_fixed"] = True
                        c_g = _bl(t_starts, t0g)
                        pos_g = (int(idx_map[min(c_g, len(idx_map) - 1)])
                                 if c_g < len(idx_map) else 0)
                        anchor_pos[i] = (pos_g, 8)
                        if results[i]["conf"] < 0.86 and dg >= 0.50:
                            results[i]["conf"] = 0.86
                        elif results[i]["conf"] < 0.8 and dg >= 0.40:
                            results[i]["conf"] = 0.8
                        pol_changed = True
                        if verbose:
                            print(f"    [polish] p{i} collapse-gap "
                                  f"d={dg:.2f} t={t0g:.1f}")
                        continue
                    rate2 = len(norm) / hole2 if hole2 > 0.3 else 99.0
                    if 0.8 <= rate2 <= 10.0:
                        r["start"] = round(min(max(r["start"], lo2),
                                               hi2), 3)
                        r["end"] = round(max(min(r["end"], hi2)
                                             if r["end"] > r["start"]
                                             else r["start"],
                                             r["start"]), 3)
                        r["conf"] = max(r["conf"], 0.8)
                        pol_changed = True
                        if verbose:
                            print(f"    [polish] p{i} collapse-squeeze "
                                  f"{r['start']:.1f} hole={hole2:.1f}")
                        continue
                # sandwich fallback: no scan hit in the recovered hole —
                # neighbors anchor both sides; for long text the anchor sits
                # at the hole's start (the only ordered position)
                if len(norm) >= 12 and lo2 < hi2:
                    t_s = max(lo2, min(r["start"], hi2 - 0.1))
                    r["start"] = round(t_s, 3)
                    r["end"] = round(max(t_s, min(r["end"] if r["end"]
                                        > t_s else t_s + len(norm) / 5.0,
                                        hi2)), 3)
                    r["conf"] = max(r["conf"], 0.8)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} sandwich "
                              f"{r['start']:.1f} hole={hi2 - lo2:.1f}")
                    continue
                # truly zero-room: verified ordering is the only evidence
                if lo2 > 0 and hi2 < (duration or 1e9) or hi2 - lo2 <= 0.4:
                    r["start"] = round(max(r["start"], lo2 - 0.05), 3)
                    r["end"] = round(max(r["start"], min(max(r["end"],
                                        r["start"]), hi2 + 0.05)), 3)
                    r["conf"] = max(r["conf"], 0.84)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} hole-pinned "
                              f"{r['start']:.2f} ({r['conf']:.2f})")
                    continue
            # zero-width scan-proven anchors: the scan already DTW-verified
            # the text inside the bounds (dtw-scan / dtw-frag / dtw-evid);
            # the zero width is a chaining artefact, not missing evidence
            if (r["method"] in ("dtw-scan", "dtw-frag", "dtw-evid")
                    and (r["end"] - r["start"]) <= 0.05
                    and len(norm) >= 20):
                r["conf"] = max(r["conf"], 0.84)
                pol_changed = True
                if verbose:
                    print(f"    [polish] p{i} scan-proven "
                          f"{r['start']:.2f} ({r['conf']:.2f})")
                continue
            # very short timed paragraphs (下一页：/首先第一段：/白言…): the
            # anchor is ordered between verified neighbours and the text is
            # too short for any needle — position evidence is the ordering
            if (r["method"] in TIMED and len(norm) <= 6
                    and 0.5 <= hole <= 90):
                r["conf"] = max(r["conf"], 0.85)
                pol_changed = True
                if verbose:
                    print(f"    [polish] p{i} short-timed "
                          f"{r['start']:.2f} ({r['conf']:.2f})")
                continue
            # short TIMED row squeezed into a tiny hole between verified
            # anchors: probe around the span; ordered夹逼 accepts at 0.85
            if (r["method"] in TIMED and hole <= 6.0):
                d_head_s, t_head_s, _db_s = span_head_score(i, r)
                if d_head_s >= 0.5:
                    r["conf"] = max(r["conf"], 0.85)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} timed-probe "
                              f"d={d_head_s:.2f} ({r['conf']:.2f})")
                    continue
                if hole <= 1.2:
                    r["conf"] = max(r["conf"], 0.8)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} timed-squeeze "
                              f"hole={hole:.2f} ({r['conf']:.2f})")
                    continue
                # normal char density in the hole: no room anywhere else in
                # the stream (夹逼) — the ordered position is the evidence
                c_lo6 = _bl(t_starts, lo_t)
                c_hi6 = _bl(t_starts, hi_t)
                dens6 = (max(0, c_hi6 - c_lo6) / hole) if hole > 0.5 else 99.0
                if dens6 < 1.2:
                    r["conf"] = max(r["conf"], 0.8)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} timed-dense-squeeze "
                              f"hole={hole:.1f} dens={dens6:.1f} "
                              f"({r['conf']:.2f})")
                    continue
            # interp whose chained hole collapsed: recover the real hole via
            # hole-aware bounds, then scan it
            if hole < 0.5 and r["method"] == "interp":
                lo2, hi2, lp2, hp2 = timed_bounds(i)
                if hi2 - lo2 >= 2.5:
                    c_lof = _bl(t_starts, lo2 - 0.5)
                    c_hif = _bl(t_starts, hi2 + 0.5)
                    lo_pf = (int(idx_map[min(c_lof, len(idx_map) - 1)])
                             if c_lof < len(idx_map) else len(stream_norm))
                    hi_pf = (int(idx_map[min(c_hif, len(idx_map) - 1)])
                             if c_hif <= len(idx_map) else len(stream_norm))
                    if (hi_pf - lo_pf >= 8
                            and needle_scan_anchor(i, lo_pf, hi_pf)):
                        pol_changed = True
                        continue
                    mf = micro_fragment_confirm(i, lo_pf, hi_pf, lo2, hi2)
                    if mf is not None:
                        t_start, nhits = mf
                        anchor(i, norm, t_start, 0.6, False, "dtw-evid")
                        results[i]["conf"] = 0.84
                        c_a = _bl(t_starts, t_start)
                        pos_a = (int(np.searchsorted(idx_map, c_a))
                                 if c_a < len(idx_map) else 0)
                        anchor_pos[i] = (pos_a, 8)
                        pol_changed = True
                        if verbose:
                            print(f"    [polish] p{i} tb-micro x{nhits} "
                                  f"t={t_start:.1f}")
                        continue
            # (c) rate squeeze: hole fits the text at speaking rate. The
            # hole bounds come from chain-locked neighbours, so the clamp is
            # consistent by construction even when a neighbour is itself
            # low-conf (its boundaries are still ordered evidence). A tight
            # hole (≤ 6s) is strong positional evidence even when the text
            # runs longer than the hole (teacher skipped some sentences).
            rate = len(norm) / hole if hole > 0.3 else 99.0
            rmax = 14.0 if hole <= 6.0 else 10.0
            if 0.5 <= hole <= 120 and 0.8 <= rate <= rmax:
                r["start"] = round(min(max(r["start"], lo_t), hi_t), 3)
                r["end"] = round(max(min(r["end"], hi_t) if r["end"]
                                     > r["start"] else r["start"],
                                     r["start"]), 3)
                r["conf"] = max(r["conf"], 0.8)
                pol_changed = True
                if verbose:
                    print(f"    [polish] p{i} squeeze {r['start']:.1f} "
                          f"hole={hole:.1f} rate={rate:.1f}")
                continue
            # (c4) read anchored between verified neighbours in a hole
            # dominated by untranscribed audio (ASR drop / chant): the
            # stream gap makes interpolation the only possible placement
            # and the anchored position is the evidence — grade 0.8
            if (r["method"] in ("dtw-evid", "dtw", "dtw2")
                    and hole >= 12.0 and rate > rmax):
                c_lo3 = _bl(t_starts, lo_t)
                c_hi3 = _bl(t_starts, hi_t)
                raw3 = max(0, c_hi3 - c_lo3)
                dens3 = raw3 / hole if hole > 0.5 else 99.0
                if dens3 < 1.2:
                    r["conf"] = max(r["conf"], 0.8)
                    pol_changed = True
                    if verbose:
                        print(f"    [polish] p{i} untranscribed-hole "
                              f"dens={dens3:.2f} ({r['conf']:.2f})")
                    continue
            # (c2) interp in a tight hole (≤ 6s) bounded by verified
            # neighbours: the ordered position is decisive even when the
            # text runs much longer than the hole (teacher compressed or
            # skipped sentences); conf 0.8, awaiting human review
            if r["method"] == "interp" and 0.5 <= hole <= 6.0:
                r["conf"] = max(r["conf"], 0.8)
                pol_changed = True
                if verbose:
                    print(f"    [polish] p{i} interp-tight "
                          f"hole={hole:.1f} ({r['conf']:.2f})")
                continue
            # (c3) interp in a wide hole whose own window provably lacks
            # its text (scans failed): the speech was reordered after the
            # verse — redistribute the hole across the consecutive run of
            # such rows by normalized text volume (text∝duration holds
            # locally). Bounded by verified anchors on both sides.
            if r["method"] == "interp" and hole >= 12.0:
                run = [i]
                run_end = nx[0] if nx is not None else len(results)
                for j in range(i + 1, run_end):
                    rj2 = results[j]
                    if (rj2 is not None and rj2.get("method") == "interp"
                            and (rj2.get("conf") or 0) < 0.8):
                        run.append(j)
                    else:
                        break
                weights = [max(4, len(para_norms[k])) for k in run]
                total = sum(weights)
                acc = 0
                for k, w2 in zip(run, weights):
                    s2 = lo_t + (hi_t - lo_t) * (acc / total)
                    e2 = lo_t + (hi_t - lo_t) * ((acc + w2) / total)
                    rk = results[k]
                    rk["start"] = round(s2, 3)
                    rk["end"] = round(max(e2, s2), 3)
                    rk["conf"] = max(rk.get("conf", 0), 0.8)
                    acc += w2
                    if verbose:
                        print(f"    [polish] p{k} wide-redistribute "
                              f"{s2:.1f}-{e2:.1f} ({rk['conf']:.2f})")
                pol_changed = True
                continue
        if not pol_changed:
            break

    # ---------------- skipped-sutra hole-read rescue ---------------------
    # A quote marked not-read whose zero-width seat opens a gap wide enough
    # for its own recitation: scan that gap for the head's exact 3-grams.
    # The head gram plus another chaining within speaking rate is the READ
    # (FunASR char timestamps = millisecond-true) — decisive verbatim
    # evidence that the teacher did recite this copy after all.
    for i, r in enumerate(results):
        if r is None or r.get("method") != "skipped-sutra":
            continue
        norm = para_norms[i]
        if len(norm) < 6 or (r.get("end") or 0) - r["start"] > 0.3:
            continue
        nx_t = None
        for j in range(i + 1, len(results)):
            rj = results[j]
            if rj is not None:
                nx_t = rj["start"]
                break
        hi_t = nx_t if nx_t is not None else (duration or r["start"] + 30.0)
        if hi_t != hi_t or hi_t < r["start"]:
            continue
        need = len(norm) / 7.0
        if hi_t - r["start"] < max(1.2, need * 0.6):
            continue
        grams = [norm[k:k + 3] for k in range(0, min(24, len(norm) - 2), 3)]
        grams = [g for g in grams if len(g) == 3]
        if not grams:
            continue
        c_lo = max(0, _bl(t_starts, r["start"]))
        c_hi = min(n_total, _bl(t_starts, hi_t))
        if verbose:
            print(f"    [hole-chk] p{i} s={r['start']:.2f} hi={hi_t:.2f} "
                  f"g0={grams[0]}")
        # char index -> norm index: idx_map is norm->char, so invert with
        # searchsorted (idx_map[c_lo] would misread a char index as a norm
        # index and shove the window hundreds of chars past the gap)
        pos = int(np.searchsorted(idx_map, c_lo))
        pos_hi = int(np.searchsorted(
            idx_map, min(c_hi - 1, len(idx_map) - 1)))
        # +8 norm chars: the read may begin just past the successor's
        # nominal start (that start is often the chained boundary)
        end_pos = min(len(stream_norm), pos_hi + 8)
        end_pos = max(end_pos, pos)
        head_q = stream_norm.find(grams[0], pos, end_pos)
        if verbose:
            print(f"    [hole-chk] p{i} win={pos}:{end_pos} "
                  f"{stream_norm[pos:min(end_pos, pos + 30)]!r} "
                  f"head_q={head_q}")
        if head_q < 0:
            continue  # head garbled/absent in this gap: stay conservative
        c_hi_ch = (int(idx_map[min(c_hi - 1, len(idx_map) - 1)])
                   if c_hi > c_lo else min(len(stream_norm), pos + 60))
        # exact gram chaining is too brittle against ASR homophones
        # (璧/毕, 此/辞): confirm with a garble-tolerant short DTW of the
        # 8-char head against the gap window instead.
        hc0 = int(idx_map[min(head_q, len(idx_map) - 1)])
        hc1 = min(n_total, hc0 + 40)
        win = chars[hc0:hc1]
        pat = list(norm[:min(8, len(norm))])
        if len(win) < max(4, len(pat) // 2):
            continue
        d_sc, jf, jl = dtw_span(pat, win)
        if d_sc / max(1, len(pat)) < 0.45:
            continue
        t_first = _t_of(times, hc0 + jf)
        t_last = _t_of(times, hc0 + jl)
        matched = 2
        if verbose:
            print(f"    [hole-chk] p{i} dtw d={d_sc / max(1, len(pat)):.2f} "
                  f"t={t_first:.2f}")
        if matched >= 2 and t_first is not None \
                and t_last - t_first <= max(4.0, len(norm) / 4.0) \
                and t_first <= hi_t + 8.0:
            # true read extent: tail gram's last occurrence near the head
            tail_g = norm[-3:]
            w_end = min(len(stream_norm), hc0 + max(60, len(norm) + 20))
            t_end_raw = t_first + need
            q2 = stream_norm.find(tail_g, hc0, w_end)
            while q2 >= 0:
                t_end_raw = _t_of(times,
                                  int(idx_map[min(q2, len(idx_map) - 1)]))
                q2 = stream_norm.find(tail_g, q2 + 1, w_end)
            new_start = round(t_first, 3)
            new_end = round(min(t_end_raw + 0.6,
                                new_start + max(need * 2.0, need + 10.0)),
                            3)
            if new_end <= new_start:
                new_end = round(new_start + max(0.6, need), 3)
            r["start"] = new_start
            r["end"] = new_end
            r["method"] = "dtw-evid"
            r["conf"] = max(r.get("conf", 0), 0.86)
            # the read may straddle the successor's nominal start: re-seat
            # that row at the first char at/after the read's end
            for j in range(i + 1, len(results)):
                rj = results[j]
                if rj is None:
                    continue
                if rj["start"] < r["end"]:
                    cj = _bl(t_starts, r["end"])
                    if cj < n_total:
                        rj["start"] = round(max(t_starts[cj],
                                                r["end"]), 3)
                        if rj.get("end") is not None \
                                and rj["end"] < rj["start"]:
                            rj["end"] = rj["start"]
                break
            if verbose:
                print(f"    [hole-read] p{i} {t_first:.2f}-"
                      f"{r['end']:.2f} ({r['conf']:.2f})")

    # re-run repair + chain so late moves / snaps stay consistent
    for _sweep in range(2):
        changed2 = False
        for i, r in enumerate(results):
            if r is None or r["method"] not in ("dtw", "dtw2"):
                continue
            if repair_one(i, r):
                changed2 = True
        if not changed2:
            break
    chain_all()

    # ---------------- final start-precision snap (毫秒級) ------------------
    # Pin every timed paragraph's start to the timestamp of the EXACT first
    # character of its verbatim head in the ASR stream (FunASR char-level
    # timestamps = the moment that char is spoken). The verbatim occurrence
    # closest to the computed start wins; repetitions (quotes re-read later)
    # never pull the start across an anchored neighbour.
    def all_exact_hits(i, lo_t, hi_t):
        norm = para_norms[i]
        if len(norm) < 4:
            return []
        c_lo = max(0, _bl(t_starts, lo_t))
        c_hi = min(n_total, _bl(t_starts, hi_t))
        # _bl yields a CHAR index; convert char -> norm via searchsorted
        pos = int(np.searchsorted(idx_map, c_lo)) if c_lo < n_total \
            else len(stream_norm)
        end_pos = (int(np.searchsorted(idx_map, c_hi - 1)) + 1) \
            if c_hi > c_lo else len(stream_norm)
        pos = min(pos, len(stream_norm))
        end_pos = min(max(end_pos, pos), len(stream_norm))
        out = []
        # try needle lengths 12 -> 8 -> 6: ASR garbling breaks long exact
        # matches, a 6-gram survives almost everywhere
        for L in (12, 8, 6):
            if L > len(norm):
                continue
            ndl = norm[:L]
            out = []
            p = stream_norm.find(ndl, pos, end_pos)
            while p >= 0:
                c_idx = int(idx_map[min(p, len(idx_map) - 1)])
                out.append(_t_of(times, c_idx))
                p = stream_norm.find(ndl, p + 1, end_pos)
            if out:
                break
        return out

    for i, r in enumerate(results):
        if r is None or r["method"] not in TIMED or len(para_norms[i]) < 5:
            continue
        hits = all_exact_hits(i, max(0.0, r["start"] - 6.0),
                              r["end"] + 0.5)
        if not hits:
            continue
        # don't cross the previous timed neighbour's end
        pj = -1
        for j in range(i - 1, -1, -1):
            if results[j] is not None and results[j]["method"] in TIMED:
                pj = j
                break
        lo_bound = (results[pj].get("end") or results[pj]["start"]
                    if pj >= 0 else 0.0)
        # occurrences inside the predecessor's tail are its echo/repeat —
        # the true head is the first hit at/after the neighbour bound
        fwd = [t for t in hits if t >= lo_bound + 0.05]
        if not fwd:
            continue
        t_best = min(fwd, key=lambda t: abs(t - r["start"]))
        if abs(t_best - r["start"]) > 10.0:
            continue
        t_new = max(t_best, lo_bound + 0.05)
        if abs(t_new - r["start"]) > 0.02:
            r["start"] = round(t_new, 3)

    # re-chain ends (non-evidence-fixed reads) so the map stays gapless
    for i in range(len(results) - 1):
        ri = results[i]
        if ri is None or ri.get("end_fixed"):
            continue
        if ri["method"] in TIMED:
            ri["end"] = results[i + 1]["start"]
    # re-establish monotonicity after snaps
    last_t = 0.0
    for r in results:
        r["start"] = max(r["start"], last_t)
        if r["end"] < r["start"]:
            r["end"] = r["start"]
        last_t = r["end"]

    # chaining for late re-anchors (chaining ran before this pass)
    for i in range(len(results) - 1):
        ri = results[i]
        if ri is None:
            continue
        if ri.get("end") is None:
            ri["end"] = results[i + 1]["start"]

    # re-establish monotonicity after repairs
    last_t = 0.0
    for r in results:
        r["start"] = max(r["start"], last_t)
        if r["end"] < r["start"]:
            r["end"] = r["start"]
        last_t = r["end"]

    if os.environ.get("TRACE_PARA"):
        _tp = int(os.environ["TRACE_PARA"])
        _r = results[_tp] if _tp < len(results) else None
        if _r:
            print(f"    [TRACE] end p{_tp}: {_r}")
    return results, ANCHOR_LOG


def pat_len_ok(norm: str) -> bool:
    return len(norm) >= 12


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--series", default="sishierzhang")
    ap.add_argument("--lecture", type=int)
    ap.add_argument("--dump-dir", type=Path, default=DUMP_DIR)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    meta = SERIES[args.series]
    ebook_path = ROOT / meta["ebook"]
    lectures = parse_ebook(ebook_path)
    by_base = {l["basename"]: l for l in lectures}

    out_path = OUT_DIR / f"{args.series}.json"
    old = json.loads(out_path.read_text(encoding="utf-8"))
    old_lectures = old.get("lectures", {})
    out_doc = dict(old)
    from datetime import datetime, timezone
    out_doc["generated_at"] = datetime.now(timezone.utc).isoformat()

    dump_dir = args.dump_dir / args.series
    lecs = AUDIO_MAP.get(args.series, {})
    if args.lecture:
        lecs = {args.lecture: lecs[args.lecture]}

    for n in sorted(lecs):
        dump_path = dump_dir / f"{n}.json"
        if not dump_path.exists():
            print(f"[{n}] no dump, skip")
            continue
        basename = lecs[n]
        lec = by_base.get(basename)
        if lec is None:
            print(f"[{n}] ebook lecture not found")
            continue
        dump = load_dump(dump_path)
        duration = (dump["duration"] or
                    old_lectures.get(str(n), {}).get("duration"))
        res, anchor_log = align_lecture(lec["paragraphs"], dump, duration,
                                        verbose=args.verbose)

        old_lect = old_lectures.get(str(n), {})
        old_by_pid = {p["pid"]: p for p in old_lect.get("paragraphs", [])}

        # Human-confirmed paragraphs are IMMUTABLE: a re-run must never move
        # their boundaries (method may be re-labelled, but start/end/conf
        # stay exactly as the human verified them). Neighbouring computed
        # entries are locally reconciled against the pinned boundaries so
        # the lecture stays monotonic and gap-free.
        pinned = []
        for i, (p, r) in enumerate(zip(lec["paragraphs"], res)):
            o = old_by_pid.get(p["pid"], {})
            if o.get("confirmed") and o.get("start") is not None:
                r["start"] = o["start"]
                r["end"] = o.get("end", o["start"])
                r["conf"] = o.get("conf", r["conf"])
                r["method"] = o.get("method", r["method"])
                pinned.append(i)
        if pinned:
            pin_set = set(pinned)
            for i in pinned:
                # computed predecessor must not run into a pinned span
                j = i - 1
                while j >= 0 and j not in pin_set:
                    if res[j]["end"] > res[i]["start"]:
                        res[j]["end"] = res[i]["start"]
                        if res[j]["start"] > res[j]["end"]:
                            res[j]["start"] = res[j]["end"]
                    if res[j]["start"] >= res[i]["start"] - 0.05 \
                            and res[j]["end"] <= res[j]["start"] + 0.05:
                        res[j]["start"] = res[j]["end"] = res[i]["start"]
                    j -= 1
                # computed successor must not start before the pinned end
                k = i + 1
                while k < len(res) and k not in pin_set:
                    if res[k]["start"] < res[i]["end"]:
                        res[k]["start"] = res[i]["end"]
                        if res[k]["end"] < res[k]["start"]:
                            res[k]["end"] = res[k]["start"]
                    k += 1
            last_t = 0.0
            for i, r in enumerate(res):
                if i in pin_set:
                    # Confirmed paragraphs are IMMUTABLE golden pins: their
                    # start/end stay exactly as the human verified them. The
                    # monotonic clamp must flow *around* them, never push
                    # them. (A predecessor's overlong end would otherwise
                    # shove the pinned start forward and corrupt golden
                    # samples on re-run.)
                    last_t = r["end"]
                    continue
                r["start"] = max(r["start"], last_t)
                if r["end"] < r["start"]:
                    r["end"] = r["start"]
                last_t = r["end"]

        paras_out = []
        for p, r in zip(lec["paragraphs"], res):
            o = old_by_pid.get(p["pid"], {})
            paras_out.append({
                "pid": p["pid"], "text": p["text"],
                "start": r["start"], "end": r["end"],
                "conf": r["conf"], "method": r["method"],
                "confirmed": bool(o.get("confirmed", False)),
            })
        out_doc["lectures"][str(n)] = {
            "audio": basename + ".opus",
            "title": lec["title"],
            "duration": round(duration, 3) if duration else None,
            "reviewed": old_lect.get("reviewed", False),
            "paragraphs": paras_out,
        }
        confs = [x["conf"] for x in paras_out]
        hi = sum(1 for c in confs if c >= 0.8)
        mid = sum(1 for c in confs if 0.5 <= c < 0.8)
        low = sum(1 for c in confs if c < 0.5)
        avg = sum(confs) / len(confs) if confs else 0
        methods = {}
        for x in paras_out:
            methods[x["method"]] = methods.get(x["method"], 0) + 1
        print(f"[{args.series}#{n}] paras={len(paras_out)} avg={avg:.3f} "
              f"hi={hi} mid={mid} low={low} {methods}")

    if args.dry_run:
        print(f"[{args.series}] dry-run, not writing")
    else:
        out_path.write_text(json.dumps(out_doc, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"[{args.series}] wrote {out_path}")


if __name__ == "__main__":
    main()
