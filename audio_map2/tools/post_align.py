#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""對齊後的收尾：修過期 notes、標註已驗證的時間、重算 `stats`、結構校驗。

做四件事（都只動 `notes`／`confidence`／`status`／`stats`，不碰文字與時間）：
1. **過期 notes**：`2024-12-11-wechat #6` 的舊註記寫「answer_text 空；音檔未讀此段」，
   但該段其實有完整 `answer_text` 與章節對應，且整場字級轉錄確認內文確實落在窗內
   （首 301.39／中 365.37／後 424.50 全在 [297.79, 448.95]）。依 2025-01-15 教訓
   「notes 可能是過期的，別照抄」改成實際情況，`conf 0.0 → 0.85`、`status auto → manual`。
2. **`html-resplit … 待人工確認`** 這是**電子書分段邊界**問題、不是時間問題；時間已逐段
   用雙解碼器字級 onset 驗過，因此在 notes 補上「時間已驗證」但**保留**該標記
   （`stats.pending` 不變，與 2025-01-15 收尾同款處理）。
3. **重算 `stats`**（口徑同 `finalize.py` 的 `recompute_stats`）。
4. **結構校驗**：鏈完整、無 overlap／倒序、open/close 齊全、null 段 label 為空字串。

用法:
    .venv/bin/python post_align.py --month 2024-12 [--inplace] [--verify-text <backup>]
"""
import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# 過期／不實的 notes 修訂：(session_id, '#index') -> (新 notes, confidence, status)
STALE = {
    ('2024-12-11-wechat', '#6'): (
        '原註記「answer_text 空；音檔未讀此段（Celine 藏传答在 #7）」已過期：'
        '本段有完整 answer_text 與章節對應，且整場字級轉錄確認內文確在窗內'
        '（首 301.39／中 365.37／後 424.50 全落在 [297.79, 448.95]）；'
        'Celine 由音檔逐字母拼出（C 297.81 / R / L / I / N），時間已用雙解碼器字級 onset 驗證',
        0.85, 'manual'),
}

VERIFY_NOTE = '時間已驗證（opus+mp3 雙解碼器 12s 短窗字級 onset ＋ 整場轉錄內容定位）'

# 需要寫清楚「這個 block 的文字實際上不在檔尾」的情況（不是過期、但同樣要記錄）。
# `2024-11-11-main` 的 closing：Word 把**整段微信問答**放進了收場 block
# （「贴吧的问题到这里结束了…1、还有想问下在监狱的环境…」），而音檔把它念在
# **檔案中段 2237–2388**（貼吧→微信的分界），檔尾 6310 念的是「祝大家晚安吧」。
# 依 SKILL §1.3 收場 start 必須等於末段 end（＝檔尾），所以時間只能留在檔尾；
# 要真正對上必須重分段（`resplit_by_html.py` 的領域，本次只動時間故不處理）。
STRUCT_NOTE = {
    ('2024-11-11-main', 'closing'): (
        '⚠️ 本 block 的 Word 文字不是檔尾收場：它是**檔案中段 2237–2388 的「貼吧→微信」'
        '分界＋整段微信問答**（「贴吧的问题到这里结束了…1、还有想问下在监狱的环境…」），'
        '音檔檔尾 6307–6311 念的是「回答了哈了啊…祝大家晚安吧」。依 SKILL §1.3 收場 '
        'start 必須等於末段 end（＝6311.585），故時間只能留在檔尾；要真正對上需'
        '重分段（resplit_by_html.py），本次僅動時間、未處理',
        None, None),
}


def recompute_stats(d):
    st = {'sessions': 0, 'segments': 0, 'matched': 0, 'low_conf': 0, 'interpolated': 0,
          'pending': 0, 'missing': 0, 'openings_ok': 0, 'closings_ok': 0}
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
                if ('no-anchor:clamped' in (seg.get('notes') or '')
                        or '待人工' in (seg.get('notes') or '')):
                    st['pending'] += 1
        if s.get('opening') and s['opening'].get('start') is not None:
            st['openings_ok'] += 1
        if s.get('closing') and s['closing'].get('start') is not None:
            st['closings_ok'] += 1
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--inplace', action='store_true')
    ap.add_argument('--verify-text', default='')
    args = ap.parse_args()

    p = REPO / 'audio_map2' / f'{args.month}.json'
    d = json.load(open(p, encoding='utf-8'))

    for s in d['sessions']:
        sid = s['session_id']
        for g in s['segments']:
            # null（音檔未讀／空答案）段**不得殘留 label**——審核 UI 會顯示不存在的時間
            # （2025-01-18 複驗清掉的 #24 就是這樣；2024-11 實測 3 段殘留）。
            if g.get('start') is None and (g.get('start_label') or g.get('end_label')):
                g['start_label'] = ''
                g['end_label'] = ''
                print(f'  清掉 null 段殘留 label: {sid} #{g["index"]}')
            key = (sid, f"#{g['index']}")
            if key in STRUCT_NOTE:
                note, conf, status = STRUCT_NOTE[key]
                g['notes'] = (g.get('notes') or '') + (' | ' if g.get('notes') else '') + note
                if conf is not None:
                    g['confidence'], g['status'] = conf, status
                print(f'  註記結構性說明: {sid} #{g["index"]}')
            if key in STALE:
                note, conf, status = STALE[key]
                g['notes'] = note
                g['confidence'] = conf
                g['status'] = status
                print(f'  修訂過期 notes: {sid} #{g["index"]}  conf→{conf} status→{status}')
            elif '待人工確認' in (g.get('notes') or '') and VERIFY_NOTE not in g['notes']:
                # 保留「待人工確認」（分段邊界問題），但標明時間已驗證
                g['notes'] += ' | ' + VERIFY_NOTE
                print(f'  標註時間已驗證（保留待人工確認）: {sid} #{g["index"]}')

    # 結構校驗
    issues = 0
    for s in d['sessions']:
        seq = [('opening', s['opening'])] + \
              [(f"#{g['index']}", g) for g in s['segments']] + [('closing', s['closing'])]
        real = [(l, g) for l, g in seq if g.get('start') is not None]
        for i in range(len(real) - 1):
            a, b = real[i][1], real[i + 1][1]
            if a.get('end') is not None and abs(a['end'] - b['start']) > 0.0015:
                issues += 1
                print(f"  ✗ 鏈斷 {s['session_id']} {real[i][0]}.end={a['end']} "
                      f"vs {real[i+1][0]}.start={b['start']}")
        for l, g in seq:
            if g.get('start') is not None and g.get('end') is not None \
                    and g['end'] < g['start'] and not g.get('zero'):
                issues += 1
                print(f"  ✗ 倒序 {s['session_id']} {l}")
        for g in s['segments']:
            if g.get('start') is None and (g.get('start_label') or g.get('end_label')):
                issues += 1
                print(f"  ✗ null 段殘留 label {s['session_id']} #{g['index']}")
        if not s.get('opening') or s['opening'].get('start') is None:
            issues += 1
            print(f"  ✗ 無 opening {s['session_id']}")
        if not s.get('closing') or s['closing'].get('start') is None:
            issues += 1
            print(f"  ✗ 無 closing {s['session_id']}")

    for s in d['sessions']:
        sid = s['session_id']
        for label in ('closing', 'opening'):
            if (sid, label) in STRUCT_NOTE:
                note, conf, status = STRUCT_NOTE[(sid, label)]
                b = s[label]
                cur = b.get('notes') or ''
                if note[:24] not in cur:
                    b['notes'] = cur + (' | ' if cur else '') + note
                if conf is not None:
                    b['confidence'], b['status'] = conf, status
                print(f'  註記結構性說明: {sid} {label}')

    d['stats'] = recompute_stats(d)
    print(f'\n結構 issues: {issues}')
    print('stats:', json.dumps(d['stats'], ensure_ascii=False))

    out = p if args.inplace else Path(str(p) + '.post')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    print('→', out)
    return 0 if issues == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
