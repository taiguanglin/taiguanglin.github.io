#!/usr/bin/env python3
"""Extract the AUTHORITATIVE question→answer text directly from the wenda2_ebook
HTML files (01–12, both simplified ``NN.html`` and traditional ``NN_trad.html``).

Pairing is DOM-document-order: every ``<div class="question" id="question-XXX">``
is paired with the NEXT ``<div class="answer" id="answer-YYY">`` that follows it
before any other ``question``/``answer`` div (skipping ``<hr/>`` / whitespace /
other inline markup).  Edge cases (a question with no answer, an answer with no
question, a question whose answer merges the next question) are recorded in
``_issues`` and left unpared rather than guessed.

Output: ``build/html_qa_simp.json`` / ``build/html_qa_trad.json``
  { "<question_id>": {"chapter": int, "q_text": str, "answer_id": str, "a_text": str} }
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EBOOK = ROOT / "wenda2_ebook"
OUT_DIR = Path(__file__).resolve().parent / "build"

BLOCK_RE = re.compile(
    r'<div class="(question|answer)" id="((?:question|answer)-[0-9a-f]+)">'
)
TEXT_RE = re.compile(r'<div class="(question|answer)-text">(.*?)</div>', re.S)


def strip_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value)
    value = re.sub(r"<[^>]+>", "", value)
    return htmlmod.unescape(value).strip()


def extract_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    out = {}
    issues = []
    # Walk answer-text/ question-text blocks in document order to avoid nested
    # divs: find each block opener, then its own text, then the block that
    # immediately follows it as the sibling.
    # Simpler robust approach: split on question/answer openers with positions.
    positions = []
    for m in re.finditer(
        r'<div class="(question|answer)" id="((?:question|answer)-[0-9a-f]+)">',
        raw,
    ):
        positions.append((m.start(), m.group(1), m.group(2)))

    for i, (pos, typ, full_id) in enumerate(positions):
        if typ != "question":
            continue
        qid = full_id  # "question-xxx"
        # question text: from this opener until the next block opener
        nxt = positions[i + 1][0] if i + 1 < len(positions) else len(raw)
        seg = raw[pos:nxt]
        qm = re.search(r'<div class="question-text">(.*?)</div>', seg, re.S)
        qt = strip_html(qm.group(1)) if qm else ""
        # answer: next block must be an answer (positions[i+1])
        if i + 1 >= len(positions):
            issues.append({"qid": qid, "why": "no-following-block"})
            continue
        npos, ntyp, nid = positions[i + 1]
        if ntyp != "answer":
            issues.append({"qid": qid, "why": f"next-block-is-{ntyp}({nid})"})
            continue
        # answer text: from npos to positions[i+2]
        aend = positions[i + 2][0] if i + 2 < len(positions) else len(raw)
        aseg = raw[npos:aend]
        am = re.search(r'<div class="answer-text">(.*?)</div>', aseg, re.S)
        at = strip_html(am.group(1)) if am else ""
        out[qid] = {
            "chapter": int(path.name[:2]),
            "q_text": qt,
            "answer_id": nid,
            "a_text": at,
        }
    return {"qa": out, "issues": issues}


def main() -> int:
    for suffix, pattern in (("simp", "[0-9][0-9].html"), ("trad", "[0-9][0-9]_trad.html")):
        qa = {}
        issues = []
        for p in sorted(EBOOK.glob(pattern)):
            ch = int(p.name[:2])
            if ch > 12:
                continue
            r = extract_file(p)
            qa.update(r["qa"])
            issues.extend(r["issues"])
        out = OUT_DIR / f"html_qa_{suffix}.json"
        out.write_text(json.dumps(qa, ensure_ascii=False, indent=1) + "\n", "utf-8")
        print(f"{suffix}: {len(qa)} question→answer pairs; {len(issues)} pairing issues → {out}")
        if suffix == "simp":
            (OUT_DIR / "html_qa_issues.json").write_text(
                json.dumps(issues, ensure_ascii=False, indent=1) + "\n", "utf-8"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())