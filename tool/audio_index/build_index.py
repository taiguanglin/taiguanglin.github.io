#!/usr/bin/env python3
"""掃描 audio/ 目錄內容，產生 `audio/index.html`（粉色系、類別篩選、涵蓋所有 .opus）。

- 來源：`/Users/paul/tai/audio/`（repo 的 `audio` 是 symlink，未進本 repo 的 git）
- 樣板：`tool/audio_index/index_template.html`
  （保留置頂大悲咒播放器、關螢幕循環、Media Session 等既有 JS，只換資料與版面配色）
- 產物：`audio/index.html`

為什麼要產生而不是手寫清單：`audio/` 隨時會新增錄音（答疑／講經／義理），
手工維護檔案陣列一定會漏；本腳本每次掃描整個資料夾，任何 `*.opus` 都會自動進清單。

用法：
  python3 tool/audio_index/build_index.py            # 產生 audio/index.html
  python3 tool/audio_index/build_index.py --dry-run  # 只印統計與未分類檔案
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
TEMPLATE = TOOL_DIR / "index_template.html"
AUDIO_ROOT = Path("/Users/paul/tai/audio")
OUT_PATH = AUDIO_ROOT / "index.html"

SKIP_DIRS = {".git", "srt", "node_modules"}
SKIP_NAMES_PREFIX = ("西方三聖",)

# 置頂大悲咒（由頁面 featured 區塊處理，不列入清單）
FEATURED = {"Tai師父大悲咒108遍.opus", "Tai師父大悲咒快速版108遍.opus"}

# 類別定義：label 顯示名稱、cls 徽章樣式、group 下拉選單分組、order 排序
CATEGORIES: dict[str, dict] = {
    # 答疑（音檔平放在 audio/ 根目錄）
    "dayi": dict(label="答疑", cls="gz", group="答疑", order=1),
    "tieba": dict(label="貼吧答疑", cls="tb", group="答疑", order=2),
    "weixin": dict(label="微信公眾號答疑", cls="wx", group="答疑", order=3),
    "guanwang": dict(label="官網答疑", cls="web", group="答疑", order=4),
    # 講經系列（audio/jiangjing/）
    "lengqie": dict(label="楞伽經", cls="jj", group="講經", order=10),
    "liuzu": dict(label="六祖壇經", cls="jj", group="講經", order=11),
    "lengyan": dict(label="楞嚴經", cls="jj", group="講經", order=12),
    "sishier": dict(label="四十二章經", cls="jj", group="講經", order=13),
    "ganen": dict(label="感恩與講經", cls="jj", group="講經", order=14),
    "yuanjue": dict(label="圓覺經", cls="jj", group="講經", order=15),
    "jingang": dict(label="金剛經", cls="jj", group="講經", order=16),
    "xinjing": dict(label="心經", cls="jj", group="講經", order=17),
    # 義理（audio/yili/）
    "yili": dict(label="義理", cls="yl", group="義理", order=20),
    # 未分類
    "other": dict(label="其他", cls="gz", group="其他", order=99),
}

# 講經系列關鍵字（簡繁都收，較長者優先）
SERIES_RULES = [
    ("楞伽经", "lengqie"), ("楞伽經", "lengqie"),
    ("六祖坛经", "liuzu"), ("六祖壇經", "liuzu"),
    ("楞严经", "lengyan"), ("楞嚴經", "lengyan"),
    ("四十二章经", "sishier"), ("四十二章經", "sishier"),
    ("圆觉经", "yuanjue"), ("圓覺經", "yuanjue"),
    ("金刚经", "jingang"), ("金剛經", "jingang"),
    ("心经", "xinjing"), ("心經", "xinjing"),
    ("感恩与讲经", "ganen"), ("感恩與講經", "ganen"),
]

# 根目錄答疑來源
ROOT_RULES = [
    ("貼吧", "tieba"), ("贴吧", "tieba"),
    ("微信公眾號", "weixin"), ("微信公众号", "weixin"),
    ("公眾號", "weixin"), ("公众号", "weixin"),
    ("官網", "guanwang"), ("官网", "guanwang"),
    ("答疑", "dayi"),
]


def classify(rel: Path) -> str | None:
    """相對路徑 → 類別 key；回傳 None 表示置頂（大悲咒）。"""
    name = rel.name
    if name in FEATURED:
        return None
    if name.startswith(SKIP_NAMES_PREFIX):
        return "other"

    dirs = rel.parts[:-1]
    if dirs:
        top = dirs[0]
        if top == "yili":
            return "yili"
        if top == "jiangjing":
            for kw, cat in SERIES_RULES:
                if kw in name:
                    return cat
            return "dayi" if "答疑" in name else "other"
        # 未來新增的子資料夾：仍先試系列關鍵字
        for kw, cat in SERIES_RULES:
            if kw in name:
                return cat

    for kw, cat in SERIES_RULES:
        if kw in name:
            return cat
    for kw, cat in ROOT_RULES:
        if kw in name:
            return cat
    if "义理" in name or "義理" in name:
        return "yili"
    return "other"


def scan() -> list[dict]:
    if not AUDIO_ROOT.is_dir():
        raise SystemExit(f"找不到音檔目錄：{AUDIO_ROOT}")
    entries: list[dict] = []
    unknown: list[str] = []
    for path in sorted(AUDIO_ROOT.rglob("*.opus")):
        rel = path.relative_to(AUDIO_ROOT)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if rel.name.startswith("."):
            continue
        cat = classify(rel)
        if cat is None:
            continue
        rel_posix = rel.as_posix()
        entries.append({"path": rel_posix, "cat": cat})
        if cat == "other":
            unknown.append(rel_posix)
    return entries, unknown


def render(entries: list[dict]) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")

    lines = []
    for e in entries:
        lines.append("  " + json.dumps(e, ensure_ascii=False) + ",")
    files_block = "const FILES = [\n" + "\n".join(lines) + "\n];"

    used = sorted({e["cat"] for e in entries} | {"other"},
                  key=lambda c: CATEGORIES[c]["order"])
    cats_block = "const CATEGORIES = " + json.dumps(
        {c: CATEGORIES[c] for c in used}, ensure_ascii=False, indent=2) + ";"

    new, n_files = re.subn(r"const FILES = \[.*?\n\];", files_block,
                           template, count=1, flags=re.S)
    if n_files != 1:
        raise SystemExit("樣板找不到 `const FILES = [` 區塊")
    new, n_cats = re.subn(r"const CATEGORIES = /\*__CATEGORIES__\*/.*?;",
                          cats_block, new, count=1, flags=re.S)
    if n_cats != 1:
        raise SystemExit("樣板找不到 CATEGORIES 佔位標記")

    stamp = (f"// built by tool/audio_index/build_index.py · "
             f"{date.today().isoformat()} · {len(entries)} files\n")
    return new.replace("<script>\n", "<script>\n" + stamp, 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="由 audio/ 內容產生 audio/index.html")
    ap.add_argument("--dry-run", action="store_true", help="只印統計，不寫檔")
    args = ap.parse_args()

    entries, unknown = scan()
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["cat"]] = counts.get(e["cat"], 0) + 1

    print(f"audio/ 掃到 {len(entries)} 個音檔（置頂大悲咒 2 個另計）")
    for cat, n in sorted(counts.items(), key=lambda kv: CATEGORIES[kv[0]]["order"]):
        print(f"  {CATEGORIES[cat]['label']:<10} {n:>4}")
    if unknown:
        print(f"⚠️ 未分類（歸入「其他」）{len(unknown)} 個：", file=sys.stderr)
        for u in unknown:
            print("   " + u, file=sys.stderr)

    if args.dry_run:
        return

    html = render(entries)
    tmp = OUT_PATH.with_suffix(".html.tmp")
    tmp.write_text(html, encoding="utf-8")
    tmp.replace(OUT_PATH)
    print(f"✅ 已寫入 {OUT_PATH}（{len(html):,} bytes）")


if __name__ == "__main__":
    main()
