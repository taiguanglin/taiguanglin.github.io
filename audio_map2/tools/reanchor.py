#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用整場轉錄把「答案內文」重新定位回音檔，用來修**整段錯位／窗口太短**的段。

`content_check.py` 只會報「內文超出窗」，不告訴你它應該在哪。本工具對指定的
（session, #index）列出：0% 探針（跳過首詞，避免人名被 ASR 聽歪）、30/60/85%
探針在整場轉錄中的最佳命中時間，並標出與現值 `start` 的差距——直接拿來寫 override。

用法:
    .venv/bin/python reanchor.py --month 2024-11 --session 2024-11-16-main --index 7 --index 44
    .venv/bin/python reanchor.py --month 2024-11 --session ... --index N --near 1010 1035
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from batch_analyze import fuzzy  # noqa: E402
from content_check import norm  # noqa: E402
from first_char_audit import first_word  # noqa: E402


def best_hit(f, cs, probe, lo, hi):
    if len(probe) < 8:
        return None
    out = []
    for i in range(len(f) - len(probe)):
        t = cs[i][0]
        if not (lo <= t <= hi):
            continue
        w = f[i:i + len(probe)]
        out.append((fuzzy(probe, w), t, w))
    return max(out, key=lambda x: x[0]) if out else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--session', required=True)
    ap.add_argument('--index', type=int, action='append', default=[])
    ap.add_argument('--lo', type=float, default=-90.0)
    ap.add_argument('--hi', type=float, default=40.0)
    ap.add_argument('--near', type=float, nargs=2, default=None,
                    help='只在 [lo, hi] 這個絕對區間搜尋（覆寫 --lo/--hi）')
    ap.add_argument('--tol', type=float, default=0.78)
    args = ap.parse_args()

    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    d = json.load(open(REPO / 'audio_map2' / f'{args.month}.json', encoding='utf-8'))
    s = next(x for x in d['sessions'] if x['session_id'] == args.session)
    r = json.load(open(cdir / 'full' / f'{args.session}.json', encoding='utf-8'))
    cs = r['chars']
    f = ''.join(c for _t, c in cs)

    for ix in args.index:
        g = next((x for x in s['segments'] if x['index'] == ix), None)
        if g is None:
            print(f'#{ix} 不存在')
            continue
        txt = norm(g['answer_text'])
        fw = first_word(g['answer_text'])
        st = g['start']
        if args.near:
            lo, hi = args.near[0], args.near[1]
        else:
            lo, hi = st + args.lo, st + args.hi
        print('=' * 96)
        print(f"#{ix} start={st} end={g['end']}  fw={fw!r}")
        print(f"  A={g['answer_text'][:78]!r}")
        probes = [('首(跳過首詞)', txt[len(norm(fw)):][:16] if fw else txt[:16])]
        for frac in (0.3, 0.6, 0.85):
            probes.append((f'{int(frac*100)}%', txt[int(frac * len(txt)):][:16]))
        for tag, p in probes:
            h = best_hit(f, cs, p, lo, hi)
            if not h:
                print(f'  {tag:<12} p={p!r} （區間內無命中）')
                continue
            sc, t, w = h
            flag = '' if (st - 8 <= t <= g['end'] + 8) else '  ✗ 窗外'
            print(f'  {tag:<12} p={p!r} sc={sc:.2f} @{t:.2f} Δstart={t - st:+.2f}{flag}')
            print(f'               {w!r}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())