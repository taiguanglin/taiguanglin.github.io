#!/usr/bin/env python3
"""錨點批量複驗：opus＋mp3 雙解碼器 FunASR 字級 onset，逐個邊界比對 JSON 的 start。

為什麼不能用 `first_char_audit.py` 收尾：它只驗「第一詞所在 cue 是否與 start 重疊」，
**不驗 start 落在哪個 cue**——實務上最常見的錯就是 `start` 落在「下一個問題 + 人名」
合併 cue 的**起點**，等於把過渡語算進本段、把人名 onset 留在前 0.3–0.7s 之外。
這個腳本直接印「start 前後的字級時間軸」，讓人眼判讀第一個詞真正的開口時刻。

用法（需要 funasr 環境；見 SKILL.md §3）:
    cd tool/sense_voice && .venv/bin/python \\
        ../../../audio_map2/tools/funasr_anchor_verify.py \\
        --month 2025-01 --date 2025-01-18 [--session <sid>] [--before 4] [--after 8]

輸出每個邊界：
    <label> start=<s> fw=<第一詞>
      cue[..] a-b  <原文>            （含 start 的 cue 標 <<START）
      [opus] t:字 t:字 …             （絕對時間，含 start 前後）
      [mp3 ] t:字 t:字 …
    結尾印 Δ 表：每個邊界 start 之後第一個字相對 start 的偏移（兩個解碼器）

Δ < 0 代表 start 晚於首字 onset（LATE，會截掉首字，必修）；
Δ 太大（> 0.3s）且 start 前一個字是「下一個問題」之類過渡語 → 過渡語歸屬錯（應交給上一段）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2/tools'))
from first_char_audit import parse_srt_raw, first_word  # noqa: E402

PUNCT = set('。！？!?，、；,;:…—～ ')
# 過渡語：出現這些字開頭時，人名／題幹 onset 才是本段起點
TRANSITION = ('下一个问题', '下个问题', '第二个问题', '第三个问题', '第一个问题',
              '还有下一个问题', '那下一个问题', '下一个')


def get_chars(model, path, t0, t1):
    ext = '.opus' if path.endswith('.opus') else '.mp3'
    tmp = tempfile.mktemp(suffix=ext)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(t0),
                    '-t', str(t1 - t0), '-i', path, tmp], check=True)
    try:
        res = model.generate(input=tmp, cache={}, batch_size_s=60, sentence_timestamp=True)
        item = res[0]
        text = (item.get('text') or '').strip()
        ts = item.get('timestamp') or []
        out, ti = [], 0
        for ch in text:
            if ch.isspace() or ch in PUNCT:
                continue
            if ti < len(ts):
                out.append((round(t0 + ts[ti][0] / 1000.0, 2), ch))
                ti += 1
        return text, out
    finally:
        os.unlink(tmp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--session', default='')
    ap.add_argument('--source', default='')
    ap.add_argument('--before', type=float, default=4.0)
    ap.add_argument('--after', type=float, default=8.0)
    ap.add_argument('--only', default='', help='只印這些 label（#3,closing…）')
    args = ap.parse_args()

    data = json.load(open(REPO / 'audio_map2' / f'{args.month}.json'))
    sess = [s for s in data['sessions']
            if s.get('date') == args.date
            and (not args.session or s['session_id'] == args.session)
            and (not args.source or s.get('source') == args.source)]
    if not sess:
        print(f'[ERROR] 找不到 session: {args.date}')
        return 2

    from funasr import AutoModel
    model = AutoModel(
        model='paraformer-zh', vad_model='fsmn-vad',
        vad_kwargs={'max_single_segment_time': 30000},
        device='cpu', disable_update=True,
        punc_model='iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch',
    )

    only = {x.strip() for x in args.only.split(',') if x.strip()}
    for s in sess:
        part = s['media_parts'][0]
        cues = parse_srt_raw(part['srt_file'])
        paths = [('opus', part['opus_path']), ('mp3', part.get('mp3_path'))]
        print(f"\n{'#' * 100}\n### {s['session_id']}  cues={len(cues)}  dur={cues[-1][1]:.2f}")
        bounds = [('opening', s['opening'], s['opening'].get('text') or '')]
        for g in s['segments']:
            bounds.append((f"#{g['index']}", g, g.get('answer_text') or ''))
        bounds.append(('closing', s['closing'], s['closing'].get('text') or ''))

        deltas = []
        for label, g, atxt in bounds:
            if only and label not in only and label.lstrip('#') not in only:
                continue
            st = g.get('start')
            if st is None:
                print(f"\n--- {label}: start=None（佔位段，{g.get('index')}）")
                continue
            fw = first_word(atxt)
            head = atxt[:34].replace('\n', ' ')
            print(f"\n--- {label} start={st:.3f} fw={fw!r}  A[:34]={head!r}")
            for i, (cs, ce, x) in enumerate(cues):
                if ce < st - 1.2 or cs > st + 1.2:
                    continue
                print(f"    cue[{i:>4}] {cs:9.2f}-{ce:9.2f} {'<<START' if cs <= st <= ce else '      '} {x[:40]}")
            first_char = {}
            for tag, p in paths:
                if not p:
                    continue
                try:
                    text, chars = get_chars(model, p, st - args.before, st + args.after)
                except Exception as e:                      # noqa: BLE001
                    print(f"    [{tag}] ERROR {e}")
                    continue
                sel = [(t, c) for t, c in chars if st - 2.0 <= t <= st + 3.5]
                print(f"    [{tag}] {' '.join(f'{t:.2f}:{c}' for t, c in sel)}")
                nxt = next(((t, c) for t, c in chars if t >= st - 0.005), None)
                if nxt:
                    first_char[tag] = (nxt, round(nxt[0] - st, 2))
            do = first_char.get('opus', (None, None))[1]
            dm = first_char.get('mp3', (None, None))[1]
            ch = {tag: v[0][1] for tag, v in first_char.items()}
            deltas.append((label, st, fw, do, dm, ch.get('opus'), ch.get('mp3')))

        print(f"\n===== {s['session_id']} Δ 表（start 之後第一個字 − start）=====")
        print(f"{'label':<10}{'start':>10}{'Δopus':>8}{'Δmp3':>8}   首字opus/mp3   first_word")
        for label, st, fw, do, dm, co, cm in deltas:
            warn = ''
            if do is not None and do > 0.15:
                warn = '  ← LATE'
            elif do is not None and do > 0.30:
                warn = '  ← 疑似過渡語歸屬錯（人名 onset 在 start 之後）'
            print(f"{label:<10}{st:>10.3f}{str(do):>8}{str(dm):>8}   "
                  f"{str(co):>6}/{str(cm):<6}   {fw}{warn}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())