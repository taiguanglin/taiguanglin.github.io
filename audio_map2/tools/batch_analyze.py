#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析 `batch_anchor.py` 的字級快取：判定每個邊界 `start` 對第一詞 onset 的偏差。

**判定口徑**（比 SKILL §5 的 Δ 表更嚴，因為 Δ 表只看「start 之後第一個字」，
抓不到「start 落在首詞第二個字之後」这种小幅截首）：

以段落文字的 `first_word`（含 `first_char_audit.variants()` 的 ASR 變形）在字級時間軸上
模糊比對定位（字面 + `pypinyin` 拼音音節級），取**離 `start` 最近且分數夠高**的匹配窗，
其第一個字的時刻＝**真實首詞 onset**。然後 `Δ = start − true_onset`：

| Δ | 判定 | 處置 |
|---|------|------|
| `> +0.15` | `LATE` | start 截進首詞內，必修（移到 true_onset） |
| `-0.15 … +0.15` | `OK` | 貼齊首字 |
| `-1.5 … -0.15` | `EARLY` | 提前量 ≤1.5s 合法（SKILL §1.3） |
| `< -1.5` | `EARLY2` | 提前過多；若 start 之前是過渡語且答案不以過渡語開頭 → 應前移到首詞 |
| 無匹配 | `???` | ASR 變形太大，需人工判讀 |
| 雙解碼器 true_onset 差 >0.15s | 加 `XDEC` | 跨解碼器不一致，取較早者並記 notes |

另標 `TRANS`：`start` 抓到的字串是「下一个问题」之類過渡語、而 `answer_text` **不**以
過渡語開頭 → 依 SKILL §2 過渡語屬上一段，`start` 應前移到首詞 onset。

用法:
    .venv/bin/python batch_analyze.py --month 2024-12 [--session SID] [--verdict V] [--ctx]
"""
import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from first_char_audit import first_word, variants  # noqa: E402

try:
    from pypinyin import lazy_pinyin, Style
    def _py(s):
        return ''.join(lazy_pinyin(s, style=Style.NORMAL, errors=lambda x: x))
except Exception:                                                      # noqa: BLE001
    def _py(s):
        return s

# 過渡語：出現在 start 與首詞 onset 之間、且答案不以它開頭 → 應屬上一段（SKILL §2）
TRANS_PAT = re.compile(
    r'(下一个问题|下个问题|下一個問題|第[一二三四五六七八九十]个问题|还有下一个问题|'
    r'那下一个问题|還有下一個問題|下一个|還有下個|下一个问题呢)')

# 純字母／數字的人名：paraformer 會把整串併在首字母，變形處理不適用
LATIN = re.compile(r'^[A-Za-z0-9_@.\-]+$')


def fuzzy(a, b):
    """字面 ＋ 大小寫無關 ＋ 拼音三軌相似度取大。"""
    s1 = SequenceMatcher(None, a, b).ratio()
    s2 = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    best = max(s1, s2)
    if not (LATIN.match(a) or LATIN.match(b)):
        pa, pb = _py(a), _py(b)
        if pa and pb:
            best = max(best, SequenceMatcher(None, pa, pb).ratio())
    return best


ALIGNED = 0.9  # 命中窗「對齊良好」門檻：拼音/字面幾乎全中


def find_word(chars, word, start, lo=-9.0, hi=6.0, min_score=0.5, use_var=True):
    """在 [(start+lo), (start+hi)] 的字級時間軸上找 `word`（含 ASR 變形）的最佳匹配。

    回傳 (score, true_onset, matched_window_text, candidate, is_plausible) 或 None。

    ⚠️ **只拿整詞／變形／長度 ≥3 的前綴去比對**：早期版本把長度 1–2 的前綴也放進候選，
    害 `下一个问题` 的前綴「我们」（`variants()` 實測會產生）以 0.5 分命中音檔裡的
    「我们」，把錨點帶到答案正文裡（2024-12-09-tieba #20）。縮到 ≥3 後這類假匹配消失。

    `use_var=False` 給「答案前綴」退級探針用：VAR 表是為**已知人名**整理的，套在任意
    前綴上會生出離譜的變形（實測 `云常听` 被變形成能命中「下一个问」）。
    """
    if not chars or not word:
        return None
    t_lo, t_hi = start + lo, start + hi
    idx = [i for i, (t, _c) in enumerate(chars) if t_lo <= t <= t_hi]
    if not idx:
        return None
    i0, i1 = idx[0], idx[-1]

    cands = [word]
    full = {word}
    if use_var and not LATIN.match(word):
        vs = [v for v in variants(word) if v != word]
        if len(word) <= 3:
            # **短詞的 VAR 變形要限長**：`VAR` 是為已知人名整理的，裡面有以單字為 key
            # 的寬鬆條目——`variants('云')` 實測會生出 `下一个问题`（5 字），
            # 害 2024-12-11-wechat #9 的「雲」以 1.0 分命中音檔裡的「下一個問」。
            # 短詞只接受長度 ≤ len+2 的變形。
            vs = [v for v in vs if len(v) <= len(word) + 2]
        cands += vs
        full |= set(vs)
    # 長度 ≥3 的遞減前綴：唸回常只唸前 3–4 字（「先拜众生再拜佛」只唸「先拜众生」）
    seen, extra = set(cands), []
    for v in list(cands):
        for n in range(len(v) - 1, 2, -1):
            p = v[:n]
            if p not in seen and p not in extra:
                extra.append(p)
    cands += extra

    hits = []
    n_c = len(chars)
    for cand in cands:
        L = len(cand)
        if L == 0 or L > n_c:
            continue
        for i in range(i0, i1 + 1):
            win = ''.join(c for _t, c in chars[i:i + L])
            # 時間連續性懲罰：防止跨長停頓拼接出假的長匹配
            if i + L <= n_c and chars[i + L - 1][0] - chars[i][0] > 4.0:
                continue
            sc = fuzzy(cand, win)
            if sc < min_score:
                continue
            hits.append((chars[i][0], sc, win, cand))
    if not hits:
        return None
    # **先對齊、後比早晚**：命中窗可以整體錯位一格（`聖輝` 的候選窗寬 2，落在
    # 「說盛」時拿到 0.588、落在真正的「盛輝」時拿到 1.0）。若直接用「取最早」的規則，
    # 錯位窗會因為出現在前面而勝出，把錨點釘在上一句尾巴上（2024-11 實測
    # `11-11 #39` −3.29s、`11-13 #19` −3.25s、`11-11 #57` −1.93s）。
    # 所以先只留分數達 ALIGNED（拼音/字面幾乎全中）的窗，**再**在其中取最早。
    aligned = [h for h in hits if h[1] >= ALIGNED]
    pool = aligned or hits
    best = None
    for t0, sc, win, cand in pool:
        if best is None:
            best = (t0, sc, win, cand)
            continue
        # 同一次出現（±1.2s 內）取分數最高者；不同次出現取**最早**那個——
        # SKILL §2／2025-01-15 golden：人名被唸兩次時錨點在第一次（第一次才是
        # 「回答首字」）。舊版用「離舊 start 近」當權重，會系統性跳過真正的第一次
        # （2024-12 實測 86 個邊界有這種雙次出現）。
        if t0 - best[0] <= 1.2:
            if sc > best[1]:
                best = (t0, sc, win, cand)
        elif t0 < best[0]:
            best = (t0, sc, win, cand)
    if best is None:
        return None
    cand = best[3]
    # 「可信候選」＝命中的是整詞／VAR 變形本身，或**正規詞的前綴**（音檔只唸前半）。
    # VAR 變形再截出來的前綴不算（`下一个问题` 的變形 `我们下一个` 截成 `我们下` 會命中
    # 答案正文裡的「我们」，2024-12-09-tieba #20 實測）。
    return best[1], best[0], best[2], best[3], (cand in full or word.startswith(cand))


def classify(delta, dec_ok=True):
    if delta is None:
        return '???'
    if delta > 0.15:
        return 'LATE'
    if delta < -1.5:
        return 'EARLY2'
    if delta < -0.15:
        return 'EARLY'
    return 'OK'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--session', default='')
    ap.add_argument('--verdict', default='', help='只印這些判定（逗號分隔）')
    ap.add_argument('--ctx', action='store_true', help='印 start 前後 3s 的完整字流')
    args = ap.parse_args()

    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    files = sorted(cdir.glob('*.json'))
    if args.session:
        files = [f for f in files if f.name.startswith(args.session)]

    rows, tally = [], {}
    for f in files:
        r = json.load(open(f, encoding='utf-8'))
        st = r['start']
        fw = r['first_word']
        res, chars = {}, {}
        for tag in ('opus', 'mp3'):
            d = r.get(tag) or {}
            if 'error' in d or not d.get('chars'):
                res[tag] = None
                chars[tag] = []
                continue
            chars[tag] = d['chars']
            res[tag] = find_word(d['chars'], fw, st)
        # 雙解碼器：取較早的 true_onset（SKILL §3 跨窗／跨解碼器不一致取較早者）
        ons = [v[1] for v in res.values() if v]
        xdec = len(ons) == 2 and abs(ons[0] - ons[1]) > 0.15
        to = min(ons) if ons else None
        delta = None if to is None else round(st - to, 3)
        vd = classify(delta)
        if to is None:
            vd = '???'
        if xdec:
            vd += '+XDEC'

        # TRANS：start 抓到的字是過渡語、但答案不以過渡語開頭
        trans = ''
        if delta is not None and delta < -0.25:
            span = (r.get('answer_head') or '').lstrip()
            if not TRANS_PAT.match(span) and not span.startswith('还有'):
                before = ''.join(c for t, c in chars.get('opus') or [] if st - 1.5 <= t < to)
                if TRANS_PAT.search(before):
                    trans = 'TRANS'
                    vd += '+TRANS'
        tally[vd] = tally.get(vd, 0) + 1
        rows.append((r, vd, delta, to, xdec, trans, res, chars))

    def _ord(x):
        lb = x[0]['label']
        return 0 if lb == 'opening' else (9999 if lb == 'closing' else int(lb.lstrip('#')))

    rows.sort(key=lambda x: (x[0]['session_id'], _ord(x)))

    print(f"{'session':<20}{'label':>9}{'start':>11}{'Δ':>8}  {'判定':<18}"
          f"{'首詞onset':>10}  first_word")
    print('-' * 116)
    for r, vd, delta, to, xdec, trans, res, chars in rows:
        if args.verdict and not any(v in vd for v in args.verdict.split(',')):
            continue
        st = r['start']
        print(f"{r['session_id']:<20}{r['label']:>9}{st:>11.3f}"
              f"{('' if delta is None else f'{delta:+.2f}'):>8}  {vd:<18}"
              f"{('' if to is None else f'{to:.2f}'):>10}  {r['first_word']}")
        if args.ctx:
            for tag in ('opus', 'mp3'):
                if not chars.get(tag):
                    continue
                sel = [f"{t:.2f}:{c}" for t, c in chars[tag] if st - 2.0 <= t <= st + 3.0]
                print(f"     {tag:<4}:", ' '.join(sel))
            print('     A[:40]:', r['answer_head'])
    print('-' * 116)
    print('統計:', json.dumps(tally, ensure_ascii=False, sort_keys=True))
    print('⚠ OK/EARLY 仍需過「內容定位檢查」才收案（SKILL §5.5）')


if __name__ == '__main__':
    raise SystemExit(main())
