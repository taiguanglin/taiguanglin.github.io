#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把抽出的區塊 JSON 組成 stories/<slug>.html 純 HTML 閱讀頁。"""
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixups  # noqa: E402
from docs import CATEGORY_ORDER, DOCS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BUILD = os.path.join(HERE, "build")
SITE = "https://taiguanglin.info"

NAV = """    <nav class="navbar" id="navbar">
        <div class="nav-container">
            <div class="nav-logo">
                <h2>TaiGuangLin</h2>
                <span>次世代終極佛法</span>
            </div>
            <div class="nav-menu" id="nav-menu">
                <a href="../index.html#home" class="nav-link">首頁</a>
                <a href="../index.html#about" class="nav-link">禪師</a>
                <a href="../index.html#books" class="nav-link">著作</a>
                <a href="../wenda2.html" class="nav-link">問答錄2</a>
                <a href="../stories.html" class="nav-link">故事</a>
                <div class="nav-dropdown">
                    <a href="#" class="nav-link nav-dropdown-toggle">圖解 <i class="fas fa-chevron-down"></i></a>
                    <div class="nav-dropdown-menu">
                        <a href="../infographic.html" class="nav-dropdown-item">名詞圖解</a>
                        <a href="../mindmap.html" class="nav-dropdown-item">名詞關聯心智圖</a>
                    </div>
                </div>
                <a href="../index.html#downloads" class="nav-link">下載</a>
            </div>
            <div class="hamburger" id="hamburger">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    </nav>"""

FOOTER = """    <footer class="footer">
        <div class="container">
            <div class="footer-content">
                <div class="footer-section">
                    <h3>TaiGuangLin</h3>
                    <p>次世代終極版佛法</p>
                    <p>用現代通俗易懂的語言，傳承純正佛法智慧</p>
                </div>
                <div class="footer-section">
                    <h4>著作與電子書</h4>
                    <ul>
                        <li><a href="../index.html#books">五本著作</a></li>
                        <li><a href="../ebook/index_trad.html" target="_blank" rel="noopener noreferrer">坐禪系列電子書</a></li>
                    </ul>
                </div>
                <div class="footer-section">
                    <h4>問答錄2</h4>
                    <ul>
                        <li><a href="../wenda2.html">主題目錄（12 章）</a></li>
                        <li><a href="../wenda2_ebook/index_trad.html" target="_blank" rel="noopener noreferrer">完整電子書</a></li>
                    </ul>
                </div>
                <div class="footer-section">
                    <h4>更多資源</h4>
                    <ul>
                        <li><a href="../infographic.html">名詞圖解</a></li>
                        <li><a href="../mindmap.html">名詞關聯心智圖</a></li>
                        <li><a href="../stories.html">實修故事</a></li>
                        <li><a href="../index.html#downloads">資料下載</a></li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                <p>歡迎分享給更多人結法緣</p>
                <p>願一切眾生離苦得樂，早證菩提</p>
            </div>
        </div>
    </footer>"""


def esc(s):
    return html.escape(s, quote=False)


def human_size(n):
    if n >= 1024 * 1024:
        return "%.1f MB" % (n / 1024 / 1024)
    return "%.0f KB" % (n / 1024)


def file_kind(source):
    return os.path.splitext(source)[1].lstrip(".").upper()


# --------------------------------------------------------------------------
def group_qa(blocks):
    """把連續的問／答段落包成一組。"""
    out, i = [], 0
    while i < len(blocks):
        b = blocks[i]
        if b.get("qa") == "q":
            group = [b]
            i += 1
            while i < len(blocks) and blocks[i]["t"] == "p" and blocks[i].get("qa") != "q":
                group.append(blocks[i])
                i += 1
            out.append({"t": "qa", "items": group})
            continue
        out.append(b)
        i += 1
    return out


def merge_quotes(blocks):
    """相鄰的引言段落合成一個 blockquote。"""
    out = []
    for b in blocks:
        if b["t"] == "p" and b.get("quote"):
            if out and out[-1]["t"] == "quote":
                out[-1]["items"].append(b)
                continue
            out.append({"t": "quote", "items": [b]})
            continue
        out.append(b)
    return out


def group_compact_tables(blocks):
    """把拆開的每月小表排成網格，免得讀者一路往下滑六張表。"""
    out, i = [], 0
    while i < len(blocks):
        if blocks[i]["t"] == "table" and blocks[i].get("compact"):
            run = []
            while i < len(blocks) and blocks[i]["t"] == "table" and blocks[i].get("compact"):
                run.append(blocks[i])
                i += 1
            out.append({"t": "table-grid", "items": run} if len(run) > 1 else run[0])
            continue
        out.append(blocks[i])
        i += 1
    return out


def merge_front(blocks):
    """原檔標題頁的數行併成一個區塊。"""
    front, rest = [], list(blocks)
    while rest and rest[0].get("front"):
        front.append(rest.pop(0))
    return ([{"t": "front", "items": front}] if front else []) + rest


def render_body(blocks, slug, title, toc):
    parts = []
    sec = 0
    n_img = 0

    def para(b):
        text = b["text"]
        if b.get("bold"):
            return '<p class="noindent"><strong>%s</strong></p>' % esc(text)
        cls = ""
        if b.get("qa") == "q":
            cls = ' class="q"'
        elif b.get("qa") == "a":
            cls = ' class="a"'
        return "<p%s>%s</p>" % (cls, esc(text))

    for b in blocks:
        t = b["t"]
        if t in ("h2", "h3"):
            sec += 1
            hid = "sec-%d" % sec
            label = b["text"]
            date = b.get("date")
            inner = esc(label)
            cls = ""
            if date:
                inner = '<span class="story-h-date">%s</span>%s' % (esc(date), esc(label))
                cls = ' class="has-date"'
            parts.append('<%s id="%s"%s>%s</%s>' % (t, hid, cls, inner, t))
            toc.append({"id": hid, "level": t, "text": (date + "　" if date else "") + label})
        elif t == "p":
            parts.append(para(b))
        elif t == "quote":
            parts.append("<blockquote>%s</blockquote>"
                         % "".join(para(x) for x in b["items"]))
        elif t == "front":
            parts.append('<div class="story-frontmatter">%s</div>'
                         % "".join('<p>%s</p>' % esc(x["text"]) for x in b["items"]))
        elif t == "qa":
            parts.append('<div class="story-qa">%s</div>'
                         % "".join(para(x) for x in b["items"]))
        elif t == "img":
            cap = b.get("caption")
            n_img += 1
            alt = b.get("alt") or cap or "《%s》原檔插圖 %d" % (title, n_img)
            wide = " wide" if b["w"] >= 1000 else ""
            fig = ['<figure class="story-figure%s">' % wide]
            fig.append('<img src="assets/img/%s/%s" alt="%s" width="%d" height="%d" loading="lazy" decoding="async">'
                       % (slug, b["src"], esc(alt), b["w"], b["h"]))
            if cap:
                fig.append("<figcaption>%s</figcaption>" % esc(cap))
            fig.append("</figure>")
            parts.append("".join(fig))
        elif t == "caption":
            parts.append('<p class="noindent"><small>%s</small></p>' % esc(b["text"]))
        elif t == "table":
            parts.append(render_table(b))
        elif t == "table-grid":
            parts.append('<div class="story-table-grid">%s</div>'
                         % "".join(render_table(x) for x in b["items"]))
    return "\n            ".join(parts)


def render_table(b):
    rows = [["" if c is None else str(c).strip() for c in r] for r in b["rows"]]
    head_rows = 1 if b.get("compact") else 2
    out = ['<div class="story-table-wrap"><table>']
    if b.get("caption"):
        out.append("<caption>%s</caption>" % esc(b["caption"]))
    out.append("<thead>")
    for r in rows[:head_rows]:
        out.append("<tr>%s</tr>" % "".join("<th>%s</th>" % esc(c) for c in r))
    out.append("</thead><tbody>")
    for r in rows[head_rows:]:
        out.append("<tr>%s</tr>" % "".join("<td>%s</td>" % esc(c) for c in r))
    out.append("</tbody></table></div>")
    return "".join(out)


def render_toc(toc):
    if len(toc) < 3:
        return ""
    items = "\n                    ".join(
        '<li class="%s"><a href="#%s">%s</a></li>'
        % ("lv3" if e["level"] == "h3" else "lv2", e["id"], esc(e["text"])) for e in toc)
    return """
    <div class="story-toc" id="story-toc">
        <details%s>
            <summary>本篇目錄（%d 節）</summary>
            <nav>
                <ol>
                    %s
                </ol>
            </nav>
        </details>
    </div>""" % (" open" if len(toc) <= 12 else "", len(toc), items)


# --------------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}｜TaiGuangLin 禪師弟子實修故事</title>
    <meta name="description" content="{summary}">
    <meta name="keywords" content="{keywords}">
    <meta name="author" content="{author}">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="{title}｜TaiGuangLin 禪師弟子實修故事">
    <meta property="og:description" content="{summary}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{site}/stories/{slug}.html">
    <meta property="og:image" content="{site}/images/taiguanglin.png">
    <link rel="canonical" href="{site}/stories/{slug}.html">
    <link rel="icon" type="image/x-icon" href="../images/favicon.ico">
    <link rel="shortcut icon" type="image/x-icon" href="../images/favicon.ico">
    <link rel="stylesheet" href="../style.css">
    <link rel="stylesheet" href="assets/story.css">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <script type="application/ld+json">
{jsonld}
    </script>
</head>
<body class="story-body">
    <div class="reading-progress" aria-hidden="true"></div>

    <!-- 導覽列 -->
{nav}

    <!-- 故事標頭 -->
    <header class="story-hero">
        <div class="story-hero-inner">
            <p class="story-crumbs">
                <a href="../index.html#home">首頁</a> ／ <a href="../stories.html">實修故事</a> ／ {category}
            </p>
            <h1>{title}</h1>
            <p class="story-original-title">原文標題：{orig_title}</p>
            <div class="story-byline">
                <span class="story-tag">{category}</span>
                <span class="story-author-name">{author}</span>{date_html}
                <span>約 {chars} 字 · 閱讀約 {minutes} 分鐘</span>
            </div>
            <p class="story-lede">{summary}</p>
        </div>
    </header>

    <!-- 閱讀工具 -->
    <div class="story-toolbar" role="toolbar" aria-label="閱讀設定">
        <button type="button" id="story-font-smaller" title="縮小字級"><i class="fas fa-minus"></i> 字級</button>
        <button type="button" id="story-font-bigger" title="放大字級"><i class="fas fa-plus"></i> 字級</button>
        <button type="button" id="story-dark-btn" aria-pressed="false"><i class="fas fa-moon"></i> 深色</button>
    </div>
{toc}

    <!-- 內文（依原檔逐字轉錄） -->
    <article class="story-article" id="story-article">
            {body}
    </article>

    <div class="story-end">
        <hr class="story-end-rule">
        <div class="story-siblings">{siblings}</div>
        <p class="story-back"><a href="../stories.html"><i class="fas fa-arrow-left"></i> 回實修故事總覽</a></p>
        <p class="story-source">
            本頁內容依原始檔案逐字轉錄；如需原始版面，可下載
            <a href="{download}" download>{filename}</a>（{kind}，{size}）。
        </p>
    </div>

    <div class="story-lightbox" role="dialog" aria-label="放大檢視圖片">
        <button type="button" class="close" aria-label="關閉">&times;</button>
        <img alt="">
    </div>

    <!-- 頁尾 -->
{footer}

    <script src="../script.js"></script>
    <script src="assets/story.js"></script>
</body>
</html>
"""


def build(cfg, neighbours):
    slug = cfg["slug"]
    with open(os.path.join(BUILD, slug + ".json"), encoding="utf-8") as fh:
        blocks = json.load(fh)
    blocks = fixups.apply(slug, blocks)
    blocks = merge_front(merge_quotes(group_compact_tables(group_qa(blocks))))

    toc = []
    body = render_body(blocks, slug, cfg["title"], toc)
    chars = sum(len(x.get("text", "")) for b in blocks
                for x in (b["items"] if b["t"] in ("qa", "quote", "front", "table-grid") else [b]))

    src_path = os.path.join(ROOT, cfg["source"])
    filename = os.path.basename(cfg["source"])

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": cfg["title"],
        "alternativeHeadline": cfg["orig_title"],
        "description": cfg["summary"],
        "author": {"@type": "Person", "name": cfg["author"]},
        "publisher": {"@type": "Organization", "name": "TaiGuangLin",
                      "url": SITE + "/"},
        "inLanguage": "zh",
        "articleSection": cfg["category"],
        "keywords": cfg["keywords"],
        "mainEntityOfPage": "%s/stories/%s.html" % (SITE, slug),
        "isBasedOn": "%s/stories/%s" % (SITE, filename),
        **({"datePublished": cfg["date"]} if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cfg["date"]) else {}),
    }, ensure_ascii=False, indent=6)

    prev_cfg, next_cfg = neighbours
    sib = []
    if prev_cfg:
        sib.append('<a href="%s.html"><span><i class="fas fa-chevron-left"></i> 上一篇</span><strong>%s</strong></a>'
                   % (prev_cfg["slug"], esc(prev_cfg["title"])))
    if next_cfg:
        sib.append('<a href="%s.html"><span>下一篇 <i class="fas fa-chevron-right"></i></span><strong>%s</strong></a>'
                   % (next_cfg["slug"], esc(next_cfg["title"])))

    page = PAGE.format(
        site=SITE, slug=slug, nav=NAV, footer=FOOTER,
        title=esc(cfg["title"]), orig_title=esc(cfg["orig_title"]),
        summary=esc(cfg["summary"]), keywords=esc(cfg["keywords"]),
        author=esc(cfg["author"]), category=esc(cfg["category"]),
        date_html=('<span>%s</span>' % esc(cfg["date"])) if cfg["date"] else "",
        chars="{:,}".format(chars), minutes=max(1, round(chars / 400)),
        toc=render_toc(toc), body=body, siblings="".join(sib),
        download=esc(filename.replace(" ", "%20")), filename=esc(filename),
        kind=file_kind(cfg["source"]), size=human_size(os.path.getsize(src_path)),
        jsonld=jsonld,
    )
    out = os.path.join(ROOT, "stories", slug + ".html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    return out, len(toc), chars


def main():
    order = sorted(DOCS, key=lambda d: (CATEGORY_ORDER.index(d["category"]),
                                        DOCS.index(d)))
    only = sys.argv[1:] or None
    for i, cfg in enumerate(order):
        if only and cfg["slug"] not in only:
            continue
        prev_cfg = order[i - 1] if i else None
        next_cfg = order[i + 1] if i + 1 < len(order) else None
        out, ntoc, chars = build(cfg, (prev_cfg, next_cfg))
        print("%-34s toc=%-4d chars=%-7d %s" %
              (cfg["slug"], ntoc, chars, os.path.relpath(out, ROOT)))


if __name__ == "__main__":
    main()
