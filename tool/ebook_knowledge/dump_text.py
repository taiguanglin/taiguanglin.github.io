#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把語料傾印成「可閱讀的純文字」（含 pid 標記）→ `data/dumps/book_NN.txt`。

給誰用
------
* 撰寫兩本複習書的人（或 AI）：完整通讀一本書時，用這個檔案按 offset/limit 分段讀，
  每一段前面都有 `[pid]`，看到想引用的段落直接記下 pid 與原文。
* 引文必須是**單一引用單位內的連續子字串**——跨段拼接會被建置驗證擋下來。

用法
----
    python3 tool/ebook_knowledge/dump_text.py            # 十本書全部傾印
    python3 tool/ebook_knowledge/dump_text.py --book 1    # 只傾印書 01
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import Corpus  # noqa: E402

OUT = HERE / "data" / "dumps"


def dump_book(corpus: Corpus, num: int) -> Path:
    book = next(b for b in corpus.books if b["num"] == num)
    head_title = {h["id"]: h for h in book["headings"]}
    lines = [f"# 書 {num:02d}　{book['title_t']}（繁體）"]
    last_path: list[str] = []
    for blk in book["blocks"]:
        # 只在「進入新的標題」時印標題行（避免每段重複整條路徑）
        for i, hid in enumerate(blk["path"]):
            h = head_title.get(hid)
            if h and (i >= len(last_path) or last_path[i] != hid):
                lines.append("")
                lines.append(f"{'#' * (h['level'] + 1)} [{hid}] {h['title_t']}")
        last_path = blk["path"]
        if blk["kind"] == "qa":
            q = blk.get("qt", "")
            meta = f"（{blk.get('asker', '')}・{blk.get('time', '')}）"
            lines.append("")
            lines.append(f"◆問 {meta} {q}")
            lines.append(f"[{blk['pid']}] {blk['t']}")
        else:
            lines.append(f"[{blk['pid']}] {blk['t']}")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"book_{num:02d}.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=int, help="只傾印這一本（1–10）")
    args = ap.parse_args()

    corpus = Corpus()
    nums = [args.book] if args.book else list(range(1, 11))
    for num in nums:
        path = dump_book(corpus, num)
        n = sum(1 for b in corpus.books if b["num"] == num for _ in b["blocks"])
        print(f"OK  {path.relative_to(HERE.parent.parent)}  ({n} 引用單位)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
