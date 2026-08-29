#!/usr/bin/env python3
"""Finalize a manually-repaired month JSON: merge note->notes, clear pending
markers, recompute stats, and run structural validation.

Usage (run from tool/word_audio_map2):
    .venv/bin/python path/to/finalize.py <month.json> [--inplace]

Reads <month.json>, writes <month.json>.finalized (or overwrites with --inplace).

Does:
  (a) merge a stray singular `note` field into the plural `notes` field the UI reads
  (b) replace `待人工確認`/`no-anchor:clamped` with verified markers (already reviewed)
  (c) strip noisy `layout-spread（依文字量展開…）` fragments
  (d) recompute the top-level `stats` object (missing/matched/low_conf/interpolated/pending/
      openings_ok/closings_ok)
  (e) structural check: no overlaps, no inversions, openings/closings intact.
      NOTE: opening.start == 0.0 is legal — compare `is None`, not truthiness.

Review the printed issue list before trusting the output.
"""
import sys
import json
import re
from pathlib import Path


def clean_notes(n):
    if not n:
        return ''
    n = n.replace('待人工確認', '已人工校驗')
    n = n.replace('no-anchor:clamped', 'verified')
    n = re.sub(r'layout-spread（依文字量展開[^）]*）;? ?', '', n)
    return n


def recompute_stats(d):
    st = {"sessions": 0, "segments": 0, "matched": 0, "low_conf": 0, "interpolated": 0,
          "pending": 0, "missing": 0, "openings_ok": 0, "closings_ok": 0}
    for s in d['sessions']:
        st['sessions'] += 1
        st['segments'] += len(s['segments'])
        for seg in s['segments']:
            if seg.get('start') is None:
                st['missing'] += 1
            else:
                st['matched'] += 1
                if (seg.get('confidence') or 0) < 0.5:
                    st['low_conf'] += 1
                if 'interpolated' in (seg.get('notes') or ''):
                    st['interpolated'] += 1
                if 'no-anchor:clamped' in (seg.get('notes') or '') or '待人工' in (seg.get('notes') or ''):
                    st['pending'] += 1
        if s.get('opening') is not None and s['opening'].get('start') is not None:
            st['openings_ok'] += 1
        if s.get('closing') is not None and s['closing'].get('start') is not None:
            st['closings_ok'] += 1
    return st


def main():
    json_path = sys.argv[1]
    inplace = '--inplace' in sys.argv
    d = json.load(open(json_path))

    for s in d['sessions']:
        for seg in s['segments']:
            notes = clean_notes(seg.get('notes') or '')
            mine = (seg.get('note') or '').strip().lstrip('|').strip()
            if mine:
                notes = (notes + ' | ' + mine) if notes else mine
            seg['notes'] = notes.strip()
            seg.pop('note', None)

    # structural re-check
    issues = 0
    for s in d['sessions']:
        prev = None
        prev_idx = None
        for seg in s['segments']:
            st, en = seg.get('start'), seg.get('end')
            if st is None or en is None:
                continue
            if prev is not None and st < prev - 0.5:
                issues += 1
                print(f"OVERLAP {s['date']} {s['source']} #{prev_idx}->#{seg['index']} {prev} {st}")
            if en < st:
                issues += 1
                print(f"INVERT {s['date']} {s['source']} #{seg['index']}")
            prev = en
            prev_idx = seg['index']
        if s.get('opening') is None or s['opening'].get('start') is None:
            issues += 1
            print(f"NO OPENING {s['date']} {s['source']}")
        if s.get('closing') is None or s['closing'].get('start') is None:
            issues += 1
            print(f"NO CLOSING {s['date']} {s['source']}")

    d['stats'] = recompute_stats(d)
    out = json_path if inplace else json_path + '.finalized'
    json.dump(d, open(out, 'w'), ensure_ascii=False, indent=1)
    print(f'structural issues: {issues}')
    print(f'stats: {json.dumps(d["stats"], ensure_ascii=False)}')
    print(f'wrote {out}')


if __name__ == '__main__':
    main()