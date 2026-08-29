#!/usr/bin/env python3
"""Content-coverage audit: find segments whose answer_text is NOT in their window.

Usage (run from tool/word_audio_map2):
    .venv/bin/python path/to/audit.py <month.json>

For every segment, computes difflib coverage of its answer_text[:180 chars]
against the SRT text inside [start, end]. Flags cov<0.4 as LOW (likely misaligned),
plus EMPTY (no answer_text) and NOTRACE (start is null).

This is a *filter*, not a verdict: low coverage can be ASR name-garbling (still
correctly placed). Always confirm flagged items by reading readspan output.
"""
import sys
import json
import difflib
from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('bm', REPO / 'tool/word_audio_map2/build_maps.py')
bm = importlib.util.module_from_spec(spec)
sys.modules['bm'] = bm
spec.loader.exec_module(bm)
from common import parse_srt, normalize, get_converter  # noqa: E402

THRESHOLD = 0.4


def between(cues, t0, t1):
    return ''.join(t for s, e, t in cues if t0 is not None and t1 is not None and s < t1 and e > t0)


def cov(win, probe):
    if not win or not probe:
        return 0.0
    sm = difflib.SequenceMatcher(None, win, probe, autojunk=False)
    return sum(m.size for m in sm.get_matching_blocks()) / max(1, len(probe))


def main():
    json_path = sys.argv[1]
    conv = get_converter()
    data = json.load(open(json_path))
    for s in data['sessions']:
        date, src = s['date'], s['source']
        cues = parse_srt(Path(s['media_parts'][0]['srt_file']), conv)
        low = []
        for seg in s['segments']:
            if seg.get('start') is None:
                low.append((seg['index'], None, 0.0, 'NOTRACE'))
                continue
            probe = normalize((seg.get('answer_text') or '')[:180], conv)
            if not probe:
                low.append((seg['index'], seg['start'], 0.0, 'EMPTY'))
                continue
            c = cov(between(cues, seg['start'], seg['end']), probe)
            if c < THRESHOLD:
                low.append((seg['index'], seg['start'], round(c, 3), 'LOW'))
        print(f'{date} {src}: flagged={len(low)}')
        for idx, st, c, tag in low:
            print(f'   #{idx:3d} start={st} cov={c} {tag}')


if __name__ == '__main__':
    main()