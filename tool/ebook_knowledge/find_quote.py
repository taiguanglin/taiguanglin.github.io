#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 `data/corpus.json` 裡找可引用的逐字段落（撰寫兩本複習書時的檢索工具）。

用法
----
    # 跨全書找含關鍵字的引用單位
    python3 tool/ebook_knowledge/find_quote.py 妄想 --book 1,4 --n 8
    python3 tool/ebook_knowledge/find_quote.py "耳根圆通" --minlen 30 --maxlen 200

    # 印出某引用單位的所有句子（帶編號），照著挑
    python3 tool/ebook_knowledge/find_quote.py --pid 01/p-se5fc701c

    # 直接抓某幾句，輸出可直接貼進 PT() 的繁體原文
    python3 tool/ebook_knowledge/find_quote.py --pid 01/p-se5fc701c --sent 2,3

輸出都是「繁體原文 + pid」，引文用 PT(pid, "繁體原文") 引用；
建置時 `common.py` 會再用 corpus 逐字驗證一次。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import Corpus  # noqa: E402
from quotepick import SENT_SPLIT  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*", help="關鍵字（找包含它的引用單位）")
    ap.add_argument("--pid", help="指定引用單位，印出帶編號的句子")
    ap.add_argument("--sent", help="配合 --pid：句號（如 2,3,4）")
    ap.add_argument("--book", help="限書號，逗號分隔（如 1,4）")
    ap.add_argument("--n", type=int, default=10, help="最多列出幾筆")
    ap.add_argument("--minlen", type=int, default=0)
    ap.add_argument("--maxlen", type=int, default=10 ** 9)
    args = ap.parse_args()

    corpus = Corpus()

    if args.pid:
        blk = corpus.get(args.pid)
        sents_t = [s for s in SENT_SPLIT.split(blk["t"]) if s.strip()]
        sents_s = [s for s in SENT_SPLIT.split(blk["s"]) if s.strip()]
        print(f"{blk['pid']}（繁 {len(blk['t'])} 字）")
        print(f"  原文段落：{blk['t'][:160]}…")
        if args.sent:
            idx = [int(x) for x in args.sent.split(",")]
            text = "".join(sents_t[n - 1] for n in idx)
            print(f"\nPT(\"{blk['pid']}\",")
            print(f'   "{text}",')
            print(f'   topic="…"),')
        else:
            for i, (t, s) in enumerate(zip(sents_t, sents_s), 1):
                print(f"  {i:>3}. {t}")
        return 0

    if not args.keys:
        ap.error("請給關鍵字或 --pid")
    books = {int(x) for x in args.book.split(",")} if args.book else None
    hits = 0
    for book in corpus.books:
        if books and book["num"] not in books:
            continue
        for blk in book["blocks"]:
            t = blk["t"]
            if not (args.minlen <= len(t) <= args.maxlen):
                continue
            if all(k in t for k in args.keys):
                hits += 1
                print(f"\n◆ {blk['pid']}（{book['short_t']}，{len(t)} 字）")
                print(f"  {t[:500]}")
                if hits >= args.n:
                    print(f"\n（已達 --n={args.n}，其餘省略）")
                    return 0
    print(f"\n合計 {hits} 筆")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
