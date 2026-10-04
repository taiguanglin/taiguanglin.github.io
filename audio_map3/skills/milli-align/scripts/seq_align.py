#!/usr/bin/env python3
"""seq_align — 序列式逐段對齊器（milli-align skill 的「改匹配器」路線）.

AGENTS §3a 的結論是「換更好的 ASR 無用，方向應是改匹配器」。本檔就是那個匹配器：
把整講當成一條**單調序列**來對（cursor 只往前走），每段用三層證據定「實際念出的
第一個字」：

  L1 逐字 needle（12→10→8→6 字，全窗內取最長延伸）
  L2 拼音 DTW（16 字頭窗 ＋ find_anchor 的 4-gram 種子候選）
  L3 全文覆蓋（把段落**整段**餵進 DTW，看實際念誦比例）

再依 SKILL §2 golden 慣例收邊界：start = run-onset（從第一個內容字往回走，
逐字間隔 ≤0.7s 就吸收），end = 下一個 READ 段的 start（鏈），末段 = duration。
兩種輸出：

  --mode rough    每段的候選 start ＋證據分數（給逐段判讀用）
  --mode verify   對**現有** JSON 做全文覆蓋與邊界雙向稽核（找 defect）

⚠️ 本檔是唯讀分析器：不寫 audio_map3/*.json。套用一律走 scripts/milli_refine.py
（保護 confirmed／reviewed／非目標講次）。手動判讀結果寫成 adjudication table
（reports/）再套用。

用法：
  seq_align.py --series lengqie --lecture 13 --mode rough  [--json out.json]
  seq_align.py --series lengqie --lecture 13 --mode verify [--json out.json]
  seq_align.py --series lengqie --lecture 13 --mode window --i 31 --pad 8
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
sys.path.insert(0, str(ROOT / "audio_map3" / "skills" / "milli-align" / "scripts"))
from realign_dtw import (  # noqa: E402
    FILLER_RE,
    dtw_span,
    find_anchor,
    load_dump,
    norm_para,
    py_string,
    sim_char,
)
from align_lengqie import load_ebook_cls  # noqa: E402
from series_cls import lecture_cls as _generic_cls  # noqa: E402

DUMP_DIR = Path("/tmp/funasr_cache")
AMAP_DIR = ROOT / "audio_map3"

# 語速鐵律（SKILL §2）：朗讀 1–12 字/s。胖 span <0.8 吞鄰段、瘦 span >12 是幻影。
RATE_MIN, RATE_MAX = 0.8, 12.0
ONSET_BACK = 0.7          # run-onset：內容字往回吸收 ≤0.7s 的停頓／語氣詞
SCORE_STRONG = 0.80       # DTW 覆蓋率 ≥ 此值 = 有逐字級證據
SCORE_WEAK = 0.62         # ≥ 此值 = 只有拼音級證據
NEEDLES = (12, 10, 8, 6)
HEAD_PY = 16              # 拼音 DTW 的頭窗長度
CAP = 26                  # 頭部 DTW 的比對長度上界
FULL_CAP = 90             # 全文覆蓋比對的長度上界（長段取頭 90 字）


def lecture_cls(series, ln):
    if series == "lengqie":
        try:
            return {c["pid"]: c["cls"] for c in load_ebook_cls()[ln]}
        except KeyError:
            return {}
    return _generic_cls(series, ln)


class Stream:
    """ASR 字元流（去語氣詞後的 norm 空間 ↔ 原字元索引 的雙向映射）。"""

    def __init__(self, dump):
        chars = dump["chars"]
        times = dump["times"]
        self.chars = chars
        self.times = times
        self.tstarts = np.array([t[0] if t[0] == t[0] else np.nan for t in times],
                                dtype=float)
        # 去語氣詞（FILLER_RE）：段落 norm 也去，兩邊口徑一致才可比
        keep = [k for k, c in enumerate(chars) if not FILLER_RE.fullmatch(c)]
        self.norm = "".join(chars[k] for k in keep)
        self.n2c = np.array(keep, dtype=np.int64)   # norm 位置 → 原字元索引
        self.c2n = np.full(len(chars), -1, dtype=np.int64)
        for q, k in enumerate(keep):
            self.c2n[k] = q
        self.py = py_string(self.norm)
        lens = [len(py_string(c)) for c in self.norm]
        self.norm2py = np.concatenate(([0], np.cumsum(lens))).astype(np.int64)

    def t_of(self, q_norm):
        """norm 位置 → 該字元的起始秒（nan → None）。"""
        if q_norm is None or not (0 <= q_norm < len(self.n2c)):
            return None
        t = self.tstarts[self.n2c[q_norm]]
        return float(t) if t == t else None

    def t_end_of(self, q_norm):
        """norm 位置 → 該字元的結束秒（吞尾邊界要用 END-time，不是字首 onset）。"""
        if q_norm is None or not (0 <= q_norm < len(self.n2c)):
            return None
        k = self.n2c[q_norm]
        e = self.times[k][1]
        return float(e) if e == e else None

    def run_onset(self, q_norm, max_back=ONSET_BACK):
        """首字前的 run-onset（SKILL §2）。

        **只吸收「首字之前的那一段停頓」**，不往前吞整句：金色講次實測
        start 落在首個內容字前 0–4s（中位 −0.84s），但那是因為師父常先說一句
        引導語再進入正文；引導語屬於**前一段**的音訊（鏈 end[i−1]=start[i]），
        若把它們算進本段，本段就會吞掉前段尾巴（§4.1 吞尾）。

        實作：回退量 = min(max_back, 與前一個 ASR 字元的間隔)。連續語音間隔
        通常 0.2–0.5s → 只回退那個間隔；靜停 ≥0.7s → 回退滿 0.7s。
        """
        t = self.t_of(q_norm)
        if t is None:
            return None
        j = int(self.n2c[q_norm])
        if j - 1 < 0:
            return round(t, 3)
        tp = self.tstarts[j - 1]
        if tp != tp:
            return round(t, 3)
        gap = t - float(tp)
        back = max(0.0, min(max_back, gap))
        return round(t - back, 3)


def dtw_cov(pat, win):
    """DTW 覆蓋率 + 首末字元（窗內）位置。"""
    n, m = len(pat), len(win)
    if n == 0 or m == 0:
        return 0.0, -1, -1
    sc, jf, jl = dtw_span(list(pat), list(win))
    if jf < 0:
        return 0.0, -1, -1
    return sc / n, jf, jl


def head_candidates(st, norm, q_lo, q_hi):
    """L1 逐字 ＋ L2 拼音候選（norm 空間）。"""
    out = {}

    def put(q, kind, base):
        if q_lo <= q < q_hi and q not in out:
            out[q] = (kind, base)

    for k in NEEDLES:
        if len(norm) < k:
            continue
        q = st.norm.find(norm[:k], q_lo, q_hi)
        while q >= 0:
            put(q, "verb", k)
            q = st.norm.find(norm[:k], q + 1, q_hi)
    if len(norm) >= 6:
        needle = norm[:min(HEAD_PY, len(norm))]
        for sc, q in find_anchor(needle, st.norm, q_lo, st.py, st.norm2py,
                                 scan_norm=q_hi - q_lo, max_cands=6):
            put(q, "py", sc)
    return out


def score_at(st, norm, q, cap=CAP):
    """在 norm 位置 q 起比對段落頭，返回 (cov, q_first, q_last)（norm 空間）。"""
    pat = list(norm[:min(cap, len(norm))])
    cov, jf, jl = dtw_cov(pat, list(st.norm[q:q + len(pat) + 10]))
    if jf < 0:
        return 0.0, None, None
    return cov, q + jf, q + jl


def full_cov(st, norm, q, cap=FULL_CAP):
    """段落全文（頭 cap 字）對齊覆蓋率 —— 用來分辨「念了」與「沒念」。"""
    pat = list(norm[:min(cap, len(norm))])
    cov, jf, jl = dtw_cov(pat, list(st.norm[q:q + len(pat) + 16]))
    if jf < 0:
        return 0.0, -1, -1
    return cov, q + jf, q + jl


def load(series, lecture):
    doc = json.loads((AMAP_DIR / f"{series}.json").read_text(encoding="utf-8"))
    lec = doc["lectures"][lecture]
    dump = load_dump(DUMP_DIR / series / f"{lecture}.json")
    return lec, Stream(dump), lecture_cls(series, lecture)


# --------------------------------------------------------------------------
# rough：由證據重新推導每段 start（單調游標）
# --------------------------------------------------------------------------

def mode_rough(series, lecture, out_json=None):
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    dur = lec.get("duration") or 0.0
    norms = [norm_para(p["text"]) for p in ps]
    M = len(st.norm)

    # 講首：ASR 首字 −0.2s（golden 慣例）
    first_t = None
    for q in range(M):
        t = st.t_of(q)
        if t is not None:
            first_t = t
            break
    anchor0 = round(max(0.0, first_t - 0.2), 3) if first_t is not None else 0.0

    rows, cursor = [], 0
    prev_anchor_t = anchor0
    for i, p in enumerate(ps):
        norm = norms[i]
        cls = cmap.get(p["pid"], "?")
        if i == 0 and (p.get("zero") or p["end"] <= p["start"]):
            # 講首印刷塊：§4.6(a) 書序≠語序 → zero 錨在講首導言之前
            rows.append({"i": i, "cls": cls, "verdict": "zero-head-block",
                         "start": 0.0, "cursor": cursor})
            continue
        # 搜尋窗：cursor 之後，長度隨段落長度放寬（念誦速率 1–12 字/s 的上限）
        q_t = st.t_of(cursor) if cursor < M else None
        base_t = q_t if q_t is not None else prev_anchor_t
        span_s = min(dur - base_t, max(45.0, len(norm) / 1.6 + 25.0))
        q_lo = cursor
        q_hi = M
        for q in range(q_lo, M):
            t = st.t_of(q)
            if t is not None and t > base_t + span_s:
                q_hi = q
                break
        cands = head_candidates(st, norm, q_lo, max(q_lo + 1, q_hi))
        best = None
        for q, (kind, base) in cands.items():
            cov, qf, ql = score_at(st, norm, q)
            if cov < SCORE_WEAK:
                continue
            key = (round(cov, 3), -q)
            if best is None or key > best[0]:
                best = (key, q, kind, base, cov, qf, ql)
        row = {"i": i, "cls": cls, "n": len(norm)}
        if best is None:
            row.update({"verdict": "no-evidence", "start": None})
            rows.append(row)
            continue
        _, q, kind, base, cov, qf, ql = best
        fc, fqf, fql = full_cov(st, norm, q)
        t0 = st.t_of(qf)
        row.update({
            "verdict": "read", "q": int(q), "kind": kind, "head_cov": round(cov, 3),
            "full_cov": round(fc, 3), "t_first": None if t0 is None else round(t0, 3),
            "t_run": st.run_onset(fqf if fqf >= 0 else q),
            "t_last": (lambda x: None if x is None else round(x, 3))(st.t_end_of(fql)),
            "start": st.run_onset(fqf if fqf >= 0 else q),
        })
        rows.append(row)
        if fc >= SCORE_WEAK:
            cursor = min(M, fql + 1)
            prev_anchor_t = rows[-1]["t_last"] or prev_anchor_t

    for r in rows:
        print(f"[{r['i']:3d}] {r.get('cls',''):5s} {str(r.get('start')):>9s} "
              f"{r['verdict']:<14} head={r.get('head_cov')} full={r.get('full_cov')} "
              f"{'kind=' + r['kind'] if r.get('kind') else ''} {ps[r['i']]['text'][:26]}")
    if out_json:
        Path(out_json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        print(f"\n→ {out_json}")
    return rows


# --------------------------------------------------------------------------
# verify：對現有 JSON 做全文覆蓋＋邊界雙向稽核
# --------------------------------------------------------------------------

def mode_verify(series, lecture, out_json=None):
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    dur = lec.get("duration") or 0.0
    norms = [norm_para(p["text"]) for p in ps]
    M = len(st.norm)

    def pos_at(t):
        """時間 → norm 位置（最近的前一個字元）。"""
        best = 0
        for q in range(M):
            tt = st.t_of(q)
            if tt is not None and tt <= t:
                best = q
            elif tt is not None and tt > t:
                break
        return best

    rows = []
    for i, p in enumerate(ps):
        norm = norms[i]
        row = {"i": i, "cls": cmap.get(p["pid"], "?"), "start": p["start"],
               "end": p["end"], "conf": p.get("conf"), "zero": bool(p.get("zero")),
               "d": []}
        if p["end"] > p["start"]:
            q0 = pos_at(p["start"] - 0.6)
            q1 = pos_at(p["end"] + 0.6)
            fc, jf, jl = dtw_cov(list(norm[:FULL_CAP]), list(st.norm[q0:q1 + 1]))
            row["full_cov"] = round(fc, 3)
            tf = st.t_of(q0 + jf) if jf >= 0 else None
            row["t_first"] = None if tf is None else round(tf, 3)
            row["off"] = None if tf is None else round(p["start"] - tf, 2)
            if fc < SCORE_WEAK:
                row["d"].append(f"full-cov {fc:.2f} 低：可能吞鄰段／沒念／位置錯")
            elif fc < SCORE_STRONG:
                row["d"].append(f"full-cov {fc:.2f}（拼音級證據，未達逐字）")
            if tf is not None and p["start"] - tf > 0.5:
                row["d"].append(f"LATE {p['start'] - tf:.2f}s")
            if tf is not None and tf - p["start"] > 3.0:
                row["d"].append(f"EARLY {tf - p['start']:.2f}s（疑吞頭）")
            rate = len(norm) / max(0.5, p["end"] - p["start"])
            row["rate"] = round(rate, 2)
            if rate < RATE_MIN:
                row["d"].append(f"fat {rate} 字/s")
            elif rate > RATE_MAX and (p["end"] - p["start"]) > 3.5:
                row["d"].append(f"thin {rate} 字/s")
            # 邊界雙向驗（§4.1 吞尾）：前段末句 needle 應命中在邊界前
            tail = norm[-8:] if len(norm) >= 8 else norm
            qt = st.norm.rfind(tail, q0, q1 + 1)
            row["tail_in"] = None if qt < 0 else round(st.t_of(qt) or -1, 2)
        else:
            # zero 段：逐字掃描全講（SKILL §3 ①「R 不存在」）
            hit = st.norm.find(norm[:8]) if len(norm) >= 8 else -1
            row["verb8_global"] = hit
            if hit >= 0:
                row["d"].append(f"頭 8 字在全講出現 @{round(st.t_of(hit) or -1, 1)}")
        if row["d"]:
            rows.append(row)
        else:
            rows.append(row)

    # 鏈
    reads = [i for i, p in enumerate(ps) if p["end"] > p["start"]]
    chain = []
    for a, b in zip(reads, reads[1:]):
        if ps[a]["end"] != ps[b]["start"]:
            chain.append((a, b, ps[a]["end"], ps[b]["start"]))
    print(f"L{lecture}: {len(ps)} 段 READ {len(reads)}／zero {len(ps) - len(reads)}；"
          f"鏈破口 {len(chain)}；缺陷 {len([r for r in rows if r['d']])}")
    for c in chain:
        print(f"  chain [{c[0]}] end={c[2]} != [{c[1]}] start={c[3]}")
    for r in rows:
        if not r["d"]:
            continue
        print(f"[{r['i']:3d}] {r['cls']:5s} {r['start']:8.2f}-{r['end']:8.2f} "
              f"cov={r.get('full_cov')} off={r.get('off')} | " + " ; ".join(r["d"]))
    if out_json:
        Path(out_json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        print(f"\n→ {out_json}")
    return rows


# --------------------------------------------------------------------------
# heads：逐段「段首第一字」定位證據（交付用的 130 行證據表）
# --------------------------------------------------------------------------

def mode_heads(series, lecture, out_json=None, pad=8.0):
    """對每段列出：段首逐字/拼音證據的最強命中點與其 run-onset，以及現值偏移。

    判讀口徑（SKILL §2 golden）：
      offset = start − run-onset(命中點)
      |offset| ≤ 0.3  精確（run-onset 就是段首）
      offset > +0.3    LATE：start 晚於實際念出的第一字（要修）
      offset < −0.3    EARLY：start 早於內容字（可能是合法 lead-in，也可能是吞頭）
    """
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    norms = [norm_para(p["text"]) for p in ps]
    M = len(st.norm)
    tstart = [st.t_of(q) for q in range(M)]

    def q_at(t, side="last"):
        lo, hi, out = 0, M, 0
        while lo < hi:
            mid = (lo + hi) // 2
            v = tstart[mid]
            if v is None or (side == "last" and v <= t):
                out = mid
                lo = mid + 1
            elif v is None:
                lo = mid + 1
            else:
                hi = mid
        return out

    rows = []
    for i, p in enumerate(ps):
        norm = norms[i]
        cls = cmap.get(p["pid"], "?")
        S = p["start"]
        row = {"i": i, "cls": cls, "start": S, "end": p["end"],
               "conf": p.get("conf"), "zero": bool(p.get("zero")),
               "confirmed": bool(p.get("confirmed")), "n": len(norm)}
        if p["end"] <= p["start"]:
            hit = st.norm.find(norm[:8]) if len(norm) >= 8 else -1
            row["verb8_global"] = None if hit < 0 else round(tstart[hit] or -1, 2)
            rows.append(row)
            continue
        q0, q1 = q_at(S - pad), q_at(S + pad)
        cands = []
        for k in (8, 6):
            if len(norm) < k:
                continue
            q = st.norm.find(norm[:k], q0, q1)
            while q >= 0:
                m = k
                while m < len(norm) and q + m < M and st.norm[q + m] == norm[m]:
                    m += 1
                cands.append((1.0, m, "verb", q))
                q = st.norm.find(norm[:k], q + 1, q1)
        if len(norm) >= 6:
            for sc, q in find_anchor(norm[:min(HEAD_PY, len(norm))], st.norm, q0,
                                    st.py, st.norm2py, scan_norm=max(8, q1 - q0),
                                    max_cands=8):
                cands.append((sc, 0, "py", q))
        best = None
        for sc, m, kind, q in cands:
            cov, qf, _ = score_at(st, norm, q)
            onset = st.run_onset(qf) if qf is not None else None
            cand = {"kind": kind, "m": m, "cov": round(cov, 3),
                    "t": None if onset is None else onset,
                    "off": None if onset is None else round(S - onset, 2),
                    "seed": sc}
            key = (round(cov, 3), m)
            if best is None or key > best[0]:
                best = (key, cand)
        row.update(best[1] if best else {"kind": "none", "cov": 0.0, "off": None})
        rows.append(row)

    print(f"{'i':>4} {'cls':<5} {'start':>8} {'end':>8} {'kind':<5} {'m':>3} "
          f"{'cov':>5} {'onset':>8} {'off':>6}  text")
    for r in rows:
        if r["zero"] or r["end"] <= r["start"]:
            print(f"{r['i']:4d} {r['cls']:<5} {r['start']:8.2f} {r['end']:8.2f} "
                  f"{'zero':<5} {'':>3} {'':>5} {str(r.get('verb8_global')):>8} {'':>6}  "
                  f"v8全局命中 {ps[r['i']]['text'][:24]}")
            continue
        flag = ""
        if r["off"] is not None:
            if r["off"] > 0.3:
                flag = "LATE"
            elif r["off"] < -0.3:
                flag = "early"
        print(f"{r['i']:4d} {r['cls']:<5} {r['start']:8.2f} {r['end']:8.2f} "
              f"{r['kind']:<5} {r.get('m', 0):>3} {r['cov']:5.2f} "
              f"{str(r.get('t')):>8} {str(r.get('off')):>6} {flag:<5} "
              f"{ps[r['i']]['text'][:22]}")
    if out_json:
        Path(out_json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        print(f"\n→ {out_json}")
    return rows


# --------------------------------------------------------------------------
# reanchor：逐段以證據重新錨定「段首第一字」（本檔主模式）
# --------------------------------------------------------------------------

def mode_reanchor(series, lecture, out_json=None, back=2.5, fwd=10.0,
                  accept_cov=0.72, accept_full=0.70):
    """對每個 READ 段重新求 start = run-onset(實際念出的第一字)。

    演算法（逐段獨立、局部窗、證據優先）：
      1. 窗 = [現值 start − back, 現值 end + fwd]（局部，避免全講漂移）
      2. 候選 = 逐字 8/6 needle ＋ 拼音 4-gram 種子候選
      3. 每候選算 head（頭 26 字 DTW 覆蓋率）與 full（頭 90 字 DTW 覆蓋率）
         ＋ 語速自檢（1–12 字/s）
      4. 取「達門檻者中最早」——最早＝首次朗讀，晚的都是後方回音（§4.8a）
      5. start = run_onset(命中第一字)，夾逼 ≥ 上一段 start、≥ 前段末字 end-time

    只在證據達門檻且與現值差 >0.3s 時才提案；其餘維持現值（誠實保守）。
    """
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    dur = lec.get("duration") or 0.0
    norms = [norm_para(p["text"]) for p in ps]
    M = len(st.norm)
    tstart = [st.t_of(q) for q in range(M)]

    def q_at(t):
        lo, hi, out = 0, M, 0
        while lo < hi:
            mid = (lo + hi) // 2
            v = tstart[mid]
            if v is None or v <= t:
                out = mid
                lo = mid + 1
            elif v is None:
                lo = mid + 1
            else:
                hi = mid
        return out

    def all_cands(norm, q0, q1):
        c = {}
        for k in NEEDLES:
            if len(norm) < k:
                continue
            q = st.norm.find(norm[:k], q0, q1)
            while q >= 0:
                c.setdefault(q, "verb")
                q = st.norm.find(norm[:k], q + 1, q1)
        if len(norm) >= 6:
            for _sc, q in find_anchor(norm[:min(HEAD_PY, len(norm))], st.norm, q0,
                                     st.py, st.norm2py,
                                     scan_norm=max(8, q1 - q0), max_cands=8):
                c.setdefault(q, "py")
        return c

    rows = []
    prev_start = 0.0
    prev_char_end = 0.0
    for i, p in enumerate(ps):
        norm = norms[i]
        cls = cmap.get(p["pid"], "?")
        S, E = p["start"], p["end"]
        row = {"i": i, "cls": cls, "cur_start": S, "cur_end": E,
               "conf": p.get("conf"), "zero": bool(p.get("zero")),
               "confirmed": bool(p.get("confirmed")), "n": len(norm),
               "new_start": S, "why": "keep"}
        if E > S and not p.get("confirmed"):
            q0, q1 = q_at(max(0.0, S - back)), q_at(min(dur, E + fwd))
            scored = []
            for q, kind in all_cands(norm, q0, q1).items():
                cov, qf, ql = score_at(st, norm, q)
                if cov < SCORE_WEAK:
                    continue
                fc, _fqf, fql = full_cov(st, norm, q)
                t0, t1 = st.t_of(qf), st.t_end_of(ql)
                if t0 is None or t1 is None or t1 <= t0:
                    continue
                rate = (ql - qf + 1) / (t1 - t0)
                if not (1.0 <= rate <= 12.0):
                    continue
                scored.append({"q": int(q), "kind": kind, "head": round(cov, 3),
                               "full": round(fc, 3), "rate": round(rate, 2),
                               "qf": int(qf), "ql": int(ql), "t0": round(t0, 3)})
            strong = [s for s in scored
                      if s["head"] >= accept_cov and s["full"] >= accept_full]
            if strong:
                top = max(s["full"] for s in strong)
                pick = min((s for s in strong if s["full"] >= top - 0.05),
                           key=lambda s: s["q"])
                onset = st.run_onset(pick["qf"], max_back=ONSET_BACK)
                floor = max(prev_start, prev_char_end - 0.05)
                new_s = max(floor, onset if onset is not None else S)
                row.update({k: pick[k] for k in ("kind", "head", "full", "rate", "t0")})
                if abs(new_s - S) > 0.3:
                    row.update({"new_start": round(new_s, 3), "why": "reanchor",
                                "onset": onset})
            else:
                row["why"] = "no-strong"
                if scored:
                    b = max(scored, key=lambda s: (round(s["head"], 2), s["full"]))
                    row.update({k: b[k] for k in ("kind", "head", "full", "rate", "t0")})
        rows.append(row)
        if E > S:
            prev_char_end = st.t_end_of(q_at(S)) or S
            prev_start = max(prev_start, S)
        else:
            prev_start = max(prev_start, S)

    nch = sum(1 for r in rows if r["why"] == "reanchor")
    nns = sum(1 for r in rows if r["why"] == "no-strong")
    print(f"L{lecture}: {len(ps)} 段；提案改錨 {nch}；無強證據 {nns}（confirmed 段不動）")
    print(f"{'i':>4} {'cls':<5} {'cur':>8} {'new':>8} {'d':>7} {'kind':<5} "
          f"{'head':>5} {'full':>5} {'rate':>5} {'t0':>9}  text")
    for r in rows:
        d = r["new_start"] - r["cur_start"]
        flag = "  <<<" if r["why"] == "reanchor" else (
            "  ~~" if r["why"] == "no-strong" else "")
        print(f"{r['i']:4d} {r['cls']:<5} {r['cur_start']:8.2f} {r['new_start']:8.2f} "
              f"{d:7.2f} {str(r.get('kind','')):<5} {str(r.get('head','')):>5} "
              f"{str(r.get('full','')):>5} {str(r.get('rate','')):>5} "
              f"{str(r.get('t0','')):>9}{flag}  {ps[r['i']]['text'][:20]}")
    if out_json:
        Path(out_json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        print(f"\n→ {out_json}")
    return rows


# --------------------------------------------------------------------------
# evidence：逐段候選證據全表（交付用的「逐一」判讀底稿）
# --------------------------------------------------------------------------

def mode_evidence(series, lecture, out_json=None, back=4.0, fwd=12.0, top=3):
    """每段列出窗內最強的 N 個候選（時間／head 覆蓋率／full 覆蓋率／語速）。

    判讀時看三件事：
      1. 候選 1 的 t0 是否 ≈ 現值 start（差 ≤0.7s → 段首已對齊）
      2. 候選之間是否拉開很遠（>3s → 中間有別段音訊，別選遠的＝回音）
      3. full 覆蓋率低的 SUTRA 段 → 多半是「只念頭」或「沒念」（SKILL §3）
    """
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    dur = lec.get("duration") or 0.0
    norms = [norm_para(p["text"]) for p in ps]
    M = len(st.norm)
    tstart = [st.t_of(q) for q in range(M)]

    def q_at(t):
        lo, hi, out = 0, M, 0
        while lo < hi:
            mid = (lo + hi) // 2
            v = tstart[mid]
            if v is None or v <= t:
                out = mid
                lo = mid + 1
            elif v is None:
                lo = mid + 1
            else:
                hi = mid
        return out

    def cands(norm, q0, q1):
        c = {}
        for k in NEEDLES:
            if len(norm) < k:
                continue
            q = st.norm.find(norm[:k], q0, q1)
            while q >= 0:
                c.setdefault(q, "verb")
                q = st.norm.find(norm[:k], q + 1, q1)
        if len(norm) >= 6:
            for _s, q in find_anchor(norm[:min(HEAD_PY, len(norm))], st.norm, q0,
                                     st.py, st.norm2py,
                                     scan_norm=max(8, q1 - q0), max_cands=8):
                c.setdefault(q, "py")
        return c

    rows = []
    for i, p in enumerate(ps):
        norm = norms[i]
        S, E = p["start"], p["end"]
        row = {"i": i, "cls": cmap.get(p["pid"], "?"), "cur_start": S, "cur_end": E,
               "conf": p.get("conf"), "zero": bool(p.get("zero")),
               "confirmed": bool(p.get("confirmed")), "n": len(norm), "cands": []}
        if E > S:
            q0, q1 = q_at(max(0.0, S - back)), q_at(min(dur, E + fwd))
            scored = []
            for q, kind in cands(norm, q0, q1).items():
                cov, qf, ql = score_at(st, norm, q)
                if cov < 0.5:
                    continue
                fc, _a, _b = full_cov(st, norm, q)
                t0, t1 = st.t_of(qf), st.t_end_of(ql)
                if t0 is None or t1 is None or t1 <= t0:
                    continue
                rate = (ql - qf + 1) / (t1 - t0)
                scored.append({"kind": kind, "head": round(cov, 3),
                               "full": round(fc, 3), "rate": round(rate, 2),
                               "t0": round(t0, 3),
                               "onset": st.run_onset(qf),
                               "d": round(S - (st.run_onset(qf) or t0), 2)})
            scored.sort(key=lambda s: (-s["head"], -s["full"]))
            row["cands"] = scored[:top]
        else:
            hits = []
            for k in (8, 6):
                if len(norm) >= k:
                    q = st.norm.find(norm[:k])
                    while q >= 0:
                        hits.append((k, round(tstart[q] or -1, 2)))
                        q = st.norm.find(norm[:k], q + 1)
                        if len(hits) > 6:
                            break
            row["verb_hits"] = hits[:6]
        rows.append(row)

    for r in rows:
        head = (f"[{r['i']:3d}] {r['cls']:<5} {r['cur_start']:8.2f}-{r['cur_end']:8.2f}"
                f" n={r['n']:<4}")
        if not r["cands"] and not r.get("verb_hits"):
            print(head + "  （窗內無候選）")
            continue
        if r["cands"]:
            s = "  ".join(
                f"t0={c['t0']:8.2f} d={c['d']:+6.2f} h={c['head']:.2f} "
                f"f={c['full']:.2f} r={c['rate']:4.1f} {c['kind']}"
                for c in r["cands"])
            print(head + "  " + s)
        else:
            print(head + f"  zero；逐字全局命中 {r['verb_hits']}")
    if out_json:
        Path(out_json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        print(f"\n→ {out_json}")
    return rows


def tolerant_scan(st, norm, q0, q1, gap=3, sim_min=0.8, max_pat=64, rate_gate=True):
    """容錯跳字掃描：找出窗內「最長連續念出段頭」的位置（§3 量 R 的同一手法）。

    DTW 對同音錯字＋掉字的段落頭太敏感（分數被攤薄），這裡改成：逐字比對、
    每字容忍在窗內跳 ≤gap 個 ASR 字，命中 ≥6 字才算證據，另做語速自檢（1–12 字/s）。
    回傳候選（依 matched 遞減）：{matched, q_first, q_last, cov, rate, t0, onset}。
    """
    pat = norm[:max_pat]
    if not pat or q1 <= q0:
        return []
    out = []
    n = len(pat)
    for j in range(q0, q1):
        if sim_char(pat[0], st.norm[j]) < sim_min:
            continue
        i, k, matched, last = 0, j, 0, -1
        while i < n and k < q1:
            nk = None
            for kk in range(k, min(q1, k + gap + 1)):
                if sim_char(pat[i], st.norm[kk]) >= sim_min:
                    nk = kk
                    break
            if nk is None:
                break
            matched += 1
            last = nk
            i += 1
            k = nk + 1
        if matched < 6 or last < 0:
            continue
        t0, t1 = st.t_of(j), st.t_end_of(last)
        if t0 is None or t1 is None or t1 <= t0:
            continue
        rate = matched / (t1 - t0)
        if rate_gate and not (1.0 <= rate <= 12.0):
            continue
        out.append({"matched": matched, "q_first": int(j), "q_last": int(last),
                    "cov": round(matched / n, 3), "rate": round(rate, 2),
                    "t0": round(t0, 3), "onset": st.run_onset(j)})
    out.sort(key=lambda s: (-s["matched"], s["q_first"]))
    return out


def mode_tol(series, lecture, out_json=None, back=4.0, fwd=12.0, top=2):
    """分塊 DTW 證據表：每段列出窗內最強的 N 個「段頭命中」與其偏移 d。

    d = 現值 start − 命中點 run-onset
      |d| ≤ 0.5  段首已對齊
      d > +0.5   start 晚於實際念出的第一字 → 候選修正
      d < −1.5   段首前有引導語／ASR 頭部錯讀 → 人工判讀（看 ASR 視窗）
    """
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    dur = lec.get("duration") or 0.0
    norms = [norm_para(p["text"]) for p in ps]
    M = len(st.norm)
    tstart = [st.t_of(q) for q in range(M)]

    def q_at(t):
        lo, hi, out = 0, M, 0
        while lo < hi:
            mid = (lo + hi) // 2
            v = tstart[mid]
            if v is None or v <= t:
                out = mid
                lo = mid + 1
            elif v is None:
                lo = mid + 1
            else:
                hi = mid
        return out

    rows = []
    for i, p in enumerate(ps):
        norm = norms[i]
        S, E = p["start"], p["end"]
        row = {"i": i, "cls": cmap.get(p["pid"], "?"), "cur_start": S, "cur_end": E,
               "conf": p.get("conf"), "zero": bool(p.get("zero")),
               "confirmed": bool(p.get("confirmed")), "n": len(norm), "hits": []}
        is_zero = E <= S
        q0, q1 = (0, M) if is_zero else (
            q_at(max(0.0, S - back)), q_at(min(dur, E + fwd)))
        hits = chunked_head_scan(st, norm, q0, q1)
        for h in hits:
            fc, _a, _b = full_cov(st, norm, h["q"])
            h["full"] = round(fc, 3)
            h["d"] = round(S - (h["onset"] if h["onset"] is not None else h["t0"]), 2)
        keep = hits[:(top if not is_zero else 3)]
        row["hits"] = keep
        rows.append(row)

    for r in rows:
        tag = "zero" if r["cur_end"] <= r["cur_start"] else "READ "
        s = "  ".join(
            f"t0={h['t0']:8.2f} d={h['d']:+6.2f} s={h['score']:.2f} "
            f"f={h['full']:.2f} r={h['rate']:4.1f}" for h in r["hits"])
        print(f"[{r['i']:3d}] {r['cls']:<5} {tag} {r['cur_start']:8.2f}-"
              f"{r['cur_end']:8.2f} n={r['n']:<4} {s or '（無命中）'}")
    if out_json:
        Path(out_json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        print(f"\n→ {out_json}")
    return rows


def chunked_head_scan(st, norm, q0, q1, cap=CAP, chunk=32, overlap=16, min_score=0.45):
    """分塊滑動 DTW：窗內切塊各跑一次「段落頭 vs 該塊」的 DTW，取所有局部峰。

    為什麼不用單次全窗 DTW：全窗只回一個最佳路徑，遇到同音錯字段頭時，那個
    最佳常常落在後方的回音上（§4.8a 的 false positive `early`）。分塊後每塊各
    給一個局部最佳（`dtw_span` 的 row-0 可自由 skip-in，所以塊內任何位置都能
    當段頭），再按「分數高 → 位置早」排序，就能同時看見真正念誦處與後方回音。
    """
    out = []
    if q1 <= q0:
        return out
    pat = list(norm[:min(cap, len(norm))])
    if not pat:
        return out
    step = max(1, chunk - overlap)
    j = q0
    while j < q1:
        b = min(q1, j + chunk)
        sc, jf, jl = dtw_span(pat, list(st.norm[j:b]), jf_min=0)
        if jf >= 0 and sc / len(pat) >= min_score:
            qf, ql = j + jf, j + jl
            t0, t1 = st.t_of(qf), st.t_end_of(ql)
            if t0 is not None:
                rate = ((ql - qf + 1) / (t1 - t0)) if (t1 and t1 > t0) else 0.0
                out.append({"q": int(qf), "ql": int(ql), "score": round(sc / len(pat), 3),
                            "rate": round(rate, 2), "t0": round(t0, 3),
                            "onset": st.run_onset(qf)})
        j += step
    out.sort(key=lambda s: (-s["score"], s["q"]))
    ded = []
    for s in out:
        if all(abs(s["q"] - d["q"]) > 8 for d in ded):
            ded.append(s)
    return ded


def mode_propose(series, lecture, out_table=None, back=4.0, fwd=12.0,
                 min_score=0.62, delta=0.3):
    """產出逐段 start 提案（adjudication table 草稿）。

    選點規則（§4.8a「最早＝首次朗讀」）：
      窗內分塊 DTW 的所有候選中，取 **分數 ≥min_score 者裡位置最早的一個**
      作為「本段第一個被念出的字」。比它更晚的高分命中＝後方回音或重引，
      一律不採用。start = run_onset(該字)，並夾逼 ≥ 前段 start、≥ 前段末字
      end-time（不剪掉前段尾音）。

    輸出每筆 {i, start, conf, why, d, score}；|d| ≤delta 的不提案（維持現值）。
    """
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    dur = lec.get("duration") or 0.0
    norms = [norm_para(p["text"]) for p in ps]
    M = len(st.norm)
    tstart = [st.t_of(q) for q in range(M)]

    def q_at(t):
        lo, hi, out = 0, M, 0
        while lo < hi:
            mid = (lo + hi) // 2
            v = tstart[mid]
            if v is None or v <= t:
                out = mid
                lo = mid + 1
            elif v is None:
                lo = mid + 1
            else:
                hi = mid
        return out

    table, prev_start, prev_end_t = [], 0.0, 0.0
    print(f"{'i':>4} {'cls':<5} {'cur':>8} {'prop':>8} {'d':>7} {'sc':>5} {'n_alt':>5}  note")
    for i, p in enumerate(ps):
        norm = norms[i]
        S, E = p["start"], p["end"]
        cls = cmap.get(p["pid"], "?")
        if E <= S or p.get("confirmed"):
            table.append({"i": i, "why": "zero/confirmed"})
            prev_start = max(prev_start, S)
            continue
        q0, q1 = q_at(max(0.0, S - back)), q_at(min(dur, E + fwd))
        hits = chunked_head_scan(st, norm, q0, q1)
        ok = [h for h in hits if h["score"] >= min_score and 1.0 <= h["rate"] <= 12.0]
        ok.sort(key=lambda h: h["q"])
        note = ""
        if not ok:
            note = "no-candidate"
            table.append({"i": i, "why": "no-candidate"})
        else:
            pick = ok[0]
            onset = pick["onset"] if pick["onset"] is not None else pick["t0"]
            floor = max(prev_start, prev_end_t - 0.05)
            new_s = round(max(floor, onset), 3)
            note = (f"sc={pick['score']} alt={len(ok)} "
                    f"next={ok[1]['t0'] if len(ok) > 1 else '-'}")
            if abs(new_s - S) > delta:
                table.append({"i": i, "start": new_s, "why": "propose",
                              "d": round(new_s - S, 2), "score": pick["score"],
                              "note": note})
            else:
                table.append({"i": i, "why": "keep", "d": round(new_s - S, 2),
                              "score": pick["score"], "note": note})
            prev_start = max(prev_start, new_s)
            prev_end_t = st.t_end_of(pick["ql"]) or pick["t0"]
        print(f"{i:4d} {cls:<5} {S:8.2f} "
              f"{(table[-1].get('start', S)):8.2f} "
              f"{table[-1].get('d', 0.0):7.2f} {table[-1].get('score', 0.0):5.2f} "
              f"{'':>5}  {table[-1]['why']} {note}")
    if out_table:
        Path(out_table).write_text(
            json.dumps([t for t in table if t["why"] == "propose"],
                       ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n提案 {len([t for t in table if t['why'] == 'propose'])} 筆 → {out_table}")
    return table


def mode_bopt(series, lecture, out_table=None, span=6.0, step=0.10,
              head_n=24, tail_n=24, win=9.0):
    """雙向邊界最佳化：逐段求「前段尾 ＋ 本段頭」共同最貼合的邊界。

    為什麼要雙向（§4.1 吞尾）：單看段頭，DTW 很容易被後方回音或半念段拖走；
    要求**同一個邊界**同時讓前段末句與本段段頭都對得上，邊界就不會偏。

    對每個相鄰 READ 段邊界 B ∈ [B₀−span, B₀+span]：
        tail(B) = DTW(前段末 tail_n 字, 音訊 [B−win, B]) 的覆蓋率
        head(B) = DTW(本段頭 head_n 字, 音訊 [B, B+win]) 的覆蓋率
      取 argmax(tail+head)，再把本段 start 收成
        start = run_onset(head 首個命中字)，夾逼 ≥ 前段 start、≥ 前段末字 end-time。

    confirmed 段是鐵錨，其邊界不動；zero 段透明（在鏈上，不單獨最佳化）。
    """
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    norms = [norm_para(p["text"]) for p in ps]
    M = len(st.norm)
    tstart = [st.t_of(q) for q in range(M)]

    def q_at(t):
        lo, hi, out = 0, M, 0
        while lo < hi:
            mid = (lo + hi) // 2
            v = tstart[mid]
            if v is None or v <= t:
                out = mid
                lo = mid + 1
            elif v is None:
                lo = mid + 1
            else:
                hi = mid
        return out

    wchars = max(12, int(win / 0.25))

    def cov_at(pat, qa, qb):
        if not pat or qb <= qa:
            return 0.0, None
        sc, jf, _jl = dtw_span(list(pat), list(st.norm[qa:qb]), jf_min=0)
        if jf < 0:
            return 0.0, None
        return sc / len(pat), qa + jf

    reads = [i for i, p in enumerate(ps)
             if p["end"] > p["start"] and not p.get("confirmed")]
    table = []
    prev_start = 0.0
    prev_last_end = 0.0
    print(f"{'i':>4} {'cls':<5} {'cur':>8} {'prop':>8} {'d':>7} "
          f"{'tail':>5} {'head':>5} {'sum':>5} {'B*':>8}  note")
    for k, i in enumerate(reads):
        cur = ps[i]["start"]
        if k == 0 or ps[reads[k - 1]].get("confirmed"):
            table.append({"i": i, "why": "first-read" if k == 0 else "prev-confirmed"})
            prev_start = max(prev_start, cur)
            prev_last_end = st.t_end_of(q_at(cur)) or cur
            print(f"{i:4d} {cmap.get(ps[i]['pid'],'?'):<5} {cur:8.2f} {cur:8.2f}"
                  f" {'':>7} {'':>5} {'':>5} {'':>5} {'':>8}  {table[-1]['why']}")
            continue
        j = reads[k - 1]
        B0 = ps[j]["end"]
        tail_pat = norms[j][-tail_n:] if len(norms[j]) > 6 else norms[j]
        head_pat = norms[i][:head_n]
        best = None
        steps = int(2 * span / step) + 1
        for sgi in range(steps):
            b = round(B0 - span + sgi * step, 2)
            qb = q_at(b)
            tc, _ = cov_at(tail_pat, max(0, qb - wchars), qb)
            hc, hf = cov_at(head_pat, qb, min(M, qb + wchars))
            tot = tc + hc
            if best is None or tot > best[0]:
                best = (tot, b, tc, hc, hf)
            if abs(b - B0) < step / 2:
                tot0, tc0, hc0 = tot, tc, hc
        tot, B, tc, hc, hf = best
        # 信賴門檻：必須**同時**比現值好、且前後兩側都有實據，否則不動
        # （低分時 DTW 只是在空窗裡找相對最好，會把邊界拉飛）
        trust = (tot >= tot0 + 0.04 and hc >= 0.60 and tc >= 0.55)
        onset = st.run_onset(hf) if hf is not None else None
        floor = max(prev_start, prev_last_end - 0.05)
        new_s = round(max(floor, onset if onset is not None else cur), 3)
        if not trust:
            new_s = cur
        row = {"i": i, "why": "propose" if (trust and abs(new_s - cur) > 0.3) else "keep",
               "d": round(new_s - cur, 2), "B": B, "tail": tc, "head": hc,
               "sum": round(tot, 3), "sum0": round(tot0, 3),
               "B0": round(B0, 2), "tc0": round(tc0, 3), "hc0": round(hc0, 3),
               "trust": trust}
        if row["why"] == "propose":
            row["start"] = new_s
        table.append(row)
        print(f"{i:4d} {cmap.get(ps[i]['pid'],'?'):<5} {cur:8.2f} {new_s:8.2f} "
              f"{row['d']:7.2f} {tc:5.2f} {hc:5.2f} {tot:5.2f} {B:8.2f}  {row['why']}")
        prev_start = max(prev_start, new_s)
        prev_last_end = st.t_end_of(q_at(new_s + 1.0)) or new_s

    nprop = len([t for t in table if t["why"] == "propose"])
    print(f"\n提案 {nprop} / {len(reads)} 段")
    if out_table:
        Path(out_table).write_text(
            json.dumps([t for t in table if t.get("start") is not None],
                       ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"→ {out_table}")
    return table


def mode_metric(series, lecture, out_json=None):
    """客觀量測：start −「本段第一個被念出的字」時間（毫秒級驗收口徑）。

    這是**唯一能量化「首字有沒有對到」**的指標；span_audit / milli_audit 量的
    是「整段有沒有對到」，會給出一樣的 ok-rate 卻漏掉邊界偏差（§4.1 吞尾）。

    兩個量測陷阱（都已修正，別改回去）：
      1. `dtw_span` 的 j_first 可能落在**被 DEL 掉的 pattern 字**上（段頭同音
         錯字時極常見）→ 必須再驗 `sim_char(段首字, 該位置 ASR 字) ≥ 0.8`，
         否則量到的是 DTW 開始嘗試的位置，不是首字被念出的位置。
      2. 短前綴會對**重引／回音**產生假命中（[49] 實測：前一段經文的
         「外道所說的常不思議」比本段的重引更早、更像）→ 用 20 字前綴，
         且要求路徑實際吃掉 ≥10 個 ASR 字。

    取窗 [start−3, start+7] 內**最早**的達標命中（首次朗讀；§4.8a）。
    """
    lec, st, cmap = load(series, lecture)
    ts = [st.t_of(q) for q in range(len(st.norm))]

    def q_at(t):
        lo, hi, out = 0, len(ts), 0
        while lo < hi:
            mid = (lo + hi) // 2
            v = ts[mid]
            if v is None or v <= t:
                out = mid
                lo = mid + 1
            elif v is None:
                lo = mid + 1
            else:
                hi = mid
        return out

    rows = []
    for i, p in enumerate(lec["paragraphs"]):
        S, E = p["start"], p["end"]
        if E <= S:
            continue
        norm = norm_para(p["text"])
        k = 20
        if len(norm) < k:
            continue
        qa, qb = q_at(S - 3.0), q_at(S + 7.0)
        best = None
        q = qa
        while q < qb:
            sc, jf, jl = dtw_span(list(norm[:k]),
                                   list(st.norm[q:min(len(st.norm), q + k + 8)]),
                                   jf_min=0)
            if (jf >= 0 and sc / k >= 0.75 and (jl - jf + 1) >= 10
                    and sim_char(norm[0], st.norm[q + jf]) >= 0.8):
                t = st.t_of(q + jf)
                if t is not None and (best is None or t < best[0]):
                    best = (t, round(sc / k, 3))
            q += 3
        if best and S - 6 <= best[0] <= S + 7:
            rows.append({"i": i, "start": S, "t_first": round(best[0], 3),
                         "d": round(S - best[0], 2), "cov": best[1]})
    ds = sorted(r["d"] for r in rows)
    if not ds:
        print("無強證據段")
        return rows
    n = len(ds)
    for thr in (0.3, 0.5, 0.7):
        late = sum(1 for x in ds if x > thr)
        early = sum(1 for x in ds if x < -thr)
        print(f"  |d|>{thr:.1f}s：晚 {late:3d} ({100 * late / n:2.0f}%)  "
              f"早 {early:3d} ({100 * early / n:2.0f}%)  "
              f"±{thr:.1f}s 內 {n - late - early:3d} ({100 * (n - late - early) / n:2.0f}%)")
    print(f"  n={n}（有強首字證據的 READ 段）median {ds[n // 2]:+.2f}s  "
          f"mean {sum(ds) / n:+.2f}s  min {ds[0]:+.2f}  max {ds[-1]:+.2f}")
    if out_json:
        Path(out_json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        print(f"→ {out_json}")
    return rows


def mode_final(series, lecture, out_table=None, span=6.0, step=0.10,
               head_n=24, tail_n=24, win=9.0, pre=2.0, post=4.0):
    """最終提案：bopt 決定邊界區域 → 短前綴滑動 DTW 精確定位首字 → start。

    兩段式（為什麼要分兩段）：
      bopt 的 B* 是「最佳切點」，精度約 ±0.5s；直接當 start 會在兩個方向都
      出錯（晚 0.5s 就吃掉首字）。所以再用 12–16 字的**短前綴**在 [B*−pre,
      B*+post] 內滑動比對——短前綴對 ASR 同音錯字不敏感，能把「第一個被念出
      的字」釘到 ±0.2s，再取 run_onset（往回 ≤0.7s 的停頓）。

    輸出完整 130 段表（含 zero/confirmed 的現值），供逐段判讀與寫入。
    """
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    norms = [norm_para(p["text"]) for p in ps]
    M = len(st.norm)
    tstart = [st.t_of(q) for q in range(M)]

    def q_at(t):
        lo, hi, out = 0, M, 0
        while lo < hi:
            mid = (lo + hi) // 2
            v = tstart[mid]
            if v is None or v <= t:
                out = mid
                lo = mid + 1
            elif v is None:
                lo = mid + 1
            else:
                hi = mid
        return out

    wchars = max(12, int(win / 0.25))

    def cov_at(pat, qa, qb):
        if not pat or qb <= qa:
            return 0.0, None
        sc, jf, _jl = dtw_span(list(pat), list(st.norm[qa:qb]), jf_min=0)
        if jf < 0:
            return 0.0, None
        return sc / len(pat), qa + jf

    def first_char(norm, B):
        """在 [B−pre, B+post] 內用 12/14/16 字前綴滑動比對，回最早高分命中。"""
        qa, qb = q_at(max(0.0, B - pre)), q_at(B + post)
        cands = []
        for k in (12, 14, 16):
            if len(norm) < k:
                continue
            step_c = 4
            q = qa
            while q < qb:
                sc, jf, _jl = dtw_span(list(norm[:k]), list(st.norm[q:min(M, q + k + 6)]),
                                       jf_min=0)
                if jf >= 0 and sc / k >= 0.62:
                    cands.append((q + jf, round(sc / k, 3), k))
                q += step_c
        if not cands:
            return None
        cands.sort(key=lambda c: (c[0], -c[1]))
        return cands[0]

    reads = [i for i, p in enumerate(ps)
             if p["end"] > p["start"] and not p.get("confirmed")]
    table, prev_start, prev_end_t = [], 0.0, 0.0
    for k, i in enumerate(reads):
        cur = ps[i]["start"]
        if k == 0 or ps[reads[k - 1]].get("confirmed"):
            table.append({"i": i, "why": "anchor", "cur": cur, "start": cur,
                          "B": cur, "sum": None})
            prev_start = max(prev_start, cur)
            prev_end_t = st.t_end_of(q_at(cur)) or cur
            continue
        j = reads[k - 1]
        B0 = ps[j]["end"]
        tail_pat = norms[j][-tail_n:] if len(norms[j]) > 6 else norms[j]
        head_pat = norms[i][:head_n]
        best, tot0 = None, None
        for sgi in range(int(2 * span / step) + 1):
            b = round(B0 - span + sgi * step, 2)
            qb = q_at(b)
            tc, _ = cov_at(tail_pat, max(0, qb - wchars), qb)
            hc, hf = cov_at(head_pat, qb, min(M, qb + wchars))
            tot = tc + hc
            if best is None or tot > best[0]:
                best = (tot, b, tc, hc, hf)
            if abs(b - B0) < step / 2:
                tot0 = tot
        tot, B, tc, hc, hf = best
        # 信賴門檻：必須**同時**比現值好、且前後兩側都有實據，否則整段不動
        # （低分時 DTW 只是在空窗裡找相對最好，會把邊界拉飛；實測 [24] 若不設
        #  門檻會被一段假命中拖到 328.04，吞掉前一段「那為什麼不一樣呢」）
        trust = (tot >= tot0 + 0.04 and hc >= 0.60 and tc >= 0.55)
        if not trust:
            table.append({"i": i, "why": "keep", "cur": cur, "start": cur,
                          "B": B0, "tail": tc, "head": hc, "sum": round(tot, 3),
                          "sum0": round(tot0, 3), "trust": False, "fc": None})
            prev_start = max(prev_start, cur)
            prev_end_t = st.t_end_of(q_at(cur)) or cur
            continue
        anchor = B
        fc = first_char(norms[i], anchor)
        tfc = st.t_of(fc[0]) if fc else None
        # 首字必須落在邊界附近（[B−pre, B+post]）且分數夠，否則退回切點 −0.3s
        if tfc is not None and fc[1] >= 0.70 and anchor - pre <= tfc <= anchor + post:
            onset = st.run_onset(fc[0])
        else:
            onset = max(0.0, anchor - 0.3)
        floor = max(prev_start, prev_end_t - 0.05)
        new_s = round(max(floor, onset), 3)
        table.append({"i": i, "why": "propose" if abs(new_s - cur) > 0.3 else "keep",
                      "cur": cur, "start": new_s, "d": round(new_s - cur, 2),
                      "B": anchor, "tail": tc, "head": hc, "sum": round(tot, 3),
                      "trust": trust, "fc": None if not fc else
                      {"q": fc[0], "score": fc[1], "k": fc[2],
                       "t": st.t_of(fc[0])}})
        prev_start = max(prev_start, new_s)
        tfc = (st.t_of(fc[0]) if fc else None)
        prev_end_t = (st.t_end_of(q_at(tfc + 2.0)) or tfc or anchor) if tfc else anchor

    for row in table:
        t = row.get("fc") or {}
        print(f"{row['i']:4d} {cmap.get(ps[row['i']]['pid'],'?'):<5} "
              f"{row['cur']:8.2f} → {row['start']:8.2f} "
              f"({row.get('d', 0):+6.2f})  B={row['B']:8.2f} "
              f"tail={row.get('tail', 0):.2f} head={row.get('head', 0):.2f} "
              f"fc_t={t.get('t')} fc_s={t.get('score')} {row['why']}")
    if out_table:
        Path(out_table).write_text(json.dumps(table, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print(f"\n→ {out_table}")
    return table


# --------------------------------------------------------------------------
# window：單段判讀視窗（含段落全文 ＋ 首候選）
# --------------------------------------------------------------------------

def mode_window(series, lecture, i, pad, width):
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    p = ps[i]
    norm = norm_para(p["text"])
    print(f"=== [{i}] {cmap.get(p['pid'],'?')} {p['start']:.2f}-{p['end']:.2f} "
          f"conf={p.get('conf')} zero={p.get('zero')} confirmed={p.get('confirmed')}")
    print(f"全文 norm({len(norm)}): {norm}")
    print(f"前 30: {norm[:30]}")
    lo, hi = max(0.0, p["start"] - pad), p["end"] + pad
    buf = [(st.t_of(q), st.norm[q]) for q in range(len(st.norm))
           if (st.t_of(q) is not None and lo <= st.t_of(q) <= hi)]
    for k in range(0, len(buf), width):
        ch = buf[k:k + width]
        print(f"[{ch[0][0]:8.2f}] {''.join(c for _, c in ch)}")


def mode_view(series, lecture, i_from, i_to, before=3.0, after=7.0, width=18):
    """逐段「邊界目視」：印前段尾／本段頭＋邊界前後的 ASR 字級流。"""
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    for i in range(i_from, min(i_to + 1, len(ps))):
        p = ps[i]
        norm = norm_para(p["text"])
        prev = norm_para(ps[i - 1]["text"]) if i else ""
        cls = cmap.get(p["pid"], "?")
        print(f"\n[{i:3d}] {cls:5s} {p['start']:8.2f}-{p['end']:8.2f} "
              f"conf={p.get('conf')} zero={int(bool(p.get('zero')))} "
              f"confirmed={int(bool(p.get('confirmed')))}")
        if prev:
            print(f"   前段尾: …{prev[-20:]}")
        print(f"   本段頭: {norm[:26]}…")
        lo, hi = max(0.0, p["start"] - before), p["end"] + after
        buf = [(st.t_of(q), st.norm[q]) for q in range(len(st.norm))
               if (st.t_of(q) is not None and lo <= st.t_of(q) <= hi)]
        for k in range(0, len(buf), width):
            ch = buf[k:k + width]
            mark = " »" if abs(ch[0][0] - p["start"]) < width else ""
            print(f"   [{ch[0][0]:8.2f}] {''.join(c for _, c in ch)}{mark}")


def mode_batch(series, lecture, idx_list, before=2.5, after=4.0, width=17,
               table=None):
    """批次邊界目視：一次印多個段落的邊界前後 ASR（判讀提案用）。

    每段輸出：段落標頭（含提案值）、前段尾、本段頭、以及邊界前後的 ASR 字流
    （用 │ 標出現行 start 的位置，方便對照）。
    """
    lec, st, cmap = load(series, lecture)
    ps = lec["paragraphs"]
    prop = {}
    if table:
        for t in json.loads(Path(table).read_text(encoding="utf-8")):
            prop[t["i"]] = t.get("start")
    for i in idx_list:
        p = ps[i]
        norm = norm_para(p["text"])
        prev = norm_para(ps[i - 1]["text"]) if i else ""
        cls = cmap.get(p["pid"], "?")
        tag = ""
        if i in prop and prop[i] is not None and abs(prop[i] - p["start"]) > 0.05:
            tag = f"  →提案 {prop[i]:.2f} ({prop[i] - p['start']:+.2f})"
        print(f"\n[{i:3d}] {cls:5s} {p['start']:8.2f}-{p['end']:8.2f}{tag}")
        if prev:
            print(f"   前段尾: …{prev[-18:]}")
        print(f"   本段頭: {norm[:24]}…")
        lo, hi = max(0.0, p["start"] - before), p["start"] + after
        buf = [(st.t_of(q), st.norm[q]) for q in range(len(st.norm))
               if (st.t_of(q) is not None and lo <= st.t_of(q) <= hi)]
        for k in range(0, len(buf), width):
            ch = buf[k:k + width]
            t0 = ch[0][0]
            flag = "«" if p["start"] <= t0 <= hi else ""
            pv = prop.get(i)
            flag += "*" if pv is not None and pv <= t0 <= hi else ""
            print(f"   [{t0:8.2f}]{flag} {''.join(c for _, c in ch)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--series", required=True)
    ap.add_argument("--lecture", required=True)
    ap.add_argument("--mode", choices=("rough", "verify", "heads", "reanchor",
                                       "evidence", "tol", "propose", "bopt", "final", "metric", "batch",
                                       "window", "view"),
                    default="verify")
    ap.add_argument("--i", type=int, default=0, help="window 模式的段落索引")
    ap.add_argument("--from", dest="i_from", type=int, default=0)
    ap.add_argument("--to", dest="i_to", type=int, default=0)
    ap.add_argument("--pad", type=float, default=8.0)
    ap.add_argument("--after", type=float, default=8.0)
    ap.add_argument("--width", type=int, default=16)
    ap.add_argument("--json")
    ap.add_argument("--list", default="", help="batch 模式的段落索引（逗號分隔）")
    ap.add_argument("--table", help="batch 模式讀入的提案 JSON")
    a = ap.parse_args()
    if a.mode == "rough":
        mode_rough(a.series, a.lecture, a.json)
    elif a.mode == "verify":
        mode_verify(a.series, a.lecture, a.json)
    elif a.mode == "heads":
        mode_heads(a.series, a.lecture, a.json, a.pad)
    elif a.mode == "reanchor":
        mode_reanchor(a.series, a.lecture, a.json)
    elif a.mode == "evidence":
        mode_evidence(a.series, a.lecture, a.json)
    elif a.mode == "tol":
        mode_tol(a.series, a.lecture, a.json)
    elif a.mode == "propose":
        mode_propose(a.series, a.lecture, a.json)
    elif a.mode == "bopt":
        mode_bopt(a.series, a.lecture, a.json)
    elif a.mode == "final":
        mode_final(a.series, a.lecture, a.json)
    elif a.mode == "metric":
        mode_metric(a.series, a.lecture, a.json)
    elif a.mode == "view":
        mode_view(a.series, a.lecture, a.i_from, a.i_to, a.pad, a.width)
    elif a.mode == "batch":
        idx = [int(x) for x in a.list.split(",") if x.strip()]
        mode_batch(a.series, a.lecture, idx, before=a.pad, after=a.after, width=int(a.width), table=a.table)
    else:
        mode_window(a.series, a.lecture, a.i, a.pad, a.width)


if __name__ == "__main__":
    main()