#!/usr/bin/env python3
"""gen_classified.py — 產生 wenda2_ebook/（全分類正式版）（Word+PDF 全分類合併電子書）

輸出格式與 wenda2_ebook/ 完全一致（word2ebook 管線渲染）：
  簡/繁雙語、全量搜尋、TOC、閱讀設定、暗色模式、PWA——全部沿用 word2ebook 的
  HTMLGenerator / SearchIndexGenerator / StaticAssetsManager。

內容合併：
  1. Word 章（wenda2_ebook/01–12.html）——解析 HTML，按 h2/h3/h4 標題映射到樹路徑
  2. PDF 分類條目（build/classified/*.jsonl）——已有 ch/l2/l3/l4 樹路徑
  3. 每個樹節點下：Word 條目（保持原序）＋ PDF 條目（按日期排），合併輸出

HTML 大小控制（與 wenda2_ebook 相同）：
  CSS 的 content-visibility: auto 讓離屏 Q&A 不渲染，
  單章 2000+ 則也能流暢捲動（00-base.css 已內建）。

usage: ../../word_audio_map2/.venv/bin/python gen_classified.py
"""
import json
import re
import sys
from pathlib import Path

from lxml import html as lhtml

ROOT = Path(__file__).resolve().parents[2]
W2E = ROOT / "tool" / "word2ebook"
SRC = ROOT / "wenda2_ebook_word"
DST = ROOT / "wenda2_ebook"
BUILD = ROOT / "tool" / "qa_split_ebook" / "build"
TREE_FILE = BUILD / "self_batches" / "tree_compact.txt"
CHAPTERS = list(range(1, 13))

sys.path.insert(0, str(W2E))

# ── 樹 ──
NAME_TO_PATH = {}
PATH_TO_NAME = {}
for line in TREE_FILE.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("=="):
        continue
    parts = line.split(" ", 1)
    if len(parts) != 2:
        continue
    p, n = parts[0].strip(), parts[1].strip()
    if re.match(r"^\d{2}", p):
        NAME_TO_PATH[n] = p
        PATH_TO_NAME[p] = n

CH_TITLES = {}
for line in TREE_FILE.read_text(encoding="utf-8").splitlines():
    m = re.match(r"^== (\d{2})(.+?) ==$", line.strip())
    if m:
        CH_TITLES[int(m.group(1))] = m.group(2).strip()

# 樹順序（每章的 path 清單，按文檔序）
TREE_ORDER = {}
for p in PATH_TO_NAME:
    ch = int(p[:2])
    TREE_ORDER.setdefault(ch, []).append(p)
for ch in TREE_ORDER:
    TREE_ORDER[ch].sort(key=lambda x: tuple(int(v) for v in x.split("-")))


def clean_heading(text: str) -> str:
    """去掉標題尾部的計數括號：'起源(29)' → '起源'"""
    return re.sub(r"\s*[（(]\d+[）)]\s*$", "", text).strip()


# ────────────────────────────────────────────────────────────── #
# 來源 1：Word 章——提取 Q&A HTML 區塊與 heading                              #
# ────────────────────────────────────────────────────────────── #
def extract_word_blocks(ch: int) -> tuple[list[str], list[tuple[int, str, str]]]:
    """從 wenda2_ebook/NN.html 的 <main> 區提取 heading 和 Q&A 區塊。

    只走訪 <main>（避免誤抓側欄 TOC / header / nav）；
    class 用精確比對（"question" 不匹配 "question-meta"）。
    """
    src = SRC / f"{ch:02d}.html"
    if not src.exists():
        return [], []
    doc = lhtml.parse(str(src)).getroot()
    main = doc.find(".//main")
    if main is None:
        return [], []

    blocks = []
    toc_items = []

    for el in main.iter():
        tag = el.tag if isinstance(el.tag, str) else ""
        if tag in ("h1", "h2", "h3", "h4"):
            text = (el.text_content() or "").strip()
            hid = el.get("id") or ""
            if not text or "本章目录" in text or "目录" == text:
                continue
            level = int(tag[1])
            # h1 含章節計數「01自性与意识(324)」——去掉括號
            blocks.append(lhtml.tostring(el, encoding="unicode"))
            if level >= 2 and hid:
                toc_items.append((level, clean_heading(text), hid))
        elif tag == "div":
            cls = el.get("class") or ""
            # ⚠️ 精確比對——不用 "in"，避免誤抓 question-meta / question-text / answer-text
            if cls == "question" or cls == "answer":
                blocks.append(lhtml.tostring(el, encoding="unicode"))

    return blocks, toc_items


# ────────────────────────────────────────────────────────────── #
# 來源 2：PDF 分類條目                                                     #
# ────────────────────────────────────────────────────────────── #
def extract_pdf_items() -> list[dict]:
    items_raw = {}
    for line in (BUILD / "items.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        items_raw[d["seq"]] = d

    results = []
    for f in sorted((BUILD / "classified").glob("batch_*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            seq = r["i"]
            it = items_raw.get(seq)
            if not it:
                continue
            ch = r["ch"]
            parts = [f"{ch:02d}"]
            if r.get("l2"): parts.append(f"{r['l2']:02d}")
            if r.get("l3"): parts.append(f"{r['l3']:02d}")
            if r.get("l4"): parts.append(f"{r['l4']:02d}")
            path = "-".join(parts)

            suffix = f"-{r['sub']}" if r.get("split") and r.get("sub", 0) > 0 else ""
            qid = it["qid"] + suffix
            aid = (it["aid"] or it["qid"].replace("question-", "answer-")) + suffix

            if r.get("split") and r.get("sub", 0) > 0:
                q_html = fix_corrupted_text(qid, _wrap_qa(r.get("q", ""), qid, "question", clean_questioner(it.get("who","")), it.get("time","")))
                a_html = _wrap_qa(r.get("a", ""), aid, "answer", "Taiguanglin", "")
            else:
                q_html = fix_corrupted_text(qid, _wrap_qa("".join(it["q_parts"]), qid, "question", clean_questioner(it.get("who","")), it.get("time","")))
                a_html = _wrap_qa("".join(it["a_parts"]), aid, "answer", "Taiguanglin", "")

            results.append({
                "qid": qid, "aid": aid, "path": path,
                "q_html": q_html, "a_html": a_html,
                "time": it.get("time", ""), "source": "pdf",
            })
    return results


def _wrap_qa(html: str, el_id: str, kind: str, who: str = "", time: str = "") -> str:
    """把 Q/A 內容包成 word2ebook 格式的 div（含 answerer/answer-meta）。"""
    if kind == "question":
        meta = f'<span class="questioner">{who}</span>'
        if time:
            meta += f'\n<span class="question-time">{time}</span>'
        return (f'<div class="question" id="{el_id}">\n'
                f'<div class="question-meta">{meta}</div>\n'
                f'<div class="question-text">{html}</div>\n</div>')
    else:
        return (f'<div class="answer" id="{el_id}">\n'
                f'<div class="answer-meta">\n<span class="answerer">Taiguanglin</span>\n</div>\n'
                f'<div class="answer-text">{html}</div>\n</div>')


# ────────────────────────────────────────────────────────────── #
# 合併：Word blocks + PDF items → content_blocks + toc_items              #
# ────────────────────────────────────────────────────────────── #
def sort_key(t: str):
    m = re.match(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", t or "")
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return (9999, 12, 31)



def clean_questioner(who: str) -> str:
    """把 questioner 名字中被吸入的日期分離：'ZH 2025-07-11' → 'ZH'。"""
    return re.sub(r'\s*\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s*$', '', who).strip()


# 已知損壞條目修正表（question-id → 重建的問題文字）
_CORRUPTED_FIXES = {
    "question-e2659b929821":
        "师父，禅定是否就是回到我们原本的状态？我们曾经体验过这些境界，现在只是往回走？（原始問題文字因 Excel 儲存格引用污染而遺失，此為依據答案內容重建）",
}

def _clean_questioner_span(q_html: str) -> str:
    """清理 question HTML 中的 questioner 名字（去掉被吸入的日期）。"""
    def _fix(m):
        return f'<span class="questioner">{clean_questioner(m.group(1))}</span>'
    return re.sub(r'<span class="questioner">([^<]+)</span>', _fix, q_html)



# 前後文推斷的日期補充（HH:MM:SS → 完整 YYYY-MM-DD HH:MM:SS）
_INFERRED_DATES = {
    "question-0306f99338b9": "2025-03-13 18:13:32",
    "question-103d9ece1af4": "2026-01-05 15:08:29",
    "question-13c772236fd5": "2026-03-07 16:24:23",
    "question-1cb39ef47d6d": "2024-02-21 11:15:36",
    "question-1cf4eea5e325": "2024-02-26",
    "question-1d7a3d25d37d": "2026-03-04 16:08:18",
    "question-1e93153fe69e": "2026-01-06 10:38:28",
    "question-22b01187c115": "2025-03-15",
    "question-2c97cf33bd62": "2024-07-16",
    "question-2fc7a9dc34ff": "2024-02-29 17:48:10",
    "question-30a774ef0812": "2024-03-18",
    "question-326bf7a5c490": "2026-01-10 16:56:55",
    "question-3351f4b26436": "2024-03-20",
    "question-34f93eac0f96": "2025-12-12 11:31:25",
    "question-36f022d174a3": "2025-01-14",
    "question-383d2169aa56": "2026-02-06 10:55:05",
    "question-3adbb87b6522": "2024-12-13",
    "question-3e36e90ed714": "2024-02-22",
    "question-45ebf0f8763d": "2025-12-12 12:34:34",
    "question-48407c3384fe": "2025-12-12 09:18:18",
    "question-4f1637fa0d48": "2026-03-06 09:19:05",
    "question-50ff9cbb6237": "2025-12-09 09:39:18",
    "question-5742cd4c8474": "2025-05-16",
    "question-5c80439af98f": "2026-03-02 13:21:52",
    "question-5ceb3c600234": "2024-02-13 13:56:45",
    "question-631572eaa062": "2026-01-10 13:13:52",
    "question-63f9027af1d1": "2024-12-09 13:59:10",
    "question-68b110a1603a": "2024-03-13",
    "question-6d03c4fd36c5": "2026-03-03 13:17:45",
    "question-6ed80c503f5f": "2024-02-22",
    "question-725f7c20bb35": "2024-11-16 07:59:44",
    "question-725f7c20bb35-2": "2024-11-16 07:59:44",
    "question-72c420b8d87c": "2026-03-05 13:29:40",
    "question-767edcfe81a9": "2025-09-05 13:33:41",
    "question-7d7737748d25": "2024-03-20",
    "question-851b75e6df73": "2026-03-06 14:53:51",
    "question-88f63acdfa6f": "2025-03-14",
    "question-8d90ce3197b6": "2024-02-24 19:34",
    "question-90da5d51d7dc": "2024-03-17",
    "question-948657a47e81": "2026-03-06 09:53:41",
    "question-972a3db5f64d": "2025-09-04 10:42:42",
    "question-9a669911f19b": "2026-03-02 13:17:45",
    "question-9ae98a55f387": "2026-02-06 16:29:48",
    "question-9ec8b1120761": "2026-02-07 14:20:56",
    "question-a0d3a10132ea": "2026-03-06 10:49:04",
    "question-a11ee56f01d3": "2025-01-15 12:34:34",
    "question-a29eaf73334c": "2024-09-11",
    "question-a30cc9c4e9a7": "2024-06-08",
    "question-a6d52349a37a": "2026-01-06 16:45:36",
    "question-abade42264d9": "2024-02-20 09:16:46",
    "question-b23973592ba7": "2024-02-24 19:34",
    "question-c2424a52ec4d": "2025-07-12 18:59:55",
    "question-c85ec0f4008d": "2024-03-27",
    "question-c886bb770d6d": "2024-03-03",
    "question-ca01a37500b7": "2026-02-06 14:53:51",
    "question-d76227293d13": "2024-03-16",
    "question-e2659b929821": "2024-02-29",
    "question-e47ca16f3a9c": "2026-03-05 13:55:26",
    "question-f08ed1987012": "2026-03-02 17:32:58",
    "question-f5307180dfaa": "2026-03-07 09:18:18",
    "question-f675e3775649": "2024-03-20",
    "question-fc1ec5d5c21b": "2024-03-09",
    "question-fdc996d832d8": "2026-03-02 08:54:48",
    "question-4079d7f4070b": "2025-05-16",
    "question-86b0ac538acd": "2024-05-22",
    "question-dc5a336f83d6": "2025-03-14",}

def infer_missing_date(qid: str, q_html: str) -> str:
    """為無日期或 HH:MM:SS only 的條目補上推斷的日期。"""
    if qid not in _INFERRED_DATES:
        return q_html
    full = _INFERRED_DATES[qid]
    # 情況1：已有 HH:MM:SS span → 替換為完整日期
    if re.search(r'<span class="question-time">\d{2}:\d{2}:\d{2}</span>', q_html):
        return re.sub(
            r'(<span class="question-time">)\d{2}:\d{2}:\d{2}(</span>)',
            r'\g<1>' + full + r'\g<2>',
            q_html)
    # 情況2：沒有 question-time span → 在 questioner 後新增
    if '<span class="question-time">' not in q_html:
        # 在 questioner span 之後插入 question-time
        return re.sub(
            r'(<span class="questioner">[^<]+</span>)',
            r'\g<1>\n<span class="question-time">' + full + '</span>',
            q_html, count=1)
    # 情況3：有 span 但內容為空
    return re.sub(
        r'(<span class="question-time">)\s*(</span>)',
        r'\g<1>' + full + r'\g<2>',
        q_html)

def fix_corrupted_text(qid: str, q_html: str) -> str:
    """修正已知損壞的問題文字。"""
    if qid in _CORRUPTED_FIXES:
        fixed = _CORRUPTED_FIXES[qid]
        # 替換 question-text div 的內容
        return re.sub(
            r'(<div class="question-text">)[^<]*(</div>)',
            r'\g<1>' + fixed + r'\g<2>',
            q_html)
    return q_html

_TIME_RE = re.compile(
    r'<span class="question-time">([^<]+)</span>')

def normalize_time_str(t: str) -> str:
    """把各種日期格式正規化為 YYYY-MM-DD [HH:MM]（補零）。

    支援：YYYY-M-D、YYYY/M/D、DD-MM-YYYY（日先月後）、MM-DD-YYYY。
    """
    t = t.strip()
    # YYYY-M-D [HH:MM] 或 YYYY/M/D [HH:MM] → YYYY-MM-DD [HH:MM]
    m = re.match(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?$', t)
    if m:
        date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        if m.group(4):
            date += f" {int(m.group(4)):02d}:{m.group(5)}"
        return date
    # DD-MM-YYYY [HH:MM]（日先月後——首組>12 或 次組>12 才確定，否則先試日先）
    m = re.match(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?:\s+(\d{1,2}):(\d{2}))?$', t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if d > 12 and mo <= 12:
            # DD-MM-YYYY
            date = f"{y}-{mo:02d}-{d:02d}"
        elif mo > 12 and d <= 12:
            # MM-DD-YYYY
            date = f"{y}-{d:02d}-{mo:02d}"
        else:
            # 兩組都 ≤12——按 DD-MM（跟 Word 源文件一致的日先月後）
            date = f"{y}-{mo:02d}-{d:02d}"
        if m.group(4):
            date += f" {int(m.group(4)):02d}:{m.group(5)}"
        return date
    return t


def normalize_qa_time(html: str) -> str:
    """把 Q&A HTML 中的 question-time span 正規化。"""
    def _fix(m):
        return f'<span class="question-time">{normalize_time_str(m.group(1))}</span>'
    return _TIME_RE.sub(_fix, html)


def extract_time_key(html: str) -> tuple:
    """排序 key：無時間=(0,...) 排最前；有時間=(1,Y,M,D,分鐘)。"""
    m = _TIME_RE.search(html)
    if not m:
        return (0, 0, 0, 0, 0)
    t = normalize_time_str(m.group(1))
    dm = re.match(r'(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{2}):(\d{2}))?', t)
    if dm:
        return (1, int(dm.group(1)), int(dm.group(2)), int(dm.group(3)),
                int(dm.group(4) or 0) * 60 + int(dm.group(5) or 0))
    return (0, 0, 0, 0, 0)


_OLD_COUNT_RE = re.compile(r'<span class="chapter-qa-count">[^<]*</span>')

def strip_old_count(heading_html: str) -> str:
    """剝掉 heading 中舊的計數 span（避免 (21)(33) 雙計數）。"""
    return _OLD_COUNT_RE.sub('', heading_html)


def build_merged_chapter(ch: int, word_blocks: list[str],
                          word_toc: list[tuple[int, str, str]],
                          pdf_items: list[dict]) -> tuple[list[str], list[tuple[int, str, str]]]:
    """合併 Word 區塊與 PDF 條目 → (content_blocks, toc_items)。

    - heading 剝掉舊計數 span（finalize_chapter 會加新的合併計數）
    - Word + PDF 條目按時間排序合併（無時間排最前）
    - 日期正規化為 YYYY-MM-DD [HH:MM]
    """
    heading_re = re.compile(r'<h([234])[^>]*id="([^"]+)"[^>]*>(.*?)</h\1>', re.S)
    qa_re = re.compile(r'<div class="(question|answer)"')

    path_data = {}
    path_order = []
    cur_path = f"{ch:02d}"
    cur_q = None

    def _ensure_path(p):
        if p not in path_data:
            path_data[p] = {"heading": None, "level": 0, "text": "", "anchor": "",
                            "pairs": [], "path": p}
            path_order.append(p)
        return path_data[p]

    for blk in word_blocks:
        hm = heading_re.match(blk)
        if hm:
            cur_q = None
            level = int(hm.group(1))
            hid = hm.group(2)
            text = re.sub(r'<[^>]+>', '', hm.group(3)).strip()
            clean = clean_heading(text)
            p = NAME_TO_PATH.get(clean) or NAME_TO_PATH.get(text)
            if p and p[:2] == f"{ch:02d}":
                cur_path = p
            pd_ = _ensure_path(cur_path)
            pd_["heading"] = blk
            pd_["level"] = level
            pd_["text"] = clean
            pd_["anchor"] = hid
            continue

        if qa_re.match(blk):
            if 'class="question"' in blk[:60]:
                cur_q = blk
            elif 'class="answer"' in blk[:60] and cur_q is not None:
                _ensure_path(cur_path)["pairs"].append((cur_q, blk))
                cur_q = None
            elif 'class="answer"' in blk[:60]:
                _ensure_path(cur_path)["pairs"].append(("", blk))

    pdf_by_path = {}
    for it in pdf_items:
        if it["path"][:2] == f"{ch:02d}":
            pdf_by_path.setdefault(it["path"], []).append(
                (normalize_qa_time(it["q_html"]), it["a_html"]))

    content_blocks = []
    toc_items = []

    title = CH_TITLES.get(ch, f"{ch:02d}")
    h1_slug = f"{ch:02d}" + re.sub(r"[^a-z0-9]+", "-",
        re.sub(r"[（）()：:／/]", "", title).lower()).strip("-")[:30]
    content_blocks.append(f'<h1 id="{h1_slug}">{ch:02d}{title}</h1>')

    all_paths = list(path_order)
    for p in TREE_ORDER.get(ch, []):
        if p in pdf_by_path and p not in all_paths:
            all_paths.append(p)
    tree_set = set(TREE_ORDER.get(ch, []))
    in_tree = [p for p in all_paths if p in tree_set]
    not_in_tree = [p for p in all_paths if p not in tree_set]
    in_tree.sort(key=lambda x: TREE_ORDER[ch].index(x))
    ordered = in_tree + not_in_tree

    for p in ordered:
        pd_ = path_data.get(p)
        pdf_pairs = pdf_by_path.get(p, [])

        if pd_ and pd_["heading"]:
            content_blocks.append(strip_old_count(pd_["heading"]))
            toc_items.append((pd_["level"], pd_["text"], pd_["anchor"]))
        elif pdf_pairs and p in PATH_TO_NAME:
            name = PATH_TO_NAME[p]
            depth = len(p.split("-"))
            level = {2: 2, 3: 3, 4: 4}.get(depth, 4)
            content_blocks.append(f'<h{level} id="{p}">{name}</h{level}>')
            toc_items.append((level, name, p))

        all_pairs = (pd_["pairs"] if pd_ else []) + pdf_pairs
        all_pairs.sort(key=lambda qa: extract_time_key(qa[0]))

        for q_html, a_html in all_pairs:
            if q_html:
                # 清理 Word 章的 questioner 名字（去日期）+ 修正損壞文字 + 日期正規化
                q_html = _clean_questioner_span(normalize_qa_time(q_html))
                qid_m = re.search(r'id="(question-[^"]+)"', q_html)
                if qid_m:
                    q_html = fix_corrupted_text(qid_m.group(1), q_html)
                    q_html = infer_missing_date(qid_m.group(1), q_html)
                content_blocks.append(q_html)
            content_blocks.append(normalize_qa_time(a_html))

    return content_blocks, toc_items


# ────────────────────────────────────────────────────────────── #
# 主流程——用 word2ebook 管線渲染                                          #
# ────────────────────────────────────────────────────────────── #
def main():
    from models.document_models import Chapter, ConversionConfig
    from core.chapter_finalizer import finalize_chapter
    from generators.html_generator import HTMLGenerator
    from generators.search_generator import SearchIndexGenerator
    from templates.static_assets import StaticAssetsManager
    from config.settings import DEFAULT_SETTINGS
    from utils.file_utils import FileManager

    print("[gen_classified] 提取 Word 章…")
    all_chapters = []

    pdf_items = extract_pdf_items()
    print(f"[gen_classified] PDF 分類條目：{len(pdf_items)} 條")

    for ch in CHAPTERS:
        word_blocks, word_toc = extract_word_blocks(ch)
        ch_pdf = [x for x in pdf_items if x["path"][:2] == f"{ch:02d}"]
        blocks, toc = build_merged_chapter(ch, word_blocks, word_toc, ch_pdf)
        n_qa = sum(1 for b in blocks if 'class="question"' in b)
        print(f"  ch{ch:02d}: word_blocks={len(word_blocks)} + pdf={len(ch_pdf)} → {n_qa} 則")

        chapter = Chapter(
            title=f"{ch:02d}{CH_TITLES.get(ch, '')}",
            filename=f"{ch:02d}.html",
        )
        chapter = finalize_chapter(chapter, blocks, toc, DEFAULT_SETTINGS)
        all_chapters.append(chapter)

    # 輸出
    print("\n[gen_classified] 渲染（word2ebook 管線）…")
    if DST.exists():
        import shutil
        shutil.rmtree(DST)
    DST.mkdir(parents=True)

    config = ConversionConfig(
        input_file=ROOT / "問答錄2" / "wenda2_250810_截止25年5月17日答疑_含图版.docx",
        output_folder=DST,
        generate_search=True,
        generate_traditional=True,
        generate_simplified=True,
        pdf_files=[
            ROOT / "問答錄2" / "2025年6月-9月答疑合并（未分类）.pdf",
            ROOT / "問答錄2" / "2025年11月-2026年3月答疑合并（未分类）.pdf",
        ],
    )

    # File manager + HTML generator（正確的建構子參數）
    fm = FileManager(config.output_folder)
    fm.setup_output_directory(clean_existing=False)  # 已手動清過

    html_gen = HTMLGenerator(
        DEFAULT_SETTINGS, fm,
        input_file=config.input_file,
        extra_source_files=list(config.pdf_files),
    )
    html_gen.copy_favicon_after_setup()

    # 生成章節頁
    html_gen.generate_chapter_pages(all_chapters, generate_traditional=True, generate_simplified=True)
    print("✅ 章節頁完成")

    # 生成首頁（ConversionConfig 自帶 get_book_title）
    html_gen.generate_index_pages(all_chapters, config, generate_traditional=True, generate_simplified=True)
    print("✅ 首頁完成")

    # 搜尋索引（SearchIndexGenerator 需要 settings + file_manager）
    search_gen = SearchIndexGenerator(DEFAULT_SETTINGS, fm)
    search_gen.generate_search_indexes(all_chapters, generate_traditional=True, generate_simplified=True)
    print("✅ 搜尋索引完成")

    # 靜態資源（CSS/JS——從 word2ebook 的模組來源串接）
    from templates.static_assets import StaticAssetsManager
    import shutil as _sh
    assets_mgr = StaticAssetsManager()
    fm.write_file("assets/css/style.css", assets_mgr.get_full_css_content())
    fm.write_file("assets/js/script.js", assets_mgr.get_full_js_content())

    # 獨立 JS 檔案（word2ebook 來源）
    for src_name in [
        "assets/js/i18n-text.js",
        "assets/js/reading-prepaint.js",
        "assets/js/search-cache.js",
        "assets/js/jieba_rs_wasm.js",
        "assets/js/jieba_rs_wasm_bg.wasm",
        "assets/js/minisearch.min.js",
    ]:
        src_f = W2E / src_name
        if src_f.exists():
            (DST / src_name).parent.mkdir(parents=True, exist_ok=True)
            _sh.copy2(src_f, DST / src_name)

    # 圖片（Word 章引用的 assets/images/*.webp——從 wenda2_ebook 複製）
    img_src = SRC / "assets" / "images"
    img_dst = DST / "assets" / "images"
    if img_src.exists():
        img_dst.mkdir(parents=True, exist_ok=True)
        for f in img_src.glob("*"):
            _sh.copy2(f, img_dst / f.name)
    print("✅ 靜態資源完成")

    total = sum(1 for ch in all_chapters for _ in range(ch.content.count('class="question"')))

    # 舊章節 13-21 跳轉頁（外部已分享的 URL 不 404）
    _REDIRECT_TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>此章節已重新分類</title>
<meta http-equiv="refresh" content="3;url=index{suffix}.html"/>
<style>
body{{font-family:-apple-system,sans-serif;background:#f5f5f5;display:flex;justify-content:center;align-items:center;min-height:100vh;color:#333;text-align:center;padding:2rem}}
.box{{background:#fff;border-radius:12px;padding:3rem;box-shadow:0 4px 12px rgba(0,0,0,.08);max-width:500px}}
h1{{color:#e75480;font-size:1.3rem;margin-bottom:1rem}}
p{{line-height:1.8;margin-bottom:.5rem}}
a{{color:#e75480;font-weight:bold;text-decoration:none}}
a:hover{{text-decoration:underline}}
</style>
</head>
<body>
<div class="box">
<h1>📌 此章節已重新分類</h1>
<p>第 {ch} 章的內容已按主題重新分類到第 01–12 章中。</p>
<p>將在 3 秒後自動跳轉到總目錄。</p>
<p><a href="index{suffix}.html">👉 立即前往總目錄</a></p>
</div>
</body>
</html>"""
    for old_ch in range(13, 22):
        for suffix in ("", "_trad"):
            page = _REDIRECT_TPL.format(ch=old_ch, suffix=suffix)
            (DST / f"{old_ch:02d}{suffix}.html").write_text(page, encoding="utf-8")
    print("✅ 舊章節跳轉頁（13-21）完成")

    print(f"\n[gen_classified] 完成 → {DST}（{total} 則）")


if __name__ == "__main__":
    main()
