#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在**任意**時刻量一次 opus+mp3 雙解碼器字級 onset（整段錯位修正用）。

`batch_anchor.py` 的 ±9s 搜尋窗抓不到「整段錯位 20–60s」的情況（2025-01-17 `wechat #3`
教訓），所以先由 `content_check.py`／`cross_check.py` 用整場轉錄指出錯位時刻，再用本工具
在正確時刻附近取雙解碼器字級 onset 當錨點。

用法:
    cd tool/sense_voice && .venv/bin/python ../../audio_map2/tools/onset_at.py \\
        --month 2024-12 --session 2024-12-09-wechat --at 2690.1 --span 3 5
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PUNCT = set('。！？!?，、；,;:…—～ ')


def decode(path, t0, dur):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t0:.3f}', '-t', f'{dur:.3f}',
                        '-i', path, '-f', 'wav', '-ar', '16000', '-ac', '1', '-'],
                       capture_output=True, check=True)
    return r.stdout or None


def chars_of(model, raw, t_base):
    res = model.generate(input=raw, cache={}, batch_size_s=60, sentence_timestamp=True)
    item = res[0]
    text, ts, out, ti = (item.get('text') or '').strip(), item.get('timestamp') or [], [], 0
    for ch in text:
        if ch.isspace() or ch in PUNCT:
            continue
        if ti < len(ts):
            out.append((round(t_base + ts[ti][0] / 1000.0, 2), ch))
            ti += 1
    return text, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--session', required=True)
    ap.add_argument('--at', type=float, required=True)
    ap.add_argument('--span', type=float, nargs=2, default=(3.0, 5.0))
    args = ap.parse_args()

    d = json.load(open(REPO / 'audio_map2' / f'{args.month}.json', encoding='utf-8'))
    s = [x for x in d['sessions'] if x['session_id'] == args.session][0]
    off = 0.0
    part = s['media_parts'][0]
    for p in s['media_parts']:
        if args.at < off + float(p.get('duration_est') or 0.0):
            part = p
            break
        off += float(p.get('duration_est') or 0.0)
    print(f'# {args.session} @ {args.at}  part={part["stem"]} (offset {off})')

    from funasr import AutoModel
    model = AutoModel(model='paraformer-zh', vad_model='fsmn-vad',
                      vad_kwargs={'max_single_segment_time': 30000}, device='cpu',
                      disable_update=True,
                      punc_model='iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch')
    for tag, key in (('opus', 'opus_path'), ('mp3', 'mp3_path')):
        p = part.get(key)
        if not p or not os.path.exists(p):
            print(f'[{tag}] 缺檔 {p}')
            continue
        t0 = max(0.0, args.at - off - args.span[0])
        dur = max(args.span[0] + args.span[1], (args.at - off + args.span[1]) - t0)
        raw = decode(p, t0, dur)
        if raw is None:
            print(f'[{tag}] ffmpeg 失敗')
            continue
        text, cs = chars_of(model, raw, off + t0)
        sel = [(t, c) for t, c in cs
               if args.at - args.span[0] <= t <= args.at + args.span[1]]
        print(f'[{tag}] {" ".join(f"{t:.2f}:{c}" for t, c in sel)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
