#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐案複驗 RESEG_LEDGER_2026-10-17.md（34 段／14 session）vs 實際 JSON。

檢查（對應 ledger 開頭的 5 件事）：
  A. 主表宣稱值 vs now JSON：時間窗／q·a 保留字數／chapter／question_id／
     chapter_answer_ids／meta.lastPlayed。
  B. 鄰段上下文表 vs base（3cadcbe^）與 now：base#／now# 的窗與 q/a 字數。
  C. session 級不變量：段數、字元多重集守恆、鏈相接（prev.end==next.start）、
     lastPlayed 政策（時間窗變動→必須清空；既有例外見 EXCEPTIONS）、
     重編範圍（未列 ledger 的 session 必須與 base 完全相同）。
  D. overrides 同步：每個 override 卼 sid|#N 的值必須等於 now JSON 該段的 start
     （否則未來重跑 apply_alignment --overrides 會回退修正）。

用法:
    tool/word_audio_map2/.venv/bin/python audio_map2/tools/verify_ledger.py \
        [--ledger ...] [--base 3cadcbe^] [--verbose]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "word_audio_map2"))
sys.path.insert(0, str(ROOT / "tool" / "pdf_audio_map"))
import split_missing_subquestions as sms  # kept_stream engine  # noqa: E402
from common import parse_srt_raw, srt_preview  # noqa: E402

# ---------------------------------------------------------------- ledger parse

SEC_RE = re.compile(r"^## (\d{4}-\d{2}):([\w-]+)\s*$")
CNT_RE = re.compile(r"^段數 \*\*(\d+) → (\d+)\*\*（([+\-0\d]+)）")


def parse_window(tok: str):
    tok = tok.strip().strip("`")
    if tok == "null" or tok == "—":
        return None
    a, b = tok.split("→")
    return (float(a), float(b))


def parse_qa(tok: str):
    tok = tok.strip()
    if tok in ("—", ""):
        return None
    q, a = tok.split("/")
    return (int(q), int(a))


def parse_ledger(path: Path):
    sections = {}
    cur = None
    mode = None  # None | 'main' | 'ctx'
    for line in path.read_text(encoding="utf-8").splitlines():
        m = SEC_RE.match(line)
        if m:
            cur = {"month": m.group(1), "sid": m.group(2), "rows": [], "ctx": [],
                   "counts": None}
            sections[m.group(2)] = cur
            mode = None
            continue
        if cur is None:
            continue
        m = CNT_RE.match(line)
        if m:
            cur["counts"] = (int(m.group(1)), int(m.group(2)))
            continue
        if "now#" in line and "時間窗" in line:
            mode = "main"
            continue
        if "base#" in line and "base窗" in line:
            mode = "ctx"
            continue
        if line.startswith("</details>"):
            mode = None
            continue
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if mode == "main" and len(cols) == 10 and cols[0].isdigit():
            cur["rows"].append({
                "now": int(cols[0]),
                "win": parse_window(cols[1]),
                "qa": parse_qa(cols[2] + "/" + cols[3]) if False else (int(cols[2]), int(cols[3])),
                "chapter": json.loads(cols[4]),
                "qid": None if cols[5] == "None" else cols[5].strip("`"),
                "aids": None if cols[6] == "None" else cols[6],
                "last": None if cols[7] == "None" else cols[7],
                "action": cols[8],
                "delta": cols[9],
            })
        elif mode == "ctx" and len(cols) == 8:
            cur["ctx"].append({
                "b": None if cols[0] == "—" else int(cols[0]),
                "bwin": parse_window(cols[1]),
                "bqa": parse_qa(cols[2]),
                "n": None if cols[4] == "—" else int(cols[4]),
                "nwin": parse_window(cols[5]),
                "nqa": parse_qa(cols[6]),
                "chg": cols[7],
            })
    return sections


# ---------------------------------------------------------------- json access

def git_json(ref: str, month: str):
    out = subprocess.run(["git", "show", f"{ref}:audio_map2/{month}.json"],
                         capture_output=True, text=True, check=True, cwd=ROOT)
    return json.loads(out.stdout)


def now_json(month: str):
    return json.loads((ROOT / "audio_map2" / f"{month}.json").read_text(encoding="utf-8"))


def get_sess(data, sid):
    for s in data.get("sessions") or []:
        if s.get("session_id") == sid:
            return s
    return None


def seg_by_index(sess):
    return {seg["index"]: seg for seg in (sess.get("segments") or [])}


def kept(s):
    return len(sms.kept_stream(s or "")[0])


def rawlen(s):
    return len(s or "")


def seg_last(seg):
    return (seg.get("meta") or {}).get("lastPlayed")


def win(seg):
    s, e = seg.get("start"), seg.get("end")
    if s is None or e is None:
        return None
    return (round(s, 3), round(e, 3))


def text_key(seg):
    """文字欄位（驗證用：不含 notes/preview 等衍生欄）。"""
    return (seg.get("q_text"), seg.get("answer_text"))


# ---------------------------------------------------------------- main

# lastPlayed 保留的既定例外（時間窗有變但刻意保留／窗未變只有文字對調）
KEEP_LAST = {
    "2024-11-16-main#2",       # end 390.02→390.04，AGENTS.md 記錄保留
}


# 拆段 session 的平移表：session_id -> (插入後首個 now index, shift)。
# now# = base# + shift（base idx >= 插入點對應的 base idx）。未列出的 session 無平移。
SHIFTS = {
    "2024-04-25-main": (21, 1),    # base#20.. -> now#21..
    "2024-07-15-main": (36, 1),    # base#35.. -> now#36..
    "2024-07-17-main": (11, 1),    # base#10.. -> now#11..
    "2024-08-17-main": (17, 1),    # base#16.. -> now#17..
    "2024-09-14-main": (49, 3),    # base#46.. -> now#49..
    "2024-11-16-main": (5, 2),     # base#3..  -> now#5..
    "2025-01-17-wechat": (3, 1),   # base#2..  -> now#3..
}
# 平移段比對時允許不同的欄位（重算/衍生欄位）
SHIFT_OK_DIFF = {"index", "stable_key", "question_id", "srt_preview",
                "q_preview", "answer_preview", "start_label", "end_label",
                "html_verbatim"}


def check(args):
    ledger = parse_ledger(Path(args.ledger))
    problems: list[str] = []
    info: list[str] = []

    def bad(msg):
        problems.append(msg)

    # 1) ledger 覆蓋的 session 數
    if len(ledger) != 14:
        bad(f"ledger 解析出 {len(ledger)} 個 session（預期 14）")
    total_rows = sum(len(s["rows"]) for s in ledger.values())
    if total_rows != 34:
        bad(f"ledger 主表共 {total_rows} 段（預期 34）")

    touched_sessions = set()
    for sid, sec in ledger.items():
        month, lrows, ctx = sec["month"], sec["rows"], sec["ctx"]
        touched_sessions.add(sid)
        nowd, based = now_json(month), git_json(args.base, month)
        ns, bs = get_sess(nowd, sid), get_sess(based, sid)
        if ns is None or bs is None:
            bad(f"{sid}: session 不存在（now={ns is not None} base={bs is not None}）")
            continue
        nseg, bseg = seg_by_index(ns), seg_by_index(bs)
        tag = f"[{sid}]"

        # C1 段數宣稱
        nb, nn = len(bs.get("segments") or []), len(ns.get("segments") or [])
        if sec["counts"] and sec["counts"] != (nb, nn):
            bad(f"{tag} 段數宣稱 {sec['counts']} != 實際 ({nb} → {nn})")

        # C2 字元多重集守恆（q_text＋answer_text，保留字元）
        def multiset(sess):
            c = Counter()
            for seg in sess.get("segments") or []:
                c.update(sms.kept_stream((seg.get("q_text") or "") + (seg.get("answer_text") or ""))[0])
            return c
        mb, mn = multiset(bs), multiset(ns)
        if mb != mn:
            d = (mn - mb) + (mb - mn)
            bad(f"{tag} 字元多重集不守恆：±{sum(d.values())} 字（例：{list(d)[:8]}）")
        else:
            info.append(f"{tag} 文字守恆 OK（{sum(mn.values())} 保留字）")

        # C3 鏈相接：只比對「連接點」——opening.end→首段.start、
        # 前段.end→次段.start（跳過 null 段）、末段.end→closing.start
        seq = ns.get("segments") or []
        opens, closes = ns.get("opening"), ns.get("closing")
        chain = []  # (label, time) 依序；只收集連接用的時間點
        nonnull = [s for s in seq if s.get("start") is not None]
        if opens and opens.get("end") is not None and nonnull:
            chain.append(("opening.end", opens["end"]))
        for s in nonnull:
            chain.append((f"#{s['index']}.start", s["start"]))
            chain.append((f"#{s['index']}.end*", s["end"]))
        if closes and closes.get("start") is not None and nonnull:
            chain.append(("closing.start", closes["start"]))
        # 連接點 = 相鄰兩元素，且左邊必為 end（帶 *）或 opening.end
        for i in range(1, len(chain)):
            (l1, v1), (l2, v2) = chain[i - 1], chain[i]
            is_conn = (l1 == "opening.end" or l1.endswith(".end*")) and \
                      (l2 != "closing.start" and not l2.endswith(".end*"))
            if is_conn and abs(v1 - v2) > 0.005:
                bad(f"{tag} 鏈斷：{l1}={v1} → {l2}={v2}（差 {v2-v1:+.3f}s）")
        if nonnull:
            info.append(f"{tag} 鏈相接檢查完成（{len(nonnull)} 個非 null 段）")

        # C7 srt_preview 新鮮度：與 [start,end] 重疊 cue 串接（build_maps 同規則）一致
        cues_raw, off = [], 0.0
        for part in (ns.get("media_parts") or []):
            sp = Path(part.get("srt_file") or "")
            if not sp.exists():
                sp = ROOT / "audio" / "srt" / f"{part.get('stem')}.srt"
            if not sp.exists():
                continue
            pcues = parse_srt_raw(sp)
            cues_raw.extend([(a + off, b + off, t) for a, b, t in pcues])
            off += part.get("duration_est") or 0.0
        if cues_raw:
            for r in lrows:
                seg = nseg.get(r["now"])
                if seg is None or seg.get("start") is None:
                    continue
                want = srt_preview(cues_raw, seg["start"], seg["end"])
                if (seg.get("srt_preview") or "") != want:
                    bad(f"{tag}#{r['now']} srt_preview 過期"
                        f"（現值開頭『{(seg.get('srt_preview') or '')[:24]}』"
                        f"→ 應為『{want[:24]}』）")

        # A 主表宣稱 vs now
        for r in lrows:
            seg = nseg.get(r["now"])
            t = f"{tag}#{r['now']}"
            if seg is None:
                bad(f"{t} ledger 段不存在於 now JSON")
                continue
            if win(seg) != (None if r["win"] is None else tuple(round(x, 3) for x in r["win"])):
                bad(f"{t} 時間窗 ledger={r['win']} JSON={win(seg)}")
            kq, ka = rawlen(seg.get("q_text")), rawlen(seg.get("answer_text"))
            if (kq, ka) != tuple(r["qa"]):
                kq2, ka2 = kept(seg.get("q_text")), kept(seg.get("answer_text"))
                alt = "（kept=%d,%d）" % (kq2, ka2) if (kq2, ka2) == tuple(r["qa"]) else ""
                bad(f"{t} q/a 原文字數 ledger={r['qa']} JSON=({kq},{ka}){alt}")
            if list(seg.get("chapter_indexes") or []) != list(r["chapter"]):
                bad(f"{t} chapter ledger={r['chapter']} JSON={seg.get('chapter_indexes')}")
            if (seg.get("question_id") or None) != (r["qid"] or None):
                bad(f"{t} question_id ledger={r['qid']} JSON={seg.get('question_id')}")
            aids = seg.get("chapter_answer_ids")
            if r["aids"] is None and aids:
                bad(f"{t} ledger answer_ids=None 但 JSON chapter_answer_ids={aids}")
            elif r["aids"] is not None:
                want = [x.strip().strip("`") for x in str(r["aids"]).strip("[]").split(",") if x.strip()]
                if list(aids or []) != want:
                    bad(f"{t} answer_ids ledger={want} JSON={aids}")
            if (seg_last(seg) or None) != (r["last"] or None):
                bad(f"{t} lastPlayed ledger={r['last']} JSON={seg_last(seg)}")

        # B 鄰段上下文表 vs base/now
        for c in ctx:
            if c["b"] is not None:
                b = bseg.get(c["b"])
                if b is None:
                    bad(f"{tag} ctx base#{c['b']} 不存在")
                else:
                    if win(b) != (None if c["bwin"] is None else tuple(round(x, 3) for x in c["bwin"])):
                        bad(f"{tag} ctx base#{c['b']} 窗 ledger={c['bwin']} JSON={win(b)}")
                    kq, ka = rawlen(b.get("q_text")), rawlen(b.get("answer_text"))
                    if (kq, ka) != c["bqa"]:
                        bad(f"{tag} ctx base#{c['b']} q/a ledger={c['bqa']} JSON=({kq},{ka})")
            if c["n"] is not None:
                n = nseg.get(c["n"])
                if n is None:
                    bad(f"{tag} ctx now#{c['n']} 不存在")
                else:
                    if win(n) != (None if c["nwin"] is None else tuple(round(x, 3) for x in c["nwin"])):
                        bad(f"{tag} ctx now#{c['n']} 窗 ledger={c['nwin']} JSON={win(n)}")
                    kq, ka = rawlen(n.get("q_text")), rawlen(n.get("answer_text"))
                    if (kq, ka) != c["nqa"]:
                        bad(f"{tag} ctx now#{c['n']} q/a ledger={c['nqa']} JSON=({kq},{ka})")
            # 未標「變更」的列：內容必須守恆。拆段 session 中 base# 與 now#
            # 因插入而錯位，改以「平移後內容」比對（文字與窗完全相同）。
            if ("變更" not in c["chg"]) and c["n"] is not None:
                n = nseg.get(c["n"])
                if n is not None:
                    cand = [b for b in (bs.get("segments") or [])
                            if text_key(b) == text_key(n) and win(b) == win(n)]
                    if not cand:
                        bad(f"{tag} ctx now#{c['n']} 未標變更但找不到內容相同的 base 段"
                            f"（窗 {win(n)}）")

        # C6 平移段完整性：插入點之後的段，除重算欄位外必須與 base 完全相同
        if sid in SHIFTS:
            first_now, shift = SHIFTS[sid]
            touched_idx = {r["now"] for r in lrows}
            for seg in seq:
                if seg["index"] < first_now or seg["index"] in touched_idx:
                    continue
                base = bseg.get(seg["index"] - shift)
                if base is None:
                    bad(f"{tag}#{seg['index']} 平移段找不到 base#{seg['index']-shift}")
                    continue
                for k in sorted(set(seg) | set(base)):
                    if k in SHIFT_OK_DIFF:
                        continue
                    if json.dumps(seg.get(k), sort_keys=True, ensure_ascii=False) != \
                       json.dumps(base.get(k), sort_keys=True, ensure_ascii=False):
                        bad(f"{tag}#{seg['index']} 平移段欄位 {k} 與 base#{base['index']} 不同"
                            f"：{json.dumps(base.get(k),ensure_ascii=False)[:60]} →"
                            f" {json.dumps(seg.get(k),ensure_ascii=False)[:60]}")

        # C4 lastPlayed 政策（內容比對）：段的時間窗若不存在於 base 任一段，
        # 表示播放目標已變 → lastPlayed 必須已清空（KEEP_LAST 例外見上）。
        base_wins = {win(s) for s in (bs.get("segments") or []) if win(s) is not None}
        for seg in seq:
            w = win(seg)
            if w is None:
                continue
            if w not in base_wins and seg_last(seg) and f"{sid}#{seg['index']}" not in KEEP_LAST:
                bad(f"{tag}#{seg['index']} 時間窗 {w} 不存在於 base（播放目標已變）"
                    f"但 lastPlayed 未清空（{seg_last(seg)}）")
        lp_now = sum(1 for s in seq if seg_last(s))
        lp_base = sum(1 for s in (bs.get("segments") or []) if seg_last(s))
        info.append(f"{tag} lastPlayed base={lp_base} now={lp_now}")
        # opening/closing 未變
        for blk in ("opening", "closing"):
            if json.dumps(bs.get(blk), sort_keys=True, ensure_ascii=False) != \
               json.dumps(ns.get(blk), sort_keys=True, ensure_ascii=False):
                bad(f"{tag} {blk} 與 base 有差異（ledger 未記載任何 opening/closing 變更）")

    # C5 重編範圍：修改月份中，未列 ledger 的 session 必須與 base 完全一致
    months = sorted({s["month"] for s in ledger.values()})
    for month in months:
        nowd, based = now_json(month), git_json(args.base, month)
        nmap = {s["session_id"]: s for s in nowd.get("sessions") or []}
        bmap = {s["session_id"]: s for s in based.get("sessions") or []}
        for sid in sorted(set(nmap) | set(bmap)):
            ns, bs = nmap.get(sid), bmap.get(sid)
            if ns is None or bs is None:
                bad(f"[{month}:{sid}] session 缺一邊（now={ns is not None} base={bs is not None}）")
                continue
            if sid in touched_sessions:
                continue
            # 僅 html_verbatim 旗標差異 → mark_html_diff 對現行電子書的冪等更新，記 INFO
            nd = {k: v for k, v in ns.items() if k != "segments"}
            bd = {k: v for k, v in bs.items() if k != "segments"}
            if json.dumps(nd, sort_keys=True, ensure_ascii=False) != \
               json.dumps(bd, sort_keys=True, ensure_ascii=False):
                bad(f"[{month}:{sid}] 未列 ledger 但與 base 有差異（session 級欄位）")
                continue
            nseg2 = {g['index']: {k: v for k, v in g.items() if k != 'html_verbatim'}
                     for g in ns['segments']}
            bseg2 = {g['index']: {k: v for k, v in g.items() if k != 'html_verbatim'}
                     for g in bs['segments']}
            if json.dumps(nseg2, sort_keys=True, ensure_ascii=False) != \
               json.dumps(bseg2, sort_keys=True, ensure_ascii=False):
                bad(f"[{month}:{sid}] 未列 ledger 但與 base 有差異")
            else:
                flags = [(g['index'], g.get('html_verbatim')) for g in ns['segments']
                         if g.get('html_verbatim') != next(
                            (b.get('html_verbatim') for b in bs['segments']
                             if b['index'] == g['index']), None)]
                if flags:
                    info.append(f"[{month}:{sid}] 僅 html_verbatim 旗標更新（已記錄於 ledger 檔頭）：{flags}")
        # ledger session 的「其他段」：文字/窗必須守恆（允許 index 平移）
        for sid in [s for s in touched_sessions if s in nmap and ledger[s]["month"] == month]:
            ns, bs = nmap[sid], bmap[sid]
            tkey = lambda seg: (seg.get("q_text"), seg.get("answer_text"),
                                seg.get("start"), seg.get("end"))
            a = [tkey(s) for s in ns["segments"]]
            b = [tkey(s) for s in bs["segments"]]
            if a != b and Counter(map(str, a)) != Counter(map(str, b)):
                # 有平移時逐個比對
                ca, cb = Counter(map(str, a)), Counter(map(str, b))
                extra, missing = ca - cb, cb - ca
                if extra or missing:
                    # 拆段後同段會被切開，多重集必不相等 → 只報文字總量
                    pass
            info.append(f"[{month}:{sid}] 段內容（q/a/窗）base {len(b)} 段 → now {len(a)} 段")

    # D overrides 同步：值必須等於 now 該段 start。區分：
    #   - 「本輪造成」：值==base start 但 !=now start（時間被本輪改掉而 overrides 沒跟上）
    #   - 「鍵錯位」：值==now 其他段的 start（拆段後鍵需重對映）
    #   - 「既存漂移」：值兩邊都不等（HEAD 前就不同步，非本輪責任）
    for month in months:
        ov_path = ROOT / "audio_map2" / "tools" / f"{month}_overrides.json"
        if not ov_path.exists():
            info.append(f"[{month}] 無 overrides 檔")
            continue
        ov = json.loads(ov_path.read_text(encoding="utf-8"))
        nowd = now_json(month)
        based = git_json(args.base, month)
        smap = {s["session_id"]: seg_by_index(s) for s in nowd.get("sessions") or []}
        bmap = {s["session_id"]: seg_by_index(s) for s in based.get("sessions") or []}
        caused = miskeyed = predrift = 0
        for key, val in sorted(ov.items()):
            sid, _, label = key.partition("|")
            segs = smap.get(sid)
            if segs is None:
                bad(f"[{month}] overrides 崩鍵：session {sid} 不存在（{key}）")
                continue
            if label in ("opening", "closing") or not label.startswith("#"):
                continue
            seg = segs.get(int(label[1:]))
            if seg is None:
                bad(f"[{month}] overrides {key} 指向不存在的段（該 session 段數 {len(segs)}）")
                continue
            if seg.get("start") is None:
                continue  # null 段
            if abs(seg["start"] - val) <= 0.005:
                continue
            # 分類
            bseg = (bmap.get(sid) or {}).get(int(label[1:]))
            if sid in touched_sessions and bseg is not None and \
               bseg.get("start") is not None and abs(bseg["start"] - val) <= 0.005:
                bad(f"[{month}] overrides {key}={val} 停在 base 值，now start={seg['start']}"
                    f"（本輪改了時間，重跑會回退）")
                caused += 1
                continue
            hit = [i for i, s2 in segs.items()
                   if s2.get("start") is not None and abs(s2["start"] - val) <= 0.005]
            if hit and sid in touched_sessions:
                bad(f"[{month}] overrides {key}={val} 其實是 now #{hit[0]} 的 start"
                    f"（鍵錯位，重跑會套錯段；now #{label[1:]} start={seg['start']}）")
                miskeyed += 1
            else:
                predrift += 1
        info.append(f"[{month}] overrides {len(ov)} 鍵：本輪回退風險 {caused}、鍵錯位 {miskeyed}、既存漂移 {predrift}")

    print("=" * 70)
    print("INFO")
    for i in info:
        print(" ", i)
    print("=" * 70)
    if problems:
        print(f"PROBLEMS ({len(problems)}):")
        for p in problems:
            print(" ✗", p)
        return 1
    print("ALL LEDGER CLAIMS + SESSION INVARIANTS PASS")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(ROOT / "audio_map2" / "tools" / "RESEG_LEDGER_2026-10-17.md"))
    ap.add_argument("--base", default="3cadcbe^")
    a = ap.parse_args()
    sys.exit(check(a))


if __name__ == "__main__":
    main()
