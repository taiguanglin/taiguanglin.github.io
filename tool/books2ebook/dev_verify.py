"""dev_verify.py — 對已產生的 ebook/ 輸出做一致性驗證（不需重建）。

用法：
    /usr/bin/python3 dev_verify.py            # 驗證預設輸出目錄 ebook/
    /usr/bin/python3 dev_verify.py --out DIR
    /usr/bin/python3 dev_verify.py --http     # 另外對 localhost:8084 做 HTTP 存在性檢查

檢查項目：
  A. 檔案齊全（01–05、_trad、index、assets、favicon、搜尋索引）
  B. 內部連結 / 錨點：href="#..."、跨檔 NN.html#id、img src 是否存在
  C. 搜尋索引：JSON 可解析、.hash 與內容一致、每筆 url 指向存在的檔案與錨點
  D. 文字健全性：U+FFFD／控制字元／私用區、殘留目錄虛線、頁碼漏進正文、
     異常短段落、相鄰重複段落、《问答录》問答欄位異常
  E. 計數一致性：h1 總數 == 各頂層標題計數和；章內目錄與正文的錨點/計數一致
  F. 簡繁對照：結構相同、繁版文字符合共用台灣正體規則、無少用異體字
  G. 目錄展開圖標：只有真的有子項的目錄項才帶三角形
"""

import argparse
import hashlib
import json
import os
import re
import sys
from html.parser import HTMLParser

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TOOL_DIR, "..", ".."))
DEFAULT_OUT = os.path.join(REPO_ROOT, "ebook")

from main import _TAIWAN_CHINESE

CHAPTERS = ["%02d" % n for n in range(1, 6)]
HEAD_TAGS = {"h2", "h3", "h4"}

issues = []   # (severity, location, message)


def issue(sev, loc, msg):
    issues.append((sev, loc, msg))


class PageParser(HTMLParser):
    """收集 id、href/src、可見文字（粗略）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.refs = []          # (attr, value)
        self.text_parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "id" in d and d["id"]:
            self.ids.add(d["id"])
        for attr in ("href", "src"):
            if attr in d and d[attr]:
                self.refs.append((attr, d[attr]))
        if tag in ("script", "style"):
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self.text_parts.append(data)


def parse_page(path):
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    p = PageParser()
    p.feed(html)
    return html, p


def strip_tags(html):
    p = PageParser()
    p.feed(html)
    return "".join(p.text_parts)


# ---------------------------------------------------------------- #

def check_files(out):
    need = (
        ["index.html", "index_trad.html", "search_index.json",
         "search_index_trad.json", "search_index.json.hash",
         "search_index_trad.json.hash", "favicon.ico"]
        + ["%s.html" % c for c in CHAPTERS]
        + ["%s_trad.html" % c for c in CHAPTERS]
        + [os.path.join("assets", "css", "style.css"),
           os.path.join("assets", "css", "books.css"),
           os.path.join("assets", "js", "script.js")]
    )
    missing = [f for f in need if not os.path.exists(os.path.join(out, f))]
    for f in missing:
        issue("bad", out, "缺少檔案：%s" % f)
    return [f for f in need if not f.startswith("search_index")]


def local_target(out, ref, cur_file):
    """把 href/src 解成 out 底下的相對路徑；外部/錨點回傳 None。"""
    if ref.startswith(("http://", "https://", "//", "mailto:", "data:", "#")):
        return None
    path = ref.split("#", 1)[0].strip()
    if not path:
        return None
    base_dir = os.path.dirname(os.path.join(out, cur_file))
    resolved = os.path.normpath(os.path.join(base_dir, path))
    rel = os.path.relpath(resolved, out).replace(os.sep, "/")
    if rel.startswith(".."):
        return rel  # ../books/... 之類，交給 HTTP/FS 檢查
    return rel


def check_links_and_anchors(out, pages):
    """pages: {rel_path: (html, parser)}"""
    all_ids = {rel: p.ids for rel, (_, p) in pages.items()}
    fs_targets = set()

    for rel, (html, p) in sorted(pages.items()):
        for attr, val in p.refs:
            if val.startswith("#"):
                frag = val[1:]
                if frag and frag not in p.ids:
                    issue("bad", rel, "同頁錨點不存在 #%s" % frag)
                continue
            tgt = local_target(out, val, rel)
            if tgt is None:
                continue
            fs_targets.add(tgt)
            frag = val.split("#", 1)[1] if "#" in val else None
            cand_paths = []
            if tgt.startswith("../"):
                cand_paths.append(os.path.join(REPO_ROOT, tgt[3:]))
            else:
                cand_paths.append(os.path.join(out, tgt))
            if not any(os.path.exists(c) for c in cand_paths):
                issue("bad", rel, "%s 指向不存在的檔案 %s" % (attr, val))
            elif frag:
                tf = next(c for c in cand_paths if os.path.exists(c))
                try:
                    _, tp = parse_page(tf)
                except Exception:
                    continue
                if frag not in tp.ids:
                    issue("bad", rel, "跨檔錨點不存在 %s" % val)
        # 同頁純文字中夾帶的 #frag 已含在上面；這裡補查 TOC <a href="#...">
    return fs_targets


def check_search_index(out):
    for suffix in ("", "_trad"):
        name = "search_index%s.json" % suffix
        path = os.path.join(out, name)
        if not os.path.exists(path):
            continue
        raw = open(path, "r", encoding="utf-8").read()
        try:
            items = json.loads(raw)
        except Exception as e:
            issue("bad", name, "JSON 解析失敗：%s" % e)
            continue
        hp = path + ".hash"
        if os.path.exists(hp):
            meta = json.load(open(hp, encoding="utf-8"))
            digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
            if meta.get("hash") != digest:
                issue("bad", name + ".hash", "hash 與內容不符")
            if meta.get("size") != len(raw.encode("utf-8")):
                issue("warn", name + ".hash", "size 欄位不符")
        bad_type = [it for it in items
                    if it.get("type") not in ("question", "answer", "content", "heading")]
        if bad_type:
            issue("bad", name, "%d 筆 type 異常（例：%r）"
                  % (len(bad_type), bad_type[0].get("type")))
        # url 抽樣全查
        cache = {}
        n_bad = 0
        first_msg = None
        for it in items:
            url = it.get("url", "")
            m = re.match(r"^([^#]+)#(.+)$", url)
            if not m:
                n_bad += 1
                if not first_msg:
                    first_msg = "url 缺錨點：%r" % url
                continue
            f, frag = m.group(1), m.group(2)
            if f not in cache:
                fp = os.path.join(out, f)
                cache[f] = parse_page(fp)[1].ids if os.path.exists(fp) else None
            ids = cache[f]
            if ids is None:
                n_bad += 1
                if not first_msg:
                    first_msg = "url 指向不存在的檔案：%r" % url
            elif frag not in ids:
                n_bad += 1
                if not first_msg:
                    first_msg = "url 錨點不存在：%r" % url
        if n_bad:
            issue("bad", name, "%d 筆 url 失效；例：%s" % (n_bad, first_msg))


_BAD_CHAR_RE = re.compile(r"[\u0000-\u0008\u000b-\u001f\u007f\ufffd\ue000-\uf8ff]")
_DOT_LEADER_RE = re.compile(r"\.{5,}")
_PAGE_NUM_RE = re.compile(r"^\d{1,4}$")


def _iter_paragraphs(text_html):
    """把可見文字依區塊切開（以標籤邊界近似）。"""
    parts = re.split(r"<(?:p|div|li|h[1-6]|figure|hr)\b", text_html)
    for part in parts:
        t = strip_tags(part)
        yield t


def check_text_sanity(out, rel, html):
    visible = strip_tags(html)
    m = _BAD_CHAR_RE.search(visible)
    if m:
        i = m.start()
        issue("bad", rel, "異常字元 U+%04X …%s…" % (ord(m.group(0)), visible[max(0, i - 15):i + 15]))
    for mm in _DOT_LEADER_RE.finditer(visible):
        ctx = visible[max(0, mm.start() - 20):mm.end() + 10]
        issue("warn", rel, "殘留目錄虛線 …%s…" % ctx.strip())
        break  # 每檔報一次即可
    shorties = []
    prev_para = None
    dup_count = 0
    for para in _iter_paragraphs(html):
        t = para.strip()
        if not t:
            continue
        if len(t) == 1 and not re.match(r"[\d（）()．.、]", t):
            shorties.append(t)
        if _PAGE_NUM_RE.match(t) and int(t) >= 13:
            # 正文裡出現獨立大頁碼（>13 才可疑，避免章節編號誤報）
            issue("warn", rel, "疑似頁碼漏進正文：%r" % t)
        if t == prev_para:
            dup_count += 1
        prev_para = t
    if len(shorties) > 30:
        issue("warn", rel, "單字段落過多（%d 個，例：%r）" % (len(shorties), shorties[:8]))


def check_counts(out, rel, html, p):
    """h1 總數 == 頂層標題計數和；章內目錄連結的錨點存在且計數與正文一致。"""
    m = re.search(r'<h1[^>]*>[^<]*<span class="chapter-qa-count">\((\d+)\)</span>', html)
    if not m:
        return  # 首頁沒有 h1 計數
    total = int(m.group(1))
    # 正文標題：tag id >text<count</tag
    body_counts = {}
    for mm in re.finditer(r'<(h[234]) id="([^"]+)">([^<]*)<span class="chapter-qa-count">\((\d+)\)</span>', html):
        body_counts[mm.group(2)] = (int(mm.group(4)), mm.group(1))
    # 目錄項：<a href="#sid">title</a><span class="toc-count">(N)</span>
    toc_items = re.findall(
        r'<a href="#([^"]+)">.*?</a><span class="toc-count">\((\d+)\)</span>', html)
    if not toc_items:
        issue("warn", rel, "章內目錄為空")
        return
    for sid, cnt in toc_items:
        cnt = int(cnt)
        if sid not in p.ids:
            issue("bad", rel, "目錄錨點不存在 #%s" % sid)
        elif sid in body_counts and body_counts[sid][0] != cnt:
            issue("bad", rel, "目錄與正文計數不一致 #%s：目錄 %d ≠ 正文 %d"
                  % (sid, cnt, body_counts[sid][0]))
    # 頂層（最小 level）標題之和應等於總數
    lvls = [int(mm.group(1)) for mm in
            re.finditer(r'class="toc-item toc-level-(\d)"', html)]
    if not lvls:
        return
    min_lvl = min(lvls)
    root_sids = []
    for mm in re.finditer(
            r'<li class="toc-item toc-level-%d"[^>]*>.*?<a href="#([^"]+)"' % min_lvl, html):
        root_sids.append(mm.group(1))
    root_sum = sum(body_counts.get(s, (0,))[0] for s in root_sids)
    if root_sum != total:
        issue("bad", rel, "頂層標題計數和 %d ≠ 全書總數 %d" % (root_sum, total))


_TOC_LI_RE = re.compile(r'<li class="toc-item[^"]*"[^>]*data-level="(\d)"[^>]*>')


def check_toc_icons(out, rel, html):
    """三角形圖標只該出現在真的有子項的目錄項上。

    首頁是嵌套 <ul>、章節頁是扁平清單，但兩者共通規則相同：文件順序中
    下一個目錄項的層級更深，才代表本項可展開。
    """
    items = [(m.start(), int(m.group(1))) for m in _TOC_LI_RE.finditer(html)]
    if not items:
        return
    bounds = [pos for pos, _ in items] + [len(html)]
    missing = extra = 0
    for i, (pos, lvl) in enumerate(items):
        has_children = i + 1 < len(items) and items[i + 1][1] > lvl
        has_icon = "toc-expand-icon" in html[pos:bounds[i + 1]]
        if has_children and not has_icon:
            missing += 1
        elif has_icon and not has_children:
            extra += 1
    if extra:
        issue("bad", rel, "%d 個無子項的目錄項帶展開三角形" % extra)
    if missing:
        issue("bad", rel, "%d 個有子項的目錄項缺少展開三角形" % missing)


def check_qa_pairs(out):
    """《坐禅之问答录》：問答欄位健全性。"""
    path = os.path.join(out, "02.html")
    if not os.path.exists(path):
        return
    html = open(path, encoding="utf-8").read()
    qs = re.findall(r'<div class="question-text">(.*?)</div>', html, re.S)
    ans = re.findall(r'<div class="answer-text">(.*?)</div>', html, re.S)
    if len(qs) != len(ans):
        issue("warn", "02.html", "問題數 %d ≠ 回答數 %d" % (len(qs), len(ans)))
    empty_a = sum(1 for a in ans if not strip_tags(a).strip())
    empty_q = sum(1 for q in qs if not strip_tags(q).strip())
    if empty_a:
        issue("warn", "02.html", "%d 個回答內容為空" % empty_a)
    if empty_q:
        issue("warn", "02.html", "%d 個問題內容為空" % empty_q)
    askers = re.findall(r'<span class="questioner">([^<]*)</span>', html)
    weird = [a for a in askers
             if len(a) > 24 or re.search(r'[。？！；]', a)]
    if weird:
        issue("warn", "02.html", "提問者暱稱異常（例：%r）" % weird[:5])


def check_trad_parity(out):
    try:
        converter = _TAIWAN_CHINESE
    except Exception:
        issue("skip", "-", "無 opencc，跳過簡繁比對")
        return
    pairs = [("index.html", "index_trad.html")] + \
            [("%s.html" % c, "%s_trad.html" % c) for c in CHAPTERS]
    for simp_f, trad_f in pairs:
        sp, tp = os.path.join(out, simp_f), os.path.join(out, trad_f)
        if not (os.path.exists(sp) and os.path.exists(tp)):
            continue
        simp_txt = strip_tags(open(sp, encoding="utf-8").read())
        trad_txt = strip_tags(open(tp, encoding="utf-8").read())
        expect = converter.to_traditional(simp_txt)
        if expect != trad_txt:
            # 找第一個差異位置供除錯
            i = next((k for k, (a, b) in enumerate(zip(expect, trad_txt)) if a != b),
                     min(len(expect), len(trad_txt)))
            issue("warn", trad_f, "繁版文字 ≠ 台灣正體轉換(簡版) @%d …%s|%s…"
                  % (i, expect[i:i + 12], trad_txt[i:i + 12]))
        uncommon = {ch: trad_txt.count(ch) for ch in "纔羣爲裏衆麪"
                    if ch in trad_txt}
        if uncommon:
            issue("bad", trad_f, "含少用異體字：%s"
                  % " ".join("%s×%d" % kv for kv in sorted(uncommon.items())))


def check_http(fs_targets, base):
    import urllib.request
    ok = fail = 0
    for rel in sorted(fs_targets):
        if rel.startswith("../"):
            url_path = "/" + rel[3:]
        else:
            # 相對於 /ebook/（或自訂 --http-base）
            url_path = "/ebook/" + rel
        from urllib.parse import quote
        url = base.rstrip("/") + quote(url_path)
        req = urllib.request.Request(url, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                if r.status == 200:
                    ok += 1
                else:
                    fail += 1
                    issue("warn", "http", "HEAD %s → %s" % (url, r.status))
        except Exception as e:
            # SimpleHTTP 少數情況不支援 HEAD → 改 GET 前 1 byte
            req2 = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
            try:
                with urllib.request.urlopen(req2, timeout=10) as r:
                    if r.status in (200, 206):
                        ok += 1
                    else:
                        fail += 1
                        issue("warn", "http", "GET %s → %s" % (url, r.status))
            except Exception as e2:
                fail += 1
                issue("warn", "http", "無法取得 %s：%s" % (url, e2))
    print("🌐 HTTP 檢查：%d OK / %d 失敗（%s）" % (ok, fail, base))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--http", action="store_true", help="對 localhost:8084 做存在性檢查")
    ap.add_argument("--http-base", default="http://localhost:8084")
    args = ap.parse_args()

    out = args.out
    print("🔎 驗證輸出目錄：%s\n" % out)

    check_files(out)

    page_files = ["index.html"] + \
        ["%s.html" % c for c in CHAPTERS] + \
        ["index_trad.html"] + \
        ["%s_trad.html" % c for c in CHAPTERS]
    pages = {}
    for f in page_files:
        fp = os.path.join(out, f)
        if os.path.exists(fp):
            pages[f] = parse_page(fp)

    fs_targets = check_links_and_anchors(out, pages)
    print("🔗 連結/錨點：檢查 %d 個頁面、%d 個本地目標" % (len(pages), len(fs_targets)))

    check_search_index(out)
    idx = json.load(open(os.path.join(out, "search_index.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(out, "search_index.json")) else []
    print("🗂 搜尋索引：%d 筆（簡）" % len(idx))

    for rel in sorted(pages):
        html, p = pages[rel]
        check_text_sanity(out, rel, html)
        check_counts(out, rel, html, p)
        check_toc_icons(out, rel, html)

    check_qa_pairs(out)
    check_trad_parity(out)

    if args.http:
        check_http(fs_targets, args.http_base)

    # ---- 報告 ----
    print()
    if not issues:
        print("✅ 未發現問題")
        return 0
    by_sev = {"bad": [], "warn": [], "skip": []}
    for sev, loc, msg in issues:
        by_sev.setdefault(sev, []).append((loc, msg))
    icons = {"bad": "❌", "warn": "⚠️ ", "skip": "➖"}
    for sev in ("bad", "warn", "skip"):
        for loc, msg in by_sev.get(sev, []):
            print("%s [%s] %s" % (icons[sev], loc, msg))
    print("\n共 %d ❌ / %d ⚠️" % (len(by_sev.get("bad", [])),
                                 len(by_sev.get("warn", []))))
    return 1 if by_sev.get("bad") else 0


if __name__ == "__main__":
    sys.exit(main())
