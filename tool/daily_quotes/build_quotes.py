#!/usr/bin/env python3
"""每日複習候選抽取：從 ebook/ 與 wenda2_ebook/ 的 search_index 過濾出優質候選。

用法：
  python3 build_quotes.py            # 規則過濾，輸出 candidates.json（供 AI 評分）
  python3 build_quotes.py --stats    # 只印統計

資料流：
  wenda2_ebook/search_index_trad.json  (answer 條目)
  ebook/search_index_trad.json         (content + answer 條目)
      → 規則過濾 → candidates.json → (AI 評分) → daily_quotes.json（repo 根目錄）
"""
import json, re, sys, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MIN_LEN, MAX_LEN = 60, 400  # 展開全文理想長度

# 黑名單：一看就是壞候選
BAD_PATTERNS = [
    re.compile(p) for p in [
        r'^[可以的對是不是嗯好]+[。！!]?$',           # 單字敷衍回答
        r'^\s*阿彌陀佛\s*$',
        r'[?？]{3,}',                                # 亂碼式的問號
        r'\[音[频頻]|\[video\]|<img',
        r'http[s]?://',
        r'不完整|待補|TODO',
        r'發表於\s*\d{4}',                            # 純時間戳行
    ]
]

def normalize(s: str) -> str:
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def clean(s: str) -> str:
    # 去掉 answer 開頭常見的 "Taiguanglin " 署名
    s = normalize(s)
    s = re.sub(r'^Taiguanglin[ 　]*', '', s)
    return s

def date_prefix_len(s: str):
    """回傳開頭日期/時間戳 hash 的長度（通常 <20 字元），無則 None。"""
    m = re.match(r'^[0-9a-f]{8}\s*[—\-–]?\s*\d{4}[-/年]', s)
    if m: return m.end()
    return None

def ok(content: str) -> bool:
    if not (MIN_LEN <= len(content) <= MAX_LEN):
        return False
    for p in BAD_PATTERNS:
        if p.search(content):
            return False
    # 中日韓字元比例要夠高（排除純經文編號或英數雜訊）
    cjk = sum(1 for ch in content if '一' <= ch <= '鿿')
    if cjk / len(content) < 0.6:
        return False
    return True

def collect():
    items = []
    seen = set()

    # wenda2_ebook: 只取 answer
    for x in json.load(open(ROOT / 'wenda2_ebook/search_index_trad.json')):
        if x.get('type') != 'answer':
            continue
        c = clean(x['content'])
        d = date_prefix_len(c)
        if d is not None:
            c = normalize(c[d:])
        if not ok(c):
            continue
        h = hashlib.md5(c.encode()).hexdigest()
        if h in seen: continue
        seen.add(h)
        items.append({
            'text': c, 'kind': 'quote', 'source': 'wenda2',
            'url': f"wenda2_ebook/{x['url']}",
            'title': x.get('title', ''),
        })

    # ebook: content(講經段落) 與 answer
    for x in json.load(open(ROOT / 'ebook/search_index_trad.json')):
        if x.get('type') not in ('content', 'answer'):
            continue
        c = clean(x['content'])
        if not ok(c):
            continue
        h = hashlib.md5(c.encode()).hexdigest()
        if h in seen: continue
        seen.add(h)
        items.append({
            'text': c, 'kind': 'quote', 'source': 'ebook',
            'url': f"ebook/{x['url']}",
            'title': x.get('title', ''),
        })
    return items

def main():
    items = collect()
    by_src = {}
    for it in items:
        by_src[it['source']] = by_src.get(it['source'], 0) + 1
    print(f'候選總數: {len(items)}  {by_src}')
    lens = sorted(len(i['text']) for i in items)
    if lens:
        print(f'長度 p10/p50/p90: {lens[len(lens)//10]}/{lens[len(lens)//2]}/{lens[len(lens)*9//10]}')
    if '--stats' not in sys.argv:
        out = ROOT / 'tool/daily_quotes/candidates.json'
        json.dump(items, open(out, 'w'), ensure_ascii=False, indent=1)
        print(f'已輸出 {out}')

if __name__ == '__main__':
    main()
