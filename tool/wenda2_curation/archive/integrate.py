# -*- coding: utf-8 -*-
import re, os

os.chdir('/Users/paul/tai/taiguanglin.github.io')

pages_root = ['index.html', 'infographic.html', 'mindmap.html', 'stories.html', 'wenda2.html']
pages_ch = [f'wenda2/chapter-{i:02d}.html' for i in range(1, 13)]
changed = []

nav_re = re.compile(r'^(\s*)<a href="((?:\.\./)?mindmap\.html)" class="nav-dropdown-item([^"]*)"(?:\s+aria-current="page")?>(名詞關聯心智圖)</a>\s*$', re.M)
foot_re = re.compile(r'^(\s*)<li><a href="((?:\.\./)?mindmap\.html)">名詞關聯心智圖</a></li>\s*$', re.M)

def patch_page(fn):
    s = open(fn, encoding='utf-8').read()
    orig = s
    def nav_sub(m):
        ind, pfx, cls, _ = m.group(1), m.group(2), m.group(3), m.group(4)
        out = (f'{ind}<a href="{pfx}mindmap.html" class="nav-dropdown-item{cls}">{m.group(4)}</a>\n'
               f'{ind}<a href="{pfx}wenda2_knowledge.html" class="nav-dropdown-item">問答錄2 重點知識</a>\n'
               f'{ind}<a href="{pfx}wenda2_mindmap.html" class="nav-dropdown-item">問答錄2 名詞心智圖</a>')
        return out
    s2 = nav_re.sub(nav_sub, s, count=1)
    def foot_sub(m):
        ind, pfx = m.group(1), m.group(2)
        return (f'{ind}<li><a href="{pfx}mindmap.html">名詞關聯心智圖</a></li>\n'
                f'{ind}<li><a href="{pfx}wenda2_knowledge.html">問答錄2 重點知識</a></li>\n'
                f'{ind}<li><a href="{pfx}wenda2_mindmap.html">問答錄2 名詞心智圖</a></li>')
    s2 = foot_re.sub(foot_sub, s2, count=1)
    if s2 != orig:
        open(fn, 'w', encoding='utf-8').write(s2)
        changed.append(fn)
        return True
    return False

for fn in pages_root + pages_ch:
    ok = patch_page(fn)
    print(('PATCHED ' if ok else 'NO-CHANGE ') + fn)

# ---- shared.js ----
s = open('shared.js', encoding='utf-8').read()
old = """        if (file === 'infographic.html' || file === 'mindmap.html') {
            var wanted = file === 'infographic.html' ? 'infographic.html' : 'mindmap.html';"""
new = """        if (file === 'infographic.html' || file === 'mindmap.html' ||
            file === 'wenda2_knowledge.html' || file === 'wenda2_mindmap.html') {
            var wanted = file;"""
assert old in s, 'shared.js pattern not found'
s = s.replace(old, new)
open('shared.js', 'w', encoding='utf-8').write(s)
print('PATCHED shared.js')

# ---- sitemap.xml ----
s = open('sitemap.xml', encoding='utf-8').read()
old = """  <!-- 名詞關聯心智圖 -->
  <url>
    <loc>https://taiguanglin.info/mindmap.html</loc>
    <lastmod>2026-07-29</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
"""
new = old + """
  <!-- 坐禪之問答錄2 重點知識 -->
  <url>
    <loc>https://taiguanglin.info/wenda2_knowledge.html</loc>
    <lastmod>2026-09-16</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>

  <!-- 坐禪之問答錄2 名詞心智圖 -->
  <url>
    <loc>https://taiguanglin.info/wenda2_mindmap.html</loc>
    <lastmod>2026-09-16</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
"""
assert old in s, 'sitemap pattern not found'
s = s.replace(old, new, 1)
open('sitemap.xml', 'w', encoding='utf-8').write(s)
print('PATCHED sitemap.xml')

# ---- wenda2.html 入口 ----
s = open('wenda2.html', encoding='utf-8').read()
old = """            <div class="more-stories">
                <a href="wenda2_ebook/index_trad.html" target="_blank" rel="noopener noreferrer" class="btn btn-primary">進入完整電子書<span class="arr">→</span></a>
            </div>"""
new = """            <div class="more-stories">
                <a href="wenda2_ebook/index_trad.html" target="_blank" rel="noopener noreferrer" class="btn btn-primary">進入完整電子書<span class="arr">→</span></a>
                <a href="wenda2_knowledge.html" class="btn btn-primary">21 章重點知識<span class="arr">→</span></a>
                <a href="wenda2_mindmap.html" class="btn btn-primary">名詞分析心智圖<span class="arr">→</span></a>
            </div>"""
assert old in s, 'wenda2.html more-stories not found'
s = s.replace(old, new, 1)
open('wenda2.html', 'w', encoding='utf-8').write(s)
print('PATCHED wenda2.html')
