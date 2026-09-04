#!/usr/bin/env python3
"""One-off surgical merge of split-artifact segments (a single Q&A block that the
splitter broke into a question stub + an answer fragment).

Four known cases (all lastPlayed empty, so safe to modify):

  A. 2025-05-17-tieba #37+#38  — flphm 业力/能力: #37 is a zero-length question
     stub (start==end), #38 holds "1、2、3、" + the answer.  Merge #37's q into
     #38's q; keep #38.
  B. 2024-03-19-main #25+#26  — 三三 双盘/崇洋媚外: the answer to #25's question
     ("三三，双盘你就做到…") leaked into #26's q_text.  Move it to #25's answer
     and strip it from #26's q.  (No merge — two distinct Q&As.)
  C. 2024-05-24-main #43+#44  — 三三 德国局势: #44's q_text is actually the
     answer.  Merge #43 (question) + #44 (answer); keep #43.
  D. 2024-11-15-main #18+#19  — 求财: #19's q_text is actually the answer.
     Merge #18 (question) + #19 (answer); keep #18.

After merging, segments are renumbered and stable_key/question_id regenerated
with the same formula build_maps.py uses (sha1 of sid#index#q_text[:80]).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"


def qid(sid: str, index: int, q_text: str) -> str:
    h = hashlib.sha1(f"{sid}#{index}#{q_text[:80]}".encode()).hexdigest()[:12]
    return f"question-{h}"


def load(month: str) -> dict:
    return json.loads((AUDIO_MAP2_DIR / f"{month}.json").read_text(encoding="utf-8"))


def save(month: str, data: dict):
    p = AUDIO_MAP2_DIR / f"{month}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_session(data: dict, sid: str):
    for s in data["sessions"]:
        if s["session_id"] == sid:
            return s
    raise KeyError(sid)


def get_seg(session: dict, idx: int) -> dict:
    for g in session["segments"]:
        if g["index"] == idx:
            return g
    raise KeyError(idx)


def renumber(session: dict):
    """Reindex 1..N and regenerate stable_key / question_id."""
    for i, g in enumerate(session["segments"], start=1):
        g["index"] = i
        g["stable_key"] = f"{session['session_id']}#{i}"
        g["question_id"] = qid(session["session_id"], i, g.get("q_text") or "")


def merge_into(session: dict, keep_idx: int, drop_idx: int,
               new_q: str | None, new_a: str | None,
               new_questioner: str | None = None):
    """Replace segment keep_idx's q/a (if given), drop drop_idx, renumber."""
    keep = get_seg(session, keep_idx)
    drop = get_seg(session, drop_idx)
    if new_q is not None:
        keep["q_text"] = new_q
    if new_a is not None:
        keep["answer_text"] = new_a
    if new_questioner is not None:
        keep["questioner"] = new_questioner
    # extend time range to cover the dropped segment if it was answer text
    if keep.get("end") is not None and drop.get("end") is not None:
        keep["end"] = max(keep["end"], drop["end"])
    session["segments"] = [g for g in session["segments"] if g is not drop]
    renumber(session)


def main() -> int:
    # ---- Case A: 2025-05-17-tieba #37 into #38 ----
    d = load("2025-05")
    s = get_session(d, "2025-05-17-tieba")
    q37 = get_seg(s, 37)["q_text"].rstrip()
    q38 = get_seg(s, 38)["q_text"]
    merged_q = q37 + "\n" + q38
    merge_into(s, 38, 37, new_q=merged_q, new_a=None, new_questioner="flphm")
    save("2025-05", d)
    print("A: merged 2025-05-17-tieba #37 into #38")

    # ---- Case C: 2024-05-24-main #44 (answer) into #43 ----
    d = load("2024-05")
    s = get_session(d, "2024-05-24-main")
    ans_c = get_seg(s, 44)["q_text"]  # the answer leaked into q_text
    merge_into(s, 43, 44, new_q=None, new_a=ans_c, new_questioner="三三")
    save("2024-05", d)
    print("C: merged 2024-05-24-main #44 (answer) into #43")

    # ---- Case D: 2024-11-15-main #19 (answer) into #18 ----
    d = load("2024-11")
    s = get_session(d, "2024-11-15-main")
    ans_d = get_seg(s, 19)["q_text"]
    merge_into(s, 18, 19, new_q=None, new_a=ans_d, new_questioner="1")
    save("2024-11", d)
    print("D: merged 2024-11-15-main #19 (answer) into #18")

    # ---- Case B: 2024-03-19-main #25 / #26 boundary fix ----
    d = load("2024-03")
    s = get_session(d, "2024-03-19-main")
    g25 = get_seg(s, 25)
    g26 = get_seg(s, 26)
    q26 = g26["q_text"]
    # q26 = A1 ("三三，双盘…这个都可以。") + "\n" + Q2 ("2、师父怎么看…")
    if "\n" in q26:
        a1, q2 = q26.split("\n", 1)
    else:
        # fallback: find the "2、" boundary
        i = q26.find("2、师父怎么看")
        a1, q2 = q26[:i].rstrip(), q26[i:]
    g25["answer_text"] = a1.strip()
    g26["q_text"] = q2.strip()
    g25["questioner"] = "三三"
    g26["questioner"] = "三三"
    # #25 currently empty answer gains one; regenerate its question_id (q_text unchanged,
    # so stable_key/question_id stay valid) — no index change needed.
    save("2024-03", d)
    print("B: moved 三三(双盘) answer from #26 into #25; #26 now 崇洋媚外 only")

    return 0


if __name__ == "__main__":
    sys.exit(main())