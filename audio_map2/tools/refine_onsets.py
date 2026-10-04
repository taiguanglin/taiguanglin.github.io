#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**逐一**把每段 `start` 收斂到音檔中「答案首字」的**字級 onset**（毫秒級）。

與既有工具的差別：

- `batch_anchor.py` 只**量**，把 12s 短窗的 opus／mp3 字級時間軸落盤；
  `batch_analyze.py`／`propose_fixes.py` 拿它去對**首詞（人名）**。
- `rebuild_anchors.py` 用**整場轉錄**做內容定位，但整場有 ±5s 的 VAD 抖動
  （見 `audio_map2/AGENTS.md` 2024-12 教訓 5），拿不到毫秒級絕對時間。

本工具**直接吃 `batch_anchor` 的字級快取**，用兩種證據各自定位「答案第一個字」，
再依 SKILL 的規則合成：

1. **人名 onset** —— 首詞（含 `first_char_audit.variants()` 變形）在窗內模糊比對，
   分數需 **≥ `--name-score`（預設 0.9）** 才採信。單字／純字母名不採信（撞字風險）。
2. **內容 onset** —— **跳過人名**後取 `answer_head` 的前 N 音節在窗內定位，
   對應到窗內第一個匹配字的時刻。

合成規則（對應 AGENTS.md「人名 ≥0.9 否則內容探針」那條，但改成**字級實測**）：

- 兩者都有且人名在內容之前 → **取人名 onset**（答案自叫名那一刻開始）。
- 兩者都有但人名比內容晚 >3s → 人名多半是誤命中，**取內容 onset**。
- 只有人名 / 只有內容 → 取該者。
- 都沒有 → **不猜**，標 `??`，留給 `reanchor.py`／`onset_at.py` 人工處理。

雙解碼器各自獨立定位；**衝突（差 > `--dec-tol`）取較早者**並標 `XDEC`，
寫進 `notes` 提醒下輪會震盪。

用法:
    tool/sense_voice/.venv/bin/python audio_map2/tools/refine_onsets.py \\
        --month 2024-03 --out /tmp/am2_2024-03/refined.json [--apply]
"""
import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from first_char_audit import first_word, variants   # noqa: E402

try:
    from pypinyin import lazy_pinyin, Style

    def _py(s):
        return ''.join(lazy_pinyin(s, style=Style.NORMAL, errors=lambda x: x))
except Exception:                                                    # noqa: BLE001
    def _py(s):
        return s


LATIN = re.compile(r'^[A-Za-z0-9_@.\-]+$')
# 虛詞／語氣字：命中窗開頭若是這些且答案首詞不以它開頭 → 前移到窗內第一個實字
FILLER = set('的了着呢吧呀嘛啊哦嗯唉喔噢')


def fuzzy(a, b):
    """字面 ＋ 小寫 ＋ 拼音三軌相似度取大（與 `batch_analyze.fuzzy` 同口徑）。"""
    best = max(SequenceMatcher(None, a, b).ratio(),
               SequenceMatcher(None, a.lower(), b.lower()).ratio())
    pa, pb = _py(a), _py(b)
    if pa and pb:
        best = max(best, SequenceMatcher(None, pa, pb).ratio())
    return best


def cands(word):
    """首詞的所有候選寫法：原字 + ASR 變形。"""
    out = {word, word.replace(' ', '')}
    out |= set(variants(word))
    return [w for w in out if w]


def find_block(chars, text, min_run=4):
    """在字級時間軸上找 `text` **最早開始被唸出**的一段（拼音比對）。

    不能用「跳過人名的固定字數」當探針：人名常常根本沒被唸（ASR 聽成別的字），
    照字數切會切到正文中間，探針整個對不上。
    也不能只用「答案前綴」：老師常常跳過開頭（`《心经》已经讲过了` 實際沒唸），
    直接從 `般若波罗蜜多` 講起 → 前綴永遠對不上。
    → 改用**拼音序列的區塊對齊**：取第一段長度 ≥ `min_run` 音節的連續命中，
      它的起點就是「答案內文最早開始被唸出」的位置。
    回傳 (匹配音節數, onset)；onset 取該區塊第一個非虛詞字的時刻。
    """
    if len(chars) < 2 or not text:
        return 0, None
    s = ''.join(c for _t, c in chars)
    ts = [t for t, _c in chars]
    pw, pt = _py(s), _py(text)
    if not pw or not pt:
        return 0, None
    # 拼音音節數 → 字元索引 的對應
    idx = []
    n = 0
    for ci, ch in enumerate(s):
        k = len(_py(ch))
        idx.extend([ci] * max(k, 1))
        n += max(k, 1)
    if n != len(pw):
        idx = list(range(len(s)))
        pw = s
    sm = SequenceMatcher(None, pw, pt, autojunk=False)
    best = (0, None)
    for a, _b, size in sm.get_matching_blocks():
        if size < min_run:
            continue
        ci = idx[a] if a < len(idx) else len(s) - 1
        j = ci
        while j < len(s) and s[j] in FILLER:
            j += 1
        t = ts[min(j, len(ts) - 1)]
        if best[0] == 0 or t < best[1]:          # 取**最早**開始的那一段
            best = (size, t)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--cache', default='')
    ap.add_argument('--out', required=True)
    ap.add_argument('--name-score', type=float, default=0.9)
    ap.add_argument('--text-run', type=int, default=4,
                    help='內容區塊至少要連續命中幾個音節才採信')
    ap.add_argument('--text-score', type=float, default=0.72)
    ap.add_argument('--probe', type=int, default=60, help='內容探針最大長度（音節）')
    ap.add_argument('--dec-tol', type=float, default=0.35, help='雙解碼器容許差')
    ap.add_argument('--min-shift', type=float, default=0.15)
    ap.add_argument('--only', default='',
                    help='只處理這些邊界（每行 `<session_id>|<label>` 的檔案）')
    ap.add_argument('--max-early', type=float, default=1.5,
                    help='最多容許比現值早幾秒（SKILL §1.3 提前量上限 1.5s）')
    args = ap.parse_args()

    cdir = Path(args.cache or f'/tmp/am2_{args.month}')
    data = json.load(open(REPO / 'audio_map2' / f'{args.month}.json', encoding='utf-8'))
    cur = {(s['session_id'], f"#{g['index']}"): g['start']
           for s in data['sessions'] for g in s['segments'] if g['start'] is not None}

    ov, unknown, xdec, src, dropped = {}, [], 0, {}, {}
    latin = 0
    only = ({ln.strip() for ln in open(args.only, encoding='utf-8') if ln.strip()}
            if args.only else None)
    for (sid, label), st in cur.items():
        if only is not None and f'{sid}|{label}' not in only:
            continue
        f = cdir / f'{sid}__{label[1:]}.json'
        if not f.exists():
            unknown.append(f'{sid}|{label}'); continue
        c = json.load(open(f, encoding='utf-8'))
        head = c.get('answer_head') or ''
        fw = c.get('first_word') or first_word(head)
        # 內容探針：跳過人名
        # 內容探針＝**整段答案**（跳過人名後、去掉標點）。用區塊對齊找出「最早開始
        # 被唸出的那一段」，所以不需要猜老師從第幾個字開口。
        cut = len(fw)
        text_full = re.sub(r'[^一-鿿A-Za-z0-9]', '', head[cut:])[:args.probe]

        name_probe = None
        if fw and not LATIN.match(fw) and len(fw) >= 2:
            name_probe = cands(fw)
        elif LATIN.match(fw or ''):
            # 字母／數字人名：師父會一個字母一個字母拼出來（`moonlight` = M-o-o-n-l-i-g-h-t
            # 佔 6 秒），**音檔裡找不到整串**，內容探針會整個滑到拼完之後（`03-19 #31`
            # 被從 1424.10 推到 1431.05，正好跳過整個人名）。這種段現值就是對的，不動。
            latin += 1

        per = {}
        for dec in ('opus', 'mp3'):
            ch = (c.get(dec) or {}).get('chars')
            if not ch:
                continue
            nsc, non = find_block(ch, ''.join(name_probe), 2) if name_probe else (0, None)
            tsc, ton = find_block(ch, text_full) if text_full else (0, None)
            per[dec] = ((nsc, non), (tsc, ton))

        if not per:
            unknown.append(f'{sid}|{label}'); continue
        n_ons = [per[d][0][1] for d in per if per[d][0][1] is not None
                 and per[d][0][0] >= args.name_score]
        t_ons = [per[d][1][1] for d in per if per[d][1][1] is not None
                 and per[d][1][0] >= args.text_run]
        if not n_ons and not t_ons:
            unknown.append(f'{sid}|{label}'); continue
        name = min(n_ons) if n_ons else None
        text = min(t_ons) if t_ons else None
        if len({round(x, 2) for x in n_ons + t_ons}) > 1:
            xdec += 1
        if name is None:
            new, why = text, 'text'
        elif text is None:
            new, why = name, 'name'
        elif name <= text:
            new, why = name, 'name'
        else:
            # 人名比內容晚 >3s → 多半誤命中
            new, why = (text, 'text') if name - text > 3.0 else (name, 'name')
        # SKILL §1.3：`start` 最早只容許比首字早 1.5s。窗的最前 4 秒是**上一段的尾巴**，
        # 區塊對齊很容易在那裡命中一段 ≥min_run 的雷同句（「這個就是…」）而把錨點
        # 拉到 start−3～4s（實測 470 筆全部落在 −3.49s，就是窗邊界）。
        # → 直接濾掉早於 `start − --max-early` 的候選。
        if new < st - args.max_early:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        if abs(new - st) >= args.min_shift:
            ov[f'{sid}|{label}'] = round(new, 2)
            src[f'{sid}|{label}'] = why

    json.dump(ov, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    srcs = {s: sum(1 for v in src.values() if v == s) for s in ('name', 'text')}
    print(f'邊界 {len(cur)}｜可定案 {len(ov)}（人名 {srcs["name"]} / 內容 {srcs["text"]}）'
          f'｜雙解碼器不一致 {xdec}｜定位不到 {len(unknown)}'
          f'｜早於 start−{args.max_early}s 而丟棄 {sum(dropped.values())}'
          f'｜字母人名跳過 {latin}')
    print('→', args.out)
    if unknown:
        print('定位不到:', ' '.join(unknown[:40]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())