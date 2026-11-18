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
import json, re, hashlib, collections, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TD = ROOT / 'tool/daily_quotes'

sys.path.insert(0, str(TD))
from scripture_filter import is_scripture  # noqa: E402  經文過濾的單一真相來源

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

# 經文過濾統一由 scripture_filter 處理（結構錨點 + 文言啟發式），此處不另立規則。

SOURCE_NAMES = {'ebook': 'ebook', 'wenda2_ebook': 'wenda2'}


def _current_entries_by_text():
    """{段落文字: [{url, title, source}, ...]}——現況電子書的段落定位表。

    來源：現況的搜尋索引（ebook/ 與 wenda2_ebook/ 的 search_index_trad.json），
    以 build_quotes.clean() 同一套正規化處理文字，才能與樣本／候選池對上。

    為什麼一定要「以文字重新定位」而不是信任既有 url：pid／答案錨點會隨電子書
    重建而換（章節合併、月份章重新分類都會搬動段落）。曾因此讓 91 條每日精選
    的「前往原文」落到已不存在的錨點，而舊稽核只看候選池、不看成品語意。
    """
    from build_quotes import clean
    out = collections.defaultdict(list)
    for sub in ('ebook', 'wenda2_ebook'):
        path = ROOT / sub / 'search_index_trad.json'
        if not path.exists():
            continue
        for x in json.load(open(path, encoding='utf-8')):
            if x.get('type') not in ('content', 'answer'):
                continue
            out[clean(x['content'])].append({
                'url': '%s/%s' % (sub, x['url']),
                'title': x.get('title', ''),
                'source': SOURCE_NAMES.get(sub, sub),
            })
    return out


def _pick_entry(entries, preferred_url=None):
    """從同一段文字的候選定位中挑一筆；優先沿用仍有效的既有 url。"""
    if not entries:
        return None
    if preferred_url:
        for entry in entries:
            if entry['url'] == preferred_url:
                return entry
    return entries[0]


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

    # 樣本檔（凍結的 AI 評分集）裡的 url 可能過期：pid 是「段落文字雜湊」
    # （md5(文字+段序)），電子書重建、區塊切分一改（例：把經文條目切成
    # 獨立區塊）就會整批換 pid → 連結斷掉，且經文過濾也失效（過期 url 不在
    # 現況的經文錨點裡 → 被誤當成不是經文而混進成品）。
    # 故以「文字」重新定位目前的名稱；定位不到者不進骨架。
    current = _current_entries_by_text()

    # 1) 骨架：AI score>=7（idx 對應 sample 位置）
    scored = []
    for i in range(24):
        for x in json.load(open(TD / f'scores/batch_{i:02d}.json')):
            if x['score'] >= MIN_SCORE:
                it = sample[x['idx']]
                entry = _pick_entry(current.get(it['text'], []))
                if not entry:
                    continue          # 文字已不存在於現況電子書 → 略過
                if is_scripture(ROOT, entry['url'], it['text']):
                    continue
                scored.append({
                    'text': it['text'], 'url': entry['url'],
                    'title': entry['title'] or it.get('title', ''),
                    'source': entry['source'], 'score': x['score'],
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
        # 同樣以「文字」對現況電子書重新定位：candidates.json 若未跟著重建，
        # 舊 url 不可信（會把斷鏈帶進成品）。
        entry = _pick_entry(current.get(it['text'], []), it.get('url'))
        if not entry:
            continue
        if is_scripture(ROOT, entry['url'], it['text']):
            continue
        rest.append((heuristic(it['text']), it['text'], entry['url'],
                     entry['title'] or it.get('title', ''), entry['source']))
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

def repair_urls():
    """只修正既有 daily_quotes.json 的過期網址，保留選文、順序與評分欄位。

    何時用：電子書重建後章節／錨點搬位，但不想讓 1,095 條選文與日期輪播
    順序整批重洗時。正常品質升級才走完整 main() 流程。

    定位方式：以「文字」對現況繁體搜尋索引重新定位段落；定位不到就失敗，
    絕不猜測或保留舊 url。
    """
    path = ROOT / 'daily_quotes.json'
    data = json.load(open(path, encoding='utf-8'))
    quotes = data['quotes']
    current = _current_entries_by_text()
    out = []
    changed_urls = changed_titles = changed_sources = 0
    unresolved = []
    for i, quote in enumerate(quotes):
        entry = _pick_entry(current.get(quote['text'], []), quote.get('url'))
        if not entry:
            unresolved.append((i, quote['text'][:60]))
            out.append(quote)
            continue
        fixed = dict(quote, url=entry['url'])
        if fixed['url'] != quote.get('url'):
            changed_urls += 1
        if entry.get('title') and fixed.get('title') != entry['title']:
            fixed['title'] = entry['title']
            changed_titles += 1
        if entry.get('source') and fixed.get('source') != entry['source']:
            fixed['source'] = entry['source']
            changed_sources += 1
        out.append(fixed)
    if unresolved:
        print('定位失敗 %d 條（未寫入）：' % len(unresolved))
        for i, text in unresolved:
            print('  ✗ #%d %s…' % (i, text))
        return 1
    data['quotes'] = out
    json.dump(data, open(path, 'w'), ensure_ascii=False, separators=(',', ':'))
    print('已依現況電子書修正：網址 %d、標題 %d、來源 %d（共 %d 條；選文與順序不變）'
          % (changed_urls, changed_titles, changed_sources, len(out)))
    return 0


if __name__ == '__main__':
    if '--repair-urls' in sys.argv:
        sys.exit(repair_urls())
    main()