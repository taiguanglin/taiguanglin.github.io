#!/usr/bin/env python3
"""把 `candidates_sample.json` 的「文字／網址」對齊現況的電子書。

為什麼需要這個工具
------------------
`candidates_sample.json` 是**凍結的 AI 評分集**（2,400 條，`scores/batch_*.json`
的 `idx` 指向它的位置）——**位置與條數不可動**，否則既有評分會錯位。

但它記錄的「文字」與「網址」會隨電子書重建而過期：

- **網址**：pid 是「段落文字雜湊」（md5(文字+段序)），區塊切分一改（例：把
  《圓覺經》的經文條目切成獨立區塊）就整批換 pid。
- **文字**：繁簡／台灣用語的轉換規則更新後，同一段落的文字也會變。

過期造成兩個問題：① 每日精選的「前往原文」連結斷掉；② 經文過濾失準
（過期 url 不在現況的經文錨點裡 → 以為不是經文而混進成品）。

本工具**只更新既有條目的文字／網址／標題**，不新增、不刪除、不重排，
評分與 idx 的對應關係完全不變；對不上的條目（url 已不存在）原樣保留，
由 `select_1095.py` 的「以文字重新定位」機制略過。

用法：
    python3 tool/daily_quotes/refresh_sample.py            # 更新
    python3 tool/daily_quotes/refresh_sample.py --check    # 只檢查
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_quotes import clean  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TD = ROOT / 'tool' / 'daily_quotes'
SAMPLE = TD / 'candidates_sample.json'


def current_index():
    """{url: (text, title)}——現況兩套電子書的繁體搜尋索引。"""
    out = {}
    for sub in ('ebook', 'wenda2_ebook'):
        path = ROOT / sub / 'search_index_trad.json'
        if not path.exists():
            continue
        for x in json.load(open(path, encoding='utf-8')):
            if x.get('type') not in ('content', 'answer'):
                continue
            out['%s/%s' % (sub, x['url'])] = (clean(x['content']), x.get('title', ''))
    return out


def main():
    check = '--check' in sys.argv
    index = current_index()
    sample = json.load(open(SAMPLE, encoding='utf-8'))
    changed_text = changed_url = unresolved = 0
    out = []
    for it in sample:
        hit = index.get(it['url'])
        if hit is None:
            unresolved += 1
            out.append(it)
            continue
        text, title = hit
        if text != it['text']:
            changed_text += 1
        if title and title != it.get('title'):
            it = dict(it, title=title)
        out.append(dict(it, text=text))
    print('樣本 %d 條：文字更新 %d、網址待重定位 %d、url 已失效 %d'
          % (len(sample), changed_text, 0, unresolved))
    if not check:
        json.dump(out, open(SAMPLE, 'w'), ensure_ascii=False, indent=1)
        print('已更新', SAMPLE)


if __name__ == '__main__':
    main()
