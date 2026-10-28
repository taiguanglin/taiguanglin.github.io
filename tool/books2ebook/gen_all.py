#!/usr/bin/env python3
"""一鍵重建 — books/ → ebook/（含全量資產與索引）

用法（任何 python 皆可——非鎖版環境會自動切換到鎖版 venv）：

    python3 gen_all.py
    # 或：python3 tool/books2ebook/gen_all.py

⚠️ 不要用 /usr/bin/python3 或其他系統 python 直接重建（守門會擋或自動切換）：
   PyMuPDF 的版本會改變 PDF 抽字的斷行與空白（parsers._join() 依賴片段
   邊界），換版重建會讓 ebook/*.html 文字、段落 pid（md5(文字+段序)）與
   search_index*.json 一起漂移，已校對講次的段落跟播會靜默失效
   （root AGENTS.md 規則 13；事故實例見 repo 根目錄
   search_index_rebuild_research.md）。鎖版環境：
   tool/word_audio_map2/.venv（requirements.txt 全 ==）。
"""

import importlib.util
import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent


def _load_env_guard():
    """以 spec 載入 word2ebook 的 env_guard（兩工具共用的守門 SoT）。

    必須在 ``import main`` **之前**載入：main → extract → pymupdf 會在
    非鎖版直譯器上 import 失敗（或缺 docx/opencc），re-exec 得先發生。
    """
    path = TOOL_DIR.parent / "word2ebook" / "utils" / "env_guard.py"
    spec = importlib.util.spec_from_file_location("_w2e_env_guard", path)
    if spec is None or spec.loader is None:
        raise ImportError("無法載入共用環境守門模組：%s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    _load_env_guard().reexec_into_venv(__file__)  # execv 成功時不返回
    # 鎖版環境下 import 才有 pymupdf / docx / opencc
    sys.path.insert(0, str(TOOL_DIR))
    import main  # noqa: E402

    main.build()

    # sitemap.xml 同步更新（單一產生器：tool/site_chrome/sitemap.py）。
    # lastmod 取自 git 最後提交日期——內容更新後 sitemap 不再停在舊日期。
    import importlib.util  # noqa: E402

    _sitemap_path = TOOL_DIR.parent / "site_chrome" / "sitemap.py"
    _spec = importlib.util.spec_from_file_location("_site_chrome_sitemap", _sitemap_path)
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    _module.write_sitemap()
    print("✅ sitemap.xml 已更新")
