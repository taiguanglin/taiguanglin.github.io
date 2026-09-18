#!/usr/bin/env python3
"""milli_refine — 套用 adjudication table 到目標講次（milli-align skill §4.4）.

table 格式（JSON list）：每筆 {"i", "start", "end"?, "conf", "method"?, "zero"?, "note"?}
  - start 為本段「實際念出第一個字」的 run-onset（毫秒級）。
  - 缺 end → 由鏈推導（end[i] = start[next READ]；末段 = duration）。
  - 缺 start（null）→ 保留現值，只改 conf/zero。
  - 未列出的段落 → 完全保留現值；鏈 pass 會修其 end。

保護（違反即 abort，不寫檔）：
  1. 目標講次 reviewed=true 或任一段 confirmed=true → 拒跑（golden 不可侵犯）。
  2. 寫檔前後：所有「非目標講次」byte-level 不變。
  3. confirmed/reviewed 鍵永不寫入。

用法：
  milli_refine.py --series lengqie --lecture 5 --table <table.json> [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
AMAP_DIR = ROOT / "audio_map3"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--lecture", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    path = AMAP_DIR / f"{args.series}.json"
    raw = path.read_text(encoding="utf-8")
    doc = json.loads(raw)
    lec = doc["lectures"][args.lecture]
    paras = lec["paragraphs"]
    dur = lec.get("duration")

    if lec.get("reviewed") or any(p.get("confirmed") for p in paras):
        print("abort: 目標講次含 reviewed/confirmed —— golden 不可侵犯")
        sys.exit(2)

    table = json.loads(Path(args.table).read_text(encoding="utf-8"))
    by_i = {}
    for e in table:
        if not 0 <= e["i"] < len(paras):
            print(f"abort: table i={e['i']} 超界")
            sys.exit(2)
        by_i[e["i"]] = e

    changes = []
    for i, e in by_i.items():
        p = paras[i]
        new = dict(p)
        if e.get("start") is not None:
            new["start"] = round(float(e["start"]), 3)
        if e.get("end") is not None:
            new["end"] = round(float(e["end"]), 3)
        if "conf" in e:
            new["conf"] = e["conf"]
        if "method" in e:
            new["method"] = e["method"]
        if "zero" in e:
            if e["zero"]:
                new["zero"] = True
                new["end"] = new["start"]
            else:
                new.pop("zero", None)
        if new != p:
            changes.append((i, p, new, e.get("note", "")))

    print(f"table {len(by_i)} 筆，段落實際變更 {len(changes)}")
    for i, p, new, note in sorted(changes):
        print(f"[{i:3d}] {p['start']:8.2f}-{p['end']:8.2f} conf={p.get('conf')} "
              f"zero={p.get('zero', False)}")
        print(f"  -> {new['start']:8.2f}-{new['end']:8.2f} conf={new.get('conf')} "
              f"zero={new.get('zero', False)}  {note}")

    if not args.apply:
        print("\n(dry-run：加 --apply 寫檔)")
        return

    # 套變更
    for i, _, new, _ in changes:
        new.pop("confirmed", None)
        paras[i] = new

    # 鏈 pass：READ 段依書序，end[i]=start[next READ]；末段 end=duration；
    # zero 段錨在 prev READ end（起訖相等）。confirmed 鍵絕不動。
    # READ 判定：end>start，或 table 明確 zero=False（半念/全念意圖——
    # 新 start 可能超過舊 end，鏈 pass 仍須接上）。
    table_read = {i for i, e in by_i.items() if e.get("zero") is False}
    reads = [i for i, p in enumerate(paras)
             if p["end"] > p["start"] or i in table_read]
    for a, b in zip(reads, reads[1:]):
        if paras[a]["end"] != paras[b]["start"]:
            paras[a]["end"] = paras[b]["start"]
    if reads and dur:
        if paras[reads[-1]]["end"] != dur:
            paras[reads[-1]]["end"] = dur

    def prev_read_end(i):
        for j in range(i - 1, -1, -1):
            if paras[j]["end"] > paras[j]["start"]:
                return paras[j]["end"]
        return 0.0

    for i, p in enumerate(paras):
        if p["end"] <= p["start"] and p.get("zero"):
            p["start"] = p["end"] = prev_read_end(i)

    # 驗證：非目標講次 byte-level 不變
    new_raw = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    doc2 = json.loads(new_raw)
    for n, l2 in doc2["lectures"].items():
        if n == args.lecture:
            continue
        old_raw = json.loads(raw)["lectures"][n]
        if json.dumps(old_raw, ensure_ascii=False, sort_keys=True) != \
                json.dumps(l2, ensure_ascii=False, sort_keys=True):
            print(f"abort: 講次 {n} 被意外變更")
            sys.exit(3)
    for p in paras:
        assert not p.get("confirmed"), "confirmed 被寫入！"
    assert not lec.get("reviewed"), "reviewed 被寫入！"

    path.write_text(new_raw, encoding="utf-8")
    print(f"\n已寫 {path}（{len(changes)} 段變更；confirmed/reviewed 未動）")


if __name__ == "__main__":
    main()
