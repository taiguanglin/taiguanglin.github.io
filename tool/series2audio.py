#!/usr/bin/env python3
"""新系列（義理／圓覺經／心經／金剛經）mp3|m4a → 去雜音 + 音量正規化 → opus。

沿用既有 audio/jiangjing 的做法與規格：

  1. ffmpeg 解碼 → 16 kHz 單聲道 WAV（`tool/audio_denoiser/denoise.py`）
  2. Facebook Denoiser **dns64** 去雜音（30 s 分段、0.5 s 重疊）
  3. 量去雜音後 mean_volume，編碼 opus 時補回增益：
     gain = TARGET_MEAN(-11.0 dB) − mean + COMP(1.4 dB，限幅器吃掉的平均值)
     濾鏡 `volume=<gain>dB,alimiter=limit=0.98:level=false:attack=3:release=60`
  4. 輸出 opus 規格與 `tool/jiangjing2audio.py` 一致：
     libopus / mono / 48 kHz / 16 kbps / -application voip
     （對齊既有 `2024年11月11日Tai師父答疑.opus` 的 17 kbps，同時長體積相當）
  5. 再量輸出的 mean_volume；與目標差 > 0.6 dB 就以修正增益重編一次。

模型每個 worker process 只載入一次；以 multiprocessing 平行（預設 3 個 worker）。

用法：
  source tool/audio_denoiser/.venv/bin/activate   # 需要 torch / soundfile
  python tool/series2audio.py --dry-run           # 只印來源 → 目標對照
  python tool/series2audio.py                     # 實際轉檔（跳過已存在的輸出）
  python tool/series2audio.py --series yili       # 只做某個系列
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
DENOISER_DIR = TOOL_DIR / "audio_denoiser"
sys.path.insert(0, str(DENOISER_DIR))

TARGET_MEAN = -11.0  # 對齊既有答疑 opus 的平均音量
COMP = 1.4           # alimiter 造成平均值下降的補償 (dB)
MAX_FIX = 0.6        # 輸出音量與目標差距超過此值就重編一次
SR_MODEL = 16_000
CHUNK_SECONDS = 30.0
OVERLAP_SECONDS = 0.5

OPUS_ARGS = ["-vn", "-ac", "1", "-ar", "48000", "-c:a", "libopus", "-b:a", "16k",
             "-application", "voip"]

AUDIO_ROOT = Path("/Users/paul/tai/audio")
DOWNLOADS = Path(os.path.expanduser("~/Downloads"))

# 系列定義：輸出資料夾 / 來源資料夾 / 來源副檔名
SERIES = [
    dict(
        key="yili",
        label="義理",
        out_dir=AUDIO_ROOT / "yili",
        src_dir=DOWNLOADS / "Tai师父义理" / "音頻",
        exts=(".mp3", ".m4a"),
    ),
    dict(
        key="yuanjuejing",
        label="圓覺經",
        out_dir=AUDIO_ROOT / "jiangjing",
        src_dir=DOWNLOADS / "Tai师父讲《圆觉经》" / "音頻",
        exts=(".mp3", ".m4a"),
    ),
    dict(
        key="xinjing",
        label="心經",
        out_dir=AUDIO_ROOT / "jiangjing",
        src_dir=DOWNLOADS / "Tai师父讲《心经》" / "音頻",
        exts=(".mp3", ".m4a"),
    ),
    dict(
        key="jingangjing",
        label="金剛經",
        out_dir=AUDIO_ROOT / "jiangjing",
        src_dir=DOWNLOADS / "Tai师父讲《金刚经》" / "音頻",
        exts=(".mp3", ".m4a"),
    ),
]

DROP_SUFFIX = re.compile(r"（(?:音频版|音頻版|文字版|群文件版)）")


def target_name(filename: str) -> str:
    """來源檔名 → 輸出 opus 檔名（去版本後綴、正規化 `·` 與空白、全形講次號轉半形）。"""
    stem = Path(filename).stem
    stem = re.sub(r"（(\d+)）", r"(\1)", stem)          # 圓覺經（12）→ (12)
    stem = DROP_SUFFIX.sub("", stem)                    # 去掉（音频版）
    stem = re.sub(r"\s*·\s*", "·", stem)                # `·` 前後不加空白
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem + ".opus"


def collect(series):
    """回傳 [(src, dst), ...]（依來源檔名排序）。"""
    src_dir = series["src_dir"]
    if not src_dir.is_dir():
        raise SystemExit(f"找不到來源資料夾：{src_dir}")
    pairs = []
    for fn in sorted(os.listdir(src_dir)):
        if not fn.lower().endswith(series["exts"]):
            continue
        pairs.append((src_dir / fn, series["out_dir"] / target_name(fn)))
    return pairs


# ---------------------------------------------------------------- 音訊處理

_FFMPEG = None
_MODEL = None


def ffmpeg() -> str:
    global _FFMPEG
    if _FFMPEG is None:
        exe = shutil.which("ffmpeg")
        if not exe:
            raise SystemExit("找不到 ffmpeg")
        _FFMPEG = exe
    return _FFMPEG


def model():
    """dns64 模型（含權重），每個 process 只載入一次。"""
    global _MODEL
    if _MODEL is None:
        import torch
        import denoise as D
        from denoiser.pretrained import DNS_64_URL

        torch.set_num_threads(int(os.environ.get("TORCH_THREADS", "2")))
        m = D.dns64(pretrained=False)
        state = D.load_state_dict_from_url_or_curl(DNS_64_URL, "cpu")
        m.load_state_dict(state)
        m.eval()
        _MODEL = m
    return _MODEL


def measure_mean(path) -> float:
    r = subprocess.run(
        [ffmpeg(), "-nostats", "-hide_banner", "-i", str(path), "-map", "0:a",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*([-0-9.]+)\s*dB", r.stderr)
    if not m:
        raise RuntimeError(f"無法量測 mean_volume：{path}")
    return float(m.group(1))


def encode_opus(src, dst, gain_db: float) -> None:
    filt = (f"volume={gain_db:.2f}dB,"
            "alimiter=limit=0.98:level=false:attack=3:release=60")
    subprocess.run(
        [ffmpeg(), "-y", "-nostats", "-hide_banner", "-loglevel", "error",
         "-i", str(src), "-map", "0:a", "-af", filt, *OPUS_ARGS, str(dst)],
        check=True)


def process(pair) -> str:
    import numpy as np
    import soundfile as sf
    import denoise as D
    import torch

    src, dst = pair
    name = os.path.basename(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    tmpdir = Path(tempfile.mkdtemp(prefix="series2audio_"))
    try:
        in16 = tmpdir / "in16.wav"
        out16 = tmpdir / "out16.wav"

        D.decode_to_16k_mono_wav(ffmpeg(), src, in16)
        wav, sr = sf.read(in16, dtype="float32", always_2d=False)
        if sr != SR_MODEL:
            raise RuntimeError(f"預期 {SR_MODEL} Hz，實得 {sr}")
        if wav.ndim > 1:
            wav = wav.mean(axis=1).astype(np.float32)
        wav = np.clip(wav, -1.0, 1.0).astype(np.float32)

        m = model()
        den = D.denoise_chunks(
            m, wav, torch.device("cpu"),
            int(CHUNK_SECONDS * SR_MODEL), int(OVERLAP_SECONDS * SR_MODEL))
        sf.write(out16, np.clip(den, -1.0, 1.0), SR_MODEL, subtype="PCM_16")

        gain = round(TARGET_MEAN - measure_mean(out16) + COMP, 2)
        tmp_opus = tmpdir / name
        encode_opus(out16, tmp_opus, gain)

        final = measure_mean(tmp_opus)
        if abs(final - TARGET_MEAN) > MAX_FIX:
            gain = round(gain + (TARGET_MEAN - final), 2)
            encode_opus(out16, tmp_opus, gain)
            final = measure_mean(tmp_opus)

        size_mb = tmp_opus.stat().st_size / 1024 / 1024
        os.replace(tmp_opus, dst)
        return (f"✅ {name}  gain={gain:+.2f}dB  mean={final:.1f}dB  "
                f"{size_mb:.1f}MB")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    p = argparse.ArgumentParser(description="新系列 → 去雜音 + 正規化 opus")
    p.add_argument("--series", action="append", help="只做指定系列 key（可重複）")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--limit", type=int, help="每個系列最多處理幾支（測試用）")
    p.add_argument("--dry-run", action="store_true", help="只印來源 → 目標")
    p.add_argument("--force", action="store_true", help="輸出已存在時仍重轉")
    args = p.parse_args()

    selected = [s for s in SERIES
                if not args.series or s["key"] in args.series]
    if not selected:
        raise SystemExit("--series 沒有對應的系列")

    jobs = []
    seen = {}
    for s in selected:
        pairs = collect(s)
        if args.limit:
            pairs = pairs[: args.limit]
        for src, dst in pairs:
            if dst in seen:
                raise SystemExit(f"檔名衝突：{seen[dst]} 與 {src} → {dst.name}")
            seen[dst] = src
            skip = dst.exists() and not args.force
            jobs.append((s, src, dst, skip))

    print(f"共 {len(jobs)} 支（跳過已存在 "
          f"{sum(1 for j in jobs if j[3])} 支）", flush=True)

    if args.dry_run:
        for s, src, dst, skip in jobs:
            print(f"[{s['key']}]{'⏭' if skip else '→'} {src.name}\n"
                  f"      ⇒ {dst}")
        return

    todo = [(src, dst) for s, src, dst, skip in jobs if not skip]
    if not todo:
        print("沒有需要處理的檔案")
        return

    done = 0
    workers = 1 if args.limit else max(1, args.workers)
    if workers == 1:
        for pair in todo:
            done += 1
            try:
                line = process(pair)
            except Exception as e:
                line = f"❌ {pair[1].name}: {e}"
            print(f"[{done}/{len(todo)}] {line}", flush=True)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(process, pair): pair for pair in todo}
            for fut in concurrent.futures.as_completed(futs):
                done += 1
                pair = futs[fut]
                try:
                    line = fut.result()
                except Exception as e:
                    line = f"❌ {pair[1].name}: {e}"
                print(f"[{done}/{len(todo)}] {line}", flush=True)


if __name__ == "__main__":
    main()
