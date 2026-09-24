#!/usr/bin/env python3
"""batch_verify — 段首批量驗證（milli-align skill §7.5／§10）.

對目標講次的**每一個 READ 段**，在鏈夾逼窗內找「第一個內容字」的逐字／拼音證據，
依 golden 慣例（start = run-onset，絕不晚於內容字；lead-in 0–4s 合法）檢查現值：
  - late（start 晚於內容字 +0.05s）→ 建議 run-onset 修復（唯一命中才自動；多重命中列人工）
  - early?（start 早於內容字 4.5s 以上）→ 列人工（echo／錨錯）
  - rate 胖／瘦／impossible、no-evidence、zero 段逐字有念 → 列人工
輸出 suspects JSON（每筆含建議 start/建議依據），供逐段判讀後寫 adjudication table。

用法：
  batch_verify.py --series liuzutanjing --lecture 1 [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
from realign_dtw import load_dump, norm_para, dtw_span  # noqa: E402
from series_cls import lecture_cls  # noqa: E402

DUMP_DIR = Path("/tmp/funasr_cache")
AMAP_DIR = ROOT / "audio_map3"

LATE_TOL = 0.05      # start 晚於內容字超過此值 → late（golden max 0.00）
EARLY_LIM = 4.5      # start 早於內容字超過此值 → early?（golden lead-in 0–4s）
RATE_MIN, RATE_MAX = 0.5, 12.0
RATE_THIN = 1.5      # 引文 span >8s 且 rate <1.5 → 必吞鄰段


def verb_hits(norm, stream, tstarts, lo, hi):
    """norm 前綴（8→6）在窗內的所有出現；回 (最長m, 該m的最早t, q, 出現數)。"""
    all_hits = []
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
                all_hits.append((m, float(t), q))
            q = stream.find(needle, q + 1)
        if all_hits:
            break
    if not all_hits:
        return None
    mmax = max(h[0] for h in all_hits)
    best = [h for h in all_hits if h[0] == mmax]
    best.sort(key=lambda h: h[1])          # earliest 偏好
    return mmax, best[0][1], best[0][2], len(all_hits)


def fuzzy_head(norm, chars, tstarts, lo, hi, head=14):
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


def run_onset(times, q, prev_end, th=0.7):
    """從內容字 q 往回走：第一個 ≥th 停頓處停（golden §A.2），
    越過 prev_end 或走滿 3s 都算「無邊界」→ 連續語流 fallback（內容字 −0.2s）。
    L6 [9] 教訓：≥2.5s 純靜音不鏈進 lead（fallback 內容字−0.2 即符合）。"""
    t0 = times[q][0]
    k = q
    onset = t0
    while k > 0:
        pe = times[k - 1][1]
        ps = times[k - 1][0]
        if pe != pe or ps != ps:
            break
        if pe < prev_end - 1e-9:
            break
        if onset - pe >= th:
            return round(onset, 3)
        if t0 - ps > 3.0:
            break
        onset = ps
        k -= 1
    # 無 ≥0.7s 邊界（連續語流或純靜音）→ 邊界落「前一個字元結束」與
    # 「內容字 −0.2s」之間取大、且不晚於內容字（golden 導言 offset，永不晚於內容字）
    prev_ch_end = times[q - 1][1] if q > 0 and times[q - 1][1] == times[q - 1][1] else 0.0
    return round(min(max(prev_ch_end, t0 - 0.2), t0), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--lecture", required=True)
    ap.add_argument("--json", help="suspects 輸出路徑")
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
    times = dump["times"]

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

    suspects = []
    n_read = n_verb = n_fuzzy = 0
    for i, p in enumerate(paras):
        cls = cmap.get(p["pid"], "?")
        norm = norm_para(p["text"])
        lo, hi = prev_read_end(i) - 0.3, next_read_start(i) + 0.3
        pe = prev_read_end(i)
        row = {"i": i, "cls": cls, "pid": p["pid"], "start": p["start"],
               "end": p["end"], "conf": p.get("conf"), "zero": bool(p.get("zero")),
               "text": p["text"][:40], "d": [], "fix": None}
        if p["start"] < p["end"]:
            n_read += 1
            hits = verb_hits(norm, stream, tstarts, lo, hi)
            span = p["end"] - p["start"]
            rate = len(norm) / max(0.5, span)
            row["rate"] = round(rate, 2)
            proposed = None
            if hits:
                m, t, q, n_occ = hits
                n_verb += 1
                row["verb"] = {"m": m, "t": round(t, 2), "off": round(p["start"] - t, 2),
                               "n_occ": n_occ}
                if p["start"] > t + LATE_TOL:
                    if n_occ == 1:
                        proposed = run_onset(times, q, pe)
                        row["d"].append(
                            f"late {row['verb']['off']}s → run-onset {proposed}")
                    else:
                        row["d"].append(
                            f"late {row['verb']['off']}s（{n_occ} 處命中，列人工）")
                elif p["start"] < t - EARLY_LIM:
                    row["d"].append(f"early? {row['verb']['off']}s（echo／錨錯，列人工）")
            else:
                fz = fuzzy_head(norm, chars, tstarts, lo, hi)
                if fz:
                    n_fuzzy += 1
                    row["fuzzy"] = {"score": fz[0], "t": round(fz[1], 2)} if fz[1] else {"score": fz[0]}
                    if fz[1] and p["start"] > fz[1] + 0.6:
                        if fz[0] >= 0.7:
                            # 以 fuzzy 首字時間為內容字錨，跑同一 run-onset 邏輯
                            qf = int(np.nanargmin(np.abs(tstarts - fz[1]))) \
                                if len(tstarts) else 0
                            proposed = run_onset(times, qf, pe)
                            row["d"].append(
                                f"fuzzy-late {round(p['start'] - fz[1], 2)}s "
                                f"→ run-onset {proposed}")
                        else:
                            row["d"].append(f"fuzzy-late {round(p['start'] - fz[1], 2)}s")
                    elif fz[1] and p["start"] < fz[1] - 4.5:
                        row["d"].append(f"fuzzy-early? {round(p['start'] - fz[1], 2)}s")
                else:
                    row["d"].append("no-evidence（頭部逐字/拼音皆無窗內命中）")
            if rate < RATE_MIN:
                row["d"].append(f"fat? 語速 {rate} 字/s（可能吞鄰段）")
            if rate > RATE_MAX and span > 3.5:
                row["d"].append(f"impossible rate {rate} 字/s")
            if cls == "SUTRA" and rate < RATE_THIN and span > 8:
                row["d"].append(f"引文瘦? {rate} 字/s")
            if proposed is not None:
                row["fix"] = {"start": proposed}
        else:
            # zero-width 段
            if len(norm) >= 8 and stream.find(norm[:8]) >= 0 and lo <= 1e18:
                # 頭 8 字逐字出現過（可能其實有念）——驗證是否落在窗內
                qs = []
                qq = stream.find(norm[:8])
                while qq >= 0:
                    t = tstarts[qq] if qq < len(tstarts) else float("nan")
                    if t == t and lo <= t <= hi:
                        qs.append(round(float(t), 2))
                    qq = stream.find(norm[:8], qq + 1)
                if qs:
                    row["d"].append(f"zero ⚠ 頭 8 字窗內逐字出現 @ {qs}（可能其實有念）")
            if cls == "COMM":
                row["d"].append("COMM 零寬（永不 zero：需重錨或人工確認）")
        if row["d"]:
            suspects.append(row)

    print(f"L{args.lecture}: {len(paras)} 段（READ {n_read}），duration={dur}")
    print(f"證據：verbatim {n_verb} / fuzzy-only {n_fuzzy} / "
          f"無 {n_read - n_verb - n_fuzzy}")
    print(f"suspect 段數 {len(suspects)}（auto-fix {sum(1 for s in suspects if s['fix'])}）")
    for s in suspects:
        tag = " ; ".join(s["d"])
        fx = f" ⇒fix {s['fix']['start']}" if s["fix"] else ""
        print(f"[{s['i']:3d}] {s['cls']:5s} {s['start']:8.2f}-{s['end']:8.2f} "
              f"conf={s['conf']}{fx}  {tag}  {s['text']}")

    if args.json:
        Path(args.json).write_text(
            json.dumps(suspects, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nsuspects → {args.json}")


if __name__ == "__main__":
    main()
