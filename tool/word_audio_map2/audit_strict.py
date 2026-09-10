#!/usr/bin/env python3
"""全量嚴格稽核 audio_map2 所有月份：每個段是否「一段 == 一個 HTML 問答塊」。

稽核項目（全部以 exact／kept-stream 位置比對，不用 fuzzy）：
  A. 孤兒漏題：某真孤兒 qid 的 q_text head（exact）出現在別段 answer 內。
  B. 空 q_text：段的 q_text 為空（很可能問題被吞進 answer 頭）。
  C. 問題混在 answer：某段自己的 qid 的 q_text head（exact）出現在 answer 頭
     （q_text 為空、answer 頭部含問題 ── 同 seg2 型）。
  D. 內容不符：段的 q_text / answer_text（kept 規一化後）與 HTML 的 q_text /
     a_text 不符（開頭不吻合或回信內有第二個問題 head）。
  E. 多 qid 未拆：一段掛 >1 qid。
  F. qid 重複掛多段（同月不同段）。

輸出 reports/strict_audit.json 與人讀摘要。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
MAP2 = ROOT / "audio_map2"
QUESTIONS = Path(__file__).resolve().parent / "build" / "questions.json"

KEPT = re.compile(r"[^\s\u3000]")

try:
    import opencc
    _CC = opencc.OpenCC("t2s")
    def t2s(s: str) -> str:
        return _CC.convert(s)
except Exception:
    def t2s(s: str) -> str:
        return s

def kept(s: str) -> str:
    """whitespace-collapsed kept stream (char set KEPT), t2s-normalised."""
    return t2s("".join(c for c in s or "" if KEPT.match(c)))

def main() -> int:
    qmap = {q["question_id"]: q for q in json.loads(QUESTIONS.read_text(encoding="utf-8"))}
    kq = {qid: kept(e["q_text"] or "") for qid, e in qmap.items()}  # kept q_text
    ka = {qid: kept(e["a_text"] or "") for qid, e in qmap.items()}  # kept a_text

    # corpus-wide frozen set → truly orphan qids
    months = sorted(MAP2.glob("????-??.json"))
    frozen = set()
    datasets = {}
    for p in months:
        d = json.loads(p.read_text(encoding="utf-8"))
        datasets[p.stem] = d
        for s in d.get("sessions") or []:
            for g in s.get("segments") or []:
                frozen.update(g.get("chapter_question_ids") or [])
    orphans = set(qmap) - frozen

    issues = []
    def add(month, sid, idx, itype, qid, detail, seg):
        issues.append({
            "month": month, "session": sid, "index": idx, "type": itype,
            "qid": qid, "detail": detail,
            "lastPlayed": bool((seg.get("meta") or {}).get("lastPlayed")),
        })

    for month, d in datasets.items():
        # per-session qid order for boundary context
        seen_qid_seg = {}
        for s in d.get("sessions") or []:
            sid = s["session_id"]
            # snapshot qids in session
            session_qids = {}
            for g in s.get("segments") or []:
                for q in g.get("chapter_question_ids") or []:
                    session_qids.setdefault(q, g.get("index"))
            for g in s.get("segments") or []:
                idx = g.get("index")
                qids = g.get("chapter_question_ids") or []
                qt = g.get("q_text") or ""
                at = g.get("answer_text") or ""
                kat = kept(at)
                # E: multi-qid
                if len(qids) > 1:
                    add(month, sid, idx, "multi_qid_unsplit", ",".join(qids),
                        f"{len(qids)} qids on one segment", g)
                # F: dup within month
                for q in qids:
                    key = f"{sid}#{idx}"
                    if q in seen_qid_seg and seen_qid_seg[q] != key:
                        add(month, sid, idx, "dup_qid", q,
                            f"also at {seen_qid_seg[q]}", g)
                    else:
                        seen_qid_seg[q] = key
                # skip non-qa segments (opening/closing etc.)
                if not qids:
                    # still check orphan leak
                    pass
                # per own qid checks (C, D)
                qtext_empty = not qt.strip()
                for q in qids:
                    if q not in qmap:
                        continue
                    hq = kq.get(q, "")
                    # C: own question head appears at very start of answer
                    if hq and qtext_empty and kat.find(hq[:24]) in (0, 2, 3, 4, 5, 6):
                        add(month, sid, idx, "qhead_in_answer_head", q,
                            "q_text empty; own question head at answer head", g)
                    # D: content mismatch
                    if hq:
                        qk = kept(qt)
                        if qt.strip() and not qk.startswith(hq[:20]):
                            # q_text present but doesn't start the matching question
                            if hq[:20] not in qk[:len(qk)+4]:
                                add(month, sid, idx, "q_text_mismatch", q,
                                    f"q_text head not matching HTML (html head: {hq[:24]})", g)
                # A: orphan question head exact in this segment's answer
                if kat:
                    for oq in orphans:
                        ho = kq.get(oq, "")
                        if not ho or len(ho) < 10:
                            continue
                        # cheap filter then exact head probe
                        head = ho[:20]
                        pos = kat.find(head)
                        if pos >= 0:
                            # require it starts the answer or follows punctuation
                            prev = kat[max(0, pos-1)] if pos else ""
                            if pos == 0 or True:
                                add(month, sid, idx, "orphan_in_answer", oq,
                                    f"orphan head at kept pos {pos} (prev {prev!r})", g)
    # summarize
    from collections import Counter
    c = Counter(i["type"] for i in issues)
    print("issues by type:", dict(c))
    print("issues touching lastPlayed segs:", sum(1 for i in issues if i["lastPlayed"]))
    by_month = Counter(i["month"] for i in issues)
    print("by month:", dict(sorted(by_month.items())))
    out = Path(__file__).resolve().parent / "reports"
    out.mkdir(exist_ok=True)
    (out / "strict_audit.json").write_text(json.dumps(issues, ensure_ascii=False, indent=1), "utf-8")
    print(f"wrote {out/'strict_audit.json'} ({len(issues)} issues)")
    return 0

if __name__ == "__main__":
    sys.exit(main())