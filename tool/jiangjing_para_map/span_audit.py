#!/usr/bin/env python3
"""Independent span-level audit for audio_map3 (lengqie etc.).

The stored [start, end) span is accepted or rejected primarily on
POSITIONAL evidence, not on DTW text score (ASR garbling caps text scores
around 0.7 even for a correct span):

  A. head-at-start : head needle (first 24 norm chars) DTW-verifies with its
     first consumption within HEAD_TOL_S of span.start → position correct.
  B. block-in-span : first ≤240 norm chars DTW-verify inside the span
     window → the span actually contains the paragraph's speech.
  C. no_speech     : whole-stream probe of the full block finds no read
     (best coverage < 0.45) and the span is (near-)zero-width → skipped
     block verdict.

Verdicts:
  span_ok / skip_ok   : accepted (high confidence justified)
  span_bad            : evidence contradicts the stored position
  unknown             : not enough evidence either way (needs eyes)

Usage:
  python3 span_audit.py --series lengqie                 # full report
  python3 span_audit.py --series lengqie --lecture 15 -v # one lecture detail
Output: reports/span_audit_<series>.json + console summary.
"""
from __future__ import annotations

import argparse
import bisect
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
from realign_dtw import (  # noqa: E402
    load_dump, norm_para, dtw_span, _t_of, FILLER_RE,
    SUTRA_DTW_MAX, DUMP_DIR,
)
from build_maps import parse_ebook  # noqa: E402

OUT = Path(__file__).resolve().parent / "reports"

EBOOKS = {"lengqie": "08.html", "sishierzhang": "07.html",
          "liuzutanjing": "09.html", "lengyanjing": "10.html",
          "ganen": "04.html"}

HEAD_TOL_S = 3.0     # head consumption must start within 3s of span.start
BLK_MIN = 0.55       # block-in-span coverage for acceptance
PROBE_MIN = 0.45     # below this a whole-stream probe = "not read"


def char_at(t_starts, t: float, n: int) -> int:
    return max(0, min(bisect.bisect_left(t_starts, t), n - 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="lengqie")
    ap.add_argument("--lecture", type=int)
    ap.add_argument("--dump-dir", type=Path, default=DUMP_DIR)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    dump_dir = args.dump_dir / args.series
    map_path = ROOT / "audio_map3" / f"{args.series}.json"
    doc = json.loads(map_path.read_text(encoding="utf-8"))
    lectures = parse_ebook(ROOT / "ebook" / EBOOKS[args.series])
    by_base = {l["basename"]: l for l in lectures}

    verdicts = Counter()
    rows = []
    per_lec = {}

    for n, lec in sorted(doc["lectures"].items(), key=lambda kv: int(kv[0])):
        if args.lecture and int(n) != args.lecture:
            continue
        dump_path = dump_dir / f"{n}.json"
        if not dump_path.exists():
            print(f"[{n}] no dump, skip")
            continue
        dump = load_dump(dump_path)
        chars = dump["chars"]
        times = dump["times"]
        n_total = len(chars)
        t_starts = [tt[0] for tt in times]
        stream_norm = norm_para("".join(chars))
        idx_map = np.array([j for j, c in enumerate(chars)
                            if not FILLER_RE.fullmatch(c)], dtype=np.int64)

        basename = lec["audio"][:-5]
        ebook = by_base.get(basename)
        paras = ebook["paragraphs"] if ebook else []
        if not paras or len(paras) != len(lec["paragraphs"]):
            print(f"[{n}] ebook paragraphs mismatch, skip")
            continue

        v = Counter()
        details = []

        for i, p in enumerate(lec["paragraphs"]):
            norm = norm_para(p["text"])
            cls = paras[i].get("cls") or ""
            is_sutra = "sutra-text" in cls
            start, end, conf, method = (p["start"], p["end"], p["conf"],
                                        p["method"])
            zero = end - start < 1.0
            ev = {}
            verdict = None

            if len(norm) < 3:
                verdict = "tiny"
            else:
                head = list(norm[:min(24, len(norm))])
                c_lo = char_at(t_starts, start - 1.5, n_total)
                c_hi = char_at(t_starts, end + 1.5, n_total)
                if c_hi - c_lo < max(8, len(head)):
                    c_lo = max(0, c_lo - 20)
                    c_hi = min(n_total, c_lo + max(40, len(head) * 3))
                win = chars[c_lo:c_hi]
                # A. head-at-start: head must be consumed starting at the
                # span head (allow small skip-in ≤ 2 chars for ASR leading
                # noise inside the window)
                if len(win) >= max(8, len(head)):
                    dh, jfh, jlh = dtw_span(head, win)
                    dh_n = dh / max(1, len(head))
                    t_head = _t_of(times, c_lo + jfh) if jfh >= 0 else None
                    t_head_end = (_t_of(times, c_lo + jlh)
                                  if jlh is not None and jlh >= 0 else None)
                    ev["d_head"] = round(dh_n, 3)
                    ev["t_head"] = (round(t_head, 2)
                                    if t_head is not None else None)
                    head_at_start = (t_head is not None
                                     and abs(t_head - start) <= HEAD_TOL_S)
                    # fuzzy head consumed fully INSIDE the span (chained
                    # start includes the predecessor's tail — position of
                    # the speech itself is verified correct)
                    head_in_span = (t_head is not None and t_head_end is not None
                                    and t_head >= start - HEAD_TOL_S
                                    and t_head_end <= end + HEAD_TOL_S)
                    # B. block-in-span
                    blk_len = min(len(norm),
                                  SUTRA_DTW_MAX if is_sutra else 240)
                    blk = list(norm[:blk_len])
                    db, _jf2, _jl2 = dtw_span(blk, win)
                    db_n = db / max(1, len(blk))
                    ev["d_blk"] = round(db_n, 3)
                    if head_at_start and db_n >= BLK_MIN:
                        verdict = "span_ok"
                    elif head_at_start and dh_n >= 0.75 and db_n >= 0.4:
                        verdict = "span_ok"
                    elif (head_in_span and dh_n >= 0.65 and db_n >= 0.45
                          and not zero):
                        # speech sits fully inside the span; only the start
                        # boundary is loose (chaining absorbed predecessor)
                        verdict = "span_ok"
                        ev["note"] = "head-in-span"
                    elif head_at_start:
                        verdict = "unknown"   # position right, text weak
                    else:
                        # C. whole-stream probe (only when position fails)
                        L = len(blk)
                        best = 0.0
                        w = 0
                        step = max(20, L)
                        while w + max(10, L // 2) < n_total:
                            win2 = chars[w:min(n_total, w + 2 * L)]
                            if len(win2) < max(10, L // 2):
                                break
                            d2, _j, _jl2 = dtw_span(blk, win2)
                            best = max(best, d2 / max(1, L))
                            if best >= 0.9:
                                break
                            w += step
                        ev["probe"] = round(best, 3)
                        if best < PROBE_MIN and (zero or is_sutra):
                            verdict = "skip_ok" if zero else "span_bad"
                        elif best >= PROBE_MIN and zero:
                            verdict = "span_bad"   # read exists, span empty
                        else:
                            verdict = "span_bad"
                else:
                    verdict = "unknown"
                    ev["win"] = c_hi - c_lo

            verdicts[verdict] += 1
            v[verdict] += 1
            details.append({"pid": p["pid"], "i": i, "method": method,
                            "conf": conf, "start": start, "end": end,
                            "is_sutra": is_sutra, "verdict": verdict,
                            "ev": ev})
            if args.verbose and verdict not in ("span_ok", "skip_ok", "tiny"):
                print(f"  [{n}] p{i} {verdict:9s} {method:14s} "
                      f"c={conf:.2f} t={start:.1f}-{end:.1f} "
                      f"sutra={is_sutra} {ev}")

        tot = sum(v.values())
        ok = v["span_ok"] + v["skip_ok"] + v["tiny"]
        per_lec[n] = {"ok": ok, "total": tot,
                      "rate": round(ok / tot, 3) if tot else None}
        rows.append({"lecture": n, "verdicts": dict(v), "details": details})

    print("\n=== verdict summary ===")
    for k, c in sorted(verdicts.items()):
        print(f"  {k:12s} {c}")
    tot = sum(verdicts.values())
    bad = verdicts["span_bad"] + verdicts["unknown"]
    print(f"  TOTAL {tot}   bad+unknown {bad} ({bad / max(1, tot):.2%})")
    print("\n=== per-lecture ok-rate (worst 15) ===")
    lows = sorted(per_lec.items(), key=lambda kv: kv[1]["rate"] or 0)[:15]
    for k, vv in lows:
        print(f"  [{k}] {vv['ok']}/{vv['total']} = {vv['rate']:.1%}")
    OUT.mkdir(exist_ok=True)
    rep = OUT / f"span_audit_{args.series}.json"
    rep.write_text(json.dumps({"per_lecture": per_lec, "rows": rows},
                              ensure_ascii=False, indent=1), "utf-8")
    print(f"wrote {rep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
