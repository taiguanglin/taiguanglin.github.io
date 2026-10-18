#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全庫逐案 triage：audio_map2 段 ↔ wenda2_ebook block 的所有長度不符案例。

對 length_audit 的非 EXACT/NEAR/MINOR 案（BIG/GLUE/MERGE/FREEZE/NOLINK/NOCLAIM）
逐一分析，輸出每案的：
  1. 形狀（shape）——用 kept-stream 子字串/多重集關係判定：
     - QA_TRANSFER   ：本段 answer_text 含 block 的 question_text（q/a 切分錯置，
                       可把問題文字從 answer 搬回 q；純文字搬位、窗不動）
     - ADJ_A_SWAP    ：鄰段的 answer_text 含本段 block 的 answer 缺字（答案在相鄰
                       段之間放錯邊；SILENT→純搬位，SPOKEN→搬位＋可能重錨）
     - ADJ_Q_SWAP    ：同上但發生在 q_text
     - SEG_EXTRA     ：段比 block 多的內容（Word 書面補充／表頭；block 側沒有）
     - BLK_EXTRA     ：block 比段多的內容（電子書黏合／表頭；JSON 動不了→僅記錄）
     - REORDER       ：段內容 = 多個 block 的答案反序黏合（要依 block 切分）
     - LINK_ISSUE    ：frozen qid 與內容對不上（要改連結）
  2. SPOKEN/SILENT：被搬動文字是否出現於該場 SRT 全文。
  3. 建議動作（move/split/merge/relink/record）。

用法:
    .venv/bin/python audio_map2/tools/full_triage.py [--json out.json] [--key 'sid#N']
"""
from __future__ import annotations

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


def kept(s: str) -> str:
    conv = _CC.convert(''.join(ch for ch in (s or '') if sms.KEPT.match(ch)))
    return conv.replace('著', '着')


def srt_text(sess) -> str:
    parts = []
    for p in sess['media_parts']:
        sp = Path(p.get('srt_file') or '')
        if not sp.exists():
            sp = REPO / 'audio' / 'srt' / f"{p.get('stem')}.srt"
        if not sp.exists():
            continue
        for _a, _b, t in parse_srt_raw(sp):
            parts.append(re.sub(r'[^\w]', '', t))
    return ''.join(parts)


def ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--json')
    ap.add_argument('--key', help='只看這些段（逗號分隔 sid#N）')
    ap.add_argument('--minbig', type=int, default=6)
    args = ap.parse_args()

    blocks = sms.load_blocks()
    ctx = sms.build_ctx(blocks)
    bmap = {b.qid: b for b in blocks}

    aud = json.loads((REPO / 'audio_map2/tools/length_audit_now.json').read_text()) \
        if False else None
    # 重新計算（不依賴外部檔）
    out = []
    srt_cache = {}
    for m in sorted(p.stem for p in (REPO / 'audio_map2').glob('????-??.json')):
        data = json.loads((REPO / f'audio_map2/{m}.json').read_text(encoding='utf-8'))
        for sess in data['sessions']:
            sid = sess['session_id']
            segs = sess['segments']
            seginfo = [sms.segment_claims(g, ctx) for g in segs]
            srt = srt_cache.get(sid)
            if srt is None:
                srt = srt_text(sess)
                srt_cache[sid] = srt
            by_idx = {g['index']: g for g in segs}
            for j, g in enumerate(segs):
                all_g, _c, _s, _a, _d = seginfo[j]
                sq, sa = kept(g.get('q_text')), kept(g.get('answer_text'))
                # 主要 block：frozen 第一個，否則 claimed 第一個
                qids = g.get('chapter_question_ids') or []
                bqids = [q for q in qids if q in bmap]
                if not bqids:
                    verdict = 'NOCLAIM'
                    out.append(dict(month=m, sid=sid, idx=g['index'], key=f"{sid}#{g['index']}",
                                    verdict=verdict, dq=len(sq), da=len(sa), shape='NO-QID',
                                    spoken=None, action='record', note='無凍結 qid'))
                    continue
                b = bmap[bqids[0]]
                BQ, BA = kept(b.q_text), kept(b.a_text)
                dq, da = len(sq) - len(BQ), len(sa) - len(BA)
                if max(abs(dq), abs(da)) < args.minbig:
                    continue
                # ---- 形狀判定 ----
                shape, action, note, spoken = None, None, '', None

                def probe_spoken(t: str):
                    t = t.strip()
                    return bool(t) and re.sub(r'[^\w]', '', t) in srt if t else False

                # 1) QA_TRANSFER：block 的問題文字出現在段的 answer_text 開頭附近
                if dq < 0 and da > 0 and abs(dq + da) <= max(6, abs(dq) // 5):
                    # block q 的「缺字」是否為 seg a 的「多字」
                    sm = difflib.SequenceMatcher(None, BQ, sq, autojunk=False)
                    qmiss = ''.join(BQ[a1:a2] for t, a1, a2, _b1, _b2 in sm.get_opcodes() if t != 'equal')
                    if qmiss and (qmiss in sa or ratio(qmiss, sa[:len(qmiss) + 10]) > 0.85):
                        shape = 'QA_TRANSFER'
                        action = 'move-q-back'
                        note = f'block q 缺字（{len(qmiss)}）在段 answer_text 內 → 搬回 q_text'
                        spoken = probe_spoken(qmiss[:40])
                # 2) ADJ_A_SWAP：鄰段 answer 含本段 block answer 的缺字
                if shape is None and da < 0 and dq == 0:
                    for nb_idx in (g['index'] - 1, g['index'] + 1):
                        nb = by_idx.get(nb_idx)
                        if not nb:
                            continue
                        nba = kept(nb.get('answer_text'))
                        sm = difflib.SequenceMatcher(None, BA, sa, autojunk=False)
                        amiss = ''.join(BA[a1:a2] for t, a1, a2, _b1, _b2 in sm.get_opcodes() if t != 'equal')
                        if amiss and len(amiss) >= args.minbig and \
                           (amiss in nba or ratio(amiss, nba[:len(amiss) + 20]) > 0.8):
                            shape = 'ADJ_A_SWAP'
                            action = f'move-a-{"to" if nb_idx > g["index"] else "from"}-#{nb_idx}'
                            note = f'block answer 缺字（{len(amiss)}）在鄰段 #{nb_idx} 的 answer_text'
                            spoken = probe_spoken(amiss[:40])
                            break
                # 3) ADJ_Q_SWAP
                if shape is None and dq < 0 and da == 0:
                    for nb_idx in (g['index'] - 1, g['index'] + 1):
                        nb = by_idx.get(nb_idx)
                        if not nb:
                            continue
                        nbq = kept(nb.get('q_text'))
                        sm = difflib.SequenceMatcher(None, BQ, sq, autojunk=False)
                        qmiss = ''.join(BQ[a1:a2] for t, a1, a2, _b1, _b2 in sm.get_opcodes() if t != 'equal')
                        if qmiss and len(qmiss) >= args.minbig and \
                           (qmiss in nbq or ratio(qmiss, nbq[:len(qmiss) + 20]) > 0.8):
                            shape = 'ADJ_Q_SWAP'
                            action = f'move-q-{"to" if nb_idx > g["index"] else "from"}-#{nb_idx}'
                            note = f'block q 缺字（{len(qmiss)}）在鄰段 #{nb_idx} 的 q_text'
                            spoken = probe_spoken(qmiss[:40])
                            break
                # 4) SEG_EXTRA：段的 q 或 a 多出 block 沒有的內容
                if shape is None:
                    sm = difflib.SequenceMatcher(None, BQ + BA, sq + sa, autojunk=False)
                    extra = ''.join((sq + sa)[b1:b2] for t, a1, a2, b1, b2 in sm.get_opcodes() if t == 'insert')
                    miss = ''.join((BQ + BA)[a1:a2] for t, a1, a2, b1, b2 in sm.get_opcodes() if t == 'delete')
                    if extra and not miss:
                        shape = 'SEG_EXTRA'
                        action = 'record' if len(extra) >= 30 else 'ignore'
                        note = f'段多出 {len(extra)} 字（Word 表頭／書面補充）『{extra[:20]}』'
                        spoken = probe_spoken(extra[:40])
                    elif miss and not extra:
                        shape = 'BLK_EXTRA'
                        action = 'record'
                        note = f'block 多出 {len(miss)} 字（電子書黏合／表頭）『{miss[:20]}』'
                        spoken = probe_spoken(miss[:40])
                    else:
                        shape = 'MIXED'
                        action = 'manual'
                        note = f'q差{dq:+d} a差{da:+d}；多出{len(extra)} 缺{len(miss)}'
                        spoken = probe_spoken((extra or miss)[:40])
                out.append(dict(month=m, sid=sid, idx=g['index'], key=f"{sid}#{g['index']}",
                                dq=dq, da=da, shape=shape, action=action,
                                spoken=spoken, note=note, qid=bqids[0],
                                win=[g.get('start'), g.get('end')]))
    if args.key:
        want = set(args.key.split(','))
        out = [c for c in out if c['key'] in want]
    from collections import Counter
    cnt = Counter(c['shape'] for c in out)
    print(f"cases: {len(out)}")
    for k, v in sorted(cnt.items(), key=lambda x: -x[1]):
        print(f"  {k:<14} {v}")
    if args.json:
        json.dump(out, open(args.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for c in sorted(out, key=lambda c: (c['sid'], c['idx'])):
        sp = {True: 'SPOKEN', False: 'SILENT', None: '-'}[c['spoken']]
        print(f"{c['shape']:<13} {c['key']:<26} dq={c['dq']:+5d} da={c['da']:+5d} {sp:<7} {c['action']:<18} {c['note'][:80]}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
