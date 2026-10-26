#!/usr/bin/env python3
"""一鍵完整重建 wenda2_ebook（Word + 兩份 PDF）。

本腳本封裝問答錄 2 電子書的預設來源路徑，更新 Word/PDF
來源後，在 ``tool/word2ebook/`` 目錄執行即可：

    python3 gen_all.py

等同於：

    python3 main.py \\
        "../../問答錄2/wenda2_250810_截止25年5月17日答疑_含图版.docx" \\
        "../../wenda2_ebook" \\
        --pdf "../../問答錄2/2025年6月-9月答疑合并（未分类）.pdf" \\
        --pdf "../../問答錄2/2025年11月-2026年3月答疑合并（未分类）.pdf"

2025年11月–2026年3月改由第二份 PDF 產生，不再餵入 ``qa/``。
``qa/`` 與線上校稿工具仍可獨立使用。

PDF 章節的逐段音檔播放鈕由站台根目錄 ``audio_map/*.json``（單一 SoT，
即 ``/audio_map/`` 校稿 UI 使用的同一份）在建置時注入
（見 ``tool/pdf_audio_map/``）。

環境守門（2026-10 起）：任何直譯器執行本腳本都會自動切換到鎖版 venv
（``tool/word_audio_map2/.venv``），並驗證 PyMuPDF 版本與
``tool/word_audio_map2/requirements.txt`` 的 pin 一致——版本差異會改變
PDF 抽字空白，造成段落 pid 與 search_index 漂移（root AGENTS.md 規則 13）。
"""

from __future__ import annotations

import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOL_DIR.parent.parent

DOCX_FILE = REPO_ROOT / "問答錄2" / "wenda2_250810_截止25年5月17日答疑_含图版.docx"
PDF_FILE = REPO_ROOT / "問答錄2" / "2025年6月-9月答疑合并（未分类）.pdf"
PDF_FILE_NOV_MAR = REPO_ROOT / "問答錄2" / "2025年11月-2026年3月答疑合并（未分类）.pdf"
PDF_FILES = [PDF_FILE, PDF_FILE_NOV_MAR]
OUTPUT_FOLDER = REPO_ROOT / "wenda2_ebook_word"

if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

# 輕量依賴（僅 stdlib）：import 階段不得拉進 docx/pymupdf，
# 否則非 venv 直譯器會在 re-exec 切換前就 import 失敗。
from utils.env_guard import ensure_locked_pymupdf, reexec_into_venv  # noqa: E402
from config.settings import DEFAULT_SETTINGS  # noqa: E402
from models.document_models import ConversionConfig  # noqa: E402


def build_config() -> ConversionConfig:
    """建立完整重建用的轉換設定（簡繁雙語 + 搜尋索引）。"""
    return ConversionConfig(
        input_file=DOCX_FILE,
        output_folder=OUTPUT_FOLDER,
        generate_search=True,
        generate_traditional=True,
        generate_simplified=True,
        pdf_files=list(PDF_FILES),
    )


def validate_paths() -> bool:
    """檢查所有來源是否存在；失敗時印出錯誤並回傳 False。"""
    ok = True
    if not DOCX_FILE.exists():
        print(f"❌ Word 來源不存在: {DOCX_FILE}")
        ok = False
    elif DOCX_FILE.suffix.lower() not in {".docx", ".doc"}:
        print(f"❌ 不支援的 Word 格式: {DOCX_FILE.suffix}")
        ok = False

    for pdf in PDF_FILES:
        if not pdf.exists():
            print(f"❌ PDF 來源不存在: {pdf}")
            ok = False
        elif pdf.suffix.lower() != ".pdf":
            print(f"❌ 不支援的 PDF 格式: {pdf.suffix}")
            ok = False

    return ok


def main() -> int:
    # 非鎖版環境先切換 venv（os.execv 成功時不返回，整個腳本於 venv 重跑）；
    # 之後才 import 重依賴（docx / pymupdf），並驗證 PyMuPDF 版本。
    reexec_into_venv(__file__)
    from main import Word2EBookConverter  # noqa: E402
    ensure_locked_pymupdf()

    print("📚 gen_all — 完整重建 wenda2_ebook（Word + 兩份 PDF）")
    print(f"   Word:   {DOCX_FILE}")
    for pdf in PDF_FILES:
        print(f"   PDF:    {pdf}")
    print(f"   輸出:   {OUTPUT_FOLDER}")
    print()

    if not validate_paths():
        return 1

    config = build_config()
    try:
        converter = Word2EBookConverter(config, DEFAULT_SETTINGS)
        converter.convert()
    except Exception as exc:
        print(f"❌ 轉換過程中發生錯誤：{exc}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
