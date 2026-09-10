#!/usr/bin/env python3
"""Verify millisecond first-char pinning: for rows whose head occurs verbatim
in the stream, the map start must pin the occurrence (|delta| <= 0.05s)."""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from realign_dtw import load_dump, norm_para, _t_of, FILLER_RE, DUMP_DIR

SERIES = sys.argv[1] if len(sys.argv) > 1 else "liuzutanjing"
doc = json.loads((ROOT / "audio_map3" / f"{SERIES}.json").read_text())

pin = leadin = bleed = novhit = 0
worst = []
for n, lec in sorted(doc["lectures"].items(), key=lambda kv: int(kv[0])):
    dump_path = DUMP_DIR / SERIES / f"{n}.json"
    if not dump_path.exists():
        continue
    dump = load_dump(dump_path)
    chars = dump["chars"]
    times = dump["times"]
    stream = norm_para("".join(chars))
    idx_map = np.array([j for j, c in enumerate(chars)
                        if not FILLER_RE.fullmatch(c)], dtype=np.int64)
    n_total = len(idx_map)

    def t_at_norm(p):
        return _t_of(times, idx_map[min(p, n_total - 1)])

    def t_at_char(c):
        return t_at_norm(int(np.searchsorted(idx_map, min(c, n_total - 1))))

    # valid (non-NaN) times sorted for bisect: norm pos -> time
    valid = sorted((t_at_norm(p), p) for p in range(n_total)
                   if t_at_norm(p) == t_at_norm(p))  # NaN check
    vts = [t for t, _ in valid]

    for p in lec["paragraphs"]:
        st = p.get("start")
        if st is None:
            continue
        txt = norm_para(p.get("text", ""))
        if len(txt) < 4:
            novhit += 1
            continue
        head = txt[:6]
        # first norm position whose char-time >= st - 0.3 (tolerate snap)
        import bisect as bi
        k = bi.bisect_left(vts, st - 0.3)
        if k >= len(valid):
            novhit += 1
            continue
        pos0 = valid[k][1]
        hit = stream.find(head, pos0)
        if hit < 0:
            novhit += 1
            continue
        tv = t_at_norm(hit)
        d = tv - st
        if abs(d) <= 0.05:
            pin += 1
        elif d > 0.05:
            # maybe a second verbatim copy sits exactly at start (dup text)
            hit2 = stream.find(head, pos0, hit + 1)
            if hit2 >= 0 and abs(t_at_norm(hit2) - st) <= 0.05:
                pin += 1
            else:
                leadin += 1
                if len(worst) < 12:
                    worst.append((n, p["pid"], round(st, 2), round(d, 2),
                                  p.get("text", "")[:24]))
        else:
            bleed += 1
            if len(worst) < 12:
                worst.append((n, p["pid"], round(st, 1), round(d, 2),
                              p.get("text", "")[:24]))

tot = pin + leadin + bleed
print(f"{SERIES}: verbatim-verifiable={tot}, pinned<=0.05s={pin} "
      f"({100 * pin / max(tot, 1):.0f}%), lead-in={leadin}, bleed={bleed}, "
      f"no-verbatim-hit={novhit}")
for w in worst:
    print("  ", w)
