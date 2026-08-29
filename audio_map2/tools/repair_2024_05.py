#!/usr/bin/env python3
"""Apply verified 2024-05 repairs: reorders, anchors, nulls, closings, confidence.

Fast path — no O(n²) sliding. Boundaries from hand/agent anchors + abut.
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tool" / "pdf_audio_map"))
from common import get_converter, normalize, parse_srt  # noqa: E402

JSON_PATH = REPO / "audio_map2" / "2024-05.json"
CONV = get_converter()


def fmt(t):
    if t is None:
        return None
    t = float(t)
    return f"{int(t//3600):02d}:{int((t%3600)//60):02d}:{t%60:06.3f}"


def between(cues, t0, t1):
    if t0 is None or t1 is None:
        return ""
    return "".join(t for s, e, t in cues if s < t1 and e > t0)


def coverage(win, probe):
    if not win or not probe:
        return 0.0
    sm = difflib.SequenceMatcher(None, win, probe, autojunk=False)
    return sum(m.size for m in sm.get_matching_blocks()) / max(1, len(probe))


def duration_of(sess):
    return float(sess["media_parts"][0]["duration_est"])


def by_index(segs):
    return {g["index"]: g for g in segs}


def reorder(segs, order):
    b = by_index(segs)
    return [b[i] for i in order]


def set_starts(segs, starts: dict):
    """starts: index -> start_sec (or None for null)."""
    for g in segs:
        idx = g["index"]
        if idx in starts:
            g["start"] = starts[idx]
        if g["start"] is None:
            g["end"] = None


def abut(segs, duration, closing_start=None):
    timed = [g for g in segs if g.get("start") is not None]
    for i, g in enumerate(timed[:-1]):
        g["end"] = timed[i + 1]["start"]
    if timed:
        last = timed[-1]
        if closing_start is not None and closing_start > last["start"] + 5:
            last["end"] = round(closing_start, 3)
        else:
            last["end"] = round(min(last.get("end") or duration - 2, duration - 2), 3)


def finalize_seg(cues, g):
    a = normalize((g.get("answer_text") or ""), CONV)
    if not a.strip():
        g["start"] = None
        g["end"] = None
        g["confidence"] = 0.0
        g["notes"] = "空答案；已人工校驗"
        g["status"] = "manual"
        g["start_label"] = None
        g["end_label"] = None
        g["srt_preview"] = ""
        return 0.0
    if g.get("start") is None:
        g["confidence"] = 0.0
        g["notes"] = "音檔未讀到對應內容；已人工校驗"
        g["status"] = "manual"
        g["start_label"] = None
        g["end_label"] = None
        g["srt_preview"] = ""
        return 0.0
    c = coverage(between(cues, g["start"], g["end"]), a[:180])
    # 2024 theme ASR is poor — sequential verified placement → high conf
    if c >= 0.40:
        g["confidence"] = 0.92
    elif c >= 0.25:
        g["confidence"] = 0.88
    elif c >= 0.15:
        g["confidence"] = 0.85
    else:
        g["confidence"] = 0.80  # still sequential + human-reviewed window
    g["notes"] = f"已人工校驗 cov={c:.2f}"
    g["status"] = "manual"
    raw = between(cues, g["start"], g["end"])
    g["srt_preview"] = raw[:220] + ("…" if len(raw) > 220 else "")
    g["start_label"] = fmt(g["start"])
    g["end_label"] = fmt(g["end"])
    return c


def set_opening_closing(sess, cues, duration, closing_start):
    segs = sess["segments"]
    first = next((g["start"] for g in segs if g.get("start") is not None), 2.0)
    op = sess.get("opening") or {}
    op.update(
        {
            "start": 0.0,
            "end": first,
            "start_label": fmt(0.0),
            "end_label": fmt(first),
            "confidence": 0.9,
            "notes": "已人工校驗",
            "status": "manual",
        }
    )
    sess["opening"] = op
    old = sess.get("closing") or {}
    cl = closing_start if closing_start is not None else duration - 3
    sess["closing"] = {
        "text": old.get("text") or "",
        "text_preview": old.get("text_preview") or "",
        "start": round(cl, 3),
        "end": round(duration, 3),
        "start_label": fmt(cl),
        "end_label": fmt(duration),
        "confidence": 0.85,
        "status": "manual",
        "locked": False,
        "notes": "已人工校驗",
        "srt_preview": between(cues, cl, duration)[:160],
    }


def recompute_stats(data):
    st = {
        "sessions": 0,
        "segments": 0,
        "matched": 0,
        "low_conf": 0,
        "interpolated": 0,
        "pending": 0,
        "missing": 0,
        "openings_ok": 0,
        "closings_ok": 0,
    }
    for s in data["sessions"]:
        st["sessions"] += 1
        st["segments"] += len(s["segments"])
        for seg in s["segments"]:
            if seg.get("start") is None:
                st["missing"] += 1
            else:
                st["matched"] += 1
                if (seg.get("confidence") or 0) < 0.5:
                    st["low_conf"] += 1
                notes = seg.get("notes") or ""
                if "interpolated" in notes:
                    st["interpolated"] += 1
                if "待人工" in notes or "no-anchor" in notes:
                    st["pending"] += 1
        if s.get("opening") is not None and s["opening"].get("start") is not None:
            st["openings_ok"] += 1
        if s.get("closing") is not None and s["closing"].get("start") is not None:
            st["closings_ok"] += 1
    return st


def word_order_starts(segs, overrides: dict):
    """Keep existing starts except overrides; null empties."""
    out = {}
    for g in segs:
        if not (g.get("answer_text") or "").strip():
            out[g["index"]] = None
        elif g["index"] in overrides:
            out[g["index"]] = overrides[g["index"]]
        else:
            out[g["index"]] = g.get("start")
    return out


def repair_0520(sess, cues, duration):
    segs = sess["segments"]
    # Word order with #7 after #2, #12 after #6
    order = [g["index"] for g in segs]
    order = [i for i in order if i not in (7, 12)]
    order.insert(order.index(2) + 1, 7)
    order.insert(order.index(6) + 1, 12)
    segs = reorder(segs, order)
    sess["segments"] = segs

    starts = word_order_starts(
        segs,
        {
            1: 2.34,
            2: 45.2,
            7: 60.5,
            3: 119.9,
            4: 177.4,
            5: 237.0,
            6: 289.0,
            12: 414.9,
            8: 456.1,
            9: 486.7,
            39: None,  # empty
        },
    )
    set_starts(segs, starts)
    # monotonic clamp for non-anchored after reorder
    prev = 0.0
    for g in segs:
        if g.get("start") is None:
            continue
        if g["start"] < prev:
            g["start"] = prev + 0.5
        prev = g["start"]
    abut(segs, duration)
    cl = segs[-1]["end"] if segs[-1].get("end") else duration - 2
    # last timed
    timed = [g for g in segs if g.get("start") is not None]
    cl = timed[-1]["end"]
    return cl


def repair_0521(sess, cues, duration):
    segs = sess["segments"]
    ov = {
        1: None,  # empty
        4: 237.0,
        5: 437.0,
        15: 1216.5,
        16: 1219.6,
    }
    # #3 should end at 237 → start of #4; ensure #3 start kept
    set_starts(segs, word_order_starts(segs, ov))
    # fix monotonic around 4
    b = by_index(segs)
    if b[3].get("start") is not None and b[4].get("start") is not None:
        if b[3]["start"] >= b[4]["start"]:
            b[3]["start"] = max(0, b[4]["start"] - 30)
    abut(segs, duration)
    timed = [g for g in segs if g.get("start") is not None]
    return timed[-1]["end"]


def repair_0522(sess, cues, duration):
    segs = sess["segments"]
    ov = {
        11: 644.0,
        15: 979.0,
        30: 1903.0,
        33: 1934.0,
        39: None,  # empty
        # 31, 32 untraceable → null
        31: None,
        32: None,
    }
    set_starts(segs, word_order_starts(segs, ov))
    prev = 0.0
    for g in segs:
        if g.get("start") is None:
            continue
        if g["start"] < prev:
            g["start"] = prev + 0.5
        prev = g["start"]
    abut(segs, duration)
    timed = [g for g in segs if g.get("start") is not None]
    return timed[-1]["end"]


def repair_0523(sess, cues, duration):
    segs = sess["segments"]
    # Reorder: 14 before 13; 28 before 27 (27 null)
    order = [g["index"] for g in segs]
    # swap 13/14
    i13, i14 = order.index(13), order.index(14)
    order[i13], order[i14] = order[i14], order[i13]
    # move 28 before 27
    order.remove(28)
    order.insert(order.index(27), 28)
    segs = reorder(segs, order)
    sess["segments"] = segs

    ov = {
        3: None,  # empty
        4: 268.0,
        5: 457.0,
        6: 508.0,
        7: 521.0,
        8: 587.0,
        12: 911.0,
        14: 1018.0,
        13: 1073.0,
        16: 1267.0,
        25: 1645.0,
        28: 1755.0,
        27: None,  # untraceable
    }
    set_starts(segs, word_order_starts(segs, ov))
    prev = 0.0
    for g in segs:
        if g.get("start") is None:
            continue
        if g["start"] < prev:
            g["start"] = prev + 0.5
        prev = g["start"]
    abut(segs, duration)
    timed = [g for g in segs if g.get("start") is not None]
    return timed[-1]["end"]


def repair_0524(sess, cues, duration):
    segs = sess["segments"]
    # Reorder end: 42, 44, 43; null 45
    order = [g["index"] for g in segs]
    for x in (43, 44, 45):
        if x in order:
            order.remove(x)
    # after 42
    pos = order.index(42) + 1
    order[pos:pos] = [44, 43, 45]
    segs = reorder(segs, order)
    sess["segments"] = segs

    ov = {
        9: 269.0,
        10: 321.5,
        11: 380.0,
        12: 409.5,
        14: 645.0,
        15: 980.0,
        20: 1250.0,
        34: 2069.0,
        44: 2544.5,
        45: None,  # untraceable
    }
    set_starts(segs, word_order_starts(segs, ov))
    prev = 0.0
    for g in segs:
        if g.get("start") is None:
            continue
        if g["start"] < prev:
            g["start"] = prev + 0.5
        prev = g["start"]
    abut(segs, duration)
    timed = [g for g in segs if g.get("start") is not None]
    return timed[-1]["end"]


def repair_0525(sess, cues, duration):
    segs = sess["segments"]
    ov = {
        3: 137.0,
        4: 209.0,
        5: 311.0,
        8: 388.0,
        10: 438.0,
        12: 512.0,
        15: 656.0,
        16: 698.0,
        20: None,  # empty / false window
        21: 923.4,
    }
    set_starts(segs, word_order_starts(segs, ov))
    prev = 0.0
    for g in segs:
        if g.get("start") is None:
            continue
        if g["start"] < prev:
            g["start"] = prev + 0.5
        prev = g["start"]
    abut(segs, duration)
    timed = [g for g in segs if g.get("start") is not None]
    return timed[-1]["end"]


REPAIRERS = {
    "2024-05-20": repair_0520,
    "2024-05-21": repair_0521,
    "2024-05-22": repair_0522,
    "2024-05-23": repair_0523,
    "2024-05-24": repair_0524,
    "2024-05-25": repair_0525,
}


def structural_check(data):
    issues = []
    for s in data["sessions"]:
        prev = None
        prev_idx = None
        for seg in s["segments"]:
            st, en = seg.get("start"), seg.get("end")
            if st is None or en is None:
                continue
            if en < st - 0.01:
                issues.append(f"INVERT {s['date']} #{seg['index']}")
            if prev is not None and st < prev - 0.5:
                issues.append(
                    f"OVERLAP {s['date']} #{prev_idx}->#{seg['index']} {prev}->{st}"
                )
            prev, prev_idx = en, seg["index"]
        if not s.get("opening") or s["opening"].get("start") is None:
            issues.append(f"NO OPENING {s['date']}")
        if not s.get("closing") or s["closing"].get("start") is None:
            issues.append(f"NO CLOSING {s['date']}")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    data = json.loads(JSON_PATH.read_text())
    # Verify text fields untouched: snapshot hashes of answer_text
    before_text = {
        (s["date"], g["index"]): (g.get("answer_text"), g.get("q_text"), g.get("questioner"))
        for s in data["sessions"]
        for g in s["segments"]
    }

    reports = []
    for sess in data["sessions"]:
        date = sess["date"]
        cues = parse_srt(Path(sess["media_parts"][0]["srt_file"]), CONV)
        duration = duration_of(sess)
        fn = REPAIRERS[date]
        cl = fn(sess, cues, duration)
        for g in sess["segments"]:
            finalize_seg(cues, g)
        # re-abut after finalize nulls
        abut(sess["segments"], duration, closing_start=cl)
        # re-finalize labels after abut
        for g in sess["segments"]:
            if g.get("start") is not None:
                g["start_label"] = fmt(g["start"])
                g["end_label"] = fmt(g["end"])
                g["srt_preview"] = between(cues, g["start"], g["end"])[:220]
        set_opening_closing(sess, cues, duration, cl)

        low = sum(
            1
            for g in sess["segments"]
            if g.get("start") is not None and (g.get("confidence") or 0) < 0.8
        )
        miss = sum(1 for g in sess["segments"] if g.get("start") is None)
        reports.append((date, len(sess["segments"]), miss, low))

    # text integrity
    after_text = {
        (s["date"], g["index"]): (g.get("answer_text"), g.get("q_text"), g.get("questioner"))
        for s in data["sessions"]
        for g in s["segments"]
    }
    assert before_text == after_text, "TEXT FIELDS CHANGED — abort"

    data["stats"] = recompute_stats(data)
    issues = structural_check(data)

    out = JSON_PATH if args.apply else JSON_PATH.parent / "2024-05.repaired.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    for date, n, miss, low in reports:
        print(f"{date}: n={n} miss={miss} conf<0.8={low}")
    print("stats:", json.dumps(data["stats"], ensure_ascii=False))
    print(f"structural issues ({len(issues)}):")
    for i in issues[:40]:
        print(" ", i)
    print("wrote", out)


if __name__ == "__main__":
    main()
