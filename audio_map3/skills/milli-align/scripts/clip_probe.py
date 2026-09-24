#!/usr/bin/env python3
"""clip_probe — 40s 音檔切片 ASR 複驗（milli-align skill §5／§4.4 教訓的標準工具）.

**為什麼需要它**：長音檔的 FunASR `sentence_info`／SRT 時間是「壓縮」的
（≈ +6.5% of elapsed），只有全域 `timestamp` 對；而字級流在同音錯字密集區會大段掉字。
所以「判 zero／改邊界」前，用 40s 切片重跑 ASR 取得的絕對時間才是可靠證據。

切片長度固定 ~40s：太短（<30s）常 IndexError 或只吐一句亂碼，太長則再現壓縮漂移。

用法：
  clip_probe.py --series lengqie --lecture 26 --windows "100-140,700-740,1200-1240"
  clip_probe.py --series lengqie --lecture 26 --centers "1557.9,1836.4"   # 各開 40s 窗（-4s 起）
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DUMP_DIR = Path("/tmp/funasr_cache")
AUDIO_DIR = Path("/Users/paul/tai/audio/jiangjing")
CLIP_LEN = 40.0


def audio_of(series, lecture):
    d = json.loads((DUMP_DIR / series / f"{lecture}.json").read_text(encoding="utf-8"))
    return AUDIO_DIR / f"{d['basename']}.opus"


def extract(src, start, length, dst):
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", str(src),
         "-ar", "16000", "-ac", "1", str(dst)],
        check=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--lecture", required=True)
    ap.add_argument("--windows", help="'a-b,c-d'（b-a≈40 最佳）")
    ap.add_argument("--centers", help="'t1,t2'：各開 [t-4, t+36]")
    ap.add_argument("--len", type=float, default=CLIP_LEN)
    ap.add_argument("--vad-ms", type=int, default=10000,
                    help="VAD 單段上限（毫秒）；切片複驗必須 ≤10000，見下方註解")
    a = ap.parse_args()

    wins = []
    if a.windows:
        for part in a.windows.split(","):
            lo, hi = part.split("-")
            wins.append((float(lo), float(hi)))
    if a.centers:
        for part in a.centers.split(","):
            t = float(part)
            wins.append((max(0.0, t - 4.0), max(0.0, t - 4.0) + a.len))
    if not wins:
        ap.error("need --windows or --centers")

    src = audio_of(a.series, a.lecture)
    print(f"# {src.name}  ({len(wins)} clips)")

    from funasr import AutoModel
    # VAD 段長上限**必須**遠小於切片長度：切片若被 VAD 判成單一長段（連續講話），
    # paraformer 只會吐出該段尾部 ~10s，其餘**靜默丟棄**（L16 [29] 實證：
    # mst=30000 → 40s 切片只認出最後 10s / 48 字；mst=10000 → 213 字全出）。
    # 同一支音檔跑「全長」時 VAD 分段不同，30000 完全正常（全檔 5000/30000
    # 逐桶比對零差異）——所以這個坑只在切片複驗時咬人。
    m = AutoModel(model="paraformer-zh", vad_model="fsmn-vad",
                  vad_kwargs={"max_single_segment_time": a.vad_ms}, device="cpu",
                  disable_update=True, log_level="ERROR",
                  punc_model="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch")

    with tempfile.TemporaryDirectory() as td:
        for lo, hi in wins:
            wav = Path(td) / "clip.wav"
            extract(src, lo, hi - lo, wav)
            try:
                res = m.generate(input=str(wav), cache={}, batch_size_s=60, sentence_timestamp=True)
            except Exception as e:              # noqa: BLE001
                print(f"\n===== {lo:.1f}-{hi:.1f}  FAILED {type(e).__name__}: {e}")
                continue
            print(f"\n===== {lo:.1f}-{hi:.1f} =====")
            for s in (res[0].get("sentence_info") or []):
                print(f"  {lo + s['start'] / 1000:8.2f}-{lo + s['end'] / 1000:8.2f} {s['text']}")


if __name__ == "__main__":
    main()
