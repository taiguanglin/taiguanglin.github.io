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

    def eval_candidates(idx, norm, cands, pat=None, jf_char_min=0):
        """DTW-verify anchor candidates; returns (d_norm, t_start, jf_char,
        jl_char, exact) for the best, or None. `pat` overrides the default
        head pattern; `jf_char_min` forbids the pattern from starting before
        that char index (used when re-anchoring past a read sutra block)."""
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
            if best is None or d_norm > best[0]:
                best = (d_norm, _t_of(times, w_lo + jf), w_lo + jf, w_lo + jl,
                        score >= 0.99)
        return best

    ANCHOR_LOG = []

    def anchor(idx, norm, t_start, d_norm, exact, method, t_end=None,
               force_end_fix=False, pat_len=None):
        conf = _conf_of(d_norm, exact)
        ANCHOR_LOG.append((idx, method, t_start, t_end, len(norm),
                           force_end_fix))
        r = {"start": round(max(0.0, t_start - LEAD_BACK), 3),
             "end": None, "conf": conf, "method": method}
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

    def anchor_sutra_fragments(idx, norm, lo_pos, hi_pos):
        """Verses are sometimes read in fragments with commentary
        interleaved (師父把偈語穿插在講解中念), so a contiguous full-block
        DTW fails. Slide short chunks from the paragraph head; the FIRST
        chunk that DTW-verifies (≥ FRAG_DTW_MIN, mostly exact chars — a
        modern-Chinese retelling shares syllables but not characters) marks
        the paragraph start. Search bounded to [lo_pos, hi_pos).
        Returns (t_start, d_norm, pos_jf, pos_jl) or None."""
        for off in range(0, max(1, len(norm) - FRAG_STRIDE), FRAG_STRIDE):
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
                "conf": _conf_of(d_f, False), "method": "dtw-frag",
                "end_fixed": True}
            # the whole block is the territory: commentary matching verse
            # words LATER in the block must still be redone past the read
            anchor_pos[idx] = (p_jf, len(norm))
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
        best = eval_candidates(idx, norm, cands, jf_char_min=jf_char_min)
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

    for idx, norm in enumerate(para_norms):
        if len(norm) < 3:
            continue
        if idx == 0 and is_sutra[idx]:
            if try_head_sutra(idx, norm):
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
                if verbose:
                    print(f"    [redo] p{idx} inside sutra p{_si} "
                          f"[{s_lo},{s_hi})")
                lastp = -1
                for a, (p, l) in sorted(anchor_pos.items()):
                    if a < idx and p + l <= s_lo:
                        lastp = max(lastp, p)
                jf_min_char = (int(idx_map[min(s_hi, len(idx_map) - 1)])
                               if s_hi < len(idx_map) else n_total)
                if try_anchor_commentary(idx, norm, s_hi, lastp,
                                         tag="dtw",
                                         jf_char_min=jf_min_char):
                    pos, ndl_len = anchor_pos[idx]
                    last_pos = max(last_pos, pos)
                    cursor = max(cursor, pos + ndl_len)
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
    TIMED = ("dtw", "dtw2", "dtw-frag", "dtw-scan")
    order = [i for i, r in enumerate(results)
             if r is not None and r["method"] in TIMED and i in anchor_pos]
    for k, idx in enumerate(order):
        if k == 0:
            continue
        prev = order[k - 1]
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
        if r["method"] not in ("dtw", "dtw2", "dtw-frag", "dtw-scan"):
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
        r["end"] = round(new_end, 3)
    if results:
        results[-1]["end"] = (round(duration, 3) if duration
                              else results[-1]["start"])
    last_t = 0.0
    for r in results:
        r["start"] = max(r["start"], last_t)
        if r["end"] < r["start"]:
            r["end"] = r["start"]
        last_t = r["end"]

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
