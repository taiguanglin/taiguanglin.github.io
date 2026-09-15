#!/usr/bin/env python3
"""楞伽經段落 ↔ 音檔精準對齊器（SKILL `lengqie-align` 的執行器）。

架構：engine（tool/jiangjing_para_map/realign_dtw.align_lecture，FunASR
字級 DTW）＋ SKILL 結構修正層（本檔 skill_correct）。

SKILL 規則（由 audio_map3/lengqie.json L1-3 人工 golden 提煉）：
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

    # -- R3：被吞掉的導言救援（只處理「講首 run＋期數 intro」型；
    #    錨＝期數「第X期」（ASR  robust）＋講首 120s 先驗；找不到就留白＋review，
    #    絕不在大窗內 fuzzy 亂錨） --
    CN = "一二三四五六七八九"
    lect_no = getattr(process_lecture, "_cur_lect_no", None)
    if first_run and first_run[0] == 0:
        cn = "" if lect_no is None else (
            CN[lect_no - 1] if lect_no <= 9 else
            ("十" if lect_no == 10 else
             ("十" + CN[lect_no - 11] if lect_no < 20 else
              (CN[lect_no // 10 - 1] + "十" + (CN[lect_no % 10 - 1] if lect_no % 10 else "")))))
        run_end = max(first_run)
        for i in range(run_end + 1, min(n, run_end + 7)):
            if cls_list[i] == "SUTRA" or len(norms[i]) < 4:
                continue
            w = (ends[i] or 0) - (starts[i] or 0)
            if w >= 1.0:
                continue  # 已有實寬
            hi_t = duration
            for j in range(i + 1, n):
                if ends[j] is not None and starts[j] is not None and ends[j] > starts[j]:
                    hi_t = starts[j]
                    break
            a, b = chars_in_range(tstarts, 0.0, min(hi_t, 150.0))
            hit = None
            if cn:
                for qi in ("第" + cn + "期", cn + "期"):
                    q = stream.find(qi, a, b)
                    if q >= 0:
                        t = t_of(times, q)
                        # 導言起點≈期數前約 0.5–3s（「楞伽經第四期…」期數在頭）
                        s = max(0.0, (t if t is not None else 0.0) - 1.5)
                        hit = (q, s, "qishu")
                        break
            if hit is None:
                for off in (0, 8, len(norms[i]) // 4):
                    nd = norms[i][off:off + HEAD_N]
                    if len(nd) < 6:
                        continue
                    q = stream.find(nd, a, b)
                    if q >= 0:
                        t = t_of(times, q)
                        back = off / 4.5
                        s = max(0.0, (t if t is not None else 0.0) - back)
                        if s > 120.0:
                            continue
                        hit = (q, s, f"verbatim@{off}")
                        break
            if hit is None:
                a1, b1 = chars_in_range(tstarts, 0.0, min(hi_t, 120.0), pad=0)
                if b1 > a1:
                    v = dtw_verify(norms[i][:HEAD_N], chars, times,
                                   a1, min(len(chars), b1 + 150))
                    if v and v[0] >= 0.7:
                        t = t_of(times, v[1])
                        s = max(0.0, (t if t is not None else 0.0) - LEAD_BACK)
                        if s <= 120.0:
                            hit = (v[1], s, "fuzzy")
            if hit is not None:
                q, s, how = hit
                if s <= min(hi_t, 120.0):
                    starts[i] = round(s, 3)
                    fixed_end[i] = False
                    confs[i] = 0.9 if how == "qishu" else 0.8
                    methods[i] = "intro-rescue"
                    note(i, f"R3 intro-rescue {how} @{s:.2f}")

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
        if methods[i] not in ("quote-rescue-fuzzy", "quote-rescue-body"):
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
        if methods[i] in ("quote-rescue", "quote-rescue-fuzzy", "split-give"):
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
    for i in range(n):
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
        t = lo_t
        for k, w in zip(members, lens):
            s = t
            t = lo_t + (hi_t - lo_t) * (sum(lens[:members.index(k) + 1]) / total)
            starts[k] = round(s, 3)
            ends[k] = round(t, 3)
            fixed_end[k] = False
            confs[k] = 0.6 if (hi_t - lo_t) <= 60 else 0.4
            methods[k] = "comm-split"
            note(k, f"R7 comm-split [{s:.1f},{t:.1f}]")
            if (hi_t - lo_t) > 60:
                need_human.append(k)
        # 外層迴圈跳過已處理成員：標記即可（ends 已有寬，迴圈條件自動跳過）

    # -- R5：鏈（尊重 end_fixed；zero 重壓） --
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
        if starts[i] < last_t - 1e-9:
            starts[i] = round(last_t, 3)
            note(i, "R5 clamped nonmonotonic")
        if ends[i] is None or ends[i] < starts[i]:
            ends[i] = starts[i]
        last_t = ends[i] if fixed_end[i] else max(last_t, ends[i])
        if not fixed_end[i]:
            last_t = ends[i]
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
                           "echo-zero"):
            reasons.append(methods[i])
        if methods[i] in ("quote-rescue-fuzzy", "quote-rescue-body",
                           "quote-rescue") and confs[i] < 0.8:
            reasons.append(f"{methods[i]}:verify-by-ear")
        if confs[i] < 0.5:
            reasons.append(f"low-conf={confs[i]}")
        if methods[i] in ("quote-skip", "skipped-sutra", "block-zero") \
                and cls_list[i] == "SUTRA" and 4 <= len(norm_para(p["text"])) <= SHORT_Q:
            # 短引文判不念：人工複核 objection 權（微讀無法自動驗證）
            reasons.append("skip-quote:verify-by-ear")
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
        for p, s, e, c, m in zip(lec["paragraphs"], starts, ends, confs, methods):
            p["start"], p["end"], p["conf"], p["method"] = \
                round(s, 3), round(e, 3), c, m
            if s == e:
                # zero 標記：沿用 UI 語義（師父沒念）
                if m in ("block-zero", "quote-skip", "skipped-sutra",
                         "echo-zero", "subsumed-dup", "rescue-blocked"):
                    p["zero"] = True
                elif "zero" in p:
                    del p["zero"]
            elif "zero" in p:
                del p["zero"]
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
