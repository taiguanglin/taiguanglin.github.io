"""回歸測試：段落互動選單與經文置頂的錨點讓位。

這兩項都曾因「元素放在 content-visibility: auto 的盒子外」而整個消失 /
被遮住，因此以原始碼斷言（不跑瀏覽器）守住兩條不变量：

1. `.para-block` 的 `.qa-actions` / `.bookmark-indicator` 必須留在段落
   padding box 之內——`content-visibility: auto` 等於 paint containment，
   放在 `bottom: 100%` 會被整片裁掉（滑鼠永遠點不到）。
2. 09c 必須把「停留經文高 + 間隙」寫成群的 `--w2e-pin-reserve`，且 CSS
   端確實把它轉成群內目標的 `scroll-margin-top`，否則跳轉後的高亮段落
   會被置頂經文蓋住。
"""

from pathlib import Path

import pytest

CSS_DIR = Path(__file__).parent.parent / "assets" / "css" / "modules"
JS_DIR = Path(__file__).parent.parent / "assets" / "js" / "modules"
BOOKS_CSS = Path(__file__).parent.parent.parent / "books2ebook" / "assets" / "books.css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rule_body(css: str, selector: str) -> str:
    """取出 `selector { ... }` 的宣告本文（第一個同名規則）。"""
    start = css.index(selector + " {")
    depth = 0
    for i in range(start + len(selector), len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[start + len(selector) + 1:i]
    raise AssertionError("unterminated rule: " + selector)


# ---------------------------------------------------------------------------
# 1. 段落互動選單必須在段落盒子內
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def books_css() -> str:
    if not BOOKS_CSS.exists():
        pytest.skip("books.css 不存在（books2ebook 工具未 checkout）")
    return _read(BOOKS_CSS)


def test_para_actions_stay_inside_paragraph(books_css):
    """.qa-actions 不得用 bottom:100% / top 負值放到段落外。"""
    body = _rule_body(books_css, ".para-block .qa-actions")
    assert "bottom: 100%" not in body
    assert "bottom: auto" in body
    assert "top: 2px" in body


def test_para_actions_not_offset_by_negative_top(books_css):
    """不得改回 top: -Npx 的寫法（會被 paint containment 裁掉）。"""
    body = _rule_body(books_css, ".para-block .qa-actions")
    assert not any(
        line.strip().startswith("top: -")
        for line in body.splitlines()
    )


def test_bookmark_indicator_stays_inside_paragraph(books_css):
    body = _rule_body(books_css, ".para-block.bookmarked .bookmark-indicator")
    assert "bottom: 100%" not in body
    assert "bottom: auto" in body


def test_para_actions_hover_reveals_menu(books_css):
    """hover 時容器取得 pointer-events，⋯ 才能展開成按鈕。"""
    assert ".para-block:hover .qa-actions," in books_css
    body = _rule_body(
        books_css,
        ".para-block:hover .qa-actions,\n.para-block .qa-actions:hover,\n"
        ".para-block .qa-actions:focus-within",
    )
    assert "opacity: 1" in body
    assert "pointer-events: auto" in body


def test_hidden_reading_toolbar_is_not_hit_testable():
    """收起狀態的浮動面板必須 pointer-events:none，否則會吃掉它覆蓋區的 hover。"""
    css = _read(CSS_DIR / "01a-layout.css")
    body = _rule_body(css, ".reading-toolbar.hidden")
    assert "opacity: 0" in body
    assert "pointer-events: none" in body


# ---------------------------------------------------------------------------
# 2. 經文置頂的錨點讓位
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sutra_js() -> str:
    return _read(JS_DIR / "09c-sutra-pin.js")


@pytest.fixture(scope="module")
def sutra_css() -> str:
    return _read(CSS_DIR / "04c-qa-audio.css")


def test_pin_reserve_css_maps_to_scroll_margin(sutra_css):
    assert ".sutra-pin-group :is(.para-block, h1, h2, h3, h4, h5, h6, .label-heading) {" in sutra_css
    body = _rule_body(
        sutra_css,
        ".sutra-pin-group :is(.para-block, h1, h2, h3, h4, h5, h6, .label-heading)",
    )
    assert "scroll-margin-top: var(--w2e-pin-reserve)" in body


def test_pin_reserve_defaults_to_zero(sutra_css):
    """未設定時（無經文置頂的頁面）留白為 0，行為與從前一致。"""
    assert ".sutra-pin-group {\n    --w2e-pin-reserve: 0px;\n}" in sutra_css


def test_pin_reserve_written_per_group(sutra_js):
    """09c 量測經文高度後逐群寫入 --w2e-pin-reserve。"""
    assert "g.style.setProperty('--w2e-pin-reserve'" in sutra_js
    assert "(h + RESERVE_GAP) + 'px'" in sutra_js
    # 置頂關閉 / 過長不停留 → 歸零
    assert "(!pinOn || tall) ? '0px'" in sutra_js


def test_reserve_gap_is_defined_once(sutra_js):
    assert sutra_js.count("var RESERVE_GAP = ") == 1


def test_reserve_for_returns_height_plus_gap(sutra_js):
    """reserveFor 與 --w2e-pin-reserve 用同一個數字（09b 與 03d 共用）。"""
    start = sutra_js.index("function reserveFor(el)")
    body = sutra_js[start:sutra_js.index("window.W2E = window.W2E || {};", start)]
    assert "sutra.offsetHeight + RESERVE_GAP" in body
    assert "sutra-pin-tall" in body


def test_pin_reserve_recomputed_on_toggle(sutra_js):
    """讓位高度是 inline style（優先級高於樣式表），切換 toggle 必須重算。"""
    body = _rule_body_brace(sutra_js, "function syncToggleUI() {")
    assert "scheduleTallCheck()" in body


def _rule_body_brace(js: str, header: str) -> str:
    start = js.index(header)
    depth = 0
    for i in range(start + len(header) - 1, len(js)):
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
            if depth == 0:
                return js[start + len(header):i]
    raise AssertionError("unterminated block: " + header)


# ---------------------------------------------------------------------------
# 3. 初始錨點：讓位 + 收斂
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def reading_settings_js() -> str:
    return _read(JS_DIR / "03d-reading-settings.js")


def test_initial_anchor_aligns_below_pinned_sutra(reading_settings_js):
    assert "function anchorTargetOffset(el)" in reading_settings_js
    body = _rule_body_brace(reading_settings_js, "function anchorTargetOffset(el) {")
    assert "anchorNeedsHeadroom(el)" in body
    assert "W2E.sutraPin.reserveFor(el)" in body


def test_initial_anchor_uses_start_when_headroom_needed(reading_settings_js):
    assert "block: anchorNeedsHeadroom(targetElement) ? 'start' : 'center'" in reading_settings_js


def test_initial_anchor_settles_repeatedly(reading_settings_js):
    """content-visibility 的估算高度會讓文件總高持續變動，必須反覆收斂。"""
    assert "function settleAnchorTo(el)" in reading_settings_js
    body = _rule_body_brace(reading_settings_js, "function settleAnchorTo(el) {")
    assert "window.scrollTo(0, want)" in body
    assert "tries >= 40" in body


def test_initial_anchor_yields_to_user_scroll(reading_settings_js):
    body = _rule_body_brace(reading_settings_js, "function settleAnchorTo(el) {")
    assert "'wheel'" in body
    assert "'touchstart'" in body
    assert "userScrolled" in body