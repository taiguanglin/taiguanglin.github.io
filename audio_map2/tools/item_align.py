#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**決定性**逐段稽核：把 session 的每一段看成一個「問題＋回答」字串，
把該場認領到的每個 ebook block 也看成一個「問題＋回答」字串，
用 `difflib` **逐項**對齊兩串。項目完全相同才算 OK。

這比「逐段比較長度」更嚴格也不會被固定 offset 誤導：
  equal          一段 = 一 block，字字相同 → 不需動
  replace        一段 ≠ 一 block（長度不同 → 可能該拆或該併）
  delete (B 側)  一個 block 沒有對應的段 → 漏切
  insert (S 側)  一段沒有對應的 block → 多切／null 佔位

用法:
    cd tool/word_audio_map2
    .venv/bin/python ../../audio_map2/tools/item_align.py --json out.json
"""
import argparse
import difflib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path('/Users/paul/tai/taiguanglin.github.io')
sys.path.insert(0, str(REPO / 'tool/word_audio_map2'))
spec = importlib.util.spec_from_file_location(
    'sms', REPO / 'tool/word_audio_map2/split_missing_subquestions.py')
sms = importlib.util.module_from_spec(spec)
sys.modules['sms'] = sms
spec.loader.exec_module(sms)


def kept(s):
    # resplit_by_html.kept_stream 已做 OpenCC t2s；再摺疊 著/着（mark_html_diff.norm 的做法），
    # 否則同一段文字會因為 著/着 造成假的 replace。
    return sms.kept_stream(s or '')[0].replace('著', '着')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', action='append')
    ap.add_argument('--json')
    ap.add_argument('--show', action='store_true', help='印每個不一致項的內容')
    args = ap.parse_args()
    blocks = sms.load_blocks()
    ctx = sms.build_ctx(blocks)
    months = args.month or sorted(p.stem for p in sms.AUDIO_MAP2_DIR.glob('????-??.json'))
    report = []
    for m in months:
        data = json.loads((REPO / f'audio_map2/{m}.json').read_text(encoding='utf-8'))
        for sess in data['sessions']:
            segs = sess['segments']
            seginfo = [sms.segment_claims(seg, ctx) for seg in segs]
            order, seen = [], set()
            for all_g, _c, _s, _a, _d in seginfo:
                for g in all_g:
                    for bi in g.blocks:
                        if bi not in seen:
                            seen.add(bi)
                            order.append(bi)
            if not order or len(order) != len(segs):
                # block 數與段數不一致 → 一定是整段錯位，交給 item 對齊結果
                pass
            S = [kept((g.get('q_text') or '') + (g.get('answer_text') or ''))
                 for g in segs]
            B = [kept(blocks[bi].q_text + blocks[bi].a_text) for bi in order]
            sm = difflib.SequenceMatcher(None, B, S, autojunk=False)
            ops = sm.get_opcodes()
            diff = [o for o in ops if o[0] != 'equal']
            if not diff:
                continue
            ent = dict(month=m, sid=sess['session_id'], nseg=len(segs),
                       nblock=len(order), ops=[])
            for tag, i1, i2, j1, j2 in diff:
                ent['ops'].append(dict(
                    tag=tag,
                    blocks=[dict(qid=blocks[order[i]].qid, ch=blocks[order[i]].chapter,
                                 aid=blocks[order[i]].aid, kq=len(kept(blocks[order[i]].q_text)),
                                 ka=len(kept(blocks[order[i]].a_text))) for i in range(i1, i2)],
                    segs=[dict(key=segs[j].get('stable_key'), start=segs[j].get('start'),
                               end=segs[j].get('end'),
                               kq=len(kept(segs[j].get('q_text'))),
                               ka=len(kept(segs[j].get('answer_text'))),
                               lp=bool((segs[j].get('meta') or {}).get('lastPlayed')))
                          for j in range(j1, j2)]))
            report.append(ent)
            print(f"{m} {sess['session_id']}: segs={len(segs)} blocks={len(order)} "
                  f"ops={len(diff)}")
            for o in ent['ops']:
                bq = ', '.join(f"ch{b['ch']} {b['qid']} q{b['kq']}/a{b['ka']}" for b in o['blocks'])
                sq = ', '.join(f"#{s['key'].split('#')[-1]} q{s['kq']}/a{s['ka']}"
                               f"[{s['start']}]" + ('LP' if s['lp'] else '') for s in o['segs'])
                print(f"    {o['tag']:<7} blocks: {bq or '-'}")
                print(f"            segs  : {sq or '-'}")
            if args.show:
                for o in ent['ops']:
                    for i in o['blocks']:
                        print('      BLOCK', i['qid'], kept(blocks[order[0]]['q_text'])[:0] or '')
    print(f'\nsessions with mismatch: {len(report)}')
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf-8')
        print(f'JSON → {args.json}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
