#!/usr/bin/env python3
"""Sequential answer-head locator — proposes true start per segment.

Usage (run from tool/word_audio_map2):
    .venv/bin/python path/to/seqloc.py <month.json> <date> <source>

Walks segments in current (playback) array order, and for each tries to find its
answer-head anchor *after the previous segment's cursor*. Prints cur_start vs found;
a `MOVE` tag or `found=None` = segment likely misaligned or reordered.

WARNING: match_start gives false positives on generic heads (e.g. answer starting
with `下一个问题`). Treat output as a hypothesis — always verify by reading the
actual SRT span with readspan.py before moving anything.
"""
import sys
import json
import bisect
from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('bm', REPO / 'tool/word_audio_map2/build_maps.py')
bm = importlib.util.module_from_spec(spec)
sys.modules['bm'] = bm
spec.loader.exec_module(bm)
from common import parse_srt, normalize, get_converter  # noqa: E402


def main():
    json_path, date, src = sys.argv[1], sys.argv[2], sys.argv[3]
    conv = get_converter()
    data = json.load(open(json_path))
    s = [x for x in data['sessions'] if x['date'] == date and x['source'] == src][0]
    cues = parse_srt(Path(s['media_parts'][0]['srt_file']), conv)
    starts = [c[0] for c in cues]

    def ci(ti):
        return bisect.bisect_left(starts, ti)

    cursor_t = 0.0
    for seg in s['segments']:
        a = (seg.get('answer_text') or '').strip()
        if not a:
            print(f"#{seg['index']:2d} EMPTY  start={seg['start']}")
            continue
        na = normalize(a, conv)
        found = None
        for off in (0, 4, 8, 12):
            p = na[off:off + 20]
            if len(p) < 8:
                continue
            r = bm.match_start(cues, ci(cursor_t), p, min_len=6, min_block=6, max_scan=400)
            if r:
                found = r
                break
        st = seg['start']
        tag = '' if found and abs(found[0] - st) < 90 else ' MOVE'
        print(f"#{seg['index']:2d} cur_start={st:8.1f}  found={found and round(found[0], 1)}{tag}")
        cursor_t = (found[0] + 1) if found else (st + 1)


if __name__ == '__main__':
    main()