#!/usr/bin/env python3
"""Comprehensive local evidence for residual low-conf liuzutanjing rows:
neighborhood (methods/spans) + verbatim 4-gram occurrences in the stream."""
import sys, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from realign_dtw import load_dump, norm_para, _t_of, FILLER_RE

DUMP_DIR = Path("/tmp/funasr_cache")
CASES = [(6, 9), (19, 56), (22, 47), (22, 68), (23, 135), (24, 93),
         (24, 130), (25, 57), (26, 140), (27, 109)]

series = "liuzutanjing"
book = json.load(open(ROOT / "audio_map3" / f"{series}.json"))

for ln, pi in CASES:
    L = book["lectures"][str(ln)]
    paras = L["paragraphs"]
    p = paras[pi]
    print(f"== L{ln} p{pi} conf={p['conf']:.2f} t={p['start']}-{p['end']} "
          f"method={p.get('method','')} read={p.get('read','')}")
    for k in range(max(0, pi - 2), min(len(paras), pi + 3)):
        if k == pi:
            continue
        q = paras[k]
        print(f"   p{k}: m={q.get('method',''):<14} c={q['conf']:.2f} "
              f"{q['start']:8.2f}-{(q['end'] if q['end'] is not None else -1):8.2f} "
              f"sutra={'Y' if q.get('sutra') else 'n'} {(q['text'] or '')[:16]!r}")
    d = load_dump(DUMP_DIR / series / f"{int(ln)}.json")
    chars, times = d["chars"], d["times"]
    s = "".join(chars)
    norm = norm_para(p["text"] or "")
    grams = [norm[i:i + 4] for i in range(0, min(len(norm), 24), 4)]
    for g in grams:
        if len(g) < 4:
            continue
        hits = []
        idx = 0
        while True:
            i = s.find(g, idx)
            if i < 0:
                break
            hits.append(round(_t_of(times, i), 1))
            idx = i + 1
        print(f"   gram {g!r}: {hits[:8]}")
    print()
