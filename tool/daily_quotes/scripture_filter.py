#!/usr/bin/env python3
"""經文（原文）段落偵測 — `build_quotes.py` 與 `select_1095.py` 共用。

每日精選只放 Tai 師父自己的話；經文不該出現在首頁。過去兩支腳本各自帶一份
偵測規則，規則弱且會各自漂移，於是經文（例如六祖壇經「師示眾云：善知識！本來
正教，無有頓漸……」）漏進了成品。此模組把判定收斂成單一真相來源，採三道互相
獨立的防線：

A. **結構錨點（權威）**——`tool/books2ebook` 用兩種結構標出經文：
   1. 講經系列以楷體字型排的**原經文** → `<div class="sutra-text para-block" id="p-x">`
      （見 `tool/books2ebook/parsers.py` 的「各書楷體（原經文）字型集合」與
      `html_generator.py` 的 `k == "quote"` 分支）；
   2. 《金剛經 心經》《圓覺經》每章的**白話譯文** → 落在
      `<div class="label-heading">譯文</div>` 與下一個 label 之間的所有段落
      （`解析`／`註解`／`本章大義` 才是老師的講解，保留）。
   這些 id 與 `search_index*.json` 的 url 一一對應，直接比對最為可靠。

B. **文字啟發式（補漏）**——有些經文不在上述區塊裡（例如書末附錄的經文）。
   這裡以「命中古典對話／稱謂標記，且現代語助詞極少」作為判準。

C. **人工複查清單**（`exclude.json`）——講經書的「解析」區段裡偶爾整段其實是
   經文白話譯文，A/B 分不出來，由人工複查後列名排除（附判斷依據）。

刻意**不做**「現代助詞密度低就排除」：講經系列的講解本身是端正的書面語
（《圓覺經》《楞伽經》尤甚），單看文白會把師父的講解誤殺。一定要搭配
古典標記，才不會傷到講解文字。
"""
import json
import re
from pathlib import Path

# A. 結構錨點 -------------------------------------------------------------- #
_SUTRA_HTML = re.compile(
    r'class="sutra-text[^"]*"[^>]*\bid="([^"]+)"'   # <div class="sutra-text …" id="p-x">
    r'|\bid="([^"]+)"[^>]*\bclass="sutra-text[^"]*"'  # 屬性順序相反時
)
# 講經書（《金剛經 心經》《圓覺經》）另有一層結構：每章切成
#   <div class="label-heading">譯文</div>   ← 經文的現代白話譯文
#   <div class="label-heading">解析</div>   ← 老師的講解（保留）
#   <div class="label-heading">註解</div>／<div class="label-heading">本章大義</div>
# 「譯文」區段整段都是經文的譯文，沒有老師自己的話，與 sutra-text 同一性質。
_LABEL_HEADING = re.compile(r'<div class="label-heading">([^<]*)</div>')
_PARA_ID = re.compile(r'<p\b[^>]*\bid="([^"]+)"')
SUTRA_LABELS = {'譯文'}

_anchor_cache: dict[str, dict[str, frozenset]] = {}


def _scan(path: Path) -> frozenset:
    """回傳此電子書檔案中屬於經文的段落 id 集合。"""
    html = path.read_text(encoding='utf-8')
    ids = {a or b for a, b in _SUTRA_HTML.findall(html)}
    # 依序走過 label-heading，維持「目前是否在譯文區段」的狀態
    in_yiwen, pos = False, 0
    for m in _LABEL_HEADING.finditer(html):
        for pid in _PARA_ID.findall(html[pos:m.start()]):
            if in_yiwen:
                ids.add(pid)
        in_yiwen = m.group(1) in SUTRA_LABELS
        pos = m.end()
    for pid in _PARA_ID.findall(html[pos:]):
        if in_yiwen:
            ids.add(pid)
    return frozenset(ids)


def sutra_anchors(root: Path) -> set[str]:
    """回傳 `'<檔名>#<id>'` 集合，涵蓋 `ebook/` 與 `wenda2_ebook/` 的經文段落
    （`sutra-text` 楷體原文區塊 ＋ 「譯文」白話譯文區段）。"""
    anchors: set[str] = set()
    for sub in ('ebook', 'wenda2_ebook'):
        for f in sorted((root / sub).glob('*_trad.html')):
            anchors |= {f'{f.name}#{i}' for i in _scan(f)}
    return anchors


def _load_anchors(root: Path) -> set[str]:
    key = str(root)
    if key not in _anchor_cache:
        _anchor_cache[key] = sutra_anchors(root)
    return _anchor_cache[key]


def is_sutra_url(root: Path, url: str) -> bool:
    """url 形如 `ebook/09_trad.html#p-s0bf8dfc2`；落在經文區塊即為 True。"""
    return url.split('/', 1)[-1] in _load_anchors(root)


# B. 文字啟發式 ----------------------------------------------------------- #
# 古典對話／稱謂標記：經文常見的說話者、聽話者、章節起手。
SCRIPT_MARKERS = re.compile(
    '|'.join([
        r'曰\s*[：:“"‘’]',   # 祖曰：／云云
        r'佛[言告問]',                    # 佛言／佛告／佛問
        r'問曰', r'對曰', r'[師祖]曰',
        r'如是我聞', r'爾時', r'世尊',
        r'善知識', r'善男子', r'善女人',
        r'須菩提', r'舍利弗', r'摩訶', r'阿耨多羅',
        r'云何', r'云云', r'即非', r'何以故', r'應住', r'不也',
        r'如是(?!因為|上|果|上所)', r'白佛', r'禮拜', r'大德',
    ])
)

# 現代語助詞／虛詞。經文（尤其未標點的文言）幾乎不出现；師父的現代講解則很密集。
MODERN_PARTICLES = '的了我你他她這那們嗎呢吧啊呀哦喔就是所以其實會要還在跟把被從對讓給又能可以應該一個什麼怎樣時後前說'
MODERN_MAX = 3  # 命中古典標記時，現代語助詞超過此數就當作講解文字，放行


def _modern_count(t: str) -> int:
    return sum(1 for ch in t if ch in MODERN_PARTICLES)


def is_scripture_text(t: str) -> bool:
    """命中古典標記且幾乎沒有現代語助詞 → 判為文言經文。"""
    return bool(SCRIPT_MARKERS.search(t)) and _modern_count(t) <= MODERN_MAX


# 匯總 ------------------------------------------------------------------- #
# C. 人工複查清單 ---------------------------------------------------------- #
# 規則 A/B 抓不到、但經文確實佔了段落主體的少數段落（講經書的「解析」區段裡
# 有時整段是經文白話譯文）。人工複查後列在 `exclude.json`，附判斷依據。
_exclude_cache: dict[str, set[str]] = {}


def excluded_urls(root: Path) -> dict[str, str]:
    """回傳 `{url: reason}`；讀不到或檔案損壞時回空 dict（不讓稽核中斷）。"""
    key = str(root)
    if key not in _exclude_cache:
        path = Path(__file__).resolve().parent / 'exclude.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            _exclude_cache[key] = {u: v.get('reason', '')
                                   for u, v in data.get('excluded', {}).items()}
        except (OSError, ValueError):
            _exclude_cache[key] = {}
    return _exclude_cache[key]


def is_excluded(root: Path, url: str) -> bool:
    return url in excluded_urls(root)


def is_scripture(root: Path, url: str, text: str) -> bool:
    """A、B、C 任一成立即視為經文，應排除於每日精選之外。"""
    return (is_sutra_url(root, url)
            or is_scripture_text(text)
            or is_excluded(root, url))
