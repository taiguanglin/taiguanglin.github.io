#!/usr/bin/env python3
"""Strictly verify that every audio_map2 segment's question text == its HTML
question paragraph and answer text == its HTML answer paragraph (direct HTML
extraction from wenda2_ebook, not questions.json).

Normalization (cosmetic only, never hides structure):
  1. 著 → 着            (ebook uses 著 in verb-suffix position; Word uses 着)
  2. collapse ALL whitespace
  3. halfwidth → fullwidth for , 。 ！ ？ ： ； 、 ( ) % etc.

Each segment is classified:
  - ok                    : q_text & answer_text both == HTML (after norm)
  - multi_qid             : segment carries >1 chapter_question_ids
  - no_qid                : segment has no chapter_question_ids (opening/closing)
  - q_text_diff           : normalized q_text != normalized HTML q_text
  - answer_diff           : normalized answer_text != normalized HTML a_text
  - orphan_qid            : qid absent from HTML extraction (missing answer etc.)

Diffs are reported with a precise description (head/tail mismatch, extra/missing
run, first divergent span) so a human (or a fixer) can act exactly.

Output: reports/verify_strict.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP2 = ROOT / "audio_map2"
TOOL = Path(__file__).resolve().parent
HTML_QA = json.loads((TOOL / "build" / "html_qa_simp.json").read_text(encoding="utf-8"))

HW2FW = str.maketrans({
    ",": "，", ".": "。", "!": "！", "?": "？", ":": "：", ";": "；",
    "(": "（", ")": "）", "[": "【", "]": "】",
})

try:
    from opencc import OpenCC
    _CC = OpenCC("t2s")
except Exception:
    _CC = None


def norm(s: str) -> str:
    if not s:
        return ""
    if _CC is not None:
        s = _CC.convert(s)               # traditional → simplified (禮→礼 etc.)
    s = s.replace("著", "着")            # ebook verb-suffix variant
    s = s.replace("\u200b", "")          # zero-width space (Word artifact)
    s = s.replace("\uFE0F", "").replace("\u20E3", "")  # emoji digit "2️⃣"→"2"
    s = re.sub(r"\s+", "", s)            # collapse all whitespace
    s = s.translate(HW2FW)               # halfwidth punct → fullwidth
    return s


def first_diff(a: str, b: str):
    """Return (a_span, b_span, pos) of first divergence or None if equal."""
    if a == b:
        return None
    i = 0
    n = min(len(a), len(b))
    while i < n and a[i] == b[i]:
        i += 1
    return a[i - 30:i + 40], b[i - 30:i + 40], i


def verify_month(month: str) -> list:
    path = MAP2 / f"{month}.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for sess in d.get("sessions") or []:
        sid = sess["session_id"]
        for g in sess.get("segments") or []:
            idx = g.get("index")
            qids = g.get("chapter_question_ids") or []
            rec = {
                "month": month, "session": sid, "index": idx,
                "qids": qids,
            }
            if len(qids) == 0:
                rec["verdict"] = "no_qid"
            elif len(qids) > 1:
                rec["verdict"] = "multi_qid"
            else:
                qid = qids[0]
                h = HTML_QA.get(qid)
                if not h:
                    rec["verdict"] = "orphan_qid"
                else:
                    qt = norm(g.get("q_text") or "")
                    qt_h = norm(h["q_text"])
                    at = norm(g.get("answer_text") or "")
                    at_h = norm(h["a_text"])
                    q_ok = qt == qt_h
                    a_ok = at == at_h
                    rec["html_answer_id"] = h.get("answer_id")
                    rec["html_id"] = qid
                    if q_ok and a_ok:
                        rec["verdict"] = "ok"
                    else:
                        rec["verdict"] = "Q" if not q_ok else ""
                        rec["verdict"] += "A" if not a_ok else ""
                        rec["verdict"] = f"diff:{rec['verdict']}"
                        if not q_ok:
                            fd = first_diff(qt, qt_h)
                            rec["q_diff"] = {
                                "seg": fd[0], "html": fd[1],
                                "seg_len": len(qt), "html_len": len(qt_h),
                            } if fd else None
                        if not a_ok:
                            fd = first_diff(at, at_h)
                            rec["a_diff"] = {
                                "seg": fd[0], "html": fd[1],
                                "seg_len": len(at), "html_len": len(at_h),
                            } if fd else None
            out.append(rec)
    return out


def main() -> int:
    allrec = []
    months = sorted(p.stem for p in MAP2.glob("????-??.json"))
    for m in months:
        allrec.extend(verify_month(m))
    c = Counter(r["verdict"] for r in allrec)
    print("verdict counts:")
    for k, v in c.most_common():
        print(f"  {k:16s} {v}")
    # structural (non-ok) entries
    bad = [r for r in allrec if r["verdict"] != "ok" and r["verdict"] != "no_qid"]
    print(f"total segments {len(allrec)}, non-ok (excl. no_qid) {len(bad)}")
    out = TOOL / "reports" / "verify_strict.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(allrec, ensure_ascii=False, indent=1), "utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())