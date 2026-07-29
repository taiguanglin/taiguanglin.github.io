#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""改寫 stories.html 的故事清單、index.html 的故事卡片與 sitemap.xml，
讓它們指向新的純 HTML 閱讀頁（原檔下載仍保留在各篇最末端）。"""
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docs import CATEGORY_ORDER, DOCS  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SITE = "https://taiguanglin.info"

CATEGORY_TITLES = {
    "雙盤打坐": "佛法修行雙盤打坐心得分享",
    "磕大頭（大禮拜）": "佛法修行磕大頭（大禮拜）實修心得",
    "呼吸法": "呼吸法修行",
    "經典研習": "經典研習心得",
    "綜合實修": "誦經、治病與家庭的綜合實修",
}


def stories_list_html():
    out = []
    for cat in CATEGORY_ORDER:
        items = [d for d in DOCS if d["category"] == cat]
        if not items:
            continue
        out.append('            <!-- %s -->' % cat)
        out.append('            <div class="story-category">')
        out.append('                <h2 class="category-title">%s</h2>' % CATEGORY_TITLES[cat])
        out.append('                <div class="stories-list">')
        for d in items:
            kind = os.path.splitext(d["source"])[1].lstrip(".").upper()
            out.append('                    <div class="story-item">')
            out.append('                        <div class="story-header">')
            out.append('                            <h3><a href="stories/%s.html">%s</a></h3>'
                       % (d["slug"], d["title"]))
            out.append('                            <span class="story-author">%s</span>' % d["author"])
            out.append('                        </div>')
            out.append('                        <p class="story-description">%s</p>' % d["summary"])
            out.append('                        <div class="story-meta">')
            out.append('                            <span class="file-type">HTML</span>')
            out.append('                            <a href="stories/%s.html" class="download-link">線上閱讀</a>'
                       % d["slug"])
            out.append('                            <a href="stories/%s" class="download-link download-link-muted" download>下載原檔（%s）</a>'
                       % (d["source"].split("/", 1)[1].replace(" ", "%20"), kind))
            out.append('                        </div>')
            out.append('                    </div>')
        out.append('                </div>')
        out.append('            </div>')
        out.append('')
    return "\n".join(out)


def patch_stories_page():
    path = os.path.join(ROOT, "stories.html")
    with open(path, encoding="utf-8") as fh:
        html = fh.read()

    # 從第一個分類區塊起、到禪師法語區塊前，整段換掉（可重複執行）
    end = html.index("            <!-- 禪師法語 -->")
    start = html.rindex("\n", 0, html.index('<div class="story-category">')) + 1
    html = html[:start] + stories_list_html() + html[end:]

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path


def patch_index_page():
    """首頁三張故事卡改為連到閱讀頁。"""
    path = os.path.join(ROOT, "index.html")
    with open(path, encoding="utf-8") as fh:
        html = fh.read()

    by_source = {d["source"]: d for d in DOCS}
    changed = 0
    for source, d in by_source.items():
        old = '<a href="%s" target="_blank" class="story-button">下載檔案</a>' % source
        if old in html:
            html = html.replace(old, '<a href="stories/%s.html" class="story-button">閱讀全文</a>' % d["slug"])
            changed += 1
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path, changed


def patch_sitemap():
    path = os.path.join(ROOT, "sitemap.xml")
    with open(path, encoding="utf-8") as fh:
        xml = fh.read()

    today = datetime.date.today().isoformat()
    xml = re.sub(r"\n  <!-- ============ 實修故事.*?(?=\n</urlset>)", "", xml, flags=re.S)
    entries = ["", "  <!-- ============ 實修故事（逐篇 HTML） ============ -->"]
    for cat in CATEGORY_ORDER:
        for d in [x for x in DOCS if x["category"] == cat]:
            entries.append("")
            entries.append("  <!-- %s｜%s -->" % (d["category"], d["title"]))
            entries.append("  <url>")
            entries.append("    <loc>%s/stories/%s.html</loc>" % (SITE, d["slug"]))
            entries.append("    <lastmod>%s</lastmod>" % today)
            entries.append("    <changefreq>yearly</changefreq>")
            entries.append("    <priority>0.7</priority>")
            entries.append("  </url>")
    xml = xml.replace("\n</urlset>", "\n".join(entries) + "\n\n</urlset>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(xml)
    return path


if __name__ == "__main__":
    print("更新", patch_stories_page())
    print("更新", "%s（%d 張卡片）" % patch_index_page())
    print("更新", patch_sitemap())
