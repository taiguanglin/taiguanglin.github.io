#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""單一边界的深度檢視：字級時間軸（opus+mp3）＋原始 SRT cue ＋ Word 文字。

用法:
    .venv/bin/python inspect_span.py --month 2024-12 --session 2024-12-11-wechat --label 9 \
        --span 8.0 8.0
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from first_char_audit import parse_srt_raw  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--session', required=True)
    ap.add_argument('--label', required=True)
    ap.add_argument('--span', type=float, nargs=2, default=(6.0, 6.0))
    args = ap.parse_args()

    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    key = args.label.lstrip('#') or 'opening'
    r = json.load(open(cdir / f"{args.session}__{key}.json", encoding='utf-8'))
    st = r['start']
    lo, hi = st - args.span[0], st + args.span[1]
    print(f"{args.session} {args.label}  start={st:.3f}  first_word={r['first_word']!r}")
    print(f"A[:120]={r['answer_head'][:120]!r}\n")
    for tag in ('opus', 'mp3'):
        cs = (r.get(tag) or {}).get('chars') or []
        print(f"[{tag}]", ' '.join(f'{t:.2f}:{c}' for t, c in cs if lo <= t <= hi))
    data = json.load(open(REPO / 'audio_map2' / f'{args.month}.json'))
    s = [x for x in data['sessions'] if x['session_id'] == args.session][0]
    off, cues = 0.0, []
    for part in s['media_parts']:
        cues += [(a + off, b + off, t) for a, b, t in parse_srt_raw(part['srt_file'])]
        off += float(part.get('duration_est') or 0.0)
    print('\n[SRT]')
    for a, b, t in cues:
        if b > lo and a < hi:
            mark = '  <<START' if a <= st <= b else ''
            print(f'  {a:9.2f}-{b:9.2f} {t[:46]}{mark}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
