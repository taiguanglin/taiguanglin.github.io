#!/usr/bin/env python3
"""【一次性來源修訂】2025-07-12 貼吧：刪除師父未回答的「苏小雅Helen」提問卡。

問題
----
`問答錄2/2025年6月-9月答疑合并（未分类）.pdf` 第 638 頁有一張問答卡：

    苏小雅helen：2025-07-12 10:41
    顶礼Tai师父。师父，吉祥如意！我在六月底去了一趟五台山朝拜……
    （六行提問內文）
    Taiguanglin：
    苏小雅Helen，无回答。

PDF 標示「无回答」——音檔裡師父只唸了「下一个问题，苏小雅Helen啊，」
（506.63–510.44）就跳去回答下一題（多杰扎西2007 的「你可以那么理解，
这个世界大框架是佛创造的……」，510.46 起）。使用者指示：沒回答的提問
不應出現在問答錄裡，連同映射 JSON 與分類電子書一併徹底刪除。

修訂
----
刪除整張卡片（提問者標頭、六行提問內文、`Taiguanglin：`、`无回答。`，
以及卡片後方的分隔線），讓「多杰扎西2007」的卡片直接接在上一張卡之後。
此後 PDF 解析只會產生 30 張卡，與刪除後的映射 JSON 段序一致
（`extract_sessions.py` 以「提問者：時間」標頭切卡並依序編號）。

配套
----
* `tool/pdf_audio_map/apply_20261026_fixes.py`：映射 JSON 刪段＋重編號、
  `qid_to_sep_chapter.json`、分類資料列刪除。
* 師父唸「下一个问题，苏小雅Helen啊」的 2.5 秒提示語依資料集慣例
  歸 #9 段尾（該腳本一併處理）。

用法
----
    tool/word_audio_map2/.venv/bin/python tool/fix_20250712_suxiaoya_remove.py --check
    tool/word_audio_map2/.venv/bin/python tool/fix_20250712_suxiaoya_remove.py

工具可重複執行：找不到該標頭列時視為「已刪除」，不會再改檔。
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

# 被刪卡片的頭尾標記（用來框出要刪的行）
HEADER_TEXT = "苏小雅helen：2025-07-12 10:41"
NEXT_HEADER_TEXT = "多杰扎西2007：2025-07-12 12:18"

# 驗證用：相鄰卡片的內文必須仍在
KEEP_MARKS = (
    "显密圆通成佛心要集",      # 上一卡（#9 灌頂問題）的提問內文
    "这个世界大框架是佛创造的",  # 下一卡（多杰扎西）的回答開頭（PDF 文字）
)
ANSWER_MARK = "无回答"


def _norm(text: str) -> str:
    """比對用：去掉所有空白（PDF 抽字可能在字間插空格）。"""
    return "".join((text or "").split())


def _header_line(page, target: str):
    """回傳該頁上『整行剛好等於 target』的 (rect, text)；找不到回傳 None。"""
    t = _norm(target)
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(s.get("text", "") for s in line.get("spans", []))
            if _norm(text) == t:
                return pymupdf.Rect(line["bbox"]), text
    return None


def find_card_lines(doc):
    """回傳 (page_index, [要刪除的行 (rect, text)])。"""
    for pno, page in enumerate(doc):
        hit = _header_line(page, HEADER_TEXT)
        if not hit:
            continue
        nxt = _header_line(page, NEXT_HEADER_TEXT)
        if not nxt:
            raise RuntimeError(f"第 {pno + 1} 頁找到蘇小雅標頭，但找不到下一卡標頭")
        h_rect, _ = hit
        n_rect, _ = nxt
        doomed = []
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                r = pymupdf.Rect(line["bbox"])
                if h_rect.y0 - 0.5 <= r.y0 and r.y1 <= n_rect.y0 - 0.5:
                    text = "".join(s.get("text", "") for s in line.get("spans", []))
                    doomed.append((r, text))
        return pno, doomed
    return None, None


def verify_removed(doc) -> None:
    text = "\n".join(page.get_text("text") for page in doc)
    norm = _norm(text)
    if _norm(HEADER_TEXT) in norm:
        raise RuntimeError("驗證失敗：蘇小雅標頭仍存在")
    if _norm("苏小雅Helen，无回答") in norm:
        raise RuntimeError("驗證失敗：「苏小雅Helen，无回答。」仍存在")
    if _norm("四大佛山朝拜") in norm:
        raise RuntimeError("驗證失敗：蘇小雅提問內文仍存在")
    for mark in KEEP_MARKS:
        if _norm(mark) not in norm:
            raise RuntimeError(f"驗證失敗：相鄰卡片內文 {mark!r} 不見了")
    if _norm(NEXT_HEADER_TEXT) not in norm:
        raise RuntimeError("驗證失敗：下一卡（多杰扎西）標頭不見了")


def main() -> int:
    ap = argparse.ArgumentParser(description="刪除 2025-07-12 蘇小雅未回答提問卡")
    ap.add_argument("--check", action="store_true", help="只檢查，不修改")
    args = ap.parse_args()

    if not PDF_PATH.exists():
        print(f"❌ 找不到來源 PDF：{PDF_PATH}")
        return 1

    doc = pymupdf.open(PDF_PATH)
    try:
        pno, doomed = find_card_lines(doc)
        if pno is None:
            verify_removed(doc)
            print("✅ 已刪除（找不到蘇小雅標頭），不需修改")
            return 0

        print(f"找到：第 {pno + 1} 頁，將刪除 {len(doomed)} 行：")
        for r, t in doomed:
            print(f"    y={r.y0:7.1f}-{r.y1:7.1f}  {t[:46]}")
        if args.check:
            print("--check：未修改檔案")
            return 0

        page = doc[pno]
        for r, _t in doomed:
            padded = pymupdf.Rect(r.x0 - 1, r.y0 - 1, r.x1 + 1, r.y1 + 1)
            page.add_redact_annot(padded, fill=(1, 1, 1))
        page.apply_redactions()
        verify_removed(doc)
        doc.saveIncr()
        print(f"✅ 已刪除蘇小雅卡片並增量存檔：{PDF_PATH}")
        return 0
    finally:
        doc.close()


if __name__ == "__main__":
    sys.exit(main())
