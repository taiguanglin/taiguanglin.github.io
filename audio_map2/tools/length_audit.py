#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**全量**逐段稽核：audio_map2 每段 ↔ wenda2_ebook 對應 block 的「保留字元數」比較。

沿用 `split_missing_subquestions.py` 的比對引擎（`segment_claims` / `kept_stream` /
`norm1`），但**不設寬容**：任何一側差 1 個字都列出，並給出判定：

  EXACT      dq==0 且 da==0（完全一樣，最理想）
  NEAR       |d| <= max(3, 1%)
  MINOR      |d| <= max(12, 5%)
  BIG        其餘（需要人工看是該拆、該併，還是文字本來就不同）
  GLUE       一段認領 ≥2 個 block（該拆）
  MERGE      一個 block 被 ≥2 段認領（該併）
  NOLINK     frozen 與 claim 不一致
  FREEZE     frozen 指向的 block 沒有被任何段認領

用法:
    cd tool/word_audio_map2
    .venv/bin/python ../../audio_map2/tools/length_audit.py            # 人 readable
    .venv/bin/python ../../audio_map2/tools/length_audit.py --json out.json
"""
import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tool/word_audio_map2'))
spec = importlib.util.spec_from_file_location('sms', REPO / 'tool/word_audio_map2/split_missing_subquestions.py')
sms = importlib.util.module_from_spec(spec)
sys.modules['sms'] = sms
spec.loader.exec_module(sms)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', action='append')
    ap.add_argument('--json')
    ap.add_argument('--only', help='只看這些判定（逗號分隔）')
    args = ap.parse_args()

    blocks = sms.load_blocks()
    ctx = sms.build_ctx(blocks)
    months_all = sorted(p.stem for p in sms.AUDIO_MAP2_DIR.glob('????-??.json'))

    datasets, strong_qid, covered = {}, defaultdict(set), defaultdict(set)
    for m in months_all:
        data = json.loads((REPO / f'audio_map2/{m}.json').read_text(encoding='utf-8'))
        per_sess = []
        for sess in data['sessions']:
            sid = sess['session_id']
            info = []
            for i, seg in enumerate(sess['segments']):
                groups, carve, streams, ambig, dropped = sms.segment_claims(seg, ctx)
                info.append((groups, carve, streams, ambig, dropped))
                for g in groups:
                    for bi in g.blocks:
                        covered[blocks[bi].qid].add((m, sid, i))
                        if g.apos is not None and g.a_exact:
                            strong_qid[blocks[bi].qid].add((m, sid, i))
            per_sess.append((sess, info))
        datasets[m] = (data, per_sess)
    ctx['strong_qid'] = strong_qid
    ctx['covered'] = covered

    rows = []
    for m in (args.month or months_all):
        data, per_sess = datasets[m]
        for sess, info in per_sess:
            sid = sess['session_id']
            for i, seg in enumerate(sess['segments']):
                groups, carve, streams, ambig, dropped = info[i]
                kq = len(sms.kept_stream(seg.get('q_text') or '')[0])
                ka = len(sms.kept_stream(seg.get('answer_text') or '')[0])
                bq = sum(len(ctx['keptq'][g.blocks[0]]) for g in carve)
                ba = sum(len(ctx['kepta'][g.blocks[0]]) for g in carve)
                frozen = list(seg.get('chapter_question_ids') or [])
                cq = sorted({blocks[bi].qid for g in carve for bi in g.blocks})
                verdict = []
                if len(carve) >= 2:
                    verdict.append('GLUE')
                elif len(carve) == 1:
                    dq, da = kq - bq, ka - ba
                    if dq == 0 and da == 0:
                        verdict.append('EXACT')
                    elif max(abs(dq), abs(da)) <= max(3, int(max(bq, ba) * 0.01)):
                        verdict.append('NEAR')
                    elif max(abs(dq), abs(da)) <= max(12, int(max(bq, ba) * 0.05)):
                        verdict.append('MINOR')
                    else:
                        verdict.append('BIG')
                    if set(frozen) != set(cq):
                        verdict.append('NOLINK')
                else:
                    verdict.append('FREEZE' if frozen else 'NOCLAIM')
                rows.append(dict(month=m, sid=sid, i=i + 1, key=seg.get('stable_key'),
                                 start=seg.get('start'), end=seg.get('end'),
                                 verdict=verdict, dq=kq - bq, da=ka - ba,
                                 kq=kq, bq=bq, ka=ka, ba=ba,
                                 frozen=frozen, claimed=cq,
                                 lp=bool((seg.get('meta') or {}).get('lastPlayed')),
                                 nclaimed=len(covered.get(cq[0], ())) if cq else 0))

    # GLUE 之外，再標出「一個 block 被多段認領」（該併）
    multi = defaultdict(list)
    for r in rows:
        for q in r['claimed']:
            multi[q].append((r['month'], r['sid'], r['i']))
    for r in rows:
        if any(len(v) > 1 for v in [multi[q] for q in r['claimed']]):
            if 'MERGE' not in r['verdict']:
                r['verdict'].append('MERGE')

    tally = defaultdict(int)
    for r in rows:
        for v in r['verdict']:
            tally[v] += 1
    print(f'segments audited: {len(rows)}')
    for k in sorted(tally):
        print(f'  {k:<8} {tally[k]}')
    print(f"  (EXACT+NEAR+MINOR = {tally['EXACT'] + tally['NEAR'] + tally['MINOR']})")

    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), 'utf-8')
        print(f'JSON → {args.json}')

    show = set(args.only.split(',')) if args.only else None
    for r in rows:
        if show and not (set(r['verdict']) & show):
            continue
        if not show and set(r['verdict']) <= {'EXACT', 'NEAR', 'MERGE'} and 'MERGE' not in r['verdict']:
            continue
        print(f"[{'/'.join(r['verdict']):<18}] {r['month']} {r['key']} "
              f"[{r['start']}→{r['end']}] dq={r['dq']}({r['kq']}/{r['bq']}) "
              f"da={r['da']}({r['ka']}/{r['ba']}) lp={r['lp']} "
              f"frozen={len(r['frozen'])} claimed={len(r['claimed'])}")
        if r['verdict'] and ('MERGE' in r['verdict'] or 'BIG' in r['verdict']):
            for q in r['claimed']:
                if len(multi[q]) > 1:
                    print(f"        block {q} 也被 {[f'{a}#{b}#{c}' for a, b, c in multi[q]]} 認領")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
