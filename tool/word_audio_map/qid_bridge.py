#!/usr/bin/env python3
"""Phase 4 — bridge thematic question_ids to chronological docx blocks.

Reads  build/questions.json (thematic ebook source of truth)
       build/session_alignment.json
Writes build/qid_bridge.json + build/bridge_conflicts.md

Matching: cleaned-nickname equality inside a date window is the primary key;
pinyin LCB similarity of answer texts verifies. One-to-one greedy assignment
by score. Residual (no usable name / low sim) falls back to text-only search.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

TOOL = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL))
sys.path.insert(0, str(TOOL.parent / "pdf_audio_map"))

from wcommon import get_converter, py_norm  # noqa: E402
from word_align import usable_name  # noqa: E402
from wcommon import BUILD_DIR  # noqa: E402

WIN_BEFORE_DAYS = 2      # question may be answered slightly "before" its stamp
WIN_AFTER_DAYS = 75      # hard outer bound (rest months)
HEAD = 70


def lcb_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    m = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(
        0, len(a), 0, len(b))
    return m.size / max(1, min(len(a), len(b)))


import re as _re
_EMOJI_RE = _re.compile(r"[^\w\u4e00-\u9fff\u3400-\u4dbf]+")


def name_key(name: str) -> str:
    n = _EMOJI_RE.sub("", usable_name(name) or "").strip().lower()
    return n


_name_sm_cache: dict = {}


def names_close(a: str, b: str) -> bool:
    ka, kb = name_key(a), name_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    if SequenceMatcher(None, ka, kb).ratio() >= 0.86:
        return True
    # homophone-tolerant: 作了便放下 == 做了便放下
    pa, pb = py_norm(ka, None), py_norm(kb, None)
    if pa and pa == pb:
        return True
    return len(pa) >= 4 and SequenceMatcher(None, pa, pb).ratio() >= 0.9


def main():
    conv = get_converter()
    questions = json.loads((TOOL / "build" / "questions.json").read_text())
    align = json.loads((TOOL / "build" / "session_alignment.json").read_text())

    # ---- flatten chrono blocks -------------------------------------------
    blocks = []
    for date, e in align.items():
        for pi, part in enumerate(e.get("parts", [])):
            for s in part["segments"]:
                blocks.append({
                    "date": date,
                    "sid": part["session_id"],
                    "seq": s["seq"],
                    "asker": s["asker"],
                    "q": py_norm((s.get("q_text") or "")[:400], conv),
                    "a": py_norm((s.get("a_text") or "")[:400], conv),
                    "status": s["status"],
                })
    blocks.sort(key=lambda b: b["date"])

    # index blocks by normalized asker
    by_name = defaultdict(list)
    for bi, b in enumerate(blocks):
        k = name_key(b["asker"])
        if k:
            by_name[k].append(bi)

    import datetime as dt

    def win_block_indices(qdate: str):
        d0 = dt.date.fromisoformat(qdate)
        lo = (d0 - dt.timedelta(days=WIN_BEFORE_DAYS)).isoformat()
        hi = (d0 + dt.timedelta(days=WIN_AFTER_DAYS)).isoformat()
        out = []
        for bi, b in enumerate(blocks):
            if lo <= b["date"] <= hi:
                out.append(bi)
        return out

    candlists = []       # per question: list of (score, bi)
    unresolved = []
    import datetime as dt
    dt_lo_all = "0000-00-00"

    for qi, q in enumerate(questions):
        qdate = q.get("date")
        qa = py_norm((q.get("a_text") or "")[:400], conv)
        qq = py_norm((q.get("q_text") or "")[:300], conv)
        qa_head, qq_head = qa[:HEAD], qq[:HEAD]
        cname = q.get("questioner") or ""
        nk = name_key(cname)

        def scan(pool, name_weight=0.6):
            scored = []
            for bi in pool:
                b = blocks[bi]
                s = lcb_ratio(qa_head, b["a"][:HEAD]) * 1.0 \
                    + lcb_ratio(qq_head, b["q"][:HEAD]) * 0.4 \
                    + (name_weight if nk and names_close(cname, b["asker"]) else 0.0)
                scored.append((round(s, 3), bi))
            scored.sort(key=lambda t: -t[0])
            return scored

        cl = []
        if qdate:
            idxs = win_block_indices(qdate)
            pool = [bi for bi in idxs if names_close(cname, blocks[bi]["asker"])] \
                if nk else idxs
            if not pool:
                pool = idxs
            cl = scan(pool)
        candlists.append(cl[:8])

    # multi-round one-to-one assignment
    bridge = {}
    used_q, used_b = set(), set()
    conflicts = 0

    def try_assign(qi, bi, sc):
        qid = questions[qi]["question_id"]
        b = blocks[bi]
        bridge[qid] = {
            "session_id": b["sid"],
            "session_date": b["date"],
            "block_seq": b["seq"],
            "block_status": b["status"],
            "score": round(sc, 3),
        }

    all_edges = [(sc, qi, ci, cl[ci][1]) for qi, cl in enumerate(candlists)
                 for ci, (sc, bi) in enumerate(cl)]
    all_edges.sort(key=lambda t: -t[0])
    dup_dropped = 0
    for sc, qi, ci, bi in all_edges:
        if qi in used_q or bi in used_b:
            dup_dropped += 1
            continue
        nk = name_key(questions[qi].get("questioner") or "")
        ok = (nk and sc >= 0.7) or sc >= 1.25
        if not ok:
            continue
        used_q.add(qi); used_b.add(bi)
        try_assign(qi, bi, sc)

    # round 2: lazy extended-window / global-text search for the stubborn few
    import datetime as dt
    for qi in list(unresolved_order := [qi for qi in range(len(questions))
                                        if qi not in used_q]):
        q = questions[qi]
        qdate = q.get("date")
        qa_head = py_norm((q.get("a_text") or "")[:400], conv)[:HEAD]
        qq_head = py_norm((q.get("q_text") or "")[:300], conv)[:HEAD]
        cname = q.get("questioner") or ""
        nk = name_key(cname)

        def scan2(pool, nw):
            scored = []
            for bi in pool:
                b = blocks[bi]
                sc2 = lcb_ratio(qa_head, b["a"][:HEAD]) \
                    + lcb_ratio(qq_head, b["q"][:HEAD]) * 0.4 \
                    + (nw if nk and names_close(cname, b["asker"]) else 0.0)
                scored.append((round(sc2, 3), bi))
            scored.sort(key=lambda t: -t[0])
            return scored

        got = None
        if qdate:
            d0 = dt.date.fromisoformat(qdate)
            lo = (d0 - dt.timedelta(days=WIN_BEFORE_DAYS)).isoformat()
            hi = (d0 + dt.timedelta(days=WIN_AFTER_DAYS + 55)).isoformat()
            pool = [bi for bi, b in enumerate(blocks) if lo <= b["date"] <= hi]
            top = scan2(pool, 0.6)[:4]
            for sc2, bi in top:
                if sc2 >= 0.95 and bi not in used_b:
                    got = (sc2, bi); break
        else:
            pool = ([bi for bi, b in enumerate(blocks)
                     if nk and names_close(cname, b["asker"])]
                    if nk else None)
            if pool is None:
                pool = range(len(blocks))
            top = scan2(pool, 0.3)[:4]
            for sc2, bi in top:
                if sc2 >= 1.05 and bi not in used_b:
                    got = (sc2, bi); break
        if got:
            used_q.add(qi); used_b.add(got[1])
            try_assign(qi, got[1], got[0])

    # round 3: relax threshold for still-unassigned with free candidates
    for qi, cl in enumerate(candlists):
        if qi in used_q:
            continue
        for sc, bi in cl:
            if bi in used_b:
                continue
            nk = name_key(questions[qi].get("questioner") or "")
            if (nk and sc >= 0.55) or sc >= 1.0:
                used_q.add(qi); used_b.add(bi)
                try_assign(qi, bi, sc)
                break

    unresolved = [qi for qi in range(len(questions)) if qi not in used_q]
    unresolved_scores = {qi: (candlists[qi][0][0] if candlists[qi] else -1)
                         for qi in unresolved}

    n_total = len(questions)
    n_dated = sum(1 for q in questions if q.get("date"))
    BUILD_DIR.mkdir(exist_ok=True)
    (BUILD_DIR / "qid_bridge.json").write_text(
        json.dumps({"bridge": bridge}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    lines = [
        "# qid_bridge 衝突報告",
        "",
        f"- 題目總數：{n_total}（有日期 {n_dated}）；橋接成功：**{len(bridge)}**"
        f"（{len(bridge)/n_total*100:.1f}%）",
        f"- 未橋接：{n_total - len(bridge)}；因重複衝突捨棄的邊：{dup_dropped}",
        "",
        "## 未橋接樣本（前 25）",
    ]
    for qi in unresolved[:25]:
        q = questions[qi]
        sc = unresolved_scores.get(qi, -1)
        lines.append(f"- [{sc:.2f}] {qid_s(q)} {q.get('questioner')!r} "
                     f"date={q.get('date')} a={(q.get('a_text') or '')[:36]!r}")
    (BUILD_DIR / "bridge_conflicts.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"bridged={len(bridge)}/{n_total} ({len(bridge)/n_total*100:.1f}%)")
    gate = len(bridge) / n_total >= 0.92
    print("GATE:", "PASS" if gate else "FAIL")
    return 0 if gate else 1


def qid_s(q):
    return q.get("question_id", "?")[-8:]


if __name__ == "__main__":
    sys.exit(main())
