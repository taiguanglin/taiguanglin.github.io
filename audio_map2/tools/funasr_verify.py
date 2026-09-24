#!/usr/bin/env python3
"""第一字錨定 FunASR 逐段驗證：每段檢查「段落文字第一個詞的實際開口 vs start」。

用法:
  funasr_verify.py <month>

只印報告（OK/EARLY/LATE/FIX-EARLY/NO-NAME/prev-tail/???），不自動改檔。
判定基準（同 first_char_audit.py ±0.15s 容差）:
  OK        = 第一詞（或其變形）字級 span 與 start 重疊（±0.15s）
  EARLY     = start 在第一詞 onset 前 ≤1.5s（合法，golden 同款）
  LATE      = start 晚於第一詞 span 結束 >0.15s（第一詞被跳過）——需修
  FIX-EARLY = start 在第一詞 onset 前 >1.5s（前段內容漏入）——需修
  NO-NAME   = 名未唸出 → 內容詞 onset 錨定（回報供判讀）
  prev-tail = 上一段尾字 end 在 start 後仍佔 ≥0.5s——需修

對位陷阱：paraformer 把整串字母的時間合併在第一個字母（HFFHI → H:3330–4990ms），
非 CJK 連續 run 共佔 1 個 timestamp entry（2024-22 實測 sum(len-1)=31=diff）。
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2/tools'))
from first_char_audit import parse_srt_raw, first_word, variants, _norm  # noqa: E402

PUNCT = set('。！？!?，、；,;: ')


def load_chars(cache_path):
    """text chars ↔ timestamp 對位：CJK 每字一筆；非 CJK 連續 run（字母串）共佔一筆"""
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


def find_occurrences(chars, vs, t0, t1):
    """第一個變形在 [t0, t1] 的字級出現（回傳 (onset, end, matched) 或 None）"""
    flat_items = [(i, s, e, ch) for i, (s, e, ch) in enumerate(chars) if s is not None]
    for i, s, e, ch in flat_items:
        if e < t0 or s > t1:
            continue
        window = ''.join(x[3] for x in flat_items[i:i + 12])
        nw = _norm(window)
        for v in vs:
            vn = _norm(v)
            if vn and vn in nw:
                return (s, e, v)
    return None


def main():
    month = sys.argv[1]
    month_path = REPO / 'audio_map2' / f'{month}.json'
    d = json.load(open(month_path))

    for sess in d['sessions']:
        sid = sess['session_id']
        cache = Path(f'/tmp/funasr_cache/{sid}.json')
        if not cache.exists():
            print(f'===== {sid}: 無 FunASR cache，跳過')
            continue
        chars = load_chars(cache)
        cues = parse_srt_raw(sess['media_parts'][0]['srt_file'])
        print(f"===== {sid} funasr_chars={len(chars)} =====")
        segs = sess['segments']
        # 音訊序 prev：JSON 序≠音訊序的月份（word-chrono 朗讀順序不同），
        # 上一段尾字要以 start 排序後的前一實段為準（單調月份排序＝原序，行為不變）
        order = sorted(range(len(segs)),
                       key=lambda i: (segs[i].get('start') is None,
                                      segs[i].get('start') if segs[i].get('start') is not None else 0))
        pos_of = {orig: pos for pos, orig in enumerate(order)}
        n_late = n_fixearly = n_prevtail = 0
        for k, g in enumerate(segs):
            st, en = g['start'], g.get('end')
            if st is None or en is None:
                print(f"{g['index']:>3} {'—':>9} {'—':>9} {'':<12} SKIP      空答案佔位段")
                continue
            fw = first_word(g['answer_text'] or g.get('q_text') or '')
            vs = [_norm(v) for v in variants(fw)]
            # 上一實段尾字 end（FunASR，音訊序）
            prev_end = None
            for kk in order[:pos_of[k]][::-1]:
                if segs[kk].get('start') is not None and segs[kk].get('end') is not None:
                    prev_end = segs[kk]['end']
                    break
            # 搜窗：start 前後（前段尾之後起）
            w0 = (prev_end - 1.0) if prev_end is not None else (st - 65)
            w0 = min(w0, st - 2)
            w1 = st + 35
            hit = find_occurrences(chars, vs, w0, w1)
            if hit is None:
                # 名未唸出 → 內容詞（文字第 2..6 詞）回退
                body = re.sub(r'^[\s\d、.．（）()【】\[\]]+', '', g['answer_text'] or g.get('q_text') or '')
                words = re.findall(r'[\u4e00-\u9fffA-Za-z0-9_]{1,8}', body)
                for wj in words[1:6]:
                    hit2 = find_occurrences(chars, [_norm(v) for v in variants(wj)], w0, w1)
                    if hit2 is not None:
                        s, e, v = hit2
                        diff = st - s
                        verdict = 'OK' if abs(diff) <= 0.15 else ('EARLY' if diff < 0 and -diff <= 1.5 else 'NO-NAME')
                        print(f"{g['index']:>3} {st:>9.3f} {en:>9.3f} {fw:<12} {verdict:<9} "
                              f"內容詞{wj!r}＝ASR{v!r} onset {s:.3f} (start {st - s:+.2f}s) [名未唸出]")
                        break
                else:
                    print(f"{g['index']:>3} {st:>9.3f} {en:>9.3f} {fw:<12} ???       "
                          f"[{w0:.1f}-{w1:.1f}] FunASR 未找到第一詞／內容詞")
                continue
            s, e, v = hit
            diff = st - s
            pt_note = ''
            if prev_end is not None and prev_end > st + 0.5:
                n_prevtail += 1
                pt_note = f' | prev-tail: 上一段尾字至 {prev_end:.3f}（逾 start {prev_end - st:.2f}s）'
            if abs(diff) <= 0.15:
                verdict = 'OK'
            elif diff < 0:
                if -diff <= 1.5:
                    verdict = 'EARLY'
                else:
                    n_fixearly += 1
                    verdict = 'FIX-EARLY'
            else:
                n_late += 1
                verdict = 'LATE'
            print(f"{g['index']:>3} {st:>9.3f} {en:>9.3f} {fw:<12} {verdict:<9} "
                  f"第一詞＝ASR{v!r} onset {s:.3f} (start {diff:+.2f}s){pt_note}")
        print(f"--- LATE: {n_late}  FIX-EARLY: {n_fixearly}  prev-tail: {n_prevtail}\n")


if __name__ == '__main__':
    raise SystemExit(main())
