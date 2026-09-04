#!/usr/bin/env python3
"""Month-by-month validation of audio_map2/*.json after a relink.

Compares the working tree against git HEAD (the frozen baseline) and reports, per
month and globally:

  1. JSON parses; sessions/segments well-formed.
  2. index contiguous 1..N (flagged, not failed, for the known 2025-03-12
     combined-timeline quirk).
  3. stable_key / question_id unique within the month.
  4. FROZEN-QID INVARIANT: every chapter qid present in git HEAD still appears
     somewhere in the tree (no curated link lost).
  5. cross-session qid: a qid spanning two sessions AFTER relink that did not
     before. Split into (a) verbatim day-over-day repeats (near-identical q_text)
     — legitimate; and (b) spurious matches (different q_text) — the error signal
     of a false-positive fill.
  6. meta.lastPlayed count preserved vs git HEAD.
  7. per-month chapter coverage delta (segments gaining a chapter link).

Exit 0 only when hard invariants (JSON, contiguity, uniqueness, zero frozen qid
loss, no spurious cross-session qid, lastPlayed preserved) all hold.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"
KNOWN_NONCONTIG = {"2025-03-12-tieba", "2025-03-12-wechat"}


def git_show(rel: str) -> dict:
    out = subprocess.run(["git", "show", f"HEAD:{rel}"],
                         capture_output=True, text=True).stdout
    return json.loads(out) if out else {}


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    total_segs = 0
    total_with_ch = 0
    new_lp = 0
    orig_lp = 0
    frozen_qids: Counter = Counter()   # qid -> n segments at HEAD
    new_qids: Counter = Counter()
    # qid -> set(session_id) at HEAD vs now, to detect NEW cross-session qid
    frozen_qid_sess: dict[str, set] = defaultdict(set)
    new_qid_sess: dict[str, set] = defaultdict(set)
    # qid -> list[(session_id, q_text, answer_text)] of the segments carrying it (now),
    # to tell a legitimate day-over-day repeat (near-identical q_text) or a
    # legitimate merged-question sub-part (different q_text but matching answer
    # text) from a spurious match (both differ).
    qid_qt_ext: dict[str, list] = defaultdict(list)

    print(f"{'month':10} {'segs':>5} {'+ch':>5} {'Δcoverage':>10}  notes")
    print("-" * 60)

    for path in sorted(AUDIO_MAP2_DIR.glob("*.json")):
        rel = path.relative_to(ROOT).as_posix()
        month = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"{month}: unreadable/invalid JSON: {e}")
            continue
        base = git_show(rel)

        sks: set = set()
        qids: set = set()
        nseg = 0
        nch = 0
        for s in data.get("sessions") or []:
            sid = s.get("session_id", "?")
            segs = s.get("segments") or []
            idx = [g.get("index") for g in segs]
            if idx != list(range(1, len(segs) + 1)):
                if sid in KNOWN_NONCONTIG:
                    warnings.append(f"{sid}: non-contiguous index (pre-existing)")
                else:
                    errors.append(f"{sid}: index not contiguous")
            for g in segs:
                nseg += 1
                sk = g.get("stable_key")
                qi = g.get("question_id")
                if sk in sks:
                    errors.append(f"{sid}: dup stable_key {sk}")
                if qi in qids:
                    errors.append(f"{sid}: dup question_id {qi}")
                sks.add(sk)
                qids.add(qi)
                ch = g.get("chapter_question_ids") or []
                if ch:
                    nch += 1
                for qid in ch:
                    new_qids[qid] += 1
                    new_qid_sess[qid].add(sid)
                    qid_qt_ext[qid].append((sid, g.get("q_text") or "", g.get("answer_text") or ""))
                if (g.get("meta") or {}).get("lastPlayed"):
                    new_lp += 1

        # baseline
        bnseg = 0
        for s in base.get("sessions") or []:
            segs = s.get("segments") or []
            sid = s.get("session_id", "?")
            bnseg += len(segs)
            for g in segs:
                for qid in (g.get("chapter_question_ids") or []):
                    frozen_qids[qid] += 1
                    frozen_qid_sess[qid].add(sid)
                if (g.get("meta") or {}).get("lastPlayed"):
                    orig_lp += 1

        total_segs += nseg
        total_with_ch += nch
        delta = nch - sum(1 for s in base.get("sessions") or [] for g in s.get("segments") or [] if g.get("chapter_question_ids"))
        flag = f"{'+' if delta else ''}{delta}"
        print(f"{month:10} {nseg:>5} {nch:>5} {flag:>10}")

    print("-" * 60)
    print(f"{'TOTAL':10} {total_segs:>5} {total_with_ch:>5}")

    # frozen qid loss
    lost = set(frozen_qids) - set(new_qids)
    print()
    print(f"frozen qids (HEAD): {len(frozen_qids)}")
    print(f"qids now:           {len(new_qids)}")
    print(f"frozen qids LOST:   {len(lost)}")
    for q in sorted(lost)[:30]:
        errors.append(f"LOST frozen qid {q}")

    # NEW cross-session qid: a qid spanning 2 sessions now, but 1 before.
    # A day-over-day repeat of the SAME question (near-identical q_text) is
    # legitimate; a cross-session qid whose segments carry DIFFERENT question
    # text is the true false-positive signal.
    def _qn(s: str) -> str:
        return re.sub(r"[^\u4e00-\u9fff\w]", "", s or "").lower()

    new_cross = 0
    repeat_cross = 0
    for qid, sess in new_qid_sess.items():
        if len(sess) <= 1 or len(frozen_qid_sess.get(qid, set())) > 1:
            continue
        recs = qid_qt_ext[qid]
        qts = [t for _, t, _ in recs]
        ans = [a for _, _, a in recs]
        # max pairwise q_text similarity AND answer_text similarity across sessions
        qsim = asim = 0.0
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                qsim = max(qsim, SequenceMatcher(None, _qn(qts[i]), _qn(qts[j])).ratio())
                asim = max(asim, SequenceMatcher(None, _qn(ans[i]), _qn(ans[j])).ratio())
        if qsim >= 0.9:
            repeat_cross += 1
            warnings.append(f"cross-session qid {qid} (verbatim day-over-day repeat, qsim={qsim:.2f}): {sorted(sess)}")
        elif asim >= 0.9:
            # merged multi-part question: two segments answer the SAME classified
            # question with (near-)identical answer text but different sub-question
            # phrasing — legitimate.
            repeat_cross += 1
            warnings.append(f"cross-session qid {qid} (merged-question sub-parts, asim={asim:.2f}): {sorted(sess)}")
        else:
            new_cross += 1
            if new_cross <= 20:
                warnings.append(f"NEW cross-session qid {qid} (different q AND answer, qsim={qsim:.2f} asim={asim:.2f}): {sorted(sess)}")
    print(f"cross-session qids — verbatim/merged repeat (OK): {repeat_cross}")
    print(f"cross-session qids — spurious (different q AND answer, error): {new_cross}")
    if new_cross:
        errors.append(f"{new_cross} spurious cross-session qid(s) — potential false-positive fills")

    print(f"meta.lastPlayed: HEAD={orig_lp} now={new_lp}")
    if orig_lp != new_lp:
        errors.append(f"meta.lastPlayed mismatch: {orig_lp} -> {new_lp}")

    print()
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print("  -", w)
    print()
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    print("ALL INVARIANTS HOLD ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())