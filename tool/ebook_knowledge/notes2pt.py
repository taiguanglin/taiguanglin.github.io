#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""notes2pt.py — 把「pid + 描述」筆記轉成逐字 PT() 行。

背景：閱讀 subagent 的空間有限，逐字抄錄引文（＋自我驗證）會把它的上下文撐爆。
改讓 subagent 只記：

    - 01/p-sXXXX :: front :: 一句話描述

本腳本從 corpus 機械抽取該 pid 的原文，生成 PT() 行——逐字性由構造保證，
之後仍交由 audit.py 再驗一次。

抽取規則：
  front — 從段首起，逐句累加，加下一句會超過 --max（預設 230）字就停；
          至少保留 1 句。
  back  — 從段尾反向逐句累加（句子順序不變），同樣不超過 --max。
  full — 整段 ≤ --max-full（預設 300）字取整段，否則同 front。
  mid::關鍵字 — 從關鍵字所在句起向後取句（每句先找得到才有效）。

用法：
  python3 notes2pt.py <notes.md> [--max 230] [--max-full 300]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CORPUS_PATH, Corpus  # noqa: E402
from quotepick import sentences  # noqa: E402

LINE_RE = re.compile(
    r"^\s*[-*]\s+`?(\d{2}/(?:p|answer)-s[0-9a-f]{8})`?\s*::\s*(front|back|full|mid)(?:::([^:\s]+))?\s*::\s*(.+)$"
)


def extract(sents: list[str], mode: str, keyword: str, mx: int, mx_full: int) -> str | None:
    if not sents:
        return None
    if mode == "full":
        text = "".join(sents)
        if len(text) <= mx_full:
            return text
        mode = "front"
    if mode == "front":
        buf = sents[0]
        for s in sents[1:]:
            if len(buf) + len(s) > mx:
                break
            buf += s
        return buf
    if mode == "back":
        buf = sents[-1]
        for s in reversed(sents[:-1]):
            if len(buf) + len(s) > mx:
                break
            buf = s + buf
        return buf
    if mode == "mid":
        if not keyword:
            return None
        idx = [i for i, s in enumerate(sents) if keyword in s]
        if not idx:
            return None
        i = idx[0]
        buf = sents[i]
        for s in sents[i + 1:]:
            if len(buf) + len(s) > mx:
                break
            buf += s
        return buf
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("notes")
    ap.add_argument("--max", type=int, default=230)
    ap.add_argument("--max-full", type=int, default=300)
    args = ap.parse_args()

    corpus = Corpus()
    src = Path(args.notes).read_text(encoding="utf-8")
    current_theme = ""
    out: list[str] = []
    n_total = n_miss = 0
    for raw in src.splitlines():
        theme_m = re.match(r"^##\s*主題[：:]\s*(.+)$", raw)
        if theme_m:
            current_theme = theme_m.group(1).strip()
            out.append("")
            out.append(f"# {current_theme}")
            continue
        m = LINE_RE.match(raw)
        if not m:
            continue
        pid, mode, kw, desc = m.group(1), m.group(2), (m.group(3) or "").strip(), m.group(4).strip()
        # 容錯：`- pid :: mid :: 關鍵字 :: 描述`（漏接的雙冒號）→ 關鍵字在 desc 第一欄
        if mode == "mid" and not kw and "::" in desc:
            first, _, rest = desc.partition("::")
            if first.strip() and rest.strip():
                kw, desc = first.strip(), rest.strip()
        blk = corpus.by_pid.get(pid)
        if blk is None:
            print(f"  ✗ 找不到 pid：{pid}", file=sys.stderr)
            n_miss += 1
            continue
        sents = sentences(corpus, pid)[0]
        q = extract(sents, mode, kw, args.max, args.max_full)
        if not q or len(q.strip()) < 10:
            print(f"  ✗ 抽取失敗：{pid}（{mode}）", file=sys.stderr)
            n_miss += 1
            continue
        n_total += 1
        # 描述截短作 topic；太長就取前 12 字
        topic = re.sub(r"\s+", "", desc)[:12] or current_theme[:12]
        out.append(f'PT("{pid}", "{q}", topic="{topic}"),')
        print(f"  ✓ {pid} [{mode}] {len(q)}字 ← {desc[:30]}")
    print(f"\n生成 {n_total} 條 PT()，失敗 {n_miss} 條", file=sys.stderr)
    if out:
        print("\n".join(out))
    return 1 if n_miss else 0


if __name__ == "__main__":
    raise SystemExit(main())
