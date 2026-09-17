# -*- coding: utf-8 -*-
"""生成 wenda2_knowledge_full.html——《坐禪之問答錄2》知識庫全檔頁。
資料來源：tool/wenda2_curation/data/（完整、未壓縮萃取檔）。"""
import json, re, os, html as H

BUILD_DIR = os.path.dirname(os.path.abspath(__file__))
CUR_DIR = os.path.dirname(BUILD_DIR)
out = os.path.join(CUR_DIR, 'data')
REPO = os.path.dirname(os.path.dirname(CUR_DIR))   # repo root（wenda2_curation -> tool -> root）
os.chdir(REPO)

def esc(s):
    return H.escape(s or '', quote=False)

site = json.load(open(f'{out}/site_data.json', encoding='utf-8'))
cur = json.load(open(f'{out}/curation_terms.json', encoding='utf-8'))
curch = json.load(open(f'{out}/curation_chapters.json', encoding='utf-8'))['chapters']
quotes = json.load(open(f'{out}/quotes.json', encoding='utf-8'))
stats = json.load(open(f'{out}/term_stats.json', encoding='utf-8'))
reps = json.load(open(f'{out}/term_reps.json', encoding='utf-8'))

# ---- 名詞出現統計（term -> {ch: count}；發願/淫慾/幻覺重掃語料補齊）----
term_pc = {}
for ch_s, counts in stats['per_ch'].items():
    for t, c in counts.items():
        term_pc.setdefault(t, {})[int(ch_s)] = c
for t in ['淫慾', '幻覺', '發願']:
    if t not in term_pc:
        pc = {}
        for i in range(1, 22):
            d = json.load(open(f'{out}/ch{i:02d}.json', encoding='utf-8'))
            pc[i] = sum(x['a'].count(t) for x in d['qa'] if x['a'])
        term_pc[t] = pc
def t_total(t):
    return sum(term_pc.get(t, {}).values())
GROUPS = [(1, 4), (5, 8), (9, 12), (13, 17), (18, 21)]
def t_groups(t):
    pc = term_pc.get(t, {})
    return [sum(pc.get(i, 0) for i in range(a, b + 1)) for a, b in GROUPS]

# ---- 章名工具 ----
def full_title(c):
    return re.sub(r'^\d+', '', c['title']).strip()
MONTH_MAP = {'一': '01', '二': '02', '三': '03', '四': '04', '五': '05', '六': '06',
             '七': '07', '八': '08', '九': '09', '十': '10', '十一': '11', '十二': '12'}
def short_title(ch, title):
    t = re.sub(r'^\d+', '', title).strip()
    if ch >= 13:
        m = re.match(r'二〇(二[五六])年([一二三四五六七八九十]{1,2})月', t)
        if m:
            yr = '25' if '五' in m.group(1) else '26'
            return f'{yr}.{MONTH_MAP.get(m.group(2), "01")}'
    if ch == 4:
        return '世界起源'
    if ch == 6:
        return '修福功德'
    if ch == 2:
        return '羯磨'
    if ch == 1:
        return '自性意識'
    return t[:4]

def ebook_link(ch, anchor):
    return f'wenda2_ebook/{ch:02d}_trad.html#{anchor}'

# ---- 名詞全檔資料（id -> 豐富欄位）----
tmap = {}
for b in cur['branches']:
    for t in b['terms']:
        tmap[t['id']] = {'id': t['id'], 'label': t['term'], 'branch': b['label'], **t}
id_of_label = {t['label']: k for k, t in tmap.items()}

def src_line(term):
    pc = term_pc.get(term, {})
    total = sum(pc.values())
    top = sorted(pc.items(), key=lambda kv: -kv[1])[:2]
    tops = '、'.join(f'第{i:02d}章（{v:,}）' for i, v in top if v > 0)
    return f'全書出現 {total:,} 次；高頻：{tops}'

def term_card(tid):
    t = tmap[tid]
    q = quotes[tid]
    s = f'《坐禪之問答錄2》第{q["ch"]:02d}章 {short_title(q["ch"], next(c["title"] for c in site["chapters"] if c["ch"] == q["ch"]))}'
    pts = ''.join(f'<li>{esc(p)}</li>' for p in t['points'])
    rels = ''
    if t.get('rel'):
        chips = ' '.join(
            f'<a href="#t-{r}">{esc(tmap[r]["label"])}</a>'
            for r in t['rel'] if r in tmap)
        rels = f'<div class="wk-rel"><span>關聯名詞：</span>{chips}</div>'
    rep = ''
    rp = reps.get(t['label'])
    if rp:
        rep = (f'<a class="wk-rep" href="{ebook_link(rp["ch"], rp["qid"])}"'
               f' target="_blank" rel="noopener noreferrer">統計上最具代表性的回答 ↗</a>')
    return (f'<div class="wk-term" id="t-{tid}">'
            f'<div class="wk-term-head"><h3>{esc(t["label"])}</h3>'
            f'<span class="wk-tag">{esc(t["branch"])}</span>'
            f'<span class="wk-term-count">{esc(src_line(t["label"]))}</span></div>'
            f'<p class="wk-term-desc">{esc(t["desc"])}</p>'
            f'<ul class="wk-term-points">{pts}</ul>'
            f'<blockquote>{esc(q["quote"])}'
            f'<br><a class="wk-qsrc" href="{ebook_link(q["ch"], q["qid"])}" target="_blank" rel="noopener noreferrer">原文 ↗ {esc(s)}</a></blockquote>'
            f'{rels}{rep}</div>')

# 名詞索引（依主幹分組）
index_rows = ''
for b in cur['branches']:
    chips = ' '.join(f'<a class="wk-chip" href="#t-{t["id"]}">{esc(t["term"])}</a>'
                     for t in b['terms'])
    index_rows += f'<div class="wk-index-row"><span>{esc(b["label"])}</span>{chips}</div>'

# 名詞全檔（依主幹分節）
terms_html = ''
for b in cur['branches']:
    terms_html += f'<h3 class="wk-branch-title">{esc(b["label"])}（{len(b["terms"])}）</h3>'
    terms_html += '<div class="wk-terms">' + ''.join(term_card(t['id']) for t in b['terms']) + '</div>'

# ---- 統計總表（131 候選 + 補掃詞，按合計排序）----
ranked = list(stats['rank'])
for t in term_pc:
    if t not in ranked:
        ranked.append(t)
ranked.sort(key=lambda t: -t_total(t))
rows = ''
for t in ranked:
    g = t_groups(t)
    name = t
    lid = id_of_label.get(t)
    if lid:
        name = f'<a href="#t-{lid}">{esc(t)}</a>'
    else:
        name = esc(t)
    rows += (f'<tr><td>{name}</td><td>{t_total(t):,}</td>'
             f'<td>{g[0]:,}</td><td>{g[1]:,}</td><td>{g[2]:,}</td>'
             f'<td>{g[3]:,}</td><td>{g[4]:,}</td></tr>')
stats_table = (
    '<div class="mm-table-wrap"><table class="mm-table">'
    '<thead><tr><th>名詞</th><th>全書合計</th><th>第01–04章<br>義理篇</th>'
    '<th>第05–08章<br>戒修篇</th><th>第09–12章<br>禪定篇</th>'
    '<th>第13–17章<br>月度 25 下</th><th>第18–21章<br>月度 25末–26</th></tr></thead>'
    f'<tbody>{rows}</tbody></table></div>'
    '<p class="mm-lead" style="margin-top:14px">粗體名詞可點入全檔卡（57 個已收錄）；'
    '其餘為候選統計詞，僅計數不展開。計數為程式對繁體語料的逐字統計。</p>')

# ---- 21 章全錄 ----
def sub_block(ch, s):
    q = ''
    if s.get('quote'):
        link = ebook_link(ch, s['qid'])
        src = f'第{ch:02d}章・{s.get("date", "")}'.rstrip('・')
        q = (f'<blockquote>{esc(s["quote"])}'
             f'<br><a class="wk-qsrc" href="{link}" target="_blank" rel="noopener noreferrer">原文 ↗ {esc(src)}</a></blockquote>')
    return (f'<div class="wk-sub" id="ch{ch:02d}-{s["anchor"]}">'
            f'<h3>{esc(s["sub"])}<span class="wk-count">{s["count"]} 個回答</span></h3>{q}</div>')

def chapter_block(c, part):
    ch = c['ch']
    cu = curch[str(ch)]
    core = '<ul class="wk-core">'
    for p in cu['core']:
        link = ebook_link(p['ch'], p['qid'])
        core += (f'<li>{esc(p["point"])}'
                 f' <a href="{link}" target="_blank" rel="noopener noreferrer">原文 ↗</a></li>')
    core += '</ul>'
    body = (f'<div class="wk-chapter" id="ch{ch:02d}">'
            f'<div class="wk-chapter-head">'
            f'<h2><a href="#ch{ch:02d}">第{ch:02d}章 {esc(full_title(c))}</a></h2>'
            f'<span class="wk-chapter-meta">{c["n_qa"]:,} 個回答・{c["date_min"]} – {c["date_max"]}</span></div>'
            f'<p class="wk-lede">{esc(cu["lede"])}</p>{core}')
    if part == 'thematic':
        subs = sorted(c['subs'], key=lambda s: -s['count'])
        body += '<div class="wk-subs">' + ''.join(sub_block(ch, s) for s in subs) + '</div>'
        body += (f'<div class="wk-subs-more"><a href="wenda2_ebook/{ch:02d}_trad.html" target="_blank" rel="noopener noreferrer">'
                 f'第{ch:02d}章完整電子書（{len(c["subs"])} 小節）↗</a></div>')
    else:
        body += '<div class="wk-subs">'
        for h in c.get('highlights', []):
            link = ebook_link(ch, h['qid'])
            body += (f'<div class="wk-sub"><h3>{esc(h["date"])} 的回答<span class="wk-count">月度精選</span></h3>'
                     f'<blockquote>{esc(h["quote"])}'
                     f'<br><a class="wk-qsrc" href="{link}" target="_blank" rel="noopener noreferrer">原文 ↗ 第{ch:02d}章</a></blockquote></div>')
        body += '</div>'
        pills = ''.join(
            f'<a class="wk-chip" href="{ebook_link(ch, s["anchor"])}" target="_blank" rel="noopener noreferrer">{esc(s["sub"])}（{s["count"]}）</a>'
            for s in c.get('sections', []))
        body += f'<div class="wk-month-stats">{pills}</div>'
        body += (f'<div class="wk-subs-more"><a href="wenda2_ebook/{ch:02d}_trad.html" target="_blank" rel="noopener noreferrer">'
                 f'第{ch:02d}章完整電子書 ↗</a></div>')
    body += '</div>'
    return body

blocks1 = ''.join(chapter_block(c, 'thematic') for c in site['chapters'][:12])
blocks2 = ''.join(chapter_block(c, 'monthly') for c in site['chapters'][12:])
quick = ''.join(
    f'<a href="#ch{c["ch"]:02d}"><b>{c["ch"]:02d}</b><span>{esc(short_title(c["ch"], c["title"]))}</span></a>'
    for c in site['chapters'])
total_qa = sum(c['n_qa'] for c in site['chapters'])

NAV = '''    <nav class="navbar" id="navbar">
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
                        <a href="wenda2_knowledge.html" class="nav-dropdown-item">問答錄2 重點知識</a>
                        <a href="wenda2_mindmap.html" class="nav-dropdown-item">問答錄2 名詞心智圖</a>
                        <a href="wenda2_knowledge_full.html" class="nav-dropdown-item active" aria-current="page">問答錄2 知識庫全檔</a>
                    </div>
                </div>
                <a href="index.html#downloads" class="nav-link nav-cta" data-download-trigger>下載資料</a>
            </div>
            <button class="hamburger" id="hamburger" aria-label="開啟選單" aria-expanded="false">
                <span></span><span></span><span></span>
            </button>
        </div>
    </nav>
    <div class="site-menu-veil" id="site-menu-veil"></div>'''

FOOTER = '''    <footer class="footer">
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
    </footer>'''

page = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>坐禪之問答錄2 知識庫全檔｜完整名詞檔與章節引句索引｜TaiGuangLin 禪師</title>
    <meta name="description" content="《坐禪之問答錄2》知識萃取的完整參考檔：57 個高頻名詞全檔（釋義、要點、逐字引句、出現次數）、131 個名詞統計總表、21 章逐章導讀與 437 個小節的逐字引句，全部可連回電子書原文。">
    <meta name="keywords" content="坐禪之問答錄2,知識庫,名詞解釋,自性,阿賴耶識,羯磨,功德,禪定,唪佛,極樂世界,TaiGuangLin">
    <meta name="author" content="TaiGuangLin">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="坐禪之問答錄2 知識庫全檔｜TaiGuangLin 禪師">
    <meta property="og:description" content="57 個名詞全檔、131 個名詞統計、21 章全部小節引句的完整參考頁">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://taiguanglin.info/wenda2_knowledge_full.html">
    <meta property="og:image" content="https://taiguanglin.info/images/taiguanglin.png">
    <link rel="canonical" href="https://taiguanglin.info/wenda2_knowledge_full.html">
    <link rel="icon" type="image/x-icon" href="images/favicon.ico">
    <link rel="shortcut icon" type="image/x-icon" href="images/favicon.ico">
    <link rel="stylesheet" href="style.css">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500;600;700;900&family=Noto+Sans+TC:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<script src="/lang-switch.js" defer></script>
</head>
<body>
''' + NAV + '''

    <!-- Hero 區塊 -->
    <section class="page-hero">
        <div class="container">
            <nav class="crumbs" aria-label="位置">
                <a href="index.html">首頁</a><span class="crumbs-sep">/</span><a href="wenda2.html">坐禪之問答錄2</a><span class="crumbs-sep">/</span>
                <span aria-current="page">知識庫全檔</span>
            </nav>
            <span class="kicker">WENDA2 KNOWLEDGE BASE</span>
            <h1 class="display">坐禪之問答錄2 知識庫全檔</h1>
            <p class="lede">本站從《坐禪之問答錄2》萃取的完整知識檔，一次全部列出：57 個高頻名詞的釋義、要點與逐字引句；131 個名詞的全書出現次數統計；21 章逐章導讀與 437 個小節的代表引句。每一筆資料都連回電子書原文，方便對照 Tai 師父的完整回答。</p>
            <div class="wk-hero-note">
                <span class="wk-chip"><b>57</b> 個名詞全檔</span>
                <span class="wk-chip"><b>131</b> 個名詞統計</span>
                <span class="wk-chip"><b>437</b> 個小節全錄</span>
                <span class="wk-chip"><b>36</b> 則月度精選</span>
                <span class="wk-chip"><b>''' + f'{total_qa:,}' + '''</b> 個回答</span>
            </div>
        </div>
    </section>
    <section class="section" style="padding-top: var(--spacing-lg); padding-bottom: 0;">
        <div class="container">
            <div class="note-ai" style="margin-bottom: 8px;">
                <span>本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。</span>
            </div>
            <p class="mm-lead" style="margin-top: 18px">這是「全錄版」：精選版（<a href="wenda2_knowledge.html">重點知識</a>）每章只挑代表小節，本頁把 437 個小節全部列出。選材與導讀由 AI 整理，引句一律逐字摘錄（省略以……標示）——遇到任何疑問，請點引句後方的「原文 ↗」看完整上下文。</p>
        </div>
    </section>

    <!-- 快速導航 -->
    <section class="section bg-light" style="padding-top: 34px; padding-bottom: 26px;">
        <div class="container">
            <h2 class="section-title mm-section-title"><span class="mm-section-icon" aria-hidden="true"><svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="4" width="14" height="14" rx="3" stroke="currentColor" stroke-width="2"/><rect x="22" y="4" width="14" height="14" rx="3" stroke="currentColor" stroke-width="2" opacity=".45"/><rect x="4" y="22" width="14" height="14" rx="3" stroke="currentColor" stroke-width="2" opacity=".45"/><rect x="22" y="22" width="14" height="14" rx="3" stroke="currentColor" stroke-width="2" opacity=".75"/></svg></span>全檔快速導航</h2>
            <div class="wk-quick">''' + quick + '''</div>
            <div style="margin-top: 20px">''' + index_rows + '''</div>
        </div>
    </section>

    <!-- Part 1 名詞全檔 -->
    <section class="section">
        <div class="container">
            <div class="wk-part-title"><h2 id="part1">一・五十七名詞全檔</h2></div>
            <p class="mm-lead">依 11 條主幹分節。每張卡：釋義、依回答整理的書中要點、逐字引句與出處、全書出現次數，以及可點的關聯名詞。</p>
            ''' + terms_html + '''
        </div>
    </section>

    <!-- Part 2 統計總表 -->
    <section class="section bg-light">
        <div class="container">
            <div class="wk-part-title"><h2 id="part2">二・名詞出現次數總表</h2></div>
            <p class="mm-lead">程式對全書 ''' + f'{total_qa:,}' + ''' 個回答逐字統計的完整列表，按全書合計次數排序。</p>
            ''' + stats_table + '''
        </div>
    </section>

    <!-- Part 3 章節全錄 -->
    <section class="section">
        <div class="container">
            <div class="wk-part-title"><h2 id="part3">三・二十一章全錄</h2></div>
            <p class="mm-lead">第 01–12 章為主題篇：每章導讀、要點與全部小節（依回答數排序，每小節附逐字引句）；第 13–21 章為月度篇：導讀、要點、月度精選與日期小節連結。</p>
            ''' + blocks1 + '''
            <div class="wk-part-title"><h2 id="part3m">月度問答篇（第 13–21 章，2025.06 – 2026.03）</h2></div>
            ''' + blocks2 + '''
        </div>
    </section>

    <!-- Part 4 資料怎麼來的 -->
    <section class="section bg-light">
        <div class="container">
            <div class="wk-part-title"><h2 id="part4">四・本檔資料怎麼來的</h2></div>
            <div class="wk-method">
                <h3>萃取</h3>
                <p>以程式解析《坐禪之問答錄2》電子書全部 21 章，取出 ''' + f'{total_qa:,}' + ''' 個有回答的問答：每一筆含提問、回答全文、所屬小節、日期與電子書原文錨點。</p>
                <h3>選材</h3>
                <p>名詞：先對全書逐字統計得 131 個候選，再從中整理出 57 個高頻名詞（11 條主幹）。章節導讀與要點：由 AI 依各章代表回答撰寫。引句：一律逐字摘錄，在句邊界切割，句首省略與句尾截斷以「……」標示，不做任何改寫。</p>
                <h3>統計</h3>
                <p>名詞出現次數為程式對繁體語料的逐字計數；「淫慾」「發願」「幻覺」等詞以繁體寫法統計（簡體寫法另計）。</p>
                <h3>保存與復用</h3>
                <p>本頁（以及「重點知識」「名詞心智圖」兩頁）的全部資料檔與生成腳本，完整保存在本站原始碼庫：<a href="https://github.com/taiguanglin/taiguanglin.github.io/tree/main/tool/wenda2_curation" target="_blank" rel="noopener noreferrer">tool/wenda2_curation（GitHub）↗</a>，未來可據此重播、更新或重建這些頁面。</p>
            </div>
            <div class="mm-more-grid">
                <a class="mm-more-card" href="wenda2_knowledge.html">
                    <strong>坐禪之問答錄2 重點知識</strong>
                    <span>每章只挑代表小節的精選版，讀起來快。</span>
                </a>
                <a class="mm-more-card" href="wenda2_mindmap.html">
                    <strong>問答錄2 名詞分析心智圖</strong>
                    <span>57 個名詞的互動關聯圖，點名詞看引句與統計。</span>
                </a>
                <a class="mm-more-card" href="wenda2.html">
                    <strong>問答錄2 主題目錄</strong>
                    <span>前 12 章主題選讀，每一章的介紹與代表問答。</span>
                </a>
                <a class="mm-more-card" href="wenda2_ebook/index_trad.html" target="_blank" rel="noopener noreferrer">
                    <strong>問答錄2 完整電子書</strong>
                    <span>9,231 個回答全文檢索；本頁所有引文都連回這裡的原文位置。</span>
                </a>
            </div>
        </div>
    </section>

''' + FOOTER + '''

    <script src="shared.js" defer></script>
</body>
</html>
'''

with open('wenda2_knowledge_full.html', 'w', encoding='utf-8') as f:
    f.write(page)
print('wenda2_knowledge_full.html written:', len(page), 'chars')
print('stats rows:', len(ranked), '| term cards:', len(tmap), '| subs:', sum(len(c.get('subs', [])) for c in site['chapters'][:12]))
