#!/usr/bin/env python3
"""Phase 2 — assign each chrono chapter's QA blocks to same-day SRT session(s).

Reads  build/chrono_sessions.json
Uses   wcommon.inventory_sessions() + pdf_audio_map.common.match_ordered
Writes build/session_assignment.json + build/session_assignment_report.md

Dual/multi-file days (公众号+贴吧, 上/下) are split by content: every block is
matched independently against each candidate stream (ordered fuzzy match on
pinyin cues), then monotone split points maximise coverage, guided by the
spoken-transition source order when available.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from itertools import permutations
from pathlib import Path

TOOL = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL))
sys.path.insert(0, str(TOOL.parent / "pdf_audio_map"))

from wcommon import inventory_sessions, get_converter, py_norm, StreamCache, BUILD_DIR  # noqa: E402
from mono_probe import StreamIndex, make_probes, locate_dp  # noqa: E402

SRC_RE = re.compile(r"(微信公眾號|公眾號|貼吧|贴吧)")


def src_slug(word: str) -> str:
    return "tieba" if word in ("貼吧", "贴吧") else "wechat"


def anchor_text(block: dict) -> str:
    t = (block.get("a_text") or "").strip()
    if len(t) < 12:
        t = (t + " " + (block.get("q_text") or "").strip()).strip()
    return t[:70]


def transition_source_order(transitions: list) -> list:
    """['tieba','wechat'] if spoken transitions mention sources in that order."""
    order = []
    for t in transitions or []:
        for m in SRC_RE.findall(t):
            s = src_slug(m)
            if not order or order[-1] != s:
                order.append(s)
    return order


def split_two(cover_a: list, cover_b: list):
    """Best split k: A takes blocks <k, B takes >=k (monotone by construction).

    cover_x[i] = matched cue index or None. Returns (k, matched_count)."""
    n = len(cover_a)
    pa = [0] * (n + 1)
    pb = [0] * (n + 1)
    for i in range(n):
        pa[i + 1] = pa[i] + (1 if cover_a[i] is not None else 0)
        pb[i + 1] = pb[i] + (1 if cover_b[i] is not None else 0)
    best_k, best_s = 0, -1
    for k in range(n + 1):
        s = pa[k] + (pb[n] - pb[k])
        if s > best_s:
            best_k, best_s = k, s
    return best_k, best_s


def merge_any(covs: list) -> list:
    """Element-wise 'first non-None' merge of cover lists."""
    n = max((len(c) for c in covs), default=0)
    return [next((c[i] for c in covs if i < len(c) and c[i] is not None), None)
            for i in range(n)]


def main():
    conv = get_converter()
    streams = StreamCache(conv)
    chrono = json.loads((BUILD_DIR / "chrono_sessions.json").read_text())
    sessions = inventory_sessions()
    by_date = defaultdict(list)
    for s in sessions:
        by_date[s["date"]].append(s)

    out = {}
    n_missing = n_multi = n_single = 0

    for ch in chrono["chapters"]:
        date = ch["session_date"]
        blocks = ch["blocks"]
        entry = {"status": "ok", "blocks_total": len(blocks), "parts": [],
                 "order_method": None}
        if ch["genre"] == "chat-log":
            entry["status"] = "skipped_chatlog"
            out[date] = entry
            continue
        if not blocks:
            entry["status"] = "no_blocks"
            out[date] = entry
            continue
        cands = by_date.get(date, [])
        if not cands:
            entry["status"] = "missing_audio"
            out[date] = entry
            n_missing += 1
            continue

        probes_per_block = [make_probes(b, conv) for b in blocks]
        meta = [b.get("asker_raw") or "" for b in blocks]

        def covers_for(sess):
            idx = StreamIndex(sess["srt_file"], streams)
            res = locate_dp(idx, probes_per_block, conv, meta)
            return [r["pos"] for r in res]

        if len(cands) == 1:
            cov = covers_for(cands[0])
            entry["parts"].append({
                "session_id": cands[0]["session_id"],
                "srt_file": cands[0]["srt_file"],
                "audio_file": cands[0]["audio_file"],
                "source": cands[0]["source"],
                "block_seq_range": [1, len(blocks)],
                "matched": sum(1 for x in cov if x is not None),
            })
            entry["order_method"] = "single"
            n_single += 1
        else:
            n_multi += 1
            hint = transition_source_order(ch.get("transitions"))
            slug_of = [c["source"] for c in cands]
            orders = []
            if len(set(hint)) >= 2 and set(hint) == set(slug_of):
                want = {s: i for i, s in enumerate(hint)}
                idx_order = tuple(sorted(range(len(cands)), key=lambda i: want[slug_of[i]]))
                orders.append(idx_order)
            for p in permutations(range(len(cands))):
                if p not in orders:
                    orders.append(p)

            covers = {i: covers_for(cands[i]) for i in range(len(cands))}
            best = None
            for order in orders:
                if len(order) == 2:
                    k, sc = split_two(covers[order[0]], covers[order[1]])
                    cand = (sc, order, [k])
                else:
                    cov0, rest = covers[order[0]], [covers[i] for i in order[1:]]
                    k1, s1 = split_two(cov0, merge_any(rest))
                    sub = [c[k1:] for c in rest]
                    k2, s2 = split_two(sub[0], merge_any(sub[1:])) if len(sub) > 1 \
                        else (len(blocks) - k1, 0)
                    cand = (s1 + s2, order, [k1, k1 + k2])
                if best is None or cand[0] > best[0]:
                    best = cand
            sc, order, ks = best
            bounds = [0] + list(ks) + [len(blocks)]
            hinted = orders[0] if (hint and len(set(hint)) >= 2
                                   and set(hint) == set(slug_of)) else None
            entry["order_method"] = "transition" if order == hinted else "content"
            for seg_i in range(len(order)):
                lo, hi = bounds[seg_i], bounds[seg_i + 1]
                if hi <= lo:
                    continue
                c = cands[order[seg_i]]
                cov = covers[order[seg_i]][lo:hi]
                entry["parts"].append({
                    "session_id": c["session_id"],
                    "srt_file": c["srt_file"],
                    "audio_file": c["audio_file"],
                    "source": c["source"],
                    "block_seq_range": [lo + 1, hi],
                    "matched": sum(1 for x in cov if x is not None),
                })
        out[date] = entry

    BUILD_DIR.mkdir(exist_ok=True)
    (BUILD_DIR / "session_assignment.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = [d for d, e in out.items() if e["status"] == "ok"]
    weak = []
    for d, e in sorted(out.items()):
        tot = e.get("blocks_total", 0)
        m = sum(p.get("matched", 0) for p in e.get("parts", []))
        if e["status"] == "ok" and tot and m / tot < 0.6:
            weak.append((d, m, tot))
    report = [
        "# session_assignment 報告",
        "",
        f"- ok：{len(ok)} 章（單檔 {n_single}、多檔 {n_multi}）；缺音頻：{n_missing}",
        f"- 低覆蓋（<60%）：{weak if weak else '無'}",
        "",
        "| 日期 | 狀態 | 切分 | parts |",
        "|---|---|---|---|",
    ]
    for d, e in sorted(out.items()):
        ps = "; ".join(
            f"{p['session_id']}[{p['block_seq_range'][0]}-{p['block_seq_range'][1]}]"
            f"({p.get('matched', 0)})" for p in e.get("parts", [])) or "-"
        report.append(f"| {d} | {e['status']} | {e.get('order_method') or '-'} | {ps} |")
    (BUILD_DIR / "session_assignment_report.md").write_text("\n".join(report), encoding="utf-8")

    print(f"ok={len(ok)} single={n_single} multi={n_multi} missing={n_missing}")
    print("weak:", weak[:8])
    gate = len(ok) >= 124 and not weak
    print("GATE:", "PASS" if gate else "FAIL")
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
