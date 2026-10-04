#!/usr/bin/env python3
"""milli_refine — 套用 adjudication table 到目標講次（milli-align skill §7.4）.

table 格式（JSON list）：每筆 {"i", "start", "end"?, "conf", "method"?, "zero"?, "note"?}
  - start 為本段「實際念出第一個字」的 run-onset（毫秒級）。
  - 缺 end → 由鏈推導（end[i] = start[next READ]；末段 = duration）。
  - 缺 start（null）→ 保留現值，只改 conf/zero。
  - 未列出的段落 → 完全保留現值；鏈 pass 會修其 end。

保護（違反即 abort，不寫檔）：
  1. 目標講次 reviewed=true → 拒跑（golden 講次整講不可侵犯）；
     講內既有 confirmed 段（如 L7 講首 zero 塊）不可被 table 觸及，且寫入前後須 byte-identical。
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

    if lec.get("reviewed"):
        print("abort: 目標講次 reviewed —— golden 不可侵犯")
        sys.exit(2)

    table = json.loads(Path(args.table).read_text(encoding="utf-8"))
    by_i = {}
    for e in table:
        if not 0 <= e["i"] < len(paras):
            print(f"abort: table i={e['i']} 超界")
            sys.exit(2)
        by_i[e["i"]] = e

    # READ 身分必須在**變更前**記錄：相鄰兩段同時改且順序使後段 start 後移時，
    # 先套的那段 end 會被夾到自己的 start 之下，事後用 `end > start` 判定就會
    # 把它踢出 READ 集合，鏈 pass 便永遠接不上（L18 r2 [48]/[49] 實測）。
    # 判準＝「沒有 zero 標記 且 起訖不等」——含已損壞的負長度段，讓本程式能自我修復。
    reads_before = {i for i, p in enumerate(paras)
                    if not p.get("zero") and p["end"] != p["start"]}

    # confirmed 段（如 L7 講首 4 個 zero 塊）不可被 table 觸及；
    # 其餘未 confirmed 段可改（golden 講次由 reviewed=true 整講擋下）。
    confirmed_before = {
        i: json.dumps(p, ensure_ascii=False, sort_keys=True)
        for i, p in enumerate(paras) if p.get("confirmed")
    }
    for i in by_i:
        if paras[i].get("confirmed"):
            print(f"abort: table 觸及 confirmed 段 [{i}] —— 不可侵犯")
            sys.exit(2)

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
    # READ 判定：**變更前的身分 ∪ table 明示 zero=False**（見上方 reads_before）。
    # 不可事後用 `end > start` 判定——夾到 start 之下的段會被誤判為 zero 而脫鏈。
    table_read = {i for i, e in by_i.items() if e.get("zero") is False}
    reads = sorted(reads_before | table_read)
    for a, b in zip(reads, reads[1:]):
        if paras[a]["end"] != paras[b]["start"]:
            paras[a]["end"] = paras[b]["start"]
    if reads and dur:
        if paras[reads[-1]]["end"] != dur:
            paras[reads[-1]]["end"] = dur

    # 安全網：鏈 pass 後若仍有負長度／未接上的 span，**不寫檔**並明確報出，
    # 免得靜靜把壞資料寫進 SoT（L18 r2 曾因此產生 703.65–703.00）。
    bad_span = [i for i, p in enumerate(paras) if p["end"] < p["start"]]
    if bad_span:
        print(f"abort: 鏈 pass 後出現負長度 span {[paras[i]['start'] for i in bad_span]}"
              f"（段 {bad_span}）—— table 的 start 互相衝突？")
        sys.exit(2)
    unlinked = [(a, b) for a, b in zip(reads, reads[1:])
                if paras[a]["end"] != paras[b]["start"]]
    if unlinked:
        print(f"abort: 鏈仍有破口 {unlinked}")
        sys.exit(2)

    def prev_read_end(i):
        for j in range(i - 1, -1, -1):
            if paras[j]["end"] > paras[j]["start"]:
                return paras[j]["end"]
        return 0.0

    for i, p in enumerate(paras):
        if i in confirmed_before:
            continue  # confirmed 零段錨點絕不動
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
    for i, p in enumerate(paras):
        if i in confirmed_before:
            assert json.dumps(p, ensure_ascii=False, sort_keys=True) \
                == confirmed_before[i], f"confirmed 段 [{i}] 被變更！"
        else:
            assert not p.get("confirmed"), "confirmed 被寫入！"
    assert not lec.get("reviewed"), "reviewed 被寫入！"

    path.write_text(new_raw, encoding="utf-8")
    print(f"\n已寫 {path}（{len(changes)} 段變更；confirmed/reviewed 未動）")


if __name__ == "__main__":
    main()
