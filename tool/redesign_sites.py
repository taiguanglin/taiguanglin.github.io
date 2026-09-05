#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Redesign remaining hand pages: wenda2.html, infographic.html, mindmap.html.
Transforms in place: replaces head <style> chrome, canonical nav/footer markup,
removes Font Awesome, retunes heroes to the pink page-hero style.
Idempotent: skips pages already containing `logo-mark` in the nav.
"""
import io
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()

def write(p, s):
    with io.open(p, 'w', encoding='utf-8') as f:
        f.write(s)

NAV = '''    <header class="navbar" id="navbar">
      <div class="nav-container">
        <a href="{p}index.html" class="nav-logo">
          <span class="logo-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4c2.2 2.2 3.2 4.6 3.2 6.8-2.1 1.3-4.3 1.3-6.4 0C8.8 8.6 9.8 6.2 12 4z"/><path d="M4.5 12.5c1.8-.8 3.8-.7 5.2.6M19.5 12.5c-1.8-.8-3.8-.7-5.2.6"/><path d="M5 16c1.8 1.6 4.2 2.4 7 2.4s5.2-.8 7-2.4"/></svg>
          </span>
          <span class="logo-text"><span class="logo-name">TaiGuangLin</span><span class="logo-sub">次世代終極佛法</span></span>
        </a>
        <nav class="nav-menu" id="nav-menu" aria-label="主選單">{links}
        </nav>
        <button class="hamburger" id="hamburger" aria-label="開啟選單" aria-expanded="false"><span></span><span></span><span></span></button>
      </div>
    </header>
    <div id="site-menu-veil" aria-hidden="true"></div>
'''

FOOTER = '''    <footer class="footer">
      <div class="container">
        <div class="footer-top">
          <div class="footer-brand">
            <div class="logo-name">TaiGuangLin</div>
            <span class="logo-sub">次世代終極佛法</span>
            <p>以現代淺白的語言，講解禪定實修與佛法深義。<br>願此妙法，利益一切尋求真理之人。</p>
          </div>
          <div class="footer-col">
            <h4>著作</h4>
            <ul>
              <li><a href="{p}index.html#books">全部著作</a></li>
              <li><a href="{p}wenda2.html">問答錄 2（十二主題）</a></li>
            </ul>
          </div>
          <div class="footer-col">
            <h4>資源</h4>
            <ul>
              <li><a href="{p}stories.html">實修故事</a></li>
              <li><a href="{p}infographic.html">名詞圖解</a></li>
              <li><a href="{p}mindmap.html">名詞心智圖</a></li>
            </ul>
          </div>
          <div class="footer-col">
            <h4>下載</h4>
            <ul><li><a href="{p}index.html#downloads">電子書與語音</a></li></ul>
          </div>
        </div>
        <div class="footer-bottom">
          <p>歡迎轉載流通，標明出處即可</p>
          <p>願一切眾生離苦得樂，早證菩提</p>
        </div>
      </div>
    </footer>
'''

def nav_for(page, prefix=''):
    links = [
        ('index.html', '首頁', page == 'index'),
        ('wenda2.html', '問答錄 2', page == 'wenda2'),
        ('stories.html', '實修故事', page == 'stories'),
        ('infographic.html', '名詞圖解', page == 'infographic'),
        ('mindmap.html', '心智圖', page == 'mindmap'),
    ]
    out = []
    for href, label, active in links:
        cls = 'nav-link' + (' active' if active else '')
        out.append(f'          <a class="{cls}" href="{prefix}{href}">{label}</a>')
    out.append(f'          <a class="nav-link nav-cta" href="{prefix}index.html#downloads">下載</a>')
    return NAV.format(p=prefix, links='\n'.join(out))


def redecorate(page, extra_body=None):
    """page: basename without .html; extra_body: fn(body)->body"""
    path = os.path.join(ROOT, page + '.html')
    html = read(path)
    if 'logo-mark' in html:
        print(page, 'already chrome-redesigned, skipping')
        return

    # --- rebuild <head>: keep meta, drop legacy <style> blocks and FA ---
    head_end = html.index('</head>')
    head = html[:head_end]
    # remove every <style>…</style> in head (they duplicate style.css)
    head = re.sub(r'\s*<style>.*?</style>', '', head, flags=re.S)
    # remove Font Awesome stylesheet link
    head = re.sub(r'\s*<link rel="stylesheet" href="https://cdnjs\.cloudflare\.com/ajax/libs/font-awesome/[^>]+>', '', head)
    # ensure font weights include 900 for serif
    head = head.replace('Noto+Serif+TC:wght@400;500;600;700&', 'Noto+Serif+TC:wght@400;500;600;700;900&')

    # --- body: replace nav + footer chrome, strip FA icons, swap script ---
    body_start = html.index('<body>') + len('<body>')
    footer_start = html.rindex('<!-- 頁尾 -->')
    footer_end = html.rindex('</footer>') + len('</footer>')
    body_mid = html[body_start:footer_start]
    # remove old nav block (everything from start up to just after </nav>)
    nav_end = body_mid.index('</nav>') + len('</nav>')
    body_mid = body_mid[nav_end:]
    # strip FA icons
    body_mid = re.sub(r'<i class="fa[sb] [^"]*"></i>', '', body_mid)
    # run page-specific fixes
    if extra_body:
        body_mid = extra_body(body_mid)

    html = head + '</head>\n<body>\n' + nav_for(page) + body_mid + FOOTER.format(p='') + html[footer_end:]
    # swap script.js → shared.js where present
    html = html.replace('<script src="script.js"></script>', '<script src="shared.js" defer></script>')
    write(path, html)
    print(page, 'done')


# ---------------- page-specific fixes ----------------
def fix_wenda2(body):
    # hero → page-hero
    body = body.replace('<section class="wenda-hero">', '<section class="page-hero">')
    body = body.replace('<h1 class="hero-title">坐禪之問答錄2 主題目錄</h1>',
                        '<span class="kicker">Q&amp;A RECORD · INDEX</span>\n            <h1 class="display">問答錄 2 目錄</h1>')
    body = body.replace('<p class="hero-subtitle">依主題分成 12 章 • 截止2025年3月15日答疑合集</p>',
                        '<p class="lede">七十餘則共分 12 大主題的修行問答記錄，涵蓋自性、業、發心、禪定等核心義理。</p>')
    body = re.sub(r'<div class="wenda-stats">.*?</div>\s*</div>', '''<div class="wd-stats reveal">
                    <div class="wd-stat-card"><strong>12</strong><span>主題章節</span></div>
                    <div class="wd-stat-card"><strong>70+</strong><span>問答集錦</span></div>
                    <div class="wd-stat-card"><strong>2025.03</strong><span>收錄時間</span></div>
                </div>''', body, flags=re.S)
    # chapter grid → wd-*
    mapping = [
        ('chapter-grid', 'wd-grid'),
        ('chapter-card', 'wd-chapter-card card reveal'),
        ('chapter-number', 'wd-chapter-num'),
        ('chapter-title', 'wd-chapter-title'),
        ('chapter-description', 'wd-chapter-desc'),
        ('chapter-topics', 'wd-chips'),
        ('topic-tag', 'wd-chip'),
        ('chapter-link', 'wd-go'),
    ]
    for old, new in mapping:
        body = body.replace('class="%s"' % old, 'class="%s"' % new)
    # back-to-home → crumbs
    body = re.sub(r'<div class="back-to-home">.*?</div>', '''<nav class="crumbs" aria-label="位置">
                <a href="index.html">首頁</a><span class="crumbs-sep">/</span>
                <span aria-current="page">問答錄 2</span>
            </nav>''', body, flags=re.S)
    # arrow icons
    body = body.replace('開始閱讀 ', '開始閱讀').replace('  <i></i>', ' <i>→</i>')
    return body


def fix_infographic(body):
    body = body.replace(
        '<section class="hero" style="height: 50vh; background: var(--pink-gradient); padding-top: 80px;">',
        '<section class="page-hero">')
    body = body.replace('<h1 class="hero-title animate-fade-in">佛法名詞圖解</h1>',
                        '<span class="kicker">CONCEPT ILLUSTRATIONS</span>\n            <h1 class="display">名詞圖解</h1>')
    body = body.replace('<p class="hero-subtitle animate-fade-in delay-1">次世代終極佛法核心概念的視覺化解釋</p>',
                        '<p class="lede">以圖像呈現《坐禪》系列與《問答錄 2》中的關鍵概念——妄想、分別、執著、戒行、禪定與因果。</p>')
    body = re.sub(r'<div class="hero-background"></div>\s*', '', body)
    body = re.sub(r'<div class="back-to-home">.*?</div>', '', body, flags=re.S)
    # disclaimer and category nav: restyle lightly
    body = body.replace('class="infographic-disclaimer"', 'class="chip" style="margin-bottom: 26px;"')
    body = body.replace('class="infographic-category-nav"', 'class="pill-nav-wrap"')
    body = body.replace('class="category-nav-grid"', 'class="pill-nav"')
    body = body.replace('class="category-nav-item"', 'class="chip"')
    body = body.replace('class="infographic-overlay"', 'class="is-overlay"')
    return body


def fix_mindmap(body):
    body = body.replace('<section class="hero mm-hero" style="height: 50vh; background: var(--pink-gradient); padding-top: 80px;">',
                        '<section class="page-hero">')
    body = body.replace('<h1 class="hero-title animate-fade-in">名詞關聯心智圖</h1>',
                        '<span class="kicker">CONCEPT MIND MAP</span>\n            <h1 class="display">名詞心智圖</h1>')
    body = body.replace('<p class="hero-subtitle animate-fade-in delay-1">一張圖看懂五冊著作的關鍵名詞，以及它們彼此的關聯</p>',
                        '<p class="lede">把《坐禪》系列與《講經》五冊的核心名詞串成一張可互動的關聯圖。</p>')
    body = re.sub(r'<div class="hero-background"></div>\s*', '', body)
    body = re.sub(r'<div class="back-to-home">.*?</div>', '', body, flags=re.S)
    # remove mm-hero-icon block (FA-based)
    body = re.sub(r'<div class="mm-hero-icon[^>]*>.*?</div>\s*</div>', '', body, flags=re.S)
    body = body.replace('class="mm-notice-icon"', 'class="chip" style="display:inline-flex; margin-right:10px;"')
    body = body.replace('class="mm-notice"', 'class="card reveal" style="padding: var(--spacing-md); margin-bottom: var(--spacing-lg);"')
    return body


if __name__ == '__main__':
    redecorate('wenda2', fix_wenda2)
    redecorate('infographic', fix_infographic)
    redecorate('mindmap', fix_mindmap)
