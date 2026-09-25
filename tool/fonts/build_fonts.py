#!/usr/bin/env python3
"""字型子集管線：站用頁面語料 → Noto Serif/Sans TC 子集 woff2 + fonts.css。

為什麼自架：
  Google Fonts（fonts.googleapis.com）在中國大陸時常連不上，而本站明確服務
  簡體讀者。把 Noto Serif TC / Noto Sans TC 以「實際用字子集」自架在
  /fonts/，全站 33+ 個頁面共用同一組檔案，跨頁快取、離線（Pages 同源）可載。

語料來源（rebuild 時自動重掃）：
  - 根目錄 *.html（含生成的 session_knowledge.html、wenda2_mindmap.html）
  - wenda2/*.html、stories/*.html、404.html
  - stories/assets/story.js（閱讀器 UI 文字）
  - daily_quotes.json（首頁「每日精選」動態注入的文字）
  - 以上全部再做一次 OpenCC t2s 轉換取聯集（lang-switch.js 會在繁頁上
    即時轉出簡體字，缺字會退化成系統字型）。

字重來源（tool/fonts/src/，不進版控）：
  - Noto Serif TC 400/500/600/700/900、Noto Sans TC 300/400/500/700：
    notofonts/noto-cjk 的 SubsetOTF/TC 靜態版。
  - Noto Sans TC 600：CJK 靜態版無 SemiBold，由 google/fonts 的
    NotoSansTC[wght].ttf 以 varLib.instancer 實例化（見 README）。

執行（需要 opencc：用 word_audio_map2 的 venv；fonttools 在 .pylibs）：
    tool/word_audio_map2/.venv/bin/python tool/fonts/build_fonts.py

輸出：
    fonts/NotoSerifTC-{400,500,600,700,900}.woff2
    fonts/NotoSansTC-{300,400,500,600,700}.woff2
    fonts/fonts.css   （絕對路徑 /fonts/...，wenda2/、stories/、404 皆可用）
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PYLIBS = HERE / ".pylibs"
sys.path.insert(0, str(PYLIBS))

# ---------------------------------------------------------------- 語料 ---------------------------------------------------------------- #

CORPUS_FILES = (
    list(ROOT.glob("*.html"))
    + list((ROOT / "wenda2").glob("*.html"))
    + list((ROOT / "stories").glob("*.html"))
    + [ROOT / "stories/assets/story.js", ROOT / "daily_quotes.json"]
)

# ------------------------------------------------------- 字重登記表 -------------------------------------------------------- #

# (family, css_weight, 來源檔, 輸出檔)
SUBSETS = [
    ("Noto Serif TC", "400", "NotoSerifTC-Regular.otf", "NotoSerifTC-400.woff2"),
    ("Noto Serif TC", "500", "NotoSerifTC-Medium.otf", "NotoSerifTC-500.woff2"),
    ("Noto Serif TC", "600", "NotoSerifTC-SemiBold.otf", "NotoSerifTC-600.woff2"),
    ("Noto Serif TC", "700", "NotoSerifTC-Bold.otf", "NotoSerifTC-700.woff2"),
    ("Noto Serif TC", "900", "NotoSerifTC-Black.otf", "NotoSerifTC-900.woff2"),
    ("Noto Sans TC", "300", "NotoSansTC-Light.otf", "NotoSansTC-300.woff2"),
    ("Noto Sans TC", "400", "NotoSansTC-Regular.otf", "NotoSansTC-400.woff2"),
    ("Noto Sans TC", "500", "NotoSansTC-Medium.otf", "NotoSansTC-500.woff2"),
    ("Noto Sans TC", "600", "NotoSansTC-SemiBold.ttf", "NotoSansTC-600.woff2"),
    ("Noto Sans TC", "700", "NotoSansTC-Bold.otf", "NotoSansTC-700.woff2"),
]


def build_corpus() -> str:
    chars: set[str] = set()
    for path in CORPUS_FILES:
        if not path.exists():
            print(f"⚠️  語料檔不存在，跳過：{path.relative_to(ROOT)}")
            continue
        chars.update(path.read_text(encoding="utf-8", errors="ignore"))
    text = "".join(sorted(chars))
    try:
        import opencc  # noqa: 僅 venv 提供；缺失時退回繁體語料並警告

        converter = opencc.OpenCC("t2s")
        chars.update(converter.convert(text))
    except ImportError:
        print("⚠️  未安裝 opencc：語料只含繁體字。請用 word_audio_map2 的 venv 執行。")
    return "".join(sorted(chars))


def subset_one(src: Path, out: Path, corpus_file: Path) -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PYLIBS) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run(
        [
            sys.executable, "-m", "fontTools.subset",
            str(src),
            f"--text-file={corpus_file}",
            f"--output-file={out}",
            "--flavor=woff2",
            "--no-hinting",
            "--desubroutinize",
            "--name-IDs=*",
            "--recalc-bounds",
        ],
        check=True,
        env=env,
    )
    return out.stat().st_size


def main() -> int:
    src_dir = HERE / "src"
    fonts_dir = ROOT / "fonts"
    build_dir = HERE / "build"
    fonts_dir.mkdir(exist_ok=True)
    build_dir.mkdir(exist_ok=True)

    corpus = build_corpus()
    corpus_file = build_dir / "corpus.txt"
    corpus_file.write_text(corpus, encoding="utf-8")
    print(f"📦 語料：{len(corpus)} 個唯一字元（含簡體聯集）")

    css_lines = [
        "/* TaiGuangLin 自架字型子集 — 由 tool/fonts/build_fonts.py 產生，勿手改。",
        "   來源：Noto Serif TC / Noto Sans TC（SIL OFL 1.1，見 fonts/OFL.txt）。",
        "   字體檔為全站共用子集；新增頁面用字後請重跑管線。 */",
    ]
    total = 0
    for family, weight, src_name, out_name in SUBSETS:
        src = src_dir / src_name
        if not src.exists():
            raise SystemExit(f"缺少來源字型：{src}（見 README 下載步驟）")
        size = subset_one(src, fonts_dir / out_name, corpus_file)
        total += size
        print(f"  ✅ {out_name:<26} {size / 1024:7.1f} KB")
        css_lines.append(
            "@font-face { font-family: '%s'; font-style: normal; font-weight: %s; "
            "font-display: swap; src: url(/fonts/%s) format('woff2'); }"
            % (family, weight, out_name)
        )
    (fonts_dir / "fonts.css").write_text("\n".join(css_lines) + "\n", encoding="utf-8")
    print(f"🎉 共輸出 {len(SUBSETS)} 個字重，合計 {total / 1024 / 1024:.2f} MB → fonts/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
