#!/usr/bin/env python3
"""楞伽經段落 ↔ 音檔精準對齊器（舊 engine 路線；現行程序見 milli-align skill）。

架構：engine（tool/jiangjing_para_map/realign_dtw.align_lecture，FunASR
字級 DTW）＋ 結構修正層（本檔 skill_correct）。

結構修正規則（由 audio_map3/lengqie.json L1-3 人工 golden 提煉）：
  R1 首 SUTRA run＝印刷參考塊：全文覆蓋 < FULL_T → ZERO（即使頭部命中，
     那多半是後方短引文的 vocalization）。
  R2 subsumed-dup：長塊頭部 ⊇ 後方短引文全文 → 長塊 ZERO，vocalization 歸短引文。
  R3 被吞掉的導言：首 run 後緊鄰 COMM 若被壓成零寬 → 從講首重錨。
  R4 误判 skip 救援：零寬短引文若在局部間隙有強逐字/拼音證據 → READ。
  R5 鏈：end[i]=start[i+1]（尊重 engine end_fixed）；zero 重壓零寬。
  R6 confirmed/reviewed/L1-3 永不觸碰（apply 前後 byte-level 校驗）。

用法（統一用 sense_voice venv，有 numpy/pypinyin/opencc）：
  align_lengqie.py --tune                        # L1-3 與人工 golden 比對（唯讀）
  align_lengqie.py --dry-run [--lecture N]       # 跑 L4-42（或單講），只印報表
  align_lengqie.py --apply [--lecture N]         # 寫回 audio_map3/lengqie.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
from realign_dtw import (  # noqa: E402
    dtw_span,
    find_anchor,
    load_dump,
    norm_para,
    py_string,
)
from realign_dtw import align_lecture as engine_align  # noqa: E402

DUMP_DIR = Path("/tmp/funasr_cache/lengqie")
JSON_PATH = ROOT / "audio_map3" / "lengqie.json"
EBOOK_PATH = ROOT / "ebook" / "08.html"

HEAD_N = 14
LEAD_BACK = 0.15
FULL_T = 0.60
SHORT_Q = 60
LONG_B = 100
GOLDEN = ("1", "2", "3")
TARGETS = [str(i) for i in range(4, 43)]


# --------------------------------------------------------------------------
# ebook cls
# --------------------------------------------------------------------------

def load_ebook_cls():
    html = EBOOK_PATH.read_text(encoding="utf-8")
    marks = list(re.finditer(r'<h2 id="[^"]*">(.*?)</h2>', html, re.S))
    out = {}
    for i, m in enumerate(marks):
        am = re.search(r'data-audio="([^"]+)"', m.group(1))
        if not am:
            continue
        base = urllib.parse.unquote(am.group(1)).rsplit("/", 1)[-1]
        base = re.sub(r"\.opus$", "", base)
        mn = re.search(r"楞伽经\((\d+)\)", base)
        if not mn:
            continue
        body = html[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(html)]
        cls = []
        for b in re.finditer(r"<(p|div)\b([^>]*)>(.*?)</\1>", body, re.S):
            cm = re.search(r'class="([^"]*)"', b.group(2))
            pm = re.search(r'id="(p-s[0-9a-f]+)"', b.group(2))
            if not pm or not cm or "para-block" not in cm.group(1).split():
                continue
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", b.group(3))).strip()
            if txt:
                cls.append({"pid": pm.group(1),
                            "cls": ("SUTRA" if "sutra-text" in cm.group(1) else "COMM")})
        out[mn.group(1)] = cls
    return out


# --------------------------------------------------------------------------
# stream helpers
# --------------------------------------------------------------------------

def build_stream(dump):
    chars = dump["chars"]
    times = dump["times"]
    stream = "".join(chars)
    py_stream = py_string(stream)
    lens = [len(py) for py in (py_string(c) for c in stream)]
    norm2py = np.concatenate(([0], np.cumsum(lens))).astype(np.int64)
    tstarts = np.array([t[0] if (t[0] is not None and t[0] == t[0]) else np.nan
                        for t in times], dtype=float)
    return chars, times, stream, py_stream, norm2py, tstarts


def t_of(times, q):
    if 0 <= q < len(times):
        t = times[q][0]
        if t is not None and t == t:
            return float(t)
    return None


def greedy_coverage(pat, stream, lo, hi):
    hi = min(hi, len(stream))
    pos, found, first = lo, 0, -1
    for ch in pat:
        q = stream.find(ch, pos, hi)
        if q < 0:
            continue
        if first < 0:
            first = q
        found += 1
        pos = q + 1
    return found / max(1, len(pat)), first


def chars_in_range(tstarts, lo_t, hi_t, pad=150):
    M = len(tstarts)
    ok = ~np.isnan(tstarts)
    idx = np.where(ok)[0]
    ts = tstarts[idx]
    a = int(np.searchsorted(ts, lo_t, side="left"))
    b = int(np.searchsorted(ts, hi_t, side="right"))
    a = max(0, (idx[a] if a < len(idx) else M) - pad)
    b = min(M, (idx[b - 1] if b > 0 else 0) + pad)
    return a, max(a + 1, b)


def dtw_verify(needle, chars, times, lo_c, hi_c, jf_min=0):
    """拼音 DTW 驗證 head needle 在字元窗內；回 (per_char_score, char_pos) / None。
    含語速合理性門檻（1–12 字/s，§8 手法 3）。jf_min 禁止路徑早於此字元
    起始（防 pad 區回音劫持）。"""
    hi_c = min(hi_c, len(chars))
    if lo_c >= hi_c or not needle:
        return None
    pat = list(needle)
    win = chars[lo_c:hi_c]
    score, jf, jl = dtw_span(pat, win, jf_min=jf_min)
    if jf < 0:
        return None
    t0, t1 = t_of(times, lo_c + jf), t_of(times, lo_c + jl)
    if t0 is not None and t1 is not None and (t1 - t0) > 0.5:
        rate = len(pat) / (t1 - t0)
        if not 1.0 <= rate <= 12.0:
            return None
    return score / max(1, len(pat)), lo_c + jf


# --------------------------------------------------------------------------
# SKILL 修正層
# --------------------------------------------------------------------------

def skill_correct(paras, cls_list, res_list, chars, times, stream, py_stream,
                  norm2py, tstarts, duration, verbose=False):
    n = len(paras)
    norms = [norm_para(p["text"]) for p in paras]
    starts = [r["start"] for r in res_list]
    ends = [r["end"] for r in res_list]
    confs = [r["conf"] for r in res_list]
    methods = [r["method"] for r in res_list]
    fixed_end = [bool(r.get("end_fixed")) for r in res_list]
    no_clamp = set()   # R5 夾逼豁免（講首/黑洞救援：書序≠語序，允許回跳）
    changed = []

    def note(i, msg):
        changed.append((i, msg))
        if verbose:
            print(f"    [skill] p{i} {msg}")

    # 首 SUTRA run＋短引文表
    first_run = []
    seen = False
    for i, c in enumerate(cls_list):
        if c == "SUTRA":
            seen = True
            first_run.append(i)
        elif seen:
            break
    quotes = [(j, norms[j]) for j in range(n)
              if cls_list[j] == "SUTRA" and 0 < len(norms[j]) <= SHORT_Q]

    def prev_end(i):
        for j in range(i - 1, -1, -1):
            if starts[j] is not None and ends[j] is not None and ends[j] > starts[j]:
                return ends[j]
            if starts[j] is not None and (ends[j] is None or ends[j] <= starts[j]):
                continue
        return 0.0

    # -- R1/R2：首 run 長塊覆蓋仲裁 --
    for i in first_run:
        m = len(norms[i])
        if m < LONG_B:
            continue
        if starts[i] is None or ends[i] is None or ends[i] <= starts[i]:
            continue  # 已是零寬
        subsumed = any(j > i and j <= i + 10 and q and q in norms[i][:len(q) + 40]
                       for j, q in quotes)
        # 局部全文覆蓋（以 engine span 為中心、前後放寬）
        exp = max(60.0, m / 4.5 * 2.0)
        a, b = chars_in_range(tstarts, max(0.0, starts[i] - 30.0), ends[i] + exp)
        cov, _ = greedy_coverage(norms[i], stream, a, b)
        if cov < FULL_T or subsumed:
            pe = prev_end(i)
            starts[i] = ends[i] = round(pe, 3)
            fixed_end[i] = True
            confs[i] = 0.85
            methods[i] = "block-zero"
            note(i, f"R1/R2 block-zero cov={cov:.2f} subsumed={subsumed}")

    # -- R3/H：講首重構（golden L1-3 慣例：書序≠語序）--
    #  golden 實測慣例：
    #   * 導言 COMM 錨在講首：start ≈ ASR 首字時間 − 0.2s（L3: 2.15−0.2=1.95、
    #     L4: 1.74−0.2=1.54，皆與人工 golden 逐 byte 相符）。比期數 fuzzy 更強。
    #   * 首 SUTRA run＝印刷參考塊；其 engine「幻影 READ」多半是講後 dup 引文
    #     （同文重印，如 L38 p0↔p12、L22 p0↔p19）的 vocalization 被前置認領，
    #     且 span 吞掉了講頭導言 → run 歸零、讀段移轉給 dup。
    #   * 連續零寬 COMM（導言區塊，如 L22 p14-18）：第一員文字錨 anchor0，
    #     其餘先逐字/拼音證據錨，無證據者按字數比例拆分剩餘窗（>60s 標人工）。
    first_char_t = None
    for _t in times:
        if _t[0] is not None and _t[0] == _t[0]:
            first_char_t = _t[0]
            break
    anchor0 = max(0.0, round(first_char_t - 0.2, 3)) if first_char_t is not None else None

    if first_run and first_run[0] == 0 and anchor0 is not None:
        run_end = max(first_run)

        # H-a：run 幻影 READ → dup 移轉（先做；head 區塊邊界會用 dup 新起點）
        for i in first_run:
            if starts[i] is None or ends[i] is None or ends[i] <= starts[i]:
                continue  # 已零寬
            if len(norms[i]) >= LONG_B or len(norms[i]) < 8:
                continue  # R1/R2 已仲裁（cov≥0.6 留下的視為真讀）；太短不仲裁
            nd = norms[i]
            dup = -1
            for j in range(run_end + 1, min(n, run_end + 17)):
                if cls_list[j] == "SUTRA" and norms[j] and norms[j][:20] == nd[:20]:
                    dup = j
                    break
            old_s, old_e = starts[i], ends[i]
            if dup >= 0:
                # run 段歸零（印刷參考塊），vocalization 移轉給 dup
                starts[i] = ends[i] = round(prev_end(i), 3)
                fixed_end[i] = True
                confs[i] = 0.85
                methods[i] = "block-zero"
                note(i, f"H dup-transfer zero (vocalization -> p{dup})")
                if not (starts[dup] is not None and ends[dup] is not None
                        and ends[dup] > starts[dup]):
                    # dup 重錨：先舊 span 緊窗（L38 型），再放寬（L10 型）
                    s3 = per3 = None
                    for w3a, w3b in ((max(0.0, old_s - 2.0), old_e + 1.0),
                                     (max(0.0, old_s - 5.0), old_e + 175.0)):
                        a3, b3 = chars_in_range(tstarts, w3a, w3b)
                        if b3 <= a3:
                            continue
                        q3 = stream.find(nd[:HEAD_N], a3, b3) if len(nd) >= 6 else -1
                        if q3 >= 0:
                            t3 = t_of(times, q3)
                            s3 = max(0.0, (t3 if t3 is not None else w3a) - LEAD_BACK)
                            per3 = 0.9
                            break
                        v3 = dtw_verify(nd[:HEAD_N], chars, times, a3, b3)
                        if v3 and v3[0] >= 0.55 and t_of(times, v3[1]) is not None:
                            s3 = max(0.0, t_of(times, v3[1]) - LEAD_BACK)
                            per3 = v3[0]
                            break
                    if s3 is not None and s3 < old_e + 175.0:
                        starts[dup] = round(s3, 3)
                        fixed_end[dup] = False
                        confs[dup] = 0.85 if per3 >= 0.9 else 0.7
                        methods[dup] = "dup-anchor"
                        no_clamp.add(dup)
                        note(dup, f"H dup-anchor {'verb' if per3 >= 0.9 else f'fuzzy{per3:.2f}'} @{s3:.2f}")
                    else:
                        # 無證據：繼承舊 span（保住可播性），R10 稽核 + 人工複核
                        starts[dup] = round(old_s, 3)
                        ends[dup] = round(old_e, 3)
                        fixed_end[dup] = False
                        confs[dup] = 0.45
                        methods[dup] = "dup-anchor"
                        no_clamp.add(dup)
                        note(dup, f"H dup-anchor inherit @{old_s:.2f} +review")
            else:
                # 無 dup：局部覆蓋仲裁（cov<0.6 → 幻影 → 歸零）
                exp3 = max(60.0, len(nd) / 4.5 * 2.0)
                a3, b3 = chars_in_range(tstarts, max(0.0, old_s - 30.0),
                                        old_e + exp3)
                cov3, _ = greedy_coverage(nd, stream, a3, b3)
                if cov3 < FULL_T:
                    starts[i] = ends[i] = round(prev_end(i), 3)
                    fixed_end[i] = True
                    confs[i] = 0.85
                    methods[i] = "block-zero"
                    note(i, f"H block-zero cov={cov3:.2f} (no dup)")

        # H-b：導言區塊（first run 後連續 COMM）重構
        blk = []
        for j in range(run_end + 1, n):
            if cls_list[j] == "COMM" and len(norms[j]) >= 2:
                blk.append(j)
            else:
                break
        if blk:
            intro = blk[0]
            # 第一員（真導言）：文字型錨 anchor0（golden-exact）
            cur = starts[intro]
            if re.match(r"《楞伽[经經]》", paras[intro]["text"]) \
                    and (cur is None or abs(cur - anchor0) > 0.5):
                starts[intro] = anchor0
                fixed_end[intro] = False
                methods[intro] = "intro-rescue"
                confs[intro] = 0.9
                note(intro, f"H intro text-anchor {cur:.2f} -> {anchor0:.2f}")
            # 區塊右邊界：block 後第一個實寬段
            hi_t = duration or 0.0
            for j in range(blk[-1] + 1, n):
                if starts[j] is not None and ends[j] is not None and ends[j] > starts[j]:
                    hi_t = starts[j]
                    break
            # 其餘成員：先證據、後比例拆分
            ev_end = starts[intro]
            unev = []
            for j in blk[1:]:
                if starts[j] is not None and ends[j] is not None \
                        and ends[j] > starts[j] and starts[j] <= hi_t:
                    ev_end = max(ev_end, starts[j])  # 已有正確實寬者尊重
                    continue
                nd = norms[j]
                hit = None
                if len(nd) >= 8 and hi_t > ev_end:
                    a4 = max(anchor0, ev_end)
                    b4 = min(hi_t, a4 + 175.0)
                    a4i, b4i = chars_in_range(tstarts, a4, b4)
                    for off4 in (0, 8):
                        nd4 = nd[off4:off4 + 10]
                        if len(nd4) < 8:
                            continue
                        q4 = stream.find(nd4, a4i, b4i)
                        if q4 >= 0:
                            t4 = t_of(times, q4)
                            s4 = max(a4, (t4 if t4 is not None else a4) - off4 / 4.5)
                            if s4 < hi_t:
                                hit = (s4, "verb")
                                break
                    if hit is None:
                        v4 = dtw_verify(nd[:HEAD_N], chars, times, a4i,
                                        min(len(chars), b4i + 150))
                        if v4 and v4[0] >= 0.6 and t_of(times, v4[1]) is not None:
                            s4 = max(a4, t_of(times, v4[1]))
                            if s4 < hi_t:
                                hit = (s4, f"fuzzy{v4[0]:.2f}")
                if hit is not None and hit[0] >= ev_end - 0.01:
                    starts[j] = round(hit[0], 3)
                    fixed_end[j] = False
                    methods[j] = "head-anchor"
                    confs[j] = 0.8
                    ev_end = starts[j]
                    note(j, f"H head-anchor {hit[1]} @{hit[0]:.2f}")
                else:
                    unev.append(j)
            if unev:
                # 拆分窗起點＝導言吃掉自身預期朗讀時長後（否則鏈會把導言壓回零寬）
                lo5 = max(anchor0 + max(1.5, len(norms[intro]) / 4.5), ev_end)
                lens5 = [max(4, len(norms[k])) for k in unev]
                tot5 = sum(lens5)
                if hi_t - lo5 >= 1.0:
                    t5 = lo5
                    for k, w5 in zip(unev, lens5):
                        s5 = t5
                        t5 = lo5 + (hi_t - lo5) * (sum(lens5[:unev.index(k) + 1]) / tot5)
                        starts[k] = round(s5, 3)
                        fixed_end[k] = True   # 防鏈塌縮（後鄰零錨可能更早）
                        methods[k] = "head-split"
                        confs[k] = 0.6 if (hi_t - lo5) <= 60 else 0.4
                        note(k, f"H head-split [{s5:.1f},{t5:.1f}]")
                for k in unev:
                    no_clamp.add(k)
            for j in blk:
                no_clamp.add(j)

    # -- R4：误判 skip 救援（零寬短引文局部強證據；只救「清楚念出」，
    #    微讀（2-6 字帶過）證據不足，不硬救，列入人工清單） --
    for i in range(n):
        if cls_list[i] != "SUTRA":
            continue
        m = len(norms[i])
        if not (4 <= m <= SHORT_Q):
            continue
        if starts[i] is not None and ends[i] is not None and ends[i] > starts[i]:
            continue  # 已有實寬
        lo_t = prev_end(i)
        hi_t = duration
        for j in range(i + 1, n):
            if ends[j] is not None and starts[j] is not None and ends[j] > starts[j]:
                hi_t = starts[j]
                break
        a, b = chars_in_range(tstarts, lo_t, hi_t)
        head = norms[i][:HEAD_N]
        q = stream.find(head, a, b)
        if q >= 0:
            t = t_of(times, q)
            s = max(lo_t, (t if t is not None else lo_t) - LEAD_BACK)
            if s <= hi_t:
                starts[i] = round(s, 3)
                fixed_end[i] = False
                confs[i] = 0.9
                methods[i] = "quote-rescue"
                note(i, f"R4 quote-rescue verbatim @{s:.2f}")
                continue
        # 體部逐字（頭部口吃/重複時換錨點；見 L3#52「而是…但是而使世尊…」型）
        body_hit = None
        for off in (4, 8):
            nd = norms[i][off:off + 10]
            if len(nd) < 8:
                continue
            qb = stream.find(nd, a, b)
            if qb >= 0 and (body_hit is None or qb < body_hit[0]):
                body_hit = (qb, off)
        if body_hit is not None:
            qb, off = body_hit
            t = t_of(times, qb)
            back = off / 4.5
            s = max(lo_t, (t if t is not None else lo_t) - back)
            if s <= hi_t:
                starts[i] = round(s, 3)
                fixed_end[i] = False
                confs[i] = 0.8
                methods[i] = "quote-rescue-body"
                note(i, f"R4 quote-rescue body@{off} @{s:.2f}")
                continue
        v = None
        a1, _b1 = chars_in_range(tstarts, lo_t, hi_t, pad=0)
        if _b1 > a1:
            v = dtw_verify(head, chars, times, a1, min(len(chars), _b1 + 150),
                           jf_min=0)
        if v and v[0] >= 0.55:
            per, qq = v
            t = t_of(times, qq)
            s = max(lo_t, (t if t is not None else lo_t) - LEAD_BACK)
            # 二階段：模糊命中點前後找逐字複核（前 15s＋後 20s；治早錨／回音）
            if t is not None:
                va, vb = chars_in_range(tstarts, t - 15.0, t + 20.0, pad=0)
                qv = stream.find(head, va, vb)
                if qv < 0 and len(norms[i]) > HEAD_N + 4:
                    qv = stream.find(norms[i][8:8 + HEAD_N], va, vb)
                if qv >= 0:
                    tv = t_of(times, qv)
                    sv = max(lo_t, (tv if tv is not None else lo_t) - LEAD_BACK)
                    if sv <= hi_t:
                        s, per = sv, 0.9
            if s <= hi_t:
                starts[i] = round(s, 3)
                fixed_end[i] = False
                confs[i] = round(min(0.8, 0.5 + per * 0.4), 3) if per < 0.9 \
                    else 0.85
                methods[i] = "quote-rescue-fuzzy" if per < 0.9 else "quote-rescue"
                note(i, f"R4 quote-rescue fuzzy {per:.2f} @{s:.2f}")

    # -- R11：黑洞仲裁（time-axis hole ≥ 30s；跑在 R8 前，讓 R8 能拆
    #    R11 產生的胖 span）--
    #  塌縮段的音檔常在相鄰「時間軸黑洞」內（書序在後、語序在前，如 L38
    #  p76-86 錨在黑洞末端 1500s、真音檔在 [1285,1498]）。處理順序：
    #  證據認領（逐字→體部→拼音，洞內書序單調）→ 未認領者在「前後錨點
    #  之間」按字數插值（勿全塞殘餘窗）→ 窗 <3s 誠實留零。洞後段若頭部
    #  在洞內有強證據（≥0.85）則晚錨救援（R11b）；跑題/ASR 天花板洞只降
    #  conf 提請人工聽（R11c，不動位置）。
    reads_t = sorted(
        (s, e, i) for i, (s, e) in enumerate(zip(starts, ends))
        if s is not None and e is not None and e > s)
    for (s1, e1, i1), (s2, e2, i2) in zip(reads_t, reads_t[1:]):
        hole = s2 - e1
        if hole < 30.0:
            continue
        cand = [i for i in range(n)
                if starts[i] is not None and ends[i] is not None
                and ends[i] <= starts[i]
                and e1 - 5.0 <= starts[i] <= s2 + 5.0
                and cls_list[i] in ("SUTRA", "COMM")
                and len(norms[i]) >= 6]
        if not cand:
            # R11b/R11c：洞後段晚錨救援 / 無人認領大洞
            nd2 = norms[i2]
            if len(nd2) >= 8:
                a11, b11 = chars_in_range(tstarts, e1, s2)
                ev11 = None
                if b11 > a11:
                    q11 = stream.find(nd2[:12], a11, b11)
                    if q11 >= 0 and t_of(times, q11) is not None:
                        ev11 = (t_of(times, q11), 1.0)
                    else:
                        v11 = dtw_verify(nd2[:HEAD_N], chars, times, a11, b11)
                        if v11 and v11[0] >= 0.85 and t_of(times, v11[1]) is not None:
                            ev11 = (t_of(times, v11[1]), v11[0])
                if ev11 is not None and ev11[0] < s2 - 5.0:
                    starts[i2] = round(max(e1, ev11[0] - LEAD_BACK), 3)
                    methods[i2] = "hole-late-rescue"
                    confs[i2] = 0.7
                    no_clamp.add(i2)
                    note(i2, f"R11b late-rescue {s2:.2f} -> {starts[i2]:.2f}")
                else:
                    # 無人認領的大洞（跑題/ASR 天花板）：不動位置，降 conf 提請人工聽
                    confs[i2] = min(confs[i2], 0.49)
                    note(i2, f"R11c hole-unexplained [{e1:.0f},{s2:.0f}] +review")
            continue
        # 塌縮段書序範圍內的短零寬段一併納入（如「下一段：」）
        base = set(cand)
        for m in range(cand[0], cand[-1] + 1):
            if starts[m] is not None and ends[m] is not None \
                    and ends[m] <= starts[m] and m not in base \
                    and cls_list[m] in ("SUTRA", "COMM"):
                cand.append(m)
                base.add(m)
        cand.sort()
        # 證據認領（書序、洞內單調；dup/echo 防護：書序在後的同文段
        # 已擁有實寬 span → 音檔屬它（§0.5 經文重複段慣例），前段不認領）
        cur_lo = e1
        anchored = {}
        for m in cand:
            nd = norms[m]
            echo = False
            for j in range(m + 1, min(n, m + 25)):
                if cls_list[j] == cls_list[m] and norms[j] \
                        and norms[j][:20] == nd[:20] \
                        and starts[j] is not None and ends[j] is not None \
                        and ends[j] > starts[j]:
                    echo = True
                    break
            if echo:
                note(m, "R11 echo-guard: book-later dup owns the audio")
                continue
            hit = None
            if len(nd) >= 10:
                a_m, b_m = chars_in_range(tstarts, cur_lo, s2)
                if b_m > a_m:
                    q11 = stream.find(nd[:10], a_m, b_m)
                    if q11 >= 0 and t_of(times, q11) is not None \
                            and t_of(times, q11) >= cur_lo - 0.5:
                        hit = (t_of(times, q11), 0.85, "verb")
            if hit is None and len(nd) >= 12:
                for off11 in (4, 8):
                    ndb = nd[off11:off11 + 10]
                    if len(ndb) < 8:
                        continue
                    a_m, b_m = chars_in_range(tstarts, cur_lo, s2)
                    qb = stream.find(ndb, a_m, b_m)
                    if qb >= 0 and t_of(times, qb) is not None:
                        tb = t_of(times, qb)
                        hit = (max(cur_lo, tb - off11 / 4.5), 0.8, f"body{off11}")
                        break
            if hit is None and len(nd) >= 8:
                a_m, b_m = chars_in_range(tstarts, cur_lo, s2)
                if b_m > a_m:
                    v11 = dtw_verify(nd[:HEAD_N], chars, times, a_m, b_m)
                    if v11 and v11[0] >= 0.60 and t_of(times, v11[1]) is not None \
                            and t_of(times, v11[1]) >= cur_lo - 0.5:
                        hit = (t_of(times, v11[1]), 0.65, f"fuzzy{v11[0]:.2f}")
            if hit is not None and hit[0] < s2 - 1.5:
                # 起點重疊防護：別的 READ 段已在同一起音點 ±2s → 音檔已被認領
                # （L7 p1 型：fuzzy 咬到洞緣上 i2 的讀經起音；文字前綴規則
                #  對「近鄰不同引文」無效，起點鄰近才是實質判準）
                clash = None
                for j in range(n):
                    if j != m and starts[j] is not None and ends[j] is not None \
                            and ends[j] > starts[j] \
                            and abs(starts[j] - (hit[0] - LEAD_BACK)) <= 2.0:
                        clash = j
                        break
                if clash is not None:
                    note(m, f"R11 start-clash p{clash}@{starts[clash]:.1f} (claimed)")
                    continue
                starts[m] = round(max(cur_lo, hit[0] - LEAD_BACK), 3)
                fixed_end[m] = False
                methods[m] = "hole-anchor"
                confs[m] = hit[1]
                no_clamp.add(m)
                anchored[m] = starts[m]
                cur_lo = starts[m]
                note(m, f"R11 hole-anchor {hit[2]} @{starts[m]:.2f}")
        # 未認領者：在「前後錨點之間」按字數插值（書序、洞內單調）
        uc = [m for m in cand if m not in anchored]
        if uc:
            runs_uc = []
            cur = [uc[0]]
            for m in uc[1:]:
                if m == cur[-1] + 1:
                    cur.append(m)
                else:
                    runs_uc.append(cur)
                    cur = [m]
            runs_uc.append(cur)
            for run in runs_uc:
                lo_b = e1
                lo_from_anchor = False
                for mm in reversed(cand[:cand.index(run[0])]):
                    if mm in anchored:
                        # 前錨成員先吃掉自己的預期朗讀時長
                        lo_b = starts[mm] + max(2.0, len(norms[mm]) / 4.5)
                        lo_from_anchor = True
                        break
                hi_b = s2
                hi_from_anchor = False
                for mm in cand[cand.index(run[-1]) + 1:]:
                    if mm in anchored:
                        hi_b = starts[mm]
                        hi_from_anchor = True
                        break
                if not (lo_from_anchor or hi_from_anchor):
                    # 兩側皆洞緣、無證據錨 → 不盲拆（L7 p1-4 型），誠實留零
                    for m in run:
                        methods[m] = "hole-zero"
                        confs[m] = 0.35
                        note(m, "R11 hole-zero (no in-hole anchor)")
                    continue
                if hi_b < lo_b:
                    hi_b = min(s2, lo_b)
                if hi_b - lo_b >= 3.0:
                    lens_r = [max(4, len(norms[m])) for m in run]
                    tot_r = sum(lens_r)
                    t_r = lo_b
                    for m, w_r in zip(run, lens_r):
                        s_r = t_r
                        t_r = lo_b + (hi_b - lo_b) * (sum(lens_r[:run.index(m) + 1]) / tot_r)
                        starts[m] = round(s_r, 3)
                        fixed_end[m] = True   # 防鏈塌縮
                        methods[m] = "hole-split"
                        confs[m] = 0.4
                        no_clamp.add(m)
                        note(m, f"R11 hole-split [{s_r:.1f},{t_r:.1f}]")
                else:
                    for m in run:
                        methods[m] = "hole-zero"
                        confs[m] = 0.35
                        note(m, "R11 hole-zero (no evidence, tiny residual)")
        # 釘住書序在前、音檔在後的相鄰 READ 段（防 R5 鏈回拉）
        for j in range(cand[0] - 1, -1, -1):
            if starts[j] is not None and ends[j] is not None and ends[j] > starts[j]:
                if ends[j] > starts[cand[0]]:
                    fixed_end[j] = True
                    note(j, "R11 pinned (book-order prev, audio-after)")
                break

    # -- R8：過胖引文拆分（SUTRA 實寬語速 < 2.5 字/s＋緊鄰零寬 COMM →
    #    前段按朗讀語速切給引文，後段還給講解） --
    for i in range(n):
        if cls_list[i] != "SUTRA":
            continue
        m = len(norms[i])
        if not (4 <= m <= SHORT_Q * 2):
            continue
        if starts[i] is None or ends[i] is None or ends[i] <= starts[i]:
            continue
        if methods[i] in ("quote-rescue", "quote-rescue-fuzzy"):
            continue
        span = ends[i] - starts[i]
        if span <= 0 or m / span >= 2.5:
            continue
        if i + 1 >= n or cls_list[i + 1] != "COMM":
            continue
        j = i + 1
        if starts[j] is not None and ends[j] is not None and ends[j] > starts[j]:
            continue  # 後段已有實寬，不拆
        # 守衛：引文本身須有局部朗讀證據（否則胖 span 是幻影，不可拆；L28#10 型）
        a8, b8 = chars_in_range(tstarts, max(0.0, starts[i] - 2.0), ends[i] + 1.0)
        head_ok = stream.find(norms[i][:10], a8, b8) >= 0
        if not head_ok:
            v8 = dtw_verify(norms[i][:HEAD_N], chars, times, a8, b8)
            head_ok = bool(v8 and v8[0] >= 0.5)
        if not head_ok:
            confs[i] = min(confs[i], 0.4)
            note(i, "R8 guard: no local read evidence, keep fat + review")
            continue
        cut = starts[i] + m / 4.5
        if cut >= ends[i] - 1.0:
            continue
        starts[j] = round(cut, 3)
        fixed_end[j] = False
        confs[j] = 0.6
        methods[j] = "split-give"
        fixed_end[i] = True
        ends[i] = round(cut, 3)
        confs[i] = min(confs[i], 0.8)
        note(i, f"R8 split @{cut:.2f} -> p{j}")
        note(j, f"R8 split-give @{cut:.2f}")

    # -- R9（early-snap）已刪除：實證在 golden 上製造回歸（最早模糊命中多為
    #    口吃預演回音，engine 的 evidence 仲裁已是最優；殘差交人工 UI 處理） --

    # -- R10：救援稽核閘（auditor 一致性：預期朗讀窗內頭 24 字 DTW；
    #    dh<0.4 無證據→退回待人工；0.4–0.55 弱保留＋複核；≥0.55 確認；
    #    緊接 R4 跑，用預期窗 [s-1.5, s+m/4.5+5]，鏈化前攔截） --
    for i in range(n):
        if methods[i] not in ("quote-rescue-fuzzy", "quote-rescue-body",
                              "dup-anchor"):
            continue
        if starts[i] is None:
            continue
        m = len(norms[i])
        head24 = list(norms[i][:min(24, m)])
        if len(head24) < 6:
            continue
        exp_end = starts[i] + m / 4.5 + 5.0
        a10, b10 = chars_in_range(tstarts, starts[i] - 1.5, exp_end)
        if b10 - a10 < max(8, len(head24)):
            a10 = max(0, a10 - 20)
            b10 = min(len(chars), a10 + max(40, len(head24) * 3))
        win10 = chars[a10:b10]
        if not win10:
            continue
        dh, jfh, jlh = dtw_span(head24, win10)
        dh_n = dh / max(1, len(head24))
        t_h = t_of(times, a10 + jfh) if jfh is not None and jfh >= 0 else None
        t_he = t_of(times, a10 + jlh) if jlh is not None and jlh >= 0 else None
        pos_ok = (t_h is not None
                  and (abs(t_h - starts[i]) <= 3.0
                       or (t_he is not None and t_h >= starts[i] - 3.0
                           and t_he <= exp_end + 3.0)))
        gverb = len(norms[i]) >= 8 and norms[i] in stream
        if dh_n >= 0.4 and pos_ok:
            if dh_n < 0.55:
                confs[i] = 0.5
                note(i, f"R10 weak-keep dh={dh_n:.2f} +review")
            # else：確認，保留 R4 證據與 conf
        elif not gverb:
            # 全講無逐字出現＋局部弱 → 確實沒念（auditor skip_ok 一致）
            starts[i] = None
            fixed_end[i] = False
            methods[i] = "rescue-blocked"
            confs[i] = 0.35
            note(i, f"R10 audit-block dh={dh_n:.2f} gverb=False")
        else:
            # 講內他處有逐字（回音）＋局部弱 → 近似保留可播性＋複核，
            # 不硬歸零（歸零反被 auditor 判 span_bad）
            confs[i] = 0.5
            note(i, f"R10 echo-keep dh={dh_n:.2f} +review")

    # -- R6'：回音誤讀修正（READ 短引文自身無證據＋後段有逐字回音 → ZERO，
    #    後段起點前移到引文起點） --
    for i in range(n):
        if cls_list[i] != "SUTRA":
            continue
        m = len(norms[i])
        if not (4 <= m <= SHORT_Q):
            continue
        if starts[i] is None or ends[i] is None or ends[i] <= starts[i]:
            continue
        if methods[i] in ("quote-rescue", "quote-rescue-fuzzy", "split-give",
                          "dup-anchor", "hole-anchor", "head-anchor",
                          "head-split", "hole-split"):
            continue
        if m / max(0.5, ends[i] - starts[i]) >= 3.0:
            continue  # 語速正常：真讀，不碰
        head10 = norms[i][:10]
        head6 = norms[i][:6]
        if len(head10) < 8:
            continue
        a0, b0 = chars_in_range(tstarts, max(0.0, starts[i] - 3.0), ends[i] + 1.0)
        if stream.find(head10, a0, b0) >= 0:
            continue  # 自身有證據：真讀
        v = dtw_verify(head10, chars, times, a0, b0)
        if v and v[0] >= 0.5:
            continue
        echo_j = -1
        for j in range(i + 1, min(n, i + 3)):
            if starts[j] is None or ends[j] is None or ends[j] <= starts[j]:
                continue
            aj, bj = chars_in_range(tstarts, starts[j], ends[j] + 2.0)
            if stream.find(head6, aj, bj) >= 0:
                echo_j = j
                break
        if echo_j < 0:
            continue
        pe = prev_end(i)
        starts[i] = ends[i] = round(pe, 3)
        fixed_end[i] = True
        confs[i] = 0.8
        methods[i] = "echo-zero"
        note(i, "R6' echo-zero")
        # 回音屬於後段講解：後段起點前移（不早於其前界）
        if starts[echo_j] > pe:
            starts[echo_j] = round(pe, 3)
            note(echo_j, "R6' echo-take")

    # -- (舊 R6' 已被上方 R8＋新 R6' 取代，刪) --

    # -- R7：COMM 永不零寬（拆分包夾間隙；大間隙標 NEEDS-HUMAN） --
    need_human = []
    r7_done = set()
    for i in range(n):
        if i in r7_done:
            continue
        if cls_list[i] != "COMM" or len(norms[i]) < 4:
            continue
        if starts[i] is not None and ends[i] is not None and ends[i] > starts[i]:
            continue
        # 找包夾：前一個有寬段的 end → 後一個有寬段的 start
        lo_t, lo_j = 0.0, -1
        for j in range(i - 1, -1, -1):
            if starts[j] is not None and ends[j] is not None and ends[j] > starts[j]:
                lo_t, lo_j = ends[j], j
                break
        hi_t, hi_j = (round(duration, 3) if duration else lo_t), n
        for j in range(i + 1, n):
            if starts[j] is not None and ends[j] is not None and ends[j] > starts[j]:
                hi_t, hi_j = starts[j], j
                break
        # 零寬連段成員
        members = [i]
        for j in range(i + 1, hi_j):
            if cls_list[j] == "COMM" and not (
                    starts[j] is not None and ends[j] is not None and ends[j] > starts[j]):
                members.append(j)
            else:
                hi_j = j
                if starts[j] is not None and ends[j] is not None and ends[j] > starts[j]:
                    hi_t = starts[j]
                break
        lens = [max(4, len(norms[k])) for k in members]
        total = sum(lens)
        degenerate = (hi_t - lo_t) < 1.0   # 鄰段相接無縫隙：語音在胖鄰居體內
        r7_done.update(members)
        t = lo_t
        for k, w in zip(members, lens):
            s = t
            t = lo_t + (hi_t - lo_t) * (sum(lens[:members.index(k) + 1]) / total)
            starts[k] = round(s, 3)
            ends[k] = round(t, 3)
            fixed_end[k] = False
            if degenerate:
                # 誠實留零＋低 conf＋人工複核（不冒充拆分）
                confs[k] = 0.35
                methods[k] = "comm-gap-zero"
                note(k, f"R7 comm-gap-zero @{s:.1f} (no gap to split)")
            else:
                confs[k] = 0.6 if (hi_t - lo_t) <= 60 else 0.4
                methods[k] = "comm-split"
                fixed_end[k] = True   # 防鏈塌縮（R7 拆分結果不得被鄰錨壓回）
                note(k, f"R7 comm-split [{s:.1f},{t:.1f}]")
            if (hi_t - lo_t) > 60:
                need_human.append(k)
        # 外層迴圈跳過已處理成員：標記即可（ends 已有寬，迴圈條件自動跳過）

    # -- R5：鏈（尊重 end_fixed；zero 重壓；golden 慣例：零寬 cosmetic 段
    #    不推進單調邊界 last_t，講首/黑洞救援段豁免夾逼——L3 人工 golden
    #    i=1-6 錨 2.15 > i=7 導言 1.95 證明零寬段允許「往後看見回跳」）--
    for i in range(n - 1):
        if fixed_end[i]:
            continue
        if starts[i + 1] is None:
            continue
        ends[i] = starts[i + 1]
    if not fixed_end[n - 1]:
        ends[n - 1] = round(duration, 3) if duration else starts[n - 1]
    last_t = 0.0
    for i in range(n):
        if starts[i] is None:
            starts[i] = round(last_t, 3)
        is_zero = ends[i] is not None and starts[i] is not None \
            and ends[i] <= starts[i]
        if not is_zero and i not in no_clamp \
                and starts[i] < last_t - 1e-9:
            note(i, f"R5 clamped nonmonotonic ({starts[i]:.1f}<{last_t:.1f})")
            starts[i] = round(last_t, 3)
        if ends[i] is None or ends[i] < starts[i]:
            ends[i] = starts[i]
        if not is_zero:
            last_t = max(last_t, ends[i])
    for i in range(n):
        is_zero = (cls_list[i] == "SUTRA" and
                   methods[i] in ("block-zero", "quote-skip", "skipped-sutra",
                                  "echo-zero", "subsumed-dup",
                                  "interp", "miss", "short"))
        if is_zero and ends[i] is not None and starts[i] is not None:
            if methods[i] in ("block-zero", "skipped-sutra", "subsumed-dup"):
                ends[i] = starts[i]
    # 救援被撞（有證據但鏈位置被鄰段佔據）：如實標記，不靜默吞掉
    # 救援語速守衛：鏈後隱含語速 > 8 字/s → 多半部分朗讀／回音，退回待人工
    review_idx = []
    for i in range(n):
        if methods[i] == "quote-rescue-fuzzy" and ends[i] > starts[i]:
            m = len(norms[i])
            if m / max(0.5, ends[i] - starts[i]) > 8.0:
                pe = prev_end(i)
                starts[i] = ends[i] = round(pe, 3)
                fixed_end[i] = True
                methods[i] = "rescue-blocked"
                confs[i] = 0.35
                note(i, "rescue rate>8/s: partial/echo, back to human")
    for i in range(n):
        if methods[i] in ("quote-rescue", "quote-rescue-body",
                           "quote-rescue-fuzzy") and ends[i] <= starts[i]:
            methods[i] = "rescue-blocked"
            confs[i] = 0.35
            review_idx.append(i)
            note(i, "rescue-blocked")
    return starts, ends, confs, methods, changed


# --------------------------------------------------------------------------
# lecture driver
# --------------------------------------------------------------------------

def process_lecture(ln, cls_map, verbose=False):
    process_lecture._cur_lect_no = int(ln)
    doc = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    lec = doc["lectures"][ln]
    paras = lec["paragraphs"]
    cmap = {c["pid"]: c["cls"] for c in cls_map[ln]}
    assert len(cmap) == len(paras), (ln, len(cmap), len(paras))
    cls_list = [cmap[p["pid"]] for p in paras]
    dump = load_dump(DUMP_DIR / f"{ln}.json")
    engine_paras = [{"text": p["text"], "cls": ("sutra-text" if c == "SUTRA" else "x")}
                    for p, c in zip(paras, cls_list)]
    res_list, _log = engine_align(engine_paras, dump, lec.get("duration"), verbose=False)
    for r, p in zip(res_list, paras):
        r["pid"] = p["pid"]
    chars, times, stream, py_stream, norm2py, tstarts = build_stream(dump)
    starts, ends, confs, methods, changed = skill_correct(
        paras, cls_list, res_list, chars, times, stream, py_stream,
        norm2py, tstarts, lec.get("duration"), verbose=verbose)
    # flags 回傳（skill_correct 內 flags 為局部；重建 NEEDS-HUMAN 清單）
    review = []
    for i, p in enumerate(paras):
        reasons = []
        if methods[i] in ("rescue-blocked", "comm-split", "split-give",
                           "echo-zero", "comm-gap-zero", "hole-zero",
                           "hole-split", "head-split", "hole-late-rescue"):
            reasons.append(methods[i])
        if methods[i] in ("quote-rescue-fuzzy", "quote-rescue-body",
                           "quote-rescue", "dup-anchor", "hole-anchor",
                           "head-anchor") and confs[i] < 0.8:
            reasons.append(f"{methods[i]}:verify-by-ear")
        if confs[i] < 0.5:
            reasons.append(f"low-conf={confs[i]}")
        if methods[i] in ("quote-skip", "skipped-sutra", "block-zero") \
                and cls_list[i] == "SUTRA" and 4 <= len(norm_para(p["text"])) <= SHORT_Q:
            # 短引文判不念：人工複核 objection 權（微讀無法自動驗證）
            reasons.append("skip-quote:verify-by-ear")
        if starts[i] == ends[i] and methods[i] not in (
                "block-zero", "quote-skip", "skipped-sutra", "echo-zero",
                "subsumed-dup", "rescue-blocked", "hole-zero", "comm-gap-zero"):
            # 引擎鏈塌縮段（dtw*/comm-split 等）：golden 從不出現此狀態，
            # 誠實進複核清單（SUTRA 由 run_targets 補 zero 旗標）
            reasons.append(f"zero-width({methods[i]}):verify-by-ear")
        if reasons:
            review.append({"lecture": ln, "i": i, "pid": p["pid"],
                           "cls": cls_list[i], "start": round(starts[i], 3),
                           "end": round(ends[i], 3), "reasons": reasons,
                           "text": p["text"][:60]})
    return paras, cls_list, res_list, (starts, ends, confs, methods, changed), review


def tune():
    import statistics
    cls_map = load_ebook_cls()
    doc = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    print(f"{'lec':>4} {'n':>4} {'eng-mean':>9} {'skl-mean':>9} {'eng≤1s':>7} {'skl≤1s':>7} {'zP':>6} {'zR':>6}")
    for ln in GOLDEN:
        paras, cls_list, res_list, (starts, ends, confs, methods, changed), _review = \
            process_lecture(ln, cls_map)
        gold = doc["lectures"][ln]["paragraphs"]
        ed, sd = [], []
        for i, p in enumerate(gold):
            if p["start"] == p["end"]:
                continue
            ed.append(abs(res_list[i]["start"] - p["start"]))
            sd.append(abs(starts[i] - p["start"]))
        gz = {i for i, p in enumerate(gold) if p["start"] == p["end"]}
        pz = {i for i, m in enumerate(methods)
              if m in ("block-zero", "quote-skip", "skipped-sutra", "subsumed-dup")
              or ends[i] <= starts[i]}
        tp = len(gz & pz)
        print(f"{ln:>4} {len(paras):>4} "
              f"{statistics.mean(ed):>9.2f} {statistics.mean(sd):>9.2f} "
              f"{sum(1 for d in ed if d<=1)/len(ed):>7.2%} {sum(1 for d in sd if d<=1)/len(sd):>7.2%} "
              f"{tp/max(1,len(pz)):>6.2%} {tp/max(1,len(gz)):>6.2%}   skill-changes={len(changed)}")
        # skill 惡化段
        for i, p in enumerate(gold):
            if p["start"] == p["end"]:
                continue
            if abs(starts[i] - p["start"]) > abs(res_list[i]["start"] - p["start"]) + 2.0:
                print(f"    REGRESS p{i} engΔ={abs(res_list[i]['start']-p['start']):.1f} "
                      f"sklΔ={abs(starts[i]-p['start']):.1f} {methods[i]} {p['text'][:45]}")
        for i in sorted(gz ^ pz):
            p = gold[i]
            tag = "MISS-ZERO" if i in gz else "FALSE-ZERO"
            print(f"    {tag} p{i} {methods[i]} gold_s={p['start']:.2f} {p['text'][:45]}")


def run_targets(dry_run=True, only=None, verbose=False):
    """跑 L4-42（只改 start/end/conf/method/zero；confirmed/reviewed 原樣）。"""
    import statistics
    cls_map = load_ebook_cls()
    doc = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    # 安全基線：L1-3 與所有旗標的快照（apply 後校驗）
    golden_snap = {ln: [(p["start"], p["end"], p.get("confirmed"),
                         p.get("zero", False)) for p in doc["lectures"][ln]["paragraphs"]]
                   for ln in GOLDEN}
    flag_snap = {ln: (lec.get("reviewed"),
                      [p.get("confirmed") for p in lec["paragraphs"]])
                 for ln, lec in doc["lectures"].items()}
    targets = [only] if only else TARGETS
    all_review = []
    for ln in targets:
        paras, cls_list, res_list, (starts, ends, confs, methods, changed), review = \
            process_lecture(ln, cls_map, verbose=verbose)
        all_review.extend(review)
        lec = doc["lectures"][ln]
        assert lec.get("reviewed") is False, f"L{ln} reviewed 非 False，拒寫"
        assert not any(p.get("confirmed") for p in paras), f"L{ln} 有 confirmed，拒寫"
        n_read = sum(1 for s, e in zip(starts, ends) if e > s)
        n_zero = len(paras) - n_read
        d = [abs(a - b) for a, b in
             zip([p["start"] for p in paras], starts)]
        print(f"[lengqie#{ln}] paras={len(paras)} read={n_read} zero={n_zero} "
              f"mean|Δvs-ngram|={statistics.mean(d):.2f}s "
              f"maxΔ={max(d):.2f}s changes={len(changed)} review={len(review)}")
        if dry_run:
            continue
        for _i, (p, s, e, c, m) in enumerate(
                zip(lec["paragraphs"], starts, ends, confs, methods)):
            p["start"], p["end"] = round(s, 3), round(e, 3)
            if s == e:
                # zero 標記：沿用 UI 語義（師父沒念）
                if m in ("block-zero", "quote-skip", "skipped-sutra",
                         "echo-zero", "subsumed-dup", "rescue-blocked",
                         "hole-zero", "comm-gap-zero"):
                    p["zero"] = True
                elif cls_list[_i] == "SUTRA":
                    # 引擎鏈塌縮的 SUTRA（dtw*/ngram…）：補誠實 zero 旗標＋降 conf
                    # golden 從不出現「無旗標零寬」狀態
                    p["zero"] = True
                    c = min(c, 0.45)
                else:
                    # COMM 塌縮：師父有講，不標 zero，降 conf 走複核清單
                    c = min(c, 0.45)
                    if "zero" in p:
                        del p["zero"]
                p["conf"] = c
            else:
                p["conf"] = c
                if "zero" in p:
                    del p["zero"]
            p["method"] = m
            # confirmed 鍵原樣保留，不碰
    if dry_run:
        print(f"dry-run：不寫檔。review total={len(all_review)}")
        return all_review
    # 寫檔＋校驗
    JSON_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    new = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for ln in GOLDEN:
        cur = [(p["start"], p["end"], p.get("confirmed"), p.get("zero", False))
               for p in new["lectures"][ln]["paragraphs"]]
        assert cur == golden_snap[ln], f"L{ln} GOLDEN 被改動！"
    for ln, lec in new["lectures"].items():
        orev, oconf = flag_snap[ln]
        assert lec.get("reviewed") == orev, f"L{ln} reviewed 被改動！"
        assert [p.get("confirmed") for p in lec["paragraphs"]] == oconf, \
            f"L{ln} confirmed 被改動！"
    print(f"wrote {JSON_PATH}；L1-3 golden 與全系列 confirmed/reviewed 校驗通過。")
    rep_path = ROOT / "tool" / "jiangjing_para_map" / "reports" / \
        "lengqie_manual_review.json"
    rep_path.write_text(json.dumps(all_review, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"人工複核清單：{rep_path}（{len(all_review)} 段）")
    return all_review


def merge_audit():
    """把 span_audit 的 span_bad  verdicts 併入人工清單（附 t_head 聽打點）。"""
    audit = json.loads((ROOT / "tool" / "jiangjing_para_map" / "reports" /
                        "span_audit_lengqie.json").read_text(encoding="utf-8"))
    rep_path = ROOT / "tool" / "jiangjing_para_map" / "reports" / \
        "lengqie_manual_review.json"
    review = json.loads(rep_path.read_text(encoding="utf-8"))
    have = {(r["lecture"], r["i"]) for r in review}
    doc = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    added = 0
    for row in audit["rows"]:
        ln = row["lecture"]
        if ln in GOLDEN:
            continue
        for d in row["details"]:
            if d["verdict"] != "span_bad" or (ln, d["i"]) in have:
                continue
            p = doc["lectures"][ln]["paragraphs"][d["i"]]
            ev = d.get("ev", {})
            review.append({
                "lecture": ln, "i": d["i"], "pid": d["pid"],
                "start": p["start"], "end": p["end"],
                "reasons": [f"span_bad:audit (d_head={ev.get('d_head')}, "
                            f"listen@{ev.get('t_head')})"],
                "text": p["text"][:60]})
            added += 1
    rep_path.write_text(json.dumps(review, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"merge-audit: +{added} span_bad → {rep_path}（共 {len(review)} 段）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--merge-audit", action="store_true")
    ap.add_argument("--lecture", type=int)
    args = ap.parse_args()
    if args.tune:
        tune()
        return
    if args.merge_audit:
        merge_audit()
        return
    only = str(args.lecture) if args.lecture else None
    if only and only not in TARGETS:
        print(f"lecture {only} 不在 4-42 目標內（L1-3 為 golden，不碰）")
        return
    if args.apply:
        run_targets(dry_run=False, only=only)
    else:
        run_targets(dry_run=True, only=only)


if __name__ == "__main__":
    main()
