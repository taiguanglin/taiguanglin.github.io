#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用**整場轉錄的內容探針**逐段重建 `start`（2024-03 需要）。

為什麼需要：`batch_anchor.py` 的量測窗是 `[start-4, start+8]`，一旦 JSON 的 `start`
整段偏離音檔（2024-03-05 從 #14 起逐段累積偏移，到 #37 已差 **110 秒**），
短窗根本碰不到真正的內文，`propose_fixes` 只會給出一堆假陰性。
`content_check.py` 的探針是「全場搜尋」，方向相反（抓得到漂移），但只印出錯、不回寫。

本工具把 `content_check` 的探針邏輯做成**可回寫**的重建器：

1. 依 `segments[]` 陣列順序逐段處理（陣列順序 = 播放順序，2024-03 已先用
   `swap_order.py` 依音訊序排好）。
2. 每段取 `answer_text` 的 0%/25%/50%/75%/85% 五個探針，**跳過人名（首詞）**。
3. 搜尋範圍限制在 `[上一段已定案的 start, 本段原 start + SLACK]`，
   **取分數最高的探針、再取其中最早的命中** → 保證單調遞增。
4. 命中時間往前回退 `LEAD`（把「正文首字」拉回成「叫名那一刻」）。
5. 輸出 `overrides.json`（人工複驗後才套用），並印出每段的證據。

單調性是硬約束：某段的內文真的唸不到（分數太低）時**不猜**，直接跳過並標 `skip`，
留給 `reanchor.py` / `onset_at.py` 人工處理。

用法:
    tool/sense_voice/.venv/bin/python audio_map2/tools/rebuild_anchors.py \\
        --month 2024-03 --slack 240 --lead 1.2 --out /tmp/am2_2024-03/rebuild.json
"""
import argparse
import json
import re
import sys as _sys
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from content_check import (  # noqa: E402
    PROBE, SEED, build_index, first_word, locate, norm, syl)
from driftmap import DriftMap  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
# **只用 0% 探針當錨點**（答案第一句正文、跳過人名）——與 content_check.py 的
# 方向性檢查同一套探針，已在 2024-04…06 逐段人工複驗過。
# 其餘探針只用來**佐證**：0% 命中太弱時退回次佳且分數更高的那個。
FRACS = (0.0, 0.25, 0.5, 0.75, 0.85)
# 探針長度。預設 PROBE=16；`--probe-len` 可拉長。**短探針容易命中錯的發話**——
# 16 音節在主題式講解裡常有兩三處共用措辭，實測 2024-02/03 的
# listen_check 例外多半就是這種假命中。拉長到 24–28 音節後唯一性大幅提高。
ANCHOR_FRACS = (0.0, 0.25, 0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--session', default='', help='只處理這一場（可重複呼叫）')
    ap.add_argument('--slack', type=float, default=240.0,
                    help='允許往後找多遠（秒）——涵蓋 JSON 的漂移量')
    ap.add_argument('--lead', type=float, default=1.2,
                    help='命中時間往前回退幾秒（把正文首字拉回叫名那一刻）')
    ap.add_argument('--min-score', type=float, default=0.72)
    ap.add_argument('--pad', type=float, default=45.0, help='整場頭尾各排除幾秒（靜音）')
    ap.add_argument('--probe-len', type=int, default=0,
                    help='探針長度（音節）；0 = 用 content_check 的 PROBE(16)。'
                         '拉長可大幅降低假命中，只建議配合 --min-score 0.78+ 使用')
    ap.add_argument('--only', default='',
                    help='只處理這些邊界（每行 `<session_id>|<label>` 的檔案），其餘跳過')
    ap.add_argument('--out', default='')
    ap.add_argument('--rate', type=float, default=4.6,
                    help='語速（音節／秒），用來把「探針命中時間」推回「答案開頭」')
    ap.add_argument('--min-shift', type=float, default=0.5,
                    help='位移小於此值不列為候選')
    args = ap.parse_args()

    plen = args.probe_len or PROBE
    only = set()
    if args.only:
        only = {ln.strip() for ln in open(args.only, encoding='utf-8') if ln.strip()}
    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    data = json.load(open(REPO / 'audio_map2' / f'{args.month}.json', encoding='utf-8'))
    out, skipped, nofile = {}, [], []
    for s in data['sessions']:
        if args.session and s['session_id'] != args.session:
            continue
        fn = cdir / 'full' / f"{s['session_id']}.json"
        if not fn.exists():
            nofile.append(s['session_id'])
            continue
        chars = json.load(open(fn, encoding='utf-8'))['chars']
        P, times = syl(''.join(c for _t, c in chars)), [x[0] for x in chars]
        idx = build_index(P)
        dm = DriftMap.for_session(cdir, s['session_id'])
        lo0 = next((i for i, t in enumerate(times) if t >= times[0] + args.pad), 0)
        hi0 = next((i for i, t in enumerate(times) if t > times[-1] - args.pad), len(P))
        segs = [g for g in s['segments'] if g.get('start') is not None]
        prev = None
        print(f"### {s['session_id']}")
        for g in segs:
            key = f"{s['session_id']}|#{g['index']}"
            if only and key not in only:
                continue
            a = norm(g.get('answer_text') or '')
            st = g['start']
            # 單調性硬約束：**一律**從「上一段已定案的 start」之後才找。
            # （先前只在 st < prev 時才套用，會讓 st 仍大於 prev 的段把搜尋窗開到全場，
            #   探針因此命中前面出現過的同樣字串 → 2024-03-02 #39 被配到 476s。）
            lo = next((i for i, t in enumerate(times) if t >= prev), 0) \
                if prev is not None else lo0
            hi = next((i for i, t in enumerate(times) if t > st + args.slack), len(P))
            hi = min(hi, hi0)
            fw = len(norm(first_word(g.get('answer_text') or '')))
            hits = []
            for fr in FRACS:
                p = a[fw + int(len(a) * fr):fw + int(len(a) * fr) + plen]
                if len(p) < SEED or lo >= hi:
                    continue
                sc, j = locate(P, idx, p, lo, hi)
                if j is not None and sc >= args.min_score:
                    hits.append((sc, dm.to_real(times[j]), fr))
            if not hits:
                skipped.append(f"{s['session_id']}|#{g['index']}")
                prev = max(prev or 0.0, st)
                continue
            # ⚠️ 命中時間是「**探針**所在的位置」，不是「答案的開頭」。探針在 frac 處，
            # 對應音節大約在答案開頭後 `fr*len(a)/RATE` 秒處，所以要把這一段推回去。
            # （第一版直接用命中時間當錨點 → 選到 0.85 探針時錨點落在答案 85% 之後，
            #   listen_check 立刻爆 845 個例外。）
            best = None
            for want in ANCHOR_FRACS:                 # 優先 0%，不夠好才退 0.25 / 0.5
                c = [h for h in hits if h[2] == want and h[0] >= args.min_score]
                if c:
                    best = min(c, key=lambda h: h[1])
                    break
            if best is None:
                skipped.append(f"{s['session_id']}|#{g['index']}")
                prev = max(prev or 0.0, st)
                continue
            sc, t, fr = best
            new = round(max(0.0, t - args.lead), 2)
            if abs(new - st) >= args.min_shift:
                out[f"{s['session_id']}|#{g['index']}"] = new
                d = new - st
                print(f"  #{g['index']:<5} {st:>9.2f} → {new:>9.2f} {d:+8.2f}s "
                      f"sc={sc:.2f} frac={fr}  {(a[:16])}")
            prev = new if abs(new - st) >= args.min_shift else max(prev or 0.0, st)
    print(f"\n候選 {len(out)} 筆；跳過（內容定位不到）{len(skipped)} 筆；無整場轉錄 {len(nofile)} 場")
    if skipped:
        print('跳過:', ' '.join(skipped))
    if nofile:
        print('缺轉錄:', ' '.join(nofile))
    if args.out:
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n',
                                  encoding='utf-8')
        print('→', args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())