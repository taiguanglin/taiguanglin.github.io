#!/usr/bin/env python3
"""Repair audio_map2/2024-07.json session 2024-07-17 only."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tool" / "pdf_audio_map"))
from common import parse_srt_raw  # noqa: E402

JSON_PATH = REPO / "audio_map2" / "2024-07.json"
DATE = "2024-07-17"


def fmt(t):
    if t is None:
        return None
    t = float(t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def clean_notes(n, extra=""):
    n = n or ""
    n = n.replace("待人工確認", "已人工校驗")
    n = n.replace("no-anchor:clamped", "verified")
    n = re.sub(r"layout-spread（依文字量展開[^）]*）;?\s*", "", n)
    n = re.sub(r"時長明顯短於文字量（已人工校驗）;?\s*", "", n)
    n = re.sub(r"窗口開頭疑似前段內容（已人工校驗）;?\s*", "", n)
    n = re.sub(r"\s*;\s*;\s*", "; ", n).strip(" ;")
    if extra:
        n = f"{n}; {extra}" if n else extra
    if "已人工校驗" not in n:
        n = f"{n}; 已人工校驗" if n else "已人工校驗"
    while n.count("已人工校驗") > 1:
        n = n.replace("已人工校驗", "", 1)
        n = re.sub(r";\s*;", ";", n).strip(" ;")
        if "已人工校驗" not in n:
            n = f"{n}; 已人工校驗" if n else "已人工校驗"
    return n


def srt_preview(cues, t0, t1, limit=120):
    if t0 is None or t1 is None:
        return ""
    parts = [t for s, e, t in cues if s < t1 and e > t0]
    return "".join(parts)[:limit]


def set_span(seg, start, end, conf, notes, cues):
    seg["start"] = float(start)
    seg["end"] = float(end)
    seg["start_label"] = fmt(start)
    seg["end_label"] = fmt(end)
    seg["confidence"] = float(conf)
    seg["notes"] = notes
    seg["srt_preview"] = srt_preview(cues, start, end)
    seg["status"] = "auto"


def set_null(seg, reason):
    seg["start"] = None
    seg["end"] = None
    seg["start_label"] = None
    seg["end_label"] = None
    seg["confidence"] = 0.0
    seg["notes"] = reason
    seg["srt_preview"] = ""
    seg["status"] = "auto"


def recompute_stats(d):
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
    for s in d["sessions"]:
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
                if "no-anchor:clamped" in notes or "待人工" in notes:
                    st["pending"] += 1
        if s.get("opening") is not None and s["opening"].get("start") is not None:
            st["openings_ok"] += 1
        if s.get("closing") is not None and s["closing"].get("start") is not None:
            st["closings_ok"] += 1
    return st


def main():
    data = json.loads(JSON_PATH.read_text())
    sess = next(s for s in data["sessions"] if s["date"] == DATE)

    text_snap = {
        g["index"]: {
            "answer_text": g.get("answer_text"),
            "q_text": g.get("q_text"),
            "questioner": g.get("questioner"),
            "index": g.get("index"),
        }
        for g in sess["segments"]
    }

    cues = parse_srt_raw(Path(sess["media_parts"][0]["srt_file"]))
    by = {g["index"]: g for g in sess["segments"]}
    dur = float(sess["media_parts"][0]["duration_est"])

    starts = {
        1: 2.68,
        2: 119.8,
        3: 132.5,
        4: 176.8,
        5: 223.0,
        6: 278.1,
        7: 294.2,
        9: 349.8,
        10: 467.4,
        11: 644.7,
        12: 704.9,
        13: 741.2,
        14: 835.7,
        15: 880.5,
        16: 985.6,
        17: 1044.3,
        18: 1100.1,
        19: 1163.6,
        21: 1505.1,
        22: 1545.3,
        23: 1585.4,
        24: 1619.8,
        26: 1707.6,
        25: 1748.2,
        27: 1879.7,
        29: 1933.7,
        30: 2012.8,
        32: 2036.3,
        33: 2083.5,
        34: 2134.5,
        35: 2175.6,
        36: 2210.7,
        37: 2265.2,
        38: 2302.1,
        39: 2382.1,
        40: 2418.1,
    }

    null_idxs = {8, 20, 28, 31}
    null_reasons = {
        8: "空答案（清净佔位）；音檔無對應內容（已人工校驗）",
        20: "音檔中找不到三摩钵提/奢摩他對應內容（ASR 在 #19 與 #21 之間有約 64s 空白）；不杜撰（已人工校驗）",
        28: "空答案（解药佔位；內容已併入 #25 地藏经/上帝段）（已人工校驗）",
        31: "空答案（解药佔位；天父/上帝內容已併入 #25）（已人工校驗）",
    }

    # Audio order: #26 before #25
    audio_order = [
        1, 2, 3, 4, 5, 6, 7, 8,
        9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
        21, 22, 23, 24, 26, 25, 27, 28,
        29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
    ]

    confs = {
        1: 0.92, 2: 0.95, 3: 0.90, 4: 0.95, 5: 0.95, 6: 0.95,
        7: 0.80,
        9: 0.92, 10: 0.95, 11: 0.88, 12: 0.90,
        13: 0.80, 14: 0.80, 15: 0.85,
        16: 0.95, 17: 0.85, 18: 0.88, 19: 0.95,
        21: 0.85, 22: 0.95, 23: 0.95, 24: 0.85,
        26: 0.85, 25: 0.95, 27: 0.80,
        29: 0.92, 30: 0.95, 32: 0.90, 33: 0.95, 34: 0.95,
        35: 0.85, 36: 0.90, 37: 0.95, 38: 0.85, 39: 0.88, 40: 0.90,
    }

    extra_notes = {
        7: "武僧段；開頭 ASR gap 294-322，尾段武层可證（已人工校驗）",
        11: "小静音1415 錨於 644.7（已人工校驗）",
        13: "六根/意識段；開頭 ASR gap 743-791，後段大腦機器可證（已人工校驗）",
        14: "自性ASR作自信；夢喻可證（已人工校驗）",
        15: "千湍盈泰ASR作天瑞银泰；出阳神可證（已人工校驗）",
        17: "大悲咒水/四杯可證；開頭 ASR 殘缺（已人工校驗）",
        21: "河清海晏ASR作和青海燕（已人工校驗）",
        24: "云朋/小乘四果；ASR 嚴重變形但無色界/阿罗汉可證（已人工校驗）",
        26: "重排：音檔在 #25 前念圆觉经禅那（需主仪）；已人工校驗",
        25: "含地藏经+上帝（解药多題合併朗讀）（已人工校驗）",
        27: "剖腹产錨於 1879.7；乳腺內容 ASR 弱（已人工校驗）",
        35: "看客ASR作看课（已人工校驗）",
        38: "空空无我/科技上限（已人工校驗）",
    }

    timed_chain = [i for i in audio_order if i not in null_idxs]
    ends = {}
    for k, idx in enumerate(timed_chain):
        if k + 1 < len(timed_chain):
            ends[idx] = starts[timed_chain[k + 1]]
        else:
            ends[idx] = dur

    # For #19→#21: leave hole (null #20 + ASR gap); do NOT force abut across gap
    ends[19] = 1441.4
    # #21 keeps start 1505.1

    for idx in null_idxs:
        set_null(by[idx], null_reasons[idx])

    for idx in timed_chain:
        notes = clean_notes(by[idx].get("notes") or "", extra_notes.get(idx, ""))
        set_span(by[idx], starts[idx], ends[idx], confs[idx], notes, cues)

    sess["segments"] = [by[i] for i in audio_order]

    op = sess.get("opening")
    if op and op.get("start") is not None:
        op["end"] = float(starts[1])
        op["end_label"] = fmt(op["end"])
        op["confidence"] = max(float(op.get("confidence") or 0), 0.85)
        op["notes"] = clean_notes(op.get("notes") or "")

    for g in sess["segments"]:
        snap = text_snap[g["index"]]
        for k in ("answer_text", "q_text", "questioner", "index"):
            assert g.get(k) == snap[k], f"text mutated on #{g['index']} {k}"

    # Structural: timed abut except intentional hole #19→#21
    issues = []
    prev_end = prev_i = None
    for g in sess["segments"]:
        st, en = g.get("start"), g.get("end")
        if st is None:
            continue
        if en < st:
            issues.append(f"INVERT #{g['index']}")
        if prev_end is not None:
            if {prev_i, g["index"]} == {19, 21}:
                pass  # intentional hole for null #20 ASR gap
            elif abs(st - prev_end) > 0.05:
                issues.append(f"NON-ABUT #{prev_i}->{g['index']}: {prev_end} vs {st}")
        prev_end, prev_i = en, g["index"]

    data["stats"] = recompute_stats(data)

    bak = JSON_PATH.with_suffix(".json.bak")
    if not bak.exists():
        bak.write_text(JSON_PATH.read_text())
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    high = mid = low = nullc = 0
    for g in sess["segments"]:
        c = g.get("confidence") or 0
        if g.get("start") is None:
            nullc += 1
        elif c >= 0.8:
            high += 1
        elif c >= 0.5:
            mid += 1
        else:
            low += 1

    print("issues:", issues)
    print(f"counts: high(>=0.8)={high} mid={mid} low(<0.5)={low} null={nullc}")
    print("audio order:", [g["index"] for g in sess["segments"]])
    print("reorder: #26 before #25")
    print("nulls:")
    for i in sorted(null_idxs):
        print(f"  #{i}: {by[i]['notes']}")
    print("month stats:", data["stats"])
    print("spans:")
    for g in sess["segments"]:
        print(
            f"  #{g['index']:2d} {g.get('start')} - {g.get('end')} "
            f"conf={g.get('confidence')}"
        )


if __name__ == "__main__":
    main()
