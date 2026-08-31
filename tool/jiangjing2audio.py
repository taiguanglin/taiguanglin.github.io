#!/usr/bin/env python3
"""mp3 → opus 批次轉檔（講經系列），輸出到 /Users/paul/tai/audio/jiangjing/。

規格：libopus, 單聲道, 48 kHz, 16 kbps CBR。對齊既有答疑 opus 的體積（同時長的檔案大小相當）。

命名：以「講次編號 N」為鍵；輸出檔名 `<系列>/<N>.opus`（保留系列前綴以便辨識）。

對照既有 `2024年11月11日Tai師父答疑.opus` (6313s / 13.6MB ≈ 17 kbps)；
ffmpeg `-b:a 16k` 對人聲單聲道接近此體積（誤差 < 20%）。
"""
import os
import re
import subprocess
import sys

SRC_ROOT = os.path.expanduser("~/Downloads")
OUT_ROOT = "/Users/paul/tai/audio/jiangjing"

# 系列定義：根目錄, 子目錄(可含括號), 檔名中提取講次 N 的 regex
SERIES = [
    # (output_subdir, search_dir, regex)
    ("ganen",
     SRC_ROOT,  # 感恩的 mp3 直接放在 Downloads 根目錄
     r"感恩与讲经.*\.mp3$"),  # 只有一支，序號 1
    ("sishierzhang",
     os.path.join(SRC_ROOT, "Tai师父讲《四十二章经》/音頻"),
     r"四十二章经[（(]?(\d+)[）)]"),
    ("lengqie",
     os.path.join(SRC_ROOT, "Tai师父讲《楞伽经》/楞伽经音频（1-42）"),
     r"楞伽经[（(]?(\d+)[）)]"),
    ("liuzutanjing",
     os.path.join(SRC_ROOT, "Tai师父讲《六祖坛经》/音频"),
     r"六祖坛经[（(]?(\d+)[）)]"),
    ("lengyanjing",
     os.path.join(SRC_ROOT, "Tai师父讲《楞严经》(未完)/音频(更新到21,未講完)"),
     r"楞严经[（(]?(\d+)[）)]"),
]

# 感恩講次固定的序號
GANEN_LECTURE_NO = 1


def convert(src, dst):
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", src,
        "-vn", "-ac", "1", "-ar", "48000",
        "-c:a", "libopus", "-b:a", "16k",
        "-application", "voip",
        dst,
    ]
    subprocess.run(cmd, check=True)


def main():
    os.makedirs(OUT_ROOT, exist_ok=True)
    summary = []
    for sub, srcdir, pat in SERIES:
        if not os.path.isdir(srcdir):
            print("⚠️ 缺少來源：%s" % srcdir, file=sys.stderr)
            continue
        outdir = os.path.join(OUT_ROOT, sub)
        os.makedirs(outdir, exist_ok=True)
        rx = re.compile(pat)
        files = sorted(os.listdir(srcdir))
        for fn in files:
            if not fn.lower().endswith(".mp3"):
                continue
            m = rx.search(fn)
            if not m:
                print("⚠️ 無法從檔名提取講次：%s" % fn, file=sys.stderr)
                continue
            if sub == "ganen":
                n = GANEN_LECTURE_NO
            else:
                n = int(m.group(1))
            src = os.path.join(srcdir, fn)
            dst = os.path.join(outdir, "%02d.opus" % n)
            if os.path.exists(dst):
                print("⏭ %s 已存在" % dst)
                summary.append((sub, n, dst, "skip"))
                continue
            convert(src, dst)
            sz_in = os.path.getsize(src)
            sz_out = os.path.getsize(dst)
            print("✅ %s %02d.opus  %s → %s (%.1fMB)" % (
                sub, n, sz_in, sz_out, sz_out / 1024 / 1024))
            summary.append((sub, n, dst, sz_out))
    # 印出彙總
    print("\n=== 彙總 ===")
    for s, n, p, x in summary:
        if isinstance(x, int):
            print("%s %02d → %s  %.2f MB" % (s, n, p, x / 1024 / 1024))
        else:
            print("%s %02d → %s  %s" % (s, n, p, x))


if __name__ == "__main__":
    main()
