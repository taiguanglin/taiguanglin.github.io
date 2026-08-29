#!/usr/bin/env python3
"""Scan a session's SRT for `下一个问题` / `下一问` transition markers.

Usage (run from tool/word_audio_map2):
    .venv/bin/python path/to/xscan.py <month.json> <date> <source>

Prints each transition marker time + its raw text. This is the primary map for
detecting reading-order reorders: compare the marker sequence (audio order)
against the JSON `index` (Word order).
"""
import sys
from pathlib import Path
import importlib.util
import json

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
    for i, (t0, t1, t) in enumerate(cues):
        n = normalize(t, conv)
        if ('下一个问题' in n) or ('下一问' in n) or (i == 0) or (i == len(cues) - 1):
            print(f"{t0:8.1f}  [{t.strip()[:60]}]")


if __name__ == '__main__':
    main()