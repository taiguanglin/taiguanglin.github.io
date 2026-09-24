#!/usr/bin/env python3
"""FunASR 逐字 timestamp：對指定音檔窗口印每個非標點字的毫秒起訖 ＋ 關鍵詞 onset。

用於 combined cue（過渡語＋人名擠在同一 cue）內定位「段落第一個詞」的實際開口時刻
——SRT cue 只有 sentence 級粒度，字級 onset 要從 model.generate() 的
item['timestamp'] 取。

用法:
  funasr_char_onset.py "<opus 絕對路徑>" <t0> <t1> "<關鍵詞>" [<關鍵詞2>...]

輸出:
  text / 每字一行: idx  start_ms  end_ms  char
  KEY '<kw>' -> char#N abs=<t0 + start_ms/1000:.3f>s   （絕對時間＝段 start 錨點）

注意: FunASR 模型載入約 40s（CPU）；多個窗口請合併成一支批次腳本跑（模型只載入一次）。
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PUNCT = set('。！？!?，、；,;: ')


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    opus = sys.argv[1]
    t0, t1 = float(sys.argv[2]), float(sys.argv[3])
    keys = sys.argv[4:]
    if not Path(opus).exists():
        print(f'[ERROR] 找不到音檔: {opus}')
        return 2

    tmp = tempfile.mktemp(suffix='.opus')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error',
                    '-ss', str(t0), '-t', str(t1 - t0), '-i', opus, tmp], check=True)

    from funasr import AutoModel
    model = AutoModel(
        model='paraformer-zh', vad_model='fsmn-vad',
        vad_kwargs={'max_single_segment_time': 30000},
        device='cpu', disable_update=True,
        punc_model='iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch',
    )
    res = model.generate(input=tmp, cache={}, batch_size_s=60, sentence_timestamp=True)
    item = res[0]
    text = (item.get('text') or '').strip()
    ts = item.get('timestamp') or []
    print(f'text: {text}')
    print(f'timestamps: {len(ts)}')

    chars = []
    ti = 0
    for ch in text:
        if ch.isspace() or ch in PUNCT:
            continue
        if ti < len(ts):
            chars.append((ti, ts[ti][0], ts[ti][1], ch))
            ti += 1
        else:
            chars.append((ti, None, None, ch))
    for i, s, e, ch in chars:
        print(f'{i:>4} {s if s is not None else -1:>9} {e if e is not None else -1:>9} {ch}')

    flat = ''.join(c[3] for c in chars)
    for k in keys:
        kk = ''.join(ch for ch in k if ch not in PUNCT and not ch.isspace())
        p = flat.find(kk)
        if p >= 0 and chars[p][1] is not None:
            print(f'KEY {k!r} -> char#{p} abs={t0 + chars[p][1] / 1000:.3f}s')
        else:
            print(f'KEY {k!r} -> NOT FOUND (flat={flat[:40]})')

    os.unlink(tmp)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
