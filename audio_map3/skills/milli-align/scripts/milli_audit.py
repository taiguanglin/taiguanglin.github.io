#!/usr/bin/env python3
"""milli_audit — 逐段證據稽核（milli-align skill §4.2）.

對目標講次的每段，在鏈夾逼窗內找頭部證據（逐字 → 拼音 DTW），檢查語速、
zero 的逐字不念、鏈完整性、COMM 零寬，輸出 defects 清單。
自報 conf 不可信，以本稽核為準。

用法：
  milli_audit.py --series lengqie --lecture 5 [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
from realign_dtw import load_dump, norm_para, py_string, dtw_span  # noqa: E402
from align_lengqie import load_ebook_cls  # noqa: E402
from series_cls import lecture_cls as _series_cls  # noqa: E402

DUMP_DIR = Path("/tmp/funasr_cache")
AMAP_DIR = ROOT / "audio_map3"

RATE_MIN, RATE_MAX = 0.5, 12.0


def lecture_cls(series, ln):
    """lengqie 走原路徑（golden 等價）；其餘系列走泛化載入器。"""
    if series == "lengqie":
        try:
            return {c["pid"]: c["cls"] for c in load_ebook_cls()[ln]}
        except KeyError:
            return {}
    return _series_cls(series, ln)


def head_hits(norm, stream, tstarts, lo, hi):
    """逐字頭命中：norm 前綴（8→6）在 [lo,hi] 內的所有出現，回最長匹配。"""
    out = []
    for k in (8, 6):
        if len(norm) < k:
            continue
        needle = norm[:k]
        q = stream.find(needle)
        while q >= 0:
            t = tstarts[q] if q < len(tstarts) else float("nan")
            if t == t and lo <= t <= hi:
                m = k
                while m < len(norm) and q + m < len(stream) \
                        and stream[q + m] == norm[m]:
                    m += 1
                out.append((m, float(t), q))
            q = stream.find(needle, q + 1)
        if out:
            break
    return out


def fuzzy_head(norm, chars, tstarts, lo, hi, head=14):
    """拼音 DTW 頭部命中（只回報分數與時間，不作最終判斷）。"""
    idx = [j for j, t in enumerate(tstarts) if t == t and lo <= t <= hi]
    if len(idx) < 6:
        return None
    pat = list(norm[:head])
    a, b = idx[0], idx[-1]
    sc, jf, jl = dtw_span(pat, chars[a:b + 1])
    if jf is None or jf < 0:
        return None
    score = sc / max(1, len(pat))
    t = tstarts[a + jf] if a + jf < len(tstarts) else float("nan")
    return (round(float(score), 3), float(t) if t == t else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--lecture", required=True)
    ap.add_argument("--json", help="report 輸出路徑")
    args = ap.parse_args()

    doc = json.loads((AMAP_DIR / f"{args.series}.json").read_text(encoding="utf-8"))
    lec = doc["lectures"][args.lecture]
    paras = lec["paragraphs"]
    dur = lec.get("duration") or 0
    cmap = lecture_cls(args.series, args.lecture)

    dump = load_dump(DUMP_DIR / args.series / f"{args.lecture}.json")
    chars = dump["chars"]
    stream = "".join(chars)
    tstarts = np.array([t[0] if t[0] == t[0] else np.nan for t in dump["times"]],
                       dtype=float)

    reads = [i for i, p in enumerate(paras) if p["end"] > p["start"]]

    def prev_read_end(i):
        for j in range(i - 1, -1, -1):
            if paras[j]["end"] > paras[j]["start"]:
                return paras[j]["end"]
        return 0.0

    def next_read_start(i):
        for j in range(i + 1, len(paras)):
            if paras[j]["end"] > paras[j]["start"]:
                return paras[j]["start"]
        return dur

    rows, defects = [], []
    for i, p in enumerate(paras):
        cls = cmap.get(p["pid"], "?")
        norm = norm_para(p["text"])
        lo, hi = prev_read_end(i) - 0.3, next_read_start(i) + 0.3
        row = {"i": i, "cls": cls, "pid": p["pid"], "start": p["start"],
               "end": p["end"], "conf": p.get("conf"), "zero": bool(p.get("zero")),
               "d": []}
        if p["start"] < p["end"]:
            hits = head_hits(norm, stream, tstarts, lo, hi)
            if hits:
                m, t, q = max(hits)
                row["verb"] = {"m": m, "t": round(t, 2),
                               "off": round(p["start"] - t, 2)}
            fz = fuzzy_head(norm, chars, tstarts, lo, hi)
            if fz:
                row["fuzzy"] = {"score": fz[0], "t": round(fz[1], 2),
                                "off": round(p["start"] - fz[1], 2)} if fz[1] else None
            rate = len(norm) / max(0.5, p["end"] - p["start"])
            row["rate"] = round(rate, 2)
            if row.get("verb") and row["verb"]["off"] > 0.5:
                row["d"].append(f"late: start 比 verb 命中晚 {row['verb']['off']}s")
            if row.get("verb") and row["verb"]["off"] < -6:
                # 半念頭 + 跨內 verbatim 重複 → echo，不是 early：
                # 若窗內有 ≥0.7 的 fuzzy 命中落在 [start−0.5, start+3]，即證實段首有內容
                fz = row.get("fuzzy")
                echo_ok = (fz and fz.get("t") is not None
                           and row["start"] - 0.5 <= fz["t"] <= row["start"] + 3
                           and fz["score"] >= 0.7)
                if not echo_ok:
                    row["d"].append(f"early: start 比 verb 命中早 {abs(row['verb']['off'])}s")
            if not row.get("verb") and not row.get("fuzzy"):
                row["d"].append("no-evidence（頭部逐字/拼音皆無窗內命中）")
            if rate < RATE_MIN:
                row["d"].append(f"fat? 語速 {rate} 字/s（可能吞鄰段）")
            if rate > RATE_MAX and (p["end"] - p["start"]) > 3.5:
                # 短 span（半念：只框「實際念出的那截」）的 rate 以全文計算是雜訊，不旗標
                row["d"].append(f"impossible rate {rate} 字/s")
            if cls == "COMM" and p["end"] - p["start"] < 0.5:
                row["d"].append("COMM 零寬/近零寬")
            if cls == "COMM" and p.get("zero"):
                row["d"].append("COMM 被標 zero（不允許）")
        else:
            row["d"].append("zero")
            if len(norm) >= 8 and norm[:8] and stream.find(norm[:8]) >= 0:
                row["d"].append("⚠ 頭 8 字逐字出現過（可能其實有念）")
            if not p.get("zero") and cls != "SUTRA":
                row["d"].append("非 SUTRA 零寬且未標 zero")
        if row["d"]:
            defects.append(row)
        rows.append(row)

    # 鏈檢查
    chain_bad = 0
    for a, b in zip(reads, reads[1:]):
        if paras[a]["end"] != paras[b]["start"]:
            chain_bad += 1
            defects.append({"i": a, "start": paras[a]["start"], "end": paras[a]["end"],
                            "d": [f"chain: end={paras[a]['end']} != "
                                  f"next start={paras[b]['start']}"]})
    if reads and paras[reads[-1]]["end"] != dur:
        defects.append({"i": reads[-1],
                        "start": paras[reads[-1]]["start"],
                        "end": paras[reads[-1]]["end"],
                        "d": [f"末段 end={paras[reads[-1]]['end']} != duration={dur}"]})

    n_read = len(reads)
    print(f"L{args.lecture}: {len(paras)} 段（READ {n_read} / zero {len(paras) - n_read}），"
          f"duration={dur}")
    verb_n = sum(1 for r in rows if r.get("verb"))
    fz_n = sum(1 for r in rows if r.get("fuzzy") and not r.get("verb"))
    noev = sum(1 for r in rows if "READ" and r.get("d") and any("no-evidence" in d for d in r["d"]))
    print(f"頭部證據：verbatim {verb_n} / fuzzy-only {fz_n} / no-evidence {noev}")
    print(f"鏈破口 {chain_bad}；defect 段數 {len({d['i'] for d in defects})}")
    print("\n=== defects（除 zero 外都值得看）===")
    for r in defects:
        cls = r.get("cls", "")
        tag = " ".join(r["d"])
        extra = ""
        if r.get("verb"):
            extra += f" verb m={r['verb']['m']} t={r['verb']['t']} off={r['verb']['off']}"
        if r.get("fuzzy"):
            extra += f" fuzzy s={r['fuzzy']['score']} t={r['fuzzy']['t']}"
        if r.get("rate") is not None:
            extra += f" rate={r['rate']}"
        if r.get("text") is None and r["i"] < len(paras):
            t = paras[r["i"]]["text"][:30]
            print(f"[{r['i']:3d}] {cls:5s} {r.get('start', 0):8.2f}-{r.get('end', 0):8.2f} "
                  f"conf={r.get('conf')}: {tag}{extra}  {t}")

    if args.json:
        Path(args.json).write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nreport → {args.json}")


if __name__ == "__main__":
    main()
