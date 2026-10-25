#!/usr/bin/env python3
"""qa_split_ebook 實驗管線 Step 3：批次產生（make_batches）

build/items.jsonl → build/batches/batch_NNN.jsonl（每批 75 則，按原始順序）＋
manifest.json。答案文字對非拆分候選截斷至 800 字（分類看主軸即可，截斷會標記
trunc=true）；拆分候選（偵測到多個編號子問題）保留全文供切分。

用法：../../word_audio_map2/.venv/bin/python make_batches.py [batch_size]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "tool/qa_split_ebook" / "build"
BATCH_DIR = BUILD / "batches"
TRUNC = 800
TRUNC_SPLIT = 6000

# 拆分觸發：行首編號標記（阿拉伯/中文數字、问题N：、第N问、①②③）
MARKER = re.compile(
    r"(?:^|\n)\s*(?:[0-9]{1,2}[、.．]|[一二三四五六七八九十]{1,3}[、.．）)]"
    r"|问题\s*[0-9]{1,2}\s*[：:]|第\s*[0-9]{1,3}(?:\.[0-9])?\s*[个個]?[问問]"
    r"|[①②③④⑤])"
)


def is_split_candidate(q_text: str) -> bool:
    return len(MARKER.findall(q_text)) >= 2


def main():
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 75
    items = [json.loads(l) for l in
             (BUILD / "items.jsonl").read_text(encoding="utf-8").splitlines()]
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    # 清掉舊批次
    for old in BATCH_DIR.glob("batch_*.jsonl"):
        old.unlink()

    manifest = []
    n_cand = n_trunc = 0
    for start in range(0, len(items), batch_size):
        chunk = items[start:start + batch_size]
        rows = []
        for it in chunk:
            sc = is_split_candidate(it["q_text"])
            limit = TRUNC_SPLIT if sc else TRUNC
            a = it["a_text"]
            trunc = len(a) > limit
            if trunc:
                a = a[:limit] + "…（截断，仅供分类参考）"
            n_cand += sc
            n_trunc += trunc
            rows.append({
                "i": it["seq"], "qid": it["qid"], "src": f"{it['ch']}章 {it['sec']}",
                "who": it["who"], "time": it["time"], "q": it["q_text"], "a": a,
                "sc": sc, "trunc": trunc, "img": it["img"] > 0,
            })
        n = start // batch_size + 1
        f = BATCH_DIR / f"batch_{n:03d}.jsonl"
        with f.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        manifest.append({"batch": n, "file": f.name, "items": [r["i"] for r in rows]})
    (BATCH_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[batches] {len(items)} 則 → {len(manifest)} 批（每批 {batch_size}）")
    print(f"[batches] 拆分候選 {n_cand} 則（sc=true，答案保留全文）")
    print(f"[batches] 答案截斷 {n_trunc} 則（trunc=true）")


if __name__ == "__main__":
    main()
