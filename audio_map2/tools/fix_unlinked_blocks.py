#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""未連結 block 的拆分／連結套用器（2026-10-18 length-fix 第二批，v2）。

拆段一律用 raw 切點搬移（不重打字）：舊段保留前半，新段承接其後全部文字
（C 案再把「監獄」之後的部分另成第三段）。每步驗證場內字元多重集不變。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tool' / 'word_audio_map2'))
sys.path.insert(0, str(REPO / 'tool' / 'pdf_audio_map'))
import split_missing_subquestions as sms  # noqa: E402
from common import parse_srt_raw, srt_preview  # noqa: E402


def qid_of(sid, index, q_text):
    return 'question-' + hashlib.sha1(f'{sid}#{index}#{q_text[:80]}'.encode()).hexdigest()[:12]


def kept(s):
    return sms.kept_stream(s or '')[0]


def make_labels(g):
    def lab(t):
        h, m = int(t // 3600), int(t % 3600 // 60)
        s = t % 60
        return f"{h:02d}:{m:02d}:{int(s):02d}.{int(round((s-int(s))*1000)):03d}"
    g['start_label'] = lab(g['start'])
    g['end_label'] = lab(g['end'])


def refresh(g):
    qp, ap = g.get('q_text') or '', g.get('answer_text') or ''
    g['q_preview'] = qp[:100] + ('…' if len(qp) > 100 else '')
    g['answer_preview'] = ap[:160] + ('…' if len(ap) > 160 else '')


def cues_of(sess):
    cues, off = [], 0.0
    for p in sess['media_parts']:
        sp = Path(p.get('srt_file') or '')
        if not sp.exists():
            sp = REPO / 'audio' / 'srt' / f"{p.get('stem')}.srt"
        if not sp.exists():
            continue
        cues.extend([(a + off, b + off, t) for a, b, t in parse_srt_raw(sp)])
        off += p.get('duration_est') or 0.0
    return cues


def renumber(sess, first):
    for g in sess['segments']:
        if g['index'] >= first:
            g['stable_key'] = f"{sess['session_id']}#{g['index']}"
            g['question_id'] = qid_of(sess['session_id'], g['index'], g.get('q_text') or '')


def base_seg(old, q, a, idx, start, end, sid, note, links):
    g = {'questioner': old.get('questioner'), 'question_time': old.get('question_time'),
         'q_text': q, 'answer_text': a, 'start': start, 'end': end,
         'confidence': 0.9, 'status': 'manual', 'notes': note,
         'index': idx, 'stable_key': f'{sid}#{idx}'}
    if links and links[0]:
        g['chapter_question_ids'] = links[0]
        g['chapter_answer_ids'] = links[1]
        g['chapter_indexes'] = links[2]
    g['question_id'] = qid_of(sid, idx, q or '')
    make_labels(g)
    refresh(g)
    return g


def clear_lp(g):
    if (g.get('meta') or {}).get('lastPlayed'):
        g['meta'] = {'lastPlayed': '', 'lastEdited': ''}
        return True
    return False


def remap_overrides(month, sid, old_idx, shift, pins, apply):
    ov_p = REPO / 'audio_map2' / 'tools' / f'{month}_overrides.json'
    if not ov_p.exists():
        return
    ov = json.loads(ov_p.read_text(encoding='utf-8'))
    moved = {}
    for k, v in ov.items():
        s2, _, lab = k.partition('|')
        if s2 == sid and lab.startswith('#') and int(lab[1:]) > old_idx:
            moved[k] = f"{sid}|#{int(lab[1:]) + shift}"
    for k, nk in moved.items():
        ov[nk] = ov.pop(k)
    for i, v in pins.items():
        ov[f"{sid}|#{i}"] = v
    if apply:
        ov_p.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def char_ms(sess):
    c = Counter()
    for g in sess['segments']:
        c.update(kept((g.get('q_text') or '') + (g.get('answer_text') or '')))
    return c


def do_split(month, sid, old_idx, cut_q_marker, cut_a_marker, boundary, new_end, links,
             note, apply, tail_a_marker=None, tail_q_for_new='', tail_links=None,
             tail_end=None, tail_note='', q_to_new2=False):
    """把 sid#old_idx 拆成兩段；tail_a_marker 有值時拆成三段。"""
    p = REPO / f'audio_map2/{month}.json'
    d = json.loads(p.read_text(encoding='utf-8'))
    sess = [s for s in d['sessions'] if s['session_id'] == sid][0]
    cues = cues_of(sess)
    before = char_ms(sess)
    old = [g for g in sess['segments'] if g['index'] == old_idx][0]
    q_raw, a_raw = old.get('q_text') or '', old.get('answer_text') or ''
    cut_a = a_raw.index(cut_a_marker)
    cut_q = q_raw.index(cut_q_marker) if cut_q_marker else None
    old_q_new = (q_raw[:cut_q].rstrip('，, \n') + '\n') if cut_q is not None else q_raw
    old_a_new = a_raw[:cut_a].rstrip()
    tail_cut = a_raw.index(tail_a_marker) if tail_a_marker else len(a_raw)
    new1_q = (q_raw[cut_q:].strip('\n') if cut_q is not None else '')
    new1_a = a_raw[cut_a:tail_cut].strip('\n')
    new2_a = a_raw[tail_cut:].strip('\n') if tail_a_marker else None
    # 舊段
    old['q_text'], old['answer_text'] = old_q_new.strip('\n') or old_q_new, old_a_new
    old['end'] = boundary
    make_labels(old)
    lp_cleared = clear_lp(old)
    old['notes'] = (old.get('notes') or '') + ' | ' + note
    refresh(old)
    old['srt_preview'] = srt_preview(cues, old['start'], old['end'])
    old['question_id'] = qid_of(sid, old['index'], old.get('q_text') or '')
    # 新段
    nseg = 2 if tail_a_marker is None else 3
    new1 = base_seg(old, ('' if q_to_new2 else new1_q), new1_a, old_idx + 1, boundary,
                    (tail_end if nseg == 3 else new_end), sid, note, links)
    new1['srt_preview'] = srt_preview(cues, new1['start'], new1['end'])
    inserts = [new1]
    if nseg == 3:
        new2_q = (new1_q if q_to_new2 else tail_q_for_new) or ''
        new2 = base_seg(old, new2_q, new2_a, old_idx + 2,
                        tail_end, new_end, sid, tail_note, tail_links)
        new2['srt_preview'] = srt_preview(cues, new2['start'], new2['end'])
        inserts.append(new2)
    # 尾段重編
    for g in sess['segments']:
        if g['index'] > old_idx:
            g['index'] += len(inserts)
    pos = next(i for i, g in enumerate(sess['segments']) if g['index'] == old_idx)
    for g in reversed(inserts):
        sess['segments'].insert(pos + 1, g)
    renumber(sess, old_idx + 1)
    # 守恆驗證
    after = char_ms(sess)
    assert before == after, f"{sid}: 字元多重集不守恆！"
    remap_overrides(month, sid, old_idx, len(inserts),
                    {g['index']: g['start'] for g in inserts}, apply)
    if apply:
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{'APPLY' if apply else 'DRY  '} {sid}#{old_idx}→+{len(inserts)}: "
          f"舊[…,{boundary}] 新1[{boundary},{new1['end']}]"
          + (f" 新2[{tail_end},{new_end}]" if nseg == 3 else '')
          + (f"｜lastPlayed已清" if lp_cleared else ""))


def do_link(month, sid, idx, qid_add, aid_add, ch_add, note, apply):
    p = REPO / f'audio_map2/{month}.json'
    d = json.loads(p.read_text(encoding='utf-8'))
    sess = [s for s in d['sessions'] if s['session_id'] == sid][0]
    g = [x for x in sess['segments'] if x['index'] == idx][0]
    g['chapter_question_ids'] = (g.get('chapter_question_ids') or []) + qid_add
    g['chapter_answer_ids'] = (g.get('chapter_answer_ids') or []) + aid_add
    g['chapter_indexes'] = (g.get('chapter_indexes') or []) + ch_add
    g['notes'] = (g.get('notes') or '') + ' | ' + note
    if apply:
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{'APPLY' if apply else 'DRY  '} LINK {sid}#{idx}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    do_split('2024-03', '2024-03-26-main', 41,
             '不定业满足什么条件能转为定业？',
             '“不定业满足什么条件转为定业”', 2286.00, 2446.65,
             [['question-4860ce7f3cd2'], ['answer-16f47cac2eb0'], [2]],
             ('2026-10-18 length-fix：本段原含兩個 Q&A（挨打反擊＋不定業），依 02.html block'
              '（question-4860ce7f3cd2）拆出下一段；邊界＝「不」字級 onset opus/mp3 '
              '2286.01/2286.00（取較早）。需複聽。'), args.apply)

    do_split('2025-02', '2025-02-11-tieba', 14,
             '像肺本身就不是很好的人，怎么消除二手烟的危害？',
             '肺本身就不是很好的人，怎么消除二手烟的危害？', 1511.67, 1561.33,
             [['question-e260c8331802'], ['answer-89e8e1f18bf8'], [2]],
             ('2026-10-18 length-fix：本段原含兩個 Q&A（二手煙消業＋消除危害），依 02.html '
              'block（question-e260c8331802）拆出下一段；邊界＝「肺」字級 onset opus/mp3 '
              '1511.71/1511.67（取較早）。需複聽。'), args.apply)

    do_split('2025-05', '2025-05-16-tieba', 34,
             '内丹与元神有',
             '内丹与元神有何不同？我这么说了', 3491.33, 3539.2,
             [['question-61986c8ee0a6'], ['answer-75c12e9c42ac'], [12]],
             ('2026-10-18 length-fix：本段原含兩個 Q&A（元神＋內丹），依 12.html block'
              '（question-61986c8ee0a6）拆出下一段；邊界＝唸回首字 onset opus/mp3 '
              '3491.35/3491.33（取較早）。彙總的子題文字本身斷在「内丹与元神有」。需複聽。'),
             args.apply)

    do_split('2024-11', '2024-11-11-main', 30,
             '2、终于能提问了，我先给Tai师父磕一个。',
             '监狱的环境不好，每天念《地藏经》好', 2236.57, 2388.32,
             [['question-a29eaf73334c'], ['answer-749988daaa10'], [7]],
             ('2026-10-18 length-fix：原 #30 含 3 問 4 答（歡喜心／夢境／母親＋監獄）。'
              '「監獄」Q&A 的問題僅在電子書（07.html block question-a29eaf73334c），彙總只有'
              '答案 → 拆成下一段（q_text 依彙總留空）；邊界1＝貼吧/微信過渡「这」onset 2236.57；'
              '歡喜心 Q&A 與 01.html block（question-0d5938f36473）對應不變。需複聽。'),
             args.apply,
             tail_a_marker='第二个问题，梦境有时候有预示性',
             tail_q_for_new='', tail_links=[[], [], []], tail_end=2275.99, q_to_new2=True,
             tail_note=('2026-10-18 length-fix：由原 11-11#30 拆出（夢境＋母親兩問）。'
                        '此兩問未出現於電子書（彙總獨有），不帶章節連結；'
                        '邊界2＝「还」字級 onset opus/mp3 2275.99/2275.99。需複聽。'))

    do_link('2024-02', '2024-02-17-main', 31,
            ['question-1013fe14c241'], ['answer-5a08fe85dfe2'], [11],
            ('2026-10-18 length-fix：本段＝11.html block（question-1013fe14c241）的答案'
             '（清風飾月：打坐/參思情），彙總缺其問題文字（q_text 留空）→ 補章節連結；'
             '窗 [1569.23,1670.7] 已含本段答案音檔（1571「你如果用更高级的修法…」）。'),
            args.apply)

    do_link('2024-03', '2024-03-02-main', 42,
            ['question-e2659b929821'], ['answer-2e8b780a6db7'], [11],
            ('2026-10-18 length-fix：本段＝11.html block（question-e2659b929821）的答案'
             '（多杰扎西：娑婆世界眾生曾有佛的狀態），該 block 的 question-text 是 Excel '
             '儲存格產物「2024+A1422:M1422」→ 以 qid＋answer id 連結；窗 [2549.33,2605.83] '
             '與音檔對應。'),
            args.apply)
    return 0


if __name__ == '__main__':
    sys.exit(main())
