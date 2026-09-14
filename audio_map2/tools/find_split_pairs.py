#!/usr/bin/env python3
"""Scan audio_map2/*.json for adjacent placeholder/real QA segment pairs.

A "split pair" is two adjacent segments covering the SAME question, typically:
  - seg A: q_text=='' and answer_text=='' (placeholder, often zero-length span
    or dup time of seg B), and
  - seg B: the real Q&A whose questioner is '' and whose answer_text starts
    with the questioner name (e.g. '空空无我，一个佛住世…').

Only unconfirmed segments are candidates (per AGENTS.md the review-completion
gate is meta.lastPlayed, and golden status = confidence>=0.8 + status
manual/reviewed); pairs where either side is already confirmed are only
reported as INFO since they'd already have been through human review.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ANSWER_HEAD = re.compile(
    r'^(?:下一个问题[，,]?\s*)?([\u4e00-\u9fff·A-Za-z0-9_]{1,20})[，,、：:]\s*')


def is_placeholder(seg):
    return not (seg.get('q_text') or '').strip() and \
        not (seg.get('answer_text') or '').strip()


def confirmed(seg):
    """Human-listened segment (per AGENTS.md the completion gate is lastPlayed;
    aligner status=manual does NOT mean a human reviewed it)."""
    return bool((seg.get('meta') or {}).get('lastPlayed'))


def seg_label(seg):
    return (f"#{seg.get('index')} {seg.get('stable_key', '')} "
            f"q={seg.get('questioner') or '∅'!r}")


def main():
    verbose = '-v' in sys.argv
    hits = []
    for path in sorted(HERE.glob('*.json')):
        try:
            d = json.loads(path.read_text())
        except Exception as e:
            print(f"!! {path.name}: {e}")
            continue
        for sess in d.get('sessions', []):
            segs = sess.get('segments', [])
            for a, b in zip(segs, segs[1:]):
                ans = (b.get('answer_text') or '')
                m = ANSWER_HEAD.match(ans)
                addr = m.group(1) if m else None
                a_ph, b_ph = is_placeholder(a), is_placeholder(b)
                a_no_q = not (a.get('questioner') or '').strip()
                b_no_q = not (b.get('questioner') or '').strip()
                conf_pair = confirmed(a) or confirmed(b)
                kind = 'INFO(1 confirmed)' if conf_pair else 'HIT'
                hit = None
                # P1: questioner-only shell before its content segment
                if a_ph and not b_ph and b_no_q:
                    hit = ('P1', kind if addr else 'SOFT')
                # P2: shell carries the questioner AFTER the content segment
                elif b_ph and not a_ph and a_no_q:
                    hit = ('P2r', kind)
                # P3: question text in A (no answer), answered content in B
                elif not a_ph and not b_ph and b_no_q and (a.get('questioner') or '').strip() \
                        and not (a.get('answer_text') or '').strip() and addr \
                        and addr == (a.get('questioner') or '').strip():
                    hit = ('P3', kind)
                if hit:
                    pat, kind2 = hit
                    hits.append({
                        'file': path.name, 'session': sess['session_id'],
                        'kind': f'{pat}:{kind2}', 'a': a, 'b': b,
                        'addressed_to': addr,
                    })

    for h in hits:
        a, b = h['a'], h['b']
        ta = f"{a.get('start')}-{a.get('end')}" if a.get('start') is not None else 'null'
        tb = f"{b.get('start')}-{b.get('end')}" if b.get('start') is not None else 'null'
        print(f"[{h['kind']}] {h['file']} {h['session']}")
        print(f"    A: {seg_label(a)} t={ta} conf={a.get('confidence')} "
              f"played={(a.get('meta') or {}).get('lastPlayed') or '-'} "
              f"notes={ (a.get('notes') or '')[:80]!r}")
        print(f"    B: {seg_label(b)} t={tb} conf={b.get('confidence')} "
              f"played={(b.get('meta') or {}).get('lastPlayed') or '-'} "
              f"addr_to={h['addressed_to']!r}")
        q = (b.get('q_text') or '')[:60].replace('\n', '⏎')
        print(f"    B.q_text: {q!r}")
        if verbose:
            ans = (b.get('answer_text') or '')[:80].replace('\n', '⏎')
            print(f"    B.answer: {ans!r}")
    for pat in ('P1', 'P2r', 'P3'):
        group = [h for h in hits if h['kind'].startswith(pat + ':')]
        n_hit = sum(1 for h in group if h['kind'].endswith(':HIT'))
        n_info = sum(1 for h in group if ':INFO' in h['kind'])
        n_soft = sum(1 for h in group if h['kind'].endswith(':SOFT'))
        print(f"{pat}: {n_hit} HIT, {n_info} INFO, {n_soft} SOFT")
    print("(scanned all audio_map2/*.json)")


if __name__ == '__main__':
    main()
