#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""驗證 data/notes/book_*.md 的每一條筆記都對得上 dumps/ 原文。

為什麼需要這支：`notes2pt.py` 對「pid 不在 dump 裡」的條目**不會報失敗**，
只是少產生一條 PT()（靜默丟失）；關鍵字取自下一段的條目則會報「抽取失敗」。
兩種都是實際發生過的缺陷，所以在整合前一律先跑這支。

檢查三件事：
  1. 條目數 == 對應 pt_bank 的 PT() 條數（沒有靜默丟失）；
  2. pid 逐字存在於 dump；
  3. `mid::關鍵字` 必須是「該 pid 那一段」裡逐字連續出現的字串。

用法：
    python3 tool/ebook_knowledge/check_notes.py            # 全部
    python3 tool/ebook_knowledge/check_notes.py book_09c3  # 指定檔案（可多個）
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTES = HERE / "data" / "notes"
DUMPS = HERE / "data" / "dumps"

# pid 形式不只一種：`09/p-sXXXX`、`02/answer-sXXXX`、`04/p-sXXXX`…
LINE_RE = re.compile(r"^- `([^`]+)` :: (\S+)(?:\s*::\s*(.*))?$")
PARA_RE = re.compile(r"\[([^\]]+)\]\s*(.*?)(?=\n\[|\Z)", re.S)


def load_paragraphs() -> dict[tuple[str, str], str]:
    paras: dict[str, str] = {}
    for dump in DUMPS.glob("book_*.txt"):
        text = dump.read_text(encoding="utf-8")
        for m in PARA_RE.finditer(text):
            paras[m.group(1)] = m.group(2)
    return paras


def main(argv: list[str]) -> int:
    paras = load_paragraphs()
    wanted = argv or None
    files = sorted(NOTES.glob("book_*.md"))
    if wanted:
        files = [f for f in files if f.stem in wanted]
        if not files:
            print(f"找不到筆記檔：{wanted}", file=sys.stderr)
            return 2

    problems: list[str] = []
    for note in files:
        lines = note.read_text(encoding="utf-8").splitlines()
        entries = [l for l in lines if l.startswith("- `")]
        bank = NOTES / note.name.replace("book_", "pt_bank_")
        n_bank = (
            len([l for l in bank.read_text(encoding="utf-8").splitlines()
                 if l.startswith("PT(")])
            if bank.exists() else -1
        )
        tag = ""
        if n_bank != len(entries):
            tag = f"  ← 筆記 {len(entries)} / bank {n_bank} 不一致"
            problems.append(f"{note.name}: 筆記 {len(entries)} 條但 bank 只有 {n_bank} 條"
                            f"（pid 對不上時 notes2pt.py 會靜默跳過）")
        print(f"{note.name}: {len(entries)} 條 / bank {n_bank} 條{tag}")

        for line in entries:
            m = LINE_RE.match(line)
            if not m:
                problems.append(f"{note.name}: 行格式不符 → {line[:60]}")
                continue
            pid, mode, _desc = m.groups()
            para = paras.get(pid)
            if para is None:
                problems.append(f"{note.name}: {pid} 不在 dump 中")
                continue
            if len(para.strip()) < 10:   # notes2pt.py 的門檻是 len(q.strip()) < 10
                problems.append(f"{note.name}: {pid} 的段落只有 {len(para.strip())} 字"
                                f"（<10，notes2pt.py 會整條靜默跳過）")
            if mode.startswith("mid::"):
                kw = mode[5:]
                if kw not in para:
                    problems.append(f"{note.name}: {pid} 的關鍵字「{kw}」"
                                    f"不在本段（是否取自下一段？）")

    if problems:
        print(f"\n✗ 問題 {len(problems)} 條：")
        for p in problems:
            print("  -", p)
        return 1
    print("\nNOTE CHECK OK：所有筆記的 pid 與關鍵字都對得上 dump。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
