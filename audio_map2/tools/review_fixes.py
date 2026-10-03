#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐場過目 `fixes.json` 的候選修正：新錨點前後的字級時間軸 ＋ SRT cue ＋ Word 首詞。

用法:
    .venv/bin/python review_fixes.py --month 2024-12 [--session 2024-12-09-tieba]
                                     [--only-change] [--before 2.0] [--after 3.0]
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from first_char_audit import parse_srt_raw  # noqa: E402


def label(t):
    if t is None:
        return ''
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--session', default='')
    ap.add_argument('--only-change', action='store_true')
    ap.add_argument('--before', type=float, default=2.0)
    ap.add_argument('--after', type=float, default=3.0)
    ap.add_argument('--maxdelta', type=float, default=99.0)
    ap.add_argument('--minchange', type=float, default=0.0)
    args = ap.parse_args()

    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    fixes = json.load(open(cdir / 'fixes.json', encoding='utf-8'))
    data = json.load(open(REPO / 'audio_map2' / f'{args.month}.json'))
    by_sid = {s['session_id']: s for s in data['sessions']}
    cues_by_sid = {}

    cur = None
    for fx in fixes:
        sid = fx['session_id']
        if args.session and sid != args.session:
            continue
        if args.only_change and abs(fx.get("delta") or 0) <= args.maxdelta:
            continue
        if abs(fx.get('delta') or 0) < args.minchange:
            continue
        if sid != cur:
            cur = sid
            s = by_sid[sid]
            cues_by_sid[sid] = []
            off = 0.0
            for part in s['media_parts']:
                cs = parse_srt_raw(part['srt_file'])
                cues_by_sid[sid].extend([(a + off, b + off, t) for a, b, t in cs])
                off += float(part.get('duration_est') or 0.0)
            print(f"\n{'=' * 110}\n### {sid}   cues={len(cues_by_sid[sid])}")
        old, new = fx['start'], fx.get('new_start')
        ch = fx.get('delta')
        m = ' ⟵ 需人工' if fx.get('weak') else ''
        print(f"{fx['label']:>8} old={old:9.3f} new={new:9.3f} Δ={ch:+7.2f} "
              f"sc={fx.get('score')} {fx.get('verdict','')}{m}")
        print(f"          fw={fx['first_word']!r}  matched={fx.get('matched')}  "
              f"onsets={fx.get('onsets')}")
        print(f"          A: {fx['answer_head'][:60]}")
        if new is None:
            continue
        cf = cdir / f"{sid}__{(fx['label'].lstrip('#') or 'opening')}.json"
        if cf.exists():
            r = json.load(open(cf, encoding='utf-8'))
            for tag in ('opus', 'mp3'):
                cs = (r.get(tag) or {}).get('chars') or []
                sel = [f'{t:.2f}:{c}' for t, c in cs
                       if new - args.before <= t <= new + args.after]
                if sel:
                    print(f"          {tag:<4} {' '.join(sel)}")
        near = [f'cue {a:.2f}-{b:.2f} {t[:26]}' for a, b, t in cues_by_sid[sid]
                if b > new - 3 and a < new + 3]
        for x in near[:3]:
            print('          ', x)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
