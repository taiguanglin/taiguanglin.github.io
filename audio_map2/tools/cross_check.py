#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交叉檢查：字級短窗錨點（`propose_fixes.py`）vs 整場轉錄的「首內文時刻」
（`content_check.py`）。兩者量測完全獨立（短窗雙解碼器 vs 整場拼音模糊比對），
不一致就是「邊界還沒對準」的訊號。

- 兩者都是**同一件事**的兩種量法：段落第一個字被唸出來的時刻。
- 整場轉錄中段漂 2–3s，所以 `|Δ| <= 3.5s` 視為一致（`SKILL §4`）。
- 檔頭 0–5s 整場轉錄反而準（短窗 VAD 會丟檔頭），開場以整場為準。

用法:
    .venv/bin/python cross_check.py --month 2024-12 [--tol 3.5] [--session SID]
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from content_check import STRIP, PROBE, SEED, build_index, locate, norm, syl  # noqa: E402
from driftmap import DriftMap  # noqa: E402
from first_char_audit import first_word  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--session', default='')
    ap.add_argument('--tol', type=float, default=3.5)
    ap.add_argument('--min-score', type=float, default=0.6)
    args = ap.parse_args()

    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    fx = {(f['session_id'], f['label']): f
          for f in json.load(open(cdir / 'fixes.json', encoding='utf-8'))}
    data = json.load(open(REPO / 'audio_map2' / f'{args.month}.json', encoding='utf-8'))
    bad, n = [], 0
    for s in data['sessions']:
        if args.session and s['session_id'] != args.session:
            continue
        fn = cdir / 'full' / f"{s['session_id']}.json"
        if not fn.exists():
            print(f'[SKIP] {s["session_id"]}')
            continue
        full = json.load(open(fn, encoding='utf-8'))
        chars = full['chars']
        P, times = syl(''.join(c for _t, c in chars)), [t for t, _c in chars]
        idx = build_index(P)
        dm = DriftMap.for_session(cdir, s['session_id'])
        for g in s['segments']:
            if g.get('start') is None:
                continue
            label = f"#{g['index']}"
            f = fx.get((s['session_id'], label))
            if not f or f.get('new_start') is None:
                continue
            a = norm(g.get('answer_text') or '')
            if len(a) < PROBE + 4:
                continue
            p = a[len(norm(first_word(g.get('answer_text') or ''))):][:PROBE]
            sc, j = locate(P, idx, p, 0, len(P))
            if j is None or sc < args.min_score:
                continue
            t = dm.to_real(times[j])
            d = f['new_start'] - t
            n += 1
            if d > args.tol:      # 只抓「start 比內文還晚」＝整段錯位
                bad.append((s['session_id'], label, f['new_start'], t, d, sc, f))
    print(f'可比 {n} 段；不一致（|Δ| > {args.tol}s）{len(bad)} 段\n')
    for sid, label, ns, t, d, sc, f in bad:
        print(f'{sid:<20}{label:>8} 提案 {ns:9.3f} vs 整場首內文 {t:9.2f}  Δ={d:+7.2f}s '
              f'sc={sc:.2f} basis={f.get("basis")} fw={f["first_word"]!r}')
        print(f'{"":>29}A: {f["answer_head"][:56]!r}')


if __name__ == '__main__':
    raise SystemExit(main())
