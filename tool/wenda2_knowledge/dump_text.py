#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把語料傾印成「可閱讀的純文字」（含 qid 標記）→ `data/dumps/ch_NN.txt`。

給誰用
------
* 撰寫兩本複習書的人（或 AI）：完整通讀一章時，用這個檔案按 offset/limit 分段讀，
  每一則前面都有 `[qid]`，看到想引用的回答直接記下 qid 與原文。
* 引文必須是**單則回答內的連續子字串**——跨問答拼接會被建置驗證擋下來。
* 注意：語料只收每則問答的**回答首段**（見 `extract_corpus.py`）；
  要看完整多段回答，回 `wenda2_ebook/NN.html` 原書。

用法
----
    python3 tool/wenda2_knowledge/dump_text.py            # 21 章全部傾印
    python3 tool/wenda2_knowledge/dump_text.py --ch 1     # 只傾印第 01 章
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import Corpus  # noqa: E402

OUT = HERE / "data" / "dumps"


def dump_chapter(corpus: Corpus, num: int) -> Path:
    ch = next(c for c in corpus.chapters if c["num"] == num)
    lines = [f"# 第 {num:02d} 章　{ch['title_t']}（繁體）"]
    sec_map = {s["id"]: s["title_t"] for s in ch["sections"]}
    last_sec = None
    for qa in ch["qa"]:
        if qa["section"] != last_sec:
            last_sec = qa["section"]
            lines.append("")
            lines.append(f"## [{last_sec}] {sec_map.get(last_sec, '')}")
        lines.append("")
        meta = f"（{qa['asker']}・{qa['time']}）" if qa["asker"] or qa["time"] else ""
        lines.append(f"◆問 {meta} {qa['qt']}")
        lines.append(f"[{qa['qid']}] {qa['at']}")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"ch_{num:02d}.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ch", type=int, help="只傾印這一章（1–21）")
    args = ap.parse_args()

    corpus = Corpus()
    nums = [args.ch] if args.ch else list(range(1, 22))
    for num in nums:
        path = dump_chapter(corpus, num)
        n = len(next(c for c in corpus.chapters if c["num"] == num)["qa"])
        print(f"OK  {path.relative_to(HERE.parent.parent)}  ({n} 則問答)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
