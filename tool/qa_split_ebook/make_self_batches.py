#!/usr/bin/env python3
"""qa_split_ebook 自制版輸入：build/items.jsonl → build/self_batches/batch_NNN.slim.jsonl

與 batches/ 同編號（每批 75、同順序）。每則只留 i／q／a（非拆分候選答案截
250 字供主軸印證；sc=true 保留全文供切分）＋ sc 標記。另產出
build/self_batches/tree_compact.txt（12 章全樽，自制分類時的對照表）。
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "tool/qa_split_ebook/build"
SLIM = BUILD / "self_batches"
TRUNC = 250
TRUNC_SC = 6000
MARKER = re.compile(
    r"(?:^|\n)\s*(?:[0-9]{1,2}[、.．]|[一二三四五六七八九十]{1,3}[、.．）)]"
    r"|问题\s*[0-9]{1,2}\s*[：:]|第\s*[0-9]{1,3}(?:\.[0-9])?\s*[个個]?[问問]"
    r"|[①②③④⑤])")


def main():
    SLIM.mkdir(parents=True, exist_ok=True)
    for old in SLIM.glob("*.jsonl"):
        old.unlink()
    items = [json.loads(l) for l in
             (BUILD / "items.jsonl").read_text(encoding="utf-8").splitlines()]
    # 樹對照表
    tree = json.loads((BUILD / "section_tree.json").read_text(encoding="utf-8"))
    lines = []
    for ch_s in sorted(tree):
        info = tree[ch_s]
        lines.append(f"== {ch_s}{info['title']} ==")
        l2i = l3i = l4i = 0
        for e in info["entries"]:
            if e["level"] == 2:
                l2i += 1; l3i = l4i = 0
                lines.append(f"{ch_s}-{l2i:02d} {e['name']}")
            elif e["level"] == 3:
                l3i += 1; l4i = 0
                lines.append(f"{ch_s}-{l2i:02d}-{l3i:02d} {e['name']}")
            else:
                l4i += 1
                lines.append(f"{ch_s}-{l2i:02d}-{l3i:02d}-{l4i:02d} {e['name']}")
    (SLIM / "tree_compact.txt").write_text("\n".join(lines), encoding="utf-8")
    # slim 批次
    n_batch = 0
    for start in range(0, len(items), 75):
        chunk = items[start:start + 75]
        n_batch += 1
        with (SLIM / f"batch_{n_batch:03d}.slim.jsonl").open("w", encoding="utf-8") as f:
            for it in chunk:
                sc = len(MARKER.findall(it["q_text"])) >= 2
                limit = TRUNC_SC if sc else TRUNC
                a = it["a_text"]
                if len(a) > limit:
                    a = a[:limit] + "…"
                f.write(json.dumps({"i": it["seq"], "q": it["q_text"], "a": a,
                                    "sc": sc}, ensure_ascii=False) + "\n")
    print(f"[slim] {len(items)} 則 → {n_batch} 批 @ {SLIM}；樹對照表 {len(lines)} 行")


if __name__ == "__main__":
    main()
