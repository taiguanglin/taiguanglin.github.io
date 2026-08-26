#!/usr/bin/env python3
"""Phase 3 — within-session monotone alignment of chrono blocks to audio.

Reads  build/chrono_sessions.json + build/session_assignment.json
Writes build/session_alignment.json     + build/mono_review_report.md

Per session part: DP monotone location (locate_dp) → char positions →
sub-cue times (frac_time) → onset refinement (spoken-name anchor preferred,
adaptive lead-in via realign_half_second.start_from_onset) → chained ends
(end_i = start_{i+1}; last end = closing「…就到这里」start or audio end).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL))
sys.path.insert(0, str(TOOL.parent / "pdf_audio_map"))

from wcommon import inventory_sessions, get_converter, StreamCache, BUILD_DIR, py_norm  # noqa: E402
from common import fmt_tc, spoken_name_variants  # noqa: E402
from realign_half_second import start_from_onset  # noqa: E402
from mono_probe import StreamIndex, make_probes, locate_dp  # noqa: E402

REVIEW_CONF = 0.30
CLOSING_PAT = ("就到这里", "就回答到这里", "答疑就到这里", "今天的回答就到这里")


def conf_from(sc: float) -> float:
    return round(max(0.05, min(0.99, (sc - 6) / 26.0)), 3)


def name_anchor_pos(idx: StreamIndex, asker: str, hint: int, conv):
    """Abs pinyin-stream pos of the spoken asker name near ``hint``, or None."""
    S_len = len(idx.S)
    if not asker or not (2 <= len(asker) <= 25):
        return None
    best = None
    for v in spoken_name_variants(asker, None):
        pv = py_norm(v, conv)
        if len(pv) < 3:
            continue
        m = idx.sm(pv)
        lo, hi = max(0, hint - 70), min(S_len, hint + len(pv) + 90)
        mb = m.find_longest_match(0, len(pv), lo, hi)
        need = max(3, len(pv) - 2)
        if mb.size >= need:
            span_lo = mb.b
            if best is None or span_lo < best:
                best = span_lo
    return best


def closing_start(ss) -> float | None:
    """Start time of the spoken closing line, if present near the end."""
    end = ss.audio_end
    for st, en, body in reversed(ss.cues[-60:] if len(ss.cues) > 60 else ss.cues):
        if st < end - 300:
            break
        compact = (body or "").replace(" ", "")
        if any(p in compact for p in CLOSING_PAT):
            return float(st)
    return None


def srt_preview(ss, start: float, end: float, limit: int = 110) -> str:
    parts = []
    for st, en, body in ss.cues:
        if en <= start:
            continue
        if st >= end:
            break
        parts.append(body)
    text = "".join(parts).replace(" ", "")
    return text[:limit]


def align_part(idx: StreamIndex, blocks: list, conv, meta: list):
    ss = idx.ss
    probes_per_block = [make_probes(b, conv) for b in blocks]
    located = locate_dp(idx, probes_per_block, conv, meta)
    segs = []
    for bi, (b, r) in enumerate(zip(blocks, located)):
        seg = {
            "seq": b["seq"],
            "asker": b["asker_raw"],
            "q_text": b["q_text"],
            "a_text": b["a_text"],
            "pos": r["pos"],
            "lcb": r["lcb"],
        }
        if r["pos"] is None:
            seg.update(status="review", reason="no-anchor",
                       confidence=0.0, named=False)
            segs.append(seg)
            continue
        conf = conf_from(r["lcb"])
        npos = name_anchor_pos(idx, meta[bi], r["pos"], conv)
        anchor_pos = npos if npos is not None else r["pos"]
        onset = ss.frac_time(anchor_pos)
        start, lead, gap = start_from_onset(onset, ss.raw_cues, floor=0.0)
        seg.update(start=round(start, 3), end=None, lead=round(lead, 3),
                   confidence=conf, named=npos is not None,
                   status=("auto" if conf >= REVIEW_CONF else "review"),
                   method=f"mono(dp,lcb={r['lcb']},lead={lead})")
        segs.append(seg)
    # chain ends over anchored segments
    assigned = [s for s in segs if s.get("start") is not None]
    for a, b2 in zip(assigned, assigned[1:]):
        a["end"] = b2["start"]
    if assigned:
        cs = closing_start(ss)
        tail = cs if cs else ss.audio_end
        last = assigned[-1]
        last["end"] = round(max(tail, last["start"] + 5.0), 3)
        last["closing"] = bool(cs)
    # monotonicity clamp (starts must be non-decreasing after lead-ins)
    prev = None
    for s in assigned:
        if prev is not None and s["start"] < prev["start"]:
            s["start"] = prev["start"]
        if s["end"] is not None and s["end"] <= s["start"]:
            s["end"] = None  # will be repaired by next chain pass if needed
        prev = s
    # previews + labels
    for s in assigned:
        s["srt_preview"] = srt_preview(ss, s["start"], s["end"] or s["start"] + 60)
        s["start_label"] = fmt_tc(s["start"])
        s["end_label"] = fmt_tc(s["end"]) if s["end"] is not None else None
    return segs


def _session_window(sess_by_date_sorted, center_date, before=14, after=21):
    import datetime as _dt
    d0 = _dt.date.fromisoformat(center_date)
    lo = (d0 - _dt.timedelta(days=before)).isoformat()
    hi = (d0 + _dt.timedelta(days=after)).isoformat()
    return [s for s in sess_by_date_sorted if lo <= s["date"] <= hi]


def rebind_chapter(ch, cands, streams, conv):
    """Content-vote every block across candidate sessions (date-window), then
    align contiguous same-session runs with DP. Returns (parts, meta_list)."""
    blocks = ch["blocks"]
    probes_per_block = [make_probes(b, conv) for b in blocks]
    idxs = {s["session_id"]: StreamIndex(s["srt_file"], streams) for s in cands}
    ids = [s["session_id"] for s in cands]
    votes = []
    for bi, b in enumerate(blocks):
        best = (-1.0, None)
        for sid, idx in idxs.items():
            for p in probes_per_block[bi]:
                if not p or len(p) < 8:
                    continue
                sm_ = idx.sm(p)
                mb = sm_.find_longest_match(0, len(p), 0, len(idx.S))
                sc = mb.size + (6 if bi < len(blocks) and _named_near(idx, blocks[bi]["asker_raw"], mb.b, conv) else 0)
                if sc > best[0]:
                    best = (sc, sid)
        votes.append(best)
    # majority smoothing (width 3)
    sm_votes = votes[:]
    for i in range(len(votes)):
        win = [v[1] for v in votes[max(0, i - 1):i + 2] if v[1]]
        if win:
            c = max(set(win), key=win.count)
            if win.count(c) >= 2:
                sm_votes[i] = (votes[i][0], c)
    # contiguous runs (chronological order enforced afterwards)
    runs = []
    for i, (_, sid) in enumerate(sm_votes):
        if sid is None:
            continue
        if runs and runs[-1]["sid"] == sid:
            runs[-1]["idx"].append(i)
        else:
            runs.append({"sid": sid, "idx": [i]})
    # drop tiny runs by merging into neighbours (keep >=2 blocks)
    cleaned = []
    for r in runs:
        if len(r["idx"]) < 2 and cleaned and len(cleaned[-1]["idx"]) >= 2:
            cleaned[-1]["idx"].extend(r["idx"])
        else:
            cleaned.append(r)
    # chronological sort of runs
    date_of = {s["session_id"]: s["date"] for s in cands}
    cleaned.sort(key=lambda r: date_of[r["sid"]])
    parts = []
    for r in cleaned:
        sess = next(s for s in cands if s["session_id"] == r["sid"])
        rb = [blocks[i] for i in r["idx"]]
        rmeta = [b.get("asker_raw") or "" for b in rb]
        idx = idxs[r["sid"]]
        segs = align_part(idx, rb, conv, rmeta)
        parts.append({
            "session_id": sess["session_id"],
            "srt_file": sess["srt_file"],
            "audio_file": sess["audio_file"],
            "source": sess["source"],
            "segments": segs,
            "rebound": True,
        })
    return parts


def _named_near(idx, asker, hint, conv):
    if not asker or not (2 <= len(asker) <= 25):
        return False
    S_len = len(idx.S)
    for v in spoken_name_variants(asker, None):
        pv = py_norm(v, conv)
        if len(pv) < 3:
            continue
        m = idx.sm(pv)
        lo, hi = max(0, hint - 70), min(S_len, hint + len(pv) + 90)
        if m.find_longest_match(0, len(pv), lo, hi).size >= max(3, len(pv) - 2):
            return True
    return False


def main():
    conv = get_converter()
    streams = StreamCache(conv)
    chrono = json.loads((BUILD_DIR / "chrono_sessions.json").read_text())
    assign = json.loads((BUILD_DIR / "session_assignment.json").read_text())
    sess_by_id = {s["session_id"]: s for s in inventory_sessions()}
    ch_by_date = {c["session_date"]: c for c in chrono["chapters"]}

    out = {}
    rep_counts = {"auto": 0, "review": 0}
    weak_parts = []

    for date, e in sorted(assign.items()):
        entry = {"status": e["status"], "parts": []}
        if e["status"] != "ok":
            out[date] = entry
            continue
        ch = ch_by_date[date]
        n_blocks_ch = len(ch["blocks"])
        entry["_pre_parts_ratio_check"] = None
        for part in e["parts"]:
            lo, hi = part["block_seq_range"]
            blocks = ch["blocks"][lo - 1:hi]
            sess = sess_by_id[part["session_id"]]
            idx = StreamIndex(sess["srt_file"], streams)
            meta = [b.get("asker_raw") or "" for b in blocks]
            segs = align_part(idx, blocks, conv, meta)
            pass
            entry["parts"].append({
                "session_id": part["session_id"],
                "srt_file": part["srt_file"],
                "audio_file": part["audio_file"],
                "source": part["source"],
                "segments": segs,
            })
        # chapter-level quality check → window rebind fallback
        tot = sum(len(p["segments"]) for p in entry["parts"])
        ok_n = sum(1 for p in entry["parts"] for s in p["segments"]
                   if s["status"] == "auto")
        if tot and ok_n / tot < 0.6:
            cands = _session_window(sorted(inventory_sessions(),
                                           key=lambda x: x["date"]), date)
            if len(cands) >= 1:
                try:
                    rparts = rebind_chapter(ch, cands, streams, conv)
                except Exception as exc:  # noqa
                    rparts = []
                    print(f"[rebind failed {date}] {exc}")
                rtot = sum(len(p["segments"]) for p in rparts)
                rok = sum(1 for p in rparts for s in p["segments"]
                          if s["status"] == "auto")
                if rparts and rok / max(rtot, 1) > ok_n / max(tot, 1):
                    entry["parts"] = rparts
                    entry["order_method"] = "rebound"
        out[date] = entry

    # ---- final stats (post-rebind) ----
    rep_counts = {"auto": 0, "review": 0}
    weak_parts = []
    mono_viol = 0
    date_order_viol = []
    for date, e in out.items():
        prev_date = None
        for p in e.get("parts", []):
            na = sum(1 for sg in p["segments"] if sg["status"] == "auto")
            rep_counts["auto"] += na
            rep_counts["review"] += len(p["segments"]) - na
            if len(p["segments"]) >= 6 and na / len(p["segments"]) < 0.5:
                weak_parts.append((date, p["session_id"], na, len(p["segments"])))
            # monotonic check over anchored segments of this part
            st = [sg["start"] for sg in p["segments"] if sg.get("start") is not None]
            mono_viol += sum(1 for a, b2 in zip(st, st[1:]) if b2 < a)
            sid_date = p["session_id"][:10]
            if prev_date and sid_date < prev_date:
                date_order_viol.append((date, p["session_id"]))
            prev_date = sid_date

    BUILD_DIR.mkdir(exist_ok=True)
    (BUILD_DIR / "session_alignment.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    total = rep_counts["auto"] + rep_counts["review"]
    auto_ratio = rep_counts["auto"] / max(total, 1)
    big_weak = [w for w in weak_parts if w[3] >= 6 and w[2] / w[3] < 0.5]
    lines = [
        "# mono_alignment 報告",
        "",
        f"- 塊總數：{total}；auto：{rep_counts['auto']}；review：{rep_counts['review']}"
        f"（auto 佔 {auto_ratio*100:.1f}%）",
        f"- 單調違例：{mono_viol}；part 日期亂序：{date_order_viol or '無'}",
        f"- 大型低覆蓋 part（≥6塊且<50%）：{big_weak or '無'}",
        f"- 小型低覆蓋（人工關注）：{weak_parts or '無'}",
        "",
    ]
    review_samples = [s for d in out.values() for p in d.get("parts", [])
                      for s in p["segments"] if s["status"] == "review"]
    lines.append(f"## review 樣本（前 15 / 共 {len(review_samples)}）")
    for s in review_samples[:15]:
        lines.append(f"- seq={s['seq']} {s['asker']!r} reason={s.get('reason')} "
                     f"conf={s.get('confidence')} q={(s['q_text'] or '')[:36]!r}")
    (BUILD_DIR / "mono_review_report.md").write_text("\n".join(lines), encoding="utf-8")

    print("auto:", rep_counts["auto"], "review:", rep_counts["review"],
          f"({auto_ratio*100:.1f}%)")
    print("mono_viol:", mono_viol, "| date_order_viol:", len(date_order_viol))
    print("big_weak:", big_weak)
    gate = (not big_weak) and mono_viol == 0 and auto_ratio >= 0.85
    print("GATE:", "PASS" if gate else "FAIL")
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
