"""books.css 的墨夜（dark-neutral）鏡像完整性。

`tool/word2ebook/assets/css/modules/06-ux-plus.css` 的墨夜鏡像只覆寫 word2ebook
的 00–05 模組；本工具自有的 `assets/css/books.css` 裡每條 `body.dark-mode` 規則
在墨夜（body 同時掛 dark-mode＋dark-neutral）下**仍然生效**——沒有對應的
`body.dark-mode.dark-neutral` 覆寫時，粉色／暗紫會整批漏進中性暖金面板
（經文整塊 #4a2c3a、時間章 #d4a5b8、標籤 #ff91af…）。此測試逐條把關。
"""

import re
from pathlib import Path

BOOKS_CSS = Path(__file__).resolve().parent.parent / "assets" / "books.css"

# 不需要墨夜鏡像的 dark-mode 規則（值本身跨面板中性，附原因）
MIRROR_EXEMPT = {
    "figure.book-img img": "純黑陰影，兩套深色面板皆中性",
    "para-block .qa-actions::after": "白底半透明「⋯」氣泡，兩套深色面板皆中性",
}


def _selectors(css: str, prefix: str) -> set:
    """回傳所有 `prefix …` 選擇器去掉前綴後的剩餘部分（粗略掃描，含 @media 內）。"""
    found = set()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for sel in re.findall(r"([^{}]+)\{", css):
        for part in sel.split(","):
            part = part.strip()
            if part.startswith(prefix):
                found.add(part[len(prefix):].strip())
    return found


def test_books_css_dark_neutral_mirror_is_complete():
    css = BOOKS_CSS.read_text(encoding="utf-8")
    dark = _selectors(css, "body.dark-mode .")
    assert dark, "books.css 應有 dark-mode 規則可供比對"
    neutral = _selectors(css, "body.dark-mode.dark-neutral .")

    missing = sorted(
        sel for sel in dark
        if sel not in neutral and sel not in MIRROR_EXEMPT
    )
    assert not missing, (
        "books.css 的 dark-mode 規則缺墨夜鏡像（粉色會漏進中性面板）："
        f"{missing}；豁免清單請附原因後加進 MIRROR_EXEMPT"
    )


def test_books_css_dark_neutral_key_selectors():
    """最容易出錯的幾條：經文本體、時間章、標籤小標、深層目錄、段落 hover。"""
    css = BOOKS_CSS.read_text(encoding="utf-8")
    for sel in [
        "body.dark-mode.dark-neutral .sutra-text",
        "body.dark-mode.dark-neutral .answer-time",
        "body.dark-mode.dark-neutral .label-heading",
        "body.dark-mode.dark-neutral h5",
        "body.dark-mode.dark-neutral h6",
        "body.dark-mode.dark-neutral .toc-item.toc-level-5 > a",
        "body.dark-mode.dark-neutral .toc-item.toc-level-6 > a",
        # 經文跟播高亮必須維持不透明（sticky 之下不能透出講解）
        "body.dark-mode.dark-neutral .sutra-text.para-block.para-active",
        "body.dark-mode.dark-neutral .para-block:hover",
        "body.dark-mode.dark-neutral .sutra-text.para-block:hover",
    ]:
        assert sel in css, f"books.css 墨夜區段缺少 {sel}"


def test_books_css_mirror_uses_neutral_tokens_not_pink():
    """墨夜區段不得殘留 books.css 自己 dark-mode 規則的粉色/暗紫硬編碼值。

    （#d4a5b8＋plum 底的時間章刻意不在此列：06-ux-plus.css 對
    .question-time 的墨夜鏡像同款，兩套電子書的時間章外觀必須一致。）
    """
    css = BOOKS_CSS.read_text(encoding="utf-8")
    mirror = css.split("body.dark-mode.dark-neutral", 1)[-1]
    for pink in ["#4a2c3a", "#fddde6", "#ff91af", "#ffd1e0", "#5b3a4c",
                 "#563139", "#4f283f", "255, 105, 180"]:
        assert pink not in mirror, f"墨夜區段殘留粉色/暗紫值：{pink}"
