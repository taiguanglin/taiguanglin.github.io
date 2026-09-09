#!/usr/bin/env python3
"""Re-segment audio_map2 month JSONs so that **one segment == one wenda2_ebook
HTML question** (the unit the play buttons are injected at).

Why: the Word-based splitter (build_maps.py) cannot reliably reproduce the
ebook's question boundaries — e.g. 2025-05-15 微信公众号 段 13/14 were split
at a numbering boundary, while the ebook (and the way the master answered)
treats the whole block as ONE question.  The HTML is the final consumer of
these time ranges, so it becomes the segmentation source of truth.

Rules
-----
1. Each segment's `chapter_question_ids` already links it to ebook questions
   (build/questions.json).  This script re-groups segments so every segment
   carries exactly ONE qid:
   - **merge**: consecutive segments sharing the same qid are merged
     (Word split one HTML question into several segments).
   - **split**: a segment with multiple qids is sliced at the positions where
     each ebook question's q_text / a_text actually starts (OpenCC-normalized
     exact locate, position mapped back to the raw text).
2. Any segment whose *shape changes* (merged or split) loses its
   `meta.lastPlayed` record — it must be re-listened.  Untouched segments
   keep everything (times, status, lastPlayed) exactly as before.
3. Time allocation for splits is proportional to slice text length
   (question + answer), flagged 待人工確認 with confidence capped — the real
   boundaries can only come from re-listening.
4. Multi-qid segments whose members cannot all be located in the text are
   left untouched and reported as *unresolved*.
5. After regrouping, a qid appears on exactly one segment per month
   (asserted); segments with no qid are passed through untouched.

Usage:
  .venv/bin/python resplit_by_html.py                 # dry-run, all months
  .venv/bin/python resplit_by_html.py --month 2025-05 # dry-run one month
  .venv/bin/python resplit_by_html.py --month 2025-05 --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from opencc import OpenCC

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"
QUESTIONS_JSON = Path(__file__).resolve().parent / "build" / "questions.json"

CC = OpenCC("t2s")  # traditional -> simplified, length-preserving on kept chars
KEPT = re.compile(r"[\w一-鿿]")


def kept_stream(raw: str) -> Tuple[str, List[int]]:
    """(converted kept-char stream, [original index per kept char])."""
    chars, idx = [], []
    for i, ch in enumerate(raw or ""):
        if KEPT.match(ch):
            chars.append(ch)
            idx.append(i)
    conv = CC.convert("".join(chars))
    if len(conv) != len(chars):  # OpenCC phrase conversion: give up safely
        return "".join(chars), idx
    return conv, idx


def fmt_label(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{int(s):02d}.{int(round((s - int(s)) * 1000)):03d}"


def question_id(sid: str, index: int, q_text: str) -> str:
    h = hashlib.sha1(f"{sid}#{index}#{q_text[:80]}".encode()).hexdigest()[:12]
    return f"question-{h}"


def locate(stream: str, idx_map: List[int], probe: str) -> Optional[int]:
    """Find normalized probe head in stream; return RAW char index or None.

    Exact head match first, then a difflib sliding-window fuzzy fallback
    (tolerates an inserted/edited char or a probe that starts mid-list).
    """
    p = stream.find(probe)
    if p >= 0:
        return idx_map[p]
    if not probe:
        return None
    from difflib import SequenceMatcher
    n = len(probe)
    step = max(1, n // 12)
    best, best_i = 0.0, -1
    for i in range(0, max(1, len(stream) - n + 1), step):
        r = SequenceMatcher(None, probe, stream[i:i + n]).ratio()
        if r > best:
            best, best_i = r, i
    if best >= 0.85 and best_i >= 0 and best_i < len(idx_map):
        return idx_map[best_i]
    return None


class Piece:
    """One ebook-question-sized slice (possibly a whole untouched segment)."""

    __slots__ = ("qid", "seg", "q_text", "a_text", "whole", "start", "end", "qids")

    def __init__(self, qid, seg, q_text, a_text, whole, start=None, end=None,
                 qids=None):
        self.qid = qid
        self.seg = seg
        self.q_text = q_text
        self.a_text = a_text
        self.whole = whole          # True = covers its source segment 1:1
        self.start = start          # only set for slices of a split segment
        self.end = end
        self.qids = qids            # resolved chapter_question_ids for this piece


def split_segment(seg: dict, qids: List[str], qmap: dict) -> Tuple[Optional[List[Piece]], List[str]]:
    """Slice a multi-qid segment into per-question pieces at text positions.

    Returns (pieces or None, dropped_qids).  dropped_qids are qids whose text
    is absent from this segment (spurious link); the caller decides whether
    that is safe (qid claimed elsewhere) or must keep the segment unresolved.
    """
    q_text = seg.get("q_text") or ""
    a_text = seg.get("answer_text") or ""

    qstream, qidx = kept_stream(q_text)
    astream, aidx = kept_stream(a_text)

    # Locate each qid's question text: first in q_text (region "Q"), then in
    # answer_text (region "A" — the master read the question back and answered;
    # these follow-up questions only exist inside the answer).
    qloc: Dict[str, Tuple[str, int]] = {}
    for qid in qids:
        hq, _ = kept_stream(qmap[qid]["q_text"])
        if not hq:
            continue
        p = locate(qstream, qidx, hq[:80])
        if p is not None:
            qloc[qid] = ("Q", p)
        else:
            p = locate(astream, aidx, hq[:80])
            if p is not None:
                qloc[qid] = ("A", p)

    located = [q for q in qids if q in qloc]
    if not located:
        return None, list(qids)
    missing = [q for q in qids if q not in qloc]

    # timeline order: Q-region positions (in question part) then A-region (in
    # answer part); both regions are individually monotone by raw index.
    ordered = sorted(located, key=lambda q: (0 if qloc[q][0] == "Q" else 1,
                                              qloc[q][1]))

    # answer_start per qid: where that question's content begins inside the
    # answer.  A-region qid -> its question position (it begins with the read
    # question).  Q-region qid -> its a_text head; if not found, fall back to
    # the next question's position (answer runs until the next question).
    apos: Dict[str, int] = {}
    for qid in located:
        if qloc[qid][0] == "A":
            apos[qid] = qloc[qid][1]
            continue
        ha, _ = kept_stream(qmap[qid]["a_text"])
        p = locate(astream, aidx, ha[:40]) if ha else None
        if p is not None:
            apos[qid] = p

    pieces: List[Piece] = []
    q_positions = sorted(set(qloc[q][1] for q in located if qloc[q][0] == "Q"))
    a_positions = sorted(set(apos.values()))
    for qid in ordered:
        region, qpos0 = qloc[qid]
        # question slice
        if region == "Q":
            nxt = next((x for x in q_positions if x > qpos0), len(q_text))
            q_slice = q_text[qpos0:nxt].strip()
        else:
            q_slice = ""  # question text lives inside the answer (read-back)
        # answer slice
        a0 = apos.get(qid)
        if a0 is None:
            a_slice = ""
        else:
            nxt_a = next((x for x in a_positions if x > a0), len(a_text))
            a_slice = a_text[a0:nxt_a].strip()
        pieces.append(Piece(qid, seg, q_slice, a_slice, whole=False, qids=[qid]))

    # unmatched answer head/tail: give to first / last piece so nothing is lost
    if a_positions:
        head = a_text[: a_positions[0]].strip()
        if head:
            pieces[0].a_text = (head + "\n\n" + pieces[0].a_text).strip()
    elif a_text.strip() and pieces:
        pieces[-1].a_text = (pieces[-1].a_text + "\n\n" + a_text).strip()

    # proportional time allocation by kept-text weight
    weights = []
    for p in pieces:
        w = len(KEPT.findall(p.q_text)) + len(KEPT.findall(p.a_text))
        weights.append(max(w, 1))
    start, end = seg.get("start"), seg.get("end")
    if start is not None and end is not None and end > start:
        total = sum(weights)
        acc = start
        for p, w in zip(pieces, weights):
            p.start = acc
            acc = acc + (end - start) * w / total
            p.end = acc
        pieces[-1].end = end  # exact outer bound
    else:
        for p in pieces:
            p.start, p.end = start, end
    return pieces, missing


def session_pieces(segments: List[dict], qmap: dict) -> Tuple[List[Piece], List[dict]]:
    """Cut the session into pieces keyed to ebook questions.

    1. Split multi-qid segments (their own frozen qid list).
    2. Split a single-qid segment when the NEXT question's text head starts
       inside it (a question boundary falling mid-segment — one Word chunk holds
       the tail of question A and the head of the next question B).  Only the
       IMMEDIATE successor qid is probed (exact match) to avoid over-matching.
    """
    pieces: List[Piece] = []
    unresolved: List[dict] = []
    claimed_qids: set = set()

    session_qids: List[str] = []
    for seg in segments:
        for q in (seg.get("chapter_question_ids") or []):
            if q and q not in session_qids:
                session_qids.append(q)
    qid_next: Dict[str, Optional[str]] = {}
    for i, q in enumerate(session_qids):
        qid_next[q] = session_qids[i + 1] if i + 1 < len(session_qids) else None

    def locate_own(seg) -> List[str]:
        """segment's own frozen qids whose text is actually present, in order."""
        own = [q for q in (seg.get("chapter_question_ids") or []) if q in qmap]
        qs, qidx = kept_stream(seg.get("q_text") or "")
        as_, aidx = kept_stream(seg.get("answer_text") or "")
        hits = []
        for qid in own:
            hq, _ = kept_stream(qmap[qid]["q_text"])
            if not hq:
                continue
            p = locate(qs, qidx, hq[:80])
            if p is None:
                p2 = locate(as_, aidx, hq[:80])
                if p2 is None:
                    continue
                hits.append(("A", p2, qid))
            else:
                hits.append(("Q", p, qid))
        hits.sort(key=lambda h: (0 if h[0] == "Q" else 1, h[1]))
        return [h[2] for h in hits]

    def successor_starting_here(seg, own_qid) -> Optional[str]:
        """If the next question's head begins inside this segment's text AFTER the
        own question's body has ended, return its qid — a genuine mid-segment
        boundary.  Requires the own q_text tail to be located first, then probes
        only the trailing remainder (exact), so multi-part questions do not
        falsely split."""
        nxt = qid_next.get(own_qid) if own_qid else None
        if not nxt or nxt not in qmap:
            return None
        qs, qidx = kept_stream(seg.get("q_text") or "")
        hn, _ = kept_stream(qmap[nxt]["q_text"])
        if not hn:
            return None
        if not own_qid or own_qid not in qmap:
            # no own body to anchor on — require the successor head at the very
            # start of the question region, and no own question present.
            p = qs.find(hn[:50])
            return nxt if p == 0 else None
        own_tail, _ = kept_stream(qmap[own_qid]["q_text"][-40:])
        t = qs.find(own_tail[:30]) if own_tail else 0
        if t < 0:
            return None
        t_end = t + (len(own_tail) if own_tail else 0)
        p = qs.find(hn[:50], t_end)
        return nxt if p >= 0 else None

    for seg in segments:
        frz_all = list(seg.get("chapter_question_ids") or [])
        missing_frozens = [q for q in frz_all if q not in qmap]
        frz_map = [q for q in frz_all if q in qmap]

        if missing_frozens:
            claimed_qids.update(frz_all)
            pieces.append(Piece(None, seg,
                                seg.get("q_text") or "", seg.get("answer_text") or "",
                                whole=True, qids=frz_all))
            continue

        if len(frz_map) >= 2:
            # multi-qid segment: split at the located question boundaries;
            # unlocatable qids are dropped only if claimed elsewhere, otherwise
            # the segment stays unresolved with every frozen qid preserved.
            sp, dropped = split_segment(seg, frz_map, qmap)
            if sp is None:
                unresolved.append(seg)
                claimed_qids.update(frz_all)
                pieces.append(Piece(None, seg, seg.get("q_text") or "",
                                    seg.get("answer_text") or "", whole=True,
                                    qids=frz_all))
                continue
            safe_drop = all(q in claimed_qids or any(
                q in (p.seg.get("chapter_question_ids") or []) for p in pieces)
                for q in dropped)
            if not safe_drop:
                unresolved.append(seg)
                claimed_qids.update(frz_all)
                pieces.append(Piece(None, seg, seg.get("q_text") or "",
                                    seg.get("answer_text") or "", whole=True,
                                    qids=frz_all))
                continue
            for q in dropped:
                print(f"      (spurious-link dropped {q} from one segment)")
            claimed_qids.update(p.qid for p in sp if p.qid)
            pieces.extend(sp)
            continue

        # single-qid segment
        located = locate_own(seg)
        if not located:
            # continuation segment carrying the middle/tail of its question:
            # trust the frozen link so it merges with the preceding same-qid seg.
            located = frz_map if len(frz_map) == 1 else []
        if len(located) <= 1:
            own_qid = located[0] if located else None
            succ = successor_starting_here(seg, own_qid)
            if succ and succ not in located:
                located = [own_qid, succ] if own_qid else [succ]
        if len(located) <= 1:
            claimed_qids.update(located)
            pieces.append(Piece(located[0] if located else None, seg,
                                seg.get("q_text") or "", seg.get("answer_text") or "",
                                whole=True, qids=list(located)))
            continue
        # a successor question starts mid-segment (and its own qid too)
        sp, dropped = split_segment(seg, located, qmap)
        if sp is None:
            unresolved.append(seg)
            claimed_qids.update(frz_all)
            pieces.append(Piece(None, seg, seg.get("q_text") or "",
                                seg.get("answer_text") or "", whole=True,
                                qids=frz_all))
            continue
        claimed_qids.update(p.qid for p in sp if p.qid)
        pieces.extend(sp)
    return pieces, unresolved


def runs_from_pieces(pieces: List[Piece]) -> List[List[Piece]]:
    """Group consecutive pieces by qid (None-qid pieces always stand alone)."""
    runs: List[List[Piece]] = []
    for p in pieces:
        if p.qid is not None and runs and runs[-1][-1].qid == p.qid and p.qid is not None:
            runs[-1].append(p)
        else:
            runs.append([p])
    return runs


def compose_run(sid: str, run: List[Piece], qmap: dict) -> dict:
    """Build the new segment dict for one run (single untouched piece -> copy).

    A single whole piece is kept VERBATIM (incl. lastPlayed) only when its
    resolved qid list still equals its original frozen list — i.e. truly
    unchanged.  If a spurious link was dropped (resolved != frozen), the qid
    list is rewritten and the segment is marked for re-listen.
    """
    p0 = run[0]
    if len(run) == 1 and p0.whole:
        resolved = p0.qids if p0.qids is not None else ([p0.qid] if p0.qid else [])
        frozen = [q for q in (p0.seg.get("chapter_question_ids") or [])]
        if resolved == frozen:
            return dict(p0.seg)  # untouched: keep everything incl. lastPlayed
        seg = dict(p0.seg)
        seg["chapter_question_ids"] = resolved
        seg["chapter_indexes"] = [qmap[q]["chapter_index"] for q in resolved
                                  if q in qmap] if resolved else []
        seg["notes"] = (seg.get("notes") or "") + " | html-resplit: 修正章節對應，待人工確認"
        seg["meta"] = {k: v for k, v in (seg.get("meta") or {}).items()
                       if k != "lastPlayed"}
        return seg

    members = [p.seg for p in run]
    first = members[0]
    qid = run[0].qid

    q_text = "\n".join(p.q_text for p in run if p.q_text).strip()
    a_text = "\n\n".join(p.a_text for p in run if p.a_text).strip()

    starts = [p.start if p.start is not None else p.seg.get("start") for p in run]
    ends = [p.end if p.end is not None else p.seg.get("end") for p in run]
    start = next((s for s in starts if s is not None), None)
    end = next((e for e in reversed(ends) if e is not None), None)

    has_split = any(not p.whole for p in run)
    confs = [m.get("confidence") for m in members if m.get("confidence") is not None]
    conf = min(confs) if confs else None

    out = {
        "questioner": first.get("questioner"),
        "question_time": first.get("question_time"),
        "q_text": q_text,
        "answer_text": a_text,
        "start": start,
        "end": end,
        "confidence": (min(conf, 0.5) if has_split and conf else conf),
        "status": "auto" if has_split else first.get("status"),
        "srt_preview": first.get("srt_preview"),
        "chapter_question_ids": [qid] if qid else [],
        "chapter_indexes": [qmap[qid]["chapter_index"]] if qid in qmap else [],
    }
    if start is not None:
        out["start_label"] = fmt_label(start)
    if end is not None:
        out["end_label"] = fmt_label(end)

    kind = "切分多題段" if has_split else "合併同一問題"
    note = f"html-resplit: 依 wenda2_ebook 問題邊界重新分段（{kind}），待人工確認"
    prev_notes = next((m.get("notes") for m in members if m.get("notes")), None)
    if prev_notes and "html-resplit" not in prev_notes:
        note = f"{prev_notes} | {note}"
    out["notes"] = note

    # erase any listened record — the boundaries changed, must be re-listened
    meta = {k: v for m in members for k, v in (m.get("meta") or {}).items()
            if k != "lastPlayed"}
    if meta:
        out["meta"] = meta
    return out


def normalize_segment_keys(segments: List[dict]) -> List[str]:
    return [f"{(s.get('q_text') or '')[:80]}|{s.get('start')}|{s.get('end')}"
            for s in segments]


def apply_spillover(segs: List[dict], qmap: dict) -> int:
    """Fixes audio ranges where a question's answer tail bleeds into the NEXT
    segment (the master read the next question, then finished the previous
    answer).  Extends the previous question's ``end`` to where its a_text tail
    actually ends inside the next segment's answer, proportionally.

    Both segments are marked needs-re-listen; returns how many were fixed.
    """
    fixed = 0
    if not segs:
        return 0
    for i in range(len(segs) - 1):
        cur, nxt = segs[i], segs[i + 1]
        qid = (cur.get("chapter_question_ids") or [None])[0]
        nqid = (nxt.get("chapter_question_ids") or [None])[0]
        if not (qid and nqid):
            continue
        if "html-resplit:答案溢出" in (cur.get("notes") or ""):
            continue  # already fixed (idempotent)
        a = qmap.get(qid)
        if not a:
            continue
        tail_conv, _ = kept_stream(a["a_text"][-40:]) if a["a_text"] else ("", [])
        if not tail_conv or len(tail_conv) < 12:
            continue
        cur_ans, _ = kept_stream(cur.get("answer_text") or "")
        if tail_conv[:24] in cur_ans or tail_conv[:12] in cur_ans:
            continue  # answer is self-contained in this segment
        nxt_ans, nxt_idx = kept_stream(nxt.get("answer_text") or "")
        if not nxt_ans:
            continue
        p = nxt_ans.find(tail_conv[:24])
        if p < 0:
            p = nxt_ans.find(tail_conv[:16])
        if p < 0:
            continue
        # proportionally extend cur.end into nxt's range at the tail's END.
        probe_end = p + len(tail_conv)
        frac = min(1.0, probe_end / len(nxt_ans))
        cs, ce = cur.get("start"), cur.get("end")
        ns, ne = nxt.get("start"), nxt.get("end")
        if None in (cs, ce, ns, ne) or not (ne > ns):
            continue
        new_end = ns + (ne - ns) * frac
        if new_end > ce:
            cur["end"] = new_end
            cur["end_label"] = fmt_label(new_end)
        for g, tag in ((cur, "答案溢出至下一段"), (nxt, "開頭為前題答案溢出")):
            g["notes"] = (g.get("notes") or "") + f" | html-resplit:{tag}，待人工確認"
            g["meta"] = {k: v for k, v in (g.get("meta") or {}).items()
                         if k != "lastPlayed"}
            g["status"] = "auto"
        fixed += 1
    return fixed


def resplit_session(sess: dict, qmap: dict) -> Tuple[List[dict], dict]:
    sid = sess["session_id"]
    old = sess.get("segments") or []
    pieces, unresolved = session_pieces(old, qmap)
    runs = runs_from_pieces(pieces)

    new: List[dict] = []
    changed = erased = merged = split_from = 0
    for run in runs:
        seg = compose_run(sid, run, qmap)
        if len(run) == 1 and run[0].whole:
            new.append(seg)
            continue
        changed += 1
        if any(not p.whole for p in run):
            split_from += 1
        if len(run) > 1:
            merged += len(run)
        if any((m.get("meta") or {}).get("lastPlayed") for m in
               (p.seg for p in run)):
            erased += 1
        new.append(seg)

    fixed = apply_spillover(new, qmap)
    if fixed:
        changed += fixed

    for i, seg in enumerate(new, start=1):
        seg["index"] = i
        seg["question_id"] = question_id(sid, i, seg.get("q_text") or "")
        seg["stable_key"] = f"{sid}#{i}"
        qp = seg.get("q_text") or ""
        ap = seg.get("answer_text") or ""
        seg["q_preview"] = qp[:100] + ("…" if len(qp) > 100 else "")
        seg["answer_preview"] = ap[:160] + ("…" if len(ap) > 160 else "")
        seg.pop("locked", None)

    info = {"changed": changed, "erased_lastPlayed": erased,
            "merged_members": merged, "split_runs": split_from,
            "spillover": fixed, "unresolved": unresolved,
            "old_n": len(old), "new_n": len(new)}
    return new, info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="write JSONs back")
    ap.add_argument("--month", action="append", help="YYYY-MM (repeatable)")
    args = ap.parse_args()

    qmap = {q["question_id"]: q for q in json.loads(
        QUESTIONS_JSON.read_text(encoding="utf-8"))}
    print(f"loaded {len(qmap)} ebook questions")

    months = args.month or sorted(p.stem for p in AUDIO_MAP2_DIR.glob("????-??.json"))
    for m in months:
        path = AUDIO_MAP2_DIR / f"{m}.json"
        if not path.exists():
            print(f"!! {m}: no JSON")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))

        tot = dict(changed=0, erased=0, merged=0, split=0, unres=0)
        month_changed = False
        seen_qids: Dict[str, str] = {}
        for sess in data["sessions"]:
            new_segs, info = resplit_session(sess, qmap)
            if new_segs != sess["segments"]:
                month_changed = True
            tot["changed"] += info["changed"]
            tot["erased"] += info["erased_lastPlayed"]
            tot["merged"] += info["merged_members"]
            tot["split"] += info["split_runs"]
            tot["unres"] += len(info["unresolved"])
            if info["new_n"] != info["old_n"] or info["changed"]:
                print(f"  {sess['session_id']}: {info['old_n']} -> {info['new_n']} seg"
                      f"  (runs changed {info['changed']}, split {info['split_runs']},"
                      f" merge-members {info['merged_members']},"
                      f" lastPlayed-erased {info['erased_lastPlayed']})")
            for u in info["unresolved"]:
                print(f"    !! UNRESOLVED {sess['session_id']}#{u.get('index')}"
                      f" qids={u.get('chapter_question_ids')}")
            for seg in new_segs:
                for qid in seg.get("chapter_question_ids") or []:
                    if qid in seen_qids:
                        print(f"    !! DUP qid {qid}:"
                              f" {seen_qids[qid]} & {sess['session_id']}#{seg['index']}")
                    seen_qids[qid] = f"{sess['session_id']}#{seg['index']}"
            sess["segments"] = new_segs

        tot_segs = sum(len(s["segments"]) for s in data["sessions"])
        stats = data.setdefault("stats", {})
        matched = missing = low = interpolated = pending = 0
        for s in data["sessions"]:
            for g in s["segments"]:
                note = g.get("notes") or ""
                if g.get("start") is None:
                    missing += 1
                else:
                    matched += 1
                    if (g.get("confidence") or 0) < 0.5:
                        low += 1
                    if "interpolated" in note:
                        interpolated += 1
                    if "待人工確認" in note or "no-anchor:clamped" in note:
                        pending += 1
        stats.update({"segments": tot_segs, "matched": matched,
                      "missing": missing, "low_conf": low,
                      "interpolated": interpolated, "pending": pending})
        print(f"{m}: seg -> {tot_segs};"
              f" changed-runs {tot['changed']}, split {tot['split']},"
              f" merged-members {tot['merged']}, lastPlayed erased {tot['erased']},"
              f" unresolved {tot['unres']}, pending {pending}, low_conf {low}")

        if not args.apply or not month_changed:
            continue
        data.pop("version_marker", None)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(f"  {m}: WRITTEN")

    if not args.apply:
        print("\n(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
