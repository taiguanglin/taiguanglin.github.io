#!/usr/bin/env python3
"""zero_probe.py — 零寬段「該不該唸」的字級證據快照（milli-align 輔助工具）

對每個候選零寬段印出：
  1. 該段開頭文字（用來跟字級流對照）
  2. anchor 前後的字級字流（預設 anchor-1s ~ anchor+15s），逐 12 字一行
  3. 下一個 READ 段的開頭文字（判斷講解從哪裡接手）

判讀方式：把 (1) 的頭幾個字拿去跟 (2) 比對——
  - 逐字／同音可辨 → 假 zero，該段是 READ，span 起點 = 該串 content 字的 run-onset。
  - 完全找不到、而且 (3) 的講解文字緊接在 anchor 後 → 真 zero（經文被講解取代）。
  - 找不到但 (2) 呈現大量缺口（>5s 無字）→ ASR dropout，需切片複驗（clip_probe.py）。

用法：
  zero_probe.py --series lengqie --lecture 26 [--indices 20,29,31] [--pre 1] [--post 15]
不給 --indices 時，自動讀 /tmp/za_<N>.json 的非 head-block 候選。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
from realign_dtw import load_dump  # noqa: E402

DUMP = Path("/tmp/funasr_cache")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--lecture", type=int, required=True)
    ap.add_argument("--indices", help="逗號分隔；不給則用 /tmp/za_<N>.json 候選")
    ap.add_argument("--pre", type=float, default=1.0)
    ap.add_argument("--post", type=float, default=15.0)
    a = ap.parse_args()

    doc = json.loads((ROOT / "audio_map3" / f"{a.series}.json").read_text())
    ps = doc["lectures"][str(a.lecture)]["paragraphs"]
    dump = load_dump(DUMP / a.series / f"{a.lecture}.json")
    chars, times = dump["chars"], dump["times"]

    if a.indices:
        idxs = [int(x) for x in a.indices.split(",") if x.strip()]
    else:
        za = Path(f"/tmp/za_{a.lecture}.json")
        idxs = [r["i"] for r in json.loads(za.read_text())
                if r["verdict"] not in ("head-block", "3-keep")]

    for i in idxs:
        p = ps[i]
        z = p["start"]
        nxt = next((j for j in range(i + 1, len(ps)) if ps[j]["end"] > ps[j]["start"]), None)
        print(f"=== [{i}] anchor={z:.2f} c={p.get('conf')} zero={p['end'] <= p['start']}")
        print(f"    TEXT: {p['text'][:110]}")
        if nxt is not None:
            print(f"    NEXT[{nxt}] start={ps[nxt]['start']:.2f}: {ps[nxt]['text'][:80]}")
        buf = [(t, c) for k, c in enumerate(chars)
               if (t := times[k][0]) == t and z - a.pre <= t <= z + a.post]
        for k in range(0, len(buf), 12):
            chunk = buf[k:k + 12]
            print(f"    [{chunk[0][0]:8.2f}] {''.join(c for _, c in chunk)}")
        print()


if __name__ == "__main__":
    main()
