# -*- coding: utf-8 -*-
import json, re, os, html as H

# 以腳本位置推算路徑：build/ -> wenda2_curation/ -> repo root
BUILD_DIR = os.path.dirname(os.path.abspath(__file__))
CUR_DIR = os.path.dirname(BUILD_DIR)
out = os.path.join(CUR_DIR, 'data')          # data/ (ch01..21.json, curation, stats)
REPO = os.path.dirname(CUR_DIR)              # = tool/
REPO = os.path.dirname(REPO)                  # repo root
os.chdir(REPO)

site = json.load(open(f'{out}/site_data.json', encoding='utf-8'))
cur = json.load(open(f'{out}/curation_chapters.json', encoding='utf-8'))['chapters']

def esc(s):
    return H.escape(s or '', quote=False)

MONTH_MAP = {'一': '01', '二': '02', '三': '03', '四': '04', '五': '05', '六': '06',
             '七': '07', '八': '08', '九': '09', '十': '10', '十一': '11', '十二': '12'}
def short_title(ch, title):
    t = re.sub(r'^\d+', '', title).strip()
    if ch >= 13:
        m = re.match(r'二〇(二[五六])年([一二三四五六七八九十]{1,2})月', t)
        if m:
            yr = '25' if '五' in m.group(1) else '26'
            mm = MONTH_MAP.get(m.group(2), '01')
            return f'{yr}.{mm}'
        return t
    if ch == 4:
        return '世界起源'
    if ch == 6:
        return '修福功德'
    if ch == 2:
        return '羯磨'
    if ch == 1:
        return '自性意識'
    return t[:4]

def date_range(c):
    a, b = c['date_min'], c['date_max']
    if a == b:
        return a
    return f'{a} – {b}'

def ebook_link(ch, anchor):
    return f'wenda2_ebook/{ch:02d}_trad.html#{anchor}'

def sub_block(ch, s):
    q = ''
    if s.get('quote'):
        link = ebook_link(ch, s['qid'])
        src = f'第{ch:02d}章・{s.get("date", "")}'.rstrip('・')
        q = (f'<blockquote>{esc(s["quote"])}'
             f'<br><a class="wk-qsrc" href="{link}" target="_blank" rel="noopener noreferrer">原文 ↗ {src}</a></blockquote>')
    return (f'<div class="wk-sub" id="ch{ch:02d}-{s["anchor"]}">'
            f'<h3>{esc(s["sub"])}<span class="wk-count">{s["count"]} 個回答</span></h3>{q}</div>')

def chapter_block(c, part):
    ch = c['ch']
    cu = cur[str(ch)]
    head = (
        f'<div class="wk-chapter" id="ch{ch:02d}">'
        f'<div class="wk-chapter-head">'
        f'<h2><a href="#ch{ch:02d}">第{ch:02d}章 {esc(short_title(ch, c["title"]) if ch >= 13 else re.sub(r"^\d+", "", c["title"]).strip())}</a></h2>'
        f'<span class="wk-chapter-meta">{c["n_qa"]:,} 個回答・{date_range(c)}</span>'
        f'</div>'
        f'<p class="wk-lede">{esc(cu["lede"])}</p>'
    )
    core = '<ul class="wk-core">'
    for p in cu['core']:
        link = ebook_link(p['ch'], p['qid'])
        core += (f'<li>{esc(p["point"])}'
                 f' <a href="{link}" target="_blank" rel="noopener noreferrer">原文 ↗</a></li>')
    core += '</ul>'
    body = head + core
    if part == 'thematic':
        subs = sorted(c['subs'], key=lambda s: -s['count'])
        detailed = [s for s in subs if s.get('quote')][:7]
        shown = {s['sub'] for s in detailed}
        rest = [s for s in subs if s['sub'] not in shown]
        if detailed:
            body += '<div class="wk-subs">' + ''.join(sub_block(ch, s) for s in detailed) + '</div>'
        if rest:
            pills = ''.join(
                f'<a class="wk-chip" href="{ebook_link(ch, s["anchor"])}" target="_blank" rel="noopener noreferrer">{esc(s["sub"])}（{s["count"]}）</a>'
                for s in rest[:20])
            more = ''
            if len(rest) > 20:
                more = (f'<a class="wk-chip" href="{ebook_link(ch, c["ch"] and 1)}" target="_blank" rel="noopener noreferrer">'
                        f'…共 {len(rest)} 小節，見電子書 ↗</a>')
                more = (f'<a class="wk-chip" href="wenda2_ebook/{ch:02d}_trad.html" target="_blank" rel="noopener noreferrer">'
                        f'…共 {len(rest)} 小節，見電子書本章 ↗</a>')
            body += (f'<div class="wk-month-stats" style="margin-top:18px">{pills}{more}</div>'
                     f'<div class="wk-subs-more"><a href="wenda2_ebook/{ch:02d}_trad.html" target="_blank" rel="noopener noreferrer">第{ch:02d}章完整電子書 ↗</a></div>')
        else:
            body += (f'<div class="wk-subs-more"><a href="wenda2_ebook/{ch:02d}_trad.html" target="_blank" rel="noopener noreferrer">'
                     f'第{ch:02d}章完整電子書（{len(c["subs"])} 小節）↗</a></div>')
    else:
        hqs = [h for h in c.get('highlights', []) if h.get('quote')][:3]
        if hqs:
            body += '<div class="wk-subs">'
            for h in hqs:
                link = ebook_link(ch, h['qid'])
                body += (f'<div class="wk-sub"><h3>{esc(h["date"])} 的回答<span class="wk-count">月度精選</span></h3>'
                         f'<blockquote>{esc(h["quote"])}'
                         f'<br><a class="wk-qsrc" href="{link}" target="_blank" rel="noopener noreferrer">原文 ↗ 第{ch:02d}章</a></blockquote></div>')
            body += '</div>'
        pills = ''.join(
            f'<a class="wk-chip" href="{ebook_link(ch, s["anchor"])}" target="_blank" rel="noopener noreferrer">{esc(s["sub"])}（{s["count"]}）</a>'
            for s in c.get('sections', [])[:14])
        if pills:
            body += f'<div class="wk-month-stats">{pills}</div>'
        body += (f'<div class="wk-subs-more"><a href="wenda2_ebook/{ch:02d}_trad.html" target="_blank" rel="noopener noreferrer">'
                 f'第{ch:02d}章完整電子書 ↗</a></div>')
    body += '</div>'
    return body

NAV_PLACEHOLDER = '__NAV_GOES_HERE__'

blocks1 = ''.join(chapter_block(c, 'thematic') for c in site['chapters'][:12])
blocks2 = ''.join(chapter_block(c, 'monthly') for c in site['chapters'][12:])

quick = ''.join(
    f'<a href="#ch{c["ch"]:02d}"><b>{c["ch"]:02d}</b><span>{esc(short_title(c["ch"], c["title"]))}</span></a>'
    for c in site['chapters'])

total_qa = sum(c['n_qa'] for c in site['chapters'])
d1 = site['chapters'][0]['date_min']
d2 = site['chapters'][-1]['date_max']
thematic_subs = sum(len(c.get('subs', [])) for c in site['chapters'][:12])

page = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>坐禪之問答錄2 重點知識｜Tai 師父回答重點總覽｜TaiGuangLin 禪師</title>
    <meta name="description" content="《坐禪之問答錄2》21 章、9,231 個 Tai 師父回答的重點整理：每章導讀、書中要點、逐字摘錄的引句與電子書原文連結。自性與意識、羯磨、發心、世界起源、戒行、修福積功德、唪誦經咒、腹式呼吸、磕大頭、雙盤、禪定、佛門修行，加 2025.06–2026.03 月度問答精選。">
    <meta name="keywords" content="坐禪之問答錄2,問答錄2,Tai師父回答,重點整理,自性,羯磨,發心,戒行,功德,禪定,打坐,TaiGuangLin">
    <meta name="author" content="TaiGuangLin">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="坐禪之問答錄2 重點知識｜TaiGuangLin 禪師">
    <meta property="og:description" content="按 21 章整理《坐禪之問答錄2》9,231 個 Tai 師父回答的重點，附逐字引句與原文連結">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://taiguanglin.info/wenda2_knowledge.html">
    <meta property="og:image" content="https://taiguanglin.info/images/taiguanglin.png">
    <link rel="canonical" href="https://taiguanglin.info/wenda2_knowledge.html">
    <link rel="icon" type="image/x-icon" href="images/favicon.ico">
    <link rel="shortcut icon" type="image/x-icon" href="images/favicon.ico">
    <link rel="stylesheet" href="style.css">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500;600;700;900&family=Noto+Sans+TC:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<script src="/lang-switch.js" defer></script>
</head>
<body>
{NAV_PLACEHOLDER}

    <!-- Hero 區塊 -->
    <section class="page-hero">
        <div class="container">
            <nav class="crumbs" aria-label="位置">
                <a href="index.html">首頁</a><span class="crumbs-sep">/</span><a href="wenda2.html">坐禪之問答錄2</a><span class="crumbs-sep">/</span>
                <span aria-current="page">重點知識</span>
            </nav>
            <span class="kicker">WENDA2 KEY KNOWLEDGE</span>
            <h1 class="display">坐禪之問答錄2 重點知識</h1>
            <p class="lede">《坐禪之問答錄2》{total_qa:,} 個 Tai 師父回答的重點整理：每一章的導讀、書中要點、逐字摘錄的代表引句，全部連結到電子書原文。第 01–12 章按主題彙編，第 13–21 章按月份收錄。</p>
            <div class="wk-hero-note">
                <span class="wk-chip"><b>21</b> 章</span>
                <span class="wk-chip"><b>{total_qa:,}</b> 個回答</span>
                <span class="wk-chip"><b>{d1} – {d2}</b></span>
                <span class="wk-chip"><b>{thematic_subs}</b> 個主題小節</span>
                <a class="wk-chip" href="wenda2_mindmap.html">名詞分析心智圖 ↗</a>
                <a class="wk-chip" href="wenda2_knowledge_full.html">知識庫全檔 ↗</a>
            </div>
        </div>
    </section>
    <section class="section" style="padding-top: var(--spacing-lg); padding-bottom: 0;">
        <div class="container">
            <div class="note-ai" style="margin-bottom: 8px;">
                <span>本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。</span>
            </div>
            <p class="mm-lead" style="margin-top: 18px">選材方式：每章由 AI 從小節標題與全部回答中，挑出出現次數最多的小節與最具代表性的回答，逐字摘錄（省略以……標示），並附上 AI 整理的章導讀與要點。它不能取代原文——把每一句引文點回電子書對照上下文，才是正確用法。</p>
        </div>
    </section>

    <!-- 快速導航 -->
    <section class="section bg-light" style="padding-top: 34px; padding-bottom: 26px;">
        <div class="container">
            <h2 class="section-title mm-section-title"><span class="mm-section-icon" aria-hidden="true"><svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="4" width="14" height="14" rx="3" stroke="currentColor" stroke-width="2"/><rect x="22" y="4" width="14" height="14" rx="3" stroke="currentColor" stroke-width="2" opacity=".45"/><rect x="4" y="22" width="14" height="14" rx="3" stroke="currentColor" stroke-width="2" opacity=".45"/><rect x="22" y="22" width="14" height="14" rx="3" stroke="currentColor" stroke-width="2" opacity=".75"/></svg></span>全書快速導航</h2>
            <div class="wk-quick">{quick}</div>
        </div>
    </section>

    <section class="section">
        <div class="container">
            <div class="wk-part-title"><h2 id="part1">第一部分・十二主題篇（2024.02 – 2025.05）</h2></div>
            <p class="mm-lead">前 12 章把 2024 年 2 月到 2025 年 5 月的問答按主題重新編排：每一章是一個主題，每一小節是一組相關問題。下面每章列出出現次數最多的代表性小節與 Tai 師父回答的逐字摘句。</p>
            {blocks1}
            <div class="wk-part-title"><h2 id="part2">第二部分・月度問答篇（2025.06 – 2026.03）</h2></div>
            <p class="mm-lead">第 13 章起，問答按月份原樣收錄：貼吧與公眾號的問題照日期排列。下面每章挑出該月最具內容的三個回答，並附該月的日期小節連結。</p>
            {blocks2}
        </div>
    </section>

    <!-- 延伸 -->
    <section class="section bg-light">
        <div class="container">
            <h2 class="section-title mm-section-title"><span class="mm-section-icon" aria-hidden="true"><svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 6l3.5 7.5L31 14.5l-5.5 5.5L26.8 28 20 24.3 13.2 28l1.3-8L9 14.5l7.5-1z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" fill="none"/><circle cx="20" cy="20" r="15" stroke="currentColor" stroke-width="1.2" opacity=".4" fill="none"/></svg></span>繼續讀</h2>
            <div class="mm-more-grid">
                <a class="mm-more-card" href="wenda2_mindmap.html">
                    <strong>問答錄2 名詞分析心智圖</strong>
                    <span>57 個高頻名詞的互動關聯圖：定義、要點、逐字引文與出現次數統計。</span>
                </a>
                <a class="mm-more-card" href="wenda2.html">
                    <strong>問答錄2 主題目錄</strong>
                    <span>前 12 章主題選讀，每一章的介紹與代表問答。</span>
                </a>
                <a class="mm-more-card" href="wenda2_ebook/index_trad.html" target="_blank" rel="noopener noreferrer">
                    <strong>問答錄2 完整電子書</strong>
                    <span>9,231 個回答全文檢索；本頁所有引文都連回這裡的原文位置。</span>
                </a>
                <a class="mm-more-card" href="wenda2_knowledge_full.html">
                    <strong>問答錄2 知識庫全檔</strong>
                    <span>名詞全檔、出現次數統計總表與 21 章全部小節引句的完整參考頁。</span>
                </a>
                <a class="mm-more-card" href="mindmap.html">
                    <strong>坐禪與講經名詞心智圖（九本著作）</strong>
                    <span>《坐禪1》《坐禪2》與六部講經的全套名詞結構總圖。</span>
                </a>
            </div>
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
                        <li><a href="mindmap.html">坐禪與講經名詞心智圖</a></li>
                        <li><a href="wenda2_knowledge.html">問答錄2 重點知識</a></li>
                        <li><a href="wenda2_mindmap.html">問答錄2 名詞心智圖</a></li>
                        <li><a href="wenda2_knowledge_full.html">問答錄2 知識庫全檔</a></li>
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

# nav with knowledge active
nav = '''    <nav class="navbar" id="navbar">
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
<div class="nav-dropdown" id="nav-dropdown">
                    <a href="#" class="nav-link nav-dropdown-toggle" id="dropdown-toggle">圖解 ▾</a>
                    <div class="nav-dropdown-menu">
                        <a href="infographic.html" class="nav-dropdown-item">名詞圖解</a>
                        <a href="mindmap.html" class="nav-dropdown-item">坐禪與講經名詞心智圖</a>
                        <a href="books_knowledge.html" class="nav-dropdown-item">坐禪與講經重點知識</a>
<a href="books_knowledge_full.html" class="nav-dropdown-item">坐禪與講經知識庫全檔</a>
                        <a href="wenda2_knowledge.html" class="nav-dropdown-item active" aria-current="page">問答錄2 重點知識</a>
                        <a href="wenda2_mindmap.html" class="nav-dropdown-item">問答錄2 名詞心智圖</a>
                        <a href="wenda2_knowledge_full.html" class="nav-dropdown-item">問答錄2 知識庫全檔</a>
                    </div>
                </div>
                <a href="stories.html" class="nav-link">實修故事</a>
                
                <a href="index.html#downloads" class="nav-link nav-cta" data-download-trigger>下載資料</a>
            </div>
            <button class="hamburger" id="hamburger" aria-label="開啟選單" aria-expanded="false">
                <span></span><span></span><span></span>
            </button>
        </div>
    </nav>
    <div class="site-menu-veil" id="site-menu-veil"></div>'''
page = page.replace('__NAV_GOES_HERE__', nav)

with open('wenda2_knowledge.html', 'w', encoding='utf-8') as f:
    f.write(page)
print('wenda2_knowledge.html written:', len(page), 'chars')
