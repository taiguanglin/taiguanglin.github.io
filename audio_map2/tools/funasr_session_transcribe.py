#!/usr/bin/env python3
"""全場 FunASR 字級轉寫：整支 session 音檔一次轉完，輸出 char-level timestamp JSON cache。

（funasr_char_onset.py 的批次版——模型只載入一次；全場絕對時間戳，免 ffmpeg 截窗）

用法:
  funasr_session_transcribe.py <month_json> <session_id> <out_cache>

輸出 cache JSON:
  { session_id, opus, text, timestamp: [[start_ms, end_ms], ...]  # 每個非標點字一筆，絕對時間
  }
"""
import json
import sys
from pathlib import Path

month_json, sess_id, out_cache = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(month_json))
sess = [x for x in data['sessions'] if x['session_id'] == sess_id]
if not sess:
    print(f'[ERROR] 找不到 session: {sess_id}')
    raise SystemExit(2)
sess = sess[0]
opus = sess['media_parts'][0]['opus_path']
if not Path(opus).exists():
    print(f'[ERROR] 找不到音檔: {opus}')
    raise SystemExit(2)

from funasr import AutoModel
model = AutoModel(
    model='paraformer-zh', vad_model='fsmn-vad',
    vad_kwargs={'max_single_segment_time': 30000},
    device='cpu', disable_update=True,
    punc_model='iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch',
)
res = model.generate(input=opus, cache={}, batch_size_s=60, sentence_timestamp=True)
item = res[0]
out = {
    'session_id': sess_id,
    'opus': opus,
    'text': item.get('text') or '',
    'timestamp': item.get('timestamp') or [],
}
Path(out_cache).write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
print(f'saved {out_cache} text_len={len(out["text"])} chars={len(out["timestamp"])}')
