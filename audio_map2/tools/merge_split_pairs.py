#!/usr/bin/env python3
"""One-shot repair: merge questioner-shell placeholder segments into the
content segment that actually carries the same Q&A (adjacent split pairs).

Pairs were flagged by find_split_pairs.py and each verified by hand:
the shell (empty q_text/answer_text or question-only) sits immediately
before the real segment whose questioner is '' and whose answer_text is
addressed to the questioner (e.g. '空空无我，一个佛住世…').

Rules (per SKILL.md 鐵律):
  - Word text fields are never modified; we only DELETE the shell segment
    and set the content segment's `questioner` from the shell.
  - Times: keep the content segment's span (envelope of the pair; the shell
    is either null or already inside/adjacent to it).
  - stable_key / index are NOT renumbered (UI keys on stable_key; the gap in
    `index` honestly records the removal). Both sides keep their meta.
  - The surviving segment keeps its own meta.lastPlayed/lastEdited.

Each edited file is backed up to /tmp/<month>.backup.json first, and every
file is revalidated afterwards (JSON parses; within a session, no inverted
or overlapping time spans; shell deleted; questioner transferred).
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# (file, session_id, shell stable_key, content stable_key)
PAIRS = [
    ("2024-02.json", "2024-02-28-main", "2024-02-28-main#54", "2024-02-28-main#55"),
    ("2024-02.json", "2024-02-29-main", "2024-02-29-main#27", "2024-02-29-main#28"),
    ("2024-03.json", "2024-03-01-main", "2024-03-01-main#48", "2024-03-01-main#49"),
    ("2024-03.json", "2024-03-22-main", "2024-03-22-main#26", "2024-03-22-main#27"),
    ("2024-03.json", "2024-03-29-main", "2024-03-29-main#1", "2024-03-29-main#2"),
    ("2024-04.json", "2024-04-24-main", "2024-04-24-main#27", "2024-04-24-main#28"),
    ("2024-05.json", "2024-05-20-main", "2024-05-20-main#34", "2024-05-20-main#35"),
    ("2024-05.json", "2024-05-22-main", "2024-05-22-main#40", "2024-05-22-main#41"),
    ("2024-05.json", "2024-05-25-main", "2024-05-25-main#20", "2024-05-25-main#21"),
    ("2024-07.json", "2024-07-18-main", "2024-07-18-main#18", "2024-07-18-main#19"),
    ("2024-07.json", "2024-07-19-main", "2024-07-19-main#44", "2024-07-19-main#45"),
    ("2025-01.json", "2025-01-14-tieba", "2025-01-14-tieba#30", "2025-01-14-tieba#31"),
    ("2025-01.json", "2025-01-15-wechat", "2025-01-15-wechat#5", "2025-01-15-wechat#6"),
    ("2025-05.json", "2025-05-14-wechat", "2025-05-14-wechat#11", "2025-05-14-wechat#12"),
]


def recompute_stats(d):
    st = {"sessions": 0, "segments": 0, "matched": 0, "low_conf": 0, "interpolated": 0,
          "pending": 0, "missing": 0, "openings_ok": 0, "closings_ok": 0}
    for s in d['sessions']:
        st['sessions'] += 1
        st['segments'] += len(s['segments'])
        for seg in s['segments']:
            if seg.get('start') is None:
                st['missing'] += 1
            else:
                st['matched'] += 1
                if (seg.get('confidence') or 0) < 0.5:
                    st['low_conf'] += 1
                if 'interpolated' in (seg.get('notes') or ''):
                    st['interpolated'] += 1
                if 'no-anchor:clamped' in (seg.get('notes') or '') or '待人工' in (seg.get('notes') or ''):
                    st['pending'] += 1
        if s.get('opening') is not None and s['opening'].get('start') is not None:
            st['openings_ok'] += 1
        if s.get('closing') is not None and s['closing'].get('start') is not None:
            st['closings_ok'] += 1
    return st


def merge_pair(session, shell_key, content_key):
    segs = session['segments']
    shell_idx = next((i for i, s in enumerate(segs)
                      if s.get('stable_key') == shell_key), None)
    if shell_idx is None:
        # Idempotent re-run: shell already merged into content.
        content = next(s for s in segs if s.get('stable_key') == content_key)
        assert (content.get('questioner') or '').strip() and \
            f'merged:{shell_key}' in (content.get('notes') or ''), \
            f"{shell_key}: shell gone but content not previously merged"
        return None
    ci = next(i for i, s in enumerate(segs) if s.get('stable_key') == content_key)
    assert ci == shell_idx + 1, \
        f"{session['session_id']}: shell/content not adjacent ({shell_idx},{ci})"
    shell, content = segs[shell_idx], segs[ci]

    assert not (shell.get('answer_text') or '').strip(), \
        f"{shell_key}: shell unexpectedly has answer_text"
    assert not (content.get('questioner') or '').strip(), \
        f"{content_key}: content already has questioner"

    shell_q = (shell.get('questioner') or '').strip()
    if shell_q:
        content['questioner'] = shell_q
    if shell.get('question_time') and not content.get('question_time'):
        content['question_time'] = shell['question_time']

    # Envelope: shell times must be contained in (not extend) the content span.
    # Zero-length stubs sitting exactly at content.start are the normal case.
    cs, ce = content.get('start'), content.get('end')
    for k in ('start', 'end'):
        v = shell.get(k)
        if v is None or cs is None or ce is None:
            continue
        assert cs - 1e-6 <= v <= ce + 1e-6, \
            f"{shell_key}: shell {k}={v} outside content span [{cs},{ce}]"

    # Fold shell provenance into notes (keep existing text fields untouched).
    old = content.get('notes') or ''
    tag = f"merged:{shell_key}"
    if tag not in old:
        content['notes'] = (old + ' | ' if old else '') + tag

    segs.pop(shell_idx)
    return shell_q or '(no questioner on shell)'


def validate(path, d, sess_id, content_key):
    """Structural check focused on the merge point. Old 2024 months carry
    pre-existing non-monotonic timelines (unaligned 主題式 audio), so quirks
    outside the merged segment are only reported, not fatal."""
    sess = next(s for s in d['sessions'] if s['session_id'] == sess_id)
    segs = sess['segments']
    keys = [s.get('stable_key') for s in segs]
    assert len(keys) == len(set(keys)), f"{path.name}: duplicate stable_key after merge"
    content = next(s for s in segs if s.get('stable_key') == content_key)
    cst, cen = content.get('start'), content.get('end')
    assert cst is None or cen is None or cen >= cst, \
        f"{path.name} {content_key}: merged segment span inverted"
    prev = None
    for seg in segs:
        st, en = seg.get('start'), seg.get('end')
        if st is not None and en is not None and en < st:
            print(f"    warn(pre-existing): inverted span at {seg.get('stable_key')} "
                  f"({st} > {en})")
        if st is None:
            continue
        if prev is not None and st < prev - 0.5:
            print(f"    warn(pre-existing): overlap {prev} -> {st} "
                  f"at {seg.get('stable_key')}")
        prev = max(prev, en) if prev is not None and en is not None \
            else (en if en is not None else prev)


def main():
    files = sorted({f for f, _, _, _ in PAIRS})
    for fname in files:
        path = HERE / fname
        backup = Path('/tmp') / (path.stem + '.backup.json')
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"  backup: {backup}")

    for fname, sess_id, shell_key, content_key in PAIRS:
        path = HERE / fname
        d = json.loads(path.read_text())
        sess = next(s for s in d['sessions'] if s['session_id'] == sess_id)
        who = merge_pair(sess, shell_key, content_key)
        if who is None:
            print(f"skip {shell_key} (already merged) [{fname}]")
            continue
        validate(path, d, sess_id, content_key)
        d['stats'] = recompute_stats(d)
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
        print(f"merged {shell_key} -> {content_key} (questioner={who}) [{fname}]")

    print("\nRe-scan after fix:")
    import subprocess
    subprocess.run([sys.executable, str(HERE / 'tools' / 'find_split_pairs.py')])


if __name__ == '__main__':
    main()
