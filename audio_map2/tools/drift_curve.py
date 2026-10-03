#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整場轉錄的**時間漂移校準**：用 SRT cue 當參考點量出「整場轉錄時刻 − SRT 時刻」
隨位置的變化，把整場轉錄的時間軸校正回真實時間。

為什麼需要：SKILL §4 說整場轉錄中段會漂 2–3s，**2024-12 實測是累積型漂移**——
到檔案中後段可以差 10–25s（2024-12-10-wechat 在 1640s 差 ~4s、2024-12-09-wechat 在
4700s 幾乎不漂，但 2600s 差 ~9s）。不做校正就不能用整場轉錄判斷任何絕對時間。

做法：每隔 ~45s 取一個 SRT cue，拿前 10 個字在整場轉錄的拼音音節序列上模糊定位，
得到 `offset = tx_t − srt_start`；再對 (SRT 時刻, offset) 做單調插值 → 任意時刻的漂移量。

輸出：`<cache>/full/<sid>_drift.json` = `[[srt_t, offset], ...]`（單調遞增）

用法:
    .venv/bin/python drift_curve.py --month 2024-12
"""
import argparse
import bisect
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from content_check import build_index, locate, norm, syl  # noqa: E402
from first_char_audit import parse_srt_raw  # noqa: E402

STEP_MS = 45000
CUE_CHARS = 10
MIN_SCORE = 0.62
MAX_OFF = 45.0        # 離群門檻：|off| 超過這個不可能是同一段文字
SPAN = 60          # 允許的前後搜尋範圍（音節）


def build_curve(sid, cues, P, times):
    """回傳 [[srt_t, offset], ...]（offset 單調不減、且每單位時間的增長有上限）。

    量測：每隔約一個 cue 取 SRT 文字在整場轉錄上的位置 → `off = tx_t − srt_t`。
    先濾掉明顯離群的匹配（|off| 過大＝根本不是同一段文字），再用**斜率上限的
    單調迴歸**（PAVA）把零散點擬合成平滑曲線——直接用 running max 會被單一離群點
    一次抬高後就再也降不下來（2024-12-10-tieba 實測整條曲線被壓成 +13.16s 常數）。
    """
    raw = []
    for i, (srt_t, _b, _t) in enumerate(cues):
        txt = norm(''.join(t for _a, _b, t in cues[i:i + 2]))
        if len(txt) < CUE_CHARS:
            continue
        q = syl(txt[:CUE_CHARS])
        if len(q) < 4:
            continue
        centre = next((k for k, t in enumerate(times) if t >= srt_t), len(P))
        lo, hi = max(0, centre - 120), min(len(P), centre + 120)
        sc, j = locate(P, _IDX, txt[:CUE_CHARS], lo, hi, span=40)
        if j is None or sc < MIN_SCORE:
            continue
        off = times[j] - srt_t
        if abs(off) > MAX_OFF:            # 離群：不可能是同一段文字
            continue
        raw.append((round(srt_t, 2), off))
    if not raw:
        return []
    raw.sort()

    # 以固定時間間隔取樣（避免長靜音段抽樣過密）
    if not times or not raw:
        return []
    step = max(20.0, (times[-1] - times[0]) / 60.0)
    buckets = []
    for srt_t, off in raw:
        if not buckets or srt_t - buckets[-1][0] >= step:
            buckets.append([srt_t, [off]])
        else:
            buckets[-1][1].append(off)
    pts = [[b[0], sorted(b[1])[len(b[1]) // 2]] for b in buckets]   # 中位數抗離群

    # 單調迴歸（PAVA，非遞減）+ 斜率上限：每 step 秒最多增加 RATE 秒
    RATE = 0.06
    level = [p[1] for p in pts]
    i = 0
    while i < len(level) - 1:
        if level[i] > level[i + 1] + 1e-6:
            m = (level[i] + level[i + 1]) / 2
            level[i] = level[i + 1] = m
            i = max(0, i - 1)
        else:
            i += 1
    for i in range(len(level) - 1):
        dt = pts[i + 1][0] - pts[i][0]
        if level[i + 1] - level[i] > RATE * dt:
            level[i + 1] = level[i] + RATE * dt
    return [[pts[i][0], round(level[i], 2)] for i in range(len(pts))]


_IDX = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    args = ap.parse_args()
    global _IDX

    cdir = Path(args.cache or f'/tmp/am2_{args.month}') / 'full'
    data = json.load(open(REPO / 'audio_map2' / f'{args.month}.json', encoding='utf-8'))
    for s in data['sessions']:
        fn = cdir / f"{s['session_id']}.json"
        if not fn.exists():
            print(f'[SKIP] {s["session_id"]}')
            continue
        full = json.load(open(fn, encoding='utf-8'))
        chars = full['chars']
        P, times = syl(''.join(c for _t, c in chars)), [t for t, _c in chars]
        _IDX = build_index(P)
        cues, off = [], 0.0
        for part in s['media_parts']:
            cues += [(a + off, b + off, t) for a, b, t in parse_srt_raw(part['srt_file'])]
            off += float(part.get('duration_est') or 0.0)
        curve = build_curve(s['session_id'], cues, P, times)
        out = cdir / f"{s['session_id']}_drift.json"
        out.write_text(json.dumps(curve), encoding='utf-8')
        if curve:
            print(f'{s["session_id"]:<22} 參考點 {len(curve):3d}  漂移 '
                  f'{curve[0][1]:+.2f}s @{curve[0][0]:.0f} → {curve[-1][1]:+.2f}s '
                  f'@{curve[-1][0]:.0f}')
        else:
            print(f'{s["session_id"]:<22} 無參考點')


if __name__ == '__main__':
    raise SystemExit(main())
