#!/usr/bin/env python3
"""使用 FunASR (Paraformer-zh + fsmn-vad + ct-punc) 將中文音檔轉成
字幕 (.srt) 與純文字 (.txt)。

預設輸出與輸入檔同目錄、同檔名，副檔名分別為 ``.srt``、``.txt``。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass


SENT_END_RE = re.compile(r"[。！？!?]+|[，、；,;:]")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Paraformer-zh 中文語音辨識並輸出 SRT 字幕",
    )
    p.add_argument("input", type=str, help="輸入音檔路徑（mp3/wav/m4a 等）")
    p.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="輸出檔基底路徑（會加 .srt / .txt；預設：與輸入同名）",
    )
    p.add_argument("--device", type=str, default="cpu", help="cpu / cuda:0")
    p.add_argument(
        "--asr-model", type=str, default="paraformer-zh",
        help="ASR 模型名稱（預設 paraformer-zh）",
    )
    p.add_argument(
        "--vad-model", type=str, default="fsmn-vad",
        help="VAD 模型名稱（預設 fsmn-vad）",
    )
    p.add_argument(
        "--punc-model", type=str,
        default="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
        help=(
            "標點還原模型。預設為 Chinese-only 較小版（約 280MB）；"
            "若要中英混排可改成 'ct-punc'（會下載 ~1GB 大模型）；"
            "設 'none' 可停用標點還原。"
        ),
    )
    p.add_argument(
        "--vad-max-segment-ms", type=int, default=30000,
        help="VAD 切段最大毫秒數（預設 30000）",
    )
    p.add_argument(
        "--max-line-chars", type=int, default=28,
        help="SRT 單行最多字數（中文預設 28）",
    )
    p.add_argument(
        "--max-cue-seconds", type=float, default=8.0,
        help="SRT 單則字幕最長秒數（預設 8 秒，超過會切開）",
    )
    p.add_argument("--no-srt", action="store_true", help="不輸出 .srt")
    p.add_argument("--no-txt", action="store_true", help="不輸出 .txt")
    return p.parse_args()


def fmt_srt_time(ms: float) -> str:
    if ms < 0:
        ms = 0
    total_ms = int(round(ms))
    hours, rem = divmod(total_ms, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, msec = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{msec:03d}"


def _split_chunk_into_lines(text: str, max_chars: int) -> list[str]:
    """把單個字幕區段的長文本切成最多兩行，盡量在標點/空白處斷行。"""
    text = text.strip()
    if not text:
        return [""]
    if len(text) <= max_chars:
        return [text]
    # 嘗試在中段附近找一個標點/空白
    mid = len(text) // 2
    best = None
    for i in range(max(1, mid - max_chars // 2), min(len(text) - 1, mid + max_chars // 2)):
        if text[i] in "。！？!?，、；,;: ":
            best = i + 1
            break
    if best is None:
        best = max_chars
    return [text[:best].strip(), text[best:].strip()]


def build_cues_from_sentence_info(sentence_info, max_cue_ms: float, max_chars: int):
    """從 FunASR 的 sentence_info 產生字幕條目。"""
    cues = []
    for s in sentence_info:
        text = (s.get("text") or "").strip()
        start = float(s.get("start", 0))
        end = float(s.get("end", start))
        if not text:
            continue
        # 把過長的句子再依時間/字數均分
        cues.extend(_split_long_cue(text, start, end, max_cue_ms, max_chars))
    return cues


def _split_long_cue(text: str, start_ms: float, end_ms: float,
                    max_cue_ms: float, max_chars: int):
    duration = max(1.0, end_ms - start_ms)
    n_parts_time = int((duration + max_cue_ms - 1) // max_cue_ms)
    n_parts_char = (len(text) + max_chars * 2 - 1) // (max_chars * 2)
    n = max(1, n_parts_time, n_parts_char)
    if n == 1:
        return [{"start": start_ms, "end": end_ms, "text": text}]
    out = []
    seg_len = duration / n
    chunk_size = (len(text) + n - 1) // n
    for i in range(n):
        s = start_ms + i * seg_len
        e = start_ms + (i + 1) * seg_len if i < n - 1 else end_ms
        chunk = text[i * chunk_size : (i + 1) * chunk_size].strip()
        if not chunk:
            continue
        out.append({"start": s, "end": e, "text": chunk})
    return out


def build_cues_from_char_timestamps(text: str, timestamps, max_cue_ms: float, max_chars: int):
    """退路：用每個字（不含標點）的時間戳 + 文本中的標點來切句。

    ``timestamps`` 是 [[start_ms, end_ms], ...]，數量 = 非標點字數。
    """
    cues = []
    cur_start = None
    cur_end = None
    cur_text = []
    ts_idx = 0

    def flush():
        if cur_text and cur_start is not None and cur_end is not None:
            cues.extend(_split_long_cue(
                "".join(cur_text).strip(),
                cur_start, cur_end, max_cue_ms, max_chars,
            ))

    for ch in text:
        if ch.isspace():
            continue
        if SENT_END_RE.match(ch):
            cur_text.append(ch)
            # 句子結束（句末標點）
            if ch in "。！？!?":
                flush()
                cur_start, cur_end, cur_text = None, None, []
            continue
        # 一般字 → 配對時間戳
        if ts_idx < len(timestamps):
            s, e = timestamps[ts_idx]
            if cur_start is None:
                cur_start = float(s)
            cur_end = float(e)
            ts_idx += 1
        cur_text.append(ch)
        # 過長就先 flush
        if cur_start is not None and cur_end is not None and (cur_end - cur_start) >= max_cue_ms:
            flush()
            cur_start, cur_end, cur_text = None, None, []
    flush()
    return cues


def write_srt(path: Path, cues) -> None:
    lines = []
    for i, c in enumerate(cues, 1):
        body = "\n".join(_split_chunk_into_lines(c["text"], 28))
        lines.append(str(i))
        lines.append(f"{fmt_srt_time(c['start'])} --> {fmt_srt_time(c['end'])}")
        lines.append(body)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"[ERROR] 找不到輸入檔案: {input_path}", file=sys.stderr)
        return 2

    base = Path(args.output).expanduser().resolve() if args.output else input_path.with_suffix("")
    base.parent.mkdir(parents=True, exist_ok=True)

    print("[INFO] 載入 FunASR (Paraformer-zh + VAD + 標點)…")
    from funasr import AutoModel

    automodel_kwargs = dict(
        model=args.asr_model,
        vad_model=args.vad_model,
        vad_kwargs={"max_single_segment_time": args.vad_max_segment_ms},
        device=args.device,
        disable_update=True,
    )
    if args.punc_model and args.punc_model.lower() != "none":
        automodel_kwargs["punc_model"] = args.punc_model

    t0 = time.time()
    model = AutoModel(**automodel_kwargs)
    print(f"[INFO] 模型載入完成（{time.time() - t0:.1f}s），開始辨識：{input_path.name}")

    t1 = time.time()
    res = model.generate(
        input=str(input_path),
        cache={},
        batch_size_s=60,
        sentence_timestamp=True,  # 部分版本支援；忽略也無妨
    )
    elapsed = time.time() - t1
    print(f"[OK] 辨識完成，耗時 {elapsed:.1f}s")

    if not res:
        print("[ERROR] FunASR 沒有回傳結果", file=sys.stderr)
        return 1
    item = res[0]
    full_text = (item.get("text") or "").strip()

    # 1) 純文字輸出
    if not args.no_txt:
        txt_path = base.with_suffix(".txt")
        txt_path.write_text(full_text + "\n", encoding="utf-8")
        print(f"[OK] 純文字：{txt_path}")

    # 2) SRT 字幕
    if not args.no_srt:
        max_cue_ms = args.max_cue_seconds * 1000.0
        sentence_info = item.get("sentence_info")
        if sentence_info:
            cues = build_cues_from_sentence_info(sentence_info, max_cue_ms, args.max_line_chars)
            print(f"[INFO] 使用 sentence_info 切句：{len(cues)} 條字幕")
        elif item.get("timestamp"):
            cues = build_cues_from_char_timestamps(
                full_text, item["timestamp"], max_cue_ms, args.max_line_chars,
            )
            print(f"[INFO] 使用逐字 timestamp + 標點切句：{len(cues)} 條字幕")
        else:
            print("[WARN] 無 timestamp，無法產生 SRT；只輸出 .txt", file=sys.stderr)
            cues = []
        if cues:
            srt_path = base.with_suffix(".srt")
            write_srt(srt_path, cues)
            print(f"[OK] 字幕：{srt_path}")

    preview = full_text.replace("\n", " ")
    if len(preview) > 200:
        preview = preview[:200] + "…"
    print("[預覽]", preview)
    return 0


if __name__ == "__main__":
    sys.exit(main())
