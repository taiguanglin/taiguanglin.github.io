#!/usr/bin/env python3
"""zero_audit — zero 段三向分診（milli-align skill §3 ①/③/④ 判準）.

對目標講次**每一個 zero 段**做：
  1. 量 R：在 [z-6s, z+18s] 窗內用字級 DTW 找 R 的最長實際念誦前綴
     （同音錯字視為逐字；以 score/len ≥0.85 逐長度回退），得到念誦 span。
  2. ③ 判準：下一 READ 段開頭是否 verbatim 重複 ≥80% 的 R（引號內重引）
     → 是 = ③，zero 正確（講解段攜帶念誦音頻）。
  3. 掉字偵測：窗內字級流是否有 >5s 空窗（ASR dropout）→ 無證據也不可信，須切片複驗。

判讀（skill §3）：
  head-block  z≈0 的講首印刷塊（書序參考文字），朗讀歸後方逐行引文段 → zero 正確
  3-keep      下一段 verbatim 重引 ≥80% R → zero 正確
  FALSE_ZERO  窗內找到 R 的念誦且下一段未重引 → 應為 READ（span=念誦 span）
  4?-dropout  無證據但窗內有 >5s 掉字 → 須 40s 切片複驗
  4?-check    無證據 → 抽查即可（但 L14/L15 教訓：仍建議抽切片）

用法：
  zero_audit.py --series lengqie --lecture 26 [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
sys.path.insert(0, str(ROOT / "audio_map3" / "skills" / "milli-align" / "scripts"))
from realign_dtw import load_dump, norm_para, sim_char  # noqa: E402
from series_cls import lecture_cls  # noqa: E402

DUMP_DIR = Path("/tmp/funasr_cache")
AMAP_DIR = ROOT / "audio_map3"

W_LO, W_HI = 6.0, 18.0      # evidence window around zero anchor
SCORE_MIN = 0.85            # per-char DTW score for "actually read"
MAX_R = 80                  # cap on R prefix length measured
RATE_MIN, RATE_MAX = 1.0, 12.0
DROPOUT = 5.0               # char-stream gap that invalidates "no evidence"
HEAD_BLOCK_T = 0.5          # z <= this = lecture-head printed block


def win_of(dump, lo, hi):
    ch, ts = [], []
    for k, c in enumerate(dump["chars"]):
        t = dump["times"][k][0]
        if t == t and lo <= t <= hi:
            ch.append(c)
            ts.append(t)
    return ch, ts


def r_prefix_cov(r: str, nxt: str) -> float:
    if not r or not nxt:
        return 0.0
    for k in range(len(r), 0, -1):
        if r[:k] in nxt:
            return k / len(r)
    return 0.0


GAP_HEAD = 14       # 找 R 頭時，允許跳過的窗內字數（上界）
GAP_FULL = 24       # 續量 R 全長時，允許跳過的窗內字數
SIM_MIN = 0.8       # 逐字相似度門檻（8/9/1.0 三級）


def _greedy(pat, ch, j0, gap):
    """從 ch[j0] 起貪婪對齊 pat（窗內可跳字），回 (matched, j_first, j_last)。"""
    i, k, last, matched = 0, j0, -1, 0
    n, m = len(pat), len(ch)
    while i < n and k < m:
        nk = None
        for kk in range(k, min(m, k + gap)):
            if sim_char(pat[i], ch[kk]) >= SIM_MIN:
                nk = kk
                break
        if nk is None:
            break
        matched += 1
        last = nk
        i += 1
        k = nk + 1
    return matched, j0, last


def measure_r(r, ch, ts):
    """量 R 的實際念誦：回 (matched, t0, t1, cov, rate)。

    用「容錯跳字」而非 DTW score：講解與經文常交錯，DTW 的 window-noise 罰分
    會把「有念」壓到 0.6 以下（L26 [20] 實證）。改為貪婪定位 R 頭（16 字，允許
    跳字）→ 再續量全 R，並用語速 1–12 字/s 自檢。
    """
    if not ch or not r:
        return None
    loc = _greedy(r[:16], ch, 0, GAP_HEAD) if len(ch) <= 16 else None
    # 掃所有起點取最長命中
    best = None
    for j in range(len(ch)):
        if sim_char(r[0], ch[j]) < SIM_MIN:
            continue
        m_, _, last = _greedy(r[:16], ch, j, GAP_HEAD)
        if last >= 0 and (best is None or m_ > best[0]):
            best = (m_, j, last)
    if best is None or best[0] < 6:
        return None
    j0 = best[1]
    matched, _, last = _greedy(r[:MAX_R], ch, j0, GAP_FULL)
    if matched < 6 or last < 0:
        return None
    span = ts[last] - ts[j0]
    if span <= 0.05:
        return None
    rate = matched / span
    if not (RATE_MIN <= rate <= RATE_MAX):
        return None
    return (matched, ts[j0], ts[last], round(matched / len(r), 2), round(rate, 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--lecture", required=True)
    ap.add_argument("--json", help="分診表輸出路徑")
    a = ap.parse_args()

    doc = json.loads((AMAP_DIR / f"{a.series}.json").read_text(encoding="utf-8"))
    lec = doc["lectures"][a.lecture]
    ps = lec["paragraphs"]
    dump = load_dump(DUMP_DIR / a.series / f"{a.lecture}.json")
    cls = lecture_cls(a.series, a.lecture) if a.series == "lengqie" else {}
    dur = lec.get("duration") or 1e9
    reads = [j for j, q in enumerate(ps) if q["end"] > q["start"]]

    rows = []
    for i, p in enumerate(ps):
        if p["end"] > p["start"]:
            continue
        z = p["start"]
        r = norm_para(p["text"])
        nxt = next((q for q in ps[i + 1:] if q["end"] > q["start"]), None)
        nxt_i = next((j for j in reads if j > i), None)
        cov = r_prefix_cov(r, norm_para(nxt["text"])[:80]) if nxt else 0.0

        ch, ts = win_of(dump, max(0.0, z - W_LO), min(dur, z + W_HI))
        gaps = [ts[k + 1] - ts[k] for k in range(len(ts) - 1)]
        drop = max(gaps) if gaps else 99.0
        m = measure_r(r, ch, ts)

        owner = None
        if m:
            for j in reads:
                if ps[j]["start"] - 0.35 <= m[1] <= ps[j]["end"] + 0.35:
                    owner = j
                    break
        if z <= HEAD_BLOCK_T:
            verdict = "head-block"
        elif m:
            verdict = "FALSE_ZERO" if owner in (None, nxt_i) else f"owned-by-{owner}"
        elif cov >= 0.8:
            verdict = "3-keep"
        elif drop > DROPOUT:
            verdict = "4?-dropout"
        else:
            verdict = "4?-check"

        rows.append({
            "i": i, "z": round(z, 2), "cls": cls.get(p.get("pid"), ""),
            "zero_conf": p.get("conf"), "verdict": verdict, "cov_next": round(cov, 2),
            "next_read": nxt_i, "owner": owner,
            "read": None if not m else {"k": m[0], "t0": round(m[1], 2), "t1": round(m[2], 2),
                                        "cov": m[3], "rate": m[4]},
            "max_gap": round(drop, 1), "text": p["text"][:46],
        })

    cnt = {}
    for r_ in rows:
        cnt[r_["verdict"]] = cnt.get(r_["verdict"], 0) + 1
    print(f"L{a.lecture}: zero {len(rows)} 段 → " + "  ".join(f"{k} {v}" for k, v in sorted(cnt.items())))
    for r_ in rows:
        if r_["verdict"] in ("head-block", "3-keep"):
            continue
        rd = r_["read"]
        ev = f"R{rd['k']} {rd['t0']}-{rd['t1']} cov={rd['cov']}" if rd else "—"
        print(f"  [{r_['i']:>3}] {r_['verdict']:<14} z={r_['z']:>8.2f} cov={r_['cov_next']:<4} "
              f"nxt={r_['next_read']} own={r_['owner']} gap={r_['max_gap']:>5}  {ev:<32} {r_['text']}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
