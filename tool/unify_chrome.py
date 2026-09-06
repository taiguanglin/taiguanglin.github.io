#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Make non-index pages' navbar + footer identical in style/layout to index.html.

Applies the canonical chrome (nav class="navbar" with the same menu incl.
「圖解」dropdown + <div class="hamburger">, and the same 4-column footer)
to wenda2.html, stories.html, infographic.html, mindmap.html and
wenda2/chapter-01..12.html. Relative links get a `../` prefix for chapters.
Idempotent: skips pages already carrying the canonical marker.
"""
import io
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

MARKER = 'data-chrome="index"'

def nav(prefix):
    return f'''    <nav class="navbar" id="navbar" {MARKER}>
        <div class="nav-container">
            <div class="nav-logo">
                <span class="logo-name">TaiGuangLin</span>
                <span class="logo-sub">次世代終極佛法</span>
            </div>
            <div class="nav-menu" id="nav-menu">
                <a href="{prefix}index.html#home" class="nav-link">首頁</a>
                <a href="{prefix}index.html#about" class="nav-link">禪師</a>
                <a href="{prefix}index.html#start" class="nav-link">入門路徑</a>
                <a href="{prefix}index.html#books" class="nav-link">著作</a>
                <a href="{prefix}wenda2.html" class="nav-link">問答錄2</a>
                <a href="{prefix}stories.html" class="nav-link">故事</a>
                <div class="nav-dropdown" id="nav-dropdown">
                    <a href="#" class="nav-link nav-dropdown-toggle" id="dropdown-toggle">圖解 ▾</a>
                    <div class="nav-dropdown-menu">
                        <a href="{prefix}infographic.html" class="nav-dropdown-item">名詞圖解</a>
                        <a href="{prefix}mindmap.html" class="nav-dropdown-item">名詞關聯心智圖</a>
                    </div>
                </div>
                <a href="{prefix}index.html#downloads" class="nav-link">下載</a>
            </div>
            <div class="hamburger" id="hamburger">
                <span></span><span></span><span></span>
            </div>
        </div>
    </nav>
'''

def footer(prefix):
    return f'''    <footer class="footer">
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
                        <li><a href="{prefix}index.html#books">全部著作</a></li>
                        <li><a href="{prefix}ebook/index_trad.html" target="_blank" rel="noopener noreferrer">坐禪系列電子書</a></li>
                    </ul>
                </div>
                <div class="footer-col">
                    <h4>問答錄2</h4>
                    <ul>
                        <li><a href="{prefix}wenda2.html">主題目錄（12 章）</a></li>
                        <li><a href="{prefix}wenda2_ebook/index_trad.html" target="_blank" rel="noopener noreferrer">完整電子書</a></li>
                    </ul>
                </div>
                <div class="footer-col">
                    <h4>更多資源</h4>
                    <ul>
                        <li><a href="{prefix}infographic.html">名詞圖解</a></li>
                        <li><a href="{prefix}mindmap.html">名詞關聯心智圖</a></li>
                        <li><a href="{prefix}stories.html">實修故事</a></li>
                        <li><a href="{prefix}index.html#downloads">資料下載</a></li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                <p>歡迎分享給更多人結法緣</p>
                <p>願一切眾生離苦得樂，早證菩提</p>
            </div>
        </div>
    </footer>
'''

def replace_nav(text, prefix):
    # current pages: <header class="navbar">...</header> optionally followed by <div id="site-menu-veil">
    m = re.search(r'\s*<header class="navbar".*?</header>\s*(?:<div id="site-menu-veil"[^>]*></div>)?', text, flags=re.S)
    if not m:
        raise SystemExit('header not found')
    return text[:m.start()] + '\n' + nav(prefix) + text[m.end():]

def replace_footer(text, prefix):
    m = re.search(r'\s*<footer class="footer">.*?</footer>', text, flags=re.S)
    if not m:
        raise SystemExit('footer not found')
    return text[:m.start()] + '\n' + footer(prefix) + text[m.end():]

def process(path, prefix):
    s = open(path, encoding='utf-8').read()
    if MARKER in s:
        print('skip (already)', path)
        return
    s = replace_nav(s, prefix)
    s = replace_footer(s, prefix)
    open(path, 'w', encoding='utf-8').write(s)
    print('done', path)

if __name__ == '__main__':
    for p in ['wenda2.html', 'stories.html', 'infographic.html', 'mindmap.html']:
        process(os.path.join(ROOT, p), '')
    for i in range(1, 13):
        process(os.path.join(ROOT, 'wenda2', 'chapter-%02d.html' % i), '../')