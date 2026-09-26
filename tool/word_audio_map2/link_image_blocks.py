#!/usr/bin/env python3
"""Link the chronological audio_map2 segments to ebook blocks that have **no
``<div class="question">``** — i.e. blocks whose question was submitted as a
screenshot (``<img alt="提问人：日期 …">``) or replaced by a placeholder
(``（此问题丢失或未收集到）`` / ``问题缺失`` / ``(TAI师父自白)`` …).

``link_chapters.py`` can only match question blocks, so those blocks were left
unmapped and never received a play button even when their spoken segment was
reviewed.  This script is the answer-only analogue: it finds every orphan
``answer-…`` block in chapters 01–12 and content-matches it to the
audio_map2 segment that speaks it, then writes

    chapter_answer_ids  += [answer-…]      (the block's own stable id)
    chapter_indexes      += [chapter]      (the chapter the block lives in)

Two match shapes are recognised, both decided on the **answer text** (the Word
text is the SoT; the ebook copy may differ by 著/着 style variants only):

  * ``full``     — the block's answer equals one segment's answer
                   (≥ ``--min-ratio`` after stripping punctuation).
  * ``portion``  — the block's answer is a verbatim slice of a **merged**
                   segment that speaks several blocks in a row (ratio 1.0
                   containment).  The block then shares the segment's range
                   with its neighbours; a ``html-portion:`` note is written so
                   the coarse range is not mistaken for a precise anchor.

Only ``chapter_answer_ids`` / ``chapter_indexes`` (and the ``html-portion:``
note) are ever written — question/answer text, times, ``status`` and
``meta.lastPlayed`` are never touched, and a segment that already carries the
block id is left alone (idempotent).

Usage (from the repo root or tool/word_audio_map2):
    .venv/bin/python link_image_blocks.py            # dry-run report
    .venv/bin/python link_image_blocks.py --apply    # write back
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
AUDIO_MAP2_DIR = ROOT / "audio_map2"
EBOOK_DIR = ROOT / "wenda2_ebook"
CHAPTERS = range(1, 13)

# NOTE: ids may carry the IDGenerator dedup suffix (``question-…-2``); a regex
# without it silently mis-pairs blocks and invents "orphan" answers.
BLOCK_RE = re.compile(
    r'<div class="(question|answer)" id="((?:question|answer)-[0-9a-f]+(?:-\d+)?)">'
)
ANSWER_TEXT_RE = re.compile(r'<div class="answer-text">(.*?)</div>', re.S)
IMG_ALT_RE = re.compile(r'<img alt="([^"]*)"')
DATE_RE = re.compile(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})")
NOTE_PREFIX = "html-portion"

_CC_SENTINEL = object()
_CC = _CC_SENTINEL  # None = opencc unavailable; sentinel = not tried yet


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
    """Fold TW→CN (OpenCC, same as link_chapters.py) and drop punctuation.

    The ebook keeps 着 where the Word 彙總 writes 著 and vice versa; folding
    first is what makes a verbatim containment test meaningful.
    """
    s = s if isinstance(s, str) else ""
    s = re.sub(r"_x[0-9A-Fa-f]{4}_", "", s)
    cc = _converter()
    if cc is not None:
        try:
            s = cc.convert(s)
        except Exception:
            pass
    # Known cosmetic variant (see audio_map2/SKILL.md): the Word 彙總 writes
    # 著 where the ebook writes 着 and vice versa.  Fold both sides to one char.
    s = s.replace("著", "着")
    return re.sub(r"[^\w一-鿿]", "", s).lower()


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s)
    return re.sub(r"<[^>]+>", "", s)


def find_orphan_blocks() -> List[dict]:
    """Answer blocks with no question div of their own, in chapters 01–12.

    A question is "spent" by the next answer block in document order, so an
    answer that arrives with no question still pending is a genuine orphan.
    """
    out: List[dict] = []
    for ch in CHAPTERS:
        path = EBOOK_DIR / f"{ch:02d}.html"
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        pending_q = 0
        for m in BLOCK_RE.finditer(content):
            kind, iid = m.group(1), m.group(2)
            if kind == "question":
                pending_q += 1
                continue
            if pending_q:
                pending_q -= 1
                continue
            region = content[m.start():]
            a_text = ""
            a_m = ANSWER_TEXT_RE.search(region)
            if a_m:
                a_text = strip_tags(a_m.group(1)).strip()
            before = content[: m.start()]
            hr = before.rfind("<hr/>")
            lead = strip_tags(before[hr + 4:]).strip() if hr != -1 else ""
            alts = IMG_ALT_RE.findall(before)
            out.append({
                "chapter": ch,
                "aid": iid,
                "a_text": a_text,
                # the screenshot alt / bare lead line is the block's question
                "q_hint": (alts[-1] if alts else lead).strip(),
            })
    return out


def load_segments(datas: Dict[Path, dict]) -> List[dict]:
    """Flatten every month JSON into segment records; keep ``datas`` for writing.

    ``datas`` is filled with the SAME parsed objects the records point at, so a
    later in-place edit of ``entry["seg"]`` is what actually gets written out.
    """
    out: List[dict] = []
    for path in sorted(AUDIO_MAP2_DIR.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        datas[path] = data
        for session in data.get("sessions") or []:
            for seg in session.get("segments") or []:
                out.append({
                    "path": path,
                    "session": session,
                    "seg": seg,
                    "na": norm(seg.get("answer_text")),
                    "nq": norm(seg.get("q_text")),
                })
    return out


def match_block(block: dict, segments: List[dict], min_ratio: float) -> List[dict]:
    """Candidate carriers, best first; ``shape`` is ``portion`` or ``full``."""
    na = norm(block["a_text"])
    if not na:
        return []
    cands: List[dict] = []
    for e in segments:
        if not e["na"]:
            continue
        if e["na"].find(na) >= 0:
            ratio = 1.0
            shape = "portion" if len(na) < len(e["na"]) else "full"
        else:
            ratio = difflib.SequenceMatcher(None, na, e["na"]).quick_ratio()
            if ratio < min_ratio:
                continue
            shape = "full"
        date = e["session"].get("date")
        hint_date = DATE_RE.search(block["q_hint"] or "")
        date_ok = True
        if hint_date and date:
            date_ok = "%04d-%02d-%02d" % tuple(int(x) for x in hint_date.groups()) == date
        cands.append({
            "entry": e, "ratio": round(ratio, 4), "shape": shape, "date_ok": date_ok,
        })
    cands.sort(key=lambda c: (-c["ratio"], c["entry"]["seg"].get("index", 0)))
    return cands


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write back (default: report only)")
    ap.add_argument("--min-ratio", type=float, default=0.98,
                    help="minimum fuzzy ratio for a whole-block match (default 0.98)")
    args = ap.parse_args()

    blocks = find_orphan_blocks()
    datas: Dict[Path, dict] = {}
    segments = load_segments(datas)
    print(f"orphan answer blocks (no question div): {len(blocks)} in chapters 01-12")
    print(f"segments scanned: {len(segments)}\n")

    claimed: Dict[str, str] = {}
    plan: List[Tuple[Path, dict, dict, dict, dict]] = []
    skipped_ambiguous = 0

    for block in blocks:
        cands = match_block(block, segments, args.min_ratio)
        if not cands:
            print(f"  ch{block['chapter']:02d} {block['aid']}  → (no match)")
            continue
        best = cands[0]
        # a verbatim slice of a merged segment is only trusted when unique
        if best["shape"] == "portion" and len(cands) > 1 and cands[1]["ratio"] == 1.0:
            skipped_ambiguous += 1
            print(f"  ch{block['chapter']:02d} {block['aid']}  → AMBIGUOUS "
                  f"({len(cands)} verbatim carriers) — skipped")
            continue
        aid = block["aid"]
        holder = claimed.get(aid)
        if holder:
            print(f"  ch{block['chapter']:02d} {aid}  → skipped: already claimed by {holder}")
            continue
        e = best["entry"]
        claimed[aid] = f"{e['path'].name} {e['session']['session_id']}#{e['seg'].get('index')}"
        flag = "" if best["date_ok"] else "  [DATE MISMATCH — check manually]"
        print(f"  ch{block['chapter']:02d} {aid}  → {best['shape']:>7} "
              f"{best['ratio']:.4f}  {e['path'].name} {e['session']['session_id']}"
              f" #{e['seg'].get('index')}{flag}")
        plan.append((e["path"], e["session"], e["seg"], block, best))

    print(f"\nmatched {len(plan)} / {len(blocks)} orphan blocks"
          + (f" ({skipped_ambiguous} skipped as ambiguous)" if skipped_ambiguous else ""))
    if not args.apply:
        print("dry-run — re-run with --apply to write chapter_answer_ids / chapter_indexes")
        return 0

    changed_paths: Dict[Path, dict] = {}
    written = 0
    for path, session, seg, block, cand in plan:
        aids = list(seg.get("chapter_answer_ids") or [])
        if block["aid"] not in aids:
            aids.append(block["aid"])
        seg["chapter_answer_ids"] = aids
        idxs = list(seg.get("chapter_indexes") or [])
        if block["chapter"] not in idxs:
            idxs.append(block["chapter"])
        seg["chapter_indexes"] = sorted(idxs)
        if cand["shape"] == "portion":
            # Coarse range on purpose: the carrier segment speaks several ebook
            # blocks in a row, so this block shares the segment's start/end.
            note = (f"{NOTE_PREFIX}: 本段含多個電子書 block，{block['aid']}"
                    f" 為其中之一，播放鈕共用本段時間")
            existing = seg.get("notes") or ""
            if NOTE_PREFIX not in existing:
                seg["notes"] = (existing + " | " + note).strip(" |")
        changed_paths[path] = datas[path]

    for path, data in sorted(changed_paths.items()):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written += 1
        print(f"wrote {path.relative_to(ROOT)}")
    print(f"applied {len(plan)} link(s) across {written} month file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
