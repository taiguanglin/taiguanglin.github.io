#!/usr/bin/env python3
"""FunASR 字流＋SRT cue 雙欄窗口檢視（讀 cache，不載模型）。

Usage:
  funasr_ctx.py <month> <session_id> <t0> <t1> [srt_only]

上欄：FunASR char@onset（字級，絕對時間）；下欄：SRT cue（原始）。
供逐段判讀「第一詞實際開口時刻」。
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2/tools'))
from first_char_audit import parse_srt_raw  # noqa: E402

PUNCT = set('。！？!?，、；,;: ')


def load_chars(cache_path):
    c = json.load(open(cache_path))
    text, ts = c['text'], c['timestamp']

    def is_cjk(ch):
        return '\u4e00' <= ch <= '\u9fff'

    chars = []
    ti = 0
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace() or ch in PUNCT:
            i += 1
            continue
        if is_cjk(ch):
            unit = ch
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in PUNCT \
                    and not is_cjk(text[j]):
                j += 1
            unit = text[i:j]
            i = j
        if ti < len(ts):
            chars.append((ts[ti][0] / 1000.0, ts[ti][1] / 1000.0, unit))
            ti += 1
        else:
            chars.append((None, None, unit))
    return chars


def main():
    month, sid, t0, t1 = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    srt_only = len(sys.argv) > 5 and sys.argv[5] == 'srt_only'
    d = json.load(open(REPO / 'audio_map2' / f'{month}.json'))
    sess = [x for x in d['sessions'] if x['session_id'] == sid][0]
    if not srt_only:
        chars = load_chars(Path(f'/tmp/funasr_cache/{sid}.json'))
        # 依 FunASR 原始斷句（timestamp gap > 1.2s 或標點）分組成行
        lines, cur = [], []
        prev_e = None
        for s, e, ch in chars:
            if s is None:
                continue
            if prev_e is not None and s - prev_e > 1.2 and cur:
                lines.append(cur)
                cur = []
            cur.append(f'{ch}@{s:.2f}')
            prev_e = e
        if cur:
            lines.append(cur)
        for ln in lines:
            # 行時間範圍
            m_ts = [float(x.split('@')[1]) for x in ln]
            if m_ts[-1] < t0 - 2 or m_ts[0] > t1:
                continue
            print('  F ' + ' '.join(ln))
    print('  --- SRT ---')
    cues = parse_srt_raw(sess['media_parts'][0]['srt_file'])
    for s, e, t in cues:
        if s < t1 and e > t0:
            print(f'  S {s:8.2f} {e:8.2f}  {t}')


if __name__ == '__main__':
    raise SystemExit(main())
