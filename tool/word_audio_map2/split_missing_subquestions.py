#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split audio_map2 segments that the wenda2_ebook HTML splits into several
question blocks, but the month JSON still keeps as ONE segment (missing split).

Why: the Word-based splitter sometimes glues several ebook questions into one
segment — most visibly multi-part posts whose sub-questions are numbered
(1、/2、/3、 or 1./2./3. or 1:/2:/3: …).  The ebook is the unit the play
buttons are injected at (one button per question/answer block), so the HTML is
the segmentation source of truth; a segment that covers several blocks cannot
carry per-question time ranges.

Detection (per session, all months):
  * every ebook block (chapters 01–12) claims a segment when BOTH its question
    head AND its answer head locate inside that segment (OpenCC-normalized
    kept chars; leading date/time header lines stripped from the question
    probe; 8-gram candidate index + difflib fuzzy fallback tolerates
    著/着-style variants);
  * a question head that only locates inside the ANSWER text is a read-back
    (師父 re-read the sub-question inside his answer): the piece gets an empty
    q_text and its answer slice starts at the read-back, like
    resplit_by_html.split_segment;
  * duplicate questions (same text asked twice, answers differ — a few pairs
    exist) are disambiguated by the answer-head check: only the block whose
    answer matches the segment claims it.  True same-text duplicates (same
    question AND same answer, e.g. 12#471/12#472) share one audio range: both
    qids are frozen on the SAME piece instead of fabricating a split;
  * a segment is a split target when ≥2 distinct blocks claim it (at carve
    positions that actually differ); a merge target when one block's question
    spans several consecutive segments (情況-only chunk + 子題 chunk, or a
    whole thread posted as several back-and-forth posts);
  * transitional lines stuck at the end of one segment's answer that belong to
    the NEXT segment's question text (per the ebook block) are moved
    (text-align).

Fix (mirror of resplit_by_html.py / fix_2025_05_12_seg74.py conventions):
  * q_text sliced at the located question-head raw positions; the shared
    leading region (date header / shared 情况) is kept on every piece whose
    ebook block itself carries it (prefix-walk divergence bound);
  * answer_text sliced at the located answer-head raw positions (unmatched
    prefix goes to the first piece, whole answer to the last piece when no
    answer head locates);
  * times proportional to kept-text weight, first piece keeps start, last
    keeps end;
  * each piece carries its block's chapter_question_ids / chapter_answer_ids /
    chapter_indexes (a merged group for same-text duplicates);
  * status=auto, confidence capped at 0.5, meta.lastPlayed dropped (must be
    re-listened — injection is lastPlayed-gated), html_verbatim dropped
    (re-run mark_html_diff.py to recompute), notes appended 待人工確認;
  * session renumbered (index, stable_key, question_id, previews, labels);
    month stats recomputed.

READ-ONLY by default; --apply writes the JSONs.  Months are processed from
the newest (2025-05) down to the oldest (2024-02).

Usage:
  .venv/bin/python split_missing_subquestions.py                 # audit all
  .venv/bin/python split_missing_subquestions.py --month 2025-03 # one month
  .venv/bin/python split_missing_subquestions.py --month 2025-03 --apply
  .venv/bin/python split_missing_subquestions.py --report /tmp/report.json
"""

from __future__ import annotations

import argparse
import difflib
import html as htmlmod
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from resplit_by_html import (  # shared conventions
    AUDIO_MAP2_DIR,
    KEPT,
    fmt_label,
    kept_stream,
    question_id,
)

ROOT = Path(__file__).resolve().parents[2]
EBOOK_DIR = ROOT / "wenda2_ebook"
CHAPTERS = range(1, 13)

# --------------------------------------------------------------------------
# HTML block extraction (document order, duplicates kept)
# --------------------------------------------------------------------------

OPENER_RE = re.compile(
    r'<div class="(?:question|answer)" id="((?:question|answer)-[0-9a-f]+)">'
    r'|<p id="(content-[0-9a-f]+)">'
)
Q_TEXT_DIV_RE = re.compile(r'<div class="question-text">(.*?)</div>', re.S)
A_TEXT_DIV_RE = re.compile(r'<div class="answer-text">(.*?)</div>', re.S)
P_TEXT_RE = re.compile(r'<p id="content-[0-9a-f]+">(.*?)</p>', re.S)


def strip_tags(fragment: str) -> str:
    txt = re.sub(r"<br\s*/?>", "\n", fragment or "")
    txt = re.sub(r"<[^>]+>", "", txt)
    return htmlmod.unescape(txt).strip()


class Block:
    __slots__ = ("chapter", "order", "qid", "aid", "q_text", "a_text")

    def __init__(self, chapter: int, order: int, qid: str, aid: Optional[str],
                 q_text: str, a_text: str):
        self.chapter = chapter
        self.order = order
        self.qid = qid
        self.aid = aid
        self.q_text = q_text
        self.a_text = a_text


def load_blocks() -> List[Block]:
    """Every question block of wenda2_ebook chapters 01–12, in document order.

    Duplicate question ids (the ebook reusing one ``question-…`` id in two
    chapters) are kept as separate entries; questions answered by a
    ``<p id="content-…">`` block get that id as their answer id; questions
    with no answer block keep ``aid=None``.
    """
    blocks: List[Block] = []
    for ch in CHAPTERS:
        path = EBOOK_DIR / f"{ch:02d}.html"
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8")
        opens = []
        for m in OPENER_RE.finditer(raw):
            if m.group(1):
                typ = "question" if m.group(1).startswith("question-") else "answer"
                full_id = m.group(1)
            else:
                typ, full_id = "content", m.group(2)
            opens.append((m.start(), typ, full_id))
        n_ch = 0
        for i, (pos, typ, full_id) in enumerate(opens):
            if typ != "question":
                continue
            n_ch += 1
            nxt = opens[i + 1][0] if i + 1 < len(opens) else len(raw)
            region = raw[pos:nxt]
            qm = Q_TEXT_DIV_RE.search(region)
            q_text = strip_tags(qm.group(1)) if qm else ""
            aid, a_text = None, ""
            for j in range(i + 1, len(opens)):
                t2, fid2 = opens[j][1], opens[j][2]
                if t2 == "question":
                    break
                a_start = opens[j][0]
                a_end = opens[j + 1][0] if j + 1 < len(opens) else len(raw)
                a_region = raw[a_start:a_end]
                aid = fid2
                if t2 == "answer":
                    am = A_TEXT_DIV_RE.search(a_region)
                    a_text = strip_tags(am.group(1)) if am else ""
                else:
                    pm = P_TEXT_RE.search(a_region)
                    a_text = strip_tags(pm.group(1)) if pm else ""
                break
            blocks.append(Block(ch, n_ch, full_id, aid, q_text, a_text))
    return blocks


# --------------------------------------------------------------------------
# probes (question / answer heads), gram index, locate
# --------------------------------------------------------------------------

DATE_LINE_RE = re.compile(r"^[\d\s\-/:.．年月日]+$")
DATELIKE_RE = re.compile(r"\d{1,4}\s*[-:/.年]\s*\d{1,2}")

# 1:1 character normalizations applied to BOTH probe and stream, on top of the
# OpenCC t2s pass.  OpenCC conservatively keeps 著 in words like 执著/念著 while
# the Word text uses 着; the replacement is length-preserving so every stream
# index stays valid.
NORM1 = str.maketrans({"著": "着", "麽": "么", "妳": "你", "牠": "它", "祢": "你"})


def norm1(s: str) -> str:
    return (s or "").translate(NORM1)


def has_datelike(line: str) -> bool:
    ln = (line or "").strip()
    return bool(ln) and bool(DATE_LINE_RE.match(ln)) and bool(DATELIKE_RE.search(ln))


def strip_header_lines(q_text: str) -> str:
    """Drop leading date/time-only lines (e.g. ``2025-0315 18:09``)."""
    lines = (q_text or "").splitlines()
    i = 0
    while i < len(lines) and has_datelike(lines[i]):
        i += 1
    return "\n".join(lines[i:])


def q_probe_of(block: Block) -> str:
    body = strip_header_lines(block.q_text)
    src = body if body.strip() else (block.q_text or "")
    stream, _ = kept_stream(src[:400])
    if len(stream) < 6:
        stream, _ = kept_stream((block.a_text or "")[:400])
        return stream[:48]
    return stream[:80]


def a_probe_of(block: Block) -> str:
    stream, _ = kept_stream((block.a_text or "")[:400])
    return stream[:48]


def gram_index(probes: List[str]) -> Dict[str, set]:
    """8-char (step 4) → block-index candidate index."""
    idx: Dict[str, set] = defaultdict(set)
    for bi, p in enumerate(probes):
        if len(p) < 8:
            continue
        for i in range(0, len(p) - 7, 4):
            idx[p[i:i + 8]].add(bi)
    return idx


def locate_blocks(stream: str, gidx8: Dict[str, set], probes: List[str],
                  short_idx: Dict[int, str]
                  ) -> Tuple[Dict[int, List[int]], Dict[int, Tuple[int, float]]]:
    """Exact + fuzzy hits of block probes inside one kept-char stream.

    Returns ``(exact: block → [stream positions], fuzzy: block → (pos, ratio))``.
    ``probes``/``short_idx`` are already ``norm1``-normalized; the stream is
    normalized here (length-preserving, so positions map 1:1).
    """
    snorm = norm1(stream)
    exact: Dict[int, List[int]] = defaultdict(list)
    grampos: Dict[int, List[int]] = defaultdict(list)
    n = len(snorm)
    for i in range(0, max(0, n - 7)):
        cands = gidx8.get(snorm[i:i + 8])
        if not cands:
            continue
        for bi in cands:
            grampos[bi].append(i)
            p = probes[bi]
            if p and snorm.startswith(p, i):
                exact[bi].append(i)
    for bi, p in short_idx.items():
        if not p:
            continue
        frm = 0
        while True:
            j = snorm.find(p, frm)
            if j < 0:
                break
            exact[bi].append(j)
            frm = j + 1
    fuzzy: Dict[int, Tuple[int, float]] = {}
    for bi, positions in grampos.items():
        if bi in exact or len(positions) < 2:
            continue
        p = probes[bi]
        if not p or len(p) < 12:
            continue
        best, best_i = 0.0, -1
        for i in positions[:24]:
            r = difflib.SequenceMatcher(None, p, snorm[i:i + len(p)]).ratio()
            if r > best:
                best, best_i = r, i
        if best >= 0.85 and best_i >= 0:
            fuzzy[bi] = (best_i, best)
    return exact, fuzzy


# --------------------------------------------------------------------------
# claims
# --------------------------------------------------------------------------

class Group:
    __slots__ = ("blocks", "kind", "pos", "apos", "q_exact", "a_exact")

    def __init__(self, blocks: List[int], kind: str, pos: Optional[int],
                 apos: Optional[int], q_exact: bool, a_exact: bool):
        self.blocks = blocks          # block indices (group = same-text dupes)
        self.kind = kind              # "Q" | "RB" | "AONLY"
        self.pos = pos                # stream idx in q_text (Q) / answer_text (RB)
        self.apos = apos              # stream idx in answer_text of the a probe
        self.q_exact = q_exact
        self.a_exact = a_exact


def segment_claims(seg: dict, ctx: dict):
    """Claim groups for one segment + kept streams + ambiguity flag.

    Returns ``(all_groups, carve_groups, (qstream, qraw, astream, araw),
    ambig, dropped)``.  ``all_groups`` feeds merge detection; ``carve_groups``
    (answer head present / read-back / frozen) drives splitting and links.
    """
    q_text = seg.get("q_text") or ""
    a_text = seg.get("answer_text") or ""
    qstream, qraw = kept_stream(q_text)
    astream, araw = kept_stream(a_text)
    blocks = ctx["blocks"]
    qprobes, aprobes = ctx["qprobes"], ctx["aprobe"]
    keptq, kepta = ctx["keptq"], ctx["kepta"]
    frozen = set(seg.get("chapter_question_ids") or [])

    q_ex, q_fz = locate_blocks(qstream, ctx["qgidx8"], qprobes, ctx["short_q_idx"])
    rb_ex, rb_fz = locate_blocks(astream, ctx["qgidx8"], qprobes, ctx["short_q_idx"])
    a_ex, a_fz = locate_blocks(astream, ctx["agidx8"], aprobes, ctx["short_a_idx"])

    # Blocks without an answer get no injected play button, so they must never
    # define a question boundary (the ebook occasionally stores the master's
    # reply as an answer-less "question" block).
    usable = ctx["usable"]

    def apos_of(bi: int) -> Optional[int]:
        if bi in a_ex:
            return a_ex[bi][0]
        if bi in a_fz:
            return a_fz[bi][0]
        return None

    recs: Dict[int, dict] = {}

    def add_rec(bi: int, kind: str, pos, apos, q_exact: bool, a_exact: bool) -> None:
        if bi not in usable:
            return
        r = recs.get(bi)
        if r is None:
            recs[bi] = {"kind": kind, "pos": pos, "apos": apos,
                        "q_exact": q_exact, "a_exact": a_exact}
        elif kind == "Q" and r["kind"] != "Q":
            # the Q-region hit wins over a read-back of the same question
            recs[bi] = {"kind": "Q", "pos": pos, "apos": apos,
                        "q_exact": q_exact, "a_exact": a_exact}

    for bi, positions in q_ex.items():
        add_rec(bi, "Q", positions[0], apos_of(bi), True, bi in a_ex)
    for bi, (pos, _r) in q_fz.items():
        add_rec(bi, "Q", pos, apos_of(bi), False, bi in a_ex)
    for bi, positions in rb_ex.items():
        if bi in recs:
            continue
        add_rec(bi, "RB", positions[0], apos_of(bi), True, bi in a_ex)
    for bi, (pos, _r) in rb_fz.items():
        if bi in recs:
            continue
        add_rec(bi, "RB", pos, apos_of(bi), False, bi in a_ex)
    # Answer head located but the question head nowhere in this segment: either
    # a 问题缺失 block (short probe) or the answer half of a block whose question
    # text sits in a previous segment — the latter is a merge candidate, so it
    # must appear in ``all_groups`` (but never carves a boundary here).
    for bi in set(a_ex) | set(a_fz):
        if bi in recs:
            continue
        apos = apos_of(bi)
        if apos is None:
            continue
        kind = "AP" if len(qprobes[bi]) >= 8 else "AONLY"
        add_rec(bi, kind, None, apos, False, bi in a_ex)

    # ---- group duplicates: identical (keptq, kepta) → one claim; same keptq
    #      with different answers (duplicate questions) → answer-head decides
    by_kq: Dict[str, List[Tuple[int, dict]]] = defaultdict(list)
    for bi, r in recs.items():
        by_kq[keptq[bi]].append((bi, r))
    groups: List[Group] = []
    ambig = False
    for _kq, members in by_kq.items():
        if len(members) == 1:
            bi, r = members[0]
            groups.append(Group([bi], r["kind"], r["pos"], r["apos"],
                                r["q_exact"], r["a_exact"]))
            continue
        by_ka: Dict[Tuple[str, str], List[Tuple[int, dict]]] = defaultdict(list)
        for bi, r in members:
            by_ka[(keptq[bi], kepta[bi])].append((bi, r))
        if len(by_ka) == 1:
            # identical question AND answer → one claim, both qids share it
            bis = [bi for bi, _r in members]
            r0 = members[0][1]
            groups.append(Group(bis, r0["kind"], r0["pos"], r0["apos"],
                                r0["q_exact"], r0["a_exact"]))
            continue
        with_a = [(bi, r) for bi, r in members if r["apos"] is not None]
        frozen_here = [x for x in members if blocks[x[0]].qid in frozen]
        if len(with_a) == 1:
            bi, r = with_a[0]
            groups.append(Group([bi], r["kind"], r["pos"], r["apos"],
                                r["q_exact"], r["a_exact"]))
        elif len(with_a) > 1:
            ambig = True   # same text, several matching answers — manual decision
        elif frozen_here:
            bi, r = frozen_here[0]
            groups.append(Group([bi], r["kind"], r["pos"], None,
                                r["q_exact"], False))
        # else: no claim — reported

    # ---- a claim carves a question boundary only when its answer head is in
    #      this segment, or it is a read-back / 问题缺失 block, or the segment
    #      is already frozen to it.  Near-duplicate questions (same wording,
    #      different answer, item 3) whose answer lives elsewhere must NOT
    #      fabricate a second piece.
    carve: List[Group] = []
    dropped: List[Group] = []
    for g in groups:
        qids = [blocks[bi].qid for bi in g.blocks]
        if g.kind == "AP":
            # answer half of a block whose question text is in another segment:
            # reported (merge detection reads all_groups) but never carved
            dropped.append(g)
        elif (g.apos is not None or g.kind in ("RB", "AONLY")
                or any(q in frozen for q in qids)):
            carve.append(g)
        else:
            dropped.append(g)
    return groups, carve, (qstream, qraw, astream, araw), ambig, dropped


# --------------------------------------------------------------------------
# split
# --------------------------------------------------------------------------

def lcp(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def raw_of(si: Optional[int], idx_map: List[int], total: int) -> int:
    """Raw index for a kept-stream index (clamped)."""
    if si is None or si < 0:
        return 0
    if si >= len(idx_map):
        return total
    return idx_map[si]


def split_plan(where: Tuple[str, str, int], seg: dict, groups: List[Group],
               ctx: dict) -> Tuple[Optional[List[dict]], List[str], List[dict]]:
    """Slice a multi-claim segment into per-question pieces (HTML-driven).

    Returns ``(pieces or None, problems, per-piece diagnostics)``.  ``problems``
    is non-empty when the shape cannot be carved faithfully (degenerate
    duplicate offsets, colliding answer bounds, or pieces whose kept text does
    not match the ebook block) — the caller then leaves the segment alone.
    """
    q_text = seg.get("q_text") or ""
    a_text = seg.get("answer_text") or ""
    blocks = ctx["blocks"]
    keptq, kepta = ctx["keptq"], ctx["kepta"]
    month, sid, _idx0 = where

    q_groups = [g for g in groups if g.kind == "Q"]
    rb_groups = [g for g in groups if g.kind == "RB"]
    ao_groups = [g for g in groups if g.kind == "AONLY"]
    if len(q_groups) + len(rb_groups) + len(ao_groups) < 2:
        return None, ["少於兩個 claim"], []

    qstream, qraw = kept_stream(q_text)
    astream, araw = kept_stream(a_text)

    # ---- unique-tail starts (stream indices) for Q groups; groups probing the
    #      same position share a prefix — the pairwise LCP bounds the unique tail
    uts: Dict[int, int] = {}
    for g in q_groups:
        others = [h for h in q_groups if h is not g and h.pos == g.pos]
        if others:
            kq = keptq[g.blocks[0]]
            d = min(lcp(kq, keptq[h.blocks[0]]) for h in others)
            uts[id(g)] = (g.pos or 0) + d
        else:
            uts[id(g)] = g.pos if g.pos is not None else 0
    starts = sorted({uts[id(g)] for g in q_groups})
    if len(starts) != len(uts):
        return None, ["unique-tail 起點重疊"], []   # AMBIG
    boundaries = starts + [len(qstream)]

    # ---- answer starts (stream indices) per group
    a_starts: List[Tuple[int, Group]] = []
    for g in q_groups:
        if g.apos is not None:
            a_starts.append((g.apos, g))
    for g in rb_groups:
        a_starts.append((g.pos if g.pos is not None else 0, g))
    for g in ao_groups:
        if g.apos is not None:
            a_starts.append((g.apos, g))
    a_starts.sort(key=lambda t: t[0])
    a_pos_list = [t[0] for t in a_starts]
    if len(a_pos_list) != len(set(a_pos_list)):
        return None, ["答案起點重疊"], []   # AMBIG

    # ---- q pieces
    q_pieces: Dict[int, str] = {}
    ordered_q = sorted(q_groups, key=lambda g: uts[id(g)])
    for idx, g in enumerate(ordered_q):
        us = uts[id(g)]
        end = boundaries[idx + 1]
        kq = keptq[g.blocks[0]]
        S = lcp(qstream, kq)                       # shared-prefix bound (stream)
        us_raw = raw_of(us, qraw, len(q_text))
        end_raw = raw_of(end, qraw, len(q_text))
        # The gap [inc, us) is covered by the *previous* piece's interval, so a
        # shared prefix is enough for later pieces.  The first piece has no
        # predecessor: it must span [0, end) in full (inc = us_raw), otherwise
        # the leading read-back text would be silently dropped.
        inc = (us_raw if idx == 0
               else min(raw_of(S, qraw, len(q_text)), us_raw))
        q_pieces[id(g)] = (q_text[:inc] + q_text[us_raw:end_raw]).strip()
    for g in rb_groups + ao_groups:
        q_pieces[id(g)] = ""

    # ---- answer pieces
    a_pieces: Dict[int, str] = {id(g): "" for g in groups}
    if a_pos_list:
        a_bounds = a_pos_list + [len(astream)]
        for idx, (apos, g) in enumerate(a_starts):
            end_a = a_bounds[idx + 1]
            a0 = raw_of(apos, araw, len(a_text))
            a1 = raw_of(end_a, araw, len(a_text))
            a_pieces[id(g)] = a_text[a0:a1].strip()
        head = a_text[:raw_of(a_pos_list[0], araw, len(a_text))].strip()
        if head:
            first_g = a_starts[0][1]
            a_pieces[id(first_g)] = (head + "\n\n" + a_pieces[id(first_g)]).strip()
    elif a_text.strip():
        last_g = ordered_q[-1] if ordered_q else \
            (rb_groups[-1] if rb_groups else ao_groups[-1])
        a_pieces[id(last_g)] = a_text.strip()

    # ---- piece order: Q by unique-tail start, then RB / AONLY by answer start
    ordered = ordered_q + \
        sorted(rb_groups, key=lambda g: g.pos if g.pos is not None else 0) + \
        sorted(ao_groups, key=lambda g: g.apos if g.apos is not None else 0)

    # ---- times proportional to kept weight
    start, end = seg.get("start"), seg.get("end")
    weights: List[int] = []
    for g in ordered:
        w = len(KEPT.findall(q_pieces.get(id(g), ""))) + \
            len(KEPT.findall(a_pieces.get(id(g), "")))
        weights.append(max(w, 1))
    total_w = sum(weights)
    if start is not None and end is not None:
        span = end - start
        t_starts: List[Optional[float]] = []
        t_ends: List[Optional[float]] = []
        cum = 0.0
        for w in weights:
            t0 = start + span * (cum / total_w)
            cum += w
            t1 = start + span * (cum / total_w)
            t_starts.append(round(t0, 3))
            t_ends.append(round(t1, 3))
        t_starts[0], t_ends[-1] = start, end
    else:
        t_starts = [start] * len(ordered)
        t_ends = [end] * len(ordered)

    # ---- piece dicts
    seg_meta = {k: v for k, v in (seg.get("meta") or {}).items()
                if k != "lastPlayed"}
    base_notes = seg.get("notes") or ""
    frozen = list(seg.get("chapter_question_ids") or [])
    tag = "html-resplit: 依 wenda2_ebook 問題邊界重新分段（切分多題段），待人工確認"
    located_a = {id(t[1]) for t in a_starts}
    out: List[dict] = []
    diags: List[dict] = []
    problems: List[str] = []
    for n, g in enumerate(ordered):
        qids: List[str] = []
        aids: List[str] = []
        chs: List[int] = []
        for bi in g.blocks:
            b = blocks[bi]
            if b.qid not in qids:
                qids.append(b.qid)
            if b.aid and b.aid not in aids:
                aids.append(b.aid)
            if b.chapter not in chs:
                chs.append(b.chapter)
        # attachment safety: a never-frozen qid strongly claimed by another
        # month's segment stays there (avoid cross-session duplicates)
        if len(g.blocks) == 1:
            b = blocks[g.blocks[0]]
            if b.qid not in frozen:
                others = ctx["strong_qid"].get(b.qid, set()) - {where}
                if others:
                    qids, aids, chs = [], [], []
        pq = q_pieces.get(id(g), "")
        pa = a_pieces.get(id(g), "")
        pkq = kept_stream(pq)[0]
        pka = kept_stream(pa)[0]
        b0 = blocks[g.blocks[0]]
        bkq, bka = keptq[g.blocks[0]], kepta[g.blocks[0]]
        # ---- verify the piece against its ebook block (item 4 char check)
        if g.kind == "Q":
            if len(bkq) >= 12:
                r = difflib.SequenceMatcher(None, bkq, pkq).ratio()
                if r < 0.6:
                    problems.append(f"{b0.qid[:12]} q文字比對低 {r:.2f}")
            if id(g) in located_a:
                if len(bka) >= 20:
                    r = difflib.SequenceMatcher(None, bka, pka).ratio()
                    if r < 0.6:
                        problems.append(f"{b0.qid[:12]} a文字比對低 {r:.2f}")
            elif len(bka) >= 40:
                # the block's answer is not in this segment: the block spans
                # segments (the question text was glued to the previous answer)
                # — carving an answerless piece here would fabricate a split
                problems.append(f"{b0.qid[:12]} answer 不在本段（疑似跨段／合併）")
        elif g.kind == "RB":
            whole_b = bkq + bka
            if len(whole_b) >= 20:
                r = difflib.SequenceMatcher(None, whole_b, pka).ratio()
                if r < 0.5:
                    problems.append(f"{b0.qid[:12]} 讀回文字比對低 {r:.2f}")
        else:   # AONLY
            if len(bka) >= 20:
                r = difflib.SequenceMatcher(None, bka, pka).ratio()
                if r < 0.5:
                    problems.append(f"{b0.qid[:12]} 缺題a文字比對低 {r:.2f}")
        if (pkq or pka) == "" and (bkq or bka):
            problems.append(f"{b0.qid[:12]} 空白piece")
        a_expected = (len(bkq) + len(bka)) if g.kind in ("RB", "AONLY") else len(bka)
        diags.append({"qids": qids, "chapter": b0.chapter, "kind": g.kind,
                      "q_kept": len(pkq), "q_block": len(bkq),
                      "a_kept": len(pka), "a_block": len(bka),
                      "dq": (len(pkq) - len(bkq)) if g.kind == "Q" else 0,
                      "da": len(pka) - a_expected})
        p: dict = {
            "questioner": seg.get("questioner"),
            "question_time": seg.get("question_time"),
            "q_text": pq,
            "answer_text": pa,
            "start": t_starts[n],
            "end": t_ends[n],
            "confidence": 0.5,
            "status": "auto",
            "notes": (base_notes + (" | " if base_notes else "") + tag),
            "chapter_question_ids": qids,
            "chapter_indexes": chs,
        }
        if aids:
            p["chapter_answer_ids"] = aids
        if seg.get("srt_preview"):
            p["srt_preview"] = seg["srt_preview"]
        if seg_meta:
            p["meta"] = dict(seg_meta)
        if p["start"] is not None:
            p["start_label"] = fmt_label(p["start"])
        if p["end"] is not None:
            p["end_label"] = fmt_label(p["end"])
        out.append(p)
    if problems:
        return None, problems, diags
    return out, [], diags


def split_pieces(where: Tuple[str, str, int], seg: dict, groups: List[Group],
                 ctx: dict) -> Optional[List[dict]]:
    """Carve a multi-claim segment; None when the shape is not faithful."""
    pieces, _problems, _diags = split_plan(where, seg, groups, ctx)
    return pieces


# --------------------------------------------------------------------------
# link fix
# --------------------------------------------------------------------------

LINK_TAG = "html-resplit: 修正章節對應（依 wenda2_ebook block），待人工確認"
QA_TAG = "html-resplit: 依 block 邊界把誤置於問題欄的答案文字移入答案欄，待人工確認"


def qa_boundary_plan(seg: dict, g: Group, ctx: dict) -> Optional[int]:
    """Raw cut index when answer text leaked into ``q_text`` (else ``None``)."""
    if g.kind != "Q" or g.pos is None:
        return None
    bi = g.blocks[0]
    bkq, bka = ctx["keptq"][bi], ctx["kepta"][bi]
    if len(bkq) < 20 or len(bka) < 40:
        return None
    q_text = seg.get("q_text") or ""
    qstream, qraw = kept_stream(q_text)
    cut = g.pos + len(bkq)
    if cut >= len(qstream) - 40:          # little or nothing leaked
        return None
    # the located block question must really occupy [pos, pos+len(bkq))
    if difflib.SequenceMatcher(
            None, bkq, qstream[g.pos:cut]).ratio() < 0.6:
        return None
    tail = qstream[cut:]
    if len(tail) < 60:
        return None
    # …and the leaked tail must match the head of the block's answer
    if difflib.SequenceMatcher(
            None, bka[:len(tail)], tail).ratio() < 0.6:
        return None
    return qraw[cut]


def qa_boundary_fix(seg: dict, g: Group, ctx: dict) -> bool:
    """Move answer text the Word parser left inside ``q_text`` down into
    ``answer_text``, using the ebook block's q/a boundary (HTML-authoritative).

    Only fires when the excess tail provably matches the head of the block's
    own answer, so the segment's text is preserved in full.
    """
    raw_cut = qa_boundary_plan(seg, g, ctx)
    if raw_cut is None:
        return False
    q_text = seg.get("q_text") or ""
    moved = q_text[raw_cut:].strip()
    rest = q_text[:raw_cut].strip()
    if not moved or not rest:
        return False
    seg["q_text"] = rest
    seg["answer_text"] = (moved + "\n\n"
                          + (seg.get("answer_text") or "").lstrip()).strip()
    seg["notes"] = ((seg.get("notes") or "")
                    + (" | " if seg.get("notes") else "") + QA_TAG)
    seg["meta"] = {k: v for k, v in (seg.get("meta") or {}).items()
                   if k != "lastPlayed"}
    seg["status"] = "auto"
    seg["confidence"] = min(seg.get("confidence") or 0.5, 0.5)
    seg.pop("html_verbatim", None)
    return True


def link_fix_ok(g: Group) -> bool:
    """Relink only on a confident claim: an exactly matched question head, or
    an answer-only / read-back shape whose answer head matched exactly."""
    if g.q_exact:
        return True
    if g.kind in ("AONLY", "VB", "RB") and g.a_exact:
        return True
    return False


def fix_links(where: Tuple[str, str, int], seg: dict, g: Group, ctx: dict,
              own: Optional[set] = None) -> bool:
    """Rewrite the segment's chapter links to its claimed block (1 claim)."""
    blocks = ctx["blocks"]
    frozen = list(seg.get("chapter_question_ids") or [])
    claimed_qids: List[str] = []
    for bi in g.blocks:
        qid = blocks[bi].qid
        if qid not in claimed_qids:
            claimed_qids.append(qid)
    claimed_set = set(claimed_qids)
    frozen_set = set(frozen)
    aids: List[str] = []
    chs: List[int] = []
    for bi in g.blocks:
        b = blocks[bi]
        if b.aid and b.aid not in aids:
            aids.append(b.aid)
        if b.chapter not in chs:
            chs.append(b.chapter)
    if frozen_set == claimed_set:
        # same qids — only the answer ids may differ (cross-chapter qid reuse)
        frozen_aids = seg.get("chapter_answer_ids") or []
        if (frozen_aids and set(frozen_aids) == set(aids)) or (not frozen_aids and not aids):
            return False
        seg["chapter_answer_ids"] = aids
        seg["chapter_indexes"] = chs
        seg["notes"] = (seg.get("notes") or "") + (" | " if seg.get("notes") else "") + LINK_TAG
        seg["meta"] = {k: v for k, v in (seg.get("meta") or {}).items()
                       if k != "lastPlayed"}
        seg["status"] = "auto"
        seg.pop("html_verbatim", None)
        return True
    # A frozen qid that ANOTHER segment claims is not lost by dropping it here —
    # this is what makes clean swaps (segments holding each other's qid) work.
    # Any other frozen qid stays (zero-loss), and new qids attach only when no
    # other segment strongly claims them.  A frozen qid whose block text does
    # not match this segment at all (``own``) is a stale link: it is dropped
    # once some other segment provably owns it.
    idx = where[2]
    cov = ctx.get("covered") or {}
    cov_a = ctx.get("covered_ans") or {}
    own = own or set()
    own_aids: set = set()
    for q in own:
        for bi in ctx["blocks_by_qid"].get(q) or []:
            b = blocks[bi]
            if b.aid:
                own_aids.add(b.aid)

    def elsewhere(q: str) -> bool:
        return not (cov.get(q, set()) - {where})

    keep = [q for q in frozen
            if q not in claimed_set
            and (elsewhere(q) or q in own)]
    attach: List[str] = []
    for q in claimed_qids:
        if q in frozen_set:
            attach.append(q)
            continue
        others = ctx["strong_qid"].get(q, set()) - {where}
        if not others:
            attach.append(q)
    final: List[str] = []
    for q in attach + keep:
        if q not in final:
            final.append(q)
    keep_aids = [a for a in (seg.get("chapter_answer_ids") or [])
                 if a not in set(aids)
                 and (not (cov_a.get(a, set()) - {where}) or a in own_aids)]
    final_aids = aids + keep_aids
    if final == frozen and (not aids or final_aids == (seg.get("chapter_answer_ids") or [])):
        return False
    seg["chapter_question_ids"] = final
    if final_aids:
        seg["chapter_answer_ids"] = final_aids
    seg["chapter_indexes"] = chs
    seg["notes"] = (seg.get("notes") or "") + (" | " if seg.get("notes") else "") + LINK_TAG
    seg["meta"] = {k: v for k, v in (seg.get("meta") or {}).items()
                   if k != "lastPlayed"}
    seg["status"] = "auto"
    seg.pop("html_verbatim", None)
    return True


# --------------------------------------------------------------------------
# merge
# --------------------------------------------------------------------------

class MergeCand:
    __slots__ = ("start_i", "end_i", "blocks")

    def __init__(self, start_i: int, end_i: int, blocks: List[int]):
        self.start_i = start_i
        self.end_i = end_i
        self.blocks = blocks


def find_merges(sid: str, segs: List[dict], seg_groups: List[List[Group]],
                ctx: dict) -> List[MergeCand]:
    """Block-level merge candidates: one block's question spans consecutive
    segments (情況-only chunk + 子題 chunk, or a whole multi-post thread)."""
    keptq, kepta = ctx["keptq"], ctx["kepta"]
    b_qseg: Dict[int, set] = defaultdict(set)
    b_aseg: Dict[int, set] = defaultdict(set)
    for i, groups in enumerate(seg_groups):
        for g in groups:
            for bi in g.blocks:
                if g.kind in ("Q", "RB"):
                    b_qseg[bi].add(i)
                if g.apos is not None:
                    b_aseg[bi].add(i)
    cands: List[MergeCand] = []
    for bi in sorted(b_qseg):
        segs_i = b_qseg[bi]
        if len(segs_i) > 1:
            continue   # block claims several segments (day-over-day repeat)
        i = min(segs_i)
        if segs[i].get("zero"):
            continue
        j_ap = min((j for j in b_aseg.get(bi, ()) if j > i), default=None)
        # smallest m ≥ i whose concatenated q covers the block's kept q
        m = None
        concat = ""
        kq = keptq[bi]
        for k in range(i, min(i + 7, len(segs))):
            concat += kept_stream(segs[k].get("q_text") or "")[0]
            if difflib.SequenceMatcher(None, kq, concat).ratio() >= 0.85:
                m = k
                break
        ends = [x for x in (m, j_ap) if x is not None]
        if not ends:
            continue
        run_end = max(ends)
        if run_end <= i:
            continue
        # guards: no zero members; no foreign block claims inside the run
        ok = True
        for k in range(i, run_end + 1):
            if segs[k].get("zero"):
                ok = False
                break
            for g in seg_groups[k]:
                for b2 in g.blocks:
                    if b2 == bi:
                        continue
                    if (keptq[b2], kepta[b2]) != (kq, kepta[bi]):
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok and kepta[bi]:
            concat_a = "".join(kept_stream(segs[k].get("answer_text") or "")[0]
                               for k in range(i, run_end + 1))
            if difflib.SequenceMatcher(None, kepta[bi], concat_a).ratio() < 0.75:
                ok = False
        if ok:
            cands.append(MergeCand(i, run_end, [bi]))
    return cands


def merge_segments(sid: str, run: List[dict], cand: MergeCand, ctx: dict) -> dict:
    """Merge consecutive segments covering ONE ebook block (envelope times)."""
    blocks = ctx["blocks"]
    first = run[0]
    q_text = "\n".join((s.get("q_text") or "").strip() for s in run
                       if (s.get("q_text") or "").strip())
    a_text = "\n\n".join((s.get("answer_text") or "").strip() for s in run
                         if (s.get("answer_text") or "").strip())
    starts = [s.get("start") for s in run if s.get("start") is not None]
    ends = [s.get("end") for s in run if s.get("end") is not None]
    start = min(starts) if starts else None
    end = max(ends) if ends else None
    qids: List[str] = []
    for bi in cand.blocks:
        qid = blocks[bi].qid
        if qid not in qids:
            qids.append(qid)
    for s in run:                       # frozen-qid zero-loss
        for q in (s.get("chapter_question_ids") or []):
            if q not in qids:
                qids.append(q)
    aids: List[str] = []
    for bi in cand.blocks:
        aid = blocks[bi].aid
        if aid and aid not in aids:
            aids.append(aid)
    for s in run:
        for aid in (s.get("chapter_answer_ids") or []):
            if aid not in aids:
                aids.append(aid)
    chs: List[int] = sorted({blocks[bi].chapter for bi in cand.blocks})
    for s in run:
        for c in (s.get("chapter_indexes") or []):
            if c not in chs:
                chs.append(c)
    chs = sorted(chs)
    confs = [s.get("confidence") for s in run if s.get("confidence") is not None]
    conf = min(confs) if confs else None
    tag = "html-resplit: 依 wenda2_ebook 問題邊界重新分段（合併同一問題），待人工確認"
    out: dict = {
        "questioner": next((s.get("questioner") for s in run if s.get("questioner")), None),
        "question_time": next((s.get("question_time") for s in run if s.get("question_time")), None),
        "q_text": q_text,
        "answer_text": a_text,
        "start": start,
        "end": end,
        "confidence": 0.5 if conf is None else min(conf, 0.5),
        "status": "auto",
        "notes": (first.get("notes") or "") + (" | " if first.get("notes") else "") + tag,
        "chapter_question_ids": qids,
        "chapter_indexes": chs,
    }
    if aids:
        out["chapter_answer_ids"] = aids
    if first.get("srt_preview"):
        out["srt_preview"] = first["srt_preview"]
    meta: dict = {}
    for s in run:
        for k, v in (s.get("meta") or {}).items():
            if k != "lastPlayed":
                meta[k] = v
    if meta:
        out["meta"] = meta
    if start is not None:
        out["start_label"] = fmt_label(start)
    if end is not None:
        out["end_label"] = fmt_label(end)
    return out


# --------------------------------------------------------------------------
# text align (transitional line stuck at the previous answer's tail)
# --------------------------------------------------------------------------

SIG_RE = re.compile(r"^(\S{1,15})\s+(\d{4}[-/]\d{1,2}[-/]\d{1,2})(\s+\d{1,2}:\d{2})?$")
ALIGN_CUR_TAG = "html-resplit: 答案尾過渡語移至下段問題，待人工確認"
ALIGN_NXT_TAG = "html-resplit: 問題前綴自上段答案移入，待人工確認"


def find_aligns(sid: str, segs: List[dict], seg_groups: List[List[Group]],
                ctx: dict) -> List[Tuple[int, int, int, str, int]]:
    """Lines stuck at the end of one segment's answer that belong to the NEXT
    segment's question text (per the ebook block): e.g. 「有關修行的問題。」
    before a numbered sub-question, or a signature + thanks line.  Exact,
    bounded moves only."""
    keptq = ctx["keptq"]
    cands: List[Tuple[int, int, int, str, int]] = []
    for i in range(len(segs) - 1):
        cur, nxt = segs[i], segs[i + 1]
        # the block that should own nxt's question head
        bi: Optional[int] = None
        q_groups = [g for g in seg_groups[i + 1] if g.kind == "Q"]
        if len(q_groups) == 1:
            bi = q_groups[0].blocks[0]
        elif len(seg_groups[i + 1]) == 1:
            bi = seg_groups[i + 1][0].blocks[0]
        else:
            fqids = nxt.get("chapter_question_ids") or []
            if len(fqids) == 1:
                bis = ctx["blocks_by_qid"].get(fqids[0]) or []
                if len(bis) == 1:
                    bi = bis[0]
        if bi is None:
            continue
        kq = keptq[bi]
        if len(kq) < 8:
            continue
        a_text = cur.get("answer_text") or ""
        if len(a_text) < 10:
            continue
        astream, araw = kept_stream(a_text)
        if len(astream) < 5:
            continue
        best_len = 0
        # the moved tail must be a PREFIX of the next block's question — a mere
        # mid-head occurrence is a coincidental overlap and must not carve text
        for L in range(min(len(astream), 100), 4, -1):
            if kq.startswith(astream[-L:]):
                best_len = L
                break
        if best_len < 5:
            continue
        raw_start = araw[len(astream) - best_len]
        moved = a_text[raw_start:].strip()
        rest = a_text[:raw_start].strip()
        if not moved or not rest:
            continue
        # signature-line bonus: the line immediately before the moved tail
        lines_before = a_text[:raw_start].rstrip("\n")
        last_line = lines_before.rsplit("\n", 1)[-1].strip() if lines_before else ""
        sig = SIG_RE.match(last_line) if last_line else None
        if sig and sig.group(1) == (nxt.get("questioner") or "").strip():
            raw_start2 = a_text[:raw_start].rfind(last_line)
            moved2 = a_text[raw_start2:].strip()
            if moved2 and a_text[:raw_start2].strip():
                raw_start, moved = raw_start2, moved2
        cands.append((i, i + 1, raw_start, moved, best_len))
    return cands


def apply_aligns(segs: List[dict], aligns: List[Tuple[int, int, int, str, int]],
                 fresh: set) -> int:
    applied = 0
    for (ci, ni, raw_start, moved, _L) in aligns:
        cur, nxt = segs[ci], segs[ni]
        if id(cur) in fresh or id(nxt) in fresh:
            continue   # structural change took precedence this run
        a_text = cur.get("answer_text") or ""
        rest = a_text[:raw_start].strip()
        moved_now = a_text[raw_start:].strip()
        if not rest or not moved_now or moved_now != moved:
            continue   # idempotency guard
        cur["answer_text"] = rest
        q_old = nxt.get("q_text") or ""
        nxt["q_text"] = (moved_now + "\n" + q_old).strip() if q_old.strip() else moved_now
        for g, tag in ((cur, ALIGN_CUR_TAG), (nxt, ALIGN_NXT_TAG)):
            if tag not in (g.get("notes") or ""):
                g["notes"] = (g.get("notes") or "") + (" | " if g.get("notes") else "") + tag
            g["meta"] = {k: v for k, v in (g.get("meta") or {}).items()
                         if k != "lastPlayed"}
            g["status"] = "auto"
            g.pop("html_verbatim", None)
        applied += 1
    return applied


# --------------------------------------------------------------------------
# audit (numbered markers / char-count deltas)
# --------------------------------------------------------------------------

NUM_LINE_RE = re.compile(r"(?m)^[（(]?\s*\d{1,2}\s*[)）]?\s*[、.．:：,，]\s*\S")
NUM_PAREN_RE = re.compile(r"(?m)^[（(]\s*\d{1,2}\s*[)）]")
NUM_PROBLEM_RE = re.compile(r"问题\s*\d{1,2}\s*[、:：.]")
NUM_Q_RE = re.compile(r"[QqＱ]\s*\d{1,2}\s*[、:：.]")
NUM_CIRCLED_RE = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩]")
NUM_CN_RE = re.compile(r"(?m)^[（(]?\s*[一二三四五六七八九十]{1,3}\s*[)）]?\s*[、.．:：]")


def numbered_markers(q_text: str) -> List[str]:
    hits: List[str] = []
    src = q_text or ""

    def line_of(pos: int) -> str:
        ls = src.rfind("\n", 0, pos) + 1
        le = src.find("\n", pos)
        return src[ls:le if le >= 0 else len(src)]

    for m in NUM_LINE_RE.finditer(src):
        line = line_of(m.start())
        if has_datelike(line):
            continue
        hits.append(line.strip()[:40])
    for m in NUM_PAREN_RE.finditer(src):
        line = line_of(m.start())
        if has_datelike(line):
            continue
        hits.append(line.strip()[:40])
    if NUM_PROBLEM_RE.search(src):
        hits.append("问题N：")
    if NUM_Q_RE.search(src):
        hits.append("QN:")
    if NUM_CIRCLED_RE.search(src):
        hits.append("①")
    if NUM_CN_RE.search(src):
        hits.append("一、")
    return hits


def audit_segment(month: str, sid: str, i: int, seg: dict, groups: List[Group],
                  ambig: bool, dropped: List[Group], all_groups: List[Group],
                  ctx: dict) -> List[dict]:
    blocks = ctx["blocks"]
    frozen = list(seg.get("chapter_question_ids") or [])
    claimed: set = set()
    for g in all_groups:
        for bi in g.blocks:
            claimed.add(blocks[bi].qid)
    carve_claimed: set = set()
    for g in groups:
        for bi in g.blocks:
            carve_claimed.add(blocks[bi].qid)
    kept_q_seg = len(kept_stream(seg.get("q_text") or "")[0])
    kept_a_seg = len(kept_stream(seg.get("answer_text") or "")[0])
    kept_q_blocks = sum(len(ctx["keptq"][g.blocks[0]]) for g in groups)
    kept_a_blocks = sum(len(ctx["kepta"][g.blocks[0]]) for g in groups)
    dq = kept_q_seg - kept_q_blocks
    da = kept_a_seg - kept_a_blocks
    tol_q = max(12, int(kept_q_blocks * 0.08))
    tol_a = max(40, int(kept_a_blocks * 0.12))
    if ambig:
        verdict = "AMBIG"
    elif seg.get("zero"):
        verdict = "zero"
    elif len(groups) >= 2:
        verdict = "SPLIT"
    elif len(groups) == 1:
        g = groups[0]
        strong = g.apos is not None and g.a_exact
        if qa_boundary_plan(seg, g, ctx) is not None:
            verdict = "QA-FIX"
        elif set(carve_claimed) == set(frozen) and frozen:
            verdict = "OK" if strong else "weak"
        elif link_fix_ok(g):
            verdict = "LINK-FIX"
        else:
            verdict = "LINK-WEAK"
    else:
        verdict = "NO-CLAIM"
    nums = numbered_markers(seg.get("q_text") or "")
    pieces_diag: List[dict] = []
    split_problems: List[str] = []
    if verdict == "SPLIT":
        pieces, split_problems, pieces_diag = split_plan((month, sid, i), seg, groups, ctx)
        if split_problems:
            verdict = "SPLIT-DEGEN"
        else:
            # per-piece char comparison against the ebook block (item 4):
            # report the worst |delta| on each side
            dq = max((abs(pc["dq"]) for pc in pieces_diag), default=0)
            da = max((abs(pc["da"]) for pc in pieces_diag), default=0)
            tol_q = max(6, max((pc["q_block"] for pc in pieces_diag), default=0) // 10)
            tol_a = max(6, max((pc["a_block"] for pc in pieces_diag), default=0) // 10)
    dropped_info = [{"qids": [blocks[bi].qid for bi in g.blocks],
                     "kind": g.kind, "apos": g.apos} for g in dropped]
    reportable = (verdict not in ("OK", "weak", "zero")
                  or bool(nums) or bool(dropped_info)
                  or (verdict == "OK" and (abs(dq) > tol_q or abs(da) > tol_a)))
    if not reportable:
        return []
    return [{
        "month": month, "session": sid, "index": i + 1,
        "stable_key": seg.get("stable_key"),
        "verdict": verdict,
        "frozen": frozen, "claimed": sorted(claimed),
        "carve_claimed": sorted(carve_claimed),
        "dq": dq, "da": da, "tol_q": tol_q, "tol_a": tol_a,
        "nums": nums,
        "kinds": [g.kind for g in groups],
        "lastPlayed": bool((seg.get("meta") or {}).get("lastPlayed")),
        "pieces": pieces_diag,
        "split_problems": split_problems,
        "dropped": dropped_info,
    }]


# --------------------------------------------------------------------------
# session driver
# --------------------------------------------------------------------------

def renumber(sid: str, segs: List[dict]) -> None:
    for n, seg in enumerate(segs, start=1):
        seg["index"] = n
        seg["question_id"] = question_id(sid, n, seg.get("q_text") or "")
        seg["stable_key"] = f"{sid}#{n}"
        qp = seg.get("q_text") or ""
        ap_ = seg.get("answer_text") or ""
        seg["q_preview"] = qp[:100] + ("…" if len(qp) > 100 else "")
        seg["answer_preview"] = ap_[:160] + ("…" if len(ap_) > 160 else "")
        if seg.get("start") is not None:
            seg["start_label"] = fmt_label(seg["start"])
        if seg.get("end") is not None:
            seg["end_label"] = fmt_label(seg["end"])


def process_session(month: str, sess: dict,
                    claims_info: List[Tuple[List[Group], tuple, bool]],
                    ctx: dict, apply: bool) -> Tuple[List[dict], bool, dict]:
    sid = sess["session_id"]
    segs = sess["segments"]
    seg_groups = [c[0] for c in claims_info]
    findings: List[dict] = []
    for i, (all_g, carve, _streams, ambig, dropped) in enumerate(claims_info):
        findings.extend(audit_segment(month, sid, i, segs[i], carve, ambig,
                                      dropped, all_g, ctx))
    merges = find_merges(sid, segs, seg_groups, ctx)
    for m in merges:
        qids: List[str] = []
        for bi in m.blocks:
            qids.append(ctx["blocks"][bi].qid)
        findings.append({
            "month": month, "session": sid, "index": m.start_i + 1,
            "stable_key": segs[m.start_i].get("stable_key"),
            "verdict": "MERGE",
            "frozen": list(segs[m.start_i].get("chapter_question_ids") or []),
            "claimed": qids, "carve_claimed": qids,
            "dq": 0, "da": 0, "tol_q": 0, "tol_a": 0, "nums": [],
            "kinds": [], "pieces": [], "split_problems": [], "dropped": [],
            "lastPlayed": any((s.get("meta") or {}).get("lastPlayed")
                              for s in segs[m.start_i:m.end_i + 1]),
            "span": f"{m.start_i + 1}..{m.end_i + 1}",
        })
    stats = {"split": 0, "merged": 0, "link": 0, "align": 0, "degenerate": 0,
             "qa": 0,
             "merge_groups": len(merges),
             "merge_segs": sum(m.end_i - m.start_i + 1 for m in merges)}
    changed = False
    if apply:
        fresh: set = set()
        new_segs: List[dict] = []
        merge_by_start = {m.start_i: m for m in merges}
        i = 0
        while i < len(segs):
            if i in merge_by_start:
                m = merge_by_start[i]
                merged = merge_segments(sid, segs[i:m.end_i + 1], m, ctx)
                fresh.add(id(merged))
                new_segs.append(merged)
                stats["merged"] += m.end_i - m.start_i + 1
                changed = True
                i = m.end_i + 1
                continue
            seg = segs[i]
            groups = claims_info[i][1]      # carveable groups only
            ambig = claims_info[i][3]
            own_qids = {ctx["blocks"][bi].qid
                        for g in claims_info[i][0] for bi in g.blocks}
            if len(groups) >= 2 and not seg.get("zero") and not ambig:
                pieces, problems, _diags = split_plan((month, sid, i), seg, groups, ctx)
                if pieces:
                    new_segs.extend(pieces)
                    fresh.update(id(p) for p in pieces)
                    stats["split"] += 1
                    changed = True
                    i += 1
                    continue
                stats["degenerate"] += 1
                stats.setdefault("degenerate_problems", []).append(
                    f"{sid}#{i + 1}: " + "; ".join(problems))
            if len(groups) == 1 and not ambig:
                if qa_boundary_fix(seg, groups[0], ctx):
                    stats["qa"] = stats.get("qa", 0) + 1
                    changed = True
                if link_fix_ok(groups[0]) and fix_links(
                        (month, sid, i), seg, groups[0], ctx, own_qids):
                    stats["link"] += 1
                    changed = True
            new_segs.append(seg)
            i += 1
        groups2: List[List[Group]] = []
        for seg in new_segs:
            g2, _c2, _s2, _a2, _d2 = segment_claims(seg, ctx)
            groups2.append(g2)
        aligns = find_aligns(sid, new_segs, groups2, ctx)
        n_align = apply_aligns(new_segs, aligns, fresh)
        if n_align:
            stats["align"] = n_align
            changed = True
        if changed:
            renumber(sid, new_segs)
            for seg in new_segs:
                if id(seg) in fresh:
                    seg.pop("two_part_group", None)
                    seg.pop("two_part_role", None)
                if id(seg) in fresh or "html-resplit:" in (seg.get("notes") or ""):
                    seg.pop("_chapter_fill", None)
            sess["segments"] = new_segs
    else:
        # read-only pass so the dry-run shows the same op counts
        aligns = find_aligns(sid, segs, [c[0] for c in claims_info], ctx)
        stats["align"] = len(aligns)
        for (ci, ni, cut, tag, sig) in aligns:
            findings.append({
                "month": month, "session": sid, "index": ci + 1,
                "stable_key": segs[ci].get("stable_key"),
                "verdict": "ALIGN",
                "frozen": list(segs[ci].get("chapter_question_ids") or []),
                "claimed": list(segs[ni].get("chapter_question_ids") or []),
                "carve_claimed": [], "dq": 0, "da": 0, "tol_q": 0, "tol_a": 0,
                "nums": [], "kinds": [], "pieces": [], "split_problems": [],
                "dropped": [], "lastPlayed": False,
                "span": f"{ci + 1}->{ni + 1} cut={cut} {tag} sig={sig}",
            })
    return findings, changed, stats


# --------------------------------------------------------------------------
# stats
# --------------------------------------------------------------------------

def recompute_stats(data: dict) -> None:
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


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def build_ctx(blocks: List[Block]) -> dict:
    qprobes = [norm1(q_probe_of(b)) for b in blocks]
    aprobes = [norm1(a_probe_of(b)) for b in blocks]
    blocks_by_qid: Dict[str, List[int]] = defaultdict(list)
    for bi, b in enumerate(blocks):
        blocks_by_qid[b.qid].append(bi)
    return {
        "blocks": blocks,
        "qprobes": qprobes,
        "aprobe": aprobes,
        "keptq": [kept_stream(b.q_text)[0] for b in blocks],
        "kepta": [kept_stream(b.a_text)[0] for b in blocks],
        "qgidx8": gram_index(qprobes),
        "agidx8": gram_index(aprobes),
        "short_q_idx": {i: p for i, p in enumerate(qprobes) if 4 <= len(p) < 8},
        "short_a_idx": {i: p for i, p in enumerate(aprobes) if 4 <= len(p) < 8},
        "blocks_by_qid": blocks_by_qid,
        "usable": {bi for bi, b in enumerate(blocks)
                   if b.aid or (b.a_text or "").strip()},
        "strong_qid": {},
    }


def debug_segment(key: str, datasets: dict, ctx: dict) -> None:
    """Print the full claim / carve detail for ``SESSION#INDEX`` (1-based)."""
    month_filter: Optional[str] = None
    k = key
    if ":" in key and key.split(":", 1)[0].count("-") == 1:
        month_filter, k = key.split(":", 1)
    sid, _, idx_s = k.rpartition("#")
    try:
        want_idx = int(idx_s)
    except ValueError:
        want_idx = 0
    blocks = ctx["blocks"]
    for m, (data, per_sess) in datasets.items():
        if month_filter and m != month_filter:
            continue
        for sess, info in per_sess:
            if sess["session_id"] != sid:
                continue
            for i, (all_g, carve, streams, ambig, dropped) in enumerate(info):
                if want_idx and i + 1 != want_idx:
                    continue
                seg = sess["segments"][i]
                groups = carve
                qstream, _qraw, astream, _araw = streams
                print(f"\n=== {sid}#{i + 1} ({m}) {seg.get('stable_key')} "
                      f"start={seg.get('start')} end={seg.get('end')} "
                      f"conf={seg.get('confidence')} status={seg.get('status')} "
                      f"lp={bool((seg.get('meta') or {}).get('lastPlayed'))} ===")
                print(f"  frozen={seg.get('chapter_question_ids')} "
                      f"aids={seg.get('chapter_answer_ids')} "
                      f"ambig={ambig} nums={numbered_markers(seg.get('q_text') or '')}")
                print(f"  q_text (kept {len(qstream)}):\n    "
                      + (seg.get("q_text") or "").replace("\n", "\n    ")[:900])
                print(f"  answer (kept {len(astream)}):\n    "
                      + (seg.get("answer_text") or "").replace("\n", "\n    ")[:900])
                print(f"  claims ({len(groups)} carve / {len(all_g)} all"
                      f" / {len(dropped)} dropped):")
                for g in groups:
                    for bi in g.blocks:
                        b = blocks[bi]
                        print(f"    [{g.kind}] pos={g.pos} apos={g.apos} "
                              f"q_exact={g.q_exact} a_exact={g.a_exact} "
                              f"{b.qid} ch{b.chapter} aid={b.aid}")
                        print(f"        block q (kept {len(ctx['keptq'][bi])}): "
                              + (b.q_text or "").replace("\n", " ")[:200])
                        print(f"        block a (kept {len(ctx['kepta'][bi])}): "
                              + (b.a_text or "").replace("\n", " ")[:200])
                pieces, problems, diags = split_plan((m, sid, i), seg, groups, ctx)
                for g in dropped:
                    for bi in g.blocks:
                        b = blocks[bi]
                        print(f"    [dropped {g.kind}] {b.qid} ch{b.chapter}"
                              f" apos={g.apos} — answer not in this segment")
                print(f"  split_plan: pieces={0 if pieces is None else len(pieces)}"
                      f" problems={problems}")
                for n, pc in enumerate(diags, start=1):
                    print(f"    piece{n} {pc['kind']} ch{pc['chapter']} "
                          f"q={pc['q_kept']}/{pc['q_block']} "
                          f"a={pc['a_kept']}/{pc['a_block']} "
                          f"qids={','.join(q[:12] for q in pc['qids']) or '-'}")
                if pieces:
                    for n, p in enumerate(pieces, start=1):
                        print(f"    --- piece{n} [{p['start']}..{p['end']}] "
                              f"qids={p.get('chapter_question_ids')}")
                        print(f"        q: " + (p.get("q_text") or "").replace("\n", " ")[:200])
                        print(f"        a: " + (p.get("answer_text") or "").replace("\n", " ")[:200])


def main() -> int:
    ap = argparse.ArgumentParser(
        description="HTML-driven question segmentation audit/fix for audio_map2")
    ap.add_argument("--apply", action="store_true", help="write the JSONs back")
    ap.add_argument("--month", action="append", help="YYYY-MM (repeatable)")
    ap.add_argument("--report", help="write the full audit JSON here")
    ap.add_argument("--quiet", action="store_true", help="only per-month summaries")
    ap.add_argument("--dump", action="store_true",
                    help="print the per-piece char comparison for SPLIT cases")
    ap.add_argument("--debug", action="append", metavar="SESSION#INDEX",
                    help="print full claim/piece detail for a segment, then exit")
    args = ap.parse_args()

    blocks = load_blocks()
    print(f"ebook blocks (ch01–12): {len(blocks)}")
    ctx = build_ctx(blocks)

    all_months = sorted(p.stem for p in AUDIO_MAP2_DIR.glob("????-??.json"))
    # phase 1: claims for ALL months (read-only) → corpus-wide strong-claim map
    datasets: Dict[str, Tuple[dict, list]] = {}
    strong_qid: Dict[str, set] = defaultdict(set)
    covered: Dict[str, set] = defaultdict(set)
    covered_ans: Dict[str, set] = defaultdict(set)
    for m in all_months:
        data = json.loads((AUDIO_MAP2_DIR / f"{m}.json").read_text(encoding="utf-8"))
        per_sess = []
        for sess in data["sessions"]:
            sid = sess["session_id"]
            info = []
            for i, seg in enumerate(sess["segments"]):
                groups, carve, streams, ambig, dropped = segment_claims(seg, ctx)
                info.append((groups, carve, streams, ambig, dropped))
                for g in groups:
                    for bi in g.blocks:
                        b = blocks[bi]
                        covered[b.qid].add((m, sid, i))
                        if b.aid:
                            covered_ans[b.aid].add((m, sid, i))
                    if g.apos is not None and g.a_exact:
                        for bi in g.blocks:
                            strong_qid[blocks[bi].qid].add((m, sid, i))
            per_sess.append((sess, info))
        datasets[m] = (data, per_sess)
    ctx["strong_qid"] = strong_qid
    ctx["covered"] = covered
    ctx["covered_ans"] = covered_ans
    print(f"strong corpus claims: {len(strong_qid)} qids")

    if args.debug:
        for key in args.debug:
            debug_segment(key, datasets, ctx)
        return 0

    months = args.month or list(reversed(all_months))   # newest → oldest
    report_findings: List[dict] = []
    for m in months:
        data, per_sess = datasets[m]
        month_findings: List[dict] = []
        month_changed = False
        tot = {"split": 0, "merged": 0, "link": 0, "align": 0, "degenerate": 0,
               "qa": 0, "merge_groups": 0, "merge_segs": 0}
        degenerate_problems: List[str] = []
        for sess, info in per_sess:
            findings, changed, stats = process_session(m, sess, info, ctx, args.apply)
            month_findings.extend(findings)
            for k in tot:
                tot[k] += stats.get(k, 0)
            degenerate_problems.extend(stats.get("degenerate_problems") or [])
            if changed:
                month_changed = True
        vc = Counter(f["verdict"] for f in month_findings)
        summ = " ".join(f"{k}:{v}" for k, v in sorted(vc.items())) or "clean"
        line = f"{m}: flagged {len(month_findings):4d} ({summ})"
        line += (f"  ops split={tot['split']}"
                 f" merge={tot['merge_groups']}({tot['merge_segs']}seg)"
                 f" link={tot['link']} qa={tot['qa']} align={tot['align']}"
                 f" degenerate={tot['degenerate']}")
        if args.apply:
            line += "  WRITTEN" if month_changed else ""
        print(line)
        if not args.quiet:
            for f in month_findings:
                tag = ""
                if f["verdict"] in ("SPLIT", "SPLIT-DEGEN", "LINK-FIX", "AMBIG",
                                    "NO-CLAIM") or f["nums"]:
                    tag = f"  nums={f['nums'][:4]}" if f["nums"] else ""
                print(f"    {f['session']}#{f['index']:<4} {f['verdict']:<11}"
                      f" qΔ={f['dq']:+5d} aΔ={f['da']:+6d}"
                      f" frozen={','.join(q[:8] for q in f['frozen']) or '-'}"
                      f" claimed={','.join(q[:8] for q in f['claimed']) or '-'}"
                      f"{('  '+f['span']) if f.get('span') else ''}"
                      f"{tag}{' [LP]' if f['lastPlayed'] else ''}")
                if args.dump and f["verdict"] in ("SPLIT", "SPLIT-DEGEN"):
                    for i, pc in enumerate(f.get("pieces") or [], start=1):
                        print(f"        piece{i} q={pc['q_kept']:5d}/{pc['q_block']:<5d}"
                              f" a={pc['a_kept']:6d}/{pc['a_block']:<6d}"
                              f" {pc['kind']:<5s} ch{pc['chapter']:<2d}"
                              f" {','.join(q[:12] for q in pc['qids']) or '(no-qid)'}")
                    for pr in f.get("split_problems") or []:
                        print(f"        !! {pr}")
                if args.dump and f.get("dropped"):
                    for d in f["dropped"]:
                        print(f"        ~dropped {d['kind']} apos={d['apos']}"
                              f" {','.join(q[:12] for q in d['qids'])}")
        if degenerate_problems:
            for p in degenerate_problems:
                print(f"    !! degenerate skip {p}")
        report_findings.extend(month_findings)
        if args.apply and month_changed:
            recompute_stats(data)
            data.pop("version_marker", None)
            (AUDIO_MAP2_DIR / f"{m}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")

    if args.report:
        Path(args.report).write_text(
            json.dumps(report_findings, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"report → {args.report}")
    if not args.apply:
        print("\n(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
