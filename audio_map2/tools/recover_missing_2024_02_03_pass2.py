#!/usr/bin/env python3
"""Pass 2: recover more missing spans by splitting neighbor windows; fix array order.

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

# Newly recovered missing segments (month, date, index) -> (start, note)
RECOVERIES = {
    ("2024-02", "2024-02-27", 16): (
        639.9,
        "SRT 646.7–676.5 命中肉邊菜／三淨肉答；自鄰段 #15 窗口切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-15", 32): (
        2577.4,
        "SRT 2577.4–2581.8 命中肌肉跳動／不疼就行；自 #33/#34 邊界切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-15", 36): (
        2680.7,
        "SRT 2680.7–2685.7 命中磕頭打坐少吃練腹式；自 #37 窗口切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-27", 17): (
        1075.1,
        "SRT 1120.8–1175.5 命中感應／往生／終極保險答；#16 雙盤後切開（已逐段校驗）",
    ),
}

# Neighbor starts that must move so recovered spans fit without overlap
BOUNDARY_REFINEMENTS = {
    ("2024-02", "2024-02-27", 15): 677.9,  # 安_Tai after #16
    ("2024-03", "2024-03-15", 34): 2583.1,  # 洛迦 after #32
    ("2024-03", "2024-03-15", 37): 2686.4,  # 我在树下 after #36
    ("2024-03", "2024-03-27", 18): 1176.6,  # 地狱 after #17
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
    """Sort timed by start, append nulls, stitch ends."""
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
        # refresh preview for changed sessions
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

        # Always normalize: nulls at end (fixes e.g. 2024-02-12 #9 mid-array)
        null_mid = False
        seen_null = False
        for seg in session["segments"]:
            if seg.get("start") is None:
                seen_null = True
            elif seen_null:
                null_mid = True
                break
        if null_mid or (session["date"], session["source"]) in touched:
            rebuild_session(session)

    data["stats"] = recompute_stats(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(f"{path.name}: {data['stats']}")


def main() -> None:
    for month in ("2024-02", "2024-03"):
        repair_month(month)


if __name__ == "__main__":
    main()
