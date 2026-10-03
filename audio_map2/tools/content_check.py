#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""內容定位檢查（SKILL §5.5，不可省）：用**整場**字級轉錄獨立估出每段答案內文的
真實位置，和 JSON 的 `start/end` 對照。

兩種輸出：
1. **首內文探針（0%）** → 估出「本段第一句真正被唸出來的時刻」`t0`。與 `start` 差
   >`--tol` → 該段錨點有問題（整段錯位、或音檔沒唸出 Word 的首句如人名）。
2. **中／後探針（50%／85%）** → 確認內文確實落在自己窗內（抓「錨到音檔裡重複出現兩次
   的同一句」那類整段錯位，2025-01-17 `wechat #3` 錯 56s）。

⚠️ 整場轉錄中段會漂 2–3s（VAD 視窗漂移），`--tol` 預設 3.5s；**檔頭 0–5s 反而準**
（短窗 VAD 會丟掉檔頭），所以開場錨點以這裡的 `t0` 為準。

用法:
    .venv/bin/python content_check.py --month 2024-12 [--session SID] [--tol 3.5]
                                     [--all] [--min-score 0.6]
"""
import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))
from driftmap import DriftMap  # noqa: E402
from first_char_audit import first_word  # noqa: E402
try:
    from pypinyin import lazy_pinyin, Style
    HAVE_PY = True
except Exception:                                                      # noqa: BLE001
    HAVE_PY = False

STRIP = re.compile(r'[\s　。，、；：？！…—～「」『』（）()《》〈〉,.!?:;\'"0-9]+')
SEED, PROBE = 4, 16


def syl(s):
    return [x for x in lazy_pinyin(s, style=Style.NORMAL, errors=lambda x: x) if x] \
        if HAVE_PY else list(s)


def norm(t):
    return STRIP.sub('', t or '')


def build_index(P):
    idx = {}
    for i in range(len(P) - SEED + 1):
        idx.setdefault(tuple(P[i:i + SEED]), []).append(i)
    return idx


def locate(P, idx, probe, lo, hi, span=50):
    """回傳 (score, pos)：probe 音節在 P[lo:hi] 的最佳模糊匹配起點。"""
    q = syl(probe)
    if len(q) < SEED:
        return 0.0, None
    cands = set()
    for off in range(0, max(1, len(q) - SEED + 1)):
        for i in idx.get(tuple(q[off:off + SEED]), []):
            for d in range(-span, span + 1):
                j = i + d - off
                if lo <= j <= hi:
                    cands.add(j)
    best = (0.0, None)
    L = len(q)
    for j in cands:
        w = P[j:j + L + 3]
        if not w:
            continue
        sc = SequenceMatcher(None, q, w[:L]).ratio()
        if sc > best[0]:
            best = (round(sc, 3), j)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--session', default='')
    ap.add_argument('--date', default='')
    ap.add_argument('--tol', type=float, default=3.5)
    ap.add_argument('--min-score', type=float, default=0.6)
    ap.add_argument('--all', action='store_true', help='全部印出（不只印有問題的）')
    args = ap.parse_args()

    cdir = Path(args.cache or f'/tmp/am2_{args.month}') / 'full'
    data = json.load(open(REPO / 'audio_map2' / f'{args.month}.json', encoding='utf-8'))
    tally = {}
    for s in data['sessions']:
        if args.session and s['session_id'] != args.session:
            continue
        if args.date and s.get('date') != args.date:
            continue
        fn = cdir / f"{s['session_id']}.json"
        if not fn.exists():
            print(f'[SKIP] 無整場轉錄: {s["session_id"]}')
            continue
        full = json.load(open(fn, encoding='utf-8'))
        chars = full['chars']
        P, times = syl(''.join(c for _t, c in chars)), [t for t, _c in chars]
        idx = build_index(P)
        dm = DriftMap.for_session(cdir.parent, s['session_id'])
        print(f'### {s["session_id"]}  整場轉錄最大漂移 +{dm.max_offset:.2f}s（已校正）') \
            if args.all else None

        def probe_at(a, frac, pad=45.0, skip=0):
            p = a[skip + int(len(a) * frac):skip + int(len(a) * frac) + PROBE]
            if len(p) < SEED:
                return 0.0, None
            lo = max(0, next((i for i, t in enumerate(times) if t >= times[0] + pad), 0))
            hi = min(len(P), next((i for i, t in enumerate(times) if t > times[-1] - pad), len(P)))
            return locate(P, idx, p, lo, hi)

        rows = []
        for g in s['segments']:
            if g.get('start') is None or g.get('end') is None:
                continue
            a = norm(g.get('answer_text') or '')
            if len(a) < PROBE:
                continue
            st = g['start']
            # 0% 探針**跳過首詞**：人名常被 ASR 聽歪（恒河沙丫→红河沙洋），
            # 含名字的探針會整段滑到名字後面的正文，量到「正文時刻」而不是「首字時刻」，
            # 造成假的 +8s 偏差（2024-12-09-wechat #28）。跳過首詞後量到的是
            # 「本段第一句正文的時刻」——必須 **不晚於** `start`，否則就是整段錯位。
            fwlen = len(norm(first_word(g.get('answer_text') or '')))
            s0, j0 = probe_at(a, 0.0, skip=fwlen)
            s5, j5 = probe_at(a, 0.5)
            s8, j8 = probe_at(a, 0.85)
            t0 = dm.to_real(times[j0]) if j0 is not None else None
            t5 = dm.to_real(times[j5]) if j5 is not None else None
            t8 = dm.to_real(times[j8]) if j8 is not None else None
            bad = []
            # 方向性：**內容必須不晚於 start**。`start > t0 + tol` 才算錯位
            # （內文已經在窗外＝整段錯位／錨太晚）。反過來 `t0 > st` 是正常情況——
            # 人名常沒被唸出，內文自然晚一點，那不是錯。
            if t0 is not None and s0 >= args.min_score and st > t0 + args.tol:
                bad.append(f'首內文 t={t0:.2f} 早於 start({st:.2f}) {st - t0:+.2f}s → start 過晚')
            for tag, t in (('中', t5), ('後', t8)):
                if t is None:
                    continue
                sc = {'中': s5, '後': s8}[tag]
                if sc < args.min_score:
                    continue
                if not (st - args.tol <= t <= g['end'] + args.tol):
                    bad.append(f'{tag}內文 t={t:.2f} 超出 [{st:.2f},{g["end"]:.2f}]')
            key = 'BAD' if bad else 'OK'
            tally[key] = tally.get(key, 0) + 1
            if bad or args.all:
                rows.append((g['index'], st, g['end'], s0, t0, s5, t5, s8, t8, bad))
        if not rows:
            continue
        print(f'\n### {s["session_id"]}')
        for idxn, st, en, s0, t0, s5, t5, s8, t8, bad in rows:
            print(f"  #{idxn:<4} [{st:9.2f},{en:9.2f}] 首: {s0:.2f}@{t0 if t0 is None else f'{t0:.2f}'}"
                  f"  中: {s5:.2f}@{t5 if t5 is None else f'{t5:.2f}'}"
                  f"  後: {s8:.2f}@{t8 if t8 is None else f'{t8:.2f}'}"
                  + ('   ✗ ' + '; '.join(bad) if bad else ''))
    print('\n統計:', json.dumps(tally, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    raise SystemExit(main())
