#!/usr/bin/env python3
"""Extract PDF ebook sessions (opening + questions + closing) into audio_map skeletons."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from closing import closing_text_from_section
from common import (
    ANSWER_TEXT_RE,
    DEFAULT_SRT_ROOT,
    EBOOK_DIR,
    H2_RE,
    MAP_DIR,
    QUESTION_BLOCK_RE,
    QUESTION_TEXT_RE,
    chapter_html_files,
    empty_range_fields,
    resolve_media,
    session_id,
    strip_html,
)


def _answer_text_between(section_html: str, start: int, end: int) -> str:
    """All PDF answer-text paragraphs between two offsets (human-proofread)."""
    chunk = section_html[start:end]
    texts = [strip_html(t) for t in ANSWER_TEXT_RE.findall(chunk)]
    return "\n\n".join(t for t in texts if t)


def _split_sections(html: str) -> List[tuple]:
    """Return list of (h2_match, section_html) for each date+source h2."""
    matches = list(H2_RE.finditer(html))
    sections = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        sections.append((m, html[start:end]))
    return sections


def _opening_text(section_html: str) -> str:
    """First content <p> after h2, before the first .question."""
    after_h2 = re.sub(r"^.*?</h2>\s*", "", section_html, count=1, flags=re.S)
    before_q = re.split(r'<div class="question"', after_h2, maxsplit=1)[0]
    paras = re.findall(r"<p(?:\s[^>]*)?>(.*?)</p>", before_q, re.S)
    texts = [strip_html(p) for p in paras if strip_html(p)]
    return "\n".join(texts)


def extract_session_from_section(
    h2_match: re.Match,
    section_html: str,
    chapter_file: str,
    srt_root: Optional[Path] = None,
) -> Dict:
    section_id = h2_match.group(1)
    year = int(h2_match.group(2))
    month = int(h2_match.group(3))
    day = int(h2_match.group(4))
    source = strip_html(h2_match.group(5)).strip()

    media = resolve_media(year, month, day, source, srt_root=srt_root or DEFAULT_SRT_ROOT)

    opening_text = _opening_text(section_html)
    opening = None
    if opening_text:
        opening = {
            "text": opening_text,
            "text_preview": opening_text[:200],
            **empty_range_fields(),
        }

    q_matches = list(QUESTION_BLOCK_RE.finditer(section_html))
    segments = []
    for idx, qm in enumerate(q_matches, start=1):
        qid = qm.group(1)
        questioner = (qm.group(2) or "").strip()
        q_time = (qm.group(3) or "").strip()
        texts = [strip_html(t) for t in QUESTION_TEXT_RE.findall(qm.group(0))]
        q_text = "\n".join(t for t in texts if t)
        next_start = q_matches[idx].start() if idx < len(q_matches) else len(section_html)
        answer_text = _answer_text_between(section_html, qm.end(), next_start)
        answer_preview = answer_text[:120]

        key = {
            "questioner": questioner,
            "question_time": q_time,
            "index": idx,
            "section_id": section_id,
        }
        segments.append(
            {
                "index": idx,
                "question_id": qid,
                "questioner": questioner,
                "question_time": q_time,
                # Include index so multi-part posts (same questioner+time) stay unique.
                "stable_key": (
                    f"{questioner}|{q_time}|{idx}"
                    if questioner and q_time
                    else f"{section_id}#{idx}"
                ),
                "q_preview": q_text[:180],
                "q_text": q_text,
                "answer_preview": answer_preview,
                "answer_text": answer_text,
                **empty_range_fields(),
                "_key": key,
            }
        )

    closing = None
    if q_matches:
        closing_text = closing_text_from_section(section_html, q_matches[-1].start())
        if closing_text:
            closing = {
                "text": closing_text,
                "text_preview": closing_text[:200],
                **empty_range_fields(),
            }

    return {
        "session_id": session_id(year, month, day, source),
        "year": year,
        "month": month,
        "day": day,
        "date": f"{year:04d}-{month:02d}-{day:02d}",
        "source": source,
        "audio_file": media["audio_file"],
        "srt_file": media["srt_file"],
        "mp3_path": media["mp3_path"],
        "media_fallback": media.get("fallback_from"),
        "resolved_source": media.get("resolved_source"),
        "chapter_file": chapter_file,
        "section_id": section_id,
        "opening": opening,
        "segments": segments,
        "closing": closing,
    }


def extract_from_html(path: Path, srt_root: Optional[Path] = None) -> List[Dict]:
    html = path.read_text(encoding="utf-8")
    sessions = []
    for h2, section in _split_sections(html):
        sessions.append(
            extract_session_from_section(h2, section, path.name, srt_root=srt_root)
        )
    return sessions


def extract_all(
    ebook_dir: Path = EBOOK_DIR,
    srt_root: Optional[Path] = None,
    months: Optional[set] = None,
) -> Dict[str, List[Dict]]:
    """Return { 'YYYY-MM': [session, ...] }."""
    by_month: Dict[str, List[Dict]] = {}
    for path in chapter_html_files(ebook_dir):
        for session in extract_from_html(path, srt_root=srt_root):
            key = f"{session['year']:04d}-{session['month']:02d}"
            if months is not None and key not in months:
                continue
            by_month.setdefault(key, []).append(session)
    for key in by_month:
        by_month[key].sort(key=lambda s: (s["day"], s["source"]))
    return by_month


def write_skeletons(by_month: Dict[str, List[Dict]], apply: bool) -> None:
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    for key, sessions in sorted(by_month.items()):
        clean = []
        for s in sessions:
            sc = {k: v for k, v in s.items() if not k.startswith("_")}
            sc["segments"] = [
                {k: v for k, v in seg.items() if not k.startswith("_")}
                for seg in (sc.get("segments") or [])
            ]
            clean.append(sc)
        payload = {
            "month": key,
            "version": 1,
            "sessions": clean,
        }
        out = MAP_DIR / f"{key}.json"
        print(f"{key}: {len(clean)} sessions, {sum(len(s['segments']) for s in clean)} questions → {out}")
        if apply:
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Extract PDF ebook sessions into audio_map skeletons")
    parser.add_argument("--ebook-dir", type=Path, default=EBOOK_DIR)
    parser.add_argument("--month", action="append", help="YYYY-MM (repeatable)")
    parser.add_argument("--apply", action="store_true", help="Write JSON under data/audio_map/")
    args = parser.parse_args(argv)

    months = set(args.month) if args.month else None
    by_month = extract_all(ebook_dir=args.ebook_dir, months=months)
    if not by_month:
        print("No sessions found.")
        return 1
    write_skeletons(by_month, apply=args.apply)
    if not args.apply:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
