#!/usr/bin/env python3
"""【一次性重對位】刪除 2025-07-12 蘇小雅卡後，分類資料列的 `i` 重新綁定。

背景
----
`extract.py` 以「文件順序」給每張問答卡 `seq`，分類資料列
（classified/batch_*.jsonl）以 `i` = seq 綁定卡片。刪除 PDF 裡的一張卡
（苏小雅Helen，師父未答）會讓之後所有卡片的 seq 全體 −1，
若不重對位，~2,750 個分類行會綁到錯的卡片（章節歸類整批錯位）。

本腳本在「PDF 已刪卡 + gen_all + extract.py 重跑」之後執行：

1. 讀新 `build/items.jsonl` → qid → seq 對照。
2. 丟棄已刪卡片的分類行（qid question-5bfed135e642；預期剛好 1 行）。
3. 其餘每行 `i` 改為其 qid 在新 items 的 seq（split 的 sub>1 行共用
   基底 qid，綁同一張卡）。任何 qid 在新 items 找不到 → 中止不寫檔。
4. 同步三份副本：`tool/qa_split_ebook/classified/`（版控）、
   `tool/qa_split_ebook/build/classified/`（gen 讀取）、
   `tool/qa_split_ebook/build/batches/`（LLM 分批暫存）。

用法（用鎖版 venv）：
    ../../word_audio_map2/.venv/bin/python realign_classified_seq.py --check
    ../../word_audio_map2/.venv/bin/python realign_classified_seq.py

腳本可重複執行：已是新 seq 時不寫檔。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = HERE / "build"
ITEMS = BUILD / "items.jsonl"

# 已刪除的卡片（tool/fix_20250712_suxiaoya_remove.py 刪卡）
QID_REMOVED = "question-5bfed135e642"

DIRS = [
    HERE / "classified",            # 版控歸檔
    BUILD / "classified",           # gen_classified.py 讀這份
    BUILD / "batches",              # LLM 分批暫存（gitignored）
]


def load_items() -> dict:
    if not ITEMS.exists():
        print(f"❌ 找不到 {ITEMS}；請先重跑 extract.py")
        sys.exit(1)
    qid2seq = {}
    for line in ITEMS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        qid2seq[d["qid"]] = d["seq"]
    return qid2seq


def realign_dir(d: Path, qid2seq: dict, check: bool, strict: bool = True) -> tuple[int, int]:
    """回傳 (丟棄行數, 改 i 行數)。

    strict=True（版控分類資料）：qid 不在新 items → 中止（防止資料錯位）。
    strict=False（build/batches LLM 暫存，gitignored）：qid 不在新 items
    → 視為過期行丟棄並警告（暫存本來就會由分類步驟重新產生；
    09-01 合併後其中仍留舊 qid，屬既有過期狀態）。
    """
    dropped = changed = 0
    for f in sorted(d.glob("batch_*.jsonl")):
        if not f.exists():
            continue
        lines = f.read_text(encoding="utf-8").splitlines()
        out, file_changed = [], False
        for line in lines:
            if not line.strip():
                out.append(line)
                continue
            row = json.loads(line)
            if row.get("qid") == QID_REMOVED:
                dropped += 1
                file_changed = True
                continue
            new_i = qid2seq.get(row.get("qid"))
            if new_i is None:
                if strict:
                    print(f"❌ {f.name}: qid {row.get('qid')} 不在新 items，已中止（未寫檔）")
                    sys.exit(1)
                print(f"  ⚠️ {d.name}/{f.name}: qid {row.get('qid')} 不在新 items，丟棄（暫存過期行）")
                dropped += 1
                file_changed = True
                continue
            if row.get("i") != new_i:
                row["i"] = new_i
                changed += 1
                file_changed = True
            out.append(json.dumps(row, ensure_ascii=False))
        if file_changed and not check:
            f.write_text("\n".join(out) + "\n", encoding="utf-8")
    return dropped, changed


def main() -> int:
    ap = argparse.ArgumentParser(description="刪卡後分類行 i 重新綁定（以 qid 對位）")
    ap.add_argument("--check", action="store_true", help="只顯示將做的事，不修改")
    args = ap.parse_args()

    qid2seq = load_items()
    print(f"[realign] 新 items qid 數 = {len(qid2seq)}")
    total_dropped = total_changed = 0
    for idx, d in enumerate(DIRS):
        if not d.exists():
            print(f"  skip（不存在）{d.relative_to(ROOT)}")
            continue
        dropped, changed = realign_dir(d, qid2seq, args.check, strict=(idx < 2))
        print(f"  {d.relative_to(ROOT)}: 丟棄 {dropped} 行、改 i {changed} 行"
              + ("（--check，未寫檔）" if args.check else ""))
        if d == DIRS[1]:
            total_dropped, total_changed = dropped, changed
    if not args.check and total_dropped != 1:
        # 冪等重跑：第一次已丟棄 → 掃描確認已無該 qid 即可
        leftover = 0
        for f in sorted((BUILD / "classified").glob("batch_*.jsonl")):
            if QID_REMOVED in f.read_text(encoding="utf-8"):
                leftover += 1
        if leftover:
            print(f"❌ build/classified 丟棄行數 = {total_dropped} 且仍殘留 {leftover} 個檔案含該 qid")
            return 1
        print(f"  註：冪等重跑（該 qid 已於前次丟棄），分類資料狀態正確")
    print("[realign] 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
