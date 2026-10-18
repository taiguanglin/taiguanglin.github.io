#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADJ 搬移對的分析器：對每個候選（dest 段的 block 缺字 X 在 src 段）驗證：
  1. 雙側孤兒檢查：src 段自己比 block 是否多出 X（或 src 無 block）——
     若 src 需要 X（自己 EXACT）→ 電子書黏合，僅記錄不搬。
  2. 音檔定位：X 的特徵 n-gram 在該場 SRT 的時間 → 落在哪個窗：
     - 找不到（SILENT）→ 純搬移
     - 在 dest 窗 → 純搬移（音檔本來就歸 dest）
     - 在 src 窗 → 不搬（音檔站在 src）→ 僅記錄
輸出每對的判定與 raw 切點。dry-run only；套用由 fix_adj_pairs.py --apply 執行。
"""
from __future__ import annotations

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


def kept_idx(s: str):
    chars, idx = [], []
    for i, ch in enumerate(s or ''):
        if sms.KEPT.match(ch):
            chars.append(ch)
            idx.append(i)
    conv = _CC.convert(''.join(chars))
    if len(conv) != len(chars):
        conv = ''.join(chars)
    return conv.replace('著', '着'), idx


def kept(s: str) -> str:
    return kept_idx(s)[0]


def load_blocks():
    qa = json.loads((REPO / 'tool/word_audio_map2/build/html_qa_simp.json')
                    .read_text(encoding='utf-8'))
    import html as htmlmod

    def get(qid):
        if qid in qa:
            return qa[qid]
        for ch in range(1, 13):
            p = REPO / 'wenda2_ebook' / f"{ch:02d}.html"
            raw = p.read_text(encoding='utf-8')
            i = raw.find(f'id="{qid}"')
            if i < 0:
                continue
            m = re.search(r'<div class="question-text">(.*?)</div>', raw[i:], re.S)
            qtext = htmlmod.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
            mn = re.search(r'<div class="(question|answer)" id="', raw[i + 10:])
            region = raw[i:i + 10 + (mn.start() if mn else 0)]
            ma = re.search(r'<div class="answer" id="(answer-[0-9a-f]+(?:-2)?)">', region)
            if ma:
                m2 = re.search(r'<div class="answer-text">(.*?)</div>', region[ma.end():], re.S)
                atext = htmlmod.unescape(re.sub(r"<[^>]+>", "", m2.group(1))).strip() if m2 else ""
            else:
                mp = re.search(r'<p id="content-[0-9a-f]+">(.*?)</p>', region, re.S)
                if not mp:
                    return None
                atext = htmlmod.unescape(re.sub(r"<[^>]+>", "",
                                                mp.group(1).replace('<br/>', '\n'))).strip()
            return {"chapter": ch, "q_text": qtext, "a_text": atext}
        return None
    return get


def srt_cues(sess):
    cues, off = [], 0.0
    for p in sess['media_parts']:
        sp = Path(p.get('srt_file') or '')
        if not sp.exists():
            sp = REPO / 'audio' / 'srt' / f"{p.get('stem')}.srt"
        if not sp.exists():
            continue
        for a, b, t in parse_srt_raw(sp):
            cues.append((a + off, b + off, t))
        off += p.get('duration_est') or 0.0
    return cues


def srt_norm_text(cues):
    return [(cs, re.sub(r'[^\w]', '', t)) for cs, _ce, t in cues]


def locate_in_srt(x: str, cues_norm, tries=4):
    """用 X 的數個 n-gram 在 SRT cue 裡找時間點；回傳 (t, matched_gram) 或 None。"""
    x = x.replace('著', '着')
    n = 12
    grams = []
    if len(x) <= n:
        grams = [x]
    else:
        for k in range(tries):
            pos = int((k + 0.5) * (len(x) - n) / tries)
            grams.append(x[pos:pos + n])
    for g in grams:
        for cs, t in cues_norm:
            if g in t:
                return cs, g
    # 拼音級 fallback 交由人工；這裡回 None
    return None


# 候選對：(month, sid, dest_idx, src_idx, field)
PAIRS = [
    ('2024-02', '2024-02-15-main', 18, 19, 'a'),
    ('2024-02', '2024-02-26-main', 17, 18, 'a'),
    ('2024-03', '2024-03-01-main', 9, 8, 'a'),
    ('2024-03', '2024-03-16-main', 35, 34, 'a'),
    ('2024-03', '2024-03-23-main', 21, 22, 'a'),
    ('2024-03', '2024-03-26-main', 49, 50, 'a'),
    ('2024-12', '2024-12-13-wechat', 7, 8, 'a'),
    ('2025-03', '2025-03-12-tieba', 20, 21, 'a'),
    ('2025-05', '2025-05-16-wechat', 13, 12, 'a'),
    ('2024-05', '2024-05-20-main', 15, 14, 'q'),
    ('2025-05', '2025-05-16-wechat', 12, 13, 'q'),
    ('2024-04', '2024-04-26-main', 14, 15, 'q'),
    ('2024-04', '2024-04-26-main', 15, 14, 'a'),
    ('2024-03', '2024-03-01-main', 61, 60, 'q'),
    ('2024-03', '2024-03-12-main', 33, 32, 'q'),
    ('2024-08', '2024-08-12-main', 10, 9, 'q'),
    ('2024-11', '2024-11-11-main', 5, 4, 'q'),
    ('2024-03', '2024-03-23-main', 25, 26, 'q'),
    ('2024-03', '2024-03-23-main', 35, 36, 'q'),
    ('2024-03', '2024-03-27-main', 39, 40, 'q'),
    ('2024-03', '2024-03-28-main', 32, 33, 'q'),
    ('2024-04', '2024-04-23-main', 21, 22, 'q'),
    ('2024-04', '2024-04-24-main', 17, 18, 'q'),
    ('2024-04', '2024-04-24-main', 22, 21, 'q'),
    ('2024-04', '2024-04-25-main', 7, 8, 'q'),
    ('2024-04', '2024-04-27-main', 35, 36, 'q'),
    ('2024-07', '2024-07-16-main', 25, 26, 'q'),
]


def main() -> int:
    get_block = load_blocks()
    months = {}
    for month, sid, dst_i, src_i, field in PAIRS:
        if month not in months:
            months[month] = json.loads((REPO / f'audio_map2/{month}.json').read_text(encoding='utf-8'))
        d = months[month]
        sess = [s for s in d['sessions'] if s['session_id'] == sid][0]
        segs = {g['index']: g for g in sess['segments']}
        dst, src = segs.get(dst_i), segs.get(src_i)
        tag = f"{sid}: #{dst_i}←#{src_i} [{field}]"
        if dst is None or src is None:
            print(f"??  {tag}: 段不存在")
            continue
        dqids = dst.get('chapter_question_ids') or []
        b = get_block(dqids[0]) if dqids else None
        if b is None:
            print(f"??  {tag}: dest block 不存在（{dqids[:1]}）")
            continue
        df = 'q_text' if field == 'q' else 'answer_text'
        D = kept(dst.get(df) or '')
        B = kept(b['q_text'] if field == 'q' else b['a_text'])
        sm = difflib.SequenceMatcher(None, D, B, autojunk=False)
        miss = ''.join(B[j1:j2] for t, _i1, _i2, j1, j2 in sm.get_opcodes()
                       if t in ('insert', 'replace') and (j2 - j1) >= 6)
        if not miss:
            print(f"??  {tag}: dest 缺字 <6（現況 {len(D)}/{len(B)}）")
            continue
        S = kept(src.get(df) or '')
        p = S.find(miss)
        # 雙側孤兒檢查：src 的 block
        sqids = src.get('chapter_question_ids') or []
        sb = get_block(sqids[0]) if sqids else None
        if sb is None:
            orphan = True
            snote = 'src 無 block（孤兒）'
        else:
            SBO = kept(sb['q_text'] if field == 'q' else sb['a_text'])
            # src 是否「多出」miss：S vs SBO 的 extra 是否含 miss
            sm2 = difflib.SequenceMatcher(None, SBO, S, autojunk=False)
            extra = ''.join(S[j1:j2] for t, _i1, _i2, j1, j2 in sm2.get_opcodes()
                            if t in ('insert', 'replace') and (j2 - j1) >= 6)
            orphan = bool(extra) and (miss in extra or difflib.SequenceMatcher(
                None, miss, extra, autojunk=False).ratio() > 0.85)
            snote = f"src block {'無' if not sqids else sqids[0]}；src extra={'有' if extra else '無'}"
        # 音檔定位
        cues_norm = srt_norm_text(srt_cues(sess))
        hit = locate_in_srt(miss, cues_norm)
        wdst = (dst.get('start'), dst.get('end'))
        wsrc = (src.get('start'), src.get('end'))
        if hit is None:
            where = 'SILENT'
        else:
            t = hit[0]
            if wdst[0] is not None and wdst[0] <= t <= wdst[1]:
                where = 'dest 窗內'
            elif wsrc[0] is not None and wsrc[0] <= t <= wsrc[1]:
                where = f'src 窗內（t={t:.1f}）'
            else:
                where = f'他處（t={t:.1f}）'
        verdict = 'MOVE' if orphan and where in ('SILENT', 'dest 窗內') else (
            'GLUE-RECORD' if not orphan else 'AUDIO-IN-SRC/elsewhere → 不搬，記錄')
        print(f"{verdict:<14} {tag}: miss={len(miss)} kept，S 中位置={p}，{snote}，音檔={where}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
