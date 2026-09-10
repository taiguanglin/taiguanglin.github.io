#!/usr/bin/env python3
"""Print raw ASR (chars + char times) for time windows: adjudication aid.
Usage: dump_window.py <series> <lecture> <t0> <t1> [more windows...]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from realign_dtw import load_dump, _t_of

DUMP_DIR = Path("/tmp/funasr_cache")

series, ln = sys.argv[1], sys.argv[2]
wins = [(float(sys.argv[i]), float(sys.argv[i + 1]))
        for i in range(3, len(sys.argv) - 1, 2)]
dump_path = DUMP_DIR / series / f"{series}-{int(ln)}.json"
if not dump_path.exists():
    cands = sorted((DUMP_DIR / series).glob(f"*{ln}.json"))
    dump_path = cands[0]
d = load_dump(dump_path)
chars, times = d["chars"], d["times"]
for t0, t1 in wins:
    print(f"---- {t0} – {t1} ----")
    buf = []
    for k, c in enumerate(chars):
        t = _t_of(times, k)
        if t != t:  # nan
            continue
        if t < t0 or t > t1:
            continue
        buf.append((t, c))
    for i in range(0, len(buf), 16):
        chunk = buf[i:i + 16]
        print(f"[{chunk[0][0]:8.2f}] {''.join(c for _, c in chunk)}")
