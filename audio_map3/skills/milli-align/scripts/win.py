#!/usr/bin/env python3
"""win — 印 FunASR 字級視窗（milli-align skill §7.3 逐段判讀用）.

把 [lo,hi] 秒內的 ASR 字元流切成固定寬度的行（每行首印第一個字時間），
供人眼對照段落全文、找最長連續匹配、定 run-onset。

用法：
  win.py --series lengqie --lecture 5 --lo 690 --hi 700 [--width 14]
  win.py --series lengyanjing --lecture 3 --lo 100 --hi 140 --all
  （--all 印全部字元時間含 nan；預設略過 nan 字元）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
from realign_dtw import load_dump, _t_of  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--lecture", required=True)
    ap.add_argument("--lo", type=float, required=True)
    ap.add_argument("--hi", type=float, required=True)
    ap.add_argument("--width", type=int, default=14)
    ap.add_argument("--all", action="store_true", help="含 nan 字元時間")
    args = ap.parse_args()

    d = load_dump(Path(f"/tmp/funasr_cache/{args.series}/{args.lecture}.json"))
    buf = []
    for k, c in enumerate(d["chars"]):
        t = _t_of(d["times"], k)
        if t is None and not args.all:
            continue
        if t is None or args.lo <= t <= args.hi:
            buf.append((t, c))
    if not buf:
        print(f"[{args.lo}–{args.hi}] 無字元")
        return
    for i in range(0, len(buf), args.width):
        ch = buf[i:i + args.width]
        t0 = ch[0][0]
        t0s = f"{t0:8.2f}" if t0 is not None else "   nan  "
        print(f"[{t0s}] {''.join(c for _, c in ch)}")


if __name__ == "__main__":
    main()
