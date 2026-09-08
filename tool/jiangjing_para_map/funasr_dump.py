#!/usr/bin/env python3
"""Run FunASR (paraformer-zh + VAD + punc) over 講經 audio and dump the raw
recognition result (text + char-level timestamps + sentence_info) as JSON,
so realign_dtw.py can build a precise char-time stream.

Output: <out_dir>/<series>/<lecture>.json
  {"basename", "duration", "text", "timestamp", "sentence_info"}

Usage (run with tool/sense_voice/.venv/bin/python):
  python3 funasr_dump.py --series sishierzhang
  python3 funasr_dump.py --series sishierzhang --lecture 1
  python3 funasr_dump.py --out-dir /tmp/funasr_cache --force
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "books2ebook"))
from audio_map import AUDIO_MAP  # noqa: E402

AUDIO_DIR = Path("/Users/paul/tai/audio/jiangjing")
DEFAULT_OUT = Path("/tmp/funasr_cache")


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--series", default="sishierzhang")
    ap.add_argument("--lecture", type=int)
    ap.add_argument("--audio-dir", type=Path, default=AUDIO_DIR)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--force", action="store_true")
    return ap.parse_args()


def duration_of(path: Path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, check=True)
        return float(out.stdout.strip())
    except Exception:
        return None


def main():
    args = parse_args()
    from funasr import AutoModel

    out_dir = args.out_dir / args.series
    out_dir.mkdir(parents=True, exist_ok=True)

    lecs = AUDIO_MAP.get(args.series, {})
    if args.lecture:
        lecs = {args.lecture: lecs[args.lecture]}

    model = None
    t0 = time.time()
    for n in sorted(lecs):
        basename = lecs[n]
        opus = args.audio_dir / (basename + ".opus")
        out_path = out_dir / f"{n}.json"
        if out_path.exists() and not args.force:
            print(f"[{n}] cached: {out_path.name}")
            continue
        if not opus.exists():
            print(f"[{n}] missing audio: {opus}")
            continue

        if model is None:
            print("[INFO] loading FunASR…")
            model = AutoModel(
                model="paraformer-zh", vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                device="cpu", disable_update=True,
                punc_model="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch")
            print(f"[INFO] model ready ({time.time() - t0:.0f}s)")

        dur = duration_of(opus)
        t1 = time.time()
        res = model.generate(input=str(opus), cache={}, batch_size_s=60,
                             sentence_timestamp=True)
        item = res[0]
        doc = {
            "basename": basename,
            "duration": dur,
            "text": item.get("text", ""),
            "timestamp": item.get("timestamp"),
            "sentence_info": item.get("sentence_info"),
        }
        out_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        chars = len(doc["timestamp"]) if doc["timestamp"] else 0
        print(f"[{n}] {basename} dur={dur:.1f}s chars={chars} "
              f"asr={time.time() - t1:.1f}s -> {out_path.name}")


if __name__ == "__main__":
    main()