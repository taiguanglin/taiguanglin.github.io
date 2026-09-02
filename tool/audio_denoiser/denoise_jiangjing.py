#!/usr/bin/env python3
"""講經系列 opus 去雜音批次：DNS64 去雜音 + 音量補償 + 重新編碼回 opus（原位替換）。

背景：
  - 講經系列音檔（audio/jiangjing/*.opus）沒有先去除雜音，聽起來雜音較多；
    答疑系列已去雜音。本腳本用既有 denoise.py（Facebook Denoiser dns64）補做去雜音。
  - 去雜音後會稍微衰減音量（本篇測得約 -0.7~-0.9 dB），因此對每支檔案
    「原始 mean_volume − 去雜音後 mean_volume」計算增益，用 `volume` 補回，
    再以 alimiter 吸收峰值，維持與原始一致的響度（使用者要求不可因去雜音而變小聲）。
  - 輸出必須維持與原檔相同的「檔名」與「格式」（libopus / mono / 48 kHz / 16 kbps /
    -application voip），因為 ebook 播放鈕 data-audio 直接指向
    `../audio/jiangjing/<原檔名>.opus`。時間長度不變（同取樣數），故 data-start/data-end 不需改。

用法：
  # 先測單支（不落地，只印結果）
  python denoise_jiangjing.py --only "2025年6月11日Tai师父讲经·楞伽经(39).opus" --dry-run

  # 處理全部（原位替換）
  python denoise_jiangjing.py

參數：
  --only NAME      只處理單支檔名（含 .opus）
  --workers N      平行處理數（預設 1，DEV 於 CPU 較穩；可提高但 CPU 已吃滿）
  --dry-run        只量測並印出增益，不寫檔
  --keep-tmp       保留 denoise.py 中間 mp3（除錯用）
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

ROOT = Path("/Users/paul/tai/audio/jiangjing")
SCRIPT_DIR = Path(__file__).resolve().parent
VENV_PY = SCRIPT_DIR / ".venv" / "bin" / "python"
DENOISE_PY = SCRIPT_DIR / "denoise.py"

# denoise.py 預設輸出 44.1k mono 128k mp3；重新編碼回 opus 的規格（與 jiangjing2audio.py 一致）
OPUS_ARGS = ["-vn", "-ac", "1", "-ar", "48000", "-c:a", "libopus", "-b:a", "16k",
             "-application", "voip"]


def require_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise SystemExit("找不到 ffmpeg，請先安裝。")
    return exe


def measure_mean(path) -> float:
    """用 ffmpeg volumedetect 量平均音量（dB）。"""
    r = subprocess.run(
        ["ffmpeg", "-nostats", "-hide_banner", "-i", str(path), "-map", "0:a",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*([-0-9.]+)\s*dB", r.stderr)
    if not m:
        raise RuntimeError(f"無法量測 mean_volume：{path}\n{r.stderr[-500:]}")
    return float(m.group(1))


def run_denoise(src: Path, out_tmp_dir: Path, stem: str) -> Path:
    """呼叫 denoise.py（dns64）輸出 denoised mp3 到暫存目錄。"""
    dst = out_tmp_dir / f"{stem}_denoised.mp3"
    cmd = [str(VENV_PY), str(DENOISE_PY), str(src), "-o", str(dst)]
    subprocess.run(cmd, check=True)
    return dst


def encode_opus(src_mp3: Path, dst_opus: Path, gain_db: float) -> None:
    """mp3 → opus（16k mono 48k voip），套用音量增益 + 限幅避免爆音。"""
    filt = f"volume={gain_db:.2f}dB,alimiter=limit=0.98:level=false:attack=3:release=60"
    cmd = ["ffmpeg", "-y", "-nostats", "-hide_banner", "-loglevel", "error",
           "-i", str(src_mp3), "-map", "0:a", "-af", filt, *OPUS_ARGS, str(dst_opus)]
    subprocess.run(cmd, check=True)


def process_one(name: str, workers: int, keep_tmp: bool, dry_run: bool, ffmpeg: str) -> str:
    src = ROOT / name
    if not src.is_file():
        return f"❌ 找不到：{name}"

    orig_mean = measure_mean(src)

    if dry_run:
        return f"📏 {name}: 原始 mean={orig_mean:.1f} dB（dry-run 不落地，未實際 denoise）"

    tmpdir = Path(tempfile.mkdtemp(prefix="denoise_jj_"))
    stem = name[:-len(".opus")] if name.endswith(".opus") else Path(name).stem
    try:
        denoised_mp3 = run_denoise(src, tmpdir, stem)
        den_mean = measure_mean(denoised_mp3)
        gain = round(orig_mean - den_mean, 2)

        out_tmp = tmpdir / f"{stem}.opus"
        encode_opus(denoised_mp3, out_tmp, gain)

        # 二次確認輸出音量
        final_mean = measure_mean(out_tmp)

        # 原子替換原檔
        os.replace(out_tmp, src)

        return (f"✅ {name}: 原始 {orig_mean:.2f} dB → 去雜音 {den_mean:.2f} dB "
                f"→ 補益 {gain:+.2f} dB → 輸出 {final_mean:.2f} dB")
    except Exception as e:
        return f"❌ {name}: {e}"
    finally:
        if not keep_tmp:
            shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    p = argparse.ArgumentParser(description="講經系列 opus 去雜音 + 音量保真（原位替換）")
    p.add_argument("--only", help="只處理單支檔名（含 .opus）")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--dry-run", action="store_true", help="只量測不寫檔")
    p.add_argument("--keep-tmp", action="store_true", help="保留中間 mp3")
    args = p.parse_args()

    ffmpeg = require_ffmpeg()
    if not VENV_PY.is_file():
        raise SystemExit(f"找不到 venv python：{VENV_PY}")

    if args.only:
        names = [args.only]
    else:
        names = sorted(f.name for f in ROOT.glob("*.opus") if not f.name.endswith(".tmp.opus"))

    print(f"共 {len(names)} 支，workers={args.workers}, dry_run={args.dry_run}", flush=True)

    if args.workers <= 1 or args.dry_run or args.only:
        done = 0
        for name in names:
            done += 1
            line = process_one(name, args.workers, args.keep_tmp, args.dry_run, ffmpeg)
            print(f"[{done}/{len(names)}] {line}", flush=True)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(process_one, n, args.workers, args.keep_tmp, args.dry_run, ffmpeg): n
                    for n in names}
            done = 0
            for fut in concurrent.futures.as_completed(futs):
                done += 1
                name = futs[fut]
                try:
                    line = fut.result()
                except Exception as e:
                    line = f"❌ {name}: {e}"
                print(f"[{done}/{len(names)}] {line}", flush=True)


if __name__ == "__main__":
    main()