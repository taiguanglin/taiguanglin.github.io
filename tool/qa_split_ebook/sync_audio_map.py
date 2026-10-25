#!/usr/bin/env python3
"""qa_split_ebook 實驗管線 Step 0：同步音檔映射（sync_audio_map）

把線上 SoT（tool/word2ebook/data/audio_map/）中 **2025年6月之後** 的月份
JSON 原樣複製到 audio_map/（實驗書的音檔資料目錄，只放 JSON）。
複製後實驗管線只讀 audio_map/，不回寫線上資料。

usage: python3 sync_audio_map.py
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tool/word2ebook/data/audio_map"
DST = ROOT / "audio_map"
CUTOFF = (2025, 6)


def main():
    DST.mkdir(exist_ok=True)
    copied = []
    for f in sorted(SRC.glob("*.json")):
        m = f.stem.split("-")
        if len(m) != 2:
            continue
        key = (int(m[0]), int(m[1]))
        if key < CUTOFF:
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("month") != f.stem:
            print(f"[sync] ⚠ {f.name} 內部 month={data.get('month')} 與檔名不符，仍照檔名複製")
        shutil.copyfile(f, DST / f.name)
        copied.append(f.name)
    print(f"[sync] 複製 {len(copied)} 個月份 JSON → {DST}: {', '.join(copied)}")


if __name__ == "__main__":
    main()
