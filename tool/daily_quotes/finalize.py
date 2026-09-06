#!/usr/bin/env python3
"""合併 AI 評分 → 產生根目錄 daily_quotes.json（首頁每日複習用）。"""
import json, glob, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
TD = ROOT / 'tool/daily_quotes'

sample = json.load(open(TD / 'candidates_sample.json'))
scores = {}
for f in sorted(glob.glob(str(TD / 'scores/batch_*.json'))):
    for s in json.load(open(f)):
        scores[s['idx']] = s['score']
print(f'已評分 {len(scores)} / {len(sample)}')

scored = [(scores[i], it) for i, it in enumerate(sample) if i in scores]
scored.sort(key=lambda t: -t[0])
dist = collections.Counter(s for s, _ in scored)
print('分數分佈:', dict(sorted(dist.items(), reverse=True)))

# 兩來源比例盡量均衡：先各取高分，再補到 500
TARGET = 400
MIN_SCORE = 7
picked, count_w, count_e = [], 0, 0
for s, it in scored:
    if s < MIN_SCORE: break
    cap = int(TARGET * 0.7)  # 單一來源上限 70%，保留混合度
    if it['source'] == 'wenda2' and count_w >= cap: continue
    if it['source'] == 'ebook' and count_e >= cap: continue
    picked.append((s, it))
    if it['source'] == 'wenda2': count_w += 1
    else: count_e += 1
    if len(picked) >= TARGET: break

quotes = [{'text': it['text'], 'url': it['url'], 'title': it['title'],
           'source': it['source'], 'score': s} for s, it in picked]
out = {'quotes': quotes}
json.dump(out, open(ROOT / 'daily_quotes.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print(f"輸出 daily_quotes.json：{len(quotes)} 條 (wenda2={count_w}, ebook={count_e})，"
      f"最低分 {min(q['score'] for q in quotes) if quotes else '-'}")
