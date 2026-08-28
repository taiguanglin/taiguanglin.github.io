"""HTML / 搜索索引生成：输出与 wenda2_ebook 同风格的电子书页面。"""

import hashlib

from config import (
    SITE_TITLE,
    TYPE_ANSWER,
    TYPE_CONTENT,
    TYPE_HEADING,
    TYPE_QUESTION,
)

_HEADING_KINDS = ("h2", "h3", "h4")

# 首页搜索需要 MiniSearch（章节页不用）
_MINISEARCH_HEAD = (
    '<script src="https://cdn.jsdelivr.net/npm/minisearch@6.3.0/dist/umd/index.min.js">'
    "</script>\n"
    "<script>\n"
    "// 备用CDN加载\n"
    "if (typeof MiniSearch === 'undefined') {\n"
    "  console.log('主CDN失败，尝试备用CDN...');\n"
    "  const script = document.createElement('script');\n"
    "  script.src = 'https://unpkg.com/minisearch@6.3.0/dist/umd/index.min.js';\n"
    "  script.onload = function() {\n"
    "    if (typeof initSearch === 'function') { initSearch(); }\n"
    "  };\n"
    "  script.onerror = function() {\n"
    "    console.error('所有CDN都失败了，搜索功能不可用');\n"
    "    const searchInput = document.getElementById('search-input');\n"
    "    const searchStatus = document.getElementById('search-status');\n"
    "    if (searchInput) searchInput.disabled = true;\n"
    "    if (searchStatus) searchStatus.textContent = "
    "getText('搜索功能暂不可用（网络问题）', '搜尋功能暫不可用（網路問題）');\n"
    "  };\n"
    "  document.head.appendChild(script);\n"
    "}\n"
    "</script>"
)


def slug_id(text):
    """由标题产生稳定的元素 ID。"""
    return "s" + hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


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
    """Build language switch links with per-language labels.

    對照 wenda2_ebook：繁頁的「简体」標籤維持簡體字（不隨頁面轉繁），「繁體」
    維持繁體字。ebook 的繁頁在 main.py 會對整頁跑 OpenCC s2t，因此這裡用數字
    HTML 實體輸出標籤文字，讓 OpenCC（只作用於字元）不會誤轉它們，瀏覽器仍會
    正確顯示「简体 / 繁體」。
    """
    # &#31616;&#20307; = "简体"（簡體字）, &#32321;&#39636; = "繁體"（繁體字）
    simp_entity = "&#31616;&#20307;"
    trad_entity = "&#32321;&#39636;"
    return (f'<a href="{simp_file}">{simp_entity}</a> | '
            f'<a href="{trad_file}">{trad_entity}</a>')


def nl2br(text):
    return text.replace("\n", "<br/>")


# ---------------------------------------------------------------------- #
# 區塊分析：元素 ID 與每個標題的內容計數
# ---------------------------------------------------------------------- #


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
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="icon" type="image/x-icon" href="favicon.ico">
<link rel="stylesheet" href="assets/css/style.css">
<link rel="stylesheet" href="assets/css/books.css">
<script src="assets/js/i18n-text.js"></script>
{extra_head}
<script src="assets/js/script.js" defer></script>
</head>
<body>
<div id="top"></div>
<div class="{header_class}">
<div class="nav-home">
{nav_left_content}
</div>
<div class="lang-switch">
{lang_switch_links}
</div>
</div>
"""

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
    btns = []
    for lv in levels:
        act = " active" if lv == active else ""
        title = "显示第%d层" % lv if lv == levels[0] else "显示前%d层" % lv
        btns.append(
            '<button class="toc-level-btn%s" data-level="%d" title="%s">%d</button>'
            % (act, lv, title, lv)
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
    btns = []
    for lv in levels:
        act = " active" if lv == active else ""
        title = "显示第%d层" % lv if lv == levels[0] else "显示前%d层" % lv
        btns.append(
            '<button class="floating-level-btn%s" data-level="%d" title="%s">%d</button>'
            % (act, lv, title, lv)
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
                   prev_book=None, next_book=None):
    """產生單書章節頁。blocks 已經過 annotate()。

    image_src_map: xref -> 相對路徑
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
    toc_levels = [lv for lv in (2, 3, 4) if lv in used_levels] or [2]
    active_level = 3 if 3 in toc_levels else toc_levels[0]
    has_children = {int(b["kind"][1]) + 1 for b in headings}
    max_level = max(toc_levels)

    parts = []
    parts.append("<ul>\n")
    open_li = False
    for b in headings:
        lvl = int(b["kind"][1])
        child_lv = lvl + 1
        expandable = child_lv in has_children and child_lv in toc_levels and any(
            int(h["kind"][1]) == child_lv for h in headings
        )
        visible = "True" if lvl == toc_levels[0] or lvl <= active_level else "False"
        icon = ('<span class="toc-expand-icon" data-level="%d">▼</span>' % lvl) if expandable else ""
        if open_li:
            parts.append("</li>\n")
            open_li = False
        parts.append(
            '<li class="toc-item toc-level-%d" data-default-visible="%s" data-level="%d">'
            '%s<a href="#%s">%s</a><span class="toc-count">(%d)</span>'
            % (lvl, visible, lvl, icon, b["sid"], esc(b["text"]), b["count"])
        )
        open_li = True
    if open_li:
        parts.append("</li>\n")
    parts.append("</ul>")
    chapter_toc_html = "".join(parts)

    # ---- 內文 ----
    body = []
    search_items = []
    sid_counter = [0]

    def add_item(item_type, content, url, title, context=None):
        # 書本名稱（TOC 第一層）前綴，便於搜尋結果辨識出處；去除 01/02 等編號
        import re as _re
        _pure_book = _re.sub(r"^\d+\s*", "", book.title).strip()
        full_title = "%s | %s" % (_pure_book, title) if not title.startswith(_pure_book) and not title.startswith(book.title) else title
        # 若 title 已含完整帶編號書名，也替換為純淨書名
        if full_title.startswith(book.title):
            full_title = _pure_book + full_title[len(book.title):]
        sid_counter[0] += 1
        search_items.append({
            "id": "%s-%d" % (fname, sid_counter[0]),
            "title": full_title,
            "type": item_type,
            "content": content,
            "context": context if context is not None else content,
            "url": url,
            "book": _pure_book,
        })

    cur_section = book.title
    for b in blocks:
        k = b["kind"]
        if k in _HEADING_KINDS:
            tag = k
            cur_section = b["text"]
            body.append(
                '<%s id="%s">%s<span class="chapter-qa-count">(%d)</span></%s>'
                % (tag, b["sid"], esc(b["text"]), b["count"], tag)
            )
            add_item(TYPE_HEADING, "%s(%d)" % (b["text"], b["count"]),
                     "%s#%s" % (fname, b["sid"]), "%s(%d)" % (b["text"], b["count"]))
        elif k == "para":
            body.append('<p id="%s">%s</p>' % (b["pid"], nl2br(esc(b["text"]))))
            add_item(TYPE_CONTENT, b["text"], "%s#%s" % (fname, b["pid"]),
                     cur_section, b["text"][:80])
        elif k == "strong":
            body.append('<p id="%s"><strong>%s</strong></p>'
                        % (b["pid"], nl2br(esc(b["text"]))))
            add_item(TYPE_CONTENT, b["text"], "%s#%s" % (fname, b["pid"]),
                     cur_section, b["text"][:80])
        elif k == "quote":
            body.append('<div class="sutra-text" id="%s">%s</div>'
                        % (b["pid"], nl2br(esc(b["text"]))))
            add_item(TYPE_CONTENT, b["text"], "%s#%s" % (fname, b["pid"]),
                     cur_section, b["text"][:80])
        elif k == "label":
            body.append('<div class="label-heading">%s</div>' % esc(b["text"]))
        elif k == "img":
            src = image_src_map.get(b.get("xref"))
            if src:
                body.append(
                    '<figure class="book-img"><img loading="lazy" src="%s" alt="%s"></figure>'
                    % (src, esc(cur_section))
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
            if meta_bits or qa.get("qtext"):
                body.append(
                    '<div class="question" id="%s">\n<div class="question-meta">\n%s\n'
                    '</div>\n<div class="question-text">%s</div>\n</div>'
                    % (b["qid"], "\n".join(meta_bits), nl2br(esc(qa.get("qtext", ""))))
                )
                add_item(TYPE_QUESTION, qa.get("qtext", ""),
                         "%s#%s" % (fname, b["qid"]),
                         title_bits or cur_section, qa.get("qtext", "")[:80])
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
                body.append(ahtml)
                add_item(TYPE_ANSWER, qa["atext"], "%s#%s" % (fname, b["aid"]),
                         title_bits or cur_section, qa["atext"][:80])
            body.append("<hr/>")

# 單書內頁：只回本系列總目錄（跨書連結僅出現在首頁）
    _book_toc_href = "index_trad.html" if is_trad else "index.html"
    _book_toc_text = "📖 坐禪系列總目錄" if is_trad else "📖 坐禅系列总目录"
    _header_class = "header-nav"
    _nav_left_content = f'<a href="{_book_toc_href}">{_book_toc_text}</a>'
    _lang_switch_links = build_lang_switch_links(book.filename, book.filename_trad, is_trad)
    html = _HEAD_TMPL.format(
        title=esc(book.title),
        header_class=_header_class,
        nav_left_content=_nav_left_content,
        lang_switch_links=_lang_switch_links,
        extra_head="",
    )
    html += (
        '<div class="top-nav"><div class="top-nav-buttons">%s</div></div>\n' % topnav_next
    )
    html += '<h1 id="%s">%s<span class="chapter-qa-count">(%d)</span></h1>\n' % (
        slug_id(book.title), esc(book.title), total)
    html += _toc_header_controls(toc_levels, active_level,
                                 "h3", "本章目录", "chapter-toc-header")
    html += '<div class="toc" id="chapter-toc">\n%s\n</div>\n' % chapter_toc_html
    html += _floating_level_buttons(toc_levels, active_level)
    html += "\n".join(body)
    html += '\n<div class="back-to-top"><a href="#top">🔝 回到本章目录</a></div>\n'
    html += '<div class="nav-footer">%s%s</div>\n' % (
        nav_prev + "\n" if nav_prev else "",
        nav_next,
    )
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
        # 書籍節點（第 1 層）
        lines.append(
            '<li class="toc-item toc-chapter" data-level="1" data-chapter="%d" '
            'data-default-visible="true">'
            '<span class="toc-expand-icon" data-level="1">▼</span>'
            '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
            '<span class="toc-count">(%d)</span>' % (i, f, esc(bc.title), total)
        )
        # 收集該書的標題節點，映射 h2→2, h3→3, h4→4
        headings = [b for b in blocks if b["kind"] in _HEADING_KINDS]
        kind_to_level = {"h2": 2, "h3": 3, "h4": 4}
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
                # 預設顯示：只有第 2 層可見（對應首頁預設層級 2）
                visible = "True" if lvl == 2 else "False"
                icon = (
                    '<span class="toc-expand-icon" data-level="%d">▼</span>' % lvl
                    if has_children else ""
                )
                lines.append(
                    '<li class="toc-item toc-level-%d" data-level="%d" '
                    'data-default-visible="%s" data-chapter="%d">'
                    '%s<a href="%s#%s" target="_blank" rel="noopener noreferrer">%s</a>'
                    '<span class="toc-count">(%d)</span>'
                    % (lvl, lvl, visible, i, icon, f, b["sid"], esc(b["text"]), b["count"])
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
    _site_home_text = "🏠 網站首頁" if is_trad else "🏠 网站首页"
    _header_class = "header-nav index-header"
    _site_home_href = "../index.html"
    _nav_left_content = f'<a href="{_site_home_href}">{_site_home_text}</a> | <a href="{_idx_cross_href}">{_idx_cross_text}</a>'
    _lang_switch_links = build_lang_switch_links("index.html", "index_trad.html", is_trad)
    html = _HEAD_TMPL.format(
        title=esc(SITE_TITLE),
        header_class=_header_class,
        nav_left_content=_nav_left_content,
        lang_switch_links=_lang_switch_links,
        extra_head=_MINISEARCH_HEAD,
    )
    html += "<h1>%s</h1>\n" % esc(SITE_TITLE)
    html += _INDEX_SEARCH_TMPL
    html += _toc_header_controls([1, 2, 3, 4], 2, "h2", "目录", "toc-header")
    html += '<div class="toc" id="main-toc">\n%s\n</div>\n' % main_toc
    html += _ACTION_BUTTONS_TMPL
    html += _FLOATING_TOC_TMPL
    html += (
        '\n<p class="source-filename" id="source-filename">Source: %s</p>\n'
        % "、".join(src_links)
    )
    html += _floating_level_buttons([1, 2, 3, 4], 2)
    html += "</body>\n</html>\n"
    return html
