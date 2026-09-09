#!/usr/bin/env python3
"""One-off surgical fix for audio_map2/2025-05.json, 2025-05-17-tieba segment #2.

The Word splitter folded TWO html questions into one segment (chapter_question_ids
only carried ``question-9d23f3df4aab``; ``question-03f6a3551d99`` was orphaned and
unlinked anywhere).  Split that segment into two, one per html question block,
preserving the Word text (simplified ``着`` variant) verbatim by slicing at the
html head anchors found inside the raw Word text.

Only this one segment is touched; neighbours keep start/end.  The two pieces get
proportional times; status -> auto; lastPlayed stripped; note appended.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "audio_map2" / "2025-05.json"
QUESTIONS = Path(__file__).resolve().parent / "build" / "questions.json"

Q1 = "question-9d23f3df4aab"   # 问题二、观地藏菩萨像
Q2 = "question-03f6a3551d99"   # 后期转思情…

def main() -> int:
    qmap = {q["question_id"]: q for q in json.loads(QUESTIONS.read_text(encoding="utf-8"))}
    data = json.loads(MAP.read_text(encoding="utf-8"))
    sess = next(s for s in data["sessions"] if s["session_id"] == "2025-05-17-tieba")
    segs = sess["segments"]
    seg = next(s for s in segs if s.get("stable_key") == "2025-05-17-tieba#2")
    idx = segs.index(seg)

    ans = seg["answer_text"]
    # html head anchors (in Simplified, matching Word's charset for these heads)
    q1_head = "问题二、"                 # Q1 question head
    q2_head = qmap[Q2]["q_text"][:18]   # "后期转思情(思念阿弥陀佛)"
    a1_head = qmap[Q1]["a_text"][:18]   # "下一个问题，观佛可不可以"
    a2_head = qmap[Q2]["a_text"][:18]   # "后期转思情，思情提不起来"

    p_q2 = ans.find(q2_head)
    p_a1 = ans.find(a1_head)
    p_a2 = ans.find(a2_head)
    assert 0 <= p_q2 < p_a1 < p_a2, (p_q2, p_a1, p_a2)

    q_text_1 = ans[:p_q2].strip()               # "问题二、…特征明显。"
    q_text_2 = ans[p_q2:p_a1].strip()           # "后期转思情…体质特殊。"
    a_text_1 = ans[p_a1:p_a2].strip()           # "下一个问题…可以啊。"
    a_text_2 = ans[p_a2:].strip()               # "后期转思情…才是真实的。"

    assert q_text_1 and q_text_2 and a_text_1 and a_text_2

    # proportional time split by kept-text length ratio (Q+A weights)
    import re
    KEPT = re.compile(r"[^\s\u3000]")
    w1 = len(KEPT.findall(q_text_1)) + len(KEPT.findall(a_text_1))
    w2 = len(KEPT.findall(q_text_2)) + len(KEPT.findall(a_text_2))
    start, end = seg["start"], seg["end"]
    split_t = start + (end - start) * w1 / (w1 + w2)

    common = {
        "questioner": seg.get("questioner"),
        "question_time": seg.get("question_time"),
        "status": "auto",
        "confidence": 0.5,
        "meta": {k: v for k, v in (seg.get("meta") or {}).items() if k != "lastPlayed"}
               if seg.get("meta") else None,
        "srt_preview": seg.get("srt_preview"),
    }
    note = "html-resplit: 依 wenda2_ebook 問題邊界重新分段（切分多題段，補掛孤兒題），待人工確認"

    seg_a = dict(common)
    seg_a.update({
        "q_text": q_text_1, "answer_text": a_text_1,
        "start": start, "end": round(split_t, 1),
        "chapter_question_ids": [Q1],
        "chapter_indexes": [qmap[Q1]["chapter_index"]],
        "chapter_answer_ids": ["answer-dc731986faa4"],
        "notes": note,
    })
    seg_b = dict(common)
    seg_b.update({
        "q_text": q_text_2, "answer_text": a_text_2,
        "start": round(split_t, 1), "end": end,
        "chapter_question_ids": [Q2],
        "chapter_indexes": [qmap[Q2]["chapter_index"]],
        "chapter_answer_ids": ["answer-9e2b66b467bc"],
        "notes": note,
    })
    if seg_a["meta"] is None:
        seg_a.pop("meta")
    if seg_b["meta"] is None:
        seg_b.pop("meta")

    segs[idx:idx + 1] = [seg_a, seg_b]

    # renumber + recompute ids/previews/labels for the whole session (mirror resplit)
    import hashlib
    def fmt_label(sec: float) -> str:
        h = int(sec // 3600); m = int((sec % 3600) // 60); s = sec % 60
        return f"{h:02d}:{m:02d}:{int(s):02d}.{int(round((s - int(s)) * 1000)):03d}"
    sid = sess["session_id"]
    for i, g in enumerate(segs, start=1):
        qp = g.get("q_text") or ""
        ap = g.get("answer_text") or ""
        g["index"] = i
        g["question_id"] = "question-" + hashlib.sha1(
            f"{sid}#{i}#{qp[:80]}".encode()).hexdigest()[:12]
        g["stable_key"] = f"{sid}#{i}"
        g["q_preview"] = qp[:100] + ("…" if len(qp) > 100 else "")
        g["answer_preview"] = ap[:160] + ("…" if len(ap) > 160 else "")
        if g.get("start") is not None:
            g["start_label"] = fmt_label(g["start"])
        if g.get("end") is not None:
            g["end_label"] = fmt_label(g["end"])

    MAP.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {MAP}")
    print(f"  seg2a {Q1}: {len(q_text_1)}+{len(a_text_1)} chars, {start}–{round(split_t,1)}")
    print(f"  seg2b {Q2}: {len(q_text_2)}+{len(a_text_2)} chars, {round(split_t,1)}–{end}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())