#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""從 `ebook/`（坐禪系列＋講經系列十本書）抽出語料 → `data/corpus.json`。

為什麼需要這一步
----------------
兩本複習電子書（《重點知識》《另一個讀法》）都要「逐字引用」Tai 師父原文，
而引文必須與線上電子書完全一致。把十本書的 HTML 抽成一份結構化語料：

1. 分析（統計、找主題、挑引文）不需要反覆解析 6MB HTML。
2. 建置時對每條引文做「逐字比對」，比對不到就 exit 1——引文是複習書的骨頭。
3. 語料以段落 DOM id 為穩定單位，日後電子書文字更新只需重跑本檔。

十本書有兩種內容格式
--------------------
* **段落體**（01、03–10）：`<h2/h3/h4 id="sXXX">` 章節 ＋ `<p id="p-sXXX" class="para-block">`。
  引用單位＝段落。
* **問答體**（02《坐禅之问答录》）：`<article class="qa-pair">` 內含
  `div.question#question-sXXX` 與 `div.answer#answer-sXXX`。引用單位＝回答。

輸出（`data/corpus.json`）
-------------------------
    {
      "generated_from": "ebook/*.html",
      "books": [
        {
          "num": 1, "title_s": "01《坐禅》", "title_t": "01《坐禪》",
          "short_s": "坐禅", "short_t": "坐禪",
          "headings": [ {"id": "s0dbff212", "level": 2, "title_s": "推荐序", "title_t": "推薦序"} ],
          "blocks": [ BLOCK, ... ]
        }, ...
      ]
    }

    BLOCK（段落體）= {
      "pid": "01/p-se5fc701c",   # 穩定識別碼（書號 + 原文 DOM id）
      "book": 1, "kind": "para",
      "path": ["s0dbff212", ...], # 歸屬的章節標題 id（h2→h3→h4，由外而內）
      "s": "...", "t": "...",     # 段落文字：簡體／繁體
      "audio": {"start":…,"end":…} or null, "imgs": [...]
    }

    BLOCK（問答體 02）= {
      "pid": "02/answer-s146d45af",
      "book": 2, "kind": "qa",
      "path": [...],
      "asker": "白龙腾顶化乌云", "time": "2014-02-25 12:05",
      "q": "...", "qt": "...",    # 問題：簡體／繁體
      "s": "...", "t": "..."      # 回答：簡體／繁體（回答者恆為 Taiguanglin）
    }

用法
----
    python3 tool/ebook_knowledge/extract_corpus.py            # 產生 data/corpus.json
    python3 tool/ebook_knowledge/extract_corpus.py --stats    # 只印統計
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EBOOK = ROOT / "ebook"
OUT = Path(__file__).resolve().parent / "data" / "corpus.json"

TAG_RE = re.compile(r"<[^>]+>")


def plain(fragment: str) -> str:
    """HTML 片段 → 純文字：`<br/>`→換行，標籤剝除，實體還原。"""
    text = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    text = TAG_RE.sub("", text)
    text = unescape(text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class BookParser(HTMLParser):
    """把一本書的 HTML 拆成（標題層級, 引用單位 blocks）。

    只認得 books2ebook 實際輸出的結構：
      `<h1 id="sXXX">書名(N)</h1>` → 書名
      `<h2|3|4 id="sXXX">` → 章節標題（`chapter-toc-header` 除外）
      `<p id="p-sXXX" class="para-block">` → 段落（可能有 data-start/data-end 屬性）
      `<article class="qa-pair">` → 問答（02《坐禅之问答录》）
    每個標題與引用單位都記 `pos`（starttag 序號），維持文件順序。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.book_title = ""
        self.headings: list[dict] = []      # {id, level, title, pos}
        self.blocks: list[dict] = []
        self._pos = 0
        self._path: list[str] = []          # 目前章節標題 id 路徑（外→內）
        self._cur: dict | None = None       # 目前段落／問答
        self._side: str | None = None       # 'q' | 'a'（問答體用）
        self._field: str | None = None      # 'h1' | 'heading' | 'asker' | 'time' | 'text'
        self._buf: list[str] = []
        self._heading_id = ""
        self._heading_level = 0

    def _path_level(self, hid: str) -> int:
        for h in self.headings:
            if h["id"] == hid:
                return h["level"]
        return 9

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        self._pos += 1
        if tag == "h1" and a.get("id"):
            self._field, self._buf = "h1", []
        elif tag in ("h2", "h3", "h4") and a.get("id") and a["id"] != "chapter-toc-header":
            level = int(tag[1])
            while self._path and self._path_level(self._path[-1]) >= level:
                self._path.pop()
            self._path.append(a["id"])
            self._heading_id, self._heading_level = a["id"], level
            self._field, self._buf = "heading", []
        elif tag == "p" and "para-block" in cls and a.get("id"):
            self._cur = {
                "kind": "para", "dom_id": a["id"], "path": list(self._path),
                "s": "", "audio": None, "imgs": [],
            }
            if a.get("data-start"):
                self._cur["audio"] = {"start": a.get("data-start", ""),
                                      "end": a.get("data-end", "")}
            self._field, self._buf = "text", []
        elif tag == "article" and "qa-pair" in cls:
            self._cur = {
                "kind": "qa", "dom_id": "", "path": list(self._path),
                "asker": "", "time": "", "q": "", "s": "", "imgs": [],
            }
        elif self._cur is not None and self._cur["kind"] == "qa":
            if a.get("id") and str(a["id"]).startswith("answer") and not self._cur["dom_id"]:
                self._cur["dom_id"] = a["id"]
            if "question" in cls and str(a.get("id", "")).startswith("question"):
                self._side, self._field, self._buf = "q", None, []
            elif "answer" in cls:
                self._side, self._field, self._buf = "a", None, []
            elif "questioner" in cls:
                self._field = "asker"
            elif "answer-time" in cls:
                self._field = "time"
            elif "question-text" in cls or "answer-text" in cls:
                self._field = "text"
        if tag == "img" and self._cur is not None:
            src = a.get("src", "")
            if src and src not in self._cur["imgs"]:
                self._cur["imgs"].append(src)

    def handle_endtag(self, tag):
        # 欄位收字只在自己的「容器標籤」收尾時進行——行內標籤（<strong>、<em>…）
        # 的 endtag 一律忽略，否則含行內標籤的段落會被攔腰截斷。
        if self._field == "h1" and tag == "h1":
            self.book_title = re.sub(r"\(\d+\)\s*$", "",
                                     "".join(self._buf).strip()).strip()
            self._field, self._buf = None, []
            return
        if self._field == "heading" and tag in ("h2", "h3", "h4"):
            text = re.sub(r"\(\d+\)\s*$", "", "".join(self._buf).strip()).strip()
            self.headings.append({
                "id": self._heading_id, "level": self._heading_level, "title": text,
            })
            self._field, self._buf = None, []
            return
        if tag == "p" and self._field == "text" and self._cur is not None \
                and self._cur["kind"] == "para":
            self._cur["s"] = "".join(self._buf).strip()
            if self._cur["s"]:
                self.blocks.append(self._cur)
            self._cur, self._field, self._buf = None, None, []
            return
        if tag == "article" and self._cur is not None:
            if self._cur["dom_id"] and self._cur["s"]:
                self.blocks.append(self._cur)
            self._cur, self._side, self._field, self._buf = None, None, None, []
            return
        if self._cur is not None and self._cur["kind"] == "qa" \
                and self._field in ("asker", "time", "text"):
            if tag not in ("span", "div"):
                return  # 行內標籤的 endtag：不收字
            if self._field in ("asker", "time") and tag != "span":
                return
            if self._field == "text" and tag != "div":
                return
            text = "".join(self._buf).strip()
            if self._field == "asker":
                self._cur["asker"] = text
            elif self._field == "time":
                self._cur["time"] = text
            elif self._field == "text":
                if self._side == "q":
                    self._cur["q"] = text
                elif self._side == "a":
                    self._cur["s"] = text
            self._field, self._buf = None, []

    def handle_data(self, data):
        if self._field is not None:
            self._buf.append(data)


def read_book(num: int, trad: bool) -> dict:
    name = f"{num:02d}_trad.html" if trad else f"{num:02d}.html"
    path = EBOOK / name
    if not path.exists():
        sys.exit(f"找不到書檔：{path}")
    parser = BookParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return {
        "title": re.sub(r"\(\d+\)\s*$", "", parser.book_title).strip(),
        "headings": parser.headings,
        "blocks": parser.blocks,
    }


def strip_book_no(title: str) -> str:
    """`01《坐禅》`→`《坐禅》`；`感恩与讲经`→`感恩与讲经`。"""
    t = re.sub(r"^\d+\s*", "", title).strip()
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true", help="只印統計，不寫檔")
    args = ap.parse_args()

    books: list[dict] = []
    for num in range(1, 11):
        s = read_book(num, trad=False)
        t = read_book(num, trad=True)
        if len(s["blocks"]) != len(t["blocks"]):
            sys.exit(f"書 {num:02d} 簡繁引用單位數不一致：{len(s['blocks'])} vs {len(t['blocks'])}")
        if len(s["headings"]) != len(t["headings"]):
            sys.exit(f"書 {num:02d} 簡繁標題數不一致：{len(s['headings'])} vs {len(t['headings'])}")
        for bs, bt in zip(s["blocks"], t["blocks"]):
            if bs["dom_id"] != bt["dom_id"]:
                sys.exit(f"書 {num:02d}：簡繁 DOM id 不一致 {bs['dom_id']} vs {bt['dom_id']}")
        for hs, ht in zip(s["headings"], t["headings"]):
            if hs["id"] != ht["id"] or hs["level"] != ht["level"]:
                sys.exit(f"書 {num:02d}：簡繁標題結構不一致 {hs['id']} vs {ht['id']}")

        blocks = []
        for bs, bt in zip(s["blocks"], t["blocks"]):
            b = {
                "pid": f"{num:02d}/{bs['dom_id']}",
                "book": num,
                "kind": bs["kind"],
                "path": bs["path"],
                "s": bs["s"],
                "t": bt["s"],
                "imgs": bs["imgs"],
            }
            if bs["kind"] == "qa":
                b.update({
                    "asker": bs["asker"] or bt["asker"],
                    "time": bs["time"],
                    "q": bs["q"], "qt": bt["q"],
                })
            else:
                b["audio"] = bs.get("audio")
            blocks.append(b)
        heads = [{
            "id": hs["id"], "level": hs["level"],
            "title_s": hs["title"], "title_t": ht["title"],
        } for hs, ht in zip(s["headings"], t["headings"])]
        books.append({
            "num": num,
            "title_s": s["title"],
            "title_t": t["title"],
            "short_s": strip_book_no(s["title"]),
            "short_t": strip_book_no(t["title"]),
            "headings": heads,
            "blocks": blocks,
        })

    n_blocks = sum(len(b["blocks"]) for b in books)
    n_chars = sum(len(x["s"]) for b in books for x in b["blocks"])
    if args.stats:
        for b in books:
            npara = sum(1 for x in b["blocks"] if x["kind"] == "para")
            nqa = sum(1 for x in b["blocks"] if x["kind"] == "qa")
            ch = sum(len(x["s"]) for x in b["blocks"])
            print(f"{b['num']:02d} {b['short_s']:<18} 段落 {npara:>5}  問答 {nqa:>4}"
                  f"  標題 {len(b['headings']):>3}  {ch:>7,} 字")
        print(f"\n合計：{len(books)} 書、{n_blocks} 引用單位、{n_chars:,} 字")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"generated_from": "ebook/*.html", "books": books},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"OK  {OUT.relative_to(ROOT)}：{len(books)} 書、{n_blocks} 引用單位、{n_chars:,} 字")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
