#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整場轉錄時間軸的漂移校正（配合 `drift_curve.py` 產出的 `*_drift.json`）。

整場 FunASR 轉錄的時間戳會隨位置累積漂移（2024-12 實測：09-tieba 僅 +1.6s，
但 12-wechat 到檔尾 +32.4s）。把整場轉錄的時刻換算回真實時間：

    real_t = tx_t − offset(real_t)      （offset 單調不減，線性內插）

用法:
    from driftmap import DriftMap
    dm = DriftMap.load('/tmp/am2_2024-12/full/2024-12-12-wechat_drift.json')
    real = dm.to_real(tx_t)
"""
import bisect
import json
from pathlib import Path


class DriftMap:
    def __init__(self, pts):
        self.t = [p[0] for p in pts]
        self.o = [p[1] for p in pts]

    @classmethod
    def load(cls, path):
        p = Path(path)
        if not p.exists():
            return cls([])
        return cls(json.load(open(p, encoding='utf-8')))

    @classmethod
    def for_session(cls, cache, sid):
        return cls.load(Path(cache) / 'full' / f'{sid}_drift.json')

    def to_real(self, tx_t):
        if not self.t:
            return tx_t
        if tx_t <= self.t[0]:
            return tx_t - self.o[0]
        if tx_t >= self.t[-1]:
            return tx_t - self.o[-1]
        i = bisect.bisect_left(self.t, tx_t)
        t0, t1 = self.t[i - 1], self.t[i]
        o0, o1 = self.o[i - 1], self.o[i]
        f = 0.0 if t1 == t0 else (tx_t - t0) / (t1 - t0)
        return tx_t - (o0 + f * (o1 - o0))

    @property
    def max_offset(self):
        return max(self.o) if self.o else 0.0
