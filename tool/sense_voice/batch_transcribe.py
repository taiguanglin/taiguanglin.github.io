#!/usr/bin/env python3
"""批次跑 transcribe.py：對目錄下所有 mp3/wav/m4a 產生 .srt + .txt。

特性：
- 共用同一個 FunASR AutoModel（模型只載入一次），比反覆 spawn ``transcribe.py`` 快
- 若同目錄已存在 ``<name>.srt`` 與 ``<name>.txt`` 則自動跳過
- 預設按檔案大小由小到大處理（先看到結果）
- 推論失敗的檔案會記錄到 ``failed.log`` 並繼續下一個
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".mp4"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="批次語音辨識（Paraformer-zh + VAD + 標點）→ SRT/TXT")
    p.add_argument("input_dir", type=str, help="輸入資料夾")
    p.add_argument("-o", "--output-dir", type=str, default=None,
                   help="輸出資料夾（預設：與輸入同目錄）")
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--asr-model", type=str, default="paraformer-zh")
    p.add_argument("--vad-model", type=str, default="fsmn-vad")
    p.add_argument(
        "--punc-model", type=str,
        default="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
        help="標點還原模型；可設 'ct-punc' 用 cn-en 大模型，或 'none' 停用",
    )
    p.add_argument("--vad-max-segment-ms", type=int, default=30000)
    p.add_argument("--batch-size-s", type=int, default=60)
    p.add_argument("--max-line-chars", type=int, default=28)
    p.add_argument("--max-cue-seconds", type=float, default=8.0)
    p.add_argument("--order", choices=["size", "name", "name-desc"], default="size",
                   help="處理順序：size=小到大、name=檔名升冪、name-desc=檔名降冪")
    p.add_argument("--limit", type=int, default=0, help="只處理前 N 個檔案（0=不限）")
    p.add_argument("--force", action="store_true", help="即使已有 .srt/.txt 也重做")
    return p.parse_args()


def collect_audio_files(in_dir: Path, order: str) -> list[Path]:
    files = [p for p in in_dir.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS]
    if order == "size":
        files.sort(key=lambda p: p.stat().st_size)
    elif order == "name":
        files.sort(key=lambda p: p.name)
    elif order == "name-desc":
        files.sort(key=lambda p: p.name, reverse=True)
    return files


def process_one(model, src: Path, out_base: Path, args, build_cues_from_sentence_info,
                build_cues_from_char_timestamps, write_srt) -> tuple[bool, str]:
    res = model.generate(
        input=str(src),
        cache={},
        batch_size_s=args.batch_size_s,
        sentence_timestamp=True,
        disable_pbar=True,
    )
    if not res:
        return False, "FunASR 未回傳結果"
    item = res[0]
    full_text = (item.get("text") or "").strip()

    txt_path = out_base.with_suffix(".txt")
    txt_path.write_text(full_text + "\n", encoding="utf-8")

    max_cue_ms = args.max_cue_seconds * 1000.0
    sentence_info = item.get("sentence_info")
    if sentence_info:
        cues = build_cues_from_sentence_info(sentence_info, max_cue_ms, args.max_line_chars)
    elif item.get("timestamp"):
        cues = build_cues_from_char_timestamps(
            full_text, item["timestamp"], max_cue_ms, args.max_line_chars,
        )
    else:
        cues = []

    if cues:
        srt_path = out_base.with_suffix(".srt")
        write_srt(srt_path, cues)
    return True, f"text={len(full_text)} chars, cues={len(cues)}"


def main() -> int:
    args = parse_args()
    in_dir = Path(args.input_dir).expanduser().resolve()
    if not in_dir.is_dir():
        print(f"[ERROR] 不是有效資料夾: {in_dir}", file=sys.stderr)
        return 2
    out_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else in_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    files = collect_audio_files(in_dir, args.order)
    if not files:
        print(f"[ERROR] 在 {in_dir} 找不到任何音檔", file=sys.stderr)
        return 2
    if args.limit > 0:
        files = files[: args.limit]

    # 從 transcribe.py 共用工具函式
    from transcribe import (
        build_cues_from_sentence_info,
        build_cues_from_char_timestamps,
        write_srt,
    )

    print(f"[INFO] 共 {len(files)} 個檔案，依 {args.order} 排序處理")
    print("[INFO] 載入 FunASR (Paraformer-zh + VAD + 標點)…")
    from funasr import AutoModel
    t0 = time.time()
    auto_kwargs = dict(
        model=args.asr_model,
        vad_model=args.vad_model,
        vad_kwargs={"max_single_segment_time": args.vad_max_segment_ms},
        device=args.device,
        disable_update=True,
        disable_pbar=True,
        disable_log=True,
    )
    if args.punc_model and args.punc_model.lower() != "none":
        auto_kwargs["punc_model"] = args.punc_model
    model = AutoModel(**auto_kwargs)
    print(f"[INFO] 模型載入完成（{time.time() - t0:.1f}s）")

    fail_log = out_dir / "failed.log"
    n_ok = n_skip = n_fail = 0
    for i, src in enumerate(files, 1):
        out_base = (out_dir / src.stem)
        srt = out_base.with_suffix(".srt")
        txt = out_base.with_suffix(".txt")
        if not args.force and srt.exists() and txt.exists():
            print(f"[{i}/{len(files)}] SKIP {src.name}（已有 .srt/.txt）")
            n_skip += 1
            continue
        size_mb = src.stat().st_size / 1024 / 1024
        print(f"[{i}/{len(files)}] {src.name}（{size_mb:.1f} MB）…", flush=True)
        t1 = time.time()
        try:
            ok, info = process_one(
                model, src, out_base, args,
                build_cues_from_sentence_info,
                build_cues_from_char_timestamps,
                write_srt,
            )
            elapsed = time.time() - t1
            if ok:
                print(f"    [OK] {info}，耗時 {elapsed:.1f}s")
                n_ok += 1
            else:
                print(f"    [FAIL] {info}")
                n_fail += 1
                with fail_log.open("a", encoding="utf-8") as f:
                    f.write(f"{src}\t{info}\n")
        except Exception as e:
            elapsed = time.time() - t1
            print(f"    [ERROR] {type(e).__name__}: {e}（耗時 {elapsed:.1f}s）")
            traceback.print_exc()
            n_fail += 1
            with fail_log.open("a", encoding="utf-8") as f:
                f.write(f"{src}\t{type(e).__name__}: {e}\n")

    print(f"\n[DONE] 成功 {n_ok}，跳過 {n_skip}，失敗 {n_fail}")
    if n_fail:
        print(f"[INFO] 失敗清單：{fail_log}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
