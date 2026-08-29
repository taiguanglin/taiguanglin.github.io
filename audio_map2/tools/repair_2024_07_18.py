#!/usr/bin/env python3
"""Repair audio_map2/2024-07.json session 2024-07-18 only.

Thematic ASR-poor session. Hand-verified anchors via readspan.
Reorder: Word #38/#39 swapped in audio (#39 看客 before #38 月影如梦).
Null: #23 Kiv empty answer.

Usage (cwd = tool/word_audio_map2):
  PYTHONPATH=../pdf_audio_map ../word_audio_map/.venv/bin/python \
    ../../audio_map2/tools/repair_2024_07_18.py
  ... --apply
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

JSON_PATH = REPO / "audio_map2" / "2024-07.json"
CONV = get_converter()
DATE = "2024-07-18"

# Audio-order starts (readspan-verified). #8 is proportional inside ASR gap 331–379.
ANCHORS = {
    1: 2.44,
    2: 42.28,
    3: 83.85,
    4: 220.8,  # 「你在现在年纪」= 偶米大（名未入 ASR）
    5: 276.2,  # 加菲猫六六六
    6: 314.9,
    7: 326.5,  # 若知我空
    8: 350.5,  # ASR gap mid；#8 結尾「這和地理沒有關係」@378.9
    9: 378.9,  # SNJYLG
    10: 417.1,  # 极乐甘泉
    11: 442.8,  # 编辑菩萨
    12: 478.1,  # 天润银泰／气柱
    13: 535.9,  # 空空无我 成佛计划
    14: 559.6,  # 哈弗／法藏
    15: 696.8,  # 那k 发了愿
    16: 751.4,  # KIB
    17: 803.9,  # 小静意
    18: 842.6,  # 阿基尼…脸黄
    19: 893.2,  # 社心 共修
    20: 950.4,  # 悟空 还阴债
    21: 985.5,  # 散进 疱疹
    22: 1032.7,  # 流量者月耳
    # 23 null
    24: 1116.3,  # 上天安排的最大
    25: 1179.1,  # 定一下／定性
    26: 1241.9,  # 泊 吃苦
    27: 1467.0,  # 千湍 梦里伤害
    28: 1530.2,  # 回家
    29: 1574.4,  # 容 堕胎
    30: 1627.7,  # 梦到天上飞
    31: 1646.7,  # 明清
    32: 1693.2,  # 小建议 舍受
    33: 1746.2,  # 吃肉便菜
    34: 1804.5,  # 其乐甘泉 无限地域
    35: 1847.6,  # 一念
    36: 1900.1,  # 毛沉水
    37: 1965.5,  # 颜肇 情绪
    39: 2019.6,  # 看客（音檔順序在 #38 前）
    38: 2055.9,  # 月影如梦
    40: 2169.9,  # 长兵少年
    41: 2344.3,  # 空空无我 业力
}

# Playback order (array order). #23 null kept between 22 and 24 (Word slot).
AUDIO_ORDER = [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37,
    39, 38, 40, 41,
]

# Segments inside large ASR gaps / heavy garble — still structurally verified.
GAP_OK = {7, 8, 11, 17, 22, 32, 39, 41}


def fmt(t):
    if t is None:
        return None
    t = float(t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def between(cues, t0, t1):
    if t0 is None or t1 is None:
        return ""
    return "".join(t for s, e, t in cues if s < t1 and e > t0)


def coverage(win, probe):
    if not win or not probe:
        return 0.0
    sm = difflib.SequenceMatcher(None, win, probe, autojunk=False)
    return sum(m.size for m in sm.get_matching_blocks()) / max(1, len(probe))


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


def repair(sess, cues, duration):
    by = {g["index"]: g for g in sess["segments"]}
    assert set(by) == set(AUDIO_ORDER), "index set mismatch"
    segs = [by[i] for i in AUDIO_ORDER]
    sess["segments"] = segs

    for g in segs:
        idx = g["index"]
        a = (g.get("answer_text") or "").strip()
        if not a:
            g["start"] = None
            g["end"] = None
            g["start_label"] = None
            g["end_label"] = None
            g["confidence"] = 0.0
            g["notes"] = "空答案（Kiv 佔位段無正文）；已人工校驗"
            g["status"] = "manual"
            continue
        g["start"] = float(ANCHORS[idx])

    timed = [g for g in segs if g.get("start") is not None]
    for i, g in enumerate(timed):
        if i + 1 < len(timed):
            g["end"] = timed[i + 1]["start"]
        else:
            g["end"] = round(min(duration - 0.01, 2400.685), 3)

    # Opening abuts first segment
    op = sess.get("opening")
    if op is not None and timed:
        op["start"] = 0.0
        op["end"] = timed[0]["start"]
        op["start_label"] = fmt(op["start"])
        op["end_label"] = fmt(op["end"])
        op["confidence"] = 0.85
        op["notes"] = "已人工校驗（無開場白，至首段）"
        op["status"] = "manual"

    high = null = low = 0
    for g in segs:
        idx = g["index"]
        a = (g.get("answer_text") or "").strip()
        if not a:
            null += 1
            continue
        probe = normalize(a[:180], CONV)
        cov = coverage(between(cues, g["start"], g["end"]), probe)
        g["start_label"] = fmt(g["start"])
        g["end_label"] = fmt(g["end"])
        g["status"] = "manual"
        g.pop("note", None)

        if idx == 8:
            g["confidence"] = 0.8
            g["notes"] = (
                "已人工校驗；#7→#8 落在 ASR 大空隙 331–379，"
                f"起點依字數比例 interpolated={g['start']:.1f}；"
                "結尾錨「這和地理沒有關係」@378.9"
            )
        elif idx == 7:
            g["confidence"] = 0.8
            g["notes"] = (
                "已人工校驗；起點「若知我空」@326.5 確認；"
                "後半落在 ASR 空隙，與 #8 比例分界"
            )
        elif idx in GAP_OK:
            g["confidence"] = 0.8
            g["notes"] = f"已人工校驗；主題式 ASR 差 cov={cov:.2f}，錨點/鄰接已 readspan 確認"
        elif cov >= 0.45:
            g["confidence"] = 0.92
            g["notes"] = f"已人工校驗 cov={cov:.2f}"
        elif cov >= 0.30:
            g["confidence"] = 0.85
            g["notes"] = f"已人工校驗 cov={cov:.2f}"
        else:
            g["confidence"] = 0.8
            g["notes"] = f"已人工校驗；ASR 變形大 cov={cov:.2f}，內容錨點已確認"

        if g["confidence"] >= 0.8:
            high += 1
        else:
            low += 1

        # light srt_preview refresh (SRT-derived, not Word text)
        raw = between(cues, g["start"], g["end"])
        g["srt_preview"] = raw[:220] + ("…" if len(raw) > 220 else "")

    # structural check
    prev_end = None
    for g in segs:
        if g.get("start") is None:
            continue
        assert g["end"] > g["start"], (g["index"], g["start"], g["end"])
        if prev_end is not None:
            assert abs(g["start"] - prev_end) < 1e-6, (
                f"abut fail #{g['index']}: start={g['start']} prev_end={prev_end}"
            )
        prev_end = g["end"]

    return {
        "reorder": "array: …37,39,38,40… (看客 before 月影如梦)",
        "nulls": [(23, "空答案 Kiv")],
        "high": high,
        "null": null,
        "low": low,
        "n": len(segs),
    }


def snapshot_texts(sess):
    return [
        (
            g["index"],
            g.get("questioner"),
            g.get("q_text"),
            g.get("answer_text"),
            g.get("question_id"),
            g.get("stable_key"),
        )
        for g in sess["segments"]
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    data = json.loads(JSON_PATH.read_text())
    sess = next(s for s in data["sessions"] if s["date"] == DATE)
    before_texts = snapshot_texts(sess)
    before_order = [g["index"] for g in sess["segments"]]

    cues = parse_srt(Path(sess["media_parts"][0]["srt_file"]), CONV)
    duration = float(sess["media_parts"][0]["duration_est"])
    summary = repair(sess, cues, duration)

    after_texts = snapshot_texts(sess)
    # texts immutable except we reordered array — compare as multisets by index
    bt = {t[0]: t[1:] for t in before_texts}
    at = {t[0]: t[1:] for t in after_texts}
    assert bt == at, "Word text fields mutated"

    after_order = [g["index"] for g in sess["segments"]]
    data["stats"] = recompute_stats(data)

    out = JSON_PATH if args.apply else JSON_PATH.with_suffix(".json.718new")
    # keep .json path when apply; else write sibling
    if not args.apply:
        out = REPO / "audio_map2" / "2024-07.json.718new"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    print("before order:", before_order)
    print("after  order:", after_order)
    print(summary)
    print("month stats:", data["stats"])
    print("wrote", out)


if __name__ == "__main__":
    main()
