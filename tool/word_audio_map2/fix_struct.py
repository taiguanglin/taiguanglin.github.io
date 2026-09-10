#!/usr/bin/env python3
"""Strict structural re-alignment of audio_map2 segments against wenda2_ebook
HTML question/answer paragraphs, using EXACT (not fuzzy) normalized matching.

Normalization is length-preserving (whitespace dropped; 著→着; halfwidth→
fullwidth punctuation), so positions map 1:1 back to the raw Word text.  Each
repair only RELOCATES verbatim text that is confirmed present in the segment's
own Word text — nothing is substituted from HTML.

Repairs (in order), each idempotent and lossless:

  1. multi-qid split — a segment carrying >1 qid is sliced at exact HTML
     q_text/a_text boundaries into per-qid segments.
  2. orphan-leak split — a truly-orphan qid whose q_text AND a_text are found
     contiguously inside another segment's answer is split out.
  3. question-readback — a q_text-empty segment whose answer BEGINS with its
     HTML q_text has that prefix moved answer → q_text.
  4. answer-tail spill — an answer tail folded into the NEXT segment's answer
     head is moved back to the previous segment.

Segments with an existing ``meta.lastPlayed`` are never modified (reported only).
Split segments get proportional times, ``status: auto``, and note appended.

Usage:
  .venv/bin/python fix_struct.py [--month YYYY-MM]... [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"
TOOL = Path(__file__).resolve().parent
HTML_QA = json.loads((TOOL / "build" / "html_qa_simp.json").read_text(encoding="utf-8"))

HW2FW = {",": "，", ".": "。", "!": "！", "?": "？", ":": "：", ";": "；",
         "(": "（", ")": "）", "[": "【", "]": "】"}

def nc(c: str) -> str:
    if c == "著":
        return "着"
    return HW2FW.get(c, c)

def nstream(raw: str) -> Tuple[str, List[int]]:
    chars, idx = [], []
    for i, ch in enumerate(raw or ""):
        if ch.isspace():
            continue
        if ch in "\u200b\u200c\u200d\ufeff":   # zero-width / BOM artifacts
            continue
        chars.append(nc(ch))
        idx.append(i)
    return "".join(chars), idx

def norm(s: str) -> str:
    return nstream(s)[0]

def raw_slice(raw: str, idx: List[int], a: int, b: int) -> str:
    """raw text between stream positions [a, b) (b may be len(idx)=end)."""
    if a >= len(idx):
        return ""
    start = idx[a]
    end = idx[b - 1] + 1 if 0 < b <= len(idx) else len(raw)
    return raw[start:end]

def fmt_label(sec: float) -> str:
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = sec % 60
    return f"{h:02d}:{m:02d}:{int(s):02d}.{int(round((s - int(s)) * 1000)):03d}"

def qid_for(sid: str, i: int, qtext: str) -> str:
    h = hashlib.sha1(f"{sid}#{i}#{qtext[:80]}".encode()).hexdigest()[:12]
    return f"question-{h}"

def strip_listen(seg: dict) -> None:
    if "meta" in seg:
        seg["meta"] = {k: v for k, v in seg["meta"].items() if k != "lastPlayed"}

def has_listen(seg: dict) -> bool:
    return bool((seg.get("meta") or {}).get("lastPlayed"))

def add_note(seg: dict, tag: str) -> None:
    if f"html-resplit:{tag}" not in (seg.get("notes") or ""):
        seg["notes"] = ((seg.get("notes") or "") + f" | html-resplit:{tag}，待人工確認").strip(" | ")

def htext(qid: str) -> Tuple[str, str]:
    h = HTML_QA.get(qid)
    if not h:
        return "", ""
    return norm(h["q_text"]), norm(h["a_text"])

def chapter_of(qid: str) -> Optional[int]:
    h = HTML_QA.get(qid)
    return h.get("chapter") if h else None

# globally-computed truly-orphan qids (linked nowhere in the whole corpus)
def compute_truly_orphan() -> set:
    frozen = set()
    for p in AUDIO_MAP2_DIR.glob("????-??.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for s in d.get("sessions") or []:
            for g in s.get("segments") or []:
                frozen.update(g.get("chapter_question_ids") or [])
    return set(HTML_QA) - frozen


def _pieces_match_html(pieces: List[dict]) -> bool:
    """True only if every piece's q_text AND answer_text exactly match its HTML
    question/answer (after normalization) — a safety gate so a split is only
    committed when it produces a perfect 1:1 HTML block."""
    for p in pieces:
        qids = p.get("chapter_question_ids") or []
        if len(qids) != 1:
            return False
        h = HTML_QA.get(qids[0])
        if not h:
            return False
        if norm(p.get("q_text") or "") != norm(h["q_text"]):
            return False
        if norm(p.get("answer_text") or "") != norm(h["a_text"]):
            return False
    return True


def split_segment(seg: dict, qids: List[str]) -> Optional[List[dict]]:
    """Split one segment into per-qid segments at exact boundaries.

    Each qid's q_text and a_text are located (EXACT) with the q_text position
    possibly in q_text or answer_text region.  Returns list of new dicts in
    audio order, or None if any qid's q_text head is not found exactly.
    """
    rawq = seg.get("q_text") or ""
    rawa = seg.get("answer_text") or ""
    # locate each qid's q_text head and a_text head, in region Q or A
    loc: dict = {}
    qs, qidx = nstream(rawq)
    as_, aidx = nstream(rawa)
    for qid in qids:
        hq, ha = htext(qid)
        if not hq:
            return None
        head = hq[:40]
        pq = qs.find(head)
        if pq >= 0:
            region = "Q"; qpos = qidx[pq]
        else:
            pa = as_.find(head)
            if pa < 0:
                return None
            region = "A"; qpos = aidx[pa]
        # a_text head: try answer region first, then question region
        pah = as_.find(ha[:40]) if ha else -1
        if pah >= 0:
            apos = aidx[pah]; aregion = "A"
        else:
            pqh = qs.find(ha[:40]) if ha else -1
            if pqh >= 0:
                apos = qidx[pqh]; aregion = "Q"
            else:
                apos = -1; aregion = region
        loc[qid] = (region, qpos, aregion, apos, hq, ha)

    ordered = sorted(qids, key=lambda q: (0 if loc[q][0] == "Q" else 1, loc[q][1]))
    # question text boundaries: in Q region, sorted qpos; in A region, sorted qpos
    pieces = []
    # Build: for each qid, q slice = from its qpos to next qid's qpos (same region)
    for i, qid in enumerate(ordered):
        region, qpos, aregion, apos, hq, ha = loc[qid]
        nxt_qpos = None
        for q2 in ordered:
            if loc[q2][0] == region and loc[q2][1] > qpos:
                nxt_qpos = loc[q2][1]; break
        if region == "Q":
            q_raw = raw_slice(rawq, qidx, qidx.index(qpos) if qpos in qidx else 0, qidx.index(nxt_qpos) if nxt_qpos else len(rawq))
        else:
            q_raw = raw_slice(rawa, aidx, aidx.index(qpos), aidx.index(nxt_qpos) if nxt_qpos else len(rawa))
        pieces.append([qid, q_raw.strip(), None])

    # answer slicing: for each qid, answer = from its apos to next apos (same aregion) or end
    for i, qid in enumerate(ordered):
        region, qpos, aregion, apos, hq, ha = loc[qid]
        nxt_apos = None
        for q2 in ordered:
            if loc[q2][2] == aregion and loc[q2][3] > apos:
                nxt_apos = loc[q2][3]; break
        if aregion == "A":
            a_raw = raw_slice(rawa, aidx, aidx.index(apos) if apos in aidx else 0, aidx.index(nxt_apos) if nxt_apos else len(rawa))
        else:
            a_raw = raw_slice(rawq, qidx, qidx.index(apos) if apos in qidx else 0, qidx.index(nxt_apos) if nxt_apos else len(rawq))
        pieces[i][2] = a_raw.strip()

    # proportional times
    start, end = seg.get("start"), seg.get("end")
    weights = []
    for qid, qraw, araw in pieces:
        w = len(nstream(qraw)[0]) + len(nstream(araw)[0])
        weights.append(max(w, 1))
    out = []
    acc = start
    total = sum(weights)
    for k, (qid, qraw, araw) in enumerate(pieces):
        w = weights[k]
        acc_end = acc + (end - start) * w / total if (start is not None and end is not None) else None
        if k == len(pieces) - 1:
            acc_end = end
        d = {k: v for k, v in seg.items() if k not in
             ("index", "stable_key", "question_id", "q_preview", "answer_preview",
              "start", "end", "start_label", "end_label", "q_text", "answer_text",
              "chapter_question_ids", "chapter_answer_ids", "chapter_indexes",
              "status", "confidence", "meta", "notes")}
        if "questioner" in seg: d["questioner"] = seg["questioner"]
        if "question_time" in seg: d["question_time"] = seg["question_time"]
        d["q_text"] = qraw
        d["answer_text"] = araw
        d["chapter_question_ids"] = [qid]
        d["chapter_indexes"] = [chapter_of(qid)]
        aid = HTML_QA.get(qid, {}).get("answer_id")
        d["chapter_answer_ids"] = [aid] if aid else []
        d["confidence"] = 0.5
        d["status"] = "auto"
        d["notes"] = "html-resplit: 依 wenda2_ebook 問題邊界重新分段（切分多題段），待人工確認"
        strip_listen(d)
        if start is not None and acc_end is not None:
            d["start"] = round(acc, 2); d["end"] = round(acc_end, 2)
            d["start_label"] = fmt_label(acc); d["end_label"] = fmt_label(acc_end)
        out.append(d)
        acc = acc_end
    return out


def fix_session(sess: dict, truly_orphan: set, force_lastplayed: bool = False) -> dict:
    segs = sess.get("segments") or []
    fixed = {"split_multi": 0, "split_orphan": 0, "readback": 0, "spill": 0, "skipped_listen": 0}
    new: List[dict] = []
    if not force_lastplayed:
        fixed["skipped_listen"] = sum(1 for g in segs if has_listen(g))

    i = 0
    while i < len(segs):
        seg = segs[i]
        qids = seg.get("chapter_question_ids") or []
        locked = has_listen(seg)

        # pass 1+2: multi-qid OR orphan-leak split.  Gather the segment's own
        # frozen qids plus any truly-orphan qid whose q_text head (in Q or A
        # region) and a_text head (in A region) are both found exactly.  Then
        # split into one segment per qid.  Locked (lastPlayed) segments skipped
        # unless --force-lastplayed.
        combined_qids = list(qids)
        if len(qids) == 1 and (not locked or force_lastplayed):
            rawa = seg.get("answer_text") or ""
            rawq = seg.get("q_text") or ""
            as_, _ = nstream(rawa)
            qs, _ = nstream(rawq)
            for oq in truly_orphan:
                hq, ha = htext(oq)
                if not hq or not ha:
                    continue
                q_found = qs.find(hq[:40]) >= 0 or as_.find(hq[:40]) >= 0
                a_found = as_.find(ha[:40]) >= 0
                if q_found and a_found and oq not in combined_qids:
                    combined_qids.append(oq)
        if len(combined_qids) > 1 and (not locked or force_lastplayed):
            sp = split_segment(seg, combined_qids)
            if sp is not None and _pieces_match_html(sp):
                new.extend(sp)
                if len(qids) > 1:
                    fixed["split_multi"] += 1
                else:
                    fixed["split_orphan"] += 1
                i += 1
                continue

        # pass 3: question-readback (q_text empty, answer starts with html q_text)
        if len(qids) == 1 and (not locked or force_lastplayed) and not (seg.get("q_text") or "").strip():
            hq, ha = htext(qids[0])
            as_, aidx = nstream(seg.get("answer_text") or "")
            if hq and as_[:120].startswith(hq):
                # move prefix hq out of answer into q_text
                raw = seg.get("answer_text")
                cut = aidx[len(hq)] if len(hq) <= len(aidx) else len(raw)
                moved = raw[:cut]
                rest = raw[cut:].strip()
                if moved and rest:
                    seg["q_text"] = moved.strip()
                    seg["answer_text"] = rest
                    quota = seg.get("q_text") or ""
                    seg["q_preview"] = quota[:100] + ("…" if len(quota) > 100 else "")
                    ap = seg.get("answer_text") or ""
                    seg["answer_preview"] = ap[:160] + ("…" if len(ap) > 160 else "")
                    add_note(seg, "問題複述移至問題")
                    strip_listen(seg)
                    fixed["readback"] += 1
        new.append(seg)
        i += 1

    # pass 4: answer-tail spill across adjacent segments
    for k in range(len(new) - 1):
        cur, nxt = new[k], new[k + 1]
        cq = cur.get("chapter_question_ids") or [None]
        nq = nxt.get("chapter_question_ids") or [None]
        if not (cq[0] and nq[0]) or ((has_listen(cur) or has_listen(nxt)) and not force_lastplayed):
            continue
        hq, ha = htext(cq[0])
        if not ha:
            continue
        # html answer tail; find its head anywhere in cur, and confirm the
        # OVERFLOW (a fragment after cur's answer end) sits at nxt answer head.
        cur_a = norm(cur.get("answer_text") or "")
        nxt_a = norm(nxt.get("answer_text") or "")
        if not cur_a or not nxt_a:
            continue
        if cur_a.endswith(ha):
            continue  # already complete
        # cur answer is a prefix of ha → find the missing tail
        if not ha.startswith(cur_a):
            continue
        missing = ha[len(cur_a):]  # normalized missing tail
        # nxt answer head must start with missing (exact)
        if not missing or not nxt_a.startswith(missing):
            continue
        # relocate: append raw missing tail to cur answer; strip from nxt head
        # raw missing tail = raw text of nxt answer up to len(missing) kept chars
        nxt_raw = nxt.get("answer_text")
        _, nidx = nstream(nxt_raw)
        cut = nidx[len(missing) - 1] + 1 if len(missing) <= len(nidx) else len(nxt_raw)
        frag = nxt_raw[:cut]
        cur["answer_text"] = (cur.get("answer_text") or "").rstrip() + frag
        nxt["answer_text"] = nxt_raw[cut:].strip()
        for g, tag in ((cur, "答案溢出收回"), (nxt, "去掉前段答案溢出")):
            add_note(g, tag)
            strip_listen(g)
        # adjust boundaries proportionally
        cs, ce = cur.get("start"), cur.get("end")
        ns2, ne = nxt.get("start"), nxt.get("end")
        if all(v is not None for v in (cs, ce, ns2, ne)) and ne > ns2:
            import math
            frac = min(1.0, len(missing) / len(norm(nxt_raw)) if norm(nxt_raw) else 0)
            # time for the moved fragment spans nxt's head; shift boundary
            if ce is not None:
                new_end = ns2 + (ne - ns2) * min(frac, 1.0)
                cur["end"] = round(new_end, 2); cur["end_label"] = fmt_label(new_end)
                nxt["start"] = round(new_end, 2); nxt["start_label"] = fmt_label(new_end)
        fixed["spill"] += 1

    # pass 5: forward read-back — part of the NEXT question was read at the END
    # of this segment's answer, while the next segment's q_text holds the rest
    # (often a trailing greeting).  Rejoin: nxt.q_text = cur.answer-tail read-back
    # + nxt's old q_text, so it exactly equals the html q_text.
    for k in range(len(new) - 1):
        cur, nxt = new[k], new[k + 1]
        cq = cur.get("chapter_question_ids") or [None]
        nq = nxt.get("chapter_question_ids") or [None]
        if not (cq[0] and nq[0]) or ((has_listen(cur) or has_listen(nxt)) and not force_lastplayed):
            continue
        nhq, nha = htext(nq[0])
        if not nhq:
            continue
        if norm(nxt.get("q_text") or "") == nhq:
            continue  # already correct
        nxt_q_old = norm(nxt.get("q_text") or "")
        # the old q_text must be the TAIL of html q_text (read-back head is missing)
        if nxt_q_old and not nhq.endswith(nxt_q_old):
            # maybe old q_text is empty-ish greeting; try empty case below
            if nxt_q_old.strip():
                continue
        missing_head = nhq[:-len(nxt_q_old)] if nxt_q_old else nhq
        if not missing_head:
            continue
        ca = norm(cur.get("answer_text") or "")
        if not ca.endswith(missing_head):
            continue
        cut = len(ca) - len(missing_head)
        raw_cur = cur.get("answer_text")
        _, cidx = nstream(raw_cur)
        raw_cut = cidx[cut] if cut < len(cidx) else len(raw_cur)
        readback = raw_cur[raw_cut:].strip()
        remainder = raw_cur[:raw_cut].strip()
        if not readback or not remainder:
            continue
        old_nxt_q = nxt.get("q_text") or ""
        cur["answer_text"] = remainder
        nxt["q_text"] = (readback + ("\n" + old_nxt_q if old_nxt_q else "")).strip()
        ok = (norm(cur["answer_text"]) == htext(cq[0])[1]
              and norm(nxt["q_text"]) == nhq)
        if not ok:
            cur["answer_text"] = raw_cur
            nxt["q_text"] = old_nxt_q
            continue
        qp = nxt.get("q_text") or ""
        nxt["q_preview"] = qp[:100] + ("…" if len(qp) > 100 else "")
        for g, tag in ((cur, "前題複述移回後段"), (nxt, "補回問題文字")):
            add_note(g, tag)
            strip_listen(g)
        fixed["readback"] += 1

    return new, fixed


def renumber(sid: str, segs: List[dict]) -> None:
    for i, g in enumerate(segs, start=1):
        qp = g.get("q_text") or ""; ap = g.get("answer_text") or ""
        g["index"] = i
        g["question_id"] = qid_for(sid, i, qp)
        g["stable_key"] = f"{sid}#{i}"
        g["q_preview"] = qp[:100] + ("…" if len(qp) > 100 else "")
        g["answer_preview"] = ap[:160] + ("…" if len(ap) > 160 else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--month", action="append")
    ap.add_argument("--force-lastplayed", action="store_true",
                    help="allow fixing segments that already have meta.lastPlayed "
                         "(earases their listened flag)")
    args = ap.parse_args()
    global force_lastplayed
    force_lastplayed = args.force_lastplayed

    truly_orphan = compute_truly_orphan()
    print(f"truly-orphan qids: {len(truly_orphan)}")

    months = args.month or sorted(p.stem for p in AUDIO_MAP2_DIR.glob("????-??.json"))
    for m in months:
        path = AUDIO_MAP2_DIR / f"{m}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        tot = {"split_multi": 0, "split_orphan": 0, "readback": 0, "spill": 0, "skipped_listen": 0}
        changed = False
        for sess in data.get("sessions") or []:
            before = json.dumps(sess.get("segments"), ensure_ascii=False, sort_keys=True)
            new, fixed = fix_session(sess, truly_orphan, force_lastplayed)
            renumber(sess["session_id"], new)
            sess["segments"] = new
            if json.dumps(new, ensure_ascii=False, sort_keys=True) != before:
                changed = True
            for k in tot:
                tot[k] += fixed[k]
        print(f"{m}: {tot} changed={changed}")
        if args.apply and changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
            print(f"  {m}: WRITTEN")
    if not args.apply:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())