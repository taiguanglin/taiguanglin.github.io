#!/usr/bin/env python3
"""gen_classified.py — 產生 wenda2_ebook/（全分類正式版）（Word+PDF 全分類合併電子書）

就地轉換（2026-10-26 起，``wenda2_ebook_word/`` 中繼目錄已移除）：
本腳本是兩段式重建的 **stage 3**，SRC＝DST＝``wenda2_ebook/``——
必須先跑 stage 1（``tool/word2ebook/gen_all.py``，重建 21 章時間序底稿）
與 stage 2（``extract.py``，重抽 ``build/items.jsonl``），本腳本才把
01–12 章就地轉成分類合併版、13–21 章換成跳轉頁。直接在分類完的成品上
重跑會誤把分類內容當 Word 原章解析——腳本開頭有守門檢查。

輸出格式與 wenda2_ebook/ 完全一致（word2ebook 管線渲染）：
  簡/繁雙語、全量搜尋、TOC、閱讀設定、暗色模式、PWA——全部沿用 word2ebook 的
  HTMLGenerator / SearchIndexGenerator / StaticAssetsManager。

內容合併：
  1. Word 章（wenda2_ebook/01–12.html，stage 1 底稿）——解析 HTML，按 h2/h3/h4 標題映射到樹路徑
  2. PDF 分類條目（build/classified/*.jsonl）——已有 ch/l2/l3/l4 樹路徑
  2b. 補充條目（supplemental_items.json，版控 SoT）——PDF 有收錄但 qa-pair
      抽取遺漏的內容（例：小節尾「师父说」結尾開示），人工歸類到樹路徑
  3. 每個樹節點下：Word 條目＋ PDF 條目依「最終顯示日期」由早到晚合併輸出
     （推斷日期必須在排序前補上，否則該則會被當成無時間而排到最前）

HTML 大小控制（與 wenda2_ebook 相同）：
  CSS 的 content-visibility: auto 讓離屏 Q&A 不渲染，
  單章 2000+ 則也能流暢捲動（00-base.css 已內建）。

usage: ../../word_audio_map2/.venv/bin/python gen_classified.py
"""
import json
import re
import sys
from html import escape as _html_escape
from pathlib import Path

from lxml import html as lhtml

ROOT = Path(__file__).resolve().parents[2]
W2E = ROOT / "tool" / "word2ebook"
# 就地流程（2026-10-26 起）：SRC＝DST。01–12 章先以 Word 底稿身分被讀取
# （stage 1 產物），組裝完成後整個目錄被重寫成分類合併版。
SRC = ROOT / "wenda2_ebook"
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
                html = lhtml.tostring(el, encoding="unicode")
                # 圖片是 question/answer div 的「兄弟節點」——word2ebook 的
                # _append_image 把圖接在區塊之後（div 與 div 之間），不在 div 內。
                # 只序列化 div 本體會把圖整個遺失（發布版 <img> 數為 0，
                # assets/images/ 卻有 64 個檔）。這裡把緊鄰的 <img> 一併收進
                # 該區塊，圖才會跟著 Q&A 進入發布版。
                imgs = []
                sib = el.getnext()
                while sib is not None and getattr(sib, "tag", None) == "img":
                    imgs.append(lhtml.tostring(sib, encoding="unicode"))
                    sib = sib.getnext()
                if imgs:
                    cut = html.rfind("</div>")
                    if cut > 0:
                        html = (html[:cut] + "\n" + "\n".join(imgs) + "\n"
                                + html[cut:])
                blocks.append(html)

    return blocks, toc_items


# ────────────────────────────────────────────────────────────── #
# 來源 2：PDF 分類條目                                                     #
# ────────────────────────────────────────────────────────────── #

# ────────────────────────────────────────────────────────────── #
# 音頻播放按鈕注入（讀 audio_map/*.json 的已校對時間）                     #
# ────────────────────────────────────────────────────────────── #
_AUDIO_MAP_DIR = ROOT / "audio_map"

_QA_PLAY_ICON = ('<span class="qa-play-icon"><svg aria-hidden="true" '
    'class="qa-play-speaker" focusable="false" height="1em" '
    'viewBox="0 0 24 24" width="1em"><path '
    'd="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05'
    'c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71'
    's-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" '
    'fill="currentColor"></path></svg></span>')

def _fmt_tc(sec):
    """秒 → HH:MM:SS.mmm"""
    if sec is None:
        return "00:00:00.000"
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"

def load_audio_map_for_play():
    """讀 audio_map/*.json → {question_id: {file, start, end}}。"""
    mapping = {}
    if not _AUDIO_MAP_DIR.exists():
        return mapping
    import urllib.parse
    for f in sorted(_AUDIO_MAP_DIR.glob("*.json")):
        if "qid_to_sep" in f.name:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            continue
        for sess in d.get("sessions", []):
            audio = sess.get("audio_file", "")
            if not audio:
                continue
            # URL encode 音頻路徑（與 word2ebook 的注入器一致）
            encoded = urllib.parse.quote(f"../audio/{audio}")
            for seg in sess.get("segments", []):
                qid = seg.get("question_id", "")
                start = seg.get("start")
                end = seg.get("end")
                # 「零長度／師父未念」(zero: true) 沒有可播的聲音 → 不給播放鈕
                if seg.get("zero") is True:
                    continue
                if qid and start is not None and end is not None and end > start:
                    entry = {
                        "audio": encoded,
                        "start": start,
                        "end": end,
                    }
                    # 「兩段式播放」：師父交錯作答時，一張卡的音檔切成
                    # 兩個不連續視窗（parts），播放鈕帶 data-segments 連播。
                    parts = seg.get("parts")
                    if isinstance(parts, list) and len(parts) >= 2:
                        entry["parts"] = parts
                    mapping[qid] = entry
    return mapping

def inject_play_button(a_html: str, qid: str, audio_map: dict) -> str:
    """為 answer HTML 注入 qa-play 播放按鈕（有音頻數據時）。"""
    if qid not in audio_map:
        return a_html
    info = audio_map[qid]
    start, end = info["start"], info["end"]
    label = f"{_fmt_tc(start)} - {_fmt_tc(end)}"
    encoded = info["audio"]
    # 「兩段式播放」：parts = [[s1,e1],[s2,e2],…] → data-segments，
    # 08-qa-audio.js 依序播放、跳過中間未選範圍（比照 Word 章
    # audio_map2 two_part_group 先例的同一份 data 契約）。
    parts_attr = ""
    parts = info.get("parts")
    if isinstance(parts, list) and len(parts) >= 2:
        parts_attr = (
            ' data-segments="'
            + _html_escape(json.dumps(parts, separators=(",", ":")), quote=True)
            + '"'
        )
    btn = (f'<button aria-label="播放 {label}" class="qa-play qa-play--inline" '
           f'data-audio="{encoded}" data-end="{end}" data-label="{label}" '
           f'{parts_attr}'
           f'data-start="{start}" type="button">{_QA_PLAY_ICON}</button>')
    # 插入到 answerer span 之後（answer-meta 內）
    return a_html.replace('</span>\n</div>', f'</span>\n{btn}\n</div>', 1)


def _attach_imgs(html: str, imgs) -> str:
    """把 stage 2 收集的 <img> 插回 question / answer div 的內部末端。

    圖在 stage 1 底稿是 Q&A div 的兄弟節點（word2ebook 的 _append_image），
    stage 2 取 inner HTML 時會遺失，故由 stage 2 單獨收集、此處插回。
    插在 div 的最後一個 </div> 之前 → 圖隨著該問答一起輸出。
    """
    if not imgs or not html:
        return html
    cut = html.rfind("</div>")
    if cut <= 0:
        return html
    return html[:cut] + "\n" + "\n".join(imgs) + "\n" + html[cut:]


def _parts_to_html(parts) -> str:
    """段落清單（或含 \\n 的單一文字）→ 逐段包 <p>，還原轉錄的段落結構。

    stage 1 底稿的多段 Q/A＝一個 answer-text/question-text div 一段；
    舊版 "".join(parts) 把段落無縫黏成文字牆（無任何分隔——1,358 問、
    2,759 答受害），讀者看到的是整面不換行的長文。<p> 由全站 CSS
    （00-base.css `p { margin: 15px 0 }`）提供段距。外層 div id 不變，
    #answer-/#question- 錨點、搜尋索引（get_text() 逐字相同）與每日精選
    連結全部不受影響。空段自動略過。"""
    if isinstance(parts, str):
        parts = parts.split("\n")
    return "\n".join(f"<p>{t.strip()}</p>" for t in parts if t and t.strip())


def extract_pdf_items(_audio_map: dict = None) -> list[dict]:
    items_raw = {}
    for line in (BUILD / "items.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        items_raw[d["seq"]] = d
    if _audio_map is None:
        _audio_map = {}

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
                q_html = fix_corrupted_text(qid, _wrap_qa(_parts_to_html(r.get("q", "")), qid, "question", clean_questioner(it.get("who","")), it.get("time","")))
                a_html = _wrap_qa(_parts_to_html(r.get("a", "")), aid, "answer", "Taiguanglin", "")
                a_html = _attach_imgs(a_html, it.get("a_imgs"))
                a_html = inject_play_button(a_html, qid, _audio_map)
            else:
                q_html = fix_corrupted_text(qid, _wrap_qa(_parts_to_html(it["q_parts"]), qid, "question", clean_questioner(it.get("who","")), it.get("time","")))
                q_html = _attach_imgs(q_html, it.get("q_imgs"))
                a_html = _wrap_qa(_parts_to_html(it["a_parts"]), aid, "answer", "Taiguanglin", "")
                a_html = _attach_imgs(a_html, it.get("a_imgs"))
                a_html = inject_play_button(a_html, qid, _audio_map)

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
# 來源 2b：補充條目（supplemental_items.json，版控 SoT）                    #
#                                                                  #
# 收錄 PDF 有收錄、但 extract.py（stage 2）只抽 article.qa-pair            #
# 而帶不進分類版的內容——例如月度章 h2 小節尾「师父说」的結尾開示：           #
# stage 1 渲染為小節尾 <p>（.qa-opening/.qa-closing 帶 play bar），        #
# stage 2 不抽、stage 3 就掉了。此檔由人工整理（文字＝stage 1 底稿         #
# 解析原文，僅加段落分隔），與 PDF 分類條目同一套包裝/排序/注入路徑。        #
# ────────────────────────────────────────────────────────────── #
SUPPLEMENTAL_FILE = Path(__file__).resolve().parent / "supplemental_items.json"


def load_supplemental_items(audio_map: dict) -> list[dict]:
    """supplemental_items.json → 與 extract_pdf_items 同構的條目清單。

    有 audio 欄位的條目以合成 qid 註冊進 audio_map（供 inject_play_button
    用同一條路徑注入播放鈕）——合成 qid（非 md5 十六進位）不會與 PDF
    真實 qid 相撞，也不寫回 audio_map/*.json。
    """
    if not SUPPLEMENTAL_FILE.exists():
        return []
    d = json.loads(SUPPLEMENTAL_FILE.read_text(encoding="utf-8"))
    import urllib.parse
    out = []
    for it in d.get("items", []):
        qid = it["qid"]
        aid = qid.replace("question-", "answer-", 1)
        q_html = _wrap_qa(it["q_html"], qid, "question", it.get("who", ""),
                         it.get("time", ""))
        a_html = _wrap_qa(it["a_html"], aid, "answer", "Taiguanglin", "")
        au = it.get("audio")
        if au and au.get("start") is not None and au.get("end") is not None:
            audio_map[qid] = {
                "audio": urllib.parse.quote(f"../audio/{au['file']}"),
                "start": au["start"],
                "end": au["end"],
            }
            a_html = inject_play_button(a_html, qid, audio_map)
        out.append({
            "qid": qid, "aid": aid, "path": it["path"],
            "q_html": q_html, "a_html": a_html,
            "time": it.get("time", ""), "source": "supplemental",
        })
    return out


# ────────────────────────────────────────────────────────────── #
# 合併：Word blocks + PDF items → content_blocks + toc_items              #
# ────────────────────────────────────────────────────────────── #
def parse_time_parts(t: str):
    """解析時間字串 → (Y, M, D, h, m, s, has_clock, has_seconds)；失敗回 None。

    支援 YYYY-M-D、YYYY/M/D、DD-MM-YYYY（日先月後）、MM-DD-YYYY；
    時間可為 HH:MM 或 HH:MM:SS（微信後端時間戳只有 HH:MM:SS）。
    DD/MM 兩組都 ≤12 時依 Word 源檔慣例當「日先月後」。
    """
    s = (t or "").strip()
    m = re.match(
        r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})日?"
        r"(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.match(
            r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})"
            r"(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$", s)
        if not m:
            return None
        first, second, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if first > 12 and second <= 12:
            d, mo = first, second            # DD-MM-YYYY
        elif second > 12 and first <= 12:
            d, mo = second, first            # MM-DD-YYYY
        else:
            d, mo = first, second            # 皆 ≤12：依源檔當日先月後
    has_clock = m.group(4) is not None
    has_seconds = m.group(6) is not None
    return (y, mo, d, int(m.group(4) or 0), int(m.group(5) or 0),
            int(m.group(6) or 0), has_clock, has_seconds)



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
    # 2024-11-11「監獄」題：原填 2024-09-11（誤抄前一題「鎧茵 2024/9/11」的日期）。
    # 該題在 Word 裡沒有提問日期，正確是本場日期 2024-11-11（轉場句「11月11號微信的問題」）。
    "question-a29eaf73334c": "2024-11-11",
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


# 題幹修正表（question-id → 正確的問題文字）
# ─────────────────────────────────────────────────────────────────────────
# 2024-11-11「監獄」題：Word 把「師父說」的轉場白與第 1 問寫在同一個段落
#   （問答錄2/wenda2_250810_截止25年5月17日答疑_含图版.docx 第 9519 段；
#    問答錄2/2024-2025 TAI师父答疑汇总 - 截止2025年7月12日.docx 第 22876 段）：
#     「师父说：贴吧的问题到这里结束了，11月11号微信的问题，从这边显示的从下面开始回答。
#       1、还有想问下在监狱的环境没有《地藏经》读，…主要是想让他以后能顺利往生。」
# stage 1 的提問者規則（任何「XXX：」開頭都算提問者）因此把整段當成
# 「師父说」這個提問者的問題，轉場白被併進題幹。
# 這裡只把轉場白摘掉、留下真正的題幹。**question-id 不變**（stage 3 沿用
# stage 1 的 id）→ audio_map2 的 chapter_question_ids / chapter_answer_ids
# 對應不受影響，播放鈕照常注入。
_QUESTION_TEXT_FIXES = {
    "question-a29eaf73334c": (
        "1、还有想问下在监狱的环境没有《地藏经》读，是让他每天念地藏王菩萨名号好，"
        "还是念阿弥陀佛好呢？ 主要是想让他以后能顺利往生。"
    ),
}

# 提問者修正表（question-id → 提問者；空字串＝該題在 Word 裡沒有姓名行）
# 「師父说」是轉場標記不是提問人，該題在 Word 裡沒有姓名行。
_QUESTIONER_FIXES = {
    "question-a29eaf73334c": "",
}


def fix_question_text(qid: str, q_html: str) -> str:
    """依 _QUESTION_TEXT_FIXES 覆寫問題文字（保留原本的 div 包裹）。"""
    if qid not in _QUESTION_TEXT_FIXES:
        return q_html
    fixed = _QUESTION_TEXT_FIXES[qid]
    return re.sub(
        r'(<div class="question-text">)(.*?)(</div>)',
        lambda m: m.group(1) + fixed + m.group(3),
        q_html, count=1, flags=re.S)


def fix_questioner(qid: str, q_html: str) -> str:
    """依 _QUESTIONER_FIXES 覆寫提問者 span 的內容（空字串＝無提問人）。"""
    if qid not in _QUESTIONER_FIXES:
        return q_html
    who = _QUESTIONER_FIXES[qid]
    return re.sub(
        r'(<span class="questioner">)[^<]*(</span>)',
        lambda m: m.group(1) + who + m.group(2),
        q_html, count=1)

_TIME_RE = re.compile(
    r'<span class="question-time">([^<]+)</span>')

def normalize_time_str(t: str) -> str:
    """把各種日期格式正規化為 YYYY-MM-DD [HH:MM[:SS]]（補零）。

    支援：YYYY-M-D、YYYY/M/D、DD-MM-YYYY（日先月後）、MM-DD-YYYY。
    ⚠️ 秒（HH:MM:SS）必須保留——部分微信問答的時間戳帶秒，
    舊版把整串視為「非日期」，導致該則被當成無時間而排到最前面。
    """
    t = t.strip()
    parts = parse_time_parts(t)
    if not parts:
        return t
    y, mo, d, hh, mm, ss, has_clock, has_seconds = parts
    date = f"{y:04d}-{mo:02d}-{d:02d}"
    if has_clock:
        date += f" {hh:02d}:{mm:02d}"
        if has_seconds:
            date += f":{ss:02d}"
    return date


def normalize_qa_time(html: str) -> str:
    """把 Q&A HTML 中的 question-time span 正規化。"""
    def _fix(m):
        return f'<span class="question-time">{normalize_time_str(m.group(1))}</span>'
    return _TIME_RE.sub(_fix, html)


def extract_time_key(html: str) -> tuple:
    """排序 key：無法解析日期 → (2,) 排最後；有日期 → (1,Y,M,D,h,m,s)。

    ⚠️ 必須能解析 HH:MM:SS（秒）與 YYYY/M/D、DD-MM-YYYY 等格式；
    舊版只認「YYYY-M-D [HH:MM]」，帶秒的時間戳整串落空 → 被當成
    無時間而排到最前（01 章「修行翻出情緒/習氣」即因此錯序）。
    """
    m = _TIME_RE.search(html)
    if not m:
        return (2,)
    parts = parse_time_parts(m.group(1))
    if not parts:
        return (2,)
    y, mo, d, hh, mm, ss, _has_clock, _has_seconds = parts
    return (1, y, mo, d, hh, mm, ss)


_OLD_COUNT_RE = re.compile(r'<span class="chapter-qa-count">[^<]*</span>')

def strip_old_count(heading_html: str) -> str:
    """剝掉 heading 中舊的計數 span（避免 (21)(33) 雙計數）。"""
    return _OLD_COUNT_RE.sub('', heading_html)


def _prepare_question_html(q_html: str) -> str:
    """把提問 HTML 整理成「最終顯示」狀態（清理提問者、補日期、修正文字）。

    這一步必須在排序之前完成——排序依的是 question-time span，
    若推斷日期在排序後才補上，該則會被當成「無時間」而排到最前面。
    """
    if not q_html:
        return q_html
    q_html = _clean_questioner_span(normalize_qa_time(q_html))
    qid_m = re.search(r'id="(question-[^"]+)"', q_html)
    if qid_m:
        qid = qid_m.group(1)
        q_html = fix_corrupted_text(qid, q_html)
        # ⚠️ infer_missing_date 必須排在 fix_questioner 之前：
        #    它把 question-time span 插在 questioner span 之後，
        #    questioner 清空後其正則（[^<]+）就不再符合、日期會插不進去。
        q_html = infer_missing_date(qid, q_html)
        q_html = fix_questioner(qid, q_html)
        q_html = fix_question_text(qid, q_html)
        # 推斷日期可能帶秒（HH:MM:SS），再正規化一次以統一補零格式
        q_html = normalize_qa_time(q_html)
    return q_html


def build_merged_chapter(ch: int, word_blocks: list[str],
                          word_toc: list[tuple[int, str, str]],
                          pdf_items: list[dict]) -> tuple[list[str], list[tuple[int, str, str]]]:
    """合併 Word 區塊與 PDF 條目 → (content_blocks, toc_items)。

    - heading 剝掉舊計數 span（finalize_chapter 會加新的合併計數）
    - 每個小節內 Word + PDF 條目「依日期由早到晚」合併排序
      （日期＝最終顯示的 question-time，含推斷補上的日期；無法解析者排最後）
    - 日期正規化為 YYYY-MM-DD [HH:MM[:SS]]
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
        # ⚠️ 排序前先做「最終顯示化」：清理提問者姓名、補上推斷日期、
        #    修正損壞文字。正文日期若在排序後才補，該則會被當成無時間
        #    而排到最前面（2026-11 修正：01 章「修行翻出情緒/習氣」首則
        #    2025-12-09 曾排在 2024-09-09 之前）。
        all_pairs = [(_prepare_question_html(q), a) for q, a in all_pairs]
        all_pairs.sort(key=lambda qa: extract_time_key(qa[0]))

        for q_html, a_html in all_pairs:
            if q_html:
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
    import shutil as _sh
    import shutil

    # ── 守門：就地流程必須從 stage 1 底稿開始 ──────────────────────
    # 13.html 在底稿狀態＝完整月度章；在分類完成狀態＝跳轉頁。
    # 若已是跳轉頁，表示有人漏跑 stage 1 就重跑本腳本——01–12 章會被
    # 誤當成 Word 原章二次解析，直接擋下。
    probe = DST / "13.html"
    if probe.exists():
        probe_text = probe.read_text(encoding="utf-8")
        if "此章節已重新分類" in probe_text:
            print("❌ wenda2_ebook/13.html 已是跳轉頁（分類完成的成品），"
                  "不是 stage 1 底稿。請先跑：")
            print("   cd tool/word2ebook && python3 gen_all.py   （stage 1）")
            print("   然後 extract.py（stage 2）再重跑本腳本（stage 3）。")
            return 1
    else:
        print("❌ 找不到 wenda2_ebook/13.html——請先跑 stage 1："
              "cd tool/word2ebook && python3 gen_all.py")
        return 1

    print("[gen_classified] 提取 Word 章…")
    all_chapters = []

    audio_map_for_play = load_audio_map_for_play()
    print(f"[gen_classified] 音頻映射（可注入播放鈕）：{len(audio_map_for_play)} 條")
    pdf_items = extract_pdf_items(audio_map_for_play)
    print(f"[gen_classified] PDF 分類條目：{len(pdf_items)} 條")
    supplemental = load_supplemental_items(audio_map_for_play)
    if supplemental:
        for it in supplemental:
            print(f"[gen_classified] 補充條目：{it['qid']} → {it['path']}")
    pdf_items += supplemental

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

    # 輸出（就地流程：先把 stage 1 的 Word 章圖片搬到 build/ 暫存，
    # rmtree 之後再放回——SRC＝DST，不先搬就會連同舊產物一起被刪掉。）
    print("\n[gen_classified] 渲染（word2ebook 管線）…")
    img_stage = BUILD / "_stage_images"
    if img_stage.exists():
        shutil.rmtree(img_stage)
    if (DST / "assets" / "images").exists():
        shutil.move(str(DST / "assets" / "images"), str(img_stage))
    if DST.exists():
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

    # 圖片（Word 章引用的 assets/images/*.webp——stage 1 產物，
    # 稍早已搬到 build/_stage_images 暫存，現在放回。
    # ⚠️ fm.setup_output_directory() 已預建空的 assets/images/——shutil.move
    # 遇到既有目錄會把來源「搬進去」而不是改名，先刪掉空目錄再還原。）
    if img_stage.exists():
        target = DST / "assets" / "images"
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(img_stage), str(target))
    print("✅ 靜態資源完成")

    total = sum(1 for ch in all_chapters for _ in range(ch.content.count('class="question"')))

    # 舊章節 13-21 跳轉頁（外部已分享的 URL 不 404）
    #
    # SEO（2026-10-28）：這些頁原本只有 meta refresh，沒有 canonical／noindex，
    # 公開搜尋結果仍以舊標題把它們當成可索引內容。處置：
    #   · <meta name="robots" content="noindex, follow"> — 不進索引，但把
    #     連結權重流向總目錄（follow）。
    #   · <link rel="canonical"> 指向對應語系的總目錄 —— canonical 與 sitemap
    #     指向不同 URL 會互相矛盾，這裡兩者一致（跳轉頁不在 sitemap）。
    #   · 每頁唯一 title／description（原本 18 頁共用同一個標題）。
    #   · 跳轉延遲 3 秒 → 1 秒（crawler 與讀者都更快抵達目的地）。
    # GitHub Pages 無法自訂 301；若日後前面加了 CDN/edge redirect，可再升級
    # 成真正的永久轉址（見 tool/site_chrome/README.md）。
    _REDIRECT_TPL = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{title}</title>
<meta name="description" content="{description}"/>
<meta name="robots" content="noindex, follow"/>
<link rel="canonical" href="{canonical}"/>
<meta http-equiv="refresh" content="1;url=index{suffix}.html"/>
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
<p>{body_text}</p>
<p>將在 1 秒後自動跳轉到總目錄。</p>
<p><a href="index{suffix}.html">👉 立即前往總目錄</a></p>
</div>
</body>
</html>"""
    _SITE_BASE = "https://taiguanglin.info/wenda2_ebook"
    for old_ch in range(13, 22):
        for suffix in ("", "_trad"):
            is_trad = bool(suffix)
            if is_trad:
                _title = f"第 {old_ch} 章已重新分類｜《坐禪之問答錄2》"
                _description = (
                    f"《坐禪之問答錄2》第 {old_ch} 章的內容已按主題重新分類到第 01–12 章，"
                    "本頁自動導向電子書總目錄。"
                )
                _body_text = f"第 {old_ch} 章的內容已按主題重新分類到第 01–12 章中。"
            else:
                _title = f"第 {old_ch} 章已重新分类｜《坐禅之问答录2》"
                _description = (
                    f"《坐禅之问答录2》第 {old_ch} 章的内容已按主题重新分类到第 01–12 章，"
                    "本页自动导向电子书总目录。"
                )
                _body_text = f"第 {old_ch} 章的内容已按主题重新分类到第 01–12 章中。"
            page = _REDIRECT_TPL.format(
                ch=old_ch,
                suffix=suffix,
                lang="zh-Hant" if is_trad else "zh-Hans",
                title=_title,
                description=_description,
                body_text=_body_text,
                canonical=f"{_SITE_BASE}/index{suffix}.html",
            )
            (DST / f"{old_ch:02d}{suffix}.html").write_text(page, encoding="utf-8")
    print("✅ 舊章節跳轉頁（13-21）完成")

    # sitemap.xml 同步更新（單一產生器：tool/site_chrome/sitemap.py）。
    # 跳轉頁帶 noindex → 產生器會自動排除，不會混進 sitemap。
    import importlib.util as _ilu

    _sitemap_py = ROOT / "tool" / "site_chrome" / "sitemap.py"
    _spec = _ilu.spec_from_file_location("_site_chrome_sitemap", _sitemap_py)
    _sitemap_mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_sitemap_mod)
    _sitemap_mod.write_sitemap()
    print("✅ sitemap.xml 已更新")

    print(f"\n[gen_classified] 完成 → {DST}（{total} 則）")


if __name__ == "__main__":
    main()
