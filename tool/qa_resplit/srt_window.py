#!/usr/bin/env python3
"""Print, for each QA segment, the SRT subtitle text overlapping its time range.

The SRT (Simplified-Chinese ASR with accurate timestamps) is the ground truth
for what is actually said during a segment's audio window. Use it to title
segments by real content and to spot answers the auto-split mispaired.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QA_DIR = ROOT / "qa"
AUDIO_ROOT = Path.home() / "Documents"

HEADING_RE = re.compile(r"^###\s+(\d+)\.\s*(.*?)\s*$", re.M)
TIME_RE = re.compile(
    r"^時間：\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})", re.M
)
QUESTION_RE = re.compile(r"^[ \t]*(?:提問|追加問題)[:：][ \t]*(.*)$", re.M)
SRT_BLOCK_RE = re.compile(
    r"(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)",
    re.S,
)


def parse_tc(value: str) -> float:
    value = value.replace(",", ".")
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def srt_path_for(qa_path: Path) -> Path:
    year = qa_path.name[:4]
    return AUDIO_ROOT / f"{year}答疑音頻" / f"{qa_path.stem}.srt"


def parse_srt(path: Path) -> list[tuple[float, float, str]]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    cues = []
    for m in SRT_BLOCK_RE.finditer(text):
        body = " ".join(line.strip() for line in m.group(4).splitlines() if line.strip())
        cues.append((parse_tc(m.group(2)), parse_tc(m.group(3)), body))
    return cues


def segments_of(text: str):
    headings = list(HEADING_RE.finditer(text))
    for i, h in enumerate(headings):
        start_idx = h.start()
        end_idx = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[start_idx:end_idx]
        tm = TIME_RE.search(block)
        qm = QUESTION_RE.search(block)
        if not tm:
            continue
        yield (
            h.group(1),
            h.group(2),
            parse_tc(tm.group(1)),
            parse_tc(tm.group(2)),
            qm.group(1) if qm else "",
        )


def window_text(cues, start: float, end: float, limit: int) -> str:
    parts = [body for (cs, ce, body) in cues if cs < end and ce > start]
    joined = "".join(parts)
    return joined if len(joined) <= limit else joined[:limit] + "…"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--limit", type=int, default=260, help="max srt chars per segment")
    args = parser.parse_args(argv)

    for p in args.paths:
        path = Path(p) if Path(p).is_absolute() else ROOT / p
        srt = srt_path_for(path)
        print(f"===== {path.name}  (srt: {'found' if srt.exists() else 'MISSING'}) =====")
        if not srt.exists():
            continue
        cues = parse_srt(srt)
        text = path.read_text(encoding="utf-8")
        for number, title, start, end, question in segments_of(text):
            print(f"\n### {number}. {title}  [{start:.0f}s-{end:.0f}s]")
            if question:
                print(f"提問：{question[:50]}")
            print(f"SRT：{window_text(cues, start, end, args.limit)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
