#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次建出《坐禪之問答錄2》的兩本複習電子書。

    tool/word_audio_map2/.venv/bin/python tool/wenda2_knowledge/build_all.py

流程
----
    wenda2_ebook/*.html
        └─ extract_corpus.py ──► data/corpus.json
              └─ src/*.py（作者手寫的編輯內容＋引文定位）
                    └─ build_all.py ──► hidden/wenda2_keypoints/、hidden/wenda2_lens/

每一步都是硬失敗：引文對不到原文、錨點對不上、免責聲明掉了，一律 exit 1。
複習書的價值全在「引文可信」，這條不能放寬。

選項
----
    --only keypoints|lens   只建其中一本
    --check                 只檢查不寫檔
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "src"))

import common  # noqa: E402
import render  # noqa: E402
from common import BOOKS, Corpus, verify_book  # noqa: E402
from quotepick import resolve_all  # noqa: E402

# (模組名, 輸出目錄鍵, 書的 metadata 覆寫)
BUILD_ORDER = [
    ("keypoints", "keypoints", None),
    ("lens", "lens", None),  # lens 自帶完整 BOOK
]


def collect(mod_name: str, override: dict | None) -> dict:
    mod = importlib.import_module(mod_name)
    book = dict(mod.BOOK) if hasattr(mod, "BOOK") else {"chapters": mod.CHAPTERS}
    if override:
        book = {**book, **override}
    return book


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=[k for _, k, _ in BUILD_ORDER], help="只建其中一本")
    ap.add_argument("--check", action="store_true", help="只檢查不寫檔")
    args = ap.parse_args()

    common.require_venv()
    corpus = Corpus()

    built: list[tuple[str, dict, Path, dict]] = []
    failures = 0
    for mod_name, key, override in BUILD_ORDER:
        if args.only and args.only != key:
            continue
        book = collect(mod_name, override)
        print(f"\n▶ {book['title']}（{mod_name}）")
        try:
            book = resolve_all(corpus, book)
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ 引文定位失敗：{exc}", file=sys.stderr)
            failures += 1
            continue
        try:
            n = verify_book(corpus, book, f"{mod_name}:")
        except SystemExit:
            failures += 1
            continue
        print(f"  ✓ 引文逐字驗證通過 {n} 條")
        chs = len(book["chapters"])
        secs = sum(len(c.get("sections") or []) for c in book["chapters"])
        unit = "場" if render.narrative_book(book) else "章"
        print(f"  ・{chs} {unit}" + (f" / {secs} 節" if secs else ""))
        if args.check:
            built.append((key, book, BOOKS[key], {"files": [], "outdir": BOOKS[key]}))
            continue
        info = render.write_book(book, corpus, BOOKS[key])
        errs: list[str] = []
        for trad in (False, True):
            errs += render.self_check(book, corpus, BOOKS[key], trad)
        if errs:
            print(f"  ✗ 落地檢查失敗 {len(errs)} 項：", file=sys.stderr)
            for e in errs[:20]:
                print("    -", e, file=sys.stderr)
            failures += 1
            continue
        print(f"  ✓ 產出 {len(info['files'])} 個檔案 → {info['outdir'].name}/")
        built.append((key, book, BOOKS[key], info))

    if failures:
        print(f"\n建置失敗：{failures} 本", file=sys.stderr)
        return 1

    print("\n完成：")
    for key, book, outdir, _ in built:
        n = render.count_quotes(book)
        secs = sum(len(c.get("sections") or []) for c in book["chapters"])
        unit = "場" if render.narrative_book(book) else "章"
        print(f"  {outdir}/  —  {len(book['chapters'])} {unit}"
              + (f"、{secs} 節" if secs else "") + f"、{n} 條原話")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
