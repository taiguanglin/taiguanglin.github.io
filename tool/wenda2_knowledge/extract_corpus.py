#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`wenda2_ebook/*.html` → `data/corpus.json`（問答錄2 語料）。

語料結構
--------
    {
      "generated_from": "wenda2_ebook/*.html",
      "chapters": [
        {
          "num": 1, "title_s": "自性与意识", "title_t": "自性與意識",
          "sections": [{"id", "title_s", "title_t", "count", "claimed"}],
          "qa": [
            {
              "qid": "01/question-e971784bcf55",   # {章號:02d}/{question DOM id}
              "ch": 1, "section": "zi-xing-…",     # 所屬小節（往前找最近的 h2/h3）
              "asker": "慧日永明", "time": "2024-03-01 13:18",
              "q":  "…簡體問", "qt": "…繁體問",
              "a":  "…簡體答", "at": "…繁體答",
              "audio": {"file","start","end","label"} | null,
              "imgs": ["assets/images/….webp", …],
            }, …
          ],
        }, …
      ]
    }

引用單位＝**一則問答**。`a`／`at` 取「該則問答**最後一個** answer-text 區塊的
**第一段**」（`<br/>` 分段）。這是 2026-09 對 `wenda2_ebook/` 的萃取慣例——
多段問答只收最後一問的首段回答；引用永遠是原書的逐字子字串，此性質由
`common.verify_book()` 在建置時保證。

繁簡：`q`/`a` 取自 `NN.html`，`qt`/`at` 取自 `NN_trad.html`；兩頁由
word2ebook 從同一來源產生，文章一一對應。

用法
----
    python3 tool/wenda2_knowledge/extract_corpus.py            # 重建語料
    python3 tool/wenda2_knowledge/extract_corpus.py --stats    # 只印統計
"""

from __future__ import annotations

import argparse
import html as htmlmod
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EBOOK = ROOT / "wenda2_ebook"
OUT = HERE / "data" / "corpus.json"

ART_RE = re.compile(r'<article class="qa-pair">(.*?)</article>', re.S)
QID_RE = re.compile(r'id="(question-[0-9a-f]+(?:-\d+)?)"')
QT_RE = re.compile(r'<div class="question-text">(.*?)</div>', re.S)
AT_RE = re.compile(r'<div class="answer-text">(.*?)</div>', re.S)
QMETA_RE = re.compile(r'<div class="question-meta">(.*?)</div>', re.S)
AMETA_RE = re.compile(r'<div class="answer-meta">(.*?)</div>', re.S)
ANS_SPLIT_RE = re.compile(r'<div class="answer"[^>]*>')
ASKER_RE = re.compile(r'<span class="questioner">(.*?)</span>', re.S)
QTIME_RE = re.compile(r'<span class="question-time">(.*?)</span>', re.S)
IMG_RE = re.compile(r'<img [^>]*?src="([^"]+)"')
AUDIO_RE = re.compile(
    r'data-audio="([^"]+)" data-end="([^"]+)" data-label="([^"]+)" data-start="([^"]+)"'
)
H_RE = re.compile(r'<h([23]) id="([^"]+)">(.*?)</h\1>', re.S)
H1_RE = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S)
COUNT_RE = re.compile(r'<span class="chapter-qa-count">\((\d+)\)</span>')
BTN_ATTR_RES = {
    "file": re.compile(r'data-audio="([^"]*)"'),
    "end": re.compile(r'data-end="([^"]*)"'),
    "label": re.compile(r'data-label="([^"]*)"'),
    "start": re.compile(r'data-start="([^"]*)"'),
}
# Word 彙總章（01–12）：回答一律帶作者署名（answer-meta 自帶時間的
# 「跟帖回答」除外）。PDF 月章（13–21）：單一回答區塊才署名，
# 多區塊回答只收最後一塊、不署名——與 2026-09 語料慣例一致。
WORD_CHAPTERS = 12


def strip_tags(s: str) -> str:
    return htmlmod.unescape(re.sub(r"<[^>]+>", "", s))


def first_line(s: str) -> str:
    """`<br/>` 分段的第一段，HTML 反轉義。"""
    return htmlmod.unescape(s.replace("<br/>", "\n").strip().split("\n")[0].strip())


def text_up_to_count(s: str) -> str:
    """標題文字（去掉 QA 數量徽章）。"""
    return strip_tags(COUNT_RE.sub("", s)).strip()


def section_title(s: str) -> str:
    """小節標題文字——**保留**「(NN)」數量，去掉章號／年份前綴數字
    （語料慣例：與原書 h1 一致，前導數字屬於頁面裝飾）。"""
    return re.sub(r"^\d+", "", strip_tags(s)).strip()


def parse_audio(art: str) -> dict | None:
    """播放鈕 → {file, start, end, label}（屬性順序不保證，逐一找）。"""
    btn = re.search(r"<button[^>]*qa-play[^>]*>", art)
    if not btn:
        return None
    tag = htmlmod.unescape(btn.group(0))
    vals = {}
    for key, rex in BTN_ATTR_RES.items():
        m = rex.search(tag)
        if not m:
            return None
        vals[key] = m.group(1)
    return {"file": vals["file"], "start": vals["start"],
            "end": vals["end"], "label": vals["label"]}


def extract_chapter(num: int) -> dict:
    s_html = (EBOOK / f"{num:02d}.html").read_text(encoding="utf-8")
    t_html = (EBOOK / f"{num:02d}_trad.html").read_text(encoding="utf-8")

    m = H1_RE.search(s_html)
    title_s = re.sub(r"^\d+", "", text_up_to_count(m.group(1)))
    m = H1_RE.search(t_html)
    title_t = re.sub(r"^\d+", "", text_up_to_count(m.group(1)))

    # 小節：所有 h2/h3（除了目錄頭），保留文件順序
    sections = []
    for _lvl, sid, body in H_RE.findall(s_html):
        if sid == "chapter-toc-header":
            continue
        claimed = COUNT_RE.search(body)
        sections.append({
            "id": sid,
            "title_s": section_title(body),
            "title_t": "",  # 稍後用繁體頁補
            "count": 0,
            "claimed": int(claimed.group(1)) if claimed else 0,
        })
    for sec in sections:
        m = re.search(
            rf'<h[23] id="{re.escape(sec["id"])}">(.*?)</h[23]>', t_html, re.S
        )
        sec["title_t"] = section_title(m.group(1)) if m else sec["title_s"]

    # 每則問答：往前找最近的 h2/h3 當小節
    events: list[tuple[int, str]] = []  # (位置, section id)
    for m in H_RE.finditer(s_html):
        _lvl, sid, _body = m.groups()
        if sid != "chapter-toc-header":
            events.append((m.start(), sid))

    qa = []
    s_arts = list(ART_RE.finditer(s_html))
    t_arts = list(ART_RE.finditer(t_html))
    if len(s_arts) != len(t_arts):
        sys.exit(f"第 {num:02d} 章：繁簡頁文章數不一致（{len(s_arts)} vs {len(t_arts)}）")

    sec_count: dict[str, int] = {}
    for sm, tm in zip(s_arts, t_arts):
        art_s, art_t = sm.group(1), tm.group(1)
        qid_tail = QID_RE.search(art_s).group(1)
        qid_tail_t = QID_RE.search(art_t).group(1)
        if qid_tail != qid_tail_t:
            sys.exit(f"第 {num:02d} 章：繁簡文章 id 不一致（{qid_tail} vs {qid_tail_t}）")

        section = next((sid for pos, sid in reversed(events) if pos < sm.start(1)), "")

        qmeta = QMETA_RE.search(art_s).group(1)
        asker_m = ASKER_RE.search(qmeta)
        asker = first_line(asker_m.group(1)) if asker_m else ""
        qtime = QTIME_RE.search(qmeta)
        time = strip_tags(qtime.group(1)) if qtime else ""

        q = first_line(QT_RE.findall(art_s)[-1])
        qt = first_line(QT_RE.findall(art_t)[-1])

        ats_s = AT_RE.findall(art_s)
        ats_t = AT_RE.findall(art_t)
        ameta = AMETA_RE.search(art_s).group(1)
        atime = QTIME_RE.search(ameta)
        if atime:
            # 「跟帖回答」：answer-meta 自帶回答時間——時間欄改記
            # 「Taiguanglin\n回答時間」（與 2026-09 語料慣例一致）。
            time = "Taiguanglin\n" + strip_tags(atime.group(1))
            prefix = False
        elif num <= WORD_CHAPTERS:
            prefix = True
        else:
            # PDF 月章：文章可能有多個 answer 區塊（同一則回答分次貼）。
            # 署名規則看**最後一個** answer 區塊：只有一段文字才署名。
            last_block = ANS_SPLIT_RE.split(art_s)[-1]
            last_ameta = AMETA_RE.search(last_block)
            prefix = (
                len(AT_RE.findall(last_block)) == 1
                and not (last_ameta and "question-time" in last_ameta.group(1))
            )
        a = ("Taiguanglin\n\n" if prefix else "") + first_line(ats_s[-1])
        at = ("Taiguanglin\n\n" if prefix else "") + first_line(ats_t[-1])

        audio = parse_audio(art_s)
        imgs = [htmlmod.unescape(x) for x in IMG_RE.findall(art_s)]

        sec_count[section] = sec_count.get(section, 0) + 1
        qa.append({
            "qid": f"{num:02d}/{qid_tail}",
            "ch": num,
            "section": section,
            "asker": asker,
            "time": time,
            "q": q,
            "qt": qt,
            "a": a,
            "at": at,
            "audio": audio,
            "imgs": imgs,
        })

    for sec in sections:
        sec["count"] = sec_count.get(sec["id"], 0)

    return {
        "num": num,
        "title_s": title_s,
        "title_t": title_t,
        "sections": sections,
        "qa": qa,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true", help="只印統計，不寫檔")
    args = ap.parse_args()

    chapters = [extract_chapter(n) for n in range(1, 22)]
    data = {"generated_from": "wenda2_ebook/*.html", "chapters": chapters}

    total = sum(len(c["qa"]) for c in chapters)
    print(f"21 章／{total} 則問答／"
          f"{sum(len(c['sections']) for c in chapters)} 小節")
    if args.stats:
        for c in chapters:
            print(f"  ch{c['num']:02d} {c['title_t'][:22]:24s} "
                  f"sections:{len(c['sections']):3d} qa:{len(c['qa']):4d}")
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"語料已寫出：{OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
