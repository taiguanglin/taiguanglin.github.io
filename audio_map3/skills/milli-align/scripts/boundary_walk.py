#!/usr/bin/env python3
"""boundary_walk.py — 邊界走查證據器（SKILL §5.1，L21 r3 walk.py 正典化）。

段號模式（默認全講）：
  V=tool/sense_voice/.venv/bin/python
  $V boundary_walk.py --series lengqie --lecture 22 --lo 40 --hi 44
  每段印：現值、TEXT、HEAD needle 候選（逐字 verb ／拼音 py＋覆蓋率）、
  PREV_TAIL 命中（前段末句逐字串＋末字 END）。

秒數模式（--raw；lo/hi 為整數秒）：
  $V boundary_walk.py --series lengqie --lecture 22 --raw --lo 1230 --hi 1265
  印字級原始流「字@start-end」10 字/行——邊界取值最終一律回到精確字元 END。

邊界值不用本腳本的行內插值，用：
  from seq_align import Stream, load_dump; st.t_end_of(q)  （見 SKILL §5.1 END 查詢）
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tool" / "jiangjing_para_map"))

from seq_align import Stream, load, head_candidates, score_at  # noqa: E402
from realign_dtw import norm_para  # noqa: E402

HEAD_BACK, HEAD_FWD = 15.0, 15.0   # 段頭候選窗（走查要寬——metric 的 ±3/+7 有窗盲點）
TAIL_BACK, TAIL_FWD = 18.0, 8.0   # 前段尾命中窗
HEAD_NEEDLE, TAIL_NEEDLE = 12, 10
CTX_PRE, CTX_POST = 8, 14


def q_window(st, t0, t1):
    """時間窗 → norm 位置範圍（跳過 nan）。"""
    lo = hi = None
    for q in range(len(st.norm)):
        t = st.t_of(q)
        if t is None:
            continue
        if lo is None and t >= t0:
            lo = q
        if t < t1:
            hi = q + 1
    if lo is None:
        return 0, 0
    return lo, (hi if hi else len(st.norm))


def fmt_slice(st, q0, q1):
    out = []
    for q in range(max(0, q0), min(len(st.norm), q1)):
        t = st.t_of(q)
        out.append(f"{st.norm[q]}@{t:.2f}" if t is not None else f"{st.norm[q]}@nan")
    return " ".join(out)


def pause_list(st, t0, t1, min_gap=0.25):
    """[t0,t1] 內 dump 字 END→下字 onset 的 ≥min_gap 間隙（停頓轉場制證據；洞區需 silencedetect 複驗）。"""
    out = []
    prev_q = None
    for q in range(len(st.norm)):
        t = st.t_of(q)
        if t is None or t < t0:
            continue
        if t > t1:
            break
        if prev_q is not None:
            e = st.t_end_of(prev_q)
            if e is not None and t - e >= min_gap:
                out.append((round(e, 2), round(t, 2), round(t - e, 2),
                            st.norm[max(0, prev_q - 3):prev_q + 1], st.norm[q:q + 4]))
        prev_q = q
    return out


def walk_boundary(lec, st, cmap, i):
    p = lec["paragraphs"][i]
    ps = lec["paragraphs"]
    prev = ps[i - 1] if i > 0 else None
    zero = p.get("zero")
    print("=" * 100)
    print(f"[{i}] cur_start={p['start']:.3f} cur_end={p['end']:.3f} "
          f"conf={p.get('conf')} zero={zero} "
          f"{'confirmed' if p.get('confirmed') else ''} "
          f"cls={cmap.get(p['pid'], '?')}")
    print(f"  TEXT: {p['text'][:72]}")
    norm = norm_para(p["text"])
    cur = p["start"]
    if not zero:
        print(f"  PAUSES(>=0.25s) in [{cur - 10:.1f},{cur + 2:.1f}]:")
        for e, t, g, pre, post in pause_list(st, cur - 10, cur + 2):
            print(f"    gap {e:8.2f}->{t:8.2f} ({g:.2f}s)  …{pre!r} | {post!r}…")
        q0, q1 = q_window(st, cur - HEAD_BACK, cur + HEAD_FWD)
        print(f"  HEAD(needle): {norm[:HEAD_NEEDLE]!r}  [win {cur - HEAD_BACK:.1f}~{cur + HEAD_FWD:.1f}]")
        cands = head_candidates(st, norm, q0, q1)
        shown = 0
        for q in sorted(cands):
            kind, base = cands[q]
            cov, qf, ql = score_at(st, norm, q)
            t = st.t_of(q)
            tag = "verb" if kind == "verb" else f"py{base:.2f}"
            print(f"    cand {t:9.2f} {tag:8s} cov={cov:.2f} "
                  f"ctx: {fmt_slice(st, q - CTX_PRE, q + CTX_POST)!r}")
            shown += 1
            if shown >= 4:
                break
        if not shown:
            print("    (no candidates)")
    if prev is not None:
        ptail = norm_para(prev["text"])[-TAIL_NEEDLE:]
        q0, q1 = q_window(st, cur - TAIL_BACK, cur + TAIL_FWD)
        print(f"  PREV_TAIL: {ptail!r}")
        hit = False
        q = st.norm.find(ptail, q0, q1)
        while q >= 0 and not hit:
            tend = None
            for k in range(q + len(ptail) - 1, q - 1, -1):
                tend = st.t_end_of(k)
                if tend is not None:
                    break
            print(f"    tailhit  {st.t_of(q):9.2f} .. end={tend}  "
                  f"ctx: {fmt_slice(st, q, min(q + len(ptail) + CTX_POST, len(st.norm)))!r}")
            hit = True
            q = st.norm.find(ptail, q + 1, q1)
        if not hit:
            print("    (no verbatim tail hit near cur)")
    print()


def walk_raw(st, lo, hi):
    for q in range(len(st.norm)):
        t, e = st.t_of(q), st.t_end_of(q)
        if t is None or not (lo <= t <= hi):
            continue
        print(f"{st.norm[q]}@{t:.2f}-{e:.2f}", end="  ")
        if (q + 1) % 10 == 0:
            print()
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True)
    ap.add_argument("--lecture", required=True)
    ap.add_argument("--lo", type=int, default=None,
                    help="段號模式=起始段（默認 0）；--raw 模式=起始秒")
    ap.add_argument("--hi", type=int, default=None,
                    help="段號模式=結束段（含，默認末段）；--raw 模式=結束秒")
    ap.add_argument("--raw", action="store_true", help="秒數模式：印字級原始流")
    a = ap.parse_args()
    lec, st, cmap = load(a.series, a.lecture)
    ps = lec["paragraphs"]
    if a.raw:
        walk_raw(st, a.lo or 0, a.hi if a.hi is not None else 10 ** 9)
        return
    lo = a.lo if a.lo is not None else 0
    hi = a.hi if a.hi is not None else len(ps) - 1
    for i in range(lo, hi + 1):
        walk_boundary(lec, st, cmap, i)


if __name__ == "__main__":
    main()
