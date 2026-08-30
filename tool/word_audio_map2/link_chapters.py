#!/usr/bin/env python3
"""Link the chronological Word↔audio mapping (audio_map2/*.json) to the
thematic ebook chapters 01–12 (wenda2_ebook), so the ebook play buttons can be
injected from the *reviewed* audio_map2 segments instead of the legacy
``data/audio_map_word/word-*.json``.

This script writes, onto each matching audio_map2 segment, a
``chapter_question_ids`` field (a list of the ebook's stable HTML
``<div class="question" id=…>`` ids, one per theme-chapter question that maps to
this chronological segment) plus ``chapter_indexes``.  It never alters the
segment's text/times/status — it only adds the join keys.

One chronological segment may legitimately map to several theme-chapter
questions (the 汇总 docx merged 2–3 sub-questions that the 12-chapter version
kept separate).  Both questions share the segment's reviewed start/end, which is
exactly the reviewer's intent (one spoken unit).

Sources (read-only; **frozen** — the thematic ``word_audio_map`` aligner that
produced them has been removed, so these gitignored ``build/`` artifacts are no
longer regenerated):
  * ebook questions … ``tool/word_audio_map/build/questions.json``
      (``question_id`` + ``chapter_index`` + ``q_text`` / ``a_text``).
  * optional bridge … ``tool/word_audio_map/build/qid_bridge_v2.json``
      (ebook ``question_id`` → chronological ``session_id``), used to *narrow*
      candidates; content still decides.
  * chronological sessions … ``tool/word_audio_map/build/chrono_sessions.json``.

Matching is content-based (normalize: strip Word ``_x0001_``/``_x000D_``
artifacts, unify 繁/簡 via OpenCC is NOT done here — instead we normalize
師傅/師父-style variants and strip all non-CJK/alnum), in this order:
  1. exact / one-side containment of q_text, within the bridged session;
  2. same across all sessions;
  3. fuzzy q_text ratio ≥ 0.8 (then answer text confirms).

Ambiguities are resolved by answer_text overlap; anything still ambiguous or
unmatched is left unlinked and reported for manual review.

Usage (from the repo root or tool/word_audio_map2):
    python3 tool/word_audio_map2/link_chapters.py --apply            # write back
    python3 tool/word_audio_map2/link_chapters.py                    # dry-run report
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"
QUESTIONS = ROOT / "tool" / "word_audio_map" / "build" / "questions.json"
BRIDGE = ROOT / "tool" / "word_audio_map" / "build" / "qid_bridge_v2.json"
CHRONO = ROOT / "tool" / "word_audio_map" / "build" / "chrono_sessions.json"


_CC_SENTINEL = object()
_CC = _CC_SENTINEL  # None means "opencc unavailable"; sentinel means "not tried yet"

_ENUM_RE = re.compile(
    r"^(?:第\d+(?:\.\d+)?问[:：]?|第[A-Za-z0-9]+问[:：]?|"
    r"[（(]?\d{1,3}[、.．,，)）]|[（(]?[一二三四五六七八九十]+[、.．,，)）])\s*"
)


def _converter():
    """Return an OpenCC t2s converter, or None if opencc is unavailable."""
    global _CC
    if _CC is not _CC_SENTINEL:
        return _CC
    try:
        from opencc import OpenCC
        _CC = OpenCC("t2s")
    except Exception:
        _CC = None
    return _CC


def norm(s: str) -> str:
    s = s if isinstance(s, str) else ""
    # strip Word field artifacts (_x0001_…_x000B_…_x000D_) anywhere
    s = re.sub(r"_x[0-9A-Fa-f]{4}_", "", s)
    cc = _converter()
    if cc is not None:
        try:
            s = cc.convert(s)
        except Exception:
            pass
    else:
        # minimal TW→CN fallback (word doc mixes both)
        for a, b in (("為", "为"), ("裡", "里"), ("說", "说"), ("師", "师"),
                     ("門", "门"), ("對", "对"), ("現", "现"), ("頭", "头"),
                     ("師傅", "师父"), ("师付", "师父")):
            s = s.replace(a, b)
    return re.sub(r"[^\w\u4e00-\u9fff]", "", s).lower()


def overlap(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def load_questions() -> List[dict]:
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    return data


def load_bridge() -> Dict[str, dict]:
    data = json.loads(BRIDGE.read_text(encoding="utf-8"))
    return data.get("bridge", {})


def load_chrono_blocks() -> Dict[str, Dict[str, str]]:
    """Return {session_id: {block_seq: normalized_block_q_text}} from chrono_sessions.

    The block q_text is the original chronological 匯總 docx question text (same
    source the audio_map2 segments were built from), so it is a far more reliable
    join key than the (possibly reworded) chapter question text.
    """
    data = json.loads(CHRONO.read_text(encoding="utf-8"))
    out: Dict[str, Dict[str, str]] = {}
    for ch in data.get("chapters") or []:
        sid = ch.get("session_date")
        if not sid:
            continue
        blk: Dict[str, str] = {}
        for b in ch.get("blocks") or []:
            seq = str(b.get("seq", ""))
            blk[seq] = norm(b.get("q_text") or "")
        out[sid] = blk
    return out


def load_audio_map2() -> Tuple[Dict[str, dict], Dict[str, list], Dict[str, list]]:
    """Return (sessions, seg_by_session, seg_norm_by_session).

    ``seg_norm_by_session[sid]`` is a list of ``(segment, normalized_q_text)``
    precomputed once so the O(n) matching pass avoids re-normalising every
    segment for every question (OpenCC is expensive).
    """
    sessions: Dict[str, dict] = {}
    seg_by_session: Dict[str, list] = defaultdict(list)
    seg_norm_by_session: Dict[str, list] = defaultdict(list)
    for path in sorted(AUDIO_MAP2_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"⚠ skip {path.name}: {exc}")
            continue
        for s in data.get("sessions") or []:
            sessions[s["session_id"]] = s
            seg_by_session[s["session_id"]] = s.get("segments") or []
            seg_norm_by_session[s["session_id"]] = [
                (seg, norm(seg.get("q_text") or ""), norm(seg.get("answer_text") or ""))
                for seg in s.get("segments") or []
            ]
    return sessions, seg_by_session, seg_norm_by_session


def _strip_enum(s: str) -> str:
    """Drop a leading sub-question enumerator so a chapter sub-question can be
    located inside a larger merged 匯總 block (whose answer text keeps the
    numbered items)."""
    return _ENUM_RE.sub("", s).strip()


def find_candidates(
    q: dict,
    bridge: Dict[str, dict],
    sessions: Dict[str, dict],
    seg_norm_by_session: Dict[str, list],
    chrono_blocks: Dict[str, Dict[str, str]],
) -> List[Tuple[dict, dict]]:
    """Return [(session_dict, segment)] candidates for this ebook question."""
    qid = q["question_id"]
    qn = norm(q["q_text"])
    qn_enumless = _strip_enum(qn)
    b = bridge.get(qid)
    sid = b.get("session_id") if b else None

    def _contains(nq: str, na: str, target: str) -> bool:
        if not target:
            return False
        if nq and (nq == target or nq in target or target in nq):
            return True
        return False

    # 0) bridge block_seq → original 匯總 q_text → same-session segment.
    #    Most authoritative: uses the source block text, not the chapter rewrite.
    hits: List[Tuple[dict, dict]] = []
    if sid and sid in sessions:
        block_q = (chrono_blocks.get(sid) or {}).get(str(b.get("block_seq", "")))
        if block_q and len(block_q) >= 6:
            for seg, sn, sa in seg_norm_by_session.get(sid, []):
                if sn and (sn == block_q or sn in block_q or block_q in sn):
                    hits.append((sessions[sid], seg))
        if hits:
            return hits

    # 1) bridged session: exact / containment on chapter q_text

    # 2) global exact / containment on q_text
    for key in sessions:
        for seg, sn, sa in seg_norm_by_session.get(key, []):
            if _contains(sn, sa, qn):
                hits.append((sessions[key], seg))
    if hits:
        return hits

    # 3) numbered sub-question: only for questions WITH a leading enumerator,
    #    whose enum-stripped body lives inside a (possibly merged) 匯總 block's
    #    q_text or answer_text. This is the 「第二个问题／第N问」multi-part case
    #    where the chapter keeps sub-items separate but the reviewer kept one
    #    spoken unit → all sub-items share that segment's range.
    has_enum = bool(_ENUM_RE.match(qn))
    if has_enum and len(qn_enumless) >= 10:
        for key in sessions:
            for seg, sn, sa in seg_norm_by_session.get(key, []):
                if (sa and qn_enumless in sa) or (sn and qn_enumless in sn):
                    hits.append((sessions[key], seg))
    if hits:
        return hits

    # 3b) bridged-session answer_text containment: the (reworded) chapter
    #    question still appears verbatim inside its own session's answer block.
    #    Scoped to the bridge-selected session only (not global) and gated on a
    #    long fragment so a shared-phrase coincidence can't trigger it.
    if sid and sid in sessions and len(qn) >= 15:
        for seg, sn, sa in seg_norm_by_session.get(sid, []):
            if sa and qn in sa:
                hits.append((sessions[sid], seg))
    if hits:
        return hits

    # 4) fuzzy within bridged session (then global) — q_text only (answer text
    #    is too broad / shared-phrase prone for a reliable fuzzy join)
    scored: List[Tuple[float, dict, dict]] = []
    pools = [sid] if sid and sid in sessions else list(sessions.keys())
    for key in pools:
        for seg, sn, sa in seg_norm_by_session.get(key, []):
            if not sn:
                continue
            r = difflib.SequenceMatcher(None, qn, sn).ratio()
            if r >= 0.8:
                scored.append((r, sessions[key], seg))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return []
    top = scored[0][0]
    best = [s for s in scored if top - s[0] < 0.05]
    return [(sess, seg) for _, sess, seg in best]


def main() -> int:
    ap = argparse.ArgumentParser(description="Link audio_map2 → ebook chapters")
    ap.add_argument("--apply", action="store_true", help="write chapter_question_id back into audio_map2 JSON")
    ap.add_argument("--report", default="tool/word_audio_map2/build/link_report.json",
                    help="where to dump the link report (default under tool/word_audio_map2/build/)")
    args = ap.parse_args()

    questions = load_questions()
    bridge = load_bridge()
    sessions, seg_by_session, seg_norm_by_session = load_audio_map2()
    chrono_blocks = load_chrono_blocks()

    linked: Dict[str, dict] = {}
    unmatched: List[dict] = []
    ambiguous: List[dict] = []

    for q in questions:
        qid = q["question_id"]
        cands = find_candidates(q, bridge, sessions, seg_norm_by_session, chrono_blocks)
        if not cands:
            unmatched.append({"question_id": qid, "chapter_index": q.get("chapter_index"),
                              "q_text": (q.get("q_text") or "")[:120]})
            continue
        if len(cands) == 1:
            session, seg = cands[0]
            linked[qid] = {"chapter_index": q.get("chapter_index"), "session_id": session["session_id"],
                           "seg_index": seg.get("index"), "start": seg.get("start"), "end": seg.get("end"),
                           "status": seg.get("status")}
            continue
        # resolve by answer_text
        scored = []
        for session, seg in cands:
            r = overlap(q.get("a_text") or "", seg.get("answer_text") or "")
            scored.append((r, session, seg))
        scored.sort(key=lambda x: -x[0])
        if scored and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.1):
            session, seg = scored[0][1], scored[0][2]
            linked[qid] = {"chapter_index": q.get("chapter_index"), "session_id": session["session_id"],
                           "seg_index": seg.get("index"), "start": seg.get("start"), "end": seg.get("end"),
                           "status": seg.get("status")}
        else:
            ambiguous.append({"question_id": qid, "chapter_index": q.get("chapter_index"),
                              "q_text": (q.get("q_text") or "")[:80],
                              "candidates": [{"session_id": s["session_id"], "seg_index": g.get("index")}
                                             for _, s, g in scored]})

    print(f"ebook questions: {len(questions)}")
    print(f"linked:           {len(linked)}")
    print(f"ambiguous:        {len(ambiguous)}")
    print(f"unmatched:        {len(unmatched)}")

    # apply writeback
    if args.apply:
        # Group linked questions by (session_id, seg_index) so a segment that
        # maps to multiple chapter questions carries a list.
        by_seg: Dict[Tuple[str, int], List[Tuple[str, int]]] = defaultdict(list)
        for qid, info in linked.items():
            by_seg[(info["session_id"], info["seg_index"])].append(
                (qid, info["chapter_index"])
            )
        written = 0
        for path in sorted(AUDIO_MAP2_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            touched = False
            for s in data.get("sessions") or []:
                sid = s["session_id"]
                for seg in s.get("segments") or []:
                    idx = seg.get("index")
                    qids = by_seg.get((sid, idx))
                    if qids:
                        seg["chapter_question_ids"] = [q for q, _ in qids]
                        seg["chapter_indexes"] = [ci for _, ci in qids]
                        seg.pop("chapter_question_id", None)  # legacy cleanup
                        seg.pop("chapter_index", None)
                        touched = True
                        written += len(qids)
                        by_seg[(sid, idx)] = []
            if touched:
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote chapter_question_ids linking {written} question(s) onto segments")
    else:
        print("(dry run — pass --apply to write chapter_question_ids)")

    # report
    rp = Path(args.report)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(
        {"linked": linked, "ambiguous": ambiguous, "unmatched": unmatched},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report → {rp}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())