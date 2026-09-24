#!/usr/bin/env python3
"""第一字錨定 FunASR 全場字級掃描（音訊序）：每段找「段落第一個詞」的 onset ＋ 建議修正。

用法:
  funasr_onset_scan.py <month> [--session <session_id>] [--cache-dir /tmp/funasr_cache]

對每個有 cache 的 session（或 --session 指定者），以音訊序（start 排序）逐段印：
  # / start / end / 第一詞 / 匹配（FunASR 串，含前後文） / onset / delta / 建議

匹配：VAR 變形表（first_char_audit.variants）＋ pinyin 模糊比對（zh/z ch/c sh/s、
ang/an eng/en ing/in、n/l 互換、數字→中文讀法）。全場字流找候選，取離 start 最近者
為建議錨點；多候選全印供判讀。

判定（同 funasr_verify ±0.15s 容差、EARLY≤1.5s 合法）:
  OK        = start 在 onset ±0.15s 內或提前 ≤1.5s
  EARLY     = 提前 1.5–3s（golden 邊緣，建議微收）
  FIX-EARLY = 提前 >3s（前段內容漏入）——需修
  LATE      = start 晚於 onset >0.15s——需修（start := onset）
  NO-NAME   = 名未轉出，以內容詞回退錨定（回報供判讀）
  ???       = 全場找不到第一詞／內容詞

另印音訊序鏈現況（gap>0.3s / overlap）與 opening/closing 銜接。
只印報告，不自動改檔。
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2/tools'))
from first_char_audit import parse_srt_raw, first_word, variants, _norm  # noqa: E402

PUNCT = set('。！？!?，、；,;: ')

try:
    from pypinyin import lazy_pinyin
except ImportError:
    lazy_pinyin = None

# 數字 → 中文讀法（FunASR 常把阿拉伯數字讀成中文數字；1 也可讀幺）
_DIGIT_PY = {
    '0': ('ling', 'dong'), '1': ('yi', 'yao'), '2': ('er', 'liang'),
    '3': ('san', 'san'), '4': ('si', 'si'), '5': ('wu', 'wu'),
    '6': ('liu', 'liu'), '7': ('qi', 'qi'), '8': ('ba', 'ba'),
    '9': ('jiu', 'jiu'),
}


def _py_raw(ch):
    """單字 → 原始拼音（ASCII 保留小寫；其他交 pypinyin）"""
    if ch.isascii():
        return re.sub(r'[^a-z0-9]', '', ch.lower())
    if lazy_pinyin is None:
        return ''
    try:
        p = lazy_pinyin(ch, errors=lambda x: [''])
        return p[0] if p and p[0] else ''
    except Exception:
        return ''


def _py_norm(p):
    """拼音模糊正規化：平翹舌、前後鼻音、n/l、v/u"""
    if not p:
        return ''
    for a, b in (('zh', 'z'), ('ch', 'c'), ('sh', 's')):
        if a in p:
            p = p.replace(a, b)
    for a, b in (('ang', 'an'), ('eng', 'en'), ('ing', 'in'),
                 ('ong', 'on'), ('uan', 'un')):
        if a in p:
            p = p.replace(a, b)
    p = p.replace('v', 'u')
    return p


def _py_alts(ch):
    """單字 → 可接受的拼音集合（本尊＋n/l 互換＋數字讀法）"""
    if ch.isdigit() and ch in _DIGIT_PY:
        return set(_DIGIT_PY[ch])
    base = _py_norm(_py_raw(ch))
    if not base:
        return set()
    out = {base}
    swap = base.replace('n', 'l') if 'n' in base else base.replace('l', 'n') if 'l' in base else base
    if swap:
        out.add(swap)
    return out


def load_chars(cache_path):
    """text chars ↔ timestamp 對位：CJK 每字一筆；非 CJK 連續 run 共佔一筆"""
    c = json.load(open(cache_path))
    text, ts = c['text'], c['timestamp']

    def is_cjk(ch):
        return '\u4e00' <= ch <= '\u9fff'

    chars = []
    ti = 0
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace() or ch in PUNCT:
            i += 1
            continue
        if is_cjk(ch):
            unit = ch
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in PUNCT \
                    and not is_cjk(text[j]):
                j += 1
            unit = text[i:j]
            i = j
        if ti < len(ts):
            chars.append((ts[ti][0] / 1000.0, ts[ti][1] / 1000.0, unit))
            ti += 1
        else:
            chars.append((None, None, unit))
    return chars


def find_candidates(chars, fw, t_ref, topn=3, ctx=6):
    """全場字流找第一詞候選；取離 t_ref 最近者為建議，全部按距離排序回傳。

    比對雙軌：(a) VAR 變形表（first_char_audit.variants）子字串比對（_norm 去
    空白／書名號，跨 12 字窗）；(b) 前 k 字（k=min(len,4)，1字詞 k=1）py-alts 全等。
    回傳 [(dist, onset, matched_str, ctx_text), ...]
    """
    flat = [(i, s, e, ch) for i, (s, e, ch) in enumerate(chars) if s is not None]
    fw_units = re.findall(r'[\u4e00-\u9fff]+|[A-Za-z0-9]+', fw)
    fw_units = fw_units[:1] if fw_units else [fw]
    fw_chars = list(fw_units[0])
    alts = [_py_alts(c) for c in fw_chars]
    k = min(len(alts), 4)
    cands = []
    if k:
        for idx in range(len(flat) - k + 1):
            ok = True
            for j in range(k):
                if not (alts[j] & _py_alts(flat[idx + j][3])):
                    ok = False
                    break
            if not ok:
                continue
            onset = flat[idx][1]
            dist = abs(onset - t_ref)
            matched = ''.join(x[3] for x in flat[idx:idx + k])
            lo = max(0, idx - ctx)
            hi = min(len(flat), idx + k + ctx)
            ctxt = ''.join(x[3] for x in flat[lo:hi])
            cands.append((dist, onset, matched, ctxt))
    # VAR 變形子字串比對（捕捉 pinyin 對不上的 ASR 亂串，如 偶米大→歐米伽）
    vs = [v for v in variants(fw_units[0]) if _norm(v)]
    for i in range(len(flat)):
        s0 = flat[i][1]
        if abs(s0 - t_ref) > 120:
            continue
        window = ''.join(x[3] for x in flat[i:i + 12])
        nw = _norm(window)
        for v in vs:
            vn = _norm(v)
            if vn and vn in nw:
                dist = abs(s0 - t_ref)
                lo = max(0, i - ctx)
                hi = min(len(flat), i + ctx + 8)
                ctxt = ''.join(x[3] for x in flat[lo:hi])
                cands.append((dist, s0, v, ctxt))
                break
    # 去重（同 onset 取先）
    seen = {}
    for c in sorted(cands, key=lambda x: (x[0], x[1])):
        if c[1] not in seen:
            seen[c[1]] = c
    out = sorted(seen.values(), key=lambda x: (x[0], x[1]))
    return out[:topn]


def fmt_t(t):
    if t is None:
        return 'None'
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('month')
    ap.add_argument('--session', default=None)
    ap.add_argument('--cache-dir', default='/tmp/funasr_cache')
    ap.add_argument('--all-real', action='store_true',
                    help='印全部實段（含 OK；預設只印需判讀段）')
    args = ap.parse_args()

    month_path = REPO / 'audio_map2' / f'{args.month}.json'
    d = json.load(open(month_path))
    for sess in d['sessions']:
        if args.session and sess['session_id'] != args.session:
            continue
        cache = Path(args.cache_dir) / f"{sess['session_id']}.json"
        if not cache.exists():
            print(f'===== {sess["session_id"]}: 無 FunASR cache，跳過')
            continue
        chars = load_chars(cache)
        print(f'===== {sess["session_id"]} funasr_chars={len(chars)} =====')
        segs = sess['segments']
        real = [(i, g) for i, g in enumerate(segs)
                if g.get('start') is not None and g.get('end') is not None]
        # 音訊序
        real_sorted = sorted(real, key=lambda x: (x[1]['start'], x[0]))
        pos = {orig: p for p, (orig, _g) in enumerate(real_sorted)}

        n_late = n_fixearly = n_novalue = 0
        for orig_i, g in real_sorted:
            st, en = g['start'], g['end']
            fw = first_word(g['answer_text'] or g.get('q_text') or '')
            # 上一實段（音訊序）尾
            prev_end = None
            for kk in [o for o, _ in real_sorted[:pos[orig_i]]][::-1]:
                if segs[kk].get('end') is not None:
                    prev_end = segs[kk]['end']
                    break
            cands = find_candidates(chars, fw, st)
            # 名未唸出 → 內容詞回退（第 2..5 詞）
            used_body = False
            if not cands:
                body = re.sub(r'^[\s\d、.．（）()【】\[\]]+', '',
                              g['answer_text'] or g.get('q_text') or '')
                words = re.findall(r'[\u4e00-\u9fffA-Za-z0-9_]{1,8}', body)
                for wj in words[1:6]:
                    bc = find_candidates(chars, wj, st, topn=1)
                    if bc:
                        cands = bc
                        used_body = True
                        break
            tag = 'NO-NAME' if used_body else ''
            if not cands:
                n_novalue += 1
                print(f"{g['index']:>3} {st:>9.3f} {en:>9.3f} {fw:<14} {'???':<9} "
                      f"全場未找到第一詞／內容詞")
                continue
            dist, onset, matched, ctxt = cands[0]
            diff = onset - st   # >0: start 提前；<0: start 落後（LATE）
            if diff >= -0.15:
                verdict = 'OK' if diff <= 1.5 else ('EARLY' if diff <= 3 else 'FIX-EARLY')
                if verdict == 'FIX-EARLY':
                    n_fixearly += 1
            else:
                verdict = 'LATE'
                n_late += 1
            pt = ''
            if prev_end is not None and prev_end > st + 0.5:
                pt = f' | prev-tail→{prev_end:.2f}'
            alt_txt = ''
            if len(cands) > 1:
                alt_txt = ' | 次選: ' + '; '.join(
                    f'{m}@{o:.2f}(d{di:.1f})' for di, o, m, _ in cands[1:3])
            fix = ''
            if verdict == 'LATE':
                fix = f' → 修 start: {st:.3f}→{onset:.3f}'
            elif verdict == 'FIX-EARLY':
                fix = f' → 修 start: {st:.3f}→{onset - 0.3:.3f}'
            elif verdict == 'EARLY':
                fix = f'（可收至 {onset - 0.3:.3f}）'
            if args.all_real or verdict not in ('OK',):
                print(f"{g['index']:>3} {st:>9.3f} {en:>9.3f} {fw:<14} {verdict + tag:<9} "
                      f"匹配{matched!r}@{onset:.3f} (start {diff:+.2f}s){pt}{fix}{alt_txt}")

        # 音訊序鏈現況
        gaps = []
        for (a_i, a), (b_i, b) in zip(real_sorted, real_sorted[1:]):
            if b['start'] - a['end'] > 0.3:
                gaps.append(f"#{a['index']}→#{b['index']} gap {b['start'] - a['end']:.2f}s")
            elif a['end'] - b['start'] > 0.01:
                gaps.append(f"#{a['index']}→#{b['index']} OVERLAP {a['end'] - b['start']:.2f}s")
        opening = sess.get('opening') or {}
        closing = sess.get('closing') or {}
        first_st = real_sorted[0][1]['start']
        last_en = real_sorted[-1][1]['end']
        oc_notes = []
        if opening.get('end') is not None and abs((opening['end'] or 0) - first_st) > 0.01:
            oc_notes.append(f"opening.end {opening['end']} ≠ 第一段 start {first_st}")
        if closing.get('start') is not None and abs(last_en - closing['start']) > 0.01:
            oc_notes.append(f"末段 end {last_en} ≠ closing.start {closing['start']}")
        print(f"--- LATE: {n_late}  FIX-EARLY: {n_fixearly}  ???: {n_novalue}")
        if gaps:
            print(f"--- 鏈 gap/overlap: {'; '.join(gaps)}")
        if oc_notes:
            print(f"--- opening/closing: {'; '.join(oc_notes)}")
        print()


if __name__ == '__main__':
    raise SystemExit(main())
