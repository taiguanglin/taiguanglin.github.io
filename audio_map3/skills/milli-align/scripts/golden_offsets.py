#!/usr/bin/env python3
"""golden_offsets — 實測人工 golden 講次的對齊慣例（milli-align skill §5.1）.

量測並輸出：鏈誤差分佈、lead-in 分佈（start vs 第一個逐字內容字）、
講首導言 offset、zero 錨點統計。用來校準 milli-align skill 的 §2 表；
換系列時先跑這個，若與 skill 預設值差很多，以新實測為準。

用法：
  golden_offsets.py --series lengqie --golden 1-4
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
from realign_dtw import load_dump, norm_para  # noqa: E402
from align_lengqie import load_ebook_cls  # noqa: E402

DUMP_DIR = Path("/tmp/funasr_cache")
AMAP_DIR = ROOT / "audio_map3"


def parse_golden(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += [str(i) for i in range(int(a), int(b) + 1)]
        else:
            out.append(part.strip())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--golden", required=True, help="例 1-4")
    args = ap.parse_args()
    golden = parse_golden(args.golden)

    doc = json_load(AMAP_DIR / f"{args.series}.json")
    cls_map = load_ebook_cls()

    lead, chain, intro_off, zero_anchor = [], [], [], {"prev_end": 0, "next_start": 0, "other": 0}
    no_evidence = []

    for ln in golden:
        lec = doc["lectures"][ln]
        paras = lec["paragraphs"]
        cmap = {c["pid"]: c["cls"] for c in cls_map[ln]} if ln in cls_map else {}
        dump = load_dump(DUMP_DIR / args.series / f"{ln}.json")
        stream = "".join(dump["chars"])
        times = dump["times"]

        def t_of(q):
            if 0 <= q < len(times):
                t = times[q][0]
                if t is not None and t == t:
                    return float(t)
            return None

        reads = [i for i, p in enumerate(paras) if p["start"] < p["end"]]
        # 鏈
        for a, b in zip(reads, reads[1:]):
            chain.append(round(paras[a]["end"] - paras[b]["start"], 3))
        # lead-in：逐字頭（≥8 連續字）在 [start-6, start+2] 窗內
        for i in reads:
            norm = norm_para(paras[i]["text"])
            if len(norm) < 8:
                continue
            q = stream.find(norm[:8])
            hit = None
            while q >= 0:
                t = t_of(q)
                if t is None or not (paras[i]["start"] - 6 <= t <= paras[i]["start"] + 2):
                    q = stream.find(norm[:8], q + 1)
                    continue
                m = 8
                while m < len(norm) and q + m < len(stream) and stream[q + m] == norm[m]:
                    m += 1
                hit = (m, t)
                break
            if hit:
                lead.append(round(paras[i]["start"] - hit[1], 3))
            else:
                no_evidence.append((ln, i, cmap.get(paras[i]["pid"], "?")))
        # 導言
        first_t = next((t for t in times if t[0] == t[0]), None)
        if first_t is not None:
            intro = next((i for i, p in enumerate(paras)
                          if p["start"] < p["end"]
                          and cmap.get(p["pid"]) != "SUTRA"), None)
            if intro is not None:
                intro_off.append((ln, round(first_t[0], 3),
                                  round(paras[intro]["start"], 3),
                                  round(paras[intro]["start"] - first_t[0], 3)))
        # zero 錨點
        for i, p in enumerate(paras):
            if p["start"] < p["end"]:
                continue
            prev_e = next((paras[j]["end"] for j in range(i - 1, -1, -1)
                           if paras[j]["start"] < paras[j]["end"]), 0.0)
            nxt_s = next((paras[j]["start"] for j in range(i + 1, len(paras))
                          if paras[j]["start"] < paras[j]["end"]), None)
            if nxt_s is not None and abs(p["start"] - nxt_s) < 0.01:
                zero_anchor["next_start"] += 1
            elif abs(p["start"] - prev_e) < 0.01:
                zero_anchor["prev_end"] += 1
            else:
                zero_anchor["other"] += 1

    def stats(name, data):
        if not data:
            print(f"{name}: (none)")
            return
        s = sorted(data)
        print(f"{name}: n={len(data)} median={statistics.median(data):+.3f} "
              f"p10={s[len(s) // 10]:+.3f} p25={s[len(s) // 4]:+.3f} "
              f"p75={s[3 * len(s) // 4]:+.3f} p90={s[9 * len(s) // 10]:+.3f} "
              f"min={s[0]:+.3f} max={s[-1]:+.3f} "
              f"|x|<=0.3: {sum(1 for d in data if abs(d) <= 0.3) / len(data):.0%}")

    print(f"=== {args.series} golden L{args.golden} 慣例實測 ===")
    stats("lead-in (golden.start - t(first verbatim char))", lead)
    stats("chain gap (end[i] - start[next READ])", chain)
    print("\n講首導言 offset（intro.start - t(ASR 首字)）:")
    for ln, fc, st, off in intro_off:
        print(f"  L{ln}: first_char={fc} intro.start={st} offset={off:+.3f}")
    print(f"\nzero 錨點分佈: {zero_anchor}")
    print(f"無逐字頭證據的 READ 段（fuzzy/人工耳需要）: {len(no_evidence)}")
    for ln, i, c in no_evidence[:40]:
        print(f"  L{ln}[{i}] {c}")


def json_load(p):
    import json
    return json.loads(p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
