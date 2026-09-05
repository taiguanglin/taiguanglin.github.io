#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Redesign chapter/marketing pages: extract inner content from legacy pages,
wrap into the new pink design-system chrome (nav per DESIGN.md, serif hero,
new footer), and write back. Idempotent via markers:
    <!-- <<<NEW-CHROME>>> --> ... <!-- <<</NEW-CHROME>>> -->
Run: python3 tool/redesign_pages.py
"""
import io
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# -----------------------------------------------------------------------------
# Design-system chrome (canonical, shared)
# -----------------------------------------------------------------------------
def nav_html(prefix):
    return f'''    <header class="navbar" id="navbar">
      <div class="nav-container">
        <a href="{prefix}index.html" class="nav-logo">
          <span class="logo-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4c2.2 2.2 3.2 4.6 3.2 6.8-2.1 1.3-4.3 1.3-6.4 0C8.8 8.6 9.8 6.2 12 4z"/><path d="M4.5 12.5c1.8-.8 3.8-.7 5.2.6M19.5 12.5c-1.8-.8-3.8-.7-5.2.6"/><path d="M5 16c1.8 1.6 4.2 2.4 7 2.4s5.2-.8 7-2.4"/></svg>
          </span>
          <span class="logo-text"><span class="logo-name">TaiGuangLin</span><span class="logo-sub">次世代終極佛法</span></span>
        </a>
        <nav class="nav-menu" id="nav-menu" aria-label="主選單">
          <a class="nav-link" href="{prefix}index.html">首頁</a>
          <a class="nav-link" href="{prefix}wenda2.html">問答錄 2</a>
          <a class="nav-link" href="{prefix}stories.html">實修故事</a>
          <a class="nav-link" href="{prefix}infographic.html">名詞圖解</a>
          <a class="nav-link" href="{prefix}mindmap.html">心智圖</a>
          <a class="nav-link" href="{prefix}index.html#downloads">下載</a>
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

FONTS = ('    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500;600;700;900'
         '&family=Noto+Sans+TC:wght@300;400;500;600;700&display=swap" rel="stylesheet">\n')

PAGE_CSS = '''
  <!-- 頁面專屬樣式寫在個別檔案的 <style id="page-style">，共用 design system 在 style.css -->
'''

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()

def write(p, s):
    with io.open(p, 'w', encoding='utf-8') as f:
        f.write(s)

def extract_block(html, start_marker, end_marker):
    """Return inner html between markers (markers not included)."""
    i = html.index(start_marker) + len(start_marker)
    j = html.index(end_marker)
    return html[i:j]


# -----------------------------------------------------------------------------
# Chapter pages (wenda2/chapter-NN.html)
# -----------------------------------------------------------------------------
CH_META = {
    1:  ("第01章：自性與意識", "自性與意識",
         "探討自性的恆常、不生不滅，與意識結構、萬法唯心所現的根本義。"),
    2:  ("第02章：羯磨（業）", "羯磨（業）",
         "業的造作、成熟、轉化與善惡因果的底層邏輯。"),
    3:  ("第03章：發心", "發心",
         "出離心、菩提心與願力；從自度到度他的發心次第。"),
    4:  ("第04章：世界起源與輪迴", "世界起源與輪迴",
         "三界結構、眾生輪轉與時間空間的佛法宇宙觀。"),
    5:  ("第05章：戒行", "戒行",
         "持戒的清淨基礎，日常生活的身語意規範與實踐。"),
    6:  ("第06章：修福積功德", "修福積功德",
         "布施、供養、放生與功德轉化的具體方法與原理。"),
    7:  ("第07章：念誦經咒", "念誦經咒",
         "經咒的持誦要訣、感應原理與常見疑難排解。"),
    8:  ("第08章：腹式呼吸", "腹式呼吸",
         "呼吸法的操作細節、身心反應與漸次的深入次第。"),
    9:  ("第09章：磕大頭", "磕大頭",
         "磕大頭的動作要領、功效、排障反應與精進方法。"),
    10: ("第10章：雙盤", "雙盤",
         "雙盤坐姿的循序漸進、腿痛處理與突破關鍵。"),
    11: ("第11章：禪定", "禪定",
         "從初禪到四禪的體證、境界辨識與安全注意事項。"),
    12: ("第12章：佛門修行", "佛門修行",
         "佛門日常功課、師承規矩與修行生活的整體說明。"),
}
NEXT_TITLE = {i: CH_META[i+1][1] for i in range(1, 12)}

# 第 12 章「佛門修行」補充佛門常識簡介（Q&A 之外的知識導讀）
CH_INTRO = {
    12: '''          <section class="chapter-intro card reveal" id="fo-men-intro">
            <h2><span class="zh-numeral">引言</span>佛門常識簡介</h2>
            <p>本章不只收錄問答，也統整初學者進入佛門修行時最常接觸的基本觀念。以下是三個貫穿本章的核心概念：</p>
            <ul class="intro-list">
              <li><strong>加持</strong>：佛菩薩以願力與功德迴向眾生，使修行者在相應的善法與因緣上獲得增上。加持不取代自力修行，而是以佛力為緣，幫助行人自己成就業的轉化。</li>
              <li><strong>諸佛同體</strong>：十方三世一切佛，在同一法身、同一真性之中。禮敬一佛即禮敬諸佛；供養一尊即供養一切。因此念佛、拜佛、持咒皆可與諸佛相應。</li>
              <li><strong>修行圓滿</strong>：以出離心為基礎、菩提心為根本、戒行為護持，輔以念佛持咒與禪定實修，循序漸進，不可只求感應而忽略心地功夫。</li>
            </ul>
            <p>如果對某些名相不熟悉，可先瀏覽上方「知識簡介」，再回到下方的師父問答原文，即可理解問題脈絡。</p>
          </section>''',
}

def redesign_chapter(n):
    path = os.path.join(ROOT, 'wenda2', 'chapter-%02d.html' % n)
    html = read(path)
    # Already redesigned? Rebuild deterministically from data segments.
    seg_start = '      <!-- @@DATA-SEG-START@@ -->\n'
    seg_end = '      <!-- @@DATA-SEG-END@@ -->'
    if seg_start in html:
        data = extract_block(html, seg_start, seg_end)
    else:
        # legacy: from TOC comment up to (excluding) the dharma quote section
        m0 = html.index('            <!-- 目錄 -->')
        m1 = html.index('            <!-- 禪師法語 -->')
        data = html[m0:m1]
        # normalize indent (legacy used 12 spaces)
        data = '\n'.join(line[12:] if line.startswith('            ') else line
                         for line in data.splitlines())
    # ---- conversions work on both legacy and already-extracted data (idempotent) ----
    # remove legacy duplicated bottom chapter-navigation block (before qa-quote)
    data = re.sub(r'\n\s*<!-- 章節導航 -->\s*\n\s*<div class="chapter-navigation">.*?</div>\s*\n',
                  '\n', data, flags=re.S)
    # remove legacy inline styles that refer to dropped variables
    data = data.replace('<span style="color: var(--text-muted); font-size: 14px;">' ,
                        '<span class="chapter-progress">')
    # strip leftover Font Awesome icons
    data = re.sub(r'<i class="(fas|far|fab)[^"]*"></i> ?', '', data)
    # toc / headings get the new design class names
    data = data.replace('class="toc"', 'class="qa-toc card reveal"')
    data = data.replace('class="toc-list"', 'class="qa-toc-list"')
    data = data.replace('class="toc-item"', 'class="qa-toc-item"')
    data = data.replace('class="toc-link"', 'class="qa-toc-link"')
    data = data.replace('class="qa-section"', 'class="qa-body"')
    data = data.replace('class="section-title"', 'class="qa-banner"')
    # normalize legacy qa-* class names onto the new system (new names are no-ops)
    pairs = [
        ('qa-content', 'qa-panel card'),
        ('qa-item', 'qa-entry'),
        ('question-meta', 'qa-q-meta'),
        ('question-text', 'qa-q-text'),
        ('answer-meta', 'qa-a-meta'),
        ('answer-text', 'qa-a-text'),
        ('question-time', 'qa-q-time'),
        ('questioner', 'qa-q-name'),
        ('subsection-title', 'qa-sub-title'),
        ('subsection', 'qa-sub'),
        ('answerer', 'qa-a-name'),
        ('answer', 'qa-a'),
        ('question', 'qa-q'),
        ('highlight', 'qa-highlight'),
        ('complete-version-container', 'qa-more'),
        ('complete-version-button', 'btn btn-primary btn-sm'),
    ]
    for old, new in pairs:
        data = data.replace('class="%s"' % old, 'class="%s"' % new)
    # drop any previously inserted chapter intro (idempotency for CH_INTRO)
    data = re.sub(r'\s*<section class="chapter-intro card reveal" id="fo-men-intro">.*?</section>\s*',
                  '\n', data, flags=re.S)
    # end conversions
    title, cn_title, subtitle = CH_META[n]
    head = html[:html.index('</head>')]
    # keep original <head> SEO/meta up to styles, rebuild fresh head:
    meta_match = re.search(r'<meta name="description" content="([^"]*)"', html)
    desc = meta_match.group(1) if meta_match else subtitle
    canon = 'https://taiguanglin.info/wenda2/chapter-%02d.html' % n
    new_head = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{CH_META[n][0]}｜TaiGuangLin 禪師佛法修行問答錄</title>
    <meta name="description" content="{desc}">
    <meta name="keywords" content="{cn_title},TaiGuangLin,佛法問答,修行問答,坐禪,問答錄2">
    <meta name="author" content="TaiGuangLin">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="{CH_META[n][0]}｜TaiGuangLin 禪師佛法修行問答錄">
    <meta property="og:description" content="{desc}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canon}">
    <meta property="og:image" content="https://taiguanglin.info/images/taiguanglin.png">
    <link rel="canonical" href="{canon}">
    <link rel="icon" type="image/x-icon" href="../images/favicon.ico">
    <link rel="shortcut icon" type="image/x-icon" href="../images/favicon.ico">
    <link rel="stylesheet" href="../style.css">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500;600;700;900&family=Noto+Sans+TC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
{nav_html('../')}
    <!-- 頁首 -->
    <section class="page-hero page-hero--chapter">
      <div class="container">
        <nav class="crumbs" aria-label="位置">
          <a href="../index.html">首頁</a><span class="crumbs-sep">/</span>
          <a href="../wenda2.html">問答錄 2</a><span class="crumbs-sep">/</span>
          <span aria-current="page">第{n:02d}章</span>
        </nav>
        <span class="kicker">Q&amp;A RECORD · CHAPTER {n:02d}</span>
        <h1 class="display">{cn_title}</h1>
        <p class="lede">{subtitle}</p>
      </div>
    </section>

    <main class="chapter main">
      <div class="container chapter-layout">
        <aside class="chapter-side">
          <div class="chapter-index card">
            <div class="chapter-index-num">{n:02d}</div>
            <div class="chapter-index-count">共 12 章</div>
            <div class="chapter-index-title">{cn_title}</div>
            <div class="chapter-side-nav">
'''
    if n > 1:
        new_head += f'              <a class="btn btn-ghost btn-sm" href="chapter-{n-1:02d}.html">⟵ 上一章</a>\n'
    new_head += f'''              <a class="btn btn-outline btn-sm" href="../wenda2.html">回目錄</a>
'''
    if n < 12:
        new_head += f'              <a class="btn btn-primary btn-sm" href="chapter-{n+1:02d}.html">下一章 ⟶</a>\n'
    new_head += f'''            </div>
          </div>
        </aside>
        <div class="chapter-body">
          <!-- 章節導航 -->
          <div class="chapter-navigation reveal">
            <a href="../wenda2.html" class="nav-button back"><i>‹</i> 返回目錄</a>
            <span>第{n:02d}章 共12章</span>
'''
    if n < 12:
        new_head += f'            <a href="chapter-{n+1:02d}.html" class="nav-button next">下一章：{NEXT_TITLE[n]} <i>›</i></a>\n'
    else:
        new_head += '            <a href="../wenda2.html" class="nav-button next">回目錄 <i>›</i></a>\n'
    new_head += f'''          </div>

          {seg_start}{data if n not in CH_INTRO else CH_INTRO[n] + chr(10) + data}{seg_end}
          <section class="qa-quote reveal">
            <div class="inner">
              <blockquote class="q">「自性恆常是初始設定，它本來就這樣，這個世界的最基本的底層真相就是這個。」</blockquote>
              <cite class="cite">── TaiGuangLin 禪師</cite>
            </div>
          </section>
        </div>
      </div>
    </main>
'''
    new_head += FOOTER.format(p='../')
    new_head += '''    <script src="../shared.js" defer></script>
</body>
</html>
'''
    write(path, new_head)
    return path


def main():
    for n in range(1, 13):
        p = redesign_chapter(n)
        print('redesigned', p)

if __name__ == '__main__':
    main()
