#!/usr/bin/env python3
"""Extract every Q&A from the Word source exactly as the ebook build sees it.

Parses the .docx through :class:`~core.document_parser.DocumentParser` (the same
code path ``gen_all.py`` uses) so question ids, texts and ordering are
guaranteed identical to what ``inject_word_chapters()`` sees at build time.

Output: ``build/questions.json``
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

from wcommon import (  # noqa: E402
    BUILD_DIR,
    DOCX_FILE,
    normalize_question_time,
    strip_html,
)


def _bootstrap_word2ebook() -> Path:
    w2e = TOOL_DIR.parent / "word2ebook"
    if str(w2e) not in sys.path:
        sys.path.insert(0, str(w2e))
    return w2e


QUESTION_OPEN_RE = re.compile(r'<div class="question" id="([^"]+)"')
STOP_RE = re.compile(r'<div class="(?:back-to-top|nav-footer)"')
QUESTIONER_RE = re.compile(r'<span class="questioner">([^<]*)</span>')
TIME_RE = re.compile(r'<span class="question-time">([^<]*)</span>')
QTEXT_RE = re.compile(r'<div class="question-text">(.*?)</div>', re.S)
ANSWER_TEXT_RE = re.compile(r'<div class="answer-text">(.*?)</div>', re.S)
TITLE_TAG_RE = re.compile(r"<[^>]+>")


def clean(html: str) -> str:
    text = TITLE_TAG_RE.sub("", html or "")
    return (
        text.replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .strip()
    )


def parse_chapters():
    """Parse the Word docx via the real build parser; returns List[Chapter]."""
    _bootstrap_word2ebook()
    from config.settings import DEFAULT_SETTINGS  # noqa: E402
    from utils.file_utils import FileManager, ImageHandler  # noqa: E402
    from core.document_parser import DocumentParser  # noqa: E402

    out_dir = BUILD_DIR / "parse_output"
    file_manager = FileManager(out_dir)
    image_handler = ImageHandler(file_manager)
    del image_handler  # DocumentParser builds its own via file_manager
    parser = DocumentParser(DEFAULT_SETTINGS, file_manager)
    chapters, _images = parser.parse_document(DOCX_FILE)
    return chapters


def extract_questions(chapters) -> List[dict]:
    """Walk chapter HTML and pull every question block with metadata."""
    questions: List[dict] = []
    for ch in chapters:
        content = ch.content or ""
        stops = [m.start() for m in STOP_RE.finditer(content)]
        opens = list(QUESTION_OPEN_RE.finditer(content))
        qnum = 0
        for i, m in enumerate(opens):
            qnum += 1
            seg_start = m.start()
            seg_end = opens[i + 1].start() if i + 1 < len(opens) else len(content)
            for s in stops:
                if seg_start < s < seg_end:
                    seg_end = s
                    break
            block = content[seg_start:seg_end]
            qm = QUESTIONER_RE.search(block)
            tm = TIME_RE.search(block)
            qt = QTEXT_RE.search(block)
            at = ANSWER_TEXT_RE.search(block)
            time_raw = clean(tm.group(1)) if tm else ""
            date, time_part = normalize_question_time(time_raw)
            questions.append(
                {
                    "question_id": m.group(1),
                    "chapter_index": chapters.index(ch) + 1,
                    "chapter_title": clean(TITLE_TAG_RE.sub("", ch.title or "")),
                    "chapter_filename": getattr(ch, "filename", "") or "",
                    "number": qnum,
                    "questioner": clean(qm.group(1)) if qm else "",
                    "time_raw": time_raw,
                    "date": date,
                    "time_part": time_part,
                    "q_text": clean(qt.group(1)) if qt else "",
                    "a_text": strip_html(at.group(1)) if at else "",
                }
            )
    return questions


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=BUILD_DIR / "questions.json")
    args = ap.parse_args(argv)

    if not DOCX_FILE.exists():
        print(f"❌ Word source missing: {DOCX_FILE}")
        return 1

    chapters = parse_chapters()
    print(f"Parsed {len(chapters)} chapters from {DOCX_FILE.name}")

    questions = extract_questions(chapters)
    dated = sum(1 for q in questions if q["date"])
    print(f"Extracted {len(questions)} questions ({dated} with a usable date)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"Wrote {args.out}")

    # Quick sanity stats
    from collections import Counter

    by_ch = Counter(q["chapter_index"] for q in questions)
    no_date = [q for q in questions if not q["date"]]
    print("per-chapter:", dict(sorted(by_ch.items())))
    print("undated examples:", [(q["chapter_index"], q["number"], q["questioner"]) for q in no_date[:8]])
    dup_ids = {k for k, c in Counter(q["question_id"] for q in questions).items() if c > 1}
    print(f"duplicate question_ids: {len(dup_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
