#!/usr/bin/env python3
"""【一次性來源修訂】2025-09-01 貼吧：把同一個提問者的兩則提問合併為一則。

問題
----
`問答錄2/2025年6月-9月答疑合并（未分类）.pdf` 第 891 頁把「孙hong 静」同一個
提問者的兩則提問排成兩個獨立卡片：

    孙hong 静: 2025-08-20 08:26     ← 第一則提問（失眠／婆婆治病）
    顶礼Tai师父！
    …第一則提問內文…
    孙hong 静: 2025-9-1 06:58       ← 第二則提問（念 128 遍《地藏经》）
    …第二則提問內文…
    Taiguanglin：                    ← 師父只有一個回答，涵蓋兩則提問

PDF 解析器因此產生兩個 `.question`，其中第一則沒有對應答案（零長音段），
音檔校稿也會多出一段 `start == end` 的假段落。

修訂
----
刪除第二個「提問者＋時間」標頭列（`孙hong 静: 2025-9-1 06:58`），
讓兩則提問內文成為同一個提問卡片的連續內文；後面的 `Taiguanglin：`
仍是唯一且不變的回答。這樣解析後只會有一張問答卡，兩段提問文字完整保留。

用法
----
    tool/word_audio_map2/.venv/bin/python tool/fix_20250901_sunhong_merge.py --check
    tool/word_audio_map2/.venv/bin/python tool/fix_20250901_sunhong_merge.py

工具可重複執行：找不到該標頭列時視為「已合併」，不會再改檔。
PDF 以增量方式存檔（只改一頁），其他頁面內容不動。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:  # PyMuPDF < 1.24 只有舊模組名
    import fitz as pymupdf

REPO_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = REPO_ROOT / "問答錄2" / "2025年6月-9月答疑合并（未分类）.pdf"

# 第二個提問者標頭（刪除後兩則提問會合併成一張卡）
HEADER_TEXT = "孙hong 静: 2025-9-1 06:58"
# 合併後仍必須存在的兩段提問開頭（驗證用）
Q1_MARK = "婆婆有家族遗传失眠症"
Q2_MARK = "师父，我从8"
ANSWER_MARK = "Taiguanglin："


def _norm(text: str) -> str:
    """比對用：去掉所有空白（PDF 抽字可能在字間插空格）。"""
    return "".join((text or "").split())


def find_header_lines(doc) -> list[tuple[int, object, str]]:
    """回傳所有『整行剛好是 HEADER_TEXT』的 (page_index, rect, text)。"""
    hits = []
    target = _norm(HEADER_TEXT)
    for pno, page in enumerate(doc):
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                text = "".join(s.get("text", "") for s in line.get("spans", []))
                if _norm(text) == target:
                    hits.append((pno, pymupdf.Rect(line["bbox"]), text))
    return hits


def verify_merged(doc) -> None:
    """驗證兩段提問文字與師父回答都還在，且第二個標頭已不存在。"""
    text = "\n".join(page.get_text("text") for page in doc)
    norm = _norm(text)
    for mark in (Q1_MARK, Q2_MARK, ANSWER_MARK):
        if _norm(mark) not in norm:
            raise RuntimeError(f"驗證失敗：找不到 {mark!r}")
    if _norm(HEADER_TEXT) in norm:
        raise RuntimeError("驗證失敗：第二個提問者標頭仍存在")


def main() -> int:
    ap = argparse.ArgumentParser(description="合併 2025-09-01 貼吧同一人兩則提問")
    ap.add_argument("--check", action="store_true", help="只檢查，不修改")
    args = ap.parse_args()

    if not PDF_PATH.exists():
        print(f"❌ 找不到來源 PDF：{PDF_PATH}")
        return 1

    doc = pymupdf.open(PDF_PATH)
    try:
        hits = find_header_lines(doc)
        if not hits:
            verify_merged(doc)
            print("✅ 已合併（找不到第二個提問者標頭），不需修改")
            return 0
        if len(hits) != 1:
            print(f"❌ 預期剛好 1 處 {HEADER_TEXT!r}，實際 {len(hits)} 處；已中止")
            return 1

        pno, rect, text = hits[0]
        print(f"找到：第 {pno + 1} 頁 bbox={tuple(round(v, 2) for v in rect)} text={text!r}")
        if args.check:
            print("--check：未修改檔案")
            return 0

        page = doc[pno]
        padded = pymupdf.Rect(rect.x0 - 1, rect.y0 - 1, rect.x1 + 1, rect.y1 + 1)
        page.add_redact_annot(padded, fill=(1, 1, 1))
        page.apply_redactions()
        verify_merged(doc)
        doc.saveIncr()
        print(f"✅ 已刪除第二個提問者標頭並增量存檔：{PDF_PATH}")
        return 0
    finally:
        doc.close()


if __name__ == "__main__":
    sys.exit(main())
