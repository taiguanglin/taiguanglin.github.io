"""**經文置頂的包層規則**（render_chapter 合成區塊，不需建置產物）。

為什麼這組測試重要
--------------------
《四十二章經》每章開頭先用楷體排一次該章**完整經文**（文字以章標題開頭，
例：「第十五章请问力明」＋全章經文），之後的講解才逐句重引。章首全文經文
是章首引文、**不是正在講解的經文段**，因此：

- 它若與緊接的第一句重引經文依「連續經文共用 host」規則併進同一個
  .sutra-pin-host，置頂時「全文＋第一句」會一起停在視窗頂（2026-12 事故：
  第 2/3/5/15/16/31 章）；
- 即使自成一 host，章首講解捲動時整段全文也會停留、佔掉大半畫面。

故建置期必須把章首全文經文**排除在置頂之外**：帶 `.sutra-full` 標記、不包
host/group（09c-sutra-pin.js 以 `:not(.sutra-full)` 一併排除）。只有講解中
逐句重引的經文段置頂。

本模組直接呼叫 `html_generator.render_chapter()` 渲染合成區塊，斷言包層
結構；建置產物的端到端斷言見 `test_sutra_markup.py`。
"""

from config import BookConfig
from html_generator import annotate, render_chapter


def _render(blocks, sutra_pin=True):
    """渲染合成區塊，回傳 HTML。"""
    book = BookConfig(7, "06 讲《四十二章经》", "x.pdf", "sishierzhang",
                      sutra_pin=sutra_pin)
    annotate(blocks)
    html, _items = render_chapter(book, blocks, {}, is_trad=False)
    return html


def test_chapter_full_text_is_not_pinned():
    """章首全文經文不置頂；緊接的第一句重引經文照常置頂。"""
    full = "第十五章请问力明沙门问佛：“何者多力？何者最明？”佛言：“忍辱多力。”"
    first = "沙门问佛：“何者多力？何者最明？”"
    html = _render([
        {"kind": "h3", "text": "第十五章请问力明"},
        {"kind": "quote", "text": full},
        {"kind": "quote", "text": first},
        {"kind": "para", "text": "讲解第一句。"},
    ])
    assert "sutra-text para-block sutra-full" in html, (
        "章首全文經文必須帶 sutra-full 標記（09c 以 :not(.sutra-full) 排除）")

    full_at = html.index("sutra-full")
    assert '<div class="sutra-pin-group">' not in html[:full_at], (
        "章首全文經文之前不該有 pin 群（它不置頂）")
    assert '<div class="sutra-pin-host">' not in html[:full_at], (
        "章首全文經文之前不該有 host（它不置頂）")

    # 全文經文之後的第一句重引經文仍要置頂：自成一 host（不與全文共用）
    assert html.count('<div class="sutra-pin-host">') == 1, (
        "第一句重引經文必須自成一 host，不可與章首全文經文共用")
    host_at = html.index('<div class="sutra-pin-host">')
    host_end = html.index("</div>", host_at)
    # 第一句的經文區塊（全文經文裡也含同一句，故取最後一個出現位置）
    first_at = html.rindex(first)
    assert host_at > full_at, "host 必須在全文經文之後"
    assert host_at < first_at < host_end, (
        "第一句重引經文必須落在 host 內（置頂才會生效）")


def test_consecutive_quotes_share_one_host():
    """連續的經文段落共用同一個 host（置頂活動範圍才不會只剩經文自身高度）。"""
    html = _render([
        {"kind": "h3", "text": "第十六章舍爱得道"},
        {"kind": "quote", "text": "人怀爱欲不见道者，譬如澄水。"},
        {"kind": "quote", "text": "汝等沙门，当舍爱欲。"},
        {"kind": "para", "text": "讲解。"},
    ])
    assert html.count('<div class="sutra-pin-host">') == 1, (
        "兩段連續經文必須共用同一個 host")
    assert html.count('<div class="sutra-pin-group">') == 1
    assert "sutra-full" not in html, (
        "不是章首全文經文的區塊不該帶 sutra-full 標記")


def test_quote_not_starting_with_heading_is_pinned():
    """不是「以標題開頭」的經文段照常置頂（經序等章節不受影響）。"""
    html = _render([
        {"kind": "h3", "text": "经序"},
        {"kind": "quote", "text": "世尊成道已，作是思惟：离欲寂静。"},
        {"kind": "para", "text": "讲解。"},
    ])
    assert "sutra-full" not in html
    assert '<div class="sutra-pin-host">' in html
    assert '<div class="sutra-pin-group">' in html


def test_chengshu_book_keeps_plain_sutra_markup():
    """sutra_pin=False 的書（成書 PDF 轉檔）：經文照常輸出，但不開包層。"""
    html = _render([
        {"kind": "h3", "text": "第一章"},
        {"kind": "quote", "text": "第一章如是我闻。"},
    ], sutra_pin=False)
    assert 'class="sutra-text para-block"' in html
    assert "sutra-pin-host" not in html
    assert "sutra-pin-group" not in html
