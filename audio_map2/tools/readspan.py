#!/usr/bin/env python3
"""Read the raw SRT text in a time span of a session.

Usage (run from tool/word_audio_map2 so `common`/`build_maps` import correctly):
    .venv/bin/python path/to/readspan.py <month.json> <date> <source> <t0> <t1>

Example:
    .venv/bin/python ../audio_map2/tools/readspan.py ../audio_map2/2025-05.json 2025-05-12 贴吧 8842 9060

Prints lines: `  <start:8.1f> <end:8.1f>  <text>` (raw SRT, no normalization).
Greppable for questioner names / answer-head phrases. Use source simplified chars
(贴吧 / 微信公众号).
"""
import sys
from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('bm', REPO / 'tool/word_audio_map2/build_maps.py')
bm = importlib.util.module_from_spec(spec)
sys.modules['bm'] = bm
spec.loader.exec_module(bm)
from common import parse_srt_raw  # noqa: E402


def main():
    json_path, date, src, t0, t1 = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
    import json
    data = json.load(open(json_path))
    s = [x for x in data['sessions'] if x['date'] == date and x['source'] == src][0]
    cues = parse_srt_raw(Path(s['media_parts'][0]['srt_file']))
    for sec, e, t in cues:
        if sec < t1 and e > t0:
            print(f'  {sec:8.1f} {e:8.1f}  {t}')


if __name__ == '__main__':
    main()