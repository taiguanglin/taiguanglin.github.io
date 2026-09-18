#!/usr/bin/env python3
"""One-off surgical fix for audio_map2/2025-05.json, 2025-05-12-tieba segment #74.

The Word chunk glued THREE sub-questions (双盘坐法 1+2 / 天谴怪病 3) into one
segment.  The wenda2_ebook splits the SAME Word question into TWO blocks in
TWO different chapters (the question div id is reused):

  - ch10 (問答收錄) block  question-375dc7c624b1 / answer-4b4ce77a0008
      question = 情况 + 问题 + 子題1 + 子題2
      answer   = 「贴吧用户_JQAEGGy，打坐的问题，我建议你选第二种…」
  - ch02 (修行与坐姿) block question-375dc7c624b1 / answer-1f29232b4fcc
      question = 情况 + 子題3
      answer   = 「那么天谴上天公报…」

Split that segment into two, one per ebook block, slicing the Word text at the
exact ebook block boundaries (question tail 「\\n3、…」 for the question side,
「那么天谴上天公报」 for the answer side).  Each piece carries the same
chapter_question_ids entry (the ebook really reuses the qid) plus its own
chapter_answer_ids; chapter_indexes now point at the block's real chapter.

Times are proportional to kept-text weight (Q+A) like fix_2025_05_17_seg2.py;
both pieces lose meta.lastPlayed (boundaries changed → re-listen; injection is
lastPlayed-gated) and get status=auto / confidence=0.5 / 待人工確認 note.

The whole session is renumbered afterwards (mirror of apply_resplit /
fix_2025_05_17_seg2): index, stable_key, question_id, previews, labels.
Month stats (segments/matched/…) are recomputed like resplit_by_html.py.

Usage:
  .venv/bin/python fix_2025_05_12_seg74.py           # dry-run report
  .venv/bin/python fix_2025_05_12_seg74.py --apply   # write back
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "audio_map2" / "2025-05.json"

SID = "2025-05-12-tieba"
STABLE_KEY = "2025-05-12-tieba#74"

QID = "question-375dc7c624b1"
CH10_AID = "answer-4b4ce77a0008"   # 子題1+2（打坐坐法 / 修復身體）
CH02_AID = "answer-1f29232b4fcc"   # 子題3（天譴怪病 / 發願度眾）

Q_TAIL_ANCHOR = "3、请问这种天谴"       # question side: ch02-only tail starts here
A_SPLIT_ANCHOR = "那么天谴上天公报"     # answer side: ch02 answer head


def fmt_label(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{int(s):02d}.{int(round((s - int(s)) * 1000)):03d}"


def kept_len(s: str) -> int:
    return len(re.findall(r"[^\s\u3000]", s or ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="write the JSON back")
    args = ap.parse_args()

    data = json.loads(MAP.read_text(encoding="utf-8"))
    sess = next(s for s in data["sessions"] if s["session_id"] == SID)
    segs = sess["segments"]
    seg = next(s for s in segs if s.get("stable_key") == STABLE_KEY)
    idx = segs.index(seg)

    q_text = seg["q_text"]
    a_text = seg["answer_text"]

    # --- question slice: ch10 keeps everything before the 「3、」 tail;
    #     ch02 keeps the 情况 paragraph + the 「3、」 tail (matches its block).
    p_tail = q_text.find("\n" + Q_TAIL_ANCHOR)
    assert p_tail > 0, "question tail anchor not found"
    p_para1 = q_text.find("\n")
    assert 0 < p_para1 < p_tail, "unexpected question paragraph layout"
    q_a = q_text[:p_tail]                       # 情况 + 问题 + 1、 + 2、
    q_b = q_text[:p_para1] + "\n" + q_text[p_tail + 1:]  # 情况 + 3、

    # --- answer slice at the ch02 answer head
    p_a = a_text.find(A_SPLIT_ANCHOR)
    assert p_a > 0, "answer split anchor not found"
    a_a = a_text[:p_a].rstrip()
    a_b = a_text[p_a:]
    assert a_a and a_b

    # --- proportional time split by kept-text weight (Q+A per piece)
    w_a = kept_len(q_a) + kept_len(a_a)
    w_b = kept_len(q_b) + kept_len(a_b)
    start, end = seg["start"], seg["end"]
    assert start is not None and end is not None and end > start
    split_t = round(start + (end - start) * w_a / (w_a + w_b), 3)

    note = ("html-resplit: 依 wenda2_ebook 問題邊界重新分段"
            "（切分多題段，同 qid 跨章 blocks 以 chapter_answer_ids 區分），待人工確認")
    meta_kept = {k: v for k, v in (seg.get("meta") or {}).items()
                 if k != "lastPlayed"}

    def piece(q, a, aid, ch, extra_note):
        p = {
            "questioner": seg.get("questioner"),
            "question_time": seg.get("question_time"),
            "q_text": q,
            "answer_text": a,
            "chapter_question_ids": [QID],
            "chapter_indexes": [ch],
            "chapter_answer_ids": [aid],
            "start": start if aid == CH10_AID else split_t,
            "end": split_t if aid == CH10_AID else end,
            "confidence": 0.5,
            "status": "auto",
            "srt_preview": seg.get("srt_preview"),
            "notes": ((seg.get("notes") or "") + " | " if seg.get("notes") else "") + extra_note + note,
        }
        if meta_kept:
            p["meta"] = dict(meta_kept)
        return p

    seg_a = piece(q_a, a_a, CH10_AID, 10, "子題1+2→第10章 answer-4b4ce77a0008；")
    seg_b = piece(q_b, a_b, CH02_AID, 2, "子題3→第2章 answer-1f29232b4fcc；")

    segs[idx:idx + 1] = [seg_a, seg_b]

    # --- renumber the whole session (deterministic ids, mirror of precedent)
    for i, g in enumerate(segs, start=1):
        qp = g.get("q_text") or ""
        ap_ = g.get("answer_text") or ""
        g["index"] = i
        g["question_id"] = "question-" + hashlib.sha1(
            f"{SID}#{i}#{qp[:80]}".encode()).hexdigest()[:12]
        g["stable_key"] = f"{SID}#{i}"
        g["q_preview"] = qp[:100] + ("…" if len(qp) > 100 else "")
        g["answer_preview"] = ap_[:160] + ("…" if len(ap_) > 160 else "")
        if g.get("start") is not None:
            g["start_label"] = fmt_label(g["start"])
        if g.get("end") is not None:
            g["end_label"] = fmt_label(g["end"])

    # --- month stats (same counting rules as resplit_by_html.py)
    stats = data.setdefault("stats", {})
    matched = missing = low = interpolated = pending = 0
    for s in data["sessions"]:
        for g in s["segments"]:
            note_txt = g.get("notes") or ""
            if g.get("start") is None:
                missing += 1
            else:
                matched += 1
                if (g.get("confidence") or 0) < 0.5:
                    low += 1
                if "interpolated" in note_txt:
                    interpolated += 1
                if "待人工確認" in note_txt or "no-anchor:clamped" in note_txt:
                    pending += 1
    stats.update({"segments": sum(len(s["segments"]) for s in data["sessions"]),
                  "matched": matched, "missing": missing, "low_conf": low,
                  "interpolated": interpolated, "pending": pending})

    print(f"{STABLE_KEY}  {start}–{end}  ->")
    print(f"  #74 {CH10_AID} (ch10) q={len(q_a)}ch a={len(a_a)}ch  "
          f"{start}–{split_t}  w={w_a}")
    print(f"  #75 {CH02_AID} (ch02) q={len(q_b)}ch a={len(a_b)}ch  "
          f"{split_t}–{end}  w={w_b}")
    print(f"  session {len(segs)-1} -> {len(segs)} segments; "
          f"lastPlayed dropped on both pieces (re-listen)")

    if not args.apply:
        print("\n(dry-run; pass --apply to write)")
        return 0

    data.pop("version_marker", None)
    MAP.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"wrote {MAP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
