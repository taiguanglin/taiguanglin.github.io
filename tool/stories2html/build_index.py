#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""改寫 stories.html 的故事清單、index.html 的故事卡片與 sitemap.xml，
讓它們指向新的純 HTML 閱讀頁（原檔下載仍保留在各篇最末端）。"""
import os
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
        out.append('            <div class="st-cat reveal">')
        out.append('                <h2 class="st-cat-title">%s</h2>' % CATEGORY_TITLES[cat])
        out.append('                <div class="st-list">')
        for d in items:
            kind = os.path.splitext(d["source"])[1].lstrip(".").upper()
            out.append('                    <div class="st-item">')
            out.append('                        <div class="st-head">')
            out.append('                            <h3><a href="stories/%s.html">%s</a></h3>'
                       % (d["slug"], d["title"]))
            out.append('                            <span class="st-author">%s</span>' % d["author"])
            out.append('                        </div>')
            out.append('                        <p class="st-desc">%s</p>' % d["summary"])
            out.append('                        <div class="st-meta">')
            out.append('                            <span class="st-type">HTML</span>')
            out.append('                            <a href="stories/%s.html" class="st-link">線上閱讀</a>'
                       % d["slug"])
            out.append('                            <a href="stories/%s" class="st-link st-link--muted" download>下載原檔（%s）</a>'
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

    # 換掉 STORIES-LIST 標記之間的整段清單（可重複執行）
    begin = '<!-- STORIES-LIST:BEGIN -->'
    end_marker = '<!-- STORIES-LIST:END -->'
    if begin in html and end_marker in html:
        i = html.index(begin) + len(begin)
        j = html.index(end_marker)
        html = html[:i] + "\n" + stories_list_html() + "\n      " + html[j:]
    else:  # legacy page: 從第一個分類區塊起、到禪師法語區塊前
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
    """更新 sitemap.xml。

    sitemap 的單一產生器是 ``tool/site_chrome/sitemap.py``（依實際發布檔案
    反推 URL 與 lastmod，並跳過 noindex / meta refresh 頁）。本函式只做
    代理，避免這裡再維護一份會過期的 URL 清單。
    """
    import importlib.util

    path = os.path.join(ROOT, "tool", "site_chrome", "sitemap.py")
    spec = importlib.util.spec_from_file_location("_site_chrome_sitemap", path)
    if spec is None or spec.loader is None:
        raise ImportError("無法載入 sitemap 產生器：%s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.write_sitemap()
    return os.path.join(ROOT, "sitemap.xml")


if __name__ == "__main__":
    print("更新", patch_stories_page())
    print("更新", "%s（%d 張卡片）" % patch_index_page())
    print("更新", patch_sitemap())
