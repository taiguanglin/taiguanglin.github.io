#!/usr/bin/env python3
"""Eyeball tool: for given (lecture, para-index) show the paragraph head vs
the raw ASR text around the mapped start, plus positional evidence."""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
from realign_dtw import load_dump, norm_para, dtw_span, _t_of, FILLER_RE
from build_maps import parse_ebook

series = sys.argv[1] if len(sys.argv) > 1 else "lengqie"
lec_n = sys.argv[2] if len(sys.argv) > 2 else "1"
idxs = [int(x) for x in sys.argv[3:]] or None

dump = load_dump(Path(f"/tmp/funasr_cache/{series}/{lec_n}.json"))
doc = json.loads((ROOT / "audio_map3" / f"{series}.json").read_text())
lec = doc["lectures"][lec_n]
times = dump["times"]
chars = dump["chars"]

# raw text with per-char index
raw_chars = []
for c in dump["chars"]:
    raw_chars.append(c)

def t2c(t):
    import bisect
    starts = [tt[0] for tt in times]
    return max(0, min(bisect.bisect_left(starts, t), len(chars) - 1))

EBOOKS = {"lengqie": "08.html", "sishierzhang": "07.html",
          "liuzutanjing": "09.html", "lengyanjing": "10.html", "ganen": "04.html"}
lectures = parse_ebook(ROOT / "ebook" / EBOOKS[series])
basename = lec["audio"][:-5]
paras = {l["basename"]: l for l in lectures}[basename]["paragraphs"]

for i, p in enumerate(lec["paragraphs"]):
    if idxs and i not in idxs:
        continue
    start, end = p["start"], p["end"]
    c_lo, c_hi = t2c(start - 2), t2c(end + 2)
    asr = "".join(raw_chars[max(0, c_lo - 10):c_hi + 10])
    book = paras[i]["text"][:60]
    print(f"== p{i} {p['method']} c={p['conf']} t={start:.1f}-{end:.1f} "
          f"sutra={'sutra-text' in (paras[i].get('cls') or '')}")
    print(f"  書: {book}")
    print(f"  音: {asr[:90]}")
