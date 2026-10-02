#!/usr/bin/env python3
"""稽核根目錄 `daily_quotes.json` — 提交前跑；有問題就 exit 1。

檢查四件事：
  1. **無經文**（最重要）：沒有一條落在 `scripture_filter` 的任一條規則上
     ——原經文楷體區塊（sutra-text 錨點）、文言經文啟發式。
     額外再跑一次「放寬版」掃描（現代助詞門檻 +5）並印出供人工複查，
     但放寬版只警告、不判失敗（講解文字本來就偏書面語，會誤報）。
  2. **連結有效**：每條 `url` 的 `<檔名>#<id>` 都能在對應的電子書 HTML 找到。
  3. **結構**：條數達 `select_1095.TARGET`、無重複文字、單一來源不超過 SRC_CAP。
  4. **引用欄位**：text / url / title 齊全。

用法：
  python3 tool/daily_quotes/audit_quotes.py           # 稽核 + 印報告
  python3 tool/daily_quotes/audit_quotes.py --strict  # 放寬版掃描也視為失敗
"""
import json, re, sys, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TD = ROOT / 'tool/daily_quotes'
sys.path.insert(0, str(TD))
import select_1095  # noqa: E402  取 TARGET / SRC_CAP
from scripture_filter import (  # noqa: E402
    is_scripture, is_sutra_url, is_scripture_text,
    excluded_urls, SCRIPT_MARKERS, MODERN_PARTICLES,
)

STRICT = '--strict' in sys.argv
WARN_MAX = 8  # 放寬版門檻：MODERN_MAX + 5


def main() -> int:
    quotes = json.load(open(ROOT / 'daily_quotes.json'))['quotes']
    errors: list[str] = []
    warns: list[str] = []

    # 1. 經文 ---------------------------------------------------------------
    hard = [q for q in quotes if is_scripture(ROOT, q['url'], q['text'])]
    for q in hard:
        if is_sutra_url(ROOT, q['url']):
            kind = '經文區塊（sutra-text／譯文）'
        elif is_scripture_text(q['text']):
            kind = '文言經文'
        else:
            kind = f'人工排除清單：{excluded_urls(ROOT).get(q["url"], "")[:40]}'
        errors.append(f'經文（{kind}）{q["url"]}：{q["text"][:50]}…')

    soft = [q for q in quotes
            if not is_scripture(ROOT, q['url'], q['text'])
            and SCRIPT_MARKERS.search(q['text'])
            and sum(1 for c in q['text'] if c in MODERN_PARTICLES) <= WARN_MAX]
    for q in soft:
        warns.append(f'待複查 {q["url"]}：{q["text"][:50]}…')

    # 2. 連結 ---------------------------------------------------------------
    ids: set[str] = set()
    for sub in ('ebook', 'wenda2_ebook'):
        for f in (ROOT / sub).glob('*_trad.html'):
            ids |= {f'{f.name}#{i}'
                    for i in re.findall(r'\bid="([^"]+)"', f.read_text(encoding='utf-8'))}
    for q in quotes:
        if q['url'].split('/', 1)[-1] not in ids:
            errors.append(f'斷鏈 {q["url"]}')

    # 3. 結構 ---------------------------------------------------------------
    if len(quotes) != select_1095.TARGET:
        errors.append(f'條數 {len(quotes)} ≠ TARGET {select_1095.TARGET}')
    texts = [q['text'] for q in quotes]
    for t, n in collections.Counter(texts).items():
        if n > 1:
            errors.append(f'重複 {n} 次：{t[:50]}…')
    cap = int(select_1095.TARGET * select_1095.SRC_CAP)
    for src, n in collections.Counter(q['source'] for q in quotes).items():
        if n > cap:
            errors.append(f'來源「{src}」{n} 條，超過上限 {cap}')

    # 4. 欄位 ---------------------------------------------------------------
    for q in quotes:
        for k in ('text', 'url', 'title', 'source'):
            if not q.get(k):
                errors.append(f'缺欄位 {k}：{q["url"]}')

    # 報告 ------------------------------------------------------------------
    print(f'daily_quotes.json：{len(quotes)} 條  '
          f'{dict(collections.Counter(q["source"] for q in quotes))}')
    print(f'經文命中（失敗條件）：{len(hard)}')
    print(f'放寬掃描待複查：{len(soft)}')
    for w in warns:
        print('  ⚠ ' + w)
    for e in errors:
        print('  ✗ ' + e)
    if errors or (STRICT and soft):
        print('稽核未通過' + ('（--strict）' if STRICT and not errors else ''))
        return 1
    print('稽核通過：每日精選無經文段落。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
