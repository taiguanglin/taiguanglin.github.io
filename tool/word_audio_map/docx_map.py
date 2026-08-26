#!/usr/bin/env python3
"""PLAN v2 / R1 — bind every chrono-docx block to audio and emit D1.

Binding : per chapter, vote every block across candidate sessions inside a
          ±14/21-day window; majority-smooth into chronological runs (a chapter
          may legitimately span several days, e.g. early Feb 2024).
Locating: locate_dp (monotone DP, raw LCB>=12) inside each run's stream.
Onset   : spoken 「下一个问题」 marker (char-interpolated) > name anchor >
          content-head; adaptive lead-in; chained ends; closing detection.
Quality : coverage = fraction of the block's own pinyin chars actually matched
          inside its final [start,end] window (union of probe matches),
          plus `named` consensus. status auto/weak/review.

Output  : build/docx_audio_map.json (D1) + build/docx_audio_report.md
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from bisect import bisect_right
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

TOOL = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL))
sys.path.insert(0, str(TOOL.parent / "pdf_audio_map"))

from wcommon import inventory_sessions, get_converter, py_norm, StreamCache, BUILD_DIR  # noqa: E402
from common import fmt_tc, spoken_name_variants  # noqa: E402
from realign_half_second import start_from_onset, find_xia_time_in_cue  # noqa: E402
from mono_probe import StreamIndex, locate_dp  # noqa: E402
from mono_align import name_anchor_pos, closing_start, srt_preview  # noqa: E402
from mono_align import name_anchor_pos, closing_start  # noqa: E402

WIN_BEFORE, WIN_AFTER = 14, 21
MIN_RUN_BLOCKS = 2


# ---------------------------------------------------------------- probes ----
def probes_full(block: dict, conv):
    """[(probe, offset_in_primary, kind)], primary pinyin, and denominators."""
    a = block.get("a_text") or ""
    q = block.get("q_text") or ""
    pa, pq = py_norm(a, conv), py_norm(q, conv)
    out, seen = [], set()

    def add(p, off, kind):
        if len(p) >= 6 and p not in seen:
            seen.add(p)
            out.append((p, off, kind))

    if len(pa) >= 8:
        add(pa[:32], 0, "a")
        if len(pa) >= 64:
            add(pa[-32:], len(pa) - 32, "a")
    if len(pq) >= 8:
        add(pq[:26], 0, "q")
    return out, pa, pq


def primary_text(block, conv):
    a = block.get("a_text") or ""
    if len(py_norm(a, conv)) >= 8:
        return py_norm(a, conv)
    return py_norm(block.get("q_text") or "", conv)


# ------------------------------------------------------------- binding ------
def vote_binding(ch, cands, streams, conv):
    """Return runs [{sid, srt_file, audio_file, date, idx:[block_i]}] in docx
    order with non-decreasing session dates."""
    blocks = ch["blocks"]
    idxs = {s["session_id"]: StreamIndex(s["srt_file"], streams) for s in cands}
    probes_all = [probes_full(b, conv)[0] for b in blocks]
    meta = [b.get("asker_raw") or "" for b in blocks]

    def named_near(idx, asker, hint):
        S_len = len(idx.S)
        if not asker or not (2 <= len(asker) <= 25):
            return False
        for v in spoken_name_variants(asker, None):
            pv = py_norm(v, conv)
            if len(pv) < 3:
                continue
            m = idx.sm(pv)
            lo, hi = max(0, hint - 70), min(S_len, hint + len(pv) + 90)
            if m.find_longest_match(0, len(pv), lo, hi).size >= max(3, len(pv) - 2):
                return True
        return False

    votes = []
    for bi in range(len(blocks)):
        best = (-1.0, None)
        for sid, idx in idxs.items():
            top = 0.0
            for p, _off, _k in probes_all[bi]:
                if not p:
                    continue
                mb = idx.sm(p).find_longest_match(0, len(p), 0, len(idx.S))
                if mb.size > top:
                    top = mb.size
                    bpos = mb.b
            if top > 0 and named_near(idx, meta[bi], bpos):
                top += 6
            if top > best[0]:
                best = (top, sid)
        votes.append(best)

    smoothed = votes[:]
    for i in range(len(votes)):
        win = [v[1] for v in votes[max(0, i - 1):i + 2] if v[1]]
        if len(win) >= 2:
            c = max(set(win), key=win.count)
            if win.count(c) >= 2:
                smoothed[i] = (votes[i][0], c)

    runs = []
    for bi, (_, sid) in enumerate(smoothed):
        if sid is None:
            continue
        if runs and runs[-1]["sid"] == sid:
            runs[-1]["idx"].append(bi)
        else:
            runs.append({"sid": sid, "idx": [bi]})
    # drop micro-runs (<2) into predecessor when possible
    cleaned = []
    for r in runs:
        if len(r["idx"]) < MIN_RUN_BLOCKS and cleaned:
            cleaned[-1]["idx"].extend(r["idx"])
        else:
            cleaned.append(r)
    date_of = {s["session_id"]: s["date"] for s in cands}
    sess_of = {s["session_id"]: s for s in cands}
    # enforce chronological order: bubble a run earlier-date than predecessor
    changed = True
    while changed:
        changed = False
        for k in range(len(cleaned) - 1):
            d0 = date_of[cleaned[k]["sid"]]
            d1 = date_of[cleaned[k + 1]["sid"]]
            if d1 < d0:
                cleaned[k], cleaned[k + 1] = cleaned[k + 1], cleaned[k]
                changed = True
    out = []
    for r in cleaned:
        s = sess_of[r["sid"]]
        out.append({"sid": s["session_id"], "date": s["date"],
                    "srt_file": s["srt_file"], "audio_file": s["audio_file"],
                    "source": s["source"], "idx": r["idx"]})
    return out


# ------------------------------------------------------------ coverage ------
class TimeChars:
    """cue-time <-> pinyin-char span helpers for one stream."""

    def __init__(self, ss):
        self.ss = ss
        self.starts = [c[0] for c in ss.cues]

    def char_span(self, t0: float, t1: float):
        ss = self.ss
        i0 = max(0, bisect_right(self.starts, t0) - 1)
        i1 = min(len(ss.cues) - 1, bisect_right(self.starts, t1) - 1)
        if i1 < i0:
            i1 = i0
        c0 = ss.cue_spans[i0][0]
        c1 = ss.cue_spans[i1][0] + ss.cue_spans[i1][1]
        return c0, max(c1, c0)


def measure(idx: StreamIndex, tc: TimeChars, probe_info, prim_len: int,
            t0: float, t1: float):
    """(coverage, lcb_win): union of probe matches (STREAM coords) inside the
    time window, plus the longest single-probe match inside it."""
    c0, c1 = tc.char_span(t0, t1)
    if c1 <= c0:
        return 0.0, 0
    ivs = []
    lcb_win = 0
    for p, _off, kind in probe_info:
        if kind != "a" or not p:
            continue
        m = idx.sm(p)
        for mb in m.get_matching_blocks():
            if mb.size == 0:
                continue
            if mb.b >= c0 and mb.b + mb.size <= c1:
                lcb_win = max(lcb_win, mb.size)
            s0, s1 = max(mb.b, c0), min(mb.b + mb.size, c1)
            if s1 > s0:
                ivs.append((s0, s1))
    if not ivs:
        return 0.0, lcb_win
    ivs.sort()
    tot = 0
    cs_, ce_ = ivs[0]
    for s0, s1 in ivs[1:]:
        if s0 > ce_:
            tot += ce_ - cs_
            cs_, ce_ = s0, s1
        else:
            ce_ = max(ce_, s1)
    tot += ce_ - cs_
    return min(1.0, tot / prim_len), lcb_win


# ---------------------------------------------------------------- main ------
_G = {}

def _init_worker():
    conv = get_converter()
    _G["conv"] = conv
    _G["streams"] = StreamCache(conv)
    _G["sessions"] = sorted(inventory_sessions(),
                            key=lambda x: (x["date"], x["session_id"]))


def process_chapter(ch):
    """Per-chapter worker -> (date, entry, counters, order_viol)."""
    conv = _G["conv"]; streams = _G["streams"]
    sessions = _G["sessions"]
    date = ch["session_date"]
    blocks = ch["blocks"]
    entry = {"chapter_title": ch["title"], "genre": ch["genre"],
             "n_blocks": len(blocks), "runs": []}
    cnt = [0, 0, 0, 0, 0]          # blocks, anchored, auto, weak, review
    ovio = []
    if ch["genre"] != "qa" or not blocks:
        return date, entry, cnt, ovio
    d0 = dt.date.fromisoformat(date)
    lo = (d0 - dt.timedelta(days=WIN_BEFORE)).isoformat()
    hi = (d0 + dt.timedelta(days=WIN_AFTER)).isoformat()
    cands = [s for s in sessions if lo <= s["date"] <= hi]
    if not cands:
        entry["status"] = "missing_audio"
        return date, entry, cnt, ovio
    runs = vote_binding(ch, cands, streams, conv)
    prev_date = None
    for r in runs:
        if prev_date and r["date"] < prev_date:
            ovio.append((date, r["sid"]))
        prev_date = r["date"]

    n_auto = n_weak = n_rev = n_anchor = 0
    for r in runs:
        rb = [blocks[i] for i in r["idx"]]
        rmeta = [b.get("asker_raw") or "" for b in rb]
        pinfo = [probes_full(b, conv) for b in rb]
        idx = StreamIndex(r["srt_file"], streams)
        tc = TimeChars(idx.ss)
        located = locate_dp(
            idx, [[p for p, _o, _k in pi[0]] for pi in pinfo], conv, rmeta)
        segs = []
        prev_end = 0.0
        anchored_positions = []   # (rb_index, segs_index)
        for bi2, (b, loc) in enumerate(zip(rb, located)):
            seg = {"seq": b["seq"], "asker": b["asker_raw"],
                   "q": (b.get("q_text") or "")[:60], "pos": loc["pos"]}
            if loc["pos"] is None:
                seg.update(status="review", reason="no-anchor",
                           coverage=0.0, named=False)
                segs.append(seg); n_rev += 1
                continue
            npos = name_anchor_pos(idx, rmeta[bi2], loc["pos"], conv)
            anchor_pos = npos if npos is not None else loc["pos"]
            t_content = idx.ss.frac_time(anchor_pos)
            marker_t = None
            lo_t, hi_t = prev_end, t_content + 3.0
            for cst, cen, body in reversed(idx.ss.raw_cues):
                if cst < lo_t:
                    break
                if cen <= hi_t and body:
                    mt = find_xia_time_in_cue(cst, cen, body)
                    if mt is not None and lo_t - 0.01 <= mt <= hi_t:
                        marker_t = mt
                        break
            onset = marker_t if marker_t is not None else t_content
            start, lead, _gap = start_from_onset(onset, idx.ss.raw_cues, floor=0.0)
            start = round(max(start, prev_end), 3)
            named = npos is not None
            seg.update(start=start, named=named,
                       marker=marker_t is not None, lead=round(lead, 3))
            segs.append(seg)
            anchored_positions.append((bi2, len(segs) - 1))
            prev_end = start
            n_anchor += 1
        cs = closing_start(idx.ss)
        tail = cs if cs else idx.ss.audio_end
        ai = anchored_positions
        for j, (bi_a, li) in enumerate(ai):
            sg = segs[li]
            if j + 1 < len(ai):
                sg["end"] = segs[ai[j + 1][1]]["start"]
            else:
                sg["end"] = round(max(tail, sg["start"] + 5.0), 3)
                sg["closing"] = bool(cs)
        for bi_a, li in ai:
            sg = segs[li]
            k = bi_a
            pi, pa, pq = pinfo[k]
            prim = pa if len(pa) >= 8 else pq
            # global best raw match size for this block (self-referential base)
            gmax = 0
            for pr, _o, kd in pi:
                if not pr:
                    continue
                mb = idx.sm(pr).find_longest_match(0, len(pr), 0, len(idx.S))
                gmax = max(gmax, mb.size)
            cov, lcbw = measure(idx, tc, pi, len(prim),
                                sg["start"], sg["end"])
            rr = lcbw / gmax if gmax else 0.0
            sg["coverage"] = round(cov, 3)
            sg["r"] = round(rr, 3)
            sg["lcb_win"] = lcbw
            has_id = bool(sg["named"]) or bool(sg.get("marker"))
            sg["confidence"] = round(min(0.99, rr * 0.70 + cov * 0.20 +
                                         (0.10 if has_id else 0.0)), 3)
            if rr >= 0.75 and (has_id or cov >= 0.30):
                sg["status"] = "auto"; n_auto += 1
            elif rr >= 0.45 or cov >= 0.20:
                sg["status"] = "weak"; n_weak += 1
            else:
                sg["status"] = "review"; sg["reason"] = "low-evidence"; n_rev += 1
            sg["method"] = (f"docx1(marker={int(sg.get('marker', False))},"
                            f"named={int(sg['named'])},r={sg['r']},cov={sg['coverage']})")
            sg.pop("pos", None)
            sg["start_label"] = fmt_tc(sg["start"])
            sg["end_label"] = fmt_tc(sg["end"]) if sg.get("end") else None
            sg["srt_preview"] = srt_preview(idx.ss, sg["start"],
                                            sg.get("end") or sg["start"] + 60)
        r_out = {k: r[k] for k in ("sid", "date", "srt_file", "audio_file", "source")}
        r_out["segments"] = segs
        entry["runs"].append(r_out)
    entry["anchored"] = n_anchor
    entry["auto"] = n_auto
    entry["weak"] = n_weak
    entry["review"] = n_rev
    cnt = [len(blocks), n_anchor, n_auto, n_weak, n_rev]
    return date, entry, cnt, ovio


def main():
    chrono = json.loads((BUILD_DIR / "chrono_sessions.json").read_text())
    chapters = [c for c in chrono["chapters"]]
    D1 = {}
    tot_blocks = anchored = auto_n = weak_n = rev_n = 0
    order_viol = []

    nproc = max(4, (__import__("os").cpu_count() or 4) - 1)
    with Pool(nproc, initializer=_init_worker) as pool:
        results = pool.imap_unordered(process_chapter, chapters, chunksize=1)
        done = 0
        for date, entry, cnt, ovio in results:
            D1[date] = entry
            tot_blocks += cnt[0]; anchored += cnt[1]
            auto_n += cnt[2]; weak_n += cnt[3]; rev_n += cnt[4]
            order_viol += ovio
            done += 1
            if done % 16 == 0:
                print(f"  ... {done}/{len(chapters)} chapters", flush=True)

    BUILD_DIR.mkdir(exist_ok=True)
    (BUILD_DIR / "docx_audio_map.json").write_text(
        json.dumps(D1, ensure_ascii=False, indent=1), encoding="utf-8")
    rate = anchored / max(tot_blocks, 1)
    rep = ["# docx_audio_map 報告（D1）", "",
           f"- 塊總數：{tot_blocks}；錨定：{anchored}（{rate*100:.1f}%）",
           f"- auto：{auto_n}；weak：{weak_n}；review：{rev_n}",
           f"- runs 時序違例：{order_viol or '無'}",
           "", "| 日期 | 塊 | 錨定 | auto | weak | review | runs(sids) |",
           "|---|---|---|---|---|---|---|"]
    for date, e in sorted(D1.items()):
        if e["genre"] != "qa":
            continue
        sids = ";".join(r["sid"] for r in e["runs"]) or "-"
        rep.append(f"| {date} | {e['n_blocks']} | {e.get('anchored',0)} | "
                   f"{e.get('auto',0)} | {e.get('weak',0)} | {e.get('review',0)} | {sids} |")
    (BUILD_DIR / "docx_audio_report.md").write_text("\n".join(rep), encoding="utf-8")

    print(f"blocks={tot_blocks} anchored={anchored} ({rate*100:.1f}%) "
          f"auto={auto_n} weak={weak_n} review={rev_n}")
    print("order_viol:", order_viol[:5])
    gate = rate >= 0.90 and not order_viol
    print("GATE:", "PASS" if gate else "FAIL")
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
