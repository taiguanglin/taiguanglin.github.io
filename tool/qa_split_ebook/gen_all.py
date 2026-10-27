#!/usr/bin/env python3
"""qa_split_ebook 實驗管線 Step 4：組裝整本電子書（gen_all）

build/items.jsonl ＋ build/classified/*.jsonl（LLM 拆分＋分類產出）
→ wenda2_ebook_sep/：12 章主題樹×簡繁雙頁、總目錄、全量搜尋索引（含 .hash）、
播放鈕（讀 audio_map/ 對位，拆分子題共用母條目音段）。

獨立於線上 word2ebook 管線：只「讀」wenda2_ebook/（頁面版型與資產來源）、
tool/qa_curation/ 的樹編號（section_tree.json 於 extract 階段自
歷史底稿 wenda2_ebook/01–12.html（2026-10-26 前位於 wenda2_ebook_word/）抽得）、audio_map/（音檔映射），
並唯讀引用 tool/word2ebook/utils/i18n_utils.py 的繁化引擎。
不寫入以上任何目錄；輸出全部落在 wenda2_ebook_sep/ 與本工具目錄內。

用法：../../word_audio_map2/.venv/bin/python gen_all.py
"""
import hashlib
import html as html_mod
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tool/qa_split_ebook"
BUILD = TOOL / "build"
OUT = ROOT / "wenda2_ebook_sep"
PROD = ROOT / "wenda2_ebook"
ASSETS_SRC = PROD / "assets"
SITE = "https://taiguanglin.info/wenda2_ebook_sep"

_i18n = None


def conv(text: str, trad: bool) -> str:
    """simp 原樣；trad 走 word2ebook 的繁化引擎（唯讀引用）。"""
    global _i18n
    if not trad or not text:
        return text
    if _i18n is None:
        sys.path.insert(0, str(ROOT / "tool/word2ebook"))
        from utils.i18n_utils import I18nProcessor
        _i18n = I18nProcessor()
    return _i18n.to_traditional(text)


# --------------------------------------------------------------------------- #
# 樹                                                                           #
# --------------------------------------------------------------------------- #

class Node:
    def __init__(self, level, idx, slug, name, count0):
        self.level = level          # 2/3/4
        self.idx = idx              # 同層內 1 起算
        self.slug = slug
        self.name = name
        self.count0 = count0        # 既有（1–12 章原始）則數
        self.children = []
        self.items = []             # 組裝後的 render entries


def load_tree():
    raw = json.loads((BUILD / "section_tree.json").read_text(encoding="utf-8"))
    chapters = {}
    for ch_s, info in raw.items():
        ch = int(ch_s)
        l2s, stack = [], []
        counters = {2: 0, 3: 0, 4: 0}
        for e in info["entries"]:
            lvl = e["level"]
            counters[lvl] += 1
            for lv in (lvl + 1, lvl + 2, lvl + 3):
                if lv in counters:
                    counters[lv] = 0
            node = Node(lvl, counters[lvl], e["slug"], e["name"], e["count"])
            if lvl == 2:
                l2s.append(node)
                stack = [node]
            elif lvl == 3:
                stack[0].children.append(node)
                stack = [stack[0], node]
            elif lvl == 4:
                stack[1].children.append(node)
                stack = [stack[0], stack[1], node]
        chapters[ch] = {
            "title": info["title"], "h1_slug": info["h1_slug"],
            "total0": info["total"], "l2s": l2s,
        }
    return chapters


def resolve(chapters, ch, l2, l3, l4, warn):
    """把 (ch,l2,l3,l4) 解析到葉節點；回傳 (leaf_node, path_str) 或 (None, reason)。"""
    if ch not in chapters:
        return None, f"章無效:{ch}"
    node = None
    if not isinstance(l2, int) or l2 < 1 or l2 > len(chapters[ch]["l2s"]):
        return None, f"L2無效:{l2}"
    node = chapters[ch]["l2s"][l2 - 1]
    path = f"{ch:02d}-{l2:02d}"
    if node.children:
        if not isinstance(l3, int) or l3 < 1 or l3 > len(node.children):
            return None, f"L3無效:{l3}(L2={node.name})"
        node = node.children[l3 - 1]
        path += f"-{l3:02d}"
        if node.children:
            if not isinstance(l4, int) or l4 < 1 or l4 > len(node.children):
                return None, f"L4無效:{l4}(L3={node.name})"
            node = node.children[l4 - 1]
            path += f"-{l4:02d}"
        elif l4 is not None:
            warn(f"{path} 不含 L4 層，忽略 l4={l4}")
    else:
        if l3 is not None or l4 is not None:
            warn(f"{path} 為葉節點，忽略 l3={l3}/l4={l4}")
    return node, path


# --------------------------------------------------------------------------- #
# 分類產出載入與組裝                                                            #
# --------------------------------------------------------------------------- #

def parse_time_key(tm: str, seq: int):
    m = re.match(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", tm or "")
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), seq)
    m = re.match(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", tm or "")
    if m:
        return (int(m.group(3)), int(m.group(2)), int(m.group(1)), seq)
    return (9999, 12, 31, seq)


def load_classified():
    rows = {}   # qid -> list of row dict
    for f in sorted((BUILD / "classified").glob("batch_*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            qid = r.get("qid") or ""
            if qid:
                rows.setdefault(qid, []).append(r)
    return rows


def assemble(chapters, items, rows, report):
    """把分類行掛到樹葉；問題行入隔離區。回傳 (quarantine, stats)。"""
    quarantine = []    # {"item", "reason", "row"}
    stats = {"unsplit": 0, "split_groups": 0, "split_children": 0,
             "nr": 0, "low": 0, "warn_names": 0, "resolved": 0}

    def warn(msg):
        report["warnings"].append(msg)
        stats["warn_names"] += 1

    for it in items:
        fam = rows.get(it["qid"], [])
        fam = [r for r in fam if isinstance(r, dict)]
        if not fam:
            quarantine.append({"item": it, "reason": "批次缺漏（分類行未產出）", "row": None})
            continue
        splits = [r for r in fam if r.get("split")]
        plain = [r for r in fam if not r.get("split")]
        use = splits if splits else plain[:1]
        if splits and plain:
            warn(f"{it['qid']} 同時含拆分行與未拆行，僅採拆分行")
        if len(use) > 1 and not splits:
            warn(f"{it['qid']} 有多個未拆行，採第一行")
        if splits:
            stats["split_groups"] += 1
            subs = sorted(splits, key=lambda r: r.get("sub") or 0)
            if [r.get("sub") for r in subs] != list(range(1, len(subs) + 1)):
                quarantine.append({"item": it, "reason": "拆分行 sub 編號不連續", "row": None})
                continue
        for k, r in enumerate(use, start=1):
            leaf, path = resolve(chapters, r.get("ch"), r.get("l2"), r.get("l3"), r.get("l4"), warn)
            if leaf is None:
                quarantine.append({"item": it, "reason": f"路徑無效：{path}", "row": r})
                continue
            # 節名對帳（信賴編號，名不符僅記錄）
            node2 = chapters[r["ch"]]["l2s"][r["l2"] - 1]
            if r.get("l2n") is not None and r["l2n"] != node2.name:
                warn(f"{it['qid']} l2n={r['l2n']} ≠ 樹節名 {node2.name}（採編號）")
            if r.get("l3") and node2.children:
                node3 = node2.children[r["l3"] - 1]
                if r.get("l3n") is not None and r["l3n"] != node3.name:
                    warn(f"{it['qid']} l3n={r['l3n']} ≠ 樹節名 {node3.name}（採編號）")
                if r.get("l4") and node3.children:
                    node4 = node3.children[r["l4"] - 1]
                    if r.get("l4n") is not None and r["l4n"] != node4.name:
                        warn(f"{it['qid']} l4n={r['l4n']} ≠ 樹節名 {node4.name}（採編號）")
            suffix = f"-{k}" if splits else ""
            if splits:
                q_text, a_text = r.get("q") or "", r.get("a") or ""
                q_html = text_to_html(q_text)
                a_htmls = [text_to_html(x) for x in a_text.split("\n")] if a_text else []
            else:
                q_html = "\n".join(it["q_parts"])
                a_htmls = list(it["a_parts"])
            entry = {
                "qid": it["qid"] + suffix,
                "aid": (it["aid"] or it["qid"].replace("question-", "answer-")) + suffix,
                "who": it["who"], "time": it["time"], "seq": it["seq"],
                "q_html": q_html, "a_htmls": a_htmls,
                "q_text": (r.get("q") if splits else it["q_text"]),
                "a_text": (r.get("a") if splits else it["a_text"]),
                "audio": it["audio"], "path": path,
                "conf": r.get("conf") or "medium",
                "rule": r.get("rule") or "",
                "ru": r.get("ru"),
                "nr": bool(r.get("nr")),
                "deferred": bool(r.get("deferred")),
            }
            leaf.items.append(entry)
            if splits:
                stats["split_children"] += 1
            else:
                stats["unsplit"] += 1
            stats["resolved"] += 1
            if entry["nr"] or entry["conf"] == "low":
                stats["nr"] += 1
            if entry["conf"] == "low":
                stats["low"] += 1
    # 葉內排序：時間升冪（鐵律 5）
    for ch in chapters.values():
        for l2 in ch["l2s"]:
            for n in walk(l2):
                n.items.sort(key=lambda e: parse_time_key(e["time"], e["seq"]))
    return quarantine, stats


def walk(node):
    yield node
    for c in node.children:
        yield from walk(c)


def text_to_html(text: str) -> str:
    """LLM 切分文字 → HTML（跳行→<br/>，其餘轉義）。"""
    esc = html_mod.escape(text or "", quote=False)
    return esc.replace("\n", "<br/>")


# --------------------------------------------------------------------------- #
# 頁面渲染                                                                     #
# --------------------------------------------------------------------------- #

DARK_HEAD = """<script>
try {
  var __dm = localStorage.getItem('darkMode');
  if (__dm === null && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) __dm = 'true';
  window.__W2E_THEME_DARK = (__dm === 'true');
  window.__W2E_THEME_NEUTRAL = window.__W2E_THEME_DARK && localStorage.getItem('w2e:darkPalette') === 'neutral';
  if (window.__W2E_THEME_DARK) {
    document.documentElement.classList.add('dark-mode');
    if (window.__W2E_THEME_NEUTRAL) document.documentElement.classList.add('dark-neutral');
  }
} catch (e) {}
</script>"""

DARK_BODY = """<script>
try {
  if (window.__W2E_THEME_DARK) {
    document.body.classList.add('dark-mode');
    if (window.__W2E_THEME_NEUTRAL) document.body.classList.add('dark-neutral');
  }
} catch (e) {}
</script>"""

PLAY_BTN = ('<button aria-label="播放 {sl} - {el}" class="qa-play qa-play--inline" '
            'data-audio="{da}" data-end="{end}" data-label="{sl} - {el}" '
            'data-start="{start}" type="button"><span class="qa-play-icon">'
            '<svg aria-hidden="true" class="qa-play-speaker" focusable="false" height="1em" '
            'viewBox="0 0 24 24" width="1em"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" '
            'fill="currentColor"></path></svg></span></button>')

HEAD_TPL_CH = None   # 由 production 01.html 抽出
HEAD_TPL_IDX = None  # 由 production index.html 抽出


def load_head_templates():
    global HEAD_TPL_CH, HEAD_TPL_IDX
    ch_html = (PROD / "01.html").read_text(encoding="utf-8")
    HEAD_TPL_CH = ch_html[: ch_html.find("</head>")]
    idx_html = (PROD / "index.html").read_text(encoding="utf-8")
    HEAD_TPL_IDX = idx_html[: idx_html.find("</head>")]


def set_meta_content(t: str, attr: str, val: str) -> str:
    """把含指定屬性（name=…/property=…）的 meta 標籤的 content 換掉（屬性順序無關）。"""
    def fix(m):
        return re.sub(r'content="[^"]*"', f'content="{val}"', m.group(0), count=1)
    return re.sub(rf'<meta[^>]*{attr}="[^"]*"[^>]*>', fix, t)


def build_head(tpl, *, page, page_pair, title, desc, trad, is_index):
    canonical = f"{SITE}/{page}"
    simp = f"{SITE}/{page_pair[0]}"
    hant = f"{SITE}/{page_pair[1]}"
    t = tpl
    t = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", t, flags=re.S)
    t = set_meta_content(t, 'name="description"', desc)
    t = set_meta_content(t, 'property="og:description"', desc)
    t = set_meta_content(t, 'property="og:title"', title)
    # canonical / hreflang / og:url（兩種 head 的屬性順序不同，逐一處理）
    t = re.sub(r'href="[^"]*" rel="canonical"', f'href="{canonical}" rel="canonical"', t)
    t = re.sub(r'rel="canonical" href="[^"]*"', f'rel="canonical" href="{canonical}"', t)
    t = re.sub(r'hreflang="zh-Hant" href="[^"]*"', f'hreflang="zh-Hant" href="{hant}"', t)
    t = re.sub(r'hreflang="zh-Hans" href="[^"]*"', f'hreflang="zh-Hans" href="{simp}"', t)
    t = re.sub(r'hreflang="x-default" href="[^"]*"', f'hreflang="x-default" href="{hant}"', t)
    t = set_meta_content(t, 'property="og:url"', canonical)
    # noindex（實驗書不得被索引）
    t = t.replace("<head>", '<head>\n<meta name="robots" content="noindex, nofollow"/>', 1)
    # 語言
    t = t.replace('<html lang="zh-Hans">', '<html lang="zh-Hant">' if trad else '<html lang="zh-Hans">')
    # 實驗樣式
    t = t.replace('<link href="assets/css/style.css" rel="stylesheet"/>',
                  '<link href="assets/css/style.css" rel="stylesheet"/>\n<link href="assets/css/sep_extra.css" rel="stylesheet"/>')
    t = t.replace('<link rel="stylesheet" href="assets/css/style.css">',
                  '<link rel="stylesheet" href="assets/css/style.css">\n<link rel="stylesheet" href="assets/css/sep_extra.css">')
    return t


def chapter_toc_html(ch_node_l2s, trad, page_prefix=""):
    """章內 TOC。預設層級 3：L4 hidden、有 L4 的 L3 收合、無 L3/L4 樹自動退階。"""
    c = conv
    levels = {2}
    for l2 in ch_node_l2s:
        for n in walk(l2):
            levels.add(n.level)
    default_lv = 3 if 3 in levels else 2

    def li(node, visible_hidden_class=""):
        has_kids = bool(node.children)
        parts = [f'<li class="toc-item toc-level-{node.level}'
                 + (" toc-expandable" if has_kids else "")
                 + visible_hidden_class + f'" data-level="{node.level}">']
        if has_kids:
            expanded = node.level < default_lv
            icon = "▼" if expanded else "▶"
            btn_cls = "" if expanded else " collapsed"
            parts.append(f'<button type="button" class="toc-expand-icon{btn_cls}" '
                         f'data-level="{node.level}" aria-label="{c("展开或收合子目录", trad)}" '
                         f'aria-expanded="{str(expanded).lower()}">{icon}</button>')
        href = f'{page_prefix}#{node.slug}' if page_prefix else f'#{node.slug}'
        parts.append(f'<a href="{href}">{c(node.name, trad)}</a>')
        parts.append(f'<span class="toc-count">({count_of(node)})</span>')
        if has_kids:
            parts.append("\n<ul>")
            for k in node.children:
                hide = " hidden" if node.children and k.level > default_lv else ""
                parts.append(li(k, hide))
            parts.append("</ul>")
        parts.append("</li>")
        return "\n".join(parts)

    body = "\n".join(li(l2) for l2 in ch_node_l2s)
    buttons = "".join(
        f'<button class="toc-level-btn{" active" if lv == default_lv else ""}" '
        f'data-level="{lv}" title="{c("显示第2层" if lv == 2 else f"显示前{lv}层", trad)}">{lv}</button>'
        for lv in sorted(levels))
    return body, buttons, levels


def count_of(node):
    n = len(node.items)
    for c_ in node.children:
        n += count_of(c_)
    return n


def render_article(e, trad):
    c = conv
    q_id = e["qid"]
    a_id = e["aid"]
    flag = ""
    if e["nr"] or e["conf"] == "low":
        tip = c(f"低信心待複查：{e['rule'] or '未記錄'}", trad)
        if e["ru"]:
            tip += c(f"；第二候選：{e['ru']}", trad)
        flag = f'<span class="sep-flag" title="{html_mod.escape(tip, quote=True)}">⚑{c("复查", trad)}</span>'
    audio = e["audio"]
    play = ""
    if audio and audio.get("file") and audio.get("start") is not None and audio.get("end") is not None:
        da = "../audio/" + quote(audio["file"], safe="")
        play = PLAY_BTN.format(da=da, start=f"{audio['start']:.3f}",
                               end=f"{audio['end']:.3f}",
                               sl=audio.get("sl") or "", el=audio.get("el") or "")
    meta_time = (f'<span class="question-time">{e["time"]}</span>' if e["time"] else "")
    a_divs = "\n".join(f'<div class="answer-text">{c(h, trad)}</div>' for h in e["a_htmls"])
    return f'''<article class="qa-pair">
<div class="question" id="{q_id}">
<div class="question-meta">
<span class="questioner">{c(e["who"], trad)}</span>
{meta_time}
{flag}
</div>
<div class="question-text">{c(e["q_html"], trad)}</div>
</div>
<div class="answer" id="{a_id}">
<div class="answer-meta">
<span class="answerer">Taiguanglin</span>
{play}
</div>
{a_divs}
</div>
</article>
<hr/>'''


def chapter_page(ch, info, l2s_rendered, page, pair_page, prev, nxt, trad, search_src):
    c = conv
    total = sum(count_of(l2) for l2 in l2s_rendered)
    toc_body, buttons, levels = chapter_toc_html(l2s_rendered, trad)
    prev_link = (f'<a href="{prev["page"]}">⬅️ {c(prev["label"], trad)}</a>' if prev else "")
    next_link = (f'<a href="{nxt["page"]}">{c(nxt["label"], trad)} ➡️</a>' if nxt else "")
    head = build_head(HEAD_TPL_CH, page=page, page_pair=(page, pair_page),
                      title=c(f"{ch:02d}{info['title']}・坐禅之问答录2·分类实验版｜TaiGuangLin 禅师", trad),
                      desc=c(f"《坐禅之问答录2·分类实验版》{ch:02d}{info['title']}——2025年6月起的月度答疑按既有12章主题树拆分分类重组，全文可检索、支持简繁切换。", trad),
                      trad=trad, is_index=False)
    lang_link_text = "简体" if trad else "繁體"
    out = [head, "\n</head>\n", DARK_BODY, '\n<div id="top"></div>\n<header class="header-nav">\n<nav aria-label="站內導覽" class="nav-home">\n<a href="index.html">📖 ', c("问答录2总目录·实验版", trad), '</a>\n</nav>\n<div class="lang-switch">\n<a href="', pair_page, '">', lang_link_text, '</a>\n</div>\n</header>\n<div class="top-nav">\n<div class="top-nav-buttons">', prev_link, next_link, '</div>\n</div>\n<main>\n<h1 id="', info["h1_slug"], '">', c(f"{ch:02d}{info['title']}", trad), f'<span class="chapter-qa-count">({total})</span></h1>\n<!-- 章節TOC -->\n<div class="toc-header-container">\n<h2 id="chapter-toc-header">', c("本章目录", trad), '</h2>\n<div class="toc-level-controls">\n<div class="toc-level-label">', c("显示层级", trad), '</div>\n<div class="toc-level-buttons-vertical">', buttons, '</div>\n</div>\n</div>\n<div class="toc" id="chapter-toc">\n<ul>\n', toc_body, '\n</ul>\n</div>\n']
    # 內容
    def sec(node):
        tag = f"h{node.level}"
        parts = [f'<{tag} id="{node.slug}">{c(node.name, trad)}<span class="chapter-qa-count">({count_of(node)})</span></{tag}>']
        for e in node.items:
            parts.append(render_article(e, trad))
        for k in node.children:
            parts.append(sec(k))
        return "\n".join(parts)
    for l2 in l2s_rendered:
        out.append("\n" + sec(l2))
    out.append(f'\n<div class="back-to-top"><a href="#top">🔝 {c("回到本章目录", trad)}</a></div>\n<div class="nav-footer">\n{prev_link}{next_link}</div>\n</main>\n</body>\n</html>\n')
    return "".join(out), total


# --------------------------------------------------------------------------- #
# index（總目錄）                                                               #
# --------------------------------------------------------------------------- #

def build_index(pre_toc, post_toc, chapter_infos, trad):
    """chapter_infos: [{ch, label, page, total, l2s}]（僅非空章，含 99）。"""
    c = conv
    pieces = []
    for i, info in enumerate(chapter_infos):
        expand_btn = ('<button type="button" class="toc-expand-icon" data-level="1" '
                      f'aria-label="{c("展开或收合子目录", trad)}" aria-expanded="true">▼</button>')
        pieces.append(f'<li class="toc-item toc-chapter toc-expandable" data-level="1" '
                      f'data-chapter="{info["ch"] - 1}">{expand_btn}'
                      f'<a href="{info["page"]}">{c(info["label"], trad)}</a>'
                      f'<span class="toc-count">({info["total"]})</span>')
        if info["l2s"]:
            pieces.append("\n<ul>")
            for l2 in info["l2s"]:
                has_kids = bool(l2.children)
                btn = (f'<button type="button" class="toc-expand-icon collapsed" data-level="2" '
                       f'aria-label="{c("展开或收合子目录", trad)}" aria-expanded="false">▶</button>'
                       if has_kids else "")
                pieces.append(f'<li class="toc-item toc-level-2{" toc-expandable" if has_kids else ""}" '
                              f'data-level="2" data-chapter="{info["ch"] - 1}">{btn}'
                              f'<a href="{info["page"]}#{l2.slug}">{c(l2.name, trad)}</a>'
                              f'<span class="toc-count">({count_of(l2)})</span>')
                if has_kids:
                    pieces.append("\n<ul>")
                    for n3 in l2.children:
                        kids3 = bool(n3.children)
                        btn3 = (f'<button type="button" class="toc-expand-icon collapsed" data-level="3" '
                                f'aria-label="{c("展开或收合子目录", trad)}" aria-expanded="false">▶</button>'
                                if kids3 else "")
                        pieces.append(f'<li class="toc-item toc-level-3{" toc-expandable" if kids3 else ""} hidden" '
                                      f'data-level="3" data-chapter="{info["ch"] - 1}">{btn3}'
                                      f'<a href="{info["page"]}#{n3.slug}">{c(n3.name, trad)}</a>'
                                      f'<span class="toc-count">({count_of(n3)})</span>')
                        if kids3:
                            pieces.append("\n<ul>")
                            for n4 in n3.children:
                                pieces.append(f'<li class="toc-item toc-level-4 hidden" data-level="4" '
                                              f'data-chapter="{info["ch"] - 1}">'
                                              f'<a href="{info["page"]}#{n4.slug}">{c(n4.name, trad)}</a>'
                                              f'<span class="toc-count">({len(n4.items)})</span></li>')
                            pieces.append("</ul>")
                        pieces.append("</li>")
                    pieces.append("</ul>")
                pieces.append("</li>")
            pieces.append("</ul>")
        pieces.append("</li>")
    toc = "\n".join(pieces)
    note = c("本書為實驗重組版：2025年6月起的月度答疑（原 13–21 章，3,452 則）經 LLM"
             "拆分子問題並依既有 12 章主題樹分類；⚑復查＝低信心條目待人工複查；"
             "99 章＝未歸類收容。內容以原書為準。", trad)
    pre = pre_toc.replace(
        "<h1>坐禅之问答录2</h1>",
        f'<h1>{c("坐禅之问答录2", trad)}·{c("分类实验版", trad)}</h1>\n'
        f'<div class="sep-note">{note}</div>')
    if trad:
        pre = c(pre, True)
    return pre + '<div class="toc" id="main-toc">\n<ul class=\'toc-level-1\'>\n' + toc + "\n</ul>\n</div>\n</main>\n" + post_toc


# --------------------------------------------------------------------------- #
# 搜尋索引                                                                     #
# --------------------------------------------------------------------------- #

def build_search_index(pages_entries):
    """pages_entries: [(page, trad, h1_label, h1_slug, l2s, entries)] → list[dict]。"""
    out = []
    for page, trad, h1_label, h1_slug, l2s, entries in pages_entries:
        n = 0

        def add(title, typ, content, url):
            nonlocal n
            out.append({"id": f"{page}-{n}", "title": conv(title, trad),
                        "type": typ, "content": conv(content, trad), "url": url})
            n += 1
        add(f"{h1_label}({len(entries)})", "heading",
            f"{h1_label}({len(entries)})", f"{page}#{h1_slug}")
        # 依文件順序：節標題→條目
        for l2 in l2s:
            for node in walk(l2):
                add(f"{node.name}({count_of(node)})", "heading",
                    f"{node.name}({count_of(node)})", f"{page}#{node.slug}")
        for e in entries:
            q_url = f"{page}#{e['qid']}"
            a_url = f"{page}#{e['aid']}"
            add(f"{e['who']} | {e['time']}", "question",
                f"{e['who']} {e['time']} {e['q_text']}", q_url)
            add(f"Tai师父的回答 | {e['time']}", "answer", e["a_text"], a_url)
    return out


def write_search(idx, filename):
    content = json.dumps(idx, ensure_ascii=False, indent=2)
    (OUT / filename).write_text(content, encoding="utf-8")
    b = content.encode("utf-8")
    (OUT / f"{filename}.hash").write_text(json.dumps(
        {"hash": hashlib.md5(b).hexdigest(), "algorithm": "md5", "size": len(b)},
        ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# 主流程                                                                       #
# --------------------------------------------------------------------------- #

def main():
    load_head_templates()
    chapters = load_tree()
    items = [json.loads(l) for l in (BUILD / "items.jsonl").read_text(encoding="utf-8").splitlines()]

    # 補充日期：items.jsonl 中 time 為空的條目，從音頻映射推導的日期表補上
    _ds_file = ROOT / "tool/word2ebook" / "data" / "audio_dates_supplement.json"
    try:
        _ds = json.loads(_ds_file.read_text(encoding="utf-8")).get("dates", {})
    except (FileNotFoundError, json.JSONDecodeError):
        _ds = {}
    _supplemented = 0
    for it in items:
        if not it.get("time"):
            qid = it.get("qid", "")
            # 拆分子題的母 qid（剝 -N 後綴）也能找到補充日期
            base_qid = qid.rsplit("-", 1)[0] if qid.rsplit("-", 1)[-1].isdigit() else qid
            date = _ds.get(qid, "") or _ds.get(base_qid, "")
            if date:
                it["time"] = date
                _supplemented += 1
    if _supplemented:
        print(f"[gen] 日期補充：{_supplemented} 則從音頻映射補上日期")

    rows = load_classified()
    report = {"warnings": []}
    quarantine, stats = assemble(chapters, items, rows, report)

    # 隔離章（99）
    q_nodes = []
    if quarantine:
        groups = {}
        for q in quarantine:
            groups.setdefault(q["reason"], []).append(q)
        for reason, qs in groups.items():
            slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"[（）()：:／/]", "", reason)
                          .lower().replace("路徑無效", "bad-path").replace("批次缺漏", "missing")).strip("-")[:40]
            node = Node(2, len(groups), slug or f"g{len(groups)}",
                        f"{reason}（{len(qs)}）", 0)
            for q in qs:
                it = q["item"]
                node.items.append({
                    "qid": it["qid"], "aid": it["aid"], "who": it["who"], "time": it["time"],
                    "seq": it["seq"], "q_html": "\n".join(it["q_parts"]),
                    "a_htmls": list(it["a_parts"]), "q_text": it["q_text"], "a_text": it["a_text"],
                    "audio": it["audio"], "path": "99", "conf": "low",
                    "rule": reason, "ru": None, "nr": True, "deferred": False,
                })
            node.items.sort(key=lambda e: parse_time_key(e["time"], e["seq"]))
            q_nodes.append(node)
    q_info = {"title": "未归类复查", "h1_slug": "99-wei-gui-lei-fu-cha", "total0": 0}
    q_l2s = q_nodes

    # 輸出目錄重建
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ASSETS_SRC, OUT / "assets", dirs_exist_ok=True)
    shutil.copyfile(PROD / "favicon.ico", OUT / "favicon.ico")
    (OUT / "assets/css/sep_extra.css").write_text(CSS_EXTRA, encoding="utf-8")

    # 非空章清單（含 99）
    active = []
    for ch in sorted(chapters):
        l2s = [l2 for l2 in chapters[ch]["l2s"] if count_of(l2) > 0]
        if l2s:
            active.append({"ch": ch, "info": chapters[ch], "l2s": l2s,
                            "page": f"{ch:02d}.html",
                            "label": f"{ch:02d}{chapters[ch]['title']}"})
    if q_l2s:
        total_q = sum(count_of(n) for n in q_l2s)
        active.append({"ch": 99, "info": q_info, "l2s": q_l2s, "page": "99.html",
                       "label": f"99{q_info['title']}"})

    # 章頁（簡繁）
    search_pages = []
    for i, a in enumerate(active):
        ch, info, l2s = a["ch"], a["info"], a["l2s"]
        page = a["page"]
        pair = page.replace(".html", "_trad.html") if not page.endswith("_trad.html") else page.replace("_trad.html", ".html")
        prev = active[i - 1] if i > 0 else None
        nxt = active[i + 1] if i < len(active) - 1 else None
        # 簡體
        simp, total = chapter_page(ch, info, l2s, page, page.replace(".html", "_trad.html"),
                                   prev, nxt, False, None)
        (OUT / page).write_text(simp, encoding="utf-8")
        # 繁體：頁內連結指向繁體頁
        def t_nav(n):
            return dict(n, page=n["page"].replace(".html", "_trad.html")) if n else None
        trad, _ = chapter_page(ch, info, l2s, page.replace(".html", "_trad.html"), page,
                               t_nav(prev), t_nav(nxt), True, None)
        (OUT / (page.replace(".html", "_trad.html"))).write_text(trad, encoding="utf-8")
        entries = [e for l2 in l2s for e in
                   [it for n in walk(l2) for it in n.items]]
        search_pages.append((page, False, a["label"], a["info"]["h1_slug"], l2s, entries))
        search_pages.append((page.replace(".html", "_trad.html"), True, a["label"],
                             a["info"]["h1_slug"], l2s, entries))
        print(f"[gen] {page}: {total} 則")

    # index（簡繁）：body_pre＝<body> 到 <main> 之間的導覽區塊（生產版原樣取用）
    idx_html = (PROD / "index.html").read_text(encoding="utf-8")
    body_pre = idx_html[idx_html.find("<body>"): idx_html.find("<main>")]
    pre_toc = idx_html[idx_html.find("<main>") + len("<main>"): idx_html.find('<div class="toc" id="main-toc">')]
    post_marker = "<!-- 滚动时显示的浮动层级控制按钮 -->"
    post_toc = idx_html[idx_html.find(post_marker):]

    def idx_infos(trad_pages):
        out = []
        for a in active:
            page = (a["page"].replace(".html", "_trad.html") if trad_pages else a["page"])
            out.append({"ch": a["ch"], "label": a["label"], "page": page,
                        "total": sum(count_of(l2) for l2 in a["l2s"]), "l2s": a["l2s"]})
        return out

    simp_idx_head = build_head(HEAD_TPL_IDX, page="index.html", page_pair=("index.html", "index_trad.html"),
                               title="坐禅之问答录2·分类实验版｜TaiGuangLin 禅师",
                               desc="TaiGuangLin 禅师《坐禅之问答录2》分类实验版：2025年6月起的月度答疑按既有12章主题树拆分分类重组，支持全文检索与简繁切换。",
                               trad=False, is_index=True)
    trad_idx_head = build_head(HEAD_TPL_IDX, page="index_trad.html", page_pair=("index.html", "index_trad.html"),
                               title=conv("坐禅之问答录2·分类实验版｜TaiGuangLin 禅师", True),
                               desc=conv("TaiGuangLin 禅师《坐禅之问答录2》分类实验版：2025年6月起的月度答疑按既有12章主题树拆分分类重组，支持全文检索与简繁切换。", True),
                               trad=True, is_index=True)
    simp_idx = simp_idx_head + "\n</head>\n" + body_pre + build_index(pre_toc, post_toc, idx_infos(False), False)
    trad_idx = trad_idx_head + "\n</head>\n" + conv(body_pre, True) + build_index(pre_toc, post_toc, idx_infos(True), True)
    # index 的 lang-switch 修正（body_pre 內含）
    trad_idx = trad_idx.replace('<a href="index_trad.html">繁體</a>', '<a href="index.html">简体</a>')
    (OUT / "index.html").write_text(simp_idx, encoding="utf-8")
    (OUT / "index_trad.html").write_text(trad_idx, encoding="utf-8")

    # 搜尋索引（簡體索引只含簡體頁、繁體索引只含繁體頁）
    write_search(build_search_index([p for p in search_pages if not p[1]]), "search_index.json")
    write_search(build_search_index([p for p in search_pages if p[1]]), "search_index_trad.json")

    # 報告
    write_report(chapters, items, rows, quarantine, stats, report, active)
    # 分類產出歸檔（供複查／進版控）
    cls_dir = TOOL / "classified"
    if cls_dir.exists():
        shutil.rmtree(cls_dir)
    if (BUILD / "classified").exists():
        shutil.copytree(BUILD / "classified", cls_dir)
    print(f"[gen] 完成 → {OUT}（隔離 {len(quarantine)} 則）")


CSS_EXTRA = """.sep-flag{margin-left:.45em;color:#c0392b;font-size:.8em;cursor:help;
border:1px solid currentColor;border-radius:4px;padding:0 .3em;white-space:nowrap;}
.sep-note{margin:0 0 1.2em;padding:.8em 1em;border-left:4px solid #e75480;
background:rgba(231,84,128,.08);font-size:.95em;border-radius:4px;line-height:1.6;}
"""


def write_report(chapters, items, rows, quarantine, stats, report, active):
    lines = ["# qa_split_ebook 組裝報告\n"]
    lines.append(f"- 輸入：{len(items)} 則（wenda2_ebook 13–21）")
    lines.append(f"- 分類行：{stats['resolved']}（未拆 {stats['unsplit']}／拆分組 {stats['split_groups']} → 子題 {stats['split_children']}）")
    lines.append(f"- needs_review＋low：{stats['nr']}（low {stats['low']}）")
    lines.append(f"- 隔離：{len(quarantine)} 則")
    lines.append(f"- 名稱對帳警告：{stats['warn_names']}（明細見 warnings 區）\n")
    lines.append("## 各章分布（新則數 vs 既有則數）\n")
    lines.append("| 章 | 標題 | 新 | 既有 |")
    lines.append("|---|---|---:|---:|")
    for ch in sorted(chapters):
        n = sum(count_of(l2) for l2 in chapters[ch]["l2s"])
        lines.append(f"| {ch:02d} | {chapters[ch]['title']} | {n} | {chapters[ch]['total0']} |")
    lines.append("\n## 空節（既有樹中未收到任何新條目的節）\n")
    empty = []
    for ch in sorted(chapters):
        for l2 in chapters[ch]["l2s"]:
            for n in walk(l2):
                if not n.children and not n.items:
                    empty.append(f"{ch:02d} {n.name}")
    lines.append(f"共 {len(empty)} 個空葉節" + ("：" if empty else "。"))
    if empty:
        lines.append("、".join(empty))
    if report["warnings"]:
        lines.append("\n## 對帳警告\n")
        for w in report["warnings"][:200]:
            lines.append(f"- {w}")
        if len(report["warnings"]) > 200:
            lines.append(f"- …共 {len(report['warnings'])} 條")
    if quarantine:
        lines.append("\n## 隔離清單\n")
        for q in quarantine[:300]:
            lines.append(f"- {q['item']['qid']}（{q['item']['who']} {q['item']['time']}）：{q['reason']}")
    (BUILD / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[gen] 報告 → {BUILD/'report.md'}")


if __name__ == "__main__":
    main()
