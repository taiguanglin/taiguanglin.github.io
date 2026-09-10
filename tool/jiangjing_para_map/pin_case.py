#!/usr/bin/env python3
"""Adjudicate flagged rows: what does the ASR say at the map start vs at the
verbatim head occurrence? Distinguishes predecessor-bleed (early start) from
teacher-repeats (start correct, verbatim copy elsewhere)."""
import sys, json, bisect as bi
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from realign_dtw import load_dump, norm_para, _t_of, FILLER_RE, DUMP_DIR

SERIES = sys.argv[1] if len(sys.argv) > 1 else "liuzutanjing"
doc = json.loads((ROOT / "audio_map3" / f"{SERIES}.json").read_text())
CASES = []
for a in sys.argv[2:]:
    n, pid = a.split(":")
    CASES.append((n, pid))

for n, pid in CASES:
    lec = doc["lectures"].get(n)
    if not lec:
        print(f"[{n}] no lecture")
        continue
    row = next((p for p in lec["paragraphs"] if p["pid"] == pid), None)
    if row is None:
        print(f"[{n}:{pid}] not found")
        continue
    dump = load_dump(DUMP_DIR / SERIES / f"{n}.json")
    chars = dump["chars"]
    times = dump["times"]
    stream = norm_para("".join(chars))
    idx_map = np.array([j for j, c in enumerate(chars)
                        if not FILLER_RE.fullmatch(c)], dtype=np.int64)
    n_total = len(idx_map)

    def t_at_norm(p):
        return _t_of(times, idx_map[min(p, n_total - 1)])

    valid = sorted((t_at_norm(p), p) for p in range(n_total)
                   if t_at_norm(p) == t_at_norm(p))
    vts = [t for t, _ in valid]

    st = row["start"]
    txt = norm_para(row.get("text", ""))
    head = txt[:6]
    k = bi.bisect_left(vts, st - 0.3)
    pos0 = valid[k][1] if k < len(valid) else 0
    hit = stream.find(head, pos0)
    print(f"=== {n}:{pid} start={st:.2f} head='{head}'")
    # window at map start (first ~14 norm chars)
    if pos0 < n_total:
        seg = stream[pos0:pos0 + 14]
        print(f"  @map-start {t_at_norm(pos0):.2f}: '{seg}'")
    if hit >= 0:
        tv = t_at_norm(hit)
        print(f"  verbatim@{tv:.2f} (d={tv - st:+.2f}): "
              f"'{stream[hit:hit + 14]}'")
        # is this the FIRST occurrence at/after start?
        first = stream.find(head, pos0)
        print(f"  first-occurrence-at/after-start: {first == hit}, "
              f"pos={first}, t={t_at_norm(first):.2f}")
