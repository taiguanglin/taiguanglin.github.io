#!/usr/bin/env python3
"""講經系列 opus 音量正規化：對齊既有答疑 opus 的平均音量。

既有答疑 opus（`2024年11月11日Tai師父答疑.opus`）測得 mean_volume ≈ -11.0 dB、
max_volume ≈ 0.0 dB（crest 約 11 dB），已是壓縮平均的人聲。新轉出的講經 opus
mean_volume 約 -13 ~ -15 dB，聽起來偏小。

做法（每支檔案）：
  1. `volumedetect` 量目前 mean_volume。
  2. 計算所需增益 gain = (-11.0 - mean) + 1.4（+1.4 補償限幅器壓掉峰值的均值損失）。
  3. `volume=<gain>dB` + `alimiter=limit=0.98`（吸收增益後超過滿刻度的峰值），
     重新以 libopus 16kbps / mono / 48kHz / voip 編碼。

原地更新 `audio/jiangjing/`（不改檔名與路徑）。以 ThreadPool 平行加速。
"""
import glob
import os
import re
import subprocess
import concurrent.futures

ROOT = "/Users/paul/tai/audio/jiangjing"
TARGET_MEAN = -11.0
COMP = 1.4  # 限幅器造成的均值損失補償 (dB)


def measure_mean(path):
    r = subprocess.run(
        ["ffmpeg", "-nostats", "-hide_banner", "-i", path, "-map", "0:a",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*([-0-9.]+)\s*dB", r.stderr)
    if not m:
        raise RuntimeError("no mean_volume for %s" % path)
    return float(m.group(1))


def normalize(path):
    mean = measure_mean(path)
    gain = round(TARGET_MEAN - mean + COMP, 1)
    if gain <= 0.1:
        return os.path.relpath(path, ROOT)
    tmp = path + ".tmp.opus"
    filt = "volume=%sdB,alimiter=limit=0.98:level=false:attack=3:release=60" % gain
    cmd = ["ffmpeg", "-y", "-nostats", "-hide_banner", "-loglevel", "error",
           "-i", path, "-map", "0:a", "-af", filt,
           "-c:a", "libopus", "-b:a", "16k", "-ar", "48000", "-ac", "1",
           "-application", "voip", tmp]
    subprocess.run(cmd, check=True)
    os.replace(tmp, path)
    return os.path.relpath(path, ROOT)


def main():
    files = sorted(f for f in glob.glob(os.path.join(ROOT, "*.opus"))
                   if not f.endswith(".tmp.opus"))
    print("共 %d 支" % len(files), flush=True)
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(normalize, f): f for f in files}
        for fut in concurrent.futures.as_completed(futs):
            rel = futs[fut]
            done += 1
            try:
                fut.result()
                print("[%d/%d] ✅ %s" % (done, len(files), rel), flush=True)
            except Exception as e:
                print("[%d/%d] ❌ %s : %s" % (done, len(files), rel, e), flush=True)


if __name__ == "__main__":
    main()