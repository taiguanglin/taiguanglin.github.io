#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批次字級錨點量測（opus＋mp3 雙解碼器 FunASR），一次跑完整個月份。

為什麼需要它：`first_char_audit.py` 只驗「第一詞所在 **cue** 是否與 `start` 重疊」，
**不驗 `start` 落在哪個 cue**——2025-01-17 有 31/31 個 `start` 全錯卻全報 `OK`。
本腳本對每個邊界（`opening`／每段／`closing`）切 `[start-4, start+8]` 的 12s 短窗
（SKILL §3 唯一可信絕對時間的窗寬），跑雙解碼器取字級 onset，落盤成 JSON 快取。

絕對時間**只信雙解碼器一致**；不一致（|Δopus−Δmp3| > 0.15s）標 `XDEC` 交人工判讀。

用法（需 funasr 環境，見 SKILL.md §3）:
    cd tool/sense_voice && .venv/bin/python \\
        ../../../audio_map2/tools/batch_anchor.py --month 2024-12

輸出（--out，預設 /tmp/am2_<month>）:
    <sid>__<label>.json   每個邊界一檔，含 opus/mp3 字級時間軸（global 秒）
可重複執行：已存在的快取會跳過（模型載入仍會發生，約 40s）。
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'audio_map2' / 'tools'))

from first_char_audit import first_word  # noqa: E402

PUNCT = set('。！？!?，、；,;:…—～ ')


def part_of(session, t_global):
    """回傳 (part_index, offset)；global 時間落在哪一個分檔。"""
    off = 0.0
    for i, p in enumerate(session.get('media_parts') or []):
        dur = float(p.get('duration_est') or 0.0)
        if t_global < off + dur or i == len(session['media_parts']) - 1:
            return i, off
        off += dur
    return 0, 0.0


def decode_window(path, t0, dur):
    """回傳 16k mono wav bytes；失敗回 None。"""
    try:
        r = subprocess.run(
            ['ffmpeg', '-v', 'error', '-ss', f'{t0:.3f}', '-t', f'{dur:.3f}', '-i', path,
             '-f', 'wav', '-ar', '16000', '-ac', '1', '-'],
            capture_output=True, check=True)
        return r.stdout if r.stdout else None
    except Exception:                                                  # noqa: BLE001
        return None


def chars_from_model(model, raw, t_base):
    """wav bytes → [[global_sec, char], ...]（略去標點／空白）。"""
    res = model.generate(input=raw, cache={}, batch_size_s=60, sentence_timestamp=True)
    item = res[0]
    text = (item.get('text') or '').strip()
    ts = item.get('timestamp') or []
    out, ti = [], 0
    for ch in text:
        if ch.isspace() or ch in PUNCT:
            continue
        if ti < len(ts):
            out.append((round(t_base + ts[ti][0] / 1000.0, 2), ch))
            ti += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--month', required=True)
    ap.add_argument('--date', default='', help='只跑某一天（可重複，用逗號分隔）')
    ap.add_argument('--source', default='', help='贴吧 / 微信公众号')
    ap.add_argument('--before', type=float, default=4.0)
    ap.add_argument('--after', type=float, default=8.0)
    ap.add_argument('--out', default='')
    args = ap.parse_args()

    outdir = Path(args.out or f'/tmp/am2_{args.month}')
    outdir.mkdir(parents=True, exist_ok=True)
    win = args.before + args.after

    data = json.load(open(REPO / 'audio_map2' / f'{args.month}.json'))
    dates = {d for d in args.date.split(',') if d}
    sessions = [s for s in data['sessions']
                if (not dates or s.get('date') in dates)
                and (not args.source or s.get('source') == args.source)]

    jobs = []                                        # (sid, label, global_start, text)
    for s in sessions:
        # 有些月份整段沒有該 block（`closing: null`／`opening: null`，共 18 個 session
        # 散在 2024-06/08/09、2025-02/03）——這些 session 就少一���邊界。
        bounds = []
        if s.get('opening'):
            bounds.append(('opening', s['opening'], s['opening'].get('text') or ''))
        for g in s['segments']:
            bounds.append((f"#{g['index']}", g, g.get('answer_text') or ''))
        if s.get('closing'):
            bounds.append(('closing', s['closing'], s['closing'].get('text') or ''))
        for label, g, txt in bounds:
            st = g.get('start')
            if st is None:
                continue
            jobs.append((s['session_id'], label, float(st), txt))

    todo = [j for j in jobs
            if not (outdir / f"{j[0]}__{j[1].lstrip('#') or 'opening'}.json").exists()]
    print(f'[batch_anchor] month={args.month} sessions={len(sessions)} 邊界={len(jobs)} '
          f'待跑={len(todo)}（已快取 {len(jobs) - len(todo)}）', flush=True)
    if not todo:
        return 0

    from funasr import AutoModel
    model = AutoModel(model='paraformer-zh', vad_model='fsmn-vad',
                      vad_kwargs={'max_single_segment_time': 30000},
                      device='cpu', disable_update=True,
                      punc_model='iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch')

    by_sid = {s['session_id']: s for s in sessions}
    done = 0
    for sid, label, st, txt in todo:
        s = by_sid[sid]
        pi, off = part_of(s, st)
        part = s['media_parts'][pi]
        local = st - off
        rec = {
            'session_id': sid, 'label': label, 'start': round(st, 3),
            'part': pi, 'local_start': round(local, 3), 'window': [local - args.before, local + args.after],
            'first_word': first_word(txt), 'answer_head': txt[:40].replace('\n', ' '),
        }
        for tag, key in (('opus', 'opus_path'), ('mp3', 'mp3_path')):
            path = part.get(key)
            if not path or not os.path.exists(path):
                rec[tag] = {'error': 'missing file', 'path': path}
                continue
            # 視窗起點夾在 0：ffmpeg 的 `-ss` 給負值會被當 0，時間戳就會整段錯位
            # （2024-12-12/13/14 的開場因此算出負數 start）。往前不足就把窗往後延，
            # 確保 [start, start+after] 仍然完整覆蓋。
            t0 = max(0.0, st - args.before - off)
            dur = max(win, (st + args.after) - off - t0)
            t_base = off + t0                      # global 時刻
            raw = decode_window(path, t0, dur)
            if raw is None:
                rec[tag] = {'error': 'ffmpeg failed', 'path': path}
                continue
            try:
                # t_base 用 **global** 時刻：分檔的 offset 必須加回來，否則 part-1 的邊界
                # 會全部記成本地時間（2024-12-09-wechat 上下檔就踩過這個坑）。
                cs = chars_from_model(model, raw, t_base)
            except Exception as e:                                      # noqa: BLE001
                rec[tag] = {'error': f'{type(e).__name__}: {e}', 'path': path}
                continue
            rec[tag] = {'path': path, 'chars': cs, 't_base_global': round(t_base, 3)}
        fn = outdir / f"{sid}__{label.lstrip('#') or 'opening'}.json"
        tmp = fn.with_suffix('.tmp')
        tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(tmp, fn)
        done += 1
        if done % 25 == 0 or done == len(todo):
            print(f'  [{done}/{len(todo)}] {sid} {label}', flush=True)
    print(f'[batch_anchor] done -> {outdir}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
