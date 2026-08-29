#!/usr/bin/env python3
"""Pass 3: recover more 2024-02/03 missing spans by splitting neighbor windows.

Only timing / confidence / notes / previews / playback order change.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "bm", REPO / "tool/word_audio_map2/build_maps.py"
)
bm = importlib.util.module_from_spec(spec)
sys.modules["bm"] = bm
spec.loader.exec_module(bm)
from common import parse_srt_raw  # noqa: E402

RECOVERIES = {
    ("2024-02", "2024-02-22", 25): (
        635.2,
        "SRT 635.2–651.4 命中地藏不接引、阿彌陀佛觀音接應；自 #18 切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-03", 35): (
        1845.0,
        "SRT 1845–1892 命中新冠共業／佛菩薩不保病災；自 #31 切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-07", 22): (
        1596.6,
        "SRT 1596.6–1611.4 命中廣結善緣／該撤就撤；自 #21 切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-19", 28): (
        1609.7,
        "SRT 1640–1669.6 命中選金剛經保底；自 #27 切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-20", 11): (
        400.4,
        "SRT 400.4–446 命中天才櫻木花路、極樂具足／談戀愛組成家庭；自 #9 切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-20", 14): (
        712.6,
        "SRT 728.2–739.3 命中鬼道／真實事件／多念佛；自 #15 切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-21", 32): (
        2496.3,
        "SRT 2496.3–2513 命中思佛觀佛／刷抖音；自 #31 切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-23", 20): (
        1415.5,
        "SRT 1415.5–1453.4 命中絕經後更難／抓月經時段精進；自 #17 切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-30", 32): (
        2265.028,
        "SRT 2269.6–2285.9 命中身份遙遠做不了／先做任務；自 #33 切開（已逐段校驗）",
    ),
}

BOUNDARY_REFINEMENTS = {
    ("2024-03", "2024-03-19", 29): 1670.5,  # 杨学辉 after #28
    ("2024-03", "2024-03-19", 30): 1708.7,  # 莫莫念咒；原誤貼在 #29 尾
    ("2024-03", "2024-03-20", 10): 489.0,  # 洛迦 after #11
    ("2024-03", "2024-03-20", 15): 740.4,  # 莫莫 after #14
    ("2024-03", "2024-03-21", 33): 2514.6,  # 合严 after #32
    ("2024-03", "2024-03-30", 33): 2289.4,  # 静慧 after #32
}


def label(t: float | None) -> str:
    if t is None:
        return ""
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    sec = t % 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}"


def preview(cues, start: float, end: float) -> str:
    text = "".join(t for st, en, t in cues if st < end and en > start)
    return text[:120] + ("…" if len(text) > 120 else "")


def recompute_stats(data: dict) -> dict:
    stats = {
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
    for session in data["sessions"]:
        stats["sessions"] += 1
        stats["segments"] += len(session["segments"])
        for segment in session["segments"]:
            if segment.get("start") is None:
                stats["missing"] += 1
                continue
            stats["matched"] += 1
            if float(segment.get("confidence") or 0) < 0.5:
                stats["low_conf"] += 1
            notes = segment.get("notes") or ""
            if "interpolated" in notes:
                stats["interpolated"] += 1
            if "待人工" in notes or "no-anchor:clamped" in notes:
                stats["pending"] += 1
        if (session.get("opening") or {}).get("start") is not None:
            stats["openings_ok"] += 1
        if (session.get("closing") or {}).get("start") is not None:
            stats["closings_ok"] += 1
    return stats


def rebuild_session(session: dict) -> None:
    cues = parse_srt_raw(Path(session["media_parts"][0]["srt_file"]))
    timed = [s for s in session["segments"] if s.get("start") is not None]
    missing = [s for s in session["segments"] if s.get("start") is None]
    timed.sort(key=lambda s: (float(s["start"]), s["index"]))
    closing_start = float((session.get("closing") or {}).get("start") or 0)

    for pos, segment in enumerate(timed):
        end = (
            float(timed[pos + 1]["start"])
            if pos + 1 < len(timed)
            else closing_start
        )
        start = float(segment["start"])
        if end < start - 0.01:
            raise RuntimeError(
                f"{session['date']} #{segment['index']} inverted {start}>{end}"
            )
        segment["start"] = round(start, 3)
        segment["end"] = round(end, 3)
        segment["start_label"] = label(start)
        segment["end_label"] = label(end)
        segment["srt_preview"] = preview(cues, start, end)

    session["segments"] = timed + missing


def repair_month(month: str) -> None:
    path = REPO / "audio_map2" / f"{month}.json"
    data = json.loads(path.read_text())
    touched: set[tuple[str, str]] = set()

    for session in data["sessions"]:
        by_index = {segment["index"]: segment for segment in session["segments"]}
        for (m, date, index), (start, note) in RECOVERIES.items():
            if m != month or date != session["date"]:
                continue
            seg = by_index[index]
            if seg.get("start") is not None:
                raise RuntimeError(f"{date} #{index} already timed")
            seg["start"] = start
            seg["confidence"] = 0.85
            seg["status"] = "manual"
            seg["notes"] = note
            touched.add((session["date"], session["source"]))

        for (m, date, index), start in BOUNDARY_REFINEMENTS.items():
            if m == month and date == session["date"]:
                by_index[index]["start"] = start
                touched.add((session["date"], session["source"]))

        if (session["date"], session["source"]) in touched:
            rebuild_session(session)

    data["stats"] = recompute_stats(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(f"{path.name}: {data['stats']}")


def main() -> None:
    for month in ("2024-02", "2024-03"):
        repair_month(month)


if __name__ == "__main__":
    main()
