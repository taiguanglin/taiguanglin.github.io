#!/usr/bin/env python3
"""一鍵完整重建 wenda2_ebook（Word + PDF + QA）。

本腳本封裝問答錄 2 電子書的預設來源路徑，修正 ``qa/`` 文字稿或更新 Word/PDF
來源後，在 ``tool/word2ebook/`` 目錄執行即可：

    python3 gen_all.py

等同於：

    python3 main.py \\
        "../../問答錄2/wenda2_250810_截止25年5月17日答疑_含图版.docx" \\
        "../../wenda2_ebook" \\
        --pdf "../../問答錄2/2025年6月-9月答疑合并（未分类）.pdf" \\
        --qa "../../qa"
"""

from __future__ import annotations

import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOL_DIR.parent.parent

DOCX_FILE = REPO_ROOT / "問答錄2" / "wenda2_250810_截止25年5月17日答疑_含图版.docx"
PDF_FILE = REPO_ROOT / "問答錄2" / "2025年6月-9月答疑合并（未分类）.pdf"
QA_FOLDER = REPO_ROOT / "qa"
OUTPUT_FOLDER = REPO_ROOT / "wenda2_ebook"

if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

from config.settings import DEFAULT_SETTINGS  # noqa: E402
from main import Word2EBookConverter  # noqa: E402
from models.document_models import ConversionConfig  # noqa: E402


def build_config() -> ConversionConfig:
    """建立完整重建用的轉換設定（簡繁雙語 + 搜尋索引）。"""
    return ConversionConfig(
        input_file=DOCX_FILE,
        output_folder=OUTPUT_FOLDER,
        generate_search=True,
        generate_traditional=True,
        generate_simplified=True,
        pdf_file=PDF_FILE,
        qa_folder=QA_FOLDER,
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

    if not PDF_FILE.exists():
        print(f"❌ PDF 來源不存在: {PDF_FILE}")
        ok = False
    elif PDF_FILE.suffix.lower() != ".pdf":
        print(f"❌ 不支援的 PDF 格式: {PDF_FILE.suffix}")
        ok = False

    if not QA_FOLDER.exists():
        print(f"❌ QA 資料夾不存在: {QA_FOLDER}")
        ok = False
    elif not QA_FOLDER.is_dir():
        print(f"❌ QA 路徑不是資料夾: {QA_FOLDER}")
        ok = False

    return ok


def main() -> int:
    print("📚 gen_all — 完整重建 wenda2_ebook（Word + PDF + QA）")
    print(f"   Word:   {DOCX_FILE}")
    print(f"   PDF:    {PDF_FILE}")
    print(f"   QA:     {QA_FOLDER}")
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
