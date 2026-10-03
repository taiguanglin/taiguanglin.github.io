#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `propose_fixes.py` 的候選錨點套回月份 JSON，並由 `start` 鏈反推所有 `end`。

**只動** `start / end / start_label / end_label / notes`（＋分段收尾時才動
`confidence / status`）。文字欄位（`q_text / answer_text / questioner / question_time /
opening.text / closing.text / index / stable_key / question_id / chapter_*`）一字不動——
收尾用 `--verify-text` 對照備份逐值驗證。

錨點來源優先序：
  1. `--overrides <json>`（人工判讀結果，鍵 `"<session_id>|<label>"`）
  2. `fixes.json` 中 `weak == false` 的候選
  3. 其餘維持原值

用法:
    .venv/bin/python apply_alignment.py --month 2024-12 --inplace \\
        [--overrides /tmp/am2_2024-12/overrides.json] [--verify-text /tmp/2024-12.backup.json]
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEXT_KEYS_SEG = ('q_text', 'answer_text', 'questioner', 'question_time', 'index',
                 'stable_key', 'question_id', 'question_id', 'chapter_question_ids',
                 'chapter_indexes', 'chapter_answer_ids', 'q_preview', 'answer_preview')
TEXT_KEYS_BLK = ('text', 'text_preview')


def hhmmss(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--overrides', default='')
    ap.add_argument('--inplace', action='store_true')
    ap.add_argument('--verify-text', default='')
    ap.add_argument('--only-overrides', action='store_true',
                    help='只套 --overrides，其餘邊界維持 JSON 現值'
                         '（第二輪收斂用：重新量測後只補新發現的錯）')
    ap.add_argument('--allow-weak', action='store_true',
                    help='連 weak 候選也套用（除錯用，正式收尾不要開）')
    args = ap.parse_args()

    p = REPO / 'audio_map2' / f'{args.month}.json'
    d = json.load(open(p, encoding='utf-8'))
    before = json.load(open(args.verify_text, encoding='utf-8')) if args.verify_text else None

    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    fixes = {}
    fx_path = cdir / 'fixes.json'
    if fx_path.exists():
        for f in json.load(open(fx_path, encoding='utf-8')):
            if f.get('new_start') is None:
                continue
            if f.get('weak') and not args.allow_weak:
                continue
            fixes[(f['session_id'], f['label'])] = f
    ov = {}
    if args.overrides:
        ov = json.load(open(args.overrides, encoding='utf-8'))

    changed = kept = 0
    report = []
    for s in d['sessions']:
        sid = s['session_id']
        blocks = [('opening', s['opening'])]
        blocks += [(f"#{g['index']}", g) for g in s['segments']]
        blocks.append(('closing', s['closing']))

        # 1) 決定每個「佔時間」的邊界新 start
        news, skipped = {}, []
        for label, g in blocks:
            key = f'{sid}|{label}'
            if g.get('start') is None:                 # null 佔位段不佔音檔時間
                skipped.append(label)
                continue
            if key in ov:
                news[label] = float(ov[key])
            elif (sid, label) in fixes and not args.only_overrides:
                news[label] = float(fixes[(sid, label)]['new_start'])
            else:
                news[label] = float(g['start'])

        # 2) 單調性檢查：start 必須嚴格遞增（含 opening／closing）
        seq = [('opening', news['opening'])] + \
              [(l, news[l]) for l, _g in blocks[1:-1] if l not in skipped] + \
              [('closing', news['closing'])]
        bad = [(seq[i][0], seq[i][1], seq[i + 1][0], seq[i + 1][1])
               for i in range(len(seq) - 1) if seq[i + 1][1] <= seq[i][1]]
        if bad:
            report.append(f'  ✗ {sid}: 新 start 非嚴格遞增，需人工處理 → '
                          + '; '.join(f'{a}={b:.2f} ≥ {c}={e:.2f}' for a, b, c, e in bad))
            continue

        # 3) 套用 + 由 start 鏈反推 end
        for label, g in blocks:
            if g.get('start') is None:
                g['start_label'] = g.get('start_label') or ''
                g['end_label'] = g.get('end_label') or ''
                continue
            ns = news[label]
            if abs(ns - g['start']) >= 0.0005:
                g['start'] = round(ns, 3)
                changed += 1
                f = fixes.get((sid, label))
                ev = ''
                if f'{sid}|{label}' in ov:
                    ev = 'manual'
                elif f:
                    on = f.get('onsets') or {}
                    ev = 'opus/mp3 ' + '/'.join(f'{v:.2f}' for v in on.values()) \
                        if on else f"sc={f.get('score')}"
                    if f.get('basis', '').startswith('prefix'):
                        ev += f" {f['basis']}"
                if ev:
                    note = f'anchor:字級 {ev}'
                    n = g.get('notes') or ''
                    if note not in n:
                        g['notes'] = (n + ' | ' + note) if n else note
            else:
                kept += 1
            g['start_label'] = hhmmss(g['start'])

        # end 鏈：end[i] := start[i+1]（null 段跳過）；末段 := closing.start
        real = [(l, g) for l, g in blocks[1:-1] if l not in skipped]
        for i, (label, g) in enumerate(real):
            nxt_end = news[real[i + 1][0]] if i + 1 < len(real) else news['closing']
            g['end'] = round(nxt_end, 3)
            g['end_label'] = hhmmss(g['end'])
        s['opening']['end'] = round(news[real[0][0]], 3)
        s['opening']['end_label'] = hhmmss(s['opening']['end'])
        report.append(f'  ✓ {sid}: 邊界 {len(seq)} 個（跳過 null {len(skipped)} 段）')

    # 文字欄位 0 違改驗證。**用 `question_id` 配對、不用 index**：依音訊序重排
    # （`swap_order.py`）會讓兩段對調 `index`，那是 SKILL §1 允許的「segments[] 順序」
    # 變更，按 index 比對會把重排誤報成「文字被改」。
    if before:
        REORDER_OK = ('index', 'stable_key')   # 只有這兩個欄位會因重排而換位
        vb = {}
        for s in before['sessions']:
            sid = s['session_id']
            vb[(sid, 'opening')] = s['opening']
            vb[(sid, 'closing')] = s['closing']
            for g in s['segments']:
                vb[(sid, g.get('question_id') or f"#{g['index']}")] = g
        viol = 0
        for s in d['sessions']:
            sid = s['session_id']
            for label in ('opening', 'closing'):
                g = s[label]
                o = vb.get((sid, label))
                if o is None:
                    continue
                for k in TEXT_KEYS_BLK:
                    if k in o and o[k] != g.get(k):
                        viol += 1
                        print(f'  ✗✗ 文字欄位被改動 {sid} {label}.{k}')
            for g in s['segments']:
                o = vb.get((sid, g.get('question_id') or f"#{g['index']}"))
                if o is None:
                    print(f'  ✗✗ 備份找不到對應段 {sid} '
                          f'#{g["index"]}（question_id={g.get("question_id")}）')
                    viol += 1
                    continue
                for k in TEXT_KEYS_SEG:
                    if k in REORDER_OK and 'reordered:' in (g.get('notes') or ''):
                        continue      # 重排段的 index/stable_key 本來就會換位
                    if k in o and o[k] != g.get(k):
                        viol += 1
                        print(f'  ✗✗ 文字欄位被改動 {sid} #{g["index"]}.{k}')
        print(f'文字欄位違改：{viol}')

    out = p if args.inplace else Path(str(p) + '.aligned')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    print('\n'.join(report))
    print(f'\n改動 {changed} 個 start；未動 {kept} 個。→ {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
