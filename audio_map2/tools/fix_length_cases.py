#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""full_triage 案例的修補器（dry-run 預設，--apply 才寫檔）。

QA_TRANSFER：段的 answer_text 開頭含 block 的 question_text（q/a 切分錯置）→
把問題部分搬回 q_text；answer_text 從 block 答案首字起切。純文字搬位：
  - 同段內搬移 → 場內字元多重集不變（文字守恆）
  - 時間窗／srt_preview 不動（問題本來就在窗內被唸回）
  - question_id 依 resplit_by_html.question_id 公式重算（含 q_text 前 80 字）
  - q_preview／answer_preview 重算
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tool' / 'word_audio_map2'))
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


def find_cut(ans_raw: str, ba_kept: str):
    """在段的 answer_text 中找到 block 答案開頭的位置（kept index → raw index）。"""
    ka, idx = kept_idx(ans_raw)
    if not ba_kept:
        return None, None, None
    probe = ba_kept[:24]
    best = None
    # 1) 精確頭匹配
    p = ka.find(probe)
    if p >= 0:
        # 往前掃：答案頭可能重複出現（唸回題幹），取「最後一次」出現之後仍吻合全長的位置
        while True:
            p2 = ka.find(probe, p + 1)
            if p2 < 0:
                break
            p = p2
        return p, idx, ka
    # 2) 滑窗模糊
    n = len(probe)
    for i in range(0, max(1, len(ka) - n + 1)):
        if difflib.SequenceMatcher(None, probe, ka[i:i + n], autojunk=False).ratio() > 0.78:
            best = i
            break
    return best, idx, ka


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--key', help='只處理這些段（sid#N 逗號分隔）')
    args = ap.parse_args()

    triage = json.loads(Path('/tmp/triage.json').read_text(encoding='utf-8'))
    cases = [c for c in triage if c['shape'] == 'QA_TRANSFER']
    if args.key:
        want = set(args.key.split(','))
        cases = [c for c in cases if c['key'] in want]

    qa_blocks = json.loads((REPO / 'tool/word_audio_map2/build/html_qa_simp.json')
                           .read_text(encoding='utf-8'))

    import html as htmlmod
    import re as _re

    def get_block(qid):
        if qid in qa_blocks:
            return qa_blocks[qid]
        # extract_html_qa 配不到的 block → 直接解析 HTML（兩種形狀：
        # ① answer id 帶 -2 後綴；② 答案是裸 <p id="content-…">（無 answer div））
        for ch in range(1, 13):
            p = REPO / 'wenda2_ebook' / f"{ch:02d}.html"
            raw = p.read_text(encoding='utf-8')
            i = raw.find(f'id="{qid}"')
            if i < 0:
                continue
            m = _re.search(r'<div class="question-text">(.*?)</div>', raw[i:], _re.S)
            qtext = htmlmod.unescape(_re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
            # 區段終點：下一個 question 或 answer div
            mn = _re.search(r'<div class="(question|answer)" id="', raw[i + 10:])
            region_end = i + 10 + (mn.start() if mn else len(raw))
            region = raw[i:region_end]
            ma = _re.search(r'<div class="answer" id="(answer-[0-9a-f]+(?:-2)?)">', region)
            if ma:
                m2 = _re.search(r'<div class="answer-text">(.*?)</div>', region[ma.end():], _re.S)
                atext = htmlmod.unescape(_re.sub(r"<br\s*/?>", "\n", m2.group(1))) if m2 else ""
                atext = htmlmod.unescape(_re.sub(r"<[^>]+>", "", atext)).strip()
                aid = ma.group(1)
            else:
                # 裸 <p id="content-…"> 答案
                mp = _re.search(r'<p id="content-[0-9a-f]+">(.*?)</p>', region, _re.S)
                if not mp:
                    raise KeyError(qid)
                atext = htmlmod.unescape(_re.sub(r"<br\s*/?>", "\n", mp.group(1)))
                atext = htmlmod.unescape(_re.sub(r"<[^>]+>", "", atext)).strip()
                aid = ""
            return {"chapter": ch, "q_text": qtext, "answer_id": aid, "a_text": atext}
        raise KeyError(qid)
    months = {}
    ok, skipped = [], []
    for c in cases:
        m = c['month']
        if m not in months:
            months[m] = json.loads((REPO / f'audio_map2/{m}.json').read_text(encoding='utf-8'))
        d = months[m]
        sess = [s for s in d['sessions'] if s['session_id'] == c['sid']][0]
        seg = [g for g in sess['segments'] if g['index'] == c['idx']][0]
        b = get_block(c['qid'])
        ans_raw = seg.get('answer_text') or ''
        ba_kept = kept(b['a_text'])
        bq, sq = kept(b['q_text']), kept(seg.get('q_text') or '')
        tag = f"{c['key']}"
        q_part = a_part = None

        # 路徑 1：整段問題在答案開頭 → 在 block 答案首字處切
        cut, idx, _ka = find_cut(ans_raw, ba_kept)
        if cut is not None and idx:
            raw_cut = idx[cut] if cut < len(idx) else len(ans_raw)
            qp0, ap0 = ans_raw[:raw_cut], ans_raw[raw_cut:]
            kq0 = kept((seg.get('q_text') or '') + qp0)
            ka0 = kept(ap0)
            rq0 = difflib.SequenceMatcher(None, kq0, bq, autojunk=False).ratio()
            ra0 = difflib.SequenceMatcher(None, ka0, ba_kept, autojunk=False).ratio()
            if rq0 >= 0.93 and ra0 >= 0.93:
                q_part, a_part = qp0, ap0
                print(f"OK    {tag}: q {len(sq)}→{len(kq0)}（blk {len(bq)}）"
                      f" a {len(kept(ans_raw))}→{len(ka0)}（blk {len(ba_kept)}）"
                      f" rq={rq0:.3f} ra={ra0:.3f}  搬移開頭『{qp0[:24]}…』")

        # 路徑 2：缺的問題字落在答案中間（子題文字夾在兩個答案之間）→ 抽出搬去 q_text 尾
        if q_part is None:
            sm = difflib.SequenceMatcher(None, sq, bq, autojunk=False)
            # 注意方向：sm(sq, bq) 的 insert/replace 的 j 側＝block q 有、seg q 沒有的字
            miss = ''.join(bq[j1:j2] for t, _i1, _i2, j1, j2 in sm.get_opcodes()
                           if t in ('insert', 'replace') and (j2 - j1) >= 6)
            kaa, iaa = kept_idx(ans_raw)
            p = kaa.find(miss) if miss else -1
            if miss and p >= 0 and kaa.find(miss, p + 1) < 0:
                start_raw = iaa[p]
                end_k = p + len(miss)
                end_raw = iaa[end_k] if end_k < len(iaa) else len(ans_raw)
                nxt = ans_raw.find('\n', end_raw)
                cut_end = (nxt + 1 if nxt > 0 else end_raw)
                qp1 = ans_raw[start_raw:cut_end]
                ap1 = ans_raw[:start_raw] + '\n' + ans_raw[cut_end:]
                kq1 = kept((seg.get('q_text') or '') + qp1)
                ka1 = kept(ap1)
                rq1 = difflib.SequenceMatcher(None, kq1, bq, autojunk=False).ratio()
                ra1 = difflib.SequenceMatcher(None, ka1, ba_kept, autojunk=False).ratio()
                if rq1 > 0.93 and ra1 > 0.93:
                    q_part, a_part = qp1, ap1
                    print(f"OK*   {tag}: 中段子題搬移 q {len(sq)}→{len(kq1)}（blk {len(bq)}）"
                          f" a {len(kaa)}→{len(ka1)}（blk {len(ba_kept)}）rq={rq1:.3f} ra={ra1:.3f}")

        if q_part is None:
            print(f"SKIP  {tag}: 兩種搬移路徑皆驗證失敗（需人工）")
            skipped.append(tag)
            continue
        ok.append((m, c['sid'], seg, q_part, a_part, c['qid']))

    if not args.apply:
        print(f"\n(dry-run) 可修 {len(ok)}／{len(cases)}，SKIP {len(skipped)}；加 --apply 套用")
        return 0
    from collections import defaultdict
    by_month = defaultdict(list)
    for m, sid, seg, q_part, a_part, qid in ok:
        seg['q_text'] = ((seg.get('q_text') or '') + ('\n' if seg.get('q_text') else '') + q_part).strip('\n')
        seg['answer_text'] = a_part
        seg['question_id'] = question_id(sid, seg['index'], seg['q_text'])
        qp, ap2 = seg['q_text'], seg['answer_text']
        seg['q_preview'] = qp[:100] + ('…' if len(qp) > 100 else '')
        seg['answer_preview'] = ap2[:160] + ('…' if len(ap2) > 160 else '')
        seg['notes'] = (seg.get('notes') or '') + (
            f" | 2026-10-18 length-fix：QA_TRANSFER——block（{qid}）的 question_text"
            f"（{len(kept(q_part))} 保留字）原誤置於本段 answer_text 開頭，搬回 q_text；"
            f"時間窗未動（問題朗讀本在窗內）")
        by_month[m].append((sid, seg['index']))
    for m, items in by_month.items():
        p = REPO / f'audio_map2/{m}.json'
        p.write_text(json.dumps(months[m], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f"  {m}: WRITTEN（{len(items)} 段）")
    print(f"套用 {len(ok)} 段，SKIP {len(skipped)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
