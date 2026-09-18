#!/usr/bin/env python3
"""session_knowledge.html 生成器（tool/session_knowledge/build.py）

單一真相來源：repo 根目錄的 SESSION_KNOWLEDGE.md（手編）。
本腳本把該 md（受限子集）轉成 HTML，包上站台 chrome（導覽／hero／免責聲明／footer），
生成全靜態的 session_knowledge.html。頁面無 inline JS：繁簡由 lang-switch.js 全頁處理。

支援的 md 子集（刻意受限，勿擴充）：
  # 標題            → 頁面 <title> 與 hero h1（僅第一個 # 生效）
  ## 節             → <h2 id="sk-N">，並進 TOC
  ### / ####        → h3 / h4
  | 表格 |          → sk-table（第二行須為 |---| 分隔列）
  - 清單 / 1. 編號  → ul / ol（不支援巢狀）
  > 引用            → blockquote
  ``` 圍欄          → pre.sk-code（只轉義，不做行內處理）
  ---               → hr
  行內：**粗體**、`code`、[文字](連結)

用法：在 repo 根目錄執行  python3 tool/session_knowledge/build.py
"""
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'SESSION_KNOWLEDGE.md')
OUT = os.path.join(ROOT, 'session_knowledge.html')


def inline(t):
    """行內處理：先轉義，再粗體／code／連結。"""
    t = html.escape(t, quote=False)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'`([^`]+?)`', r'<code>\1</code>', t)
    t = re.sub(r'\[([^\]]+?)\]\(([^)\s]+?)\)', r'<a href="\2">\1</a>', t)
    return t


def cells(row):
    r = row.strip()
    if r.startswith('|'):
        r = r[1:]
    if r.endswith('|'):
        r = r[:-1]
    return [inline(c.strip()) for c in r.split('|')]


def parse(md):
    lines = md.split('\n')
    out, toc = [], []
    title = ''
    in_code = False
    code_buf = []
    n_h2 = 0
    n_tables = 0
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('```'):
            if in_code:
                out.append('<pre class="sk-code">' + html.escape('\n'.join(code_buf)) + '</pre>')
                code_buf = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(ln)
            i += 1
            continue
        if ln.startswith('# ') and not title:
            title = ln[2:].strip()
            i += 1
            continue
        if ln.startswith('## '):
            h = ln[3:].strip()
            hid = 'sk-%d' % n_h2
            toc.append((hid, h))
            out.append('<h2 class="sk-h2" id="%s">%s</h2>' % (hid, inline(h)))
            n_h2 += 1
            i += 1
            continue
        if ln.startswith('### '):
            out.append('<h3 class="sk-h3">%s</h3>' % inline(ln[4:].strip()))
            i += 1
            continue
        if ln.startswith('#### '):
            out.append('<h4 class="sk-h4">%s</h4>' % inline(ln[5:].strip()))
            i += 1
            continue
        if ln.strip() == '---':
            out.append('<hr class="sk-hr">')
            i += 1
            continue
        if ln.startswith('|'):
            tbl = []
            while i < len(lines) and lines[i].startswith('|'):
                tbl.append(lines[i])
                i += 1
            if len(tbl) < 2 or not re.match(r'^\|[\s:-]+\|', tbl[1]):
                sys.exit('表格分隔列格式錯誤：%r' % (tbl[1] if tbl else '(空表格)'))
            n_tables += 1
            head = cells(tbl[0])
            rows = [cells(r) for r in tbl[2:]]
            th = '<thead><tr>' + ''.join('<th>%s</th>' % c for c in head) + '</tr></thead>'
            tb = '<tbody>' + ''.join(
                '<tr>' + ''.join('<td>%s</td>' % c for c in r) + '</tr>' for r in rows) + '</tbody>'
            out.append('<div class="sk-table-wrap"><table class="sk-table">%s%s</table></div>' % (th, tb))
            continue
        if ln.startswith('- '):
            items = []
            while i < len(lines) and lines[i].startswith('- '):
                items.append(inline(lines[i][2:].strip()))
                i += 1
            out.append('<ul class="sk-list">' + ''.join('<li>%s</li>' % it for it in items) + '</ul>')
            continue
        if re.match(r'^\d+\. ', ln):
            items = []
            while i < len(lines) and re.match(r'^\d+\. ', lines[i]):
                items.append(inline(re.sub(r'^\d+\. ', '', lines[i]).strip()))
                i += 1
            out.append('<ol class="sk-list">' + ''.join('<li>%s</li>' % it for it in items) + '</ol>')
            continue
        if ln.startswith('> '):
            quotes = []
            while i < len(lines) and lines[i].startswith('> '):
                quotes.append(inline(lines[i][2:].strip()))
                i += 1
            out.append('<blockquote class="sk-quote">' + '<br>'.join(quotes) + '</blockquote>')
            continue
        if ln.strip() == '':
            i += 1
            continue
        para = []
        while (i < len(lines) and lines[i].strip() != ''
               and not lines[i].startswith(('#', '|', '-', '>', '```'))
               and lines[i].strip() != '---'
               and not re.match(r'^\d+\. ', lines[i])):
            para.append(inline(lines[i].strip()))
            i += 1
        out.append('<p class="sk-p">%s</p>' % ''.join(para))
    return title, toc, out, n_h2, n_tables


def build():
    if not os.path.exists(SRC):
        sys.exit('找不到 SESSION_KNOWLEDGE.md：%s' % SRC)
    title, toc, body, n_h2, n_tables = parse(open(SRC, encoding='utf-8').read())

    toc_html = ''.join('<a class="sk-toc-item" href="#%s">%s</a>' % (hid, inline(h)) for hid, h in toc)
    body_html = '\n'.join(body)

    page = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__TITLE__｜TaiGuangLin 禪師</title>
    <meta name="description" content="九書名詞查證與圖解工程的完整知識庫：查證方法、逐批報告、證據速查表、禁用術語、關鍵節點定稿、腳本與回歸基準。">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="__TITLE__｜TaiGuangLin 禪師">
    <meta property="og:description" content="mindmap.html 名詞查證工程的完整知識萃取，全部存成可復用的知識庫">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://taiguanglin.info/session_knowledge.html">
    <link rel="canonical" href="https://taiguanglin.info/session_knowledge.html">
    <link rel="icon" type="image/x-icon" href="images/favicon.ico">
    <link rel="shortcut icon" type="image/x-icon" href="images/favicon.ico">
    <link rel="stylesheet" href="style.css">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500;600;700;900&family=Noto+Sans+TC:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<script src="/lang-switch.js" defer></script>
</head>
<body>
    <nav class="navbar" id="navbar">
        <div class="nav-container">
            <a href="index.html" class="nav-logo">
                <span class="logo-name">TaiGuangLin</span>
                <span class="logo-sub">次世代終極佛法</span>
            </a>
            <div class="nav-menu" id="nav-menu">
                <a href="index.html" class="nav-link">首頁</a>
                <a href="index.html#about" class="nav-link">禪師</a>
                <a href="index.html#start" class="nav-link">入門路徑</a>
                <a href="index.html#books" class="nav-link">著作</a>
                <a href="wenda2.html" class="nav-link">問答錄 2</a>
                <a href="stories.html" class="nav-link">實修故事</a>
                <div class="nav-dropdown" id="nav-dropdown">
                    <a href="#" class="nav-link nav-dropdown-toggle" id="dropdown-toggle">圖解 ▾</a>
                    <div class="nav-dropdown-menu">
                        <a href="infographic.html" class="nav-dropdown-item">名詞圖解</a>
                        <a href="mindmap.html" class="nav-dropdown-item">名詞關聯心智圖</a>
                        <a href="books_knowledge.html" class="nav-dropdown-item">九書重點知識</a>
                        <a href="wenda2_knowledge.html" class="nav-dropdown-item">問答錄2 重點知識</a>
                        <a href="wenda2_mindmap.html" class="nav-dropdown-item">問答錄2 名詞心智圖</a>
                        <a href="wenda2_knowledge_full.html" class="nav-dropdown-item">問答錄2 知識庫全檔</a>
                    </div>
                </div>
                <a href="index.html#downloads" class="nav-link nav-cta" data-download-trigger>下載資料</a>
            </div>
            <button class="hamburger" id="hamburger" aria-label="開啟選單" aria-expanded="false">
                <span></span><span></span><span></span>
            </button>
        </div>
    </nav>
    <div class="site-menu-veil" id="site-menu-veil"></div>

    <section class="page-hero">
        <div class="container">
            <nav class="crumbs" aria-label="位置">
                <a href="index.html">首頁</a><span class="crumbs-sep">/</span>
                <span aria-current="page">__TITLE__</span>
            </nav>
            <span class="kicker">SESSION · WORK KNOWLEDGE</span>
            <h1 class="display">__TITLE__</h1>
            <p class="lede">九書名詞查證工程的完整知識萃取：查證方法、逐批報告、證據速查、禁用術語、節點定稿、腳本與回歸基準——全部存成可復用的知識庫，改內容改 SESSION_KNOWLEDGE.md 再重跑生成器。</p>
        </div>
    </section>

    <section class="section" style="padding-top: var(--spacing-lg); padding-bottom: 0;">
        <div class="container">
            <div class="note-ai" style="margin-bottom: 20px;">
                <span>本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。</span>
            </div>
            <h2 class="mm-subtitle">目錄</h2>
            <div class="sk-toc">
__TOC__
            </div>
        </div>
    </section>

    <section class="section">
        <div class="container sk-body">
__BODY__
        </div>
    </section>

    <footer class="footer">
        <div class="container">
            <div class="footer-top">
                <div class="footer-brand">
                    <div class="logo-name">TaiGuangLin</div>
                    <p>次世代終極版佛法</p>
                    <p>用現代通俗易懂的語言，傳承純正佛法智慧。</p>
                </div>
                <div class="footer-col">
                    <h4>著作與電子書</h4>
                    <ul>
                        <li><a href="index.html#books">全部著作</a></li>
                        <li><a href="ebook/index_trad.html" target="_blank" rel="noopener noreferrer">坐禪系列電子書</a></li>
                    </ul>
                </div>
                <div class="footer-col">
                    <h4>問答錄2</h4>
                    <ul>
                        <li><a href="wenda2.html">主題目錄（12 章）</a></li>
                        <li><a href="wenda2_ebook/index_trad.html" target="_blank" rel="noopener noreferrer">完整電子書</a></li>
                    </ul>
                </div>
                <div class="footer-col">
                    <h4>更多資源</h4>
                    <ul>
                        <li><a href="infographic.html">名詞圖解</a></li>
                        <li><a href="mindmap.html">名詞關聯心智圖</a></li>
                        <li><a href="books_knowledge.html">九書重點知識</a></li>
                        <li><a href="review.html">名詞複習（閃卡與測驗）</a></li>
                        <li><a href="wenda2_knowledge.html">問答錄2 重點知識</a></li>
                        <li><a href="wenda2_mindmap.html">問答錄2 名詞心智圖</a></li>
                        <li><a href="stories.html">實修故事</a></li>
                        <li><a href="index.html#downloads">資料下載</a></li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                <p>歡迎分享給更多人結法緣</p>
                <p>願一切眾生離苦得樂，早證菩提</p>
            </div>
        </div>
    </footer>

    <script src="shared.js" defer></script>
</body>
</html>
'''
    page = page.replace('__TITLE__', title).replace('__TOC__', toc_html).replace('__BODY__', body_html)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(page)

    # 生成後自檢
    checks = [
        ['免責聲明', '本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。' in page],
        ['lang-switch.js', '/lang-switch.js' in page],
        ['shared.js', 'shared.js' in page],
        ['canonical', 'https://taiguanglin.info/session_knowledge.html"' in page],
        ['TOC 與 h2 數量一致', page.count('<a class="sk-toc-item"') == n_h2],
        ['十一個章節', n_h2 == 11],
        ['十三張表格', n_tables == 13],
        ['無未處理的 md 標記', page.count('**') == 0 and '\n| ' not in page and '\n- ' not in page],
    ]
    bad = [c[0] for c in checks if not c[1]]
    if bad:
        sys.exit('自檢失敗：%s' % ', '.join(bad))
    print('OK  session_knowledge.html 生成：%d 節、%d 表、%d 字元' % (n_h2, n_tables, len(page)))


if __name__ == '__main__':
    build()
