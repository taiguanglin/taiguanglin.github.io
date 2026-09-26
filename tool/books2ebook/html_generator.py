"""HTML / 搜索索引生成：输出与 wenda2_ebook 同风格的电子书页面。"""

import hashlib
import importlib.util
import os

from config import (
    SITE_TITLE,
    TYPE_ANSWER,
    TYPE_CONTENT,
    TYPE_HEADING,
    TYPE_QUESTION,
    EBOOK_URL_PATH,
    OG_IMAGE_PATH,
    SEO_CHAPTER_DESCRIPTION,
    SEO_HREFLANG_DEFAULT,
    SEO_INDEX_DESCRIPTION,
    SEO_SITE_NAME,
    SITE_BASE_URL,
    shared_asset_url,
)
try:
    from audio_map import AUDIO_MAP, AUDIO_BASE, audio_duration
except ImportError:  # 供 -c 單獨載入等邊界情境
    AUDIO_MAP, AUDIO_BASE = {}, "../audio/jiangjing/"
    def audio_duration(series, n):  # noqa: E306
        return None

try:
    from para_audio_map import para_time_attrs
except ImportError:  # 供 -c 單獨載入等邊界情境
    def para_time_attrs(series, pid):  # noqa: E306
        return ""

_HEADING_KINDS = ("h2", "h3", "h4", "h5", "h6")

# 首页搜索需要 MiniSearch（章节页不用）。改為本地自架（defer、中國網路可達）；
# 運行期 CDN 兜底由共用的 01e-search-ui.js ensureMiniSearchLoaded 處理。
# minisearch.min.js 不在 ebook/ 另存一份，直接引用 wenda2_ebook 的資產。
_MINISEARCH_HEAD = (
    '<script src="%s" defer></script>\n'
    '<script src="assets/js/w2e-config.js" defer></script>'
) % shared_asset_url("js/minisearch.min.js")

# 防閃爍：首繪前依深色偏好把 dark-mode 掛到 <html>（00-base.js 於 DOM 就緒後
# 改掛 <body> 並移除）。與 word2ebook templates/i18n_templates.py 的
# DARK_MODE_PREPAINT_SCRIPT 同源——兩份需同步修改。
_DARK_MODE_PREPAINT = """<script>
try {
  var __dm = localStorage.getItem('darkMode');
  if (__dm === null && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) __dm = 'true';
  if (__dm === 'true') document.documentElement.classList.add('dark-mode');
} catch (e) {}
</script>"""


def slug_id(text):
    """由标题产生稳定的元素 ID。"""
    return "s" + hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def _load_render_img_tag():
    """載入 word2ebook 的 <img> 標記 SoT（lazy + 語意 alt + 實檔寬高）。

    image_markup.py 無內部 import，可獨立執行；與 main.py 載入
    i18n_utils 的方式一致，避開兩工具的 config 模組名稱衝突。
    """
    path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "word2ebook", "utils", "image_markup.py"
    ))
    spec = importlib.util.spec_from_file_location("_w2e_image_markup", path)
    if spec is None or spec.loader is None:
        raise ImportError("無法載入 word2ebook image_markup：%s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render_img_tag


render_img_tag = _load_render_img_tag()


def esc(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def nl2br(text):
    return text.replace("\n", "<br/>")


def build_lang_switch_links(simp_file: str, trad_file: str, is_trad: bool) -> str:
    """Build the language switch link with a single per-page target label.

    繁頁只顯示「简体」（指向簡體檔）、簡頁只顯示「繁體」（指向繁體檔），節省空間。
    對照 wenda2_ebook：繁頁的「简体」標籤維持簡體字（不隨頁面轉繁）、簡頁的「繁體」
    維持繁體字。ebook 的繁頁在 main.py 會對整頁跑 OpenCC s2t，因此這裡用數字
    HTML 實體輸出標籤文字，讓 OpenCC（只作用於字元）不會誤轉它們，瀏覽器仍會
    正確顯示「简体 / 繁體」。
    """
    # &#31616;&#20307; = "简体"（簡體字）, &#32321;&#39636; = "繁體"（繁體字）
    simp_entity = "&#31616;&#20307;"
    trad_entity = "&#32321;&#39636;"
    if is_trad:
        return f'<a href="{simp_file}">{simp_entity}</a>'
    return f'<a href="{trad_file}">{trad_entity}</a>'


def nl2br(text):
    return text.replace("\n", "<br/>")


# 講經系列播放按鈕：與 wenda2_ebook 的 .qa-play 共用同一套 JS/CSS（assets 影印過來的
# 08-qa-audio.js / 04c-qa-audio.css）。每個「講次」章節一把完整音檔，data-start=0、
# data-end=時長（空著則播到檔尾）。
_SPEAKER_SVG = (
    '<svg class="qa-play-speaker" viewBox="0 0 24 24" width="1em" height="1em" '
    'aria-hidden="true" focusable="false">'
    '<path fill="currentColor" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29'
    '-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s'
    '-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>'
    '</svg>'
)


def _fmt_hms(seconds):
    s = int(seconds or 0)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return "%02d:%02d:%02d" % (h, m, sec)


def lecture_play_button(series, n, label):
    """回傳講次 N 的播放按鈕 HTML；無音檔映射則回傳空字串。"""
    if not series or series not in AUDIO_MAP or n not in AUDIO_MAP[series]:
        return ""
    fn = AUDIO_MAP[series][n]
    import html as _html
    from urllib.parse import quote
    url = "%s%s.opus" % (AUDIO_BASE, quote(fn))
    dur = audio_duration(series, n)
    end_attr = (' data-end="%.3f"' % dur) if dur else ""
    range_label = "00:00:00 - %s" % (_fmt_hms(dur) if dur else "??:??:??")
    return (
        '<button class="qa-play" type="button" aria-label="播放 %s" '
        'data-audio="%s" data-start="0.000"%s data-label="%s">'
        '<span class="qa-play-icon">%s</span></button>'
        % (_html.escape(range_label, quote=True),
           _html.escape(url, quote=True), end_attr,
           _html.escape(range_label, quote=True), _SPEAKER_SVG)
    )


def _content_weight(block):
    kind = block["kind"]
    if kind in ("qa", "para", "quote", "strong", "img"):
        return 1
    return 0


def annotate(blocks):
    """为标题区块加上 sid(锚点)与 count。

    count 语意与 wenda2_ebook 一致：每个标题显示"自己名下的直接内容数 +
    所有子標題的計數」；每個內容區塊只會被最近的標題統計一次，不重複累加。
    """
    idxs = [i for i, b in enumerate(blocks) if b["kind"] in _HEADING_KINDS]
    # 直接內容數：相鄰兩個標題之間的內容歸前一個標題所有
    for pos, i in enumerate(idxs):
        blk = blocks[i]
        end = idxs[pos + 1] if pos + 1 < len(idxs) else len(blocks)
        blk["count"] = sum(_content_weight(b) for b in blocks[i + 1:end])
        # 錨點需在同一篇文章內唯一：文字相同時加入索引
        blk["sid"] = slug_id(f"{i}-{blk['text']}")
    # 孤立內容（第一個標題之前的插圖/段落）歸入第一個標題
    if idxs:
        first = idxs[0]
        stray = sum(_content_weight(b) for b in blocks[:first])
        if stray:
            blocks[first]["count"] += stray
    # 由深至淺，把直接子標題的計數累加到父標題（避免孫節點重複計算）
    for pos in range(len(idxs) - 1, -1, -1):
        i = idxs[pos]
        lvl = int(blocks[i]["kind"][1])
        # 找最近的前一個層級更小的標題作為父節點
        parent_pos = None
        for k in range(pos - 1, -1, -1):
            parent_lvl = int(blocks[idxs[k]]["kind"][1])
            if parent_lvl < lvl:
                parent_pos = k
                break
        if parent_pos is not None:
            blocks[idxs[parent_pos]]["count"] += blocks[i]["count"]
    for i, b in enumerate(blocks):
        if b["kind"] == "qa":
            b["qid"] = "question-" + slug_id(b["qa"].get("qtext", "") + str(i))
            b["aid"] = "answer-" + slug_id(b["qa"].get("atext", "") + str(i))
        elif b["kind"] in ("para", "quote", "strong"):
            b["pid"] = "p-" + slug_id(b.get("text", "") + str(i))
    return blocks


# ---------------------------------------------------------------------- #
# HTML 片段
# ---------------------------------------------------------------------- #

_HEAD_TMPL = """<!DOCTYPE html>
<html lang="{html_lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
{prepaint_head}
<link rel="icon" type="image/x-icon" href="favicon.ico">
<link rel="stylesheet" href="{shared_style_css}">
<link rel="stylesheet" href="assets/css/books.css">
<script src="{shared_i18n_js}"></script>
<script src="assets/js/w2e-config.js" defer></script>
{extra_head}
<script src="{shared_script_js}" defer></script>
<script src="/lang-switch.js" defer></script>
</head>
<body>
<div id="top"></div>
<header class="{header_class}">
<nav class="nav-home" aria-label="站内导航">
{nav_left_content}
</nav>
<div class="lang-switch">
{lang_switch_links}
</div>
</header>
"""

_TRAD_SUFFIX = "_trad"


def _seo_clean_title(raw_title):
    """書名清理：移除前導序號（如「01《坐禅》」→「《坐禅》」），供 og:title／描述使用。"""
    import re

    text = re.sub(r"^\s*\d+\s*", "", raw_title or "").strip()
    return text or (raw_title or "").strip()


def _build_seo_head(filename, is_trad, seo_title, description, og_type):
    """組裝 SEO head：meta description、canonical、簡繁 hreflang、og: 分享標籤。

    文字一律以簡體寫入；繁版由 convert_html_to_trad() 整頁轉換
    （屬性轉換清單含 content，meta 內文會跟著轉繁）。
    """
    base = "%s/%s/" % (SITE_BASE_URL, EBOOK_URL_PATH)
    canonical = base + filename
    if is_trad:
        trad_href = canonical
        simp_href = base + filename.replace(_TRAD_SUFFIX + ".html", ".html")
    else:
        simp_href = canonical
        trad_href = base + filename.replace(".html", _TRAD_SUFFIX + ".html")
    default_href = trad_href if SEO_HREFLANG_DEFAULT == "zh-Hant" else simp_href
    og_image = "%s/%s" % (SITE_BASE_URL, OG_IMAGE_PATH)
    return "\n".join(
        [
            '<meta name="description" content="%s">' % esc(description),
            '<link rel="canonical" href="%s">' % canonical,
            '<link rel="alternate" hreflang="zh-Hant" href="%s">' % trad_href,
            '<link rel="alternate" hreflang="zh-Hans" href="%s">' % simp_href,
            '<link rel="alternate" hreflang="x-default" href="%s">' % default_href,
            '<meta property="og:type" content="%s">' % og_type,
            '<meta property="og:title" content="%s">' % esc(seo_title),
            '<meta property="og:description" content="%s">' % esc(description),
            '<meta property="og:url" content="%s">' % canonical,
            '<meta property="og:image" content="%s">' % og_image,
            '<meta property="og:site_name" content="%s">' % esc(SEO_SITE_NAME),
        ]
    )


_INDEX_SEARCH_TMPL = """
<!-- 搜索激活按钮 -->
<div class="search-activation">
  <button class="search-activate-btn" id="search-activate-btn">
    启用全文搜索
  </button>
</div>

<!-- 搜索功能（默认隐藏） -->
<div class="search-container" id="search-container" style="display: none;">
  <div class="search-box">
    <input type="text" id="search-input" placeholder="搜索全文内容..." autocomplete="off">
    <div class="search-scope" role="group" aria-label="搜索范围">
      <button type="button" class="search-scope-btn" data-scope="question" aria-pressed="false">问题</button>
      <button type="button" class="search-scope-btn" data-scope="answer" aria-pressed="false">回答</button>
      <button type="button" class="search-scope-btn is-active" data-scope="both" aria-pressed="true">全部</button>
    </div>
    <div class="search-status" id="search-status">正在初始化搜索功能...</div>
  </div>

  <!-- 搜索结果 -->
  <div class="search-results" id="search-results" style="display: none;">
    <div class="search-results-header">
      <span class="search-results-count" id="search-results-count"></span>
      <div class="search-results-actions">
        <button class="search-load-more" id="search-load-more" style="display: none;">显示更多</button>
        <button class="search-load-all" id="search-load-all" style="display: none;">显示全部</button>
        <button class="search-clear" id="search-clear">清除搜索</button>
        <button class="search-collapse" id="search-collapse">收起搜索</button>
      </div>
    </div>
    <ul class="search-results-list" id="search-results-list"></ul>

    <!-- 底部控制按钮 -->
    <div class="search-results-footer">
      <div class="search-results-actions">
        <button class="search-load-more" id="search-load-more-bottom" style="display: none;">显示更多</button>
        <button class="search-load-all" id="search-load-all-bottom" style="display: none;">显示全部</button>
        <button class="search-clear" id="search-clear-bottom">清除搜索</button>
        <button class="search-collapse" id="search-collapse-bottom">收起搜索</button>
      </div>
    </div>
  </div>
</div>
"""


def _toc_header_controls(levels, active, header_tag, header_text, header_id):
    # 單層目錄無切換必要：只留標題，不渲染「顯示層級」控制列
    if len(levels) <= 1:
        return (
            '<div class="toc-header-container">'
            '<%s id="%s">%s</%s>'
            "</div>" % (header_tag, header_id, header_text, header_tag)
        )
    btns = []
    deepest = levels[-1] if levels else 0
    # 「All（显示全部层级）」只在存在第五層（h5）時出現；h6 視為 All 展開時的葉子
    show_all = 5 in levels
    for lv in levels:
        act = " active" if lv == active else ""
        if lv == deepest and show_all:
            # 最深層按鈕 = 「全部」，點擊時連同更深的葉層（如 h6）一起展開
            title = "显示全部层级"
            label = "All"
        elif lv == levels[0]:
            title = "显示第%d层" % lv
            label = str(lv)
        else:
            title = "显示前%d层" % lv
            label = str(lv)
        btns.append(
            '<button class="toc-level-btn%s" data-level="%d" title="%s">%s</button>'
            % (act, lv, title, label)
        )
    return (
        '<div class="toc-header-container">'
        '<%s id="%s">%s</%s>'
        '<div class="toc-level-controls">'
        '<div class="toc-level-label">显示层级</div>'
        '<div class="toc-level-buttons-vertical">%s</div>'
        "</div></div>" % (header_tag, header_id, header_text, header_tag, "".join(btns))
    )


_FLOATING_LEVEL_TMPL = """
<!-- 滚动时显示的浮动层级控制按钮 -->
<div class="floating-level-controls" id="floating-level-controls" style="display: none;">
  <button class="floating-level-toggle" id="floating-level-toggle" title="收缩/展开层级控制">⇄</button>
  <div class="floating-level-content">
    <div class="floating-level-label">层级</div>
    <div class="floating-level-buttons">%s</div>
  </div>
</div>
"""


def _floating_level_buttons(levels, active):
    # 單層目錄無切換必要：整個浮動控制列都不輸出
    if len(levels) <= 1:
        return ""
    btns = []
    deepest = levels[-1] if levels else 0
    # 與 _toc_header_controls 同步：All 只在存在第五層（h5）時出現
    show_all = 5 in levels
    for lv in levels:
        act = " active" if lv == active else ""
        if lv == deepest and show_all:
            title = "显示全部层级"
            label = "All"
        elif lv == levels[0]:
            title = "显示第%d层" % lv
            label = str(lv)
        else:
            title = "显示前%d层" % lv
            label = str(lv)
        btns.append(
            '<button class="floating-level-btn%s" data-level="%d" title="%s">%s</button>'
            % (act, lv, title, label)
        )
    return _FLOATING_LEVEL_TMPL % "".join(btns)


_ACTION_BUTTONS_TMPL = """
<!-- 悬浮操作按钮 -->
<div class="action-buttons">
  <div class="action-menu">
    <button class="action-btn menu-btn" data-action="toggle-menu" title="功能菜单">☰</button>
    <div class="action-menu-items">
      <button class="action-btn" data-action="toc" title="书签">🔖</button>
      <button class="action-btn" data-action="top" title="回到顶部">↑</button>
      <button class="action-btn" data-action="settings" title="设置">⚙️</button>
    </div>
  </div>
</div>
"""

_FLOATING_TOC_TMPL = """
<!-- 悬浮目录 -->
<div class="floating-toc" id="floating-toc">
  <div class="floating-toc-header">
    <div class="floating-toc-tabs">
      <button class="floating-toc-tab active" data-tab="toc">📖 目录</button>
      <button class="floating-toc-tab" data-tab="bookmarks">🔖 书签</button>
    </div>
    <button class="ctrl-btn" data-action="close-toc">✕</button>
  </div>

  <div class="floating-toc-content">
    <h3 id="toc-title">📖 章节目录</h3>
    <ul id="toc-list">
      <!-- 动态生成的内容 -->
    </ul>
    <ul id="bookmarks-list" style="display: none;">
      <!-- 动态生成的书签内容 -->
    </ul>
  </div>
</div>
"""


# ---------------------------------------------------------------------- #
# 章節頁
# ---------------------------------------------------------------------- #


def render_chapter(book, blocks, image_src_map, is_trad,
                   prev_book=None, next_book=None, out_dir=None):
    """產生單書章節頁。blocks 已經過 annotate()。

    image_src_map: xref -> 相對路徑
    out_dir: 輸出目錄（供 <img> 讀取實際檔案解析寬高；None 時省略寬高）
    回傳 (html, search_items)
    """
    fname = book.filename_trad if is_trad else book.filename
    other = book.filename if is_trad else book.filename_trad
    headings = [b for b in blocks if b["kind"] in _HEADING_KINDS]

    total = sum(_content_weight(b) for b in blocks)
    nav_prev = ""
    nav_next = ""
    if prev_book:
        p = prev_book.filename_trad if is_trad else prev_book.filename
        nav_prev = '<a href="%s">⬅️ %s</a>' % (p, esc(prev_book.title))
    if next_book:
        n = next_book.filename_trad if is_trad else next_book.filename
        nav_next = "<a href=\"%s\">%s ➡️</a>" % (n, esc(next_book.title))
    topnav_next = ("<a href=\"%s\">%s ➡️</a>" % (next_book.filename_trad if is_trad else next_book.filename, esc(next_book.title))) if next_book else ""

    # ---- 章內目錄 ----
    used_levels = sorted({int(b["kind"][1]) for b in headings})
    toc_levels = [lv for lv in (2, 3, 4, 5) if lv in used_levels] or [2]
    active_level = 3 if 3 in toc_levels else toc_levels[0]

    # 章內目錄：語意巢狀 <ul>（螢幕閱讀器可感知結構）；視覺仍為扁平——
    # 縮排由共用 CSS（04a-toc-levels.css）歸零，JS 巢狀/扁平兩種結構都支援。
    heading_levels = [int(b["kind"][1]) for b in headings]
    expandables = [
        i + 1 < len(heading_levels) and heading_levels[i + 1] > lvl
        for i, lvl in enumerate(heading_levels)
    ]

    parts = ["<ul>\n"]
    prev_lvl = toc_levels[0]
    open_li = False
    for b, lvl, expandable in zip(headings, heading_levels, expandables):
        if lvl > prev_lvl:
            parts.append("<ul>\n" * (lvl - prev_lvl))
        elif lvl < prev_lvl:
            if open_li:
                parts.append("</li>\n")
                open_li = False
            parts.append("</ul>\n</li>\n" * (prev_lvl - lvl))
        elif open_li:
            parts.append("</li>\n")
            open_li = False
        icon = (
            '<button type="button" class="toc-expand-icon" data-level="%d"'
            ' aria-label="展开或收合子目录" aria-expanded="true">▼</button>' % lvl
        ) if expandable else ""
        parts.append(
            '<li class="toc-item toc-level-%d" data-level="%d">'
            '%s<a href="#%s">%s</a><span class="toc-count">(%d)</span>\n'
            % (lvl, lvl, icon, b["sid"], esc(b["text"]), b["count"])
        )
        open_li = True
        prev_lvl = lvl
    if open_li:
        parts.append("</li>\n")
    parts.append("</ul>\n</li>\n" * max(0, prev_lvl - toc_levels[0]))
    parts.append("</ul>")
    chapter_toc_html = "".join(parts)

    # ---- 內文 ----
    body = []
    search_items = []
    sid_counter = [0]

    def add_item(item_type, content, url, title):
        # 書本名稱（TOC 第一層）前綴，便於搜尋結果辨識出處；去除 01/02 等編號
        import re as _re
        _pure_book = _re.sub(r"^\d+\s*", "", book.title).strip()
        full_title = "%s | %s" % (_pure_book, title) if not title.startswith(_pure_book) and not title.startswith(book.title) else title
        # 若 title 已含完整帶編號書名，也替換為純淨書名
        if full_title.startswith(book.title):
            full_title = _pure_book + full_title[len(book.title):]
        sid_counter[0] += 1
        # context 欄位已移除（與 content 重複、佔索引體積；顯示摘要由
        # 01c getBestContextForHighlight 從 content 現場截取）
        search_items.append({
            "id": "%s-%d" % (fname, sid_counter[0]),
            "title": full_title,
            "type": item_type,
            "content": content,
            "url": url,
            "book": _pure_book,
        })

    # 「回到目錄」連結：仿 wenda2_ebook 的 insert_back_to_top，於每個章節
    # （各層級標題）之間插入，讓讀者回到本章目錄；單書內頁改叫「回到目錄」。
    _back_to_toc = '<div class="back-to-top"><a href="#top">🔝 回到目录</a></div>'
    _seen_heading = False
    cur_section = book.title
    _series = getattr(book, "series", None)  # 講經系列：段落級 data-start/data-end 注入
    for b in blocks:
        k = b["kind"]
        if k in _HEADING_KINDS:
            if _seen_heading:
                body.append(_back_to_toc)
            _seen_heading = True
            tag = k
            cur_section = b["text"]
            play = ""
            n = b.get("lecture")
            if n is not None:
                play = lecture_play_button(getattr(book, "series", None), n, b["text"])
            body.append(
                '<%s id="%s">%s%s<span class="chapter-qa-count">(%d)</span></%s>'
                % (tag, b["sid"], esc(b["text"]), play, b["count"], tag)
            )
            add_item(TYPE_HEADING, "%s(%d)" % (b["text"], b["count"]),
                     "%s#%s" % (fname, b["sid"]), "%s(%d)" % (b["text"], b["count"]))
        elif k == "para":
            body.append('<p id="%s" class="para-block"%s>%s</p>'
                        % (b["pid"], para_time_attrs(_series, b["pid"]),
                           nl2br(esc(b["text"]))))
            add_item(TYPE_CONTENT, b["text"], "%s#%s" % (fname, b["pid"]),
                     cur_section)
        elif k == "strong":
            body.append('<p id="%s" class="para-block"%s><strong>%s</strong></p>'
                        % (b["pid"], para_time_attrs(_series, b["pid"]),
                           nl2br(esc(b["text"]))))
            add_item(TYPE_CONTENT, b["text"], "%s#%s" % (fname, b["pid"]),
                     cur_section)
        elif k == "quote":
            body.append('<div class="sutra-text para-block" id="%s"%s>%s</div>'
                        % (b["pid"], para_time_attrs(_series, b["pid"]),
                           nl2br(esc(b["text"]))))
            add_item(TYPE_CONTENT, b["text"], "%s#%s" % (fname, b["pid"]),
                     cur_section)
        elif k == "label":
            body.append('<div class="label-heading">%s</div>' % esc(b["text"]))
        elif k == "img":
            src = image_src_map.get(b.get("xref"))
            if src:
                # 統一 <img> 標記（lazy + 語意 alt + 實檔寬高）來自 word2ebook
                # 的 utils/image_markup.py——經 main.py 以 importlib 載入共用
                abs_img = os.path.join(out_dir, src) if out_dir else None
                body.append(
                    '<figure class="book-img">%s</figure>'
                    % render_img_tag(src, cur_section, abs_img)
                )
        elif k == "qa":
            qa = b["qa"]
            meta_bits = []
            if qa.get("questioner"):
                meta_bits.append('<span class="questioner">%s</span>'
                                 % esc(qa["questioner"]))
            if qa.get("qtime"):
                meta_bits.append('<span class="question-time">%s</span>'
                                 % esc(qa["qtime"]))
            title_bits = qa.get("questioner") or ""
            if qa.get("qtime"):
                title_bits += " " + qa["qtime"]
            # 師父連續發帖時，後幾則沒有對應的提問，不輸出空的提問區塊
            qhtml = ""
            if meta_bits or qa.get("qtext"):
                qhtml = (
                    '<div class="question" id="%s">\n<div class="question-meta">\n%s\n'
                    '</div>\n<div class="question-text">%s</div>\n</div>'
                    % (b["qid"], "\n".join(meta_bits), nl2br(esc(qa.get("qtext", ""))))
                )
                add_item(TYPE_QUESTION, qa.get("qtext", ""),
                         "%s#%s" % (fname, b["qid"]),
                         title_bits or cur_section)
            ahtml = ""
            if qa.get("atext"):
                ameta = ['<span class="answerer">Taiguanglin</span>']
                if qa.get("atime"):
                    ameta.append('<span class="answer-time">%s</span>'
                                 % esc(qa["atime"]))
                ahtml = (
                    '<div class="answer" id="%s">\n<div class="answer-meta">\n'
                    '%s\n</div>\n'
                    '<div class="answer-text">%s</div>\n</div>'
                    % (b["aid"], "\n".join(ameta), nl2br(esc(qa["atext"])))
                )
                add_item(TYPE_ANSWER, qa["atext"], "%s#%s" % (fname, b["aid"]),
                         title_bits or cur_section)
            # 問+答成對 → 包進語意 <article>（螢幕閱讀器可逐對導覽）；
            # <hr/> 分隔線保持在 article 之外。僅有單側時照舊輸出。
            if qhtml and ahtml:
                body.append('<article class="qa-pair">')
                body.append(qhtml)
                body.append(ahtml)
                body.append("</article>")
            else:
                if qhtml:
                    body.append(qhtml)
                if ahtml:
                    body.append(ahtml)
            body.append("<hr/>")

# 單書內頁：只回本系列總目錄（跨書連結僅出現在首頁）
    _book_toc_href = "index_trad.html" if is_trad else "index.html"
    _book_toc_text = "📖 坐禪與講經總目錄" if is_trad else "📖 坐禅与讲经总目录"
    _header_class = "header-nav"
    _nav_left_content = f'<a href="{_book_toc_href}">{_book_toc_text}</a>'
    _lang_switch_links = build_lang_switch_links(book.filename, book.filename_trad, is_trad)
    # SEO：<title>「書名・系列名｜站名」；meta 以簡體寫入，繁版整頁轉換
    _clean_title = _seo_clean_title(book.title)
    _seo_title = "%s・%s｜%s" % (_clean_title, SITE_TITLE, SEO_SITE_NAME)
    _seo_description = SEO_CHAPTER_DESCRIPTION.format(title=_clean_title)
    _page_filename = book.filename_trad if is_trad else book.filename
    html = _HEAD_TMPL.format(
        title=esc(_seo_title),
        header_class=_header_class,
        nav_left_content=_nav_left_content,
        lang_switch_links=_lang_switch_links,
        html_lang="zh-Hant" if is_trad else "zh-Hans",
        prepaint_head=_DARK_MODE_PREPAINT,
        shared_style_css=shared_asset_url("css/style.css"),
        shared_i18n_js=shared_asset_url("js/i18n-text.js"),
        shared_script_js=shared_asset_url("js/script.js"),
        extra_head=_build_seo_head(
            _page_filename, is_trad, _seo_title, _seo_description, "article"
        ),
    )
    html += (
        '<div class="top-nav"><div class="top-nav-buttons">%s</div></div>\n' % topnav_next
    )
    # <main> 語意地標：正文（含章節目錄、內文、上下冊導航）皆屬主要內容
    html += "<main>\n"
    html += '<h1 id="%s">%s<span class="chapter-qa-count">(%d)</span></h1>\n' % (
        slug_id(book.title), esc(book.title), total)
    html += _toc_header_controls(toc_levels, active_level,
                                 "h2", "本章目录", "chapter-toc-header")
    html += '<div class="toc" id="chapter-toc">\n%s\n</div>\n' % chapter_toc_html
    html += _floating_level_buttons(toc_levels, active_level)
    html += "\n".join(body)
    html += '\n<div class="back-to-top"><a href="#top">🔝 回到目录</a></div>\n'
    html += '<div class="nav-footer">%s%s</div>\n' % (
        nav_prev + "\n" if nav_prev else "",
        nav_next,
    )
    html += "</main>\n"
    html += "</body>\n</html>\n"
    return html, search_items


# ---------------------------------------------------------------------- #
# 首頁
# ---------------------------------------------------------------------- #


def render_index(books_meta, source_pdfs, is_trad):
    """books_meta: [{config, blocks}]（已 annotate）。"""
    lines = ["<ul class='toc-level-1'>"]
    for i, bm in enumerate(books_meta):
        bc = bm["config"]
        blocks = bm["blocks"]
        total = sum(_content_weight(b) for b in blocks)
        f = bc.filename_trad if is_trad else bc.filename
        # 收集該書的標題節點，映射 h2→2, h3→3, h4→4
        headings = [b for b in blocks if b["kind"] in _HEADING_KINDS]
        kind_to_level = {"h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
        # 書籍節點（第 1 層）
        book_icon = (
            '<button type="button" class="toc-expand-icon" data-level="1"'
            ' aria-label="展开或收合子目录" aria-expanded="true">▼</button>'
            if headings else ""
        )
        lines.append(
            '<li class="toc-item toc-chapter" data-level="1" data-chapter="%d">'
            '%s'
            '<a href="%s">%s</a>'
            '<span class="toc-count">(%d)</span>'
            % (i, book_icon, f, esc(bc.title), total)
        )
        # 構建樹：每個節點 {block, children}
        root_children = []
        stack = []  # (level, node)
        for b in headings:
            lvl = kind_to_level[b["kind"]]
            node = {"block": b, "children": [], "level": lvl}
            # 找到父節點（level-1）
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            if stack:
                stack[-1][1]["children"].append(node)
            else:
                root_children.append(node)
            stack.append((lvl, node))

        def _render_nodes(nodes):
            if not nodes:
                return
            lines.append("<ul>")
            for node in nodes:
                b = node["block"]
                lvl = node["level"]
                has_children = len(node["children"]) > 0
                icon = (
                    '<button type="button" class="toc-expand-icon" data-level="%d"'
                    ' aria-label="展开或收合子目录" aria-expanded="true">▼</button>' % lvl
                    if has_children else ""
                )
                lines.append(
                    '<li class="toc-item toc-level-%d" data-level="%d" data-chapter="%d">'
                    '%s<a href="%s#%s">%s</a>'
                    '<span class="toc-count">(%d)</span>'
                    % (lvl, lvl, i, icon, f, b["sid"], esc(b["text"]), b["count"])
                )
                if has_children:
                    _render_nodes(node["children"])
                lines.append("</li>")
            lines.append("</ul>")

        _render_nodes(root_children)
        lines.append("</li>")
    lines.append("</ul>")
    main_toc = "\n".join(lines)

    src_links = []
    for pdf_name in source_pdfs:
        quoted = pdf_name.replace("&", "&amp;").replace('"', "&quot;")
        src_links.append(
            '<a class="source-link" href="../books/%s" download="%s">%s</a>'
            % (quoted, quoted, quoted)
        )

    _idx_cross_href = "../wenda2_ebook/index_trad.html" if is_trad else "../wenda2_ebook/index.html"
    _idx_cross_text = "📚 問答錄2" if is_trad else "📚 问答录2"
    _site_home_text = "🏠 首頁" if is_trad else "🏠 首页"
    _header_class = "header-nav index-header"
    _site_home_href = "../index.html"
    _nav_left_content = f'<a href="{_site_home_href}">{_site_home_text}</a> | <a href="{_idx_cross_href}">{_idx_cross_text}</a>'
    _lang_switch_links = build_lang_switch_links("index.html", "index_trad.html", is_trad)
    # SEO：<title>「系列名｜站名」＋meta（website）；繁版由整頁轉換處理
    _seo_title = "%s｜%s" % (SITE_TITLE, SEO_SITE_NAME)
    _index_filename = "index_trad.html" if is_trad else "index.html"
    html = _HEAD_TMPL.format(
        title=esc(_seo_title),
        header_class=_header_class,
        nav_left_content=_nav_left_content,
        lang_switch_links=_lang_switch_links,
        html_lang="zh-Hant" if is_trad else "zh-Hans",
        prepaint_head=_DARK_MODE_PREPAINT,
        shared_style_css=shared_asset_url("css/style.css"),
        shared_i18n_js=shared_asset_url("js/i18n-text.js"),
        shared_script_js=shared_asset_url("js/script.js"),
        extra_head=_build_seo_head(
            _index_filename, is_trad, _seo_title, SEO_INDEX_DESCRIPTION, "website"
        )
        + "\n"
        + _MINISEARCH_HEAD,
    )
    # <main> 語意地標：書名、搜尋、目錄與來源檔連結屬主要內容；
    # 懸浮操作按鈕/懸浮目錄屬工具列，留在 main 之外。
    html += "<main>\n"
    html += "<h1>%s</h1>\n" % esc(SITE_TITLE)
    html += _INDEX_SEARCH_TMPL
    html += _toc_header_controls([1, 2, 3, 4, 5], 2, "h2", "目录", "toc-header")
    html += '<div class="toc" id="main-toc">\n%s\n</div>\n' % main_toc
    html += (
        '\n<p class="source-filename" id="source-filename">Source: %s</p>\n'
        % "、".join(src_links)
    )
    html += "</main>\n"
    html += _ACTION_BUTTONS_TMPL
    html += _FLOATING_TOC_TMPL
    html += _floating_level_buttons([1, 2, 3, 4, 5], 2)
    html += "</body>\n</html>\n"
    return html
