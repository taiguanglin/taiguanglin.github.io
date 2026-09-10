#!/usr/bin/env python3
"""Diagnose residual low-conf liuzutanjing rows: whole-stream probe of the
paragraph head + local neighbour context."""
import sys, json
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from realign_dtw import load_dump, norm_para, dtw_span, _t_of

DUMP_DIR = Path("/tmp/funasr_cache")

CASES = [(6, 9), (19, 56), (22, 47), (22, 68), (23, 135), (24, 93),
         (24, 130), (25, 57), (26, 140), (27, 109)]

series = "liuzutanjing"
book = json.load(open(ROOT / "audio_map3" / f"{series}.json"))

for ln, pi in CASES:
    L = book["lectures"][str(ln)]
    paras = L["paragraphs"]
    dump_path = DUMP_DIR / series / f"{int(ln)}.json"
    if not dump_path.exists():
        print(f"== L{ln} p{pi}: NO DUMP ({dump_path})")
        continue
    d = load_dump(dump_path)
    chars, times = d["chars"], d["times"]
    stream_norm = norm_para("".join(chars))
    idx_map = np.array([j for j, c in enumerate(chars)
                        if not __import__("re").fullmatch(
                            r"[啊呀吧嗯呃哦啦哇欸诶喽嘍嘛咧咯哟]", c)],
                       dtype=np.int64)
    n_total = len(idx_map)

    def t_at(cp):
        return _t_of(times, cp)

    txt = paras[pi]["text"] or ""
    norm = norm_para(txt)
    if not norm:
        print(f"== L{ln} p{pi}: EMPTY NORM  raw={txt[:30]!r}")
        continue
    Lp = min(len(norm), 40)
    pat = list(norm[:Lp])
    best = 0.0
    hits = []
    w = 0
    step = max(20, Lp // 2)
    while w + max(10, Lp // 2) < n_total:
        win2 = stream_norm[w:min(n_total, w + 2 * Lp)]
        if len(win2) < max(10, Lp // 2):
            break
        dd, jf2, jl2 = dtw_span(pat, win2)
        dn = dd / max(1, Lp)
        if dn > best:
            best = dn
        if dn >= 0.55 and jf2 >= 0:
            p_jf = max(0, int(np.searchsorted(idx_map, w + jf2,
                                              side="right")) - 1)
            t = t_at(p_jf)
            if not hits or t - hits[-1][0] > 3.0:
                hits.append((t, dn))
            elif dn > hits[-1][1]:
                hits[-1] = (t, dn)
        if best >= 0.9:
            break
        w += step
    p = paras[pi]
    prev = paras[pi - 1] if pi else None
    nxt = paras[pi + 1] if pi + 1 < len(paras) else None
    print(f"== L{ln} p{pi} conf={p['conf']:.2f} "
          f"t={p['start']}-{p['end']} norm={norm[:24]!r}")
    if prev:
        print(f"   prev: c={prev['conf']:.2f} {prev['start']}-{prev['end']} "
              f"{(prev['text'] or '')[:18]!r}")
    if nxt:
        print(f"   next: c={nxt['conf']:.2f} {nxt['start']}-{nxt['end']} "
              f"{(nxt['text'] or '')[:18]!r}")
    print(f"   probe best={best:.2f} hits>0.55: "
          f"{[(round(t,1), round(dn,2)) for t, dn in hits[:6]]}")
    print(f"   dump last t={t_at(len(chars) - 1):.1f}  audio_dur="
          f"{L.get('duration')}")
    print()
