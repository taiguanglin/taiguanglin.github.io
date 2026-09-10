#!/usr/bin/env python3
"""Re-run FunASR over one audio segment [t0, t1) and dump the char stream.

Used when the full-file ASR cache is truncated / VAD-mangled near the end:
splitting the segment out with ffmpeg and re-recognizing it standalone
recovers the missing text with char-level timestamps (offset back to the
original timeline by t0).

Usage:
  python3 rescore_segment.py <audio.opus> <t0> <t1> <out.json>
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    audio, t0, t1, out = (sys.argv[1], float(sys.argv[2]),
                          float(sys.argv[3]), Path(sys.argv[4]))
    from funasr import AutoModel

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav = Path(tf.name)
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-ss", str(t0), "-i", audio, "-t", str(t1 - t0), str(wav)],
        check=True)
    model = AutoModel(
        model="paraformer-zh", vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device="cpu", disable_update=True,
        punc_model="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch")
    res = model.generate(input=str(wav), cache={}, batch_size_s=60,
                         sentence_timestamp=True, disable_pbar=True)
    item = res[0]
    doc = {
        "t0": t0, "t1": t1,
        "duration": item.get("duration", t1 - t0),
        "text": item.get("text", ""),
        "timestamp": item.get("timestamp", []),
        "sentence_info": item.get("sentence_info", []),
    }
    out.write_text(json.dumps(doc, ensure_ascii=False))
    print(f"wrote {out} chars~{len(item.get('timestamp', []))} "
          f"t={t0}-{t1}")


if __name__ == "__main__":
    main()
