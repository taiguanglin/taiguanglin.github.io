#!/usr/bin/env python3
"""Restore missing 2024-02/03 spans that have direct content evidence in SRT.

Only timing metadata, confidence, notes, previews, and playback order are changed.
The boundaries below were reviewed one by one against readspan.py output.
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


# (month, date, Word index): (reviewed start, evidence note)
RECOVERIES = {
    ("2024-02", "2024-02-14", 28): (
        1592.4,
        "SRT 1592.4–1603.6 命中百日築基、月經消失及四小時段（已逐段校驗）",
    ),
    ("2024-02", "2024-02-15", 31): (
        1282.8,
        "SRT 1312.8–1331.6 命中周邊人與氣場答覆；前段 ASR 缺字（已逐段校驗）",
    ),
    ("2024-02", "2024-02-21", 28): (
        248.3,
        "SRT 280.1–305.8 命中善業顯現及離婚答覆；前段 ASR 缺字（已逐段校驗）",
    ),
    ("2024-03", "2024-03-07", 32): (
        1792.2,
        "SRT 1792.2–1922.7 命中常鐵軍、兩佛關係及跨世界傳法（已逐段校驗）",
    ),
    ("2024-03", "2024-03-09", 10): (
        494.3,
        "SRT 494.3–541.0 命中打坐瞌睡、熟普及運動答覆（已逐段校驗）",
    ),
    ("2024-03", "2024-03-09", 14): (
        706.4,
        "SRT 706.4–726.9 命中腳跟頂大腿根及膝蓋保護答覆（已逐段校驗）",
    ),
    ("2024-03", "2024-03-13", 7): (
        617.0,
        "SRT 647.3–710.4 命中腳腕修復、女轉男身答覆；前段 ASR 缺字（已逐段校驗）",
    ),
    ("2024-03", "2024-03-16", 9): (
        457.5,
        "SRT 457.5–557.8 命中走路消業、磕頭及朝山風險答覆（已逐段校驗）",
    ),
    ("2024-03", "2024-03-16", 29): (
        1602.6,
        "SRT 1639.9–1663.4 命中地藏經打底、大悲咒及打坐答覆；前段 ASR 缺字（已逐段校驗）",
    ),
    ("2024-03", "2024-03-18", 11): (
        777.7,
        "SRT 777.7–838.8 命中提問人及最小世界、鬼道攻擊答覆（已逐段校驗）",
    ),
    ("2024-03", "2024-03-18", 32): (
        1972.7,
        "SRT 1972.7–2006.1 命中站樁後打坐收功答覆；第一題未讀（已逐段校驗）",
    ),
    ("2024-03", "2024-03-19", 17): (
        967.8,
        "SRT 999.2–1013.0 命中腹式呼吸及磕頭配合；前段 ASR 缺字（已逐段校驗）",
    ),
    ("2024-03", "2024-03-21", 5): (
        375.0,
        "SRT 375.0–461.2 命中觀呀觀自在及女性出家答覆（已逐段校驗）",
    ),
    ("2024-03", "2024-03-26", 17): (
        595.1,
        "SRT 595.1–691.8 命中何其自性、往生信心與捨棄答覆（已逐段校驗）",
    ),
    ("2024-03", "2024-03-28", 4): (
        203.9,
        "SRT 263.1–303.0 命中批評他人修法及破壞信心答覆；前段 ASR 缺字（已逐段校驗）",
    ),
    ("2024-03", "2024-03-30", 11): (
        775.3,
        "SRT 775.3–911.6 命中往生前受業及信願行答覆（已逐段校驗）",
    ),
}

# Refined starts of the immediately following, already-matched segment.
BOUNDARY_REFINEMENTS = {
    ("2024-02", "2024-02-21", 9): 307.1,
    ("2024-03", "2024-03-09", 15): 727.7,
    ("2024-03", "2024-03-26", 12): 691.8,
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


def repair_month(month: str) -> None:
    path = REPO / "audio_map2" / f"{month}.json"
    data = json.loads(path.read_text())
    changed_sessions: set[tuple[str, str]] = set()

    for session in data["sessions"]:
        key = (session["date"], session["source"])
        by_index = {segment["index"]: segment for segment in session["segments"]}
        for (target_month, date, index), (start, note) in RECOVERIES.items():
            if target_month != month or date != session["date"]:
                continue
            segment = by_index[index]
            if segment.get("start") is not None:
                raise RuntimeError(f"{date} #{index} is no longer missing")
            segment["start"] = start
            segment["confidence"] = 0.85
            segment["status"] = "manual"
            segment["notes"] = note
            changed_sessions.add(key)

        for (target_month, date, index), start in BOUNDARY_REFINEMENTS.items():
            if target_month == month and date == session["date"]:
                by_index[index]["start"] = start
                changed_sessions.add(key)

    for session in data["sessions"]:
        key = (session["date"], session["source"])
        if key not in changed_sessions:
            continue
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
            if end < start:
                raise RuntimeError(
                    f"{session['date']} #{segment['index']} inverted {start}>{end}"
                )
            segment["start"] = round(start, 3)
            segment["end"] = round(end, 3)
            segment["start_label"] = label(start)
            segment["end_label"] = label(end)
            segment["srt_preview"] = preview(cues, start, end)

        session["segments"] = timed + missing

    data["stats"] = recompute_stats(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(f"{path.name}: {data['stats']}")


def main() -> None:
    for month in ("2024-02", "2024-03"):
        repair_month(month)


if __name__ == "__main__":
    main()
