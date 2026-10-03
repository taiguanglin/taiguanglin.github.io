#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整場 FunASR 字級轉寫（多段分檔自動接軌），供「內容定位檢查」使用。

用途（SKILL §5.5）：把每段 `answer_text` 的內文模糊定位回音檔，確認它真的落在自己的
`[start, end]` 內——這是唯一能抓到「整段錯位」的方法（2025-01-17 `wechat #3` 錯 56s）。

⚠️ **整場轉錄只能用來驗內容位置，不能取絕對時間**：實測中段會漂 2–3s（VAD 視窗漂移）。
   絕對時間只信 `batch_anchor.py` 的 10–25s 短窗 ＋ 雙解碼器。
   （檔頭 0–5s 是例外：整場轉錄在檔頭反而比短窗可靠。）

用法（需 funasr 環境）:
    cd tool/sense_voice && .venv/bin/python ../../audio_map2/tools/full_transcribe.py --month 2024-12

輸出: <out>/full/<session_id>.json
    { session_id, duration, text, chars: [[global_sec, ch], ...] }
"""
import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

PUNCT = set('。！？!?，、；,;:…—～ ')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--date', default='')
    ap.add_argument('--out', default='')
    args = ap.parse_args()

    outdir = Path(args.out or f'/tmp/am2_{args.month}') / 'full'
    outdir.mkdir(parents=True, exist_ok=True)
    data = json.load(open(REPO / 'audio_map2' / f'{args.month}.json'))
    dates = {d for d in args.date.split(',') if d}
    sessions = [s for s in data['sessions'] if not dates or s.get('date') in dates]

    todo = [s for s in sessions
            if not (outdir / f"{s['session_id']}.json").exists()]
    print(f'[full] sessions={len(sessions)} 待跑={len(todo)}', flush=True)
    if not todo:
        return 0

    from funasr import AutoModel
    model = AutoModel(model='paraformer-zh', vad_model='fsmn-vad',
                      vad_kwargs={'max_single_segment_time': 30000},
                      device='cpu', disable_update=True,
                      punc_model='iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch')

    for s in todo:
        chars, texts, off = [], [], 0.0
        for part in s.get('media_parts') or []:
            opus = part.get('opus_path')
            if not opus or not os.path.exists(opus):
                print(f'  [WARN] {s["session_id"]} 缺音檔 {opus}', flush=True)
                off += float(part.get('duration_est') or 0.0)
                continue
            res = model.generate(input=opus, cache={}, batch_size_s=60, sentence_timestamp=True)
            item = res[0]
            text = (item.get('text') or '').strip()
            ts = item.get('timestamp') or []
            texts.append(text)
            ti = 0
            for ch in text:
                if ch.isspace() or ch in PUNCT:
                    continue
                if ti < len(ts):
                    chars.append([round(off + ts[ti][0] / 1000.0, 2), ch])
                    ti += 1
            off += float(part.get('duration_est') or 0.0)
        fn = outdir / f"{s['session_id']}.json"
        tmp = fn.with_suffix('.tmp')
        tmp.write_text(json.dumps({'session_id': s['session_id'], 'duration': round(off, 3),
                                   'text': '\n'.join(texts), 'chars': chars},
                                  ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, fn)
        print(f'  {s["session_id"]}: chars={len(chars)} dur={off:.1f}', flush=True)
    print(f'[full] done -> {outdir}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
