#!/usr/bin/env python3
"""Fill the remaining "real-Q&A but unmapped" segments with their classified
(thematic) chapter question.

Policy (per maintainer decision):
  * A classified question that was merged from several numbered sub-questions
    ("1、…2、…3、…") may be referenced by MULTIPLE chronological sub-segments
    (each sub-segment points at the same classified question id).
  * Segments whose question genuinely does not appear in the classified docx
    (off-topic news/chat, or ASR too degraded) stay unmapped.

Matching is q_text-only (never answer_text, which is the false-positive source
that once attached 57 qids to a "感恩师父！" greeting segment):
  1. containment, either direction, with a substantive-length guard so generic
     greetings / bare enumerations don't match everything; and
  2. SequenceMatcher ratio >= CONFIDENCE (default 0.6), also length-guarded.

Dry-run by default (prints every proposed assignment); pass --apply to write.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"
QUESTIONS = ROOT / "tool" / "word_audio_map2" / "build" / "questions.json"

CONFIDENCE = 0.6        # fuzzy ratio threshold for a "good enough" q_text match
MIN_HANZI = 8           # substantive length guard (blocks greetings / enumerations)

LOST_MARKERS = ("问题丢失", "问题未收录", "问题缺失", "未收集", "找不到问题", "以下仅回答")
PLACEHOLDER_HINTS = ("群規", "發帖規範", "收場", "切换", "切換", "师父说", "佔位", "占位",
                     "公告", "開場", "开场", "元說明", "元说明", "closing", "opening", "桥接")


def norm(s: str) -> str:
    s = re.sub(r"_x[0-9A-Fa-f]{4}_", "", s or "")
    return re.sub(r"[^\u4e00-\u9fff\w]", "", s).lower()


def hanzi_count(s: str) -> int:
    return sum(1 for c in norm(s) if "\u4e00" <= c <= "\u9fff")


def load_questions() -> list[dict]:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))


def find_unmapped() -> list[tuple]:
    """Return [(month, session_id, index, q_text, answer_text, notes)] for every
    segment that has a real Q&A but no classified link."""
    out = []
    for path in sorted(AUDIO_MAP2_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for s in data.get("sessions") or []:
            sid = s["session_id"]
            for g in s.get("segments") or []:
                if g.get("chapter_question_ids"):
                    continue
                q = (g.get("q_text") or "").strip()
                a = (g.get("answer_text") or "").strip()
                notes = g.get("notes") or ""
                if len(q) <= 2 or len(a) <= 2:
                    continue
                if any(k in q for k in LOST_MARKERS):
                    continue
                if any(k in notes for k in PLACEHOLDER_HINTS):
                    continue
                out.append((path.stem, sid, g.get("index"), q, a, notes))
    return out


def best_match(q_text: str, questions: list[dict]):
    """Return (question, kind, ratio) for the best classified question, or None.

    kind in {'contain', 'fuzzy'}; containment is preferred over fuzzy.
    """
    nq = norm(q_text)
    hz = hanzi_count(q_text)
    best = None  # (question, kind, ratio)

    for q in questions:
        cq = norm(q.get("q_text") or "")
        if not cq:
            continue
        # containment — guard both sides by substantive length
        if len(nq) >= MIN_HANZI and len(cq) >= MIN_HANZI:
            if nq in cq or cq in nq:
                # prefer the more specific containment (sub-question inside merged q)
                r = SequenceMatcher(None, nq, cq).ratio()
                if best is None or r > best[2]:
                    best = (q, "contain", r)
    # fuzzy
    for q in questions:
        cq = norm(q.get("q_text") or "")
        if not cq:
            continue
        r = SequenceMatcher(None, nq, cq).ratio()
        if r >= CONFIDENCE:
            if best is None or (best[1] == "fuzzy" and r > best[2] and not best[1] == "contain"):
                if best is None or best[1] != "contain":
                    best = (q, "fuzzy", r)
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write links into audio_map2 JSON")
    ap.add_argument("--min-ratio", type=float, default=CONFIDENCE)
    args = ap.parse_args()

    questions = load_questions()
    gaps = find_unmapped()
    print(f"real-Q&A unmapped segments: {len(gaps)}\n")

    proposals = []  # (month, sid, idx, qid, chapter_index, kind, ratio, q_text)
    for month, sid, idx, q_text, a_text, notes in gaps:
        m = best_match(q_text, questions)
        if m is None:
            print(f"[SKIP   ] {month} {sid}#{idx}  (no classified match)  q={q_text[:34]!r}")
            continue
        q, kind, r = m
        proposals.append((month, sid, idx, q["question_id"], q["chapter_index"], kind, r, q_text))
        print(f"[{'APPLY' if args.apply else 'propose'}] {month} {sid}#{idx}  {kind:7} r={r:.2f} -> ch{q['chapter_index']}  {q['question_id']}")
        print(f"          q={q_text[:46]!r}")
        print(f"          classified={q['q_text'][:46]!r}")

    print(f"\nresolvable: {len(proposals)}, left unmapped: {len(gaps) - len(proposals)}")

    if not args.apply:
        print("(dry run — pass --apply to write)")
        return 0

    # group by (month, sid) -> idx -> list[(qid, chapter_index)]
    by_file: dict[str, dict] = {}
    for month, sid, idx, qid, ci, kind, r, _ in proposals:
        key = (sid, idx)
        d = by_file.setdefault(month, {})
        d.setdefault(key, []).append((qid, ci))

    for month, segmap in by_file.items():
        path = AUDIO_MAP2_DIR / f"{month}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        touched = False
        for s in data.get("sessions") or []:
            sid = s["session_id"]
            for g in s.get("segments") or []:
                pairs = segmap.get((sid, g.get("index")))
                if not pairs:
                    continue
                g["chapter_question_ids"] = [q for q, _ in pairs]
                g["chapter_indexes"] = [ci for _, ci in pairs]
                touched = True
        if touched:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {month}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())