#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""掃描「首詞在視窗內被唸了不只一次」的所有邊界——找出**第一次**出現被錯過的段。

SKILL §2 + 2025-01-15 golden：人名被唸兩次時要看清楚兩次的位置。若第一次是
「叫名 ＋（讀回題幹或先答完上一題）」、第二次才是「叫名 ＋ 本題答案」，錨點應取第二次；
但若答案文字本身就以人名開頭、第一次就是本段開頭，錨點應取第一次。
`batch_analyze.find_word` 的 `adj = score − 0.02·|t−start|` 懲罰**偏向離舊 start 近的那次**，
可能因此跳過了真正的第一次——本腳本把所有候選攤開供人工判讀。

用法:
    .venv/bin/python dup_scan.py --month 2024-12 [--min-score 0.75]
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from batch_analyze import find_word  # noqa: E402


def all_hits(chars, word, start, lo=-9.0, hi=6.0, min_score=0.7):
    """在視窗內找出 word（或其變形）所有達標的匹配起點。"""
    out = []
    for cand in [word] + [v for v in __import__('first_char_audit').variants(word)
                          if v != word]:
        L = len(cand)
        if L < 2 or L > len(chars):
            continue
        for i, (t, _c) in enumerate(chars):
            if not (start + lo <= t <= start + hi):
                continue
            if i + L > len(chars):
                break
            win = ''.join(c for _tt, c in chars[i:i + L])
            from batch_analyze import fuzzy
            sc = fuzzy(cand, win)
            if sc >= min_score and chars[min(i + L, len(chars) - 1)][0] - t <= 4.0:
                out.append((round(t, 2), round(sc, 2), win))
    # 同一時刻只留分數最高者
    best = {}
    for t, sc, w in out:
        if t not in best or sc > best[t][0]:
            best[t] = (sc, w)
    # **聚類**：滑動窗會讓同一次出現產生多個 ±1s 的匹配（'下一个问题'／'二个问题身'
    # 是同一處），先按 1.2s 聚成「一次出現」，只留分數最高的那個當該次的代表。
    items = sorted((t, sc, w) for t, (sc, w) in best.items())
    clusters = []
    for t, sc, w in items:
        if clusters and t - clusters[-1][-1][0] <= 1.2:
            clusters[-1].append((t, sc, w))
        else:
            clusters.append([(t, sc, w)])
    return [max(c, key=lambda x: x[1]) for c in clusters]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--min-score', type=float, default=0.75)
    ap.add_argument('--window', type=float, default=9.0)
    args = ap.parse_args()

    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    fx = {(f['session_id'], f['label']): f
          for f in json.load(open(cdir / 'fixes.json', encoding='utf-8'))}
    n = 0
    for f in sorted(cdir.glob('*.json')):
        if not isinstance(json.load(open(f, encoding='utf-8')), dict):
            continue
        r = json.load(open(f, encoding='utf-8'))
        if 'start' not in r:
            continue
        st, w = r['start'], r['first_word']
        if len(w) < 2:
            continue
        hits = all_hits((r.get('opus') or {}).get('chars') or [], w, st,
                        lo=-args.window, min_score=args.min_score)
        if len(hits) < 2:
            continue
        chosen = (fx.get((r['session_id'], r['label'])) or {}).get('new_start')
        n += 1
        print(f"{r['session_id']:<20}{r['label']:>9} 提案={chosen}  fw={w!r}")
        for t, sc, txt in hits:
            mark = ' ← 採用' if chosen is not None and abs(t - chosen) < 0.25 else ''
            print(f'      {t:9.2f}  sc={sc:.2f}  {txt!r}{mark}')
        print(f"      A: {r['answer_head'][:56]!r}")
    print(f'\n視窗內首詞出現 ≥2 次的邊界：{n}')


if __name__ == '__main__':
    raise SystemExit(main())
