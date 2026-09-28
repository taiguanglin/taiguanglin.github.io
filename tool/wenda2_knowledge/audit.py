#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次列出 `src/*.py` 裡所有引文定位的問題（不建置、不寫檔）。

用法
----
    venv/bin/python tool/wenda2_knowledge/audit.py            # 檢查並逐條印出引文
    venv/bin/python tool/wenda2_knowledge/audit.py --short    # 只印錯誤
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "src"))

from common import Corpus  # noqa: E402
from quotepick import Quote, TextQuote  # noqa: E402


def load_books(mods: list[str]) -> dict:
    out = {}
    for name in mods:
        mod = importlib.import_module(name)
        if hasattr(mod, "BOOK"):
            out[name] = mod.BOOK
        else:
            out[name] = {
                "slug": name,
                "chapters": mod.CHAPTERS,
            }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mods", nargs="*", default=["keypoints", "lens"],
                    help="要檢查的 src 模組名")
    ap.add_argument("--short", action="store_true", help="只印錯誤")
    args = ap.parse_args()

    corpus = Corpus()
    books = load_books(args.mods)
    total_q = 0
    errors = 0
    for name, book in books.items():
        nodes: list[tuple[str, object]] = []

        def walk(node, path="$"):
            if isinstance(node, (Quote, TextQuote)):
                nodes.append((path, node))
            elif isinstance(node, dict):
                for k, v in node.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")

        walk(book)
        print(f"\n=== {name}：{len(nodes)} 條引文定位 ===")
        for path, q in nodes:
            total_q += 1
            try:
                resolved = q.resolve(corpus)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"  ✗ {path}\n    {exc}")
                continue
            qa = corpus.get(resolved["qid"])
            ok = resolved["at"] in qa["at"] and resolved["a"] in qa["a"]
            if not ok:
                errors += 1
                print(f"  ✗ {path}：片段不是原文子字串")
                continue
            if not args.short:
                print(f"  ✓ {path}  「{q.spec[2] if isinstance(q, Quote) else q.topic}」")
                print(f"      {qa['qid']}")
                print(f"      {resolved['at'][:110]}")

    print(f"\n合計 {total_q} 條，問題 {errors} 條")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
