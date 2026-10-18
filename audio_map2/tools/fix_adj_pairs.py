#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADJ 搬移對套用器：把 src 段的孤兒文字搬到 dest 段（依 analyze_adj_pairs.py 的 MOVE 判定）。

每對驗證後才動手：
  - dest 的 block 缺字 miss（kept 對齊）
  - miss 在 src 同欄位的對應 raw span（頭尾 12 字錨定模糊定位）
  - 搬後 dest／src 各自與 block 的吻合度都必須改善且 ≥0.93（wording 差允許些微殘差）
  - 時間窗全程不動 → lastPlayed／srt_preview 不變
  - q_text 有動的段重算 question_id／q_preview／answer_preview
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
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


def question_id(sid: str, index: int, q_text: str) -> str:
    h = hashlib.sha1(f"{sid}#{index}#{q_text[:80]}".encode()).hexdigest()[:12]
    return f"question-{h}"


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


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


PAIRS = [
    # (month, sid, dest_idx, src_idx, field)
    ('2024-02', '2024-02-15-main', 18, 19, 'a'),
    ('2024-03', '2024-03-01-main', 9, 8, 'a'),
    ('2024-03', '2024-03-16-main', 35, 34, 'a'),
    ('2024-03', '2024-03-23-main', 21, 22, 'a'),
    ('2024-03', '2024-03-26-main', 49, 50, 'a'),
    ('2024-12', '2024-12-13-wechat', 7, 8, 'a'),
    ('2025-03', '2025-03-12-tieba', 20, 21, 'a'),
    ('2024-05', '2024-05-20-main', 15, 14, 'q'),
    ('2024-03', '2024-03-01-main', 61, 60, 'q'),
    ('2024-03', '2024-03-12-main', 33, 32, 'q'),
    ('2024-08', '2024-08-12-main', 10, 9, 'q'),
    ('2024-11', '2024-11-11-main', 5, 4, 'q'),
    ('2024-04', '2024-04-24-main', 22, 21, 'q'),
]


def fuzzy_find(stream: str, probe: str):
    """在 kept stream 中找 probe 的位置（精確 → 滑窗模糊）→ kept index or None。"""
    p = stream.find(probe)
    if p >= 0:
        return p
    n = len(probe)
    if n < 6:
        return None
    for i in range(0, max(1, len(stream) - n + 1)):
        if ratio(probe, stream[i:i + n]) > 0.78:
            return i
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    get_block = load_blocks()
    months, applied, skipped = {}, [], []
    for month, sid, dst_i, src_i, field in PAIRS:
        if month not in months:
            months[month] = json.loads((REPO / f'audio_map2/{month}.json').read_text(encoding='utf-8'))
        d = months[month]
        sess = [s for s in d['sessions'] if s['session_id'] == sid][0]
        segs = {g['index']: g for g in sess['segments']}
        dst, src = segs[dst_i], segs[src_i]
        tag = f"{sid}: #{dst_i}←#{src_i} [{field}]"
        df = 'q_text' if field == 'q' else 'answer_text'
        b = get_block((dst.get('chapter_question_ids') or [None])[0])
        if b is None:
            print(f"SKIP {tag}: dest 無 block")
            skipped.append(tag)
            continue
        BK = kept(b['q_text'] if field == 'q' else b['a_text'])
        DK, SK = kept(dst.get(df) or ''), kept(src.get(df) or '')
        sm = difflib.SequenceMatcher(None, DK, BK, autojunk=False)
        ops = [(t, j1, j2) for t, _i1, _i2, j1, j2 in sm.get_opcodes()
               if t in ('insert', 'replace') and (j2 - j1) >= 6]
        miss = ''.join(BK[j1:j2] for t, j1, j2 in ops)
        at_head = ops and ops[0][1] == 0
        at_tail = ops and ops[-1][2] == len(BK)
        if not miss:
            print(f"SKIP {tag}: dest 已無 ≥6 缺字（可能已修）")
            skipped.append(tag)
            continue
        # ---- src 側切點：優先用「src vs 自己的 block」的 extra 區域 ----
        sb = get_block((src.get('chapter_question_ids') or [None])[0])
        sraw = src.get(df) or ''
        SKall, sidx = kept_idx(sraw)
        p1 = p2 = None
        if sb is not None:
            SBO = kept(sb['q_text'] if field == 'q' else sb['a_text'])
            sm2 = difflib.SequenceMatcher(None, SBO, SKall, autojunk=False)
            regions = [(j1, j2) for t, _i1, _i2, j1, j2 in sm2.get_opcodes()
                       if t in ('insert', 'replace') and (j2 - j1) >= 6]
            # 取與 miss 吻合度最高的區域（可能多段 → 串接）
            best = None
            for j1, j2 in regions:
                cand = SKall[j1:j2]
                r = ratio(miss, cand)
                if best is None or r > best[0]:
                    best = (r, j1, j2)
            if best and best[0] > 0.7:
                p1, p2 = best[1], best[2]
        if p1 is None:
            # src 無 block → 錨定 dest 的 miss
            p1 = fuzzy_find(SKall, miss[:12] if len(miss) >= 12 else miss)
            if p1 is not None:
                p2f = SKall.find(miss[-12:], p1 + 1) if len(miss) >= 24 else -1
                p2 = (p2f + 12) if p2f >= 0 else min(len(SKall), p1 + int(len(miss) * 1.2))
        if p1 is None:
            print(f"SKIP {tag}: src 中無法定位搬移 span")
            skipped.append(tag)
            continue
        moved_kept = SKall[p1:p2]
        r_move = ratio(miss, moved_kept)
        if r_move < 0.72:
            print(f"SKIP {tag}: 搬移文字吻合度不足 {r_move:.2f}（miss={len(miss)} moved={len(moved_kept)}）")
            skipped.append(tag)
            continue
        # ---- raw 邊界：向兩側延伸只吃標點/換行，吃到 kept 字為止 ----
        r1 = sidx[p1] if p1 < len(sidx) else len(sraw)
        r2 = sidx[p2] if p2 < len(sidx) else len(sraw)
        start = r1
        while start > 0 and (sraw[start - 1] in '\n\r\t '):
            start -= 1
        end = r2
        while end < len(sraw) and (sraw[end] in '。！？；，、…\n\r\t '):
            end += 1
        raw_span = sraw[start:end]
        # 搬後 raw
        new_src_raw = sraw[:start] + sraw[end:]
        new_src_raw = new_src_raw.strip('\n') if new_src_raw.strip() else ''
        draw = dst.get(df) or ''
        if at_head:
            new_dst_raw = raw_span + ('\n' if draw else '') + draw
        else:
            new_dst_raw = draw + ('\n\n' if draw and not draw.endswith('\n') else '') + raw_span
        r_dst = ratio(kept(new_dst_raw), BK)
        r_src = ratio(kept(new_src_raw or ''), kept(sb['a_text'] if field == 'a' else sb['q_text'])) if sb else 1.0
        if r_dst < 0.9 or (sb is not None and r_src < 0.9):
            print(f"SKIP {tag}: 搬後 dest {r_dst:.3f}／src {r_src:.3f} 不足")
            skipped.append(tag)
            continue
        print(f"MOVE {tag}: miss={len(miss)} src_span={p1}..{p2}（{len(moved_kept)} kept，吻合 {r_move:.2f}）"
              f" → dest {'頭' if at_head else '尾'}；搬後 dest↔block {r_dst:.3f}、src↔block {r_src:.3f}")
        applied.append((month, sid, dst, src, field, df, raw_span, new_dst_raw, new_src_raw))
    if not args.apply:
        print(f"\n(dry-run) 可搬 {len(applied)}／{len(PAIRS)}，SKIP {len(skipped)}")
        return 0
    from collections import defaultdict
    touched = defaultdict(set)
    for month, sid, dst, src, field, df, raw_span, new_dst_raw, new_src_raw in applied:
        dst[df] = new_dst_raw
        src[df] = new_src_raw
        for seg in (dst, src):
            if field == 'q':
                seg['question_id'] = question_id(sid, seg['index'], seg['q_text'])
            qp, ap2 = seg.get('q_text') or '', seg.get('answer_text') or ''
            seg['q_preview'] = qp[:100] + ('…' if len(qp) > 100 else '')
            seg['answer_preview'] = ap2[:160] + ('…' if len(ap2) > 160 else '')
        n_dst = (f"2026-10-18 length-fix：自鄰段 #{src['index']} 搬入 block 缺字"
                 f"（{len(kept(raw_span))} 保留字）→ 尾部" if True else '')
        dst['notes'] = (dst.get('notes') or '') + (
            f" | 2026-10-18 length-fix：自 #{src['index']} 搬入本段 block 缺字"
            f"（{len(kept(raw_span))} 保留字）；時間窗不動")
        src['notes'] = (src.get('notes') or '') + (
            f" | 2026-10-18 length-fix：本段多出的 {len(kept(raw_span))} 保留字"
            f" 屬 #{dst['index']} 的 block → 搬出；時間窗不動")
        touched[month].add(sid)
    for m, sids in touched.items():
        p = REPO / f'audio_map2/{m}.json'
        p.write_text(json.dumps(months[m], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f"  {m}: WRITTEN")
    print(f"套用 {len(applied)} 對")
    return 0


if __name__ == '__main__':
    sys.exit(main())
