#!/usr/bin/env python3
"""Audit audio_map2 segmentation against the wenda2_ebook HTML block boundaries.

The ebook HTML is the segmentation source of truth for Word chapters 01–12:
every ``question``/``answer`` block is one playable unit and the injector
places one button per block.  This script slides a window over every month
JSON's segments and cross-checks them against the HTML blocks.  READ-ONLY —
it never mutates the JSONs; it only reports:

  A. **跨章同qid** — the SAME question id used by ebook blocks in TWO
     different chapters.  These are Word questions the ebook split into two
     blocks; the segment(s) carrying that qid must be re-split so each block
     gets its own range (pattern: fix_2025_05_12_seg74.py — same qid on both
     pieces, distinct chapter_answer_ids / chapter_indexes).
  B. **多qid段** — a segment frozen with ≥2 chapter_question_ids while the
     matched ebook blocks each carry their own id (one Word chunk covering
     several ebook questions) → split candidate.
  C. **同qid連續多段** — consecutive segments of one session sharing a single
     qid where the ebook has ONE block → merge candidate.
  D. **滑動視窗邊界** — an ebook block whose text head starts strictly INSIDE
     a segment (not at its start): the Word segmentation put that boundary
     mid-block (question read back late / answer spillover / missing split).
     Also: a block whose qid is frozen on a DIFFERENT segment than the one
     containing its text (mis-link), and blocks whose qid is frozen nowhere
     (unlinked block).
  E. **跨session同qid** — the same qid linked from two different sessions
     (expected only for the ebook's own cross-chapter splits; otherwise a
     mis-link).

Matching normalizes text with OpenCC t2s over kept characters only
(identical to resplit_by_html.py), so 繁/簡 variants compare equal.

Usage:
  .venv/bin/python audit_html_blocks.py                  # all months
  .venv/bin/python audit_html_blocks.py --month 2025-05  # one month
  .venv/bin/python audit_html_blocks.py --json out.json  # machine-readable
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from opencc import OpenCC

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"
EBOOK_DIR = ROOT / "wenda2_ebook"
CHAPTERS = range(1, 13)  # Word chapters 01–12

CC = OpenCC("t2s")  # traditional -> simplified, length-preserving on kept chars
KEPT = re.compile(r"[\w一-鿿]")

Q_OPEN_RE = re.compile(r'<div class="question" id="(question-[0-9a-f]+)"')
SPAN_TIME_RE = re.compile(r'<span class="question-time">([^<]*)</span>')
SPAN_QWER_RE = re.compile(r'<span class="questioner">([^<]*)</span>')
ANSWER_ID_RE = re.compile(r'<div class="answer" id="(answer-[0-9a-f]+)"')
TEXT_RE = re.compile(r'<div class="(question|answer)-text">(.*?)</div>', re.S)


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


def strip_tags(fragment: str) -> str:
    txt = re.sub(r"<br\s*/?>", "\n", fragment or "")
    txt = re.sub(r"<[^>]+>", "", txt)
    return htmllib.unescape(txt).strip()


def load_ebook_blocks() -> List[dict]:
    """Every question/answer block of wenda2_ebook chapters 01–12."""
    blocks: List[dict] = []
    for ch in CHAPTERS:
        path = EBOOK_DIR / f"{ch:02d}.html"
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        opens = list(Q_OPEN_RE.finditer(content))
        for n, m in enumerate(opens):
            end = opens[n + 1].start() if n + 1 < len(opens) else len(content)
            region = content[m.start():end]
            hr = region.find("<hr/>")
            if hr > 0:
                region = region[:hr]
            qid = m.group(1)
            aid_m = ANSWER_ID_RE.search(region)
            texts = TEXT_RE.findall(region)
            q_text = strip_tags(next((t[1] for t in texts if t[0] == "question"), ""))
            a_text = strip_tags(next((t[1] for t in texts if t[0] == "answer"), ""))
            time_m = SPAN_TIME_RE.search(region)
            qwer_m = SPAN_QWER_RE.search(region)
            blocks.append({
                "chapter": ch,
                "order": n + 1,
                "qid": qid,
                "aid": aid_m.group(1) if aid_m else None,
                "qwer": qwer_m.group(1).strip() if qwer_m else "",
                "q_time": time_m.group(1).strip() if time_m else "",
                "q_text": q_text,
                "a_text": a_text,
            })
    return blocks


def load_month_sessions(month: str) -> List[dict]:
    path = AUDIO_MAP2_DIR / f"{month}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("sessions") or []


class SessionStream:
    """Concatenated kept-char stream of one session's segment texts,
    remembering the owning segment index for every character."""

    def __init__(self, session: dict):
        self.session = session
        segs = session.get("segments") or []
        chars: List[str] = []
        owner: List[int] = []
        self.seg_starts: List[int] = []
        cursor = 0
        for i, seg in enumerate(segs):
            self.seg_starts.append(cursor)
            for text in (seg.get("q_text") or "", seg.get("answer_text") or ""):
                stream, _ = kept_stream(text)
                chars.append(stream)
                owner.extend([i] * len(stream))
                cursor += len(stream)
        self.text = "".join(chars)
        self.owner = owner
        self.frozen = [list(seg.get("chapter_question_ids") or []) for seg in segs]
        self.keys = [seg.get("stable_key") or f"{session['session_id']}#{i + 1}"
                     for i, seg in enumerate(segs)]

    def locate(self, probe: str) -> Optional[Tuple[int, int]]:
        """Find probe head in the stream → (segment index, offset-in-segment)."""
        if not probe:
            return None
        p = self.text.find(probe)
        if p < 0:
            return None
        seg_i = self.owner[p]
        return seg_i, p - self.seg_starts[seg_i]


def block_probe(block: dict, n: int = 60) -> str:
    stream, _ = kept_stream((block["q_text"] or "")[:400])
    if len(stream) < 12:
        stream, _ = kept_stream((block["a_text"] or "")[:400])
    return stream[:n]


def month_of_block(block: dict) -> Optional[str]:
    m = re.match(r"(\d{4})-(\d{2})", block["q_time"] or "")
    return f"{m.group(1)}-{m.group(2)}" if m else None


def audit(months: List[str]) -> dict:
    blocks = load_ebook_blocks()
    by_qid_chapters: Dict[str, set] = defaultdict(set)
    for b in blocks:
        by_qid_chapters[b["qid"]].add(b["chapter"])

    # ---- category A: cross-chapter duplicate qids + their audio_map2 state
    dup_report = []
    for qid, chs in sorted(by_qid_chapters.items(), key=lambda kv: sorted(kv[1])):
        if len(chs) < 2:
            continue
        carriers = []  # (month, session, seg) carrying this qid
        for month in months:
            for sess in load_month_sessions(month):
                for seg in sess.get("segments") or []:
                    if qid in (seg.get("chapter_question_ids") or []):
                        carriers.append((month, sess["session_id"], seg))
        pieces_ok = (
            len(carriers) >= 2
            and all(seg.get("chapter_answer_ids") for _, _, seg in carriers)
            and len({tuple(seg.get("chapter_answer_ids") or [])
                     for _, _, seg in carriers}) == len(carriers)
        ) if carriers else False
        dup_report.append({
            "qid": qid, "chapters": sorted(chs),
            "blocks": [f'{b["chapter"]:02d}#{b["order"]}/{b["aid"]}'
                       for b in blocks if b["qid"] == qid],
            "carriers": [f'{m}/{sid}#{seg.get("index")}' for m, sid, seg in carriers],
            "state": "fixed (per-block chapter_answer_ids)" if pieces_ok
                     else ("no carriers" if not carriers else "NEEDS SPLIT"),
        })

    # ---- index: qid → sessions that freeze it (per month)
    qid_sessions: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    segs_by_key: Dict[str, dict] = {}
    month_sessions: Dict[str, List[dict]] = {}
    for month in months:
        sessions = load_month_sessions(month)
        month_sessions[month] = sessions
        for sess in sessions:
            for seg in sess.get("segments") or []:
                segs_by_key[seg.get("stable_key") or ""] = seg
                for qid in seg.get("chapter_question_ids") or []:
                    qid_sessions[qid].append((month, sess["session_id"]))

    # ---- sliding-window check (D) + B + C + E
    findings: List[dict] = []
    for month in months:
        for sess in month_sessions[month]:
            stream = SessionStream(sess)
            sid = sess["session_id"]
            segs = sess.get("segments") or []
            # C: consecutive same-single-qid segments.  Legit cross-chapter
            # splits carry the same qid with DIFFERENT chapter_answer_ids —
            # only flag when the answer ids are identical/absent.
            for a, b in zip(segs, segs[1:]):
                qa = a.get("chapter_question_ids") or []
                qb = b.get("chapter_question_ids") or []
                if len(qa) == 1 and qa == qb \
                        and (a.get("chapter_answer_ids") or []) \
                        == (b.get("chapter_answer_ids") or []):
                    findings.append({
                        "cat": "C", "month": month, "session": sid,
                        "where": f'{a.get("stable_key")}+{b.get("stable_key")}',
                        "qid": qa[0],
                        "detail": "連續兩段同一 qid（電子書僅一個 block）→ 併候選",
                    })
            # B + D: block heads landing inside segments
            seen_blocks = set()
            for seg_i, seg in enumerate(segs):
                for qid in seg.get("chapter_question_ids") or []:
                    for blk in blocks:
                        if blk["qid"] == qid:
                            seen_blocks.add((blk["chapter"], blk["order"], qid))
            for blk in blocks:
                if month_of_block(blk) not in (None, month):
                    continue
                if (blk["chapter"], blk["order"], blk["qid"]) not in seen_blocks \
                        and blk["qid"] in qid_sessions:
                    # frozen elsewhere; only inspect when THIS session is among them
                    if (month, sid) not in qid_sessions[blk["qid"]]:
                        continue
                probe = block_probe(blk)
                if len(probe) < 12:
                    continue
                hit = stream.locate(probe)
                if hit is None:
                    continue
                seg_i, off = hit
                frozen_here = blk["qid"] in stream.frozen[seg_i]
                if frozen_here and off <= 2:
                    continue  # healthy: block starts at its own segment
                if frozen_here and off > 2:
                    multi = len(stream.frozen[seg_i]) >= 2
                    findings.append({
                        "cat": "B" if multi else "D",
                        "month": month, "session": sid,
                        "where": stream.keys[seg_i],
                        "qid": blk["qid"],
                        "detail": (f"block {blk['chapter']:02d}#{blk['order']} 文字頭"
                                   f"落在段內 offset={off}"
                                   + ("（多 qid 段）" if multi else "（單 qid 段）")),
                    })
                elif not frozen_here:
                    owners = [i for i, qs in enumerate(stream.frozen)
                              if blk["qid"] in qs]
                    if owners:
                        findings.append({
                            "cat": "D", "month": month, "session": sid,
                            "where": stream.keys[seg_i],
                            "qid": blk["qid"],
                            "detail": f"文字在 {stream.keys[seg_i]} 內，qid 卻凍結在 "
                                      f"{[stream.keys[i] for i in owners]}（錯掛）",
                        })
                    else:
                        other = qid_sessions.get(blk["qid"]) or []
                        if other and (month, sid) not in other:
                            findings.append({
                                "cat": "E", "month": month, "session": sid,
                                "where": stream.keys[seg_i], "qid": blk["qid"],
                                "detail": f"qid 也被其他 session 凍結：{other}",
                            })
                        elif not other:
                            findings.append({
                                "cat": "D", "month": month, "session": sid,
                                "where": stream.keys[seg_i], "qid": blk["qid"],
                                "detail": f"block {blk['chapter']:02d}#{blk['order']}"
                                          " 文字存在但 qid 未凍結在任何段（漏掛）",
                            })

    # blocks never frozen anywhere (informational)
    unfrozen = sorted({
        f'{b["chapter"]:02d}#{b["order"]} {b["qid"]}'
        for b in blocks if b["qid"] not in qid_sessions
    })
    return {
        "dup_qids": dup_report,
        "findings": findings,
        "unfrozen_blocks": unfrozen,
        "blocks_total": len(blocks),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--month", action="append", help="YYYY-MM (repeatable)")
    ap.add_argument("--json", help="also write the report as JSON")
    args = ap.parse_args()

    months = args.month or sorted(p.stem for p in AUDIO_MAP2_DIR.glob("????-??.json"))
    report = audit(months)

    print(f"ebook blocks (ch01–12): {report['blocks_total']}")
    print(f"\n== A. 跨章同qid（{len(report['dup_qids'])}) ==")
    for d in report["dup_qids"]:
        print(f"  {d['qid']}  chapters={d['chapters']}  [{d['state']}]")
        for blk in d["blocks"]:
            print(f"     block {blk}")
        for c in d["carriers"]:
            print(f"     carrier {c}")

    by_cat: Dict[str, List[dict]] = defaultdict(list)
    for f in report["findings"]:
        by_cat[f["cat"]].append(f)
    for cat, title in (("B", "B. 多qid段（一 Word 段蓋多個電子書 block）"),
                       ("C", "C. 同qid連續多段（併候選）"),
                       ("D", "D. 滑動視窗邊界／漏掛／錯掛"),
                       ("E", "E. 跨session同qid")):
        rows = by_cat.get(cat) or []
        print(f"\n== {title}（{len(rows)}) ==")
        for f in rows[:80]:
            print(f"  [{f['month']}] {f['where']}  {f['qid']}")
            print(f"     {f['detail']}")
        if len(rows) > 80:
            print(f"  … 其餘 {len(rows) - 80} 筆略")

    unfrozen = report["unfrozen_blocks"]
    print(f"\n== 未凍結的電子書 block（{len(unfrozen)}) ==")
    for u in unfrozen[:60]:
        print(f"  {u}")
    if len(unfrozen) > 60:
        print(f"  … 其餘 {len(unfrozen) - 60} 筆略")

    if args.json:
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nJSON report → {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
