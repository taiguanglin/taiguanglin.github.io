#!/usr/bin/env python3
"""選出 1095 條每日精選，輸出根目錄 daily_quotes.json。

不需 subagent：以既有的 AI 評分（2400 條，score>=7 共 361 條）為品質骨幹，
其餘未評分候選用「規則式可讀性啟發」排序補足到 1095 條（並於日後有 AI 評分
容量時可替換後段）。

選取規則：
  1. 骨架：candidates_sample + scores 中 score>=7 的 361 條，按分數降冪。
  2. 補充：candidates.json 中「尚未被評到」的候選，依 heuristic() 降冪，
     補到 1095 條；單一來源（ebook）不超過 70%。
"""
import json, re, hashlib, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TD = ROOT / 'tool/daily_quotes'

TARGET = 1095
MIN_SCORE = 7
SRC_CAP = 0.70

TERMINAL = re.compile(r'[。！？!?」”…]$')
LEAD_TS = re.compile(r'^\S{2,20}\s+20\d\d[-/.年]\d')
LEAD_NICK = re.compile(r'^[一-鿿\w]{2,8}[，,、]\s*')   # 開頭「暱稱，」型（問答把提問兜進去的片段）
LEAD_TIME = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?')     # 開頭時間戳
LEAD_ASCII = re.compile(r'^[A-Za-z_][A-Za-z0-9_ ]{2,20}(，|,|：|:)')  # 開頭英文/代號暱稱
BAD_QQ = re.compile(r'[?？]{2,}')
NUM_RATIO = re.compile(r'\d')
TEACH = ('所以', '因此', '也就是', '其實', '就是說', '換句話', '總之', '記住',
         '關鍵', '重點', '簡單說', '簡單來', '反過來', '由此', '可見', '這就是')

# 原經文（文言段落）偵測：古典對話標記＋幾乎無現代語助詞
SCRIPT_DIALOG = re.compile(r'曰\s*[：:“"‘’]|佛[言問]|問曰|對曰|[師祖]曰|如是我聞|爾時|世尊|沙門')
STRONG_MODERN = '的了我你他這那們嗎呢吧啦呦噢啊呀耶'
def _strong_count(t): return sum(1 for ch in t if ch in STRONG_MODERN)
def is_scripture(t):
    """純原文經文段落（相對於師父的現代講解／翻譯）應排除。"""
    return bool(SCRIPT_DIALOG.search(t)) and _strong_count(t) <= 2

def heuristic(t):
    s = 4.0
    n = len(t)
    if 90 <= n <= 280: s += 3.0
    elif (60 <= n < 90) or (280 < n <= 400): s += 1.5
    else: s += 0.3
    if TERMINAL.search(t): s += 1.0
    if LEAD_TS.search(t): s -= 2.5
    if LEAD_NICK.match(t): s -= 2.5
    if LEAD_TIME.match(t): s -= 3.0
    if LEAD_ASCII.match(t): s -= 2.5
    if any(w in t for w in TEACH): s += 1.2
    if ('「' in t and '」' in t) or ('“' in t and '”' in t): s += 0.4
    if BAD_QQ.search(t): s -= 3.0
    if t.count('（') != t.count('）'): s -= 1.0
    if t.count('(') != t.count(')'): s -= 1.0
    digits = len(NUM_RATIO.findall(t))
    if digits / max(n, 1) > 0.25: s -= 1.0
    if t.startswith('問') or '：問' in t or t.rstrip().endswith('？'): s -= 1.2
    return round(max(0.0, min(10.0, s)), 2)

def main():
    sample = json.load(open(TD / 'candidates_sample.json'))
    pool = json.load(open(TD / 'candidates.json'))

    # 1) 骨架：AI score>=7（idx 對應 sample 位置）
    scored = []
    for i in range(24):
        for x in json.load(open(TD / f'scores/batch_{i:02d}.json')):
            if x['score'] >= MIN_SCORE:
                it = sample[x['idx']]
                if is_scripture(it['text']):
                    continue
                scored.append({
                    'text': it['text'], 'url': it['url'], 'title': it['title'],
                    'source': it['source'], 'score': x['score'],
                })
    scored.sort(key=lambda q: -q['score'])

    # 已被評分樣本涵蓋的 text（無論分數），避免補充重複；也涵蓋骨架本身
    seen = set()
    for it in sample:
        seen.add(hashlib.md5(it['text'].encode()).hexdigest())

    # 2) 補充：未評分候選，啟發式排序
    rest = []
    for it in pool:
        h = hashlib.md5(it['text'].encode()).hexdigest()
        if h in seen:
            continue
        if is_scripture(it['text']):
            continue
        rest.append((heuristic(it['text']), it['text'], it['url'], it['title'], it['source']))
    rest.sort(key=lambda r: -r[0])

    # 3) 合併，來源上限
    quotes = []
    count = collections.Counter()
    for q in scored:
        if count[q['source']] >= int(TARGET * SRC_CAP):
            rest.insert(0, (q['score'], q['text'], q['url'], q['title'], q['source']))
            continue
        quotes.append(q)
        count[q['source']] += 1
    for hs, text, url, title, source in rest:
        if len(quotes) >= TARGET:
            break
        if count[source] >= int(TARGET * SRC_CAP):
            continue
        quotes.append({'text': text, 'url': url, 'title': title,
                       'source': source, 'score': None, 'heuristic': hs})
        count[source] += 1

    # 若仍不足（來源上限卡住），放寬 crop 補足
    if len(quotes) < TARGET:
        for hs, text, url, title, source in rest:
            if len(quotes) >= TARGET:
                break
            if any(q['text'] == text for q in quotes):
                continue
            quotes.append({'text': text, 'url': url, 'title': title, 'source': source,
                           'score': None, 'heuristic': hs})

    # 批次排一下，「品質」靠前但保留日期輪播打散由前端負責
    out = []
    for q in quotes:
        out.append({k: q[k] for k in ('text', 'url', 'title', 'source')
                    if k in q and q[k] is not None})
        if q.get('score') is not None:
            out[-1]['score'] = q['score']
        if q.get('heuristic') is not None:
            out[-1]['heuristic'] = q['heuristic']

    json.dump({'quotes': out}, open(ROOT / 'daily_quotes.json', 'w'),
              ensure_ascii=False, separators=(',', ':'))
    ai = sum(1 for q in out if 'score' in q)
    hx = sum(1 for q in out if 'heuristic' in q)
    print(f'輸出 {len(out)} 條（AI 骨架 {ai}、啟發式補充 {hx}）')
    print('來源:', dict(collections.Counter(q['source'] for q in out)))

if __name__ == '__main__':
    main()