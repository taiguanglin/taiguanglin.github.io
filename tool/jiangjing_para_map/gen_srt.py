#!/usr/bin/env python3
"""Generate precise per-lecture SRT subtitles from the final audio_map3 map.

Each spoken paragraph becomes one cue with the map's verified (start, end)
boundaries — the start is pinned to the millisecond-level timestamp of the
paragraph's first spoken character (FunASR char-level timestamps). Unspoken
blocks (zero-width skipped-sutra markers / placeholders) emit no cue.

Output: audio_map3/srt/<series>/<basename>.srt  (basename matches the audio
file so players auto-load the subtitles when placed next to it).

Usage:
  python3 gen_srt.py --series lengqie
  python3 gen_srt.py --series lengqie --lecture 7
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP_DIR = ROOT / "audio_map3"
OUT_DIR = ROOT / "audio_map3" / "srt"

WRAP = 30  # max chars per cue line


def ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap(text: str, width: int = WRAP) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    lines = []
    while len(text) > width:
        cut = text.rfind(" ", 0, width + 1)
        if cut < width // 2:
            cut = width
        lines.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        lines.append(text)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--series", default="lengqie")
    ap.add_argument("--lecture", type=int)
    args = ap.parse_args()

    map_path = MAP_DIR / f"{args.series}.json"
    doc = json.loads(map_path.read_text(encoding="utf-8"))
    out_dir = OUT_DIR / args.series
    out_dir.mkdir(parents=True, exist_ok=True)

    lecs = doc.get("lectures", {})
    if args.lecture:
        lecs = {str(args.lecture): lecs[str(args.lecture)]}

    sys.path.insert(0, str(ROOT / "tool" / "books2ebook"))
    from audio_map import AUDIO_MAP  # noqa: E402

    for n in sorted(lecs, key=int):
        lec = lecs[n]
        cues = []
        for p in lec.get("paragraphs", []):
            start, end = p.get("start"), p.get("end")
            if start is None or end is None or end - start < 0.05:
                continue  # unspoken / zero-width marker
            text = (p.get("text") or "").strip()
            if not text:
                continue
            cues.append((start, end, text))
        if not cues:
            continue
        basename = lec.get("basename") \
            or AUDIO_MAP.get(args.series, {}).get(int(n)) \
            or f"{n}"
        lines = []
        for k, (s, e, text) in enumerate(cues, 1):
            lines.append(f"{k}")
            lines.append(f"{ts(s)} --> {ts(max(e, s + 0.2))}")
            lines.append(wrap(text))
            lines.append("")
        out = out_dir / f"{basename}.srt"
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"[{n}] {len(cues):3d} cues -> {out.name}")


if __name__ == "__main__":
    main()
