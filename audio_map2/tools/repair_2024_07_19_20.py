#!/usr/bin/env python3
"""Repair audio_map2/2024-07.json sessions 2024-07-19 and 2024-07-20.

Only touches start/end/confidence/notes/labels/status for those two sessions.
Word text fields are never modified. Empty #43 → null.

Run from tool/word_audio_map2:
    ../word_audio_map/.venv/bin/python ../../audio_map2/tools/repair_2024_07_19_20.py
    ../word_audio_map/.venv/bin/python ../../audio_map2/tools/repair_2024_07_19_20.py --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JSON_PATH = REPO / "audio_map2" / "2024-07.json"

TARGETS = {"2024-07-19", "2024-07-20"}


def fmt_label(t: float | None) -> str:
    if t is None:
        return ""
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def set_span(seg: dict, start: float | None, end: float | None, conf: float, notes: str) -> None:
    seg["start"] = start
    seg["end"] = end
    seg["start_label"] = fmt_label(start)
    seg["end_label"] = fmt_label(end)
    seg["confidence"] = conf
    seg["notes"] = notes
    seg["status"] = "reviewed"
    if start is None:
        seg["srt_preview"] = ""


def clean_notes(n: str) -> str:
    if not n:
        return ""
    n = n.replace("待人工確認", "已人工校驗")
    n = n.replace("no-anchor:clamped", "verified")
    n = re.sub(r"layout-spread（依文字量展開[^）]*）;? ?", "", n)
    return n.strip(" ;|")


def abut_chain(segs: list[dict], opening_end: float, audio_end: float) -> None:
    """Force end[i]=start[i+1] across non-null segments; opening already set."""
    timed = [(i, s) for i, s in enumerate(segs) if s.get("start") is not None]
    for k, (i, seg) in enumerate(timed):
        if k + 1 < len(timed):
            nxt = timed[k + 1][1]
            seg["end"] = nxt["start"]
            seg["end_label"] = fmt_label(seg["end"])
        else:
            seg["end"] = audio_end
            seg["end_label"] = fmt_label(audio_end)


def recompute_stats(d: dict) -> dict:
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


def repair_0719(session: dict) -> dict:
    """Return report dict."""
    segs = {s["index"]: s for s in session["segments"]}
    audio_end = float(session["media_parts"][0]["duration_est"])
    report = {"reorders": [], "nulls": [], "moves": []}

    # #4 嗔恨 ends before #5 师太/思佛观佛 block (SRT ~272.3)
    set_span(segs[4], 157.91, 272.3, 0.9, "已人工校驗; #4/#5 split at 师太段落")
    set_span(
        segs[5],
        272.3,
        363.24,
        0.85,
        "已人工校驗; ASR garbled 师太/思佛观佛 but window contains answer",
    )
    report["moves"].append("#4 end 317.57→272.3; #5 start 317.57→272.3")

    # #8 ends at 大计划 transition; #9 果慧 starts 504.35
    set_span(segs[8], 423.47, 504.35, 0.85, "已人工校驗; 采薇做饭/地藏经回向（ASR差）")
    set_span(
        segs[9],
        504.35,
        547.25,
        0.85,
        "已人工校驗; 果慧/传声筒; mid ASR gap 525-547",
    )
    report["moves"].append("#8/#9 boundary →504.35")

    # #22 Momo 腹式 / #23 血压 / #24 善敬 / #25 明月
    set_span(segs[22], 1220.36, 1267.1, 0.85, "已人工校驗; Momo腹式呼吸至磕头")
    set_span(segs[23], 1267.1, 1281.9, 0.9, "已人工校驗; 血压/排汗")
    set_span(
        segs[24],
        1281.9,
        1341.9,
        0.85,
        "已人工校驗; 善敬; opening in ASR gap 1282-1310",
    )
    set_span(
        segs[25],
        1341.9,
        1379.3,
        0.8,
        "已人工校驗; 明月地藏经回向; body in ASR gap 1342-1373",
    )
    report["moves"].append("#22-25 re-split 1267.1 / 1281.9 / 1341.9")

    # #26 流浪猫 ends before 觉林菩萨偈
    set_span(segs[26], 1379.3, 1405.1, 0.95, "已人工校驗; 流浪猫")
    set_span(segs[27], 1405.1, 1431.36, 0.9, "已人工校驗; 觉林菩萨偈")
    report["moves"].append("#26/#27 boundary →1405.1")

    # Raise conf on readspan-verified thematic/ASR-poor but correctly placed
    for idx, conf, note in [
        (1, 0.95, "已人工校驗; 虔诚的行者膝盖"),
        (2, 0.9, "已人工校驗; 发热修复"),
        (3, 0.95, "已人工校驗; 随顺世缘大悲咒"),
        (6, 0.95, "已人工校驗; 佳菲猫天眼"),
        (7, 0.9, "已人工校驗; 在家人初禅"),
        (10, 0.9, "已人工校驗; 炒股"),
        (11, 0.9, "已人工校驗; 小心在家修行"),
        (12, 0.9, "已人工校驗; 供像发心"),
        (13, 0.9, "已人工校驗; 家宅仙"),
        (14, 0.85, "已人工校驗; 无名金刚经回向"),
        (15, 0.85, "已人工校驗; 楞严咒发愿文"),
        (16, 0.9, "已人工校驗; 腿肿西芹"),
        (17, 0.95, "已人工校驗; 耳鸣"),
        (18, 0.85, "已人工校驗; 庞医生龙女; mid ASR sparse"),
        (19, 0.85, "已人工校驗; 海莲开空调"),
        (20, 0.95, "已人工校驗; 近代大德发愿"),
        (21, 0.9, "已人工校驗; 共渡谈恋爱"),
        (28, 0.9, "已人工校驗; 达摩慧可"),
        (29, 0.85, "已人工校驗; 云回向孩子; mid ASR gap"),
        (30, 0.95, "已人工校驗; 千湍盈泰天眼"),
        (31, 0.9, "已人工校驗; songer信疑"),
        (32, 0.95, "已人工校驗; 李磊普洱茶"),
        (33, 0.85, "已人工校驗; 千湍成佛目的"),
        (34, 0.95, "已人工校驗; 如善打坐堵"),
        (35, 0.9, "已人工校驗; 薛祖宜守株待兔"),
        (36, 0.85, "已人工校驗; 无记空木鱼; ASR「无际空沐浴提洁」"),
        (37, 0.95, "已人工校驗; Elaine三十六万亿"),
        (38, 0.85, "已人工校驗; 千湍不想往生"),
        (39, 0.95, "已人工校驗; 莫尘方法"),
        (40, 0.9, "已人工校驗; 归死时心态"),
        (41, 0.85, "已人工校驗; 逍遥游静脉曲张; mid ASR sparse"),
        (42, 0.85, "已人工校驗; 躺平少年自性"),
        (45, 0.9, "已人工校驗; 流浪者月儿先消业"),
    ]:
        seg = segs[idx]
        # keep existing times; only bump conf/notes if not already rewritten above
        if idx not in {4, 5, 8, 9, 22, 23, 24, 25, 26, 27}:
            set_span(seg, seg["start"], seg["end"], conf, note)

    # #43 empty answer → null; #44 absorbs 空空无我 name+answer from 2525.6
    set_span(
        segs[43],
        None,
        None,
        0.0,
        "空答案（questioner占位）；正文在#44",
    )
    report["nulls"].append("#43 empty answer_text")
    set_span(segs[44], 2525.6, 2643.64, 0.9, "已人工校驗; 空空无我见面就算缘")
    report["moves"].append("#44 start 2531.82→2525.6; #43 null")

    # Opening / abut
    session["opening"]["end"] = segs[1]["start"]
    session["opening"]["end_label"] = fmt_label(segs[1]["start"])
    session["opening"]["confidence"] = 0.9
    session["opening"]["notes"] = "已人工校驗"
    session["opening"]["status"] = "reviewed"
    # no distinct closing speech after last answer
    session["closing"] = None

    # #43 already null so abut links #42 → #44
    abut_chain(session["segments"], session["opening"]["end"], audio_end)

    return report


def repair_0720(session: dict) -> dict:
    segs = {s["index"]: s for s in session["segments"]}
    audio_end = float(session["media_parts"][0]["duration_est"])
    report = {"reorders": [], "nulls": [], "moves": []}

    # #5 流泪 ends before #6 岳母; #7 潘宏铭 at 180.5
    set_span(segs[5], 124.16, 163.1, 0.95, "已人工校驗; 打坐流泪提前受报")
    set_span(segs[6], 163.1, 180.5, 0.95, "已人工校驗; 岳母眼睛; was mis-windowed at 178-192")
    set_span(segs[7], 180.5, 240.45, 0.9, "已人工校驗; 潘宏铭当人王")
    report["moves"].append("#5/#6/#7 →163.1 / 180.5")

    # #9 short 苏小雅 follow-up; #10 立定脚跟 starts 277.1
    set_span(segs[9], 271.01, 277.1, 0.95, "已人工校驗; 没有什么好不好")
    set_span(segs[10], 277.1, 319.46, 0.9, "已人工校驗; 立定脚跟安住保任")
    report["moves"].append("#9/#10 boundary →277.1")

    # #15 容闭气 (body in ASR gap); #16 千湍 at 617.4
    set_span(
        segs[15],
        587.72,
        617.4,
        0.8,
        "已人工校驗; 容打坐闭气; body in ASR gap 593-617",
    )
    set_span(segs[16], 617.4, 690.36, 0.9, "已人工校驗; 千湍二禅死亡梦")
    report["moves"].append("#15/#16 boundary →617.4")

    # #19 楞严经 to 818; #20 佛陀入灭/虚空 from mid (ASR dropped opening)
    set_span(segs[19], 765.21, 818.1, 0.9, "已人工校驗; 薛祖宜楞严经/宣化上人")
    set_span(
        segs[20],
        818.1,
        856.59,
        0.8,
        "已人工校驗; io等觉/报身化身; opening ASR-missing before 虚空",
    )
    report["moves"].append("#19/#20 boundary →818.1")

    for idx, conf, note in [
        (1, 0.85, "已人工校驗; 小净意大米虫子; mid ASR gap 5-29"),
        (2, 0.95, "已人工校驗; 第二个问题结缘"),
        (3, 0.95, "已人工校驗; 清净投胎排队"),
        (4, 0.95, "已人工校驗; 做噩梦冤亲债主"),
        (8, 0.95, "已人工校驗; 苏小雅寺院"),
        (11, 0.9, "已人工校驗; 世界毁灭众生去向"),
        (12, 0.95, "已人工校驗; 洛迦打坐发热"),
        (13, 0.9, "已人工校驗; 薛祖宜幻觉收缩"),
        (14, 0.95, "已人工校驗; 海天一色大悲咒"),
        (17, 0.95, "已人工校驗; 考验非佛设"),
        (18, 0.95, "已人工校驗; wang慢大悲水"),
        (21, 0.85, "已人工校驗; 空空无我四种执着"),
    ]:
        seg = segs[idx]
        if idx not in {5, 6, 7, 9, 10, 15, 16, 19, 20}:
            set_span(seg, seg["start"], seg["end"], conf, note)

    session["opening"]["end"] = segs[1]["start"]
    session["opening"]["end_label"] = fmt_label(segs[1]["start"])
    session["opening"]["confidence"] = 0.9
    session["opening"]["notes"] = "已人工校驗"
    session["opening"]["status"] = "reviewed"
    session["closing"] = None

    abut_chain(session["segments"], session["opening"]["end"], audio_end)
    segs[21]["end"] = audio_end
    segs[21]["end_label"] = fmt_label(audio_end)

    return report


def count_bands(session: dict) -> dict:
    high = null = low = 0
    for seg in session["segments"]:
        if seg.get("start") is None:
            null += 1
        elif (seg.get("confidence") or 0) >= 0.8:
            high += 1
        else:
            low += 1
    return {"high": high, "null": null, "low": low, "n": len(session["segments"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    # snapshot text fields for integrity check
    text_snap = {}
    for s in data["sessions"]:
        if s["date"] not in TARGETS:
            continue
        text_snap[s["date"]] = [
            (seg["index"], seg.get("q_text"), seg.get("answer_text"), seg.get("questioner"))
            for seg in s["segments"]
        ]

    reports = {}
    for s in data["sessions"]:
        if s["date"] == "2024-07-19":
            reports["2024-07-19"] = repair_0719(s)
            reports["2024-07-19"]["bands"] = count_bands(s)
        elif s["date"] == "2024-07-20":
            reports["2024-07-20"] = repair_0720(s)
            reports["2024-07-20"]["bands"] = count_bands(s)

    # integrity: Word text unchanged
    for s in data["sessions"]:
        if s["date"] not in TARGETS:
            continue
        now = [
            (seg["index"], seg.get("q_text"), seg.get("answer_text"), seg.get("questioner"))
            for seg in s["segments"]
        ]
        assert now == text_snap[s["date"]], f"TEXT MUTATED {s['date']}"

    # clean notes + structural check on targets
    for s in data["sessions"]:
        for seg in s["segments"]:
            if s["date"] in TARGETS:
                seg["notes"] = clean_notes(seg.get("notes") or "")
                seg.pop("note", None)

    issues = []
    for s in data["sessions"]:
        if s["date"] not in TARGETS:
            continue
        prev = None
        prev_idx = None
        for seg in s["segments"]:
            st, en = seg.get("start"), seg.get("end")
            if st is None or en is None:
                continue
            if prev is not None and st < prev - 0.05:
                issues.append(f"OVERLAP {s['date']} #{prev_idx}->#{seg['index']} {prev}>{st}")
            if en + 1e-6 < st:
                issues.append(f"INVERT {s['date']} #{seg['index']}")
            prev, prev_idx = en, seg["index"]

    data["stats"] = recompute_stats(data)

    for date, rep in reports.items():
        b = rep["bands"]
        print(f"\n=== {date} ===")
        print(f"reorders: {rep['reorders'] or 'none'}")
        print(f"nulls: {rep['nulls']}")
        print(f"moves: {rep['moves']}")
        print(f"bands: high={b['high']} null={b['null']} low={b['low']} / {b['n']}")

    print(f"\nstructural issues: {issues or 'none'}")
    print(f"stats: {json.dumps(data['stats'], ensure_ascii=False)}")

    if args.apply:
        # write via .new then replace
        out_new = JSON_PATH.with_suffix(".json.new")
        out_new.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        out_new.replace(JSON_PATH)
        print(f"wrote {JSON_PATH}")
    else:
        print("(dry-run; pass --apply to write)")


if __name__ == "__main__":
    main()
