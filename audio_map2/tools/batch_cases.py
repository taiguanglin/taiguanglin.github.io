#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批次處理 worklist 的 1:1 STRUCT 案例。

對每個案例：
  1. 用 difflib 找出 block 與段之間多／少的字，給出**確切切點**（原始字串 index）
  2. 用 SRT 全文搜尋被搬動的那段文字 → 判斷 **SPOKEN（要重量音檔邊界）** 還是
     **SILENT（純文字搬位，時間不動）**
  3. 輸出可直接套用的修補描述

用法: batch_cases.py [--json out.json] [--minbig 6] [--only SPOKEN|SILENT]
"""
import argparse
import difflib
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tool' / 'word_audio_map2'))
sys.path.insert(0, str(REPO / 'tool' / 'pdf_audio_map'))
spec = importlib.util.spec_from_file_location(
    'sms', REPO / 'tool/word_audio_map2/split_missing_subquestions.py')
sms = importlib.util.module_from_spec(spec)
sys.modules['sms'] = sms
spec.loader.exec_module(sms)
from common import parse_srt_raw  # noqa: E402
from opencc import OpenCC  # noqa: E402
_CC = OpenCC('t2s')


def kept_idx(s):
    chars, idx = [], []
    for i, ch in enumerate(s or ''):
        if sms.KEPT.match(ch):
            chars.append(ch)
            idx.append(i)
    conv = _CC.convert(''.join(chars))
    if len(conv) != len(chars):
        conv = ''.join(chars)
    return conv.replace('著', '着'), idx


def srt_text(sess):
    off, parts = 0.0, []
    for p in sess['media_parts']:
        for _a, _b, t in parse_srt_raw(Path(p['srt_file'])):
            parts.append(re.sub(r'[^\w]', '', t))
        off += float(p.get('duration_est') or 0)
    return ''.join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--minbig', type=int, default=6)
    ap.add_argument('--json')
    ap.add_argument('--only', choices=['SPOKEN', 'SILENT'])
    ap.add_argument('--default', help='把結果寫到這個 JSON（預設 audio_map2/tools/reseg_worklist.json）')
    args = ap.parse_args()
    blocks = sms.load_blocks()
    ctx = sms.build_ctx(blocks)
    months = sorted(p.stem for p in sms.AUDIO_MAP2_DIR.glob('????-??.json'))
    out = []
    for m in months:
        data = json.loads((REPO / f'audio_map2/{m}.json').read_text(encoding='utf-8'))
        for sess in data['sessions']:
            segs = sess['segments']
            seginfo = [sms.segment_claims(seg, ctx) for seg in segs]
            owner, order, seen = {}, [], set()
            for j, (all_g, _c, _s, _a, _d) in enumerate(seginfo):
                for g in all_g:
                    for bi in g.blocks:
                        owner.setdefault(blocks[bi].qid, j)
                        if bi not in seen:
                            seen.add(bi)
                            order.append(bi)
            if not order:
                continue
            S = [kept_idx((g.get('q_text') or '') + (g.get('answer_text') or ''))[0]
                 for g in segs]
            B = [kept_idx(blocks[bi].q_text + blocks[bi].a_text)[0] for bi in order]
            SRT = srt_text(sess)
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                    None, B, S, autojunk=False).get_opcodes():
                if tag != 'replace' or (i2 - i1) != 1 or (j2 - j1) != 1:
                    continue
                b, s = blocks[order[i1]], segs[j1]
                dq = len(kept_idx(s.get('q_text'))[0]) - len(kept_idx(b.q_text)[0])
                da = len(kept_idx(s.get('answer_text'))[0]) - len(kept_idx(b.a_text)[0])
                if max(abs(dq), abs(da)) < args.minbig:
                    continue
                moves = []
                for field, bt, st in (('q', b.q_text, s.get('q_text') or ''),
                                      ('a', b.a_text, s.get('answer_text') or '')):
                    kb, _ = kept_idx(bt)
                    ks, isx = kept_idx(st)
                    for t2, a1, a2, b1, b2 in difflib.SequenceMatcher(
                            None, kb, ks, autojunk=False).get_opcodes():
                        if t2 == 'equal':
                            continue          # equal 只是用字差異，不是搬位
                        n_blk, n_seg = a2 - a1, b2 - b1
                        if max(n_blk, n_seg) < args.minbig:
                            continue
                        probe = (kb[a1:a2] if n_blk >= n_seg else ks[b1:b2])[:14]
                        spoken = bool(probe) and probe in SRT
                        cut = isx[b1] if b1 < len(isx) else len(st)
                        moves.append(dict(field=field, op=t2, n_blk=n_blk, n_seg=n_seg,
                                          probe=probe, spoken=spoken, cut=cut,
                                          blk_text=kb[a1:a2][:60], seg_text=ks[b1:b2][:60]))
                if not moves:
                    continue
                ent = dict(month=m, sid=sess['session_id'], segkey=s.get('stable_key'),
                           index=j1 + 1, start=s.get('start'), end=s.get('end'),
                           lp=bool((s.get('meta') or {}).get('lastPlayed')),
                           block=b.qid, ch=b.chapter, aid=b.aid, dq=dq, da=da, moves=moves)
                ent['verdict'] = 'SPOKEN' if any(x['spoken'] for x in moves) else 'SILENT'
                out.append(ent)
    n_sp = sum(1 for e in out if e['verdict'] == 'SPOKEN')
    print(f'cases={len(out)}  SPOKEN(要重量音檔)={n_sp}  SILENT(純文字搬位)={len(out)-n_sp}')
    import collections
    print('SILENT by month:', dict(sorted(collections.Counter(
        e['month'] for e in out if e['verdict'] == 'SILENT').items())))
    print()
    for e in out:
        if args.only and e['verdict'] != args.only:
            continue
        mv = '; '.join(f"{x['field']}:{x['op']} blk{x['n_blk']}/seg{x['n_seg']} "
                       f"cut={x['cut']} {'SPOKEN' if x['spoken'] else 'SILENT'} "
                       f"{x['seg_text'][:24] or x['blk_text'][:24]}" for x in e['moves'])
        print(f"{e['verdict']:<6} {e['month']} {e['segkey']} "
              f"[{e['start']}→{e['end']}] ch{e['ch']} dq={e['dq']} da={e['da']} lp={e['lp']}")
        print(f"        {mv}")
    dest = args.json or str(REPO / 'audio_map2/tools/reseg_worklist.json')
    Path(dest).write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')
    print(f'\nJSON → {dest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
