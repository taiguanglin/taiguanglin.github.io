#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一批邊界壓成一屏：答案開頭 ＋ 舊 `start` 與候選錨點之間的字級時間軸。

`inspect_span.py` 每次只看一個邊界、且視窗釘在舊 `start`；人工過 `propose_fixes`
產出的候選時常要看「候選錨點落在哪個字、那個字是不是答案首詞」。這個工具直接從
`batch_anchor.py` 的快取讀字級軸（視窗 ±9s，足以涵蓋所有候選），兩解碼器併排印出，
每行一個字並標出 `start`／`new_start` 的位置。

用法:
    .venv/bin/python review_batch.py --month M --pick prefix --dmin 0.5
    .venv/bin/python review_batch.py --month M --weak
    .venv/bin/python review_batch.py --month M --session 2024-11-13-main --label 8
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from content_check import norm  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--session', default='')
    ap.add_argument('--label', default='')
    ap.add_argument('--pick', default='', help='basis 名稱過濾（first_word / prefix8 …）')
    ap.add_argument('--weak', action='store_true')
    ap.add_argument('--dmin', type=float, default=0.0, help='|Δ| 下限')
    ap.add_argument('--dmax', type=float, default=99.0)
    ap.add_argument('--limit', type=int, default=40)
    ap.add_argument('--b1', type=float, default=1.2, help='before 秒')
    ap.add_argument('--b2', type=float, default=4.0, help='after 秒')
    args = ap.parse_args()

    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    fx = json.load(open(cdir / 'fixes.json', encoding='utf-8'))
    n = 0
    for f in fx:
        if args.session and f['session_id'] != args.session:
            continue
        if args.label and f['label'] != args.label:
            continue
        if args.pick and not str(f.get('basis') or '').startswith(args.pick):
            continue
        if args.weak and not f.get('weak'):
            continue
        d = abs(f['delta'] or 0)
        if not (args.dmin <= d <= args.dmax):
            continue
        n += 1
        if n > args.limit:
            print(f'… 還有更多（已達 --limit {args.limit}）')
            break
        fp = cdir / f"{f['session_id']}__{(f['label'].lstrip('#') or 'opening')}.json"
        lo = min(f['start'], f['new_start'] or f['start']) - args.b1
        hi = max(f['start'], f['new_start'] or f['start']) + args.b2
        print('=' * 100)
        print(f"{f['session_id']} {f['label']}  start={f['start']:.3f} → {f['new_start']}  "
              f"Δ={f['delta']:+.2f}  basis={f['basis']} sc={f['score']} weak={f['weak']}")
        print(f"  fw={f['first_word']!r}  A={f['answer_head'][:64]!r}")
        print(f"  matched opus={ (f['matched'] or {}).get('opus','') !r} mp3={ (f['matched'] or {}).get('mp3','') !r}")
        if not fp.exists():
            print('  （無快取）')
            continue
        r = json.load(open(fp, encoding='utf-8'))
        for tag in ('opus', 'mp3'):
            cs = (r.get(tag) or {}).get('chars') or []
            out = []
            for t, c in cs:
                if not (lo <= t <= hi):
                    continue
                mark = ''
                if abs(t - f['start']) < 0.02:
                    mark += '«起»'
                if f['new_start'] is not None and abs(t - f['new_start'] + 0.02) < 0.02:
                    mark += '«新»'
                out.append(f'{t:.2f}{mark}{c}')
            print(f"  [{tag}] {' '.join(out)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())