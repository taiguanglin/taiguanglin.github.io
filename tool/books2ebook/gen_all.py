#!/usr/bin/env python3
"""一鍵重建 — books/ → ebook/（含全量資產與索引）

用法：
    cd tool/books2ebook && python3 gen_all.py
    # 或：python3 tool/books2ebook/gen_all.py
"""

import os
import sys

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOL_DIR)
# 確保以倉庫根的 /usr/bin/python3（pymupdf/opencc）執行
import main  # noqa: E402

if __name__ == "__main__":
    main.build()
