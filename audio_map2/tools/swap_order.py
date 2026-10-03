#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""依音訊序重排 `segments[]`（SKILL §1 鐵律第 1 條允許改「`segments[]` 順序」）。

有些月份同一問者連續問了兩個子題，**Word 的收錄順序與音檔實際作答順序相反**，
於是 `segments[]` 的指數序 ≠ 時間序，`start` 無法嚴格遞增（`apply_alignment.py`
會直接拒絕該場）。2024-11 實測兩處：

- `2024-11-11-main` #20`教员`↔#21`第六个问题`：音檔先答 #21（1292.6「還有第六個問題…」），
  再答 #20（1349.5「還有這個教員是天人…」）
- `2024-11-12-main` #14`睡梦中的入定`↔#15`睡梦中打通`：音檔先答 #15（1549.6
  「下一個問題 SNJYLG…」），再答 #14（1594.1「還有睡夢中的入定…」）

重排規則：交換兩個相鄰 segment 在陣列中的位置，對調兩者的 `index`，並把
`stable_key` 重新寫成 `<session_id>#<index>`（`question_id`／`stable_key` 唯一性
由 `validate_relink.py` 檢查，`question_id` 跟著自己的文字走、不動）。兩段都追加
`reordered:` 說明依據。

除了「相鄰兩段對調」，2024-07 實測還有**三段循環錯位**（音檔順序 #46 → #44 → #45，
JSON 順序 #44 → #45 → #46），用 `--move` 兩次即可（`--move A:B` 不必相鄰）。

用法:
    .venv/bin/python swap_order.py --month 2024-11 \
        --swap 2024-11-11-main:20:21 --swap 2024-11-12-main:14:15 --inplace

    # 三段循環：44/45/46 → 46/44/45
    .venv/bin/python swap_order.py --month 2024-07 \
        --move 2024-07-15-main:44:46 --move 2024-07-15-main:45:46 --inplace
"""
import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--swap', action='append', default=[],
                    help='<session_id>:<indexA>:<indexB>（兩者必須相鄰）')
    ap.add_argument('--move', action='append', default=[],
                    help='<session_id>:<indexA>:<indexB>（**不必相鄰**，任意兩段對調；'
                         '處理「三段循環錯位」用：44/45/46 要變成 46/44/45 時，'
                         'swap 44:46 再 swap 45:46 即可）')
    ap.add_argument('--note', default='依音訊順序（音檔先答後者的題）重排；原 Word 收錄順序相反')
    ap.add_argument('--inplace', action='store_true')
    args = ap.parse_args()

    p = REPO / 'audio_map2' / f'{args.month}.json'
    d = json.load(open(p, encoding='utf-8'))
    by_sid = {s['session_id']: s for s in d['sessions']}

    for spec in args.swap + args.move:
        sid, a, b = spec.rsplit(':', 2)
        a, b = int(a), int(b)
        adjacent = spec in args.swap
        s = by_sid[sid]
        segs = s['segments']
        ia = next(i for i, g in enumerate(segs) if g['index'] == a)
        ib = next(i for i, g in enumerate(segs) if g['index'] == b)
        if adjacent and ib != ia + 1:
            raise SystemExit(f'--swap 只支援相鄰兩段（實得 index {a} 在第 {ia} 位、{b} 在第 {ib} 位）；'
                             f'不相鄰請改用 --move')
        ga, gb = segs[ia], segs[ib]
        # 先驗證：只有「後段的 start 比前段早」才是順序問題；否則不准動
        if (ga.get('start') is not None and gb.get('start') is not None
                and gb['start'] >= ga['start']):
            raise SystemExit(f'{spec}: #{b}.start({gb["start"]}) 本來就不早於 '
                             f'#{a}.start({ga["start"]})，不是順序問題')
        segs[ia], segs[ib] = gb, ga
        for i, g in enumerate(segs, start=1):
            g['index'] = i
            g['stable_key'] = f'{sid}#{i}'
        for g in (ga, gb):
            n = g.get('notes') or ''
            if 'reordered:' not in n:
                g['notes'] = (n + ' | ' if n else '') + f'reordered:與 {gb["index"] if g is ga else ga["index"]} 依音訊序對調 — {args.note}'
        print(f'  ✓ {sid}: 交換 #{a} ↔ #{b}（現為 #{gb["index"]} 在前）')

    out = p if args.inplace else Path(str(p) + '.swap')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    print('→', out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())