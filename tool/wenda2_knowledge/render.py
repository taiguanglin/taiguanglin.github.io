#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把兩本書的資料（`src/*.py`）渲染成靜態 HTML。

輸出一本書的目錄結構（與 `wenda2_ebook/` 對齊，方便共用 `lang-switch.js`
的 `XX ↔ XX_trad` 跳轉規則）：

    wenda2_keypoints/
      index.html  index_trad.html        總目錄（每章一張卡）
      ch01.html   ch01_trad.html          …每一章
      assets/css/book.css  assets/js/book.js
      search_index.json  search_index_trad.json

繁簡策略
--------
* **編輯文字**（書名、章節標題、導言、說明、自測題）：SoT 只寫繁體，
  簡體頁由 `common.to_simplified()` 在建置時轉出。
* **師父原話**：不經轉換。簡體頁直接取語料裡對應的 `a`，
  因為它必須與 `wenda2_ebook/NN.html` 的字完全一致。

自檢（任一項不過就 exit 1 的等價效果：build_all 彙報失敗）
--------------------------------------------------------
1. 每條引文繁簡都逐字存在於 `data/corpus.json`（`common.verify_book`）。
2. 每章都帶 AI 免責聲明、lang-switch.js、canonical。
3. 站內連結（回原書的深連結）目標檔存在。
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import common
from common import (
    AI_NOTICE, BOOKS, Corpus, esc, ebook_link, pick, rich,
    source_label, to_simplified, verify_book,
)

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
ORIGIN = "https://taiguanglin.info"

# 站內相關電子書互相連結用的標籤（與 /ebook_keypoints/、/ebook_lens/ 交叉連結）
SIBLINGS = {
    "wenda2_keypoints": [
        ("/wenda2_ebook/index_trad.html", "問答錄2 原書"),
        ("/hidden/wenda2_lens/index.html", "另類讀法"),
        ("/hidden/ebook_keypoints/index.html", "十書複習・重點知識"),
    ],
    "wenda2_lens": [
        ("/wenda2_ebook/index_trad.html", "問答錄2 原書"),
        ("/hidden/wenda2_keypoints/index.html", "重點知識"),
        ("/hidden/ebook_lens/index.html", "十書複習・另一個讀法"),
    ],
}


def chapter_file(book_slug: str, num: int, trad: bool) -> str:
    return f"ch{num:02d}{'_trad' if trad else ''}.html"


def _other_page(name: str, trad: bool) -> str:
    """繁簡對應的檔名：`ch01_trad.html` ↔ `ch01.html`、`index_trad.html` ↔ `index.html``。

    注意 `_trad` 接在主檔名後、副檔名**前**——寫成 `ch01.html_trad` 是錯的。
    """
    stem, dot, ext = name.partition(".")
    if not dot:
        return name
    if stem.endswith("_trad"):
        return stem[:-5] + "." + ext
    return stem + "_trad." + ext


def head(book: dict, title: str, description: str, trad: bool, depth: str) -> str:
    slug = book["slug"]
    base = f"{ORIGIN}{common.WEB_BASE}/{slug}/"
    hreflang_alt = f"{base}{'index' if not trad else 'index_trad'}.html"
    other = f"{base}{'index' if trad else 'index_trad'}.html"
    page = f"{base}{'index' if trad else 'index_trad'}.html" if depth == "index" else f"{base}{depth}"
    return f"""<!DOCTYPE html>
<html lang="{'zh-Hant' if trad else 'zh-Hans'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>{esc(title)}｜TaiGuangLin 禪師</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{page}">
<link rel="alternate" hreflang="zh-Hant" href="{hreflang_alt if trad else other}">
<link rel="alternate" hreflang="zh-Hans" href="{other if trad else hreflang_alt}">
<link rel="alternate" hreflang="x-default" href="{other}">
<meta property="og:type" content="book">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{page}">
<meta property="og:image" content="{ORIGIN}/images/og-default.jpg">
<meta property="og:site_name" content="TaiGuangLin 禪師">
<meta name="theme-color" content="#e75480">
<link rel="icon" href="/images/favicon.ico" type="image/x-icon">
<link rel="stylesheet" href="/fonts/fonts.css">
<link rel="stylesheet" href="assets/css/book.css">
<script src="/lang-switch.js" defer></script>
<script src="assets/js/book.js" defer></script>
</head>
<body>
"""


def topbar(book: dict, trad: bool, active: str) -> str:
    slug = book["slug"]
    books = [(f"index{'_trad' if trad else ''}.html", book["title"])]
    for ch in book["chapters"]:
        books.append((chapter_file(slug, ch["num"], trad), f"第{ch['num']:02d}章 {pick(ch['title'], trad)}"))
    links = "\n".join(
        f'      <a href="{href}"{" aria-current=\"page\"" if href == active else ""}>{esc(label)}</a>'
        for href, label in books
    )
    return f"""<header class="topbar">
  <div class="topbar__in">
    <a class="topbar__home" href="/index.html">🏠 首頁</a>
    <span class="topbar__title">{esc(book['title'])}</span>
    <nav class="topbar__nav" aria-label="章節導覽">
{links}
    </nav>
  </div>
</header>
"""


def footer(book: dict, trad: bool) -> str:
    ebook = f"/wenda2_ebook/{'index_trad' if trad else 'index'}.html"
    # 姊妹頁要跟著當前語言走（`lang-switch.js` 對電子書是跳頁而非即時轉換）
    lang = "_trad" if trad else ""
    sib = " ｜ ".join(
        f'<a href="{h.replace("/index.html", "/index" + lang + ".html")}">{esc(l)}</a>'
        for h, l in SIBLINGS[book["slug"]]
    )
    return f"""<footer class="foot">
  <div class="wrap">
    <p class="foot__line">{esc(book['title'])}｜{esc(book['kind'])}｜{esc(book['audience'])}</p>
    <p class="foot__line">全書引文皆逐字取自 <a href="{ebook}">《坐禪之問答錄2》</a>，
      點擊任一引文的出處可跳回原書該則問答。</p>
    <p class="foot__line">相關閱讀：{sib} ｜
      <a href="index{lang}.html">{"簡體版" if trad else "繁體版"}</a></p>
    <p class="foot__line">本站與本站電子書內容版權屬 TaiGuangLin 禪師；本整理頁由 AI 協助編排，內容僅供複習參考。</p>
  </div>
</footer>
</body>
</html>
"""


def render_quote(corpus: Corpus, quote: dict, trad: bool,
                 default_topic: str = "師父的話") -> str:
    text = quote["at"] if trad else quote["a"]
    href = ebook_link(trad, quote["qid"])
    topic = pick(quote.get("topic") or "", trad) if quote.get("topic") else default_topic
    topic_html = f'<span class="quote__topic">{esc(topic)}</span>' if topic else ""
    return (
        f'    <figure class="quote">\n'
        f'      {topic_html}\n'
        f'      <blockquote class="quote__text">{esc(text)}</blockquote>\n'
        f'      <figcaption class="quote__src">'
        f'<span class="src-book">{esc(source_label(corpus, quote, trad))}</span>'
        f'<a href="{href}">回原書看這一問 →</a></figcaption>\n'
        f'    </figure>'
    )


def render_check(check: dict | None, trad: bool) -> str:
    if not check:
        return ""
    q = pick(check["q"], trad)
    a = pick(check["a"], trad)
    return (
        '    <div class="check">\n'
        f'      <p class="check__q">自測：{esc(q)}</p>\n'
        f'      <p class="check__a">{esc(a)}</p>\n'
        '      <button type="button" class="check__btn">看參考答案</button>\n'
        '    </div>'
    )


def section_body(section: dict, trad: bool) -> str:
    parts = "\n".join(rich(pick(p, trad)) for p in section.get("body", []))
    return parts


# --------------------------------------------------------------------------
# 章節頁
# --------------------------------------------------------------------------
def render_scene(book: dict, corpus: Corpus, ch: dict, trad: bool) -> str:
    """「另一個讀法」用的場景頁：第二人稱敘事 ＋ 師父的話 ＋ 今天可以做的一件事。"""
    slug = book["slug"]
    name = chapter_file(slug, ch["num"], trad)
    other = _other_page(name, trad)
    title = f"第{ch['num']:02d}場 {pick(ch['title'], trad)}｜{book['title']}"
    desc = (f"{book['title']}第 {ch['num']:02d} 場："
            f"{pick(ch.get('part', ''), trad)}・{pick(ch['title'], trad)}。")
    out = [head(book, title, desc, trad, name), topbar(book, trad, name)]
    out.append(f"""<main class="wrap" id="main">
  <article class="scene" id="s-scene-{ch['num']:02d}" data-anchor="top">
    <p class="scene__part">{esc(pick(ch.get('part', ''), trad))}</p>
    <h2>{esc(pick(ch['title'], trad))}</h2>
    <p class="notice"><strong>整理說明：</strong>{esc(AI_NOTICE)}
      下面這段敘事是 AI 依《問答錄2》重組的閱讀脈絡，引文則是 Tai 師父原話逐字。</p>
    <div class="narrative">
""")
    for p in ch.get("narrative", []):
        out.append(f"      <p>{esc(pick(p, trad))}</p>")
    out.append("    </div>\n")

    voices = ch.get("voices") or []
    if voices:
        out.append('    <div class="voices">')
        for v in voices:
            out.append(render_quote(corpus, v, trad, "師父的話"))
        out.append("    </div>\n")

    if ch.get("practice"):
        out.append(f'    <div class="check">\n'
                   f'      <p class="check__q">今天可以做的一件事</p>\n'
                   f'      <p class="check__a">{esc(pick(ch["practice"], trad))}</p>\n'
                   f'    </div>\n')

    prev_ch = next((c for c in book["chapters"] if c["num"] == ch["num"] - 1), None)
    next_ch = next((c for c in book["chapters"] if c["num"] == ch["num"] + 1), None)
    links = ['      <a class="backtop" href="index.html">← 回到總目錄</a>']
    if prev_ch:
        links.append(
            f'      <a class="backtop" href="{chapter_file(slug, prev_ch["num"], trad)}">'
            f'← 第{prev_ch["num"]:02d}場 {esc(pick(prev_ch["title"], trad))}</a>'
        )
    if next_ch:
        links.append(
            f'      <a class="backtop" href="{chapter_file(slug, next_ch["num"], trad)}">'
            f'第{next_ch["num"]:02d}場 {esc(pick(next_ch["title"], trad))} →</a>'
        )
    links.append(f'      <a class="backtop" href="{other}">'
                 f'{"簡體版" if trad else "繁體版"}</a>')
    out.append('    <p style="margin-top:26px">\n' + "\n".join(links) + "\n    </p>")
    out.append("  </article>\n</main>\n")
    out.append(footer(book, trad))
    return "\n".join(out)


def render_chapter(book: dict, corpus: Corpus, ch: dict, trad: bool) -> str:
    if "narrative" in ch:
        return render_scene(book, corpus, ch, trad)
    slug = book["slug"]
    name = chapter_file(slug, ch["num"], trad)
    other = _other_page(name, trad)
    title = f"第{ch['num']:02d}章 {pick(ch['title'], trad)}｜{book['title']}"
    desc = f"{book['title']}第 {ch['num']:02d} 章：{pick(ch['title'], trad)}。{pick(ch['lead'], trad)[:90]}"
    out = [head(book, title, desc, trad, name), topbar(book, trad, name)]
    out.append(f"""<main class="wrap" id="main">
  <article class="chapter" id="top">
    <p class="chapter__n">第 {ch['num']:02d} 章</p>
    <h1>{esc(pick(ch['title'], trad))}</h1>
    <p class="chapter__lead">{esc(pick(ch['lead'], trad))}</p>
    <p class="notice"><strong>整理說明：</strong>{esc(AI_NOTICE)}</p>
""")
    for sec in ch["sections"]:
        out.append(f"""    <section class="section" id="s-{esc(sec['id'])}">
      <h3>{esc(pick(sec['title'], trad))}</h3>
{section_body(sec, trad)}""")
        quotes = sec.get("quotes") or []
        if quotes:
            out.append('      <div class="quotes">')
            for q in quotes:
                out.append(render_quote(corpus, q, trad))
            out.append("      </div>")
        check = render_check(sec.get("check"), trad)
        if check:
            out.append(check)
        out.append("    </section>\n")

    nav = []
    for other_ch in book["chapters"]:
        if other_ch["num"] == ch["num"]:
            continue
        nav.append((other_ch["num"], other_ch["title"]))
    prev = next((n for n, _ in nav if n == ch["num"] - 1), None)
    nxt = next((n for n, _ in nav if n == ch["num"] + 1), None)
    links = ['      <a class="backtop" href="index.html">← 回到總目錄</a>']
    if prev:
        links.append(
            f'      <a class="backtop" href="{chapter_file(slug, prev, trad)}">← 第{prev:02d}章</a>'
        )
    if nxt:
        links.append(
            f'      <a class="backtop" href="{chapter_file(slug, nxt, trad)}">第{nxt:02d}章 →</a>'
        )
    out.append("    <p style=\"margin-top:26px\">\n" + "\n".join(links) + "\n    </p>")
    out.append(f'    <p style="margin-top:6px"><a class="backtop" href="{other}">'
               f'{"簡體版" if trad else "繁體版"}</a></p>')
    out.append("  </article>\n</main>\n")
    out.append(footer(book, trad))
    return "\n".join(out)


# --------------------------------------------------------------------------
# 總目錄頁
# --------------------------------------------------------------------------
def render_index(book: dict, corpus: Corpus, trad: bool) -> str:
    slug = book["slug"]
    name = "index_trad.html" if trad else "index.html"
    title = book["title"]
    desc = f"{book['subtitle']}。{book['kind']}：{book['audience']}。"
    unit = "場" if narrative_book(book) else "章"
    extra = "" if narrative_book(book) else f"・{count_sections(book)} 節"
    out = [head(book, title, desc, trad, "index"), topbar(book, trad, name)]
    out.append(f"""<main class="wrap wrap--wide" id="main">
  <section class="hero">
    <p class="hero__kicker">{esc(pick(book['kind'], trad))}</p>
    <h1>{esc(book['title'])}</h1>
    <p class="hero__sub">{esc(pick(book['subtitle'], trad))}</p>
    <p class="hero__meta">共 {len(book['chapters'])} {unit}{extra}
      ・{count_quotes(book)} 條師父原話
      ・繁簡切換、全文檢索、回原書深連結</p>
  </section>

  <div class="notice"><strong>整理說明：</strong>{esc(AI_NOTICE)}</div>

  <section class="search">
    <h2 style="font-size:20px;margin:0 0 10px">全文檢索這本書</h2>
    <form class="search__box" id="search-form" data-index="search_index{'_trad' if trad else ''}.json">
      <input type="search" id="search-input" placeholder="輸入關鍵字，例如：迴向、冤親債主、初禪…"
             autocomplete="off" aria-label="全文檢索">
      <button type="submit">搜尋</button>
    </form>
    <p class="search__status" id="search-status"></p>
    <ul class="search__results" id="search-results"></ul>
  </section>
""")
    for p in book.get("intro", []):
        out.append(f"  <p class=\"narrative\">{esc(pick(p, trad))}</p>")

    if book.get("routes"):
        out.append('  <h2 style="font-size:22px;margin:32px 0 12px">'
                   f'{esc(pick("閱讀路線", trad))}</h2>\n  <div class="routes">')
        for route in book["routes"]:
            steps = "\n".join(
                f'<li><a href="{chapter_file(slug, s, trad)}">'
                f'第{s:02d}{unit}'
                + (f" {esc(pick(t, trad))}" if t else "")
                + '</a></li>'
                for s, t in route["steps"]
            )
            out.append(
                f'    <div class="route">\n'
                f'      <h4>{esc(pick(route["name"], trad))}</h4>\n'
                f'      <p>{esc(pick(route["desc"], trad))}</p>\n'
                f'      <ol>{steps}</ol>\n'
                f'    </div>'
            )
        out.append("  </div>")

    out.append('  <h2 style="font-size:22px;margin:34px 0 12px">'
               f'{esc(pick("目錄" if not narrative_book(book) else "十八場", trad))}</h2>\n  <div class="toc toc--2">')
    for ch in book["chapters"]:
        head_n = f'第 {ch["num"]:02d} {unit}'
        if ch.get("part"):
            head_n = f'{esc(pick(ch["part"], trad))}・第 {ch["num"]:02d} 場'
        if narrative_book(book):
            first = next((p for p in ch.get("narrative", []) if p), "")
            desc = esc(pick(first, trad)[:72]) + "…"
            subs = ""
        else:
            desc = esc(pick(ch["lead"], trad)[:70]) + "…"
            subs = "".join(
                f'<li><a href="{chapter_file(slug, ch["num"], trad)}#s-{esc(s["id"])}">'
                f'{esc(pick(s["title"], trad))}</a></li>'
                for s in ch["sections"]
            )
            subs = f'      <ul class="toc__subs">{subs}</ul>\n'
        out.append(
            f'    <a href="{chapter_file(slug, ch["num"], trad)}">\n'
            f'      <span class="toc__n">{head_n}</span>\n'
            f'      <span class="toc__t">{esc(pick(ch["title"], trad))}</span>\n'
            f'      <span class="toc__d">{desc}</span>\n'
            f'{subs}'
            f'    </a>'
        )
    out.append("  </div>\n</main>\n")
    out.append(footer(book, trad))
    return "\n".join(out)


def narrative_book(book: dict) -> bool:
    """敘事體（另一個讀法）vs 主題體（重點知識）。"""
    return any("narrative" in ch for ch in book["chapters"])


def count_sections(book: dict) -> int:
    return sum(len(c.get("sections") or []) for c in book["chapters"])


def count_quotes(book: dict) -> int:
    n = 0
    for ch in book["chapters"]:
        n += len(ch.get("voices") or [])
        for sec in ch.get("sections") or []:
            n += len(sec.get("quotes") or [])
            n += len(sec.get("voices") or [])
    return n


# --------------------------------------------------------------------------
# 檢索索引
# --------------------------------------------------------------------------
def build_search_index(book: dict, trad: bool) -> str:
    docs = []
    unit = "場" if narrative_book(book) else "章"
    for ch in book["chapters"]:
        page = chapter_file(book["slug"], ch["num"], trad)
        docs.append({
            "h": f"第{ch['num']:02d}{unit} {pick(ch['title'], trad)}",
            "u": f"{page}#s-scene-{ch['num']:02d}" if narrative_book(book) else f"{page}#top",
            "t": pick(ch.get("lead") or (ch.get("narrative") or [""])[0], trad),
        })
        for sec in ch.get("sections") or []:
            body = " ".join(pick(p, trad) for p in sec.get("body", []))
            if body:
                docs.append({
                    "h": f"{ch['num']:02d}·{pick(sec['title'], trad)}",
                    "u": f"{page}#s-{sec['id']}",
                    "t": body,
                })
            for q in sec.get("quotes") or []:
                docs.append({
                    "h": f"{ch['num']:02d}·{pick(sec['title'], trad)}｜{pick(q.get('topic', ''), trad)}",
                    "u": f"{page}#s-{sec['id']}",
                    "t": q["at"] if trad else q["a"],
                })
            for v in sec.get("voices") or []:
                docs.append({
                    "h": f"{ch['num']:02d}·{pick(sec['title'], trad)}｜{pick(v.get('topic', ''), trad)}",
                    "u": f"{page}#s-{sec['id']}",
                    "t": v["at"] if trad else v["a"],
                })
            ck = sec.get("check")
            if ck:
                docs.append({
                    "h": f"{ch['num']:02d}·{pick(sec['title'], trad)}｜自測",
                    "u": f"{page}#s-{sec['id']}",
                    "t": pick(ck["q"], trad) + " " + pick(ck["a"], trad),
                })
        if narrative_book(book):
            narr = " ".join(pick(p, trad) for p in ch.get("narrative", []))
            if narr:
                docs.append({
                    "h": f"{ch['num']:02d}｜{pick(ch.get('part', ''), trad)}・{pick(ch['title'], trad)}",
                    "u": f"{page}#s-scene-{ch['num']:02d}",
                    "t": narr,
                })
            if ch.get("practice"):
                docs.append({
                    "h": f"{ch['num']:02d}｜今天可以做的一件事",
                    "u": f"{page}#s-scene-{ch['num']:02d}",
                    "t": pick(ch["practice"], trad),
                })
    return json.dumps({"docs": docs}, ensure_ascii=False, separators=(",", ":"))


# --------------------------------------------------------------------------
# 產出
# --------------------------------------------------------------------------
def write_book(book: dict, corpus: Corpus, outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "assets" / "css").mkdir(parents=True, exist_ok=True)
    (outdir / "assets" / "js").mkdir(parents=True, exist_ok=True)
    shutil.copy(ASSETS / "book.css", outdir / "assets" / "css" / "book.css")
    shutil.copy(ASSETS / "book.js", outdir / "assets" / "js" / "book.js")

    written = []
    for trad in (False, True):
        idx = render_index(book, corpus, trad)
        name = "index_trad.html" if trad else "index.html"
        (outdir / name).write_text(idx, encoding="utf-8")
        written.append(name)
        for ch in book["chapters"]:
            page = render_chapter(book, corpus, ch, trad)
            cname = chapter_file(book["slug"], ch["num"], trad)
            (outdir / cname).write_text(page, encoding="utf-8")
            written.append(cname)
        sname = "search_index_trad.json" if trad else "search_index.json"
        (outdir / sname).write_text(build_search_index(book, trad), encoding="utf-8")
        written.append(sname)
    return {"files": written, "outdir": outdir}


def self_check(book: dict, corpus: Corpus, outdir: Path, trad: bool) -> list[str]:
    """產出後的落地檢查。"""
    errs: list[str] = []
    name = "index_trad.html" if trad else "index.html"
    idx = (outdir / name).read_text(encoding="utf-8")
    for needle, label in (
        (AI_NOTICE, "AI 免責聲明"),
        ('/lang-switch.js', "lang-switch.js"),
        ('rel="canonical"', "canonical"),
    ):
        if needle not in idx:
            errs.append(f"{name}: 缺少{label}")
    for ch in book["chapters"]:
        page = (outdir / chapter_file(book["slug"], ch["num"], trad)).read_text(encoding="utf-8")
        if AI_NOTICE not in page:
            errs.append(f"第{ch['num']:02d}章: 缺少 AI 免責聲明")
        if narrative_book(book):
            if f'id="s-scene-{ch["num"]:02d}"' not in page:
                errs.append(f"第{ch['num']:02d}場: 錨點缺失")
        else:
            for sec in ch.get("sections") or []:
                if f'id="s-{sec["id"]}"' not in page:
                    errs.append(f"第{ch['num']:02d}章 {sec['id']}: 錨點缺失")
    # 回原書的深連結：目標章檔必須存在
    for href in set(re.findall(r'href="(/wenda2_ebook/[^"#]+)', idx)):
        if not (common.ROOT / href.lstrip("/")).exists():
            errs.append(f"{name}: 連結目標不存在 {href}")
    return errs
