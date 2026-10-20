"""**經文區塊的標記與「經文置頂」包層**——經文必須真的以經文格式呈現。

為什麼這組測試重要
--------------------
《金剛經 心經》（書 05）與《圓覺經》（書 06）是由**已經成書的 PDF** 轉換而來，
書裡的經文有兩種排法：

1. 楷體／宋體大字的**原經文**（例：「如是我闻：一时，佛在舍卫国祇树给孤独园…」）；
2. 「解析」段落裡**重引的經文條目**——排成**粗體**、且**前面帶數字編號**
   （例：「3．闻是章句乃至一念生净信者。须菩提…」／「1. 一切障碍即究竟觉。」）。

第 2 種過去被當成一般段落（`<strong>` 粗體）輸出，**不是經文區塊**，
於是「經文置頂」（.sutra-pin-host sticky）對它完全失效——置頂要有意義，
經文必須先被標成經文區塊（`.sutra-text`），跟講四十二章經／楞伽經／
六祖壇經／楞嚴經一致。

另有一個結構條件：原書常把**一段經文縮排切成數段**，若每段各開一個
sticky host，活動範圍就只剩經文自身高度 → 等於沒有置頂效果。因此連續的
經文段落必須**共用同一個 host**（同一個 .sutra-pin-group）。

本模組直接讀**版控中的建置產物**（ebook/*.html）做端到端斷言。
"""

import json
import re
from html.parser import HTMLParser

import pytest

from conftest import book_html

# 講經書本（由已經成書的 PDF 轉換而來：經文有原文與「解析」中的重引條目兩種排法）
CHENG_SHU_BOOKS = ["05", "06"]          # 講《金剛經 心經》／講《圓覺經》
# 講經系列（段落跟播、經文為獨立楷體區塊）
SERIES_BOOKS = ["07", "08", "09", "10"]  # 四十二章／楞伽／六祖壇經／楞嚴
ALL_BOOKS = CHENG_SHU_BOOKS + SERIES_BOOKS

_SUTRA_TEXT_RE = re.compile(r'<div class="sutra-text para-block" id="([^"]+)">')
_STRONG_BLOCK_RE = re.compile(r'<p id="(p-[^"]+)" class="para-block"><strong>', re.S)

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}


class SutraScanner(HTMLParser):
    """掃描經文區塊與其 sticky host 的關係。

    記錄：
    - `sutra_ids`：每段經文的 id
    - `host_sutras`：每個 .sutra-pin-host 內含的經文段數
    - `bad_host`：不在 .sutra-pin-host 內的經文 id
    """

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.sutra_ids = []
        self.host_sutras = []
        self.bad_host = []
        self._frames = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "div" and "sutra-pin-host" in cls:
            self._frames.append({"host": True, "n": 0})
            return
        if tag == "div" and "sutra-text" in cls:
            self.sutra_ids.append(a.get("id"))
            for f in reversed(self._frames):
                if f.get("host"):
                    f["n"] += 1
                    break
            else:
                self.bad_host.append(a.get("id"))
        self._frames.append({"host": False})

    def handle_endtag(self, tag):
        if tag in VOID_TAGS or tag != "div":
            return
        if not self._frames:
            return
        f = self._frames.pop()
        if f.get("host"):
            self.host_sutras.append(f["n"])


def scan(html):
    return SutraScanner(html)


@pytest.mark.artifacts
@pytest.mark.parametrize("book", CHENG_SHU_BOOKS)
def test_scripture_is_marked_as_sutra_text(ebook_dir, book):
    """經文（原文 + 重引條目）必須輸出為 .sutra-text 經文區塊。"""
    html = book_html(ebook_dir, book)
    n_sutra = len(_SUTRA_TEXT_RE.findall(html))
    assert n_sutra > 0, "書 %s 沒有任何經文區塊（經文置頂無從談起）" % book
    # 兩本書的經文段落數都遠超過「只有原經文」的水準——重引的條目也要算
    assert n_sutra >= 200, (
        "書 %s 只有 %d 個經文區塊：《金剛經 心經》《圓覺經》的「解析」裡"
        "重引的經文條目（粗體＋數字編號）也必須標成經文，否則置頂對它們失效"
        % (book, n_sutra))


@pytest.mark.artifacts
@pytest.mark.parametrize("book", CHENG_SHU_BOOKS)
def test_no_bold_left_as_scripture(ebook_dir, book):
    """不得再有以粗體輸出、卻其實是經文的段落（舊行為的殘留）。"""
    html = book_html(ebook_dir, book)
    bold = _STRONG_BLOCK_RE.findall(html)
    assert not bold, (
        "書 %s 還有 %d 個粗體段落（%s…）；經文必須以 .sutra-text 呈現，"
        "不可留成一般粗體段落" % (book, len(bold), bold[:3]))


@pytest.mark.artifacts
@pytest.mark.parametrize("book", ALL_BOOKS)
def test_sutra_text_ids_are_unique(ebook_dir, book):
    """經文區塊的 id 必須唯一（否則錨點／搜尋會指向錯的段落）。"""
    html = book_html(ebook_dir, book)
    ids = _SUTRA_TEXT_RE.findall(html)
    assert len(ids) == len(set(ids)), "書 %s 有重複的經文 id" % book


@pytest.mark.artifacts
@pytest.mark.parametrize("book", ALL_BOOKS)
def test_every_sutra_text_is_inside_a_pin_host(ebook_dir, book):
    """每段經文都必須在 .sutra-pin-host 內（置頂的 sticky 定位單位）。"""
    html = book_html(ebook_dir, book)
    s = scan(html)
    assert s.sutra_ids, "書 %s 沒有經文區塊" % book
    assert not s.bad_host, (
        "書 %s 有 %d 段經文不在 .sutra-pin-host 內（置頂對它們無效）：%s"
        % (book, len(s.bad_host), s.bad_host[:5]))


@pytest.mark.artifacts
@pytest.mark.parametrize("book", ALL_BOOKS)
def test_consecutive_scripture_shares_one_host(ebook_dir, book):
    """連續的經文段落必須共用同一個 host。

    否則 sticky 的活動範圍只剩經文自身的高度 → 等於沒有置頂效果。
    """
    html = book_html(ebook_dir, book)
    s = scan(html)
    multi = [n for n in s.host_sutras if n > 1]
    assert multi, (
        "書 %s 沒有任何「多段經文共用一個 host」的實例——原書常把一段經文"
        "縮排切成數段，若各開一個 host，置頂的活動範圍只剩經文自身高度，"
        "等於沒有置頂效果（host 內經文段數：%s）"
        % (book, sorted(set(s.host_sutras))))


@pytest.mark.artifacts
@pytest.mark.parametrize("book", CHENG_SHU_BOOKS)
def test_sutra_text_ids_exist_in_search_index(ebook_dir, book):
    """經文區塊的 id 必須在搜尋索引中（讀者從搜尋結果跳回原文時要能找到）。"""
    index_path = ebook_dir / "search_index.json"
    if not index_path.exists():
        pytest.skip("沒有 search_index.json")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    urls = set(x["url"] for x in index)
    html = book_html(ebook_dir, book)
    ids = _SUTRA_TEXT_RE.findall(html)
    missing = [i for i in ids if "%s.html#%s" % (book, i) not in urls]
    assert not missing, (
        "書 %s 有 %d 個經文 id 不在搜尋索引中：%s" % (book, len(missing), missing[:5]))


@pytest.mark.artifacts
def test_commentary_is_not_mistaken_for_scripture(ebook_dir):
    """老師的白話講解不得被誤標成經文。

    《圓覺經》「解析」裡有一句「即离，不作方便。离幻即觉，亦无渐次。”
    佛已然答复，菩萨修行」——前半引經文、後半是老師自己的話，整段不可
    當成經文（否則會以經文格式呈現並置頂）。
    """
    html = book_html(ebook_dir, "06")
    for m in re.finditer(r'<div class="sutra-text para-block" id="[^"]*">(.*?)</div>',
                         html, re.S):
        assert "佛已然答复" not in m.group(1), (
            "《圓覺經》「佛已然答复，菩萨修行」是老師的話（引用經文＋自己的解說），"
            "不可標成經文")


@pytest.mark.artifacts
def test_yuanjue_numbered_sutra_items_are_standalone(ebook_dir):
    """《圓覺經》「解析」的經文條目（編號＋粗體）必須**各自成段**。

    2026-10 修訂原檔 PDF（`tool/fix_yuanjue_sutra_numbers.py`：把條目編號改成
    與經文同粗體）後，條目不再與其後的講解黏成同一段 → 每條都能獨立輸出為
    經文區塊，「經文置頂」對每條都有效。修訂前「1. 一切障碍即究竟觉。」會與
    講解黏成一段（被當成一般段落，置頂對它無效）。
    """
    html = book_html(ebook_dir, "06")
    sutra_texts = [m.group(1) for m in
                   re.finditer(r'<div class="sutra-text para-block" id="[^"]*">(.*?)</div>',
                               html, re.S)]
    items = [t for t in sutra_texts if re.match(r"^\d{1,2}[.．]\s", t)]
    assert len(items) >= 100, (
        "《圓覺經》的經文條目只有 %d 條成為經文區塊（應為解析各章的條目）" % len(items))
    for t in items:
        # 條目本身必須完整（不可黏著後面的講解——那會變成很長的一段）
        assert len(t) <= 120, (
            "經文條目黏著了後面的講解（長度 %d）：%r" % (len(t), t[:60]))
    assert any(t.startswith("1. 一切障碍即究竟觉。") for t in items), (
        "《圓覺經》「1. 一切障碍即究竟觉。」沒有成為獨立的經文區塊")


@pytest.mark.artifacts
@pytest.mark.parametrize("book", SERIES_BOOKS)
def test_jiangjing_series_still_have_sutra_text(ebook_dir, book):
    """講經系列（段落跟播）的經文區塊不得被本次改動影響。"""
    html = book_html(ebook_dir, book)
    n = len(_SUTRA_TEXT_RE.findall(html))
    assert n > 20, "書 %s 的經文區塊只剩 %d 個" % (book, n)
