#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**收案測試（播放端視角）**：從 `start` 播下去，答案的開頭必須在 `--win` 秒內被唸到。

這是最貼近交付需求的驗收——使用者按播放鈕，耳朵聽到的第一個詞要等於段落答案的第一個詞。
做法：取答案文字正規化後的開頭 `N` 個字，在**字級時間軸 `[start-0.05, start+win]`**
內滑動比對（字面 + 拼音）。允許的 `win` 就是 SKILL §1.3 的「提前／延後 ≤1.5s」寬限，
外加語氣墊字與過渡語（音檔常在正文前多說半句「嗯，下一個問題，某某」）。

與 `first_char_audit.py` 的差別：稽核拿「答案首詞」去 **SRT cue** 裡找（cue 級、而且不看
`start` 落在哪個 cue——2025-01-17 有 31/31 個 `start` 全錯卻全報 OK）；這裡是**字級**
滑動比對，且方向相反：驗證的是「從 `start` 聽下去聽得到答案開頭」。兩者互補，都不可省。

用法:
    .venv/bin/python listen_check.py --month 2024-12 [--tol 0.6] [--win 2.5] [--ctx]
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from batch_analyze import fuzzy  # noqa: E402
from content_check import norm  # noqa: E402

N = 8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--tol', type=float, default=0.6)
    ap.add_argument('--win', type=float, default=6.0)
    ap.add_argument('--session', default='')
    ap.add_argument('--ctx', action='store_true')
    args = ap.parse_args()

    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    d = json.load(open(REPO / 'audio_map2' / f'{args.month}.json', encoding='utf-8'))
    bad, n, low = [], 0, 0
    for s in d['sessions']:
        if args.session and s['session_id'] != args.session:
            continue
        # opening／closing 可能整個不存在（2024-06/08/09、2025-02/03 共 18 個 session）
        seq = []
        if s.get('opening'):
            seq.append(('opening', s['opening'], s['opening'].get('text') or ''))
        seq += [(f"#{g['index']}", g, g.get('answer_text') or '') for g in s['segments']]
        if s.get('closing'):
            seq.append(('closing', s['closing'], s['closing'].get('text') or ''))
        for label, g, txt in seq:
            st = g.get('start')
            if st is None or not norm(txt):
                continue
            f = cdir / f"{s['session_id']}__{(label.lstrip('#') or 'opening')}.json"
            if not f.exists():
                continue
            r = json.load(open(f, encoding='utf-8'))
            want = norm(txt)[:N]
            if len(want) < 5:
                continue
            n += 1
            scores, heard, at = {}, {}, {}
            for tag in ('opus', 'mp3'):
                cs = (r.get(tag) or {}).get('chars') or []
                win = [(t, c) for t, c in cs if st - 0.05 <= t <= st + args.win]
                best = (0.0, None, '')
                for i in range(len(win)):
                    # 窗內字數常不足 N（人名逐字母唸、起音墊字多）→ 逐個長度都試一次，
                    # 取最高分；否則純粹因「窗口被截短」而誤判。
                    for L in range(3, N + 1):
                        cand = ''.join(c for _t, c in win[i:i + L])
                        if len(cand) < 3:
                            break
                        sc_ = fuzzy(want, cand)
                        if sc_ > best[0]:
                            best = (sc_, win[i][0], cand)
                scores[tag], at[tag], heard[tag] = best
            sc = min(scores.values())
            if sc < args.tol:
                bad.append((s['session_id'], label, st, sc, want, heard, at))
                low += 1
    print(f'可比 {n} 個邊界；從 start 播放後 {args.win}s 內聽不到答案開頭'
          f'（<{args.tol}）：{low}\n')
    for sid, label, st, sc, want, heard, at in bad:
        print(f'{sid:<20}{label:>9} start={st:9.3f} 分數={sc:.2f} '
              f'(opus@{at.get('opus')} mp3@{at.get('mp3')})')
        print(f'      答案開頭 {want!r}')
        print(f"      聽到 opus {heard.get('opus', '')!r}  mp3 {heard.get('mp3', '')!r}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())