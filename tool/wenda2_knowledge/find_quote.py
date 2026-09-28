#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 `data/corpus.json` 裡找可引用的逐字回答（撰寫兩本複習書時的檢索工具）。

用法
----
    # 跨全書找含關鍵字的問答
    python3 tool/wenda2_knowledge/find_quote.py 迴向 --ch 3,6 --n 8
    python3 tool/wenda2_knowledge/find_quote.py "冤親債主" --minlen 30 --maxlen 200

    # 印出某則回答的所有句子（帶編號），照著挑
    python3 tool/wenda2_knowledge/find_quote.py --qid 04/question-f6fd885db29a

    # 直接抓某幾句，輸出可直接貼進 QT() 的繁體原文
    python3 tool/wenda2_knowledge/find_quote.py --qid 04/question-f6fd885db29a --sent 2,3

輸出都是「繁體原文 + qid」，引文用 QT(qid, "繁體原文") 引用；
建置時 `common.py` 會再用 corpus 逐字驗證一次。

提醒：語料只收每則問答的**回答首段**（見 `extract_corpus.py`），
句號 1 通常是作者名 `Taiguanglin`，正文從句 2 起算。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import Corpus  # noqa: E402
from quotepick import sentences  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*", help="關鍵字（找包含它的問答）")
    ap.add_argument("--qid", help="指定問答，印出帶編號的句子")
    ap.add_argument("--sent", help="配合 --qid：句號（如 2,3,4）")
    ap.add_argument("--ch", help="限章號，逗號分隔（如 3,6）")
    ap.add_argument("--n", type=int, default=10, help="最多列出幾筆")
    ap.add_argument("--minlen", type=int, default=0)
    ap.add_argument("--maxlen", type=int, default=10 ** 9)
    args = ap.parse_args()

    corpus = Corpus()

    if args.qid:
        qa = corpus.get(args.qid)
        sents_t, sents_s = sentences(corpus, args.qid)
        print(f"{qa['qid']}（繁 {len(qa['at'])} 字・第{qa['ch']:02d}章）")
        print(f"  問（{qa['asker']}・{qa['time']}）：{qa['qt'][:120]}")
        if args.sent:
            idx = [int(x) for x in args.sent.split(",")]
            text = "".join(sents_t[n - 1] for n in idx)
            print(f"\nQT(\"{qa['qid']}\",")
            print(f'   "{text}",')
            print(f'   topic="…"),')
        else:
            for i, (t, s) in enumerate(zip(sents_t, sents_s), 1):
                print(f"  {i:>3}. {t}")
        return 0

    if not args.keys:
        ap.error("請給關鍵字或 --qid")
    chs = {int(x) for x in args.ch.split(",")} if args.ch else None
    hits = 0
    for ch in corpus.chapters:
        if chs and ch["num"] not in chs:
            continue
        for qa in ch["qa"]:
            at = qa["at"]
            if not (args.minlen <= len(at) <= args.maxlen):
                continue
            hay = qa["qt"] + "\n" + at
            if all(k in hay for k in args.keys):
                hits += 1
                print(f"\n◆ {qa['qid']}（第{ch['num']:02d}章 {ch['title_t']}，{len(at)} 字）")
                print(f"  問（{qa['asker']}・{qa['time']}）：{qa['qt'][:120]}")
                print(f"  答：{at[:500]}")
                if hits >= args.n:
                    print(f"\n（已達 --n={args.n}，其餘省略）")
                    return 0
    print(f"\n合計 {hits} 筆")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
