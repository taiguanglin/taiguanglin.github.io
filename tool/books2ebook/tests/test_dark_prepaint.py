"""夜間模式防閃爍（首繪前套用）——頁面模板層測試。

內容配色都掛在 body.dark-mode（html.dark-mode 只改 canvas 底色），body 的
類別若等到 deferred script.js（DOM 就緒）才補上，頁面切換時首繪會先以日間
配色繪製、再整頁轉暗——夜讀時特別刺眼。守兩件事：

1. ``_HEAD_TMPL`` 把 body 防閃腳本放在 ``<body>`` 的第一個子元素位置；
2. 本工具的兩段腳本與 word2ebook ``templates/i18n_templates.py`` 的
   ``DARK_MODE_PREPAINT_SCRIPT`` / ``DARK_MODE_BODY_PREPAINT_SCRIPT``
   逐字同步（兩處宣告「需同步修改」，這裡把它變成可執行的約束）。
"""

import re
from pathlib import Path

from html_generator import (
    _DARK_MODE_BODY_PREPAINT,
    _DARK_MODE_PREPAINT,
    _HEAD_TMPL,
)

_WORD2EBOOK_TEMPLATES = (
    Path(__file__).resolve().parent.parent.parent
    / "word2ebook" / "templates" / "i18n_templates.py"
)


def _word2ebook_script(constant_name):
    """從 word2ebook 的模板原始碼抽下指名常數的腳本內容（不 import，
    避免兩工具的 config 模組名稱衝突）。"""
    text = _WORD2EBOOK_TEMPLATES.read_text(encoding="utf-8")
    m = re.search(
        r'%s\s*=\s*"""(.*?)"""' % re.escape(constant_name), text, re.DOTALL
    )
    assert m, "word2ebook 模板找不到 %s" % constant_name
    return m.group(1)


class TestBodyPrepaintPlacement:
    def test_head_tmpl_body_script_is_first_body_child(self):
        """``{prepaint_body}`` 必須緊跟在 ``<body{body_attrs}>`` 之後、
        任何可見內容（<div id="top"> 等）之前。"""
        m = re.search(
            r"<body\{body_attrs\}>\s*\n\{prepaint_body\}\s*\n<div id=\"top\">",
            _HEAD_TMPL,
        )
        assert m, "_HEAD_TMPL 必須把 {prepaint_body} 放在 <body> 的第一個子元素"

    def test_rendered_page_carries_body_prepaint(self):
        html = _HEAD_TMPL.format(
            title="t", body_attrs="", header_class="header-nav",
            nav_left_content="", lang_switch_links="", html_lang="zh-Hans",
            prepaint_head=_DARK_MODE_PREPAINT,
            prepaint_body=_DARK_MODE_BODY_PREPAINT,
            shared_style_css="../wenda2_ebook/assets/css/style.css",
            shared_reading_prepaint_js="../wenda2_ebook/assets/js/reading-prepaint.js",
            shared_i18n_js="../wenda2_ebook/assets/js/i18n-text.js",
            shared_script_js="../wenda2_ebook/assets/js/script.js",
            extra_head="",
            jsonld_marker="",
        )
        head = html[: html.index("</head>")]
        assert "window.__W2E_THEME_DARK" in head
        assert "documentElement.classList.add('dark-mode')" in head
        body_open = html.index("<body>") + len("<body>")
        first_child = html[body_open: html.index('<div id="top">')]
        assert "document.body.classList.add('dark-mode')" in first_child
        assert "document.body.classList.add('dark-neutral')" in first_child

    def test_body_prepaint_composes_with_no_sutra_pin(self):
        """成書 PDF 轉檔頁的 <body class=\"no-sutra-pin\"> 也要接在腳本後。"""
        html = _HEAD_TMPL.format(
            title="t", body_attrs=' class="no-sutra-pin"',
            header_class="header-nav",
            nav_left_content="", lang_switch_links="", html_lang="zh-Hans",
            prepaint_head=_DARK_MODE_PREPAINT,
            prepaint_body=_DARK_MODE_BODY_PREPAINT,
            shared_style_css="css", shared_reading_prepaint_js="rp",
            shared_i18n_js="i18n", shared_script_js="s", extra_head="",
            jsonld_marker="",
        )
        assert '<body class="no-sutra-pin">' in html
        body_open = html.index('<body class="no-sutra-pin">') + len(
            '<body class="no-sutra-pin">'
        )
        first_child = html[body_open: html.index('<div id="top">')]
        assert "document.body.classList.add('dark-mode')" in first_child


class TestScriptsInSyncWithWord2ebook:
    def test_head_script_matches_word2ebook(self):
        assert _DARK_MODE_PREPAINT == _word2ebook_script(
            "DARK_MODE_PREPAINT_SCRIPT"
        ), "head 防閃腳本與 word2ebook 不同步"

    def test_body_script_matches_word2ebook(self):
        assert _DARK_MODE_BODY_PREPAINT == _word2ebook_script(
            "DARK_MODE_BODY_PREPAINT_SCRIPT"
        ), "body 防閃腳本與 word2ebook 不同步"

    def test_body_script_has_no_theme_logic(self):
        """決定只在 head 算一次：body 腳本只讀全域掛 class。"""
        assert "localStorage" not in _DARK_MODE_BODY_PREPAINT
        assert "matchMedia" not in _DARK_MODE_BODY_PREPAINT
