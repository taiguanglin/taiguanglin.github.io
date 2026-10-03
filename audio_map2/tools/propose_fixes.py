#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""依 `batch_anchor.py` 的字級快取產生候選修正（`fixes.json`），供逐場人工過目後套用。

信任規則（不滿足就標 `weak`，不自動改，交人工判讀）:
  - 匹配分數 `score >= MIN_SCORE`
  - **雙解碼器都聽到首詞**，且兩者 onset 差 `<= 0.15s`（SKILL §3：絕對時間只信雙解碼器一致；
    2025-01-16 實測兩個解碼器可能一個整段丟字，所以「不一致」時取較早者並標 `XDEC`）

候選新值 = `min(onset_opus, onset_mp3) - 0.02`（留 20ms 給字頭輔音，不截首音）。

用法:
    .venv/bin/python propose_fixes.py --month 2024-12 [--out /tmp/am2_2024-12/fixes.json]
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from batch_analyze import find_word, classify  # noqa: E402
from first_char_audit import first_word  # noqa: E402

MIN_SCORE = 0.62
BACK = 0.02          # 起音留白：不截首字首音
PREFIX_K = (3, 5, 8, 12, 16, 20)   # 退級探針：首詞沒被唸出時改用較長的答案前綴
PREFIX_MIN = 0.72
PUNCT = '，。！？、；：…—～「」『』（）()《》〈〉,.!?:;’“” '
# 純語氣／墊字：音檔在答案正文前常有這些，但它們不在 Word 文字裡，錨點要落在它們**之後**
# 的那個字，才算「回答首字 ＝ 音檔首字」（實測 12-11-wechat #9 嗯、12-wechat #33 啊）。
FILLER = set('嗯呃啊哦唉喂噢喔诶欸唄哈')
# 虛詞／語助：VAR 變形有時會在前面塞一個助詞（實測 `第二个问题` 的變形
# `的啊第二个问`），把錨點拉到真正的首詞之前 1.7s（2024-12-09-wechat #3）。
# 命中窗第一個字是這些、而答案首詞並不以它開頭時 → 前移到窗內第一個實字。
FUNCTION = set('的了着呢吧呀嘛')


def norm_probe(t):
    return ''.join(ch for ch in (t or '') if ch not in PUNCT)[:24]


def drop_filler(chars, to, flat):
    """錨點落在語氣墊字／虛詞上、而該字不在答案文字裡 → 前移到第一個真正對應的字。"""
    bad = FILLER | FUNCTION
    for tag in ('opus', 'mp3'):
        seq = chars.get(tag) or []
        for i, (t, c) in enumerate(seq):
            if abs(t - to) < 0.02:
                if c in bad and not flat.startswith(c):
                    nxt = next((tt for tt, cc in seq[i + 1:i + 8] if cc not in bad), None)
                    return nxt if nxt is not None else to
                return to
    return to


def pick(chars, probe, start, min_score):
    """opus/mp3 都要找；分數差 >0.10 取較有把握的，相近才取較早 onset。"""
    m = {t: find_word(chars.get(t) or [], probe, start, use_var=False)
         for t in ('opus', 'mp3')}
    hit = {t: v for t, v in m.items() if v and v[0] >= min_score}
    if not hit:
        return None
    best = max(v[0] for v in hit.values())
    top = [t for t in hit if hit[t][0] >= best - 0.10]
    return {'score': round(best, 3),
            'onset': min(hit[t][1] for t in top),
            'matched': {t: hit[t][2] for t in top},
            'probe': probe}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--out', default='')
    ap.add_argument('--min-score', type=float, default=MIN_SCORE)
    ap.add_argument('--session', default='')
    args = ap.parse_args()

    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    out = Path(args.out or cdir / 'fixes.json')
    data = json.load(open(REPO / 'audio_map2' / f'{args.month}.json'))

    by_sid = {s['session_id']: s for s in data['sessions']}
    fixes, weak = [], []

    def _ord(lb):
        return 0 if lb == 'opening' else (9999 if lb == 'closing' else int(lb.lstrip('#')))

    for f in sorted(cdir.glob('*.json')):
        if f.resolve() == out.resolve():
            continue
        r = json.load(open(f, encoding='utf-8'))
        if not isinstance(r, dict) or 'start' not in r:
            continue
        sid, lb, st = r['session_id'], r['label'], r['start']
        if args.session and sid != args.session:
            continue
        m = {t: find_word((r.get(t) or {}).get('chars') or [], r['first_word'], st)
             for t in ('opus', 'mp3')}
        scores = [v[0] for v in m.values() if v]
        chars = {t: (r.get(t) or {}).get('chars') or [] for t in ('opus', 'mp3')}
        basis = 'first_word'
        if not scores:
            rec = {'session_id': sid, 'label': lb, 'start': st, 'verdict': '???',
                   'first_word': r['first_word'], 'answer_head': r['answer_head'],
                   'weak': True, 'basis': 'none'}
            weak.append(rec)
            continue
        best_score = max(scores)
        # 解碼器取捨：分數差 >0.10 取較有把握的那個（它的切字邊界較可信）；
        # 分數相近才依 SKILL §3 取**較早**的 onset。
        top = [t for t in m if m[t] and m[t][0] >= best_score - 0.10]
        onsets = {t: m[t][1] for t in top}
        to = drop_filler(chars, min(onsets.values()), norm_probe(r.get('answer_head') or ''))
        agree = len([t for t in m if m[t]]) == 2 and \
            abs(m['opus'][1] - m['mp3'][1]) <= 0.15
        delta = round(st - to, 3)
        new = round(to - BACK, 3)
        full_ok = all(m[t][4] for t in top)
        # R1：首詞 ≤2 字容易撞字（「雲」撞「下一個問」、「覺」撞 3.6s 後的「我覺得」、
        #     「威」撞「問」）。但**拼音全中的**那種（慧裕→惠譽 1.0、醉日→這一日 1.0）
        #     還是可信的首詞位置，直接採用並標人工複核；其餘走下面的退級探針。
        # R2：分數 <0.75 一律人工（「好了」撞上 3.8s 前的「做了」是 0.6）。
        short = len(r['first_word']) <= 2
        # R5（2024-11 實測）：`full_ok`（命中窗逐字相符）太嚴時會把**人名明明有唸、
        # 只是被 ASR 聽成別的字**的情況整個踢去退級探針，而退級探針的命中窗起點是
        # 「匹配開始的位置」——常常落在**上一段句尾**（实测 `11-11 #39 聖輝→盛輝`：
        # 首詞分數 1.0 卻被判 weak，prefix3 命中「說聖輝」把錨點拉到 3.3s 前的
        # 上一句尾巴）。拼音 1.0 表示 ASR 聽到的就是同一個詞，取其 onset 才是對的。
        # 單字詞仍有撞字風險（`覺` 撞「我覺得」），維持要 `full_ok`。
        strong = best_score >= 0.9 and len(r['first_word']) >= 2
        trusted = ((best_score >= args.min_score and full_ok
                    and (not short or best_score >= 0.9)
                    and best_score >= 0.75)
                   or strong)
        if not trusted:
            # 退級探針：首詞在音檔裡沒被唸／唸得很不像時，用較長的答案前綴去找
            # 「本題第一個真的被唸出來的字」。命中窗的起點就是該字 onset。
            flat = norm_probe(r.get('answer_head') or '')
            for k in PREFIX_K:
                if k > len(flat):
                    break
                hit = pick(chars, flat[:k], st, PREFIX_MIN)
                if hit and -6.0 <= hit['onset'] - st <= 6.0:
                    to = drop_filler(chars, hit['onset'], flat)
                    delta = round(st - to, 3)
                    new = round(to - BACK, 3)
                    best_score = hit['score']
                    basis = f'prefix{k}'
                    trusted = True
                    onsets = {'probe': round(hit['onset'], 2)}
                    full_ok = True
                    break
        rec = {
            'session_id': sid, 'label': lb, 'start': st, 'new_start': new,
            'delta': delta, 'verdict': classify(delta) + ('' if agree else '+XDEC'),
            'score': round(best_score, 3), 'onsets': {k: round(v, 2) for k, v in onsets.items()},
            'matched': {k: m[k][2] for k in top} if basis == 'first_word' else hit['matched'],
            'basis': basis, 'full_match': full_ok,
            'first_word': r['first_word'], 'answer_head': r['answer_head'],
            'weak': not trusted, 'changes': abs(new - st) >= 0.05,
        }
        fixes.append(rec)
        if not trusted:
            weak.append(rec)

    def _k(x):
        lb = x['label']
        return (x['session_id'], 0 if lb == 'opening' else (9999 if lb == 'closing'
                                                            else int(lb.lstrip('#'))))

    fixes.sort(key=_k)
    weak.sort(key=_k)
    out.write_text(json.dumps(fixes, ensure_ascii=False, indent=1), encoding='utf-8')

    n_chg = sum(1 for x in fixes if x['changes'])
    print(f'[{args.month}] 邊界 {len(fixes)}；需改 ≥50ms：{n_chg}；weak（分數<{args.min_score}）：{len(weak)}')
    print(f'→ {out}')
    from collections import Counter
    print('判定分布:', dict(Counter(x['verdict'] for x in fixes)))
    for x in weak:
        print(f"  WEAK {x['session_id']:<20}{x['label']:>9} sc={x.get('score')} "
              f"fw={x['first_word']!r} Δ={x.get('delta')}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
