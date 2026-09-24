#!/usr/bin/env python3
"""逐段判讀 dump：印指定段的 FunASR 字級時間軸 + SRT cue 窗口（判讀用，不改檔）。

用法:
  funasr_dump.py <month> <session_id> <index> [<index>...] [--before 12] [--after 30]

每段印：
  - 段 start/end / 第一詞 / answer_text 頭 40 字
  - FunASR 字級：[start-before, start+after] 內每字 (t, char)，橫向 compact
  - SRT cue：重疊同窗口的 cue（含毫秒）
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2/tools'))
from first_char_audit import parse_srt_raw, first_word, variants, _norm  # noqa: E402
from funasr_verify import load_chars  # noqa: E402


def main():
    args = []
    before, after = 12.0, 30.0
    it = iter(sys.argv[1:])
    for a in it:
        if a == '--before':
            before = float(next(it))
        elif a == '--after':
            after = float(next(it))
        else:
            args.append(a)
    month, sid = args[0], args[1]
    idxs = [int(x) for x in args[2:]]

    d = json.load(open(REPO / 'audio_map2' / f'{month}.json'))
    sess = [x for x in d['sessions'] if x['session_id'] == sid][0]
    cache = Path(f'/tmp/funasr_cache/{sid}.json')
    chars = load_chars(cache) if cache.exists() else []
    cues = parse_srt_raw(sess['media_parts'][0]['srt_file'])

    for idx in idxs:
        g = [x for x in sess['segments'] if x['index'] == idx]
        if not g:
            print(f'#{idx}: NOT FOUND')
            continue
        g = g[0]
        st, en = g['start'], g.get('end')
        txt = g['answer_text'] or g.get('q_text') or ''
        fw = first_word(txt)
        print(f"===== #{idx} start={st} end={en} fw={fw!r} var={variants(fw)[:6]}")
        print(f"  answer[:60]: {txt[:60]!r}")
        print(f"  q_text[:40]: {(g.get('q_text') or '')[:40]!r}")
        if st is None:
            print('  (null 段)')
            continue
        # FunASR 字級軸
        win = [(s, ch) for s, e, ch in chars if s is not None and st - before <= s <= st + after]
        s_line, last_t = [], None
        for s, ch in win:
            s_line.append(f'{s:.2f}:{ch}')
        print(f"  FunASR: {' '.join(s_line) if s_line else '(無)'}")
        # SRT cue
        for i, (s, e, x) in enumerate(cues):
            if e < st - before or s > st + after:
                continue
            mark = ' <<<' if s <= st <= e else ''
            print(f"  cue[{i}]{s:.3f}-{e:.3f}:{x[:44]}{mark}")
        print()


if __name__ == '__main__':
    main()
