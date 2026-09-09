#!/usr/bin/env python3
"""Extract the question_id → answer_id pairing from the wenda2_ebook chapters
(01–12) and write ``build/answer_map.json``.

Each ``<div class="question" id="question-XXX">`` is paired with the most recent
unmatched question's ``<div class="answer" id="answer-YYY">`` in document order
(LIFO).  99.9%+ of questions pair 1:1; a handful of edge cases (a question whose
answer was merged/omitted, a closing "贴吧问题就答到这里…" pseudo-question, or a
single answer shared by two questions) are left unmapped / recorded.

Output format: {"<question_id>": "<answer_id>", ...}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EBOOK_DIR = ROOT / "wenda2_ebook"
OUT = Path(__file__).resolve().parent / "build" / "answer_map.json"

BLOCK_RE = re.compile(
    r'<div class="(question|answer)" id="((?:question|answer)-[0-9a-f]+)">'
)


def build() -> dict:
    qm: dict = {}
    open_q: list = []
    for f in sorted(EBOOK_DIR.glob("[0-9][0-9].html")):
        ch = int(f.name[:2])
        if ch > 12:
            continue
        html = f.read_text(encoding="utf-8")
        for typ, iid in BLOCK_RE.findall(html):
            if typ == "question":
                open_q.append(iid)
            elif open_q:
                qm[open_q.pop()] = iid
    return qm


def main() -> int:
    qm = build()
    OUT.write_text(json.dumps(qm, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"wrote {len(qm)} question→answer pairs to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())