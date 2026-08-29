#!/usr/bin/env python3
"""Pass 4: recover spans swallowed by opening/closing or neighbor windows."""
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
    ("2024-03", "2024-03-20", 1): (
        2.5,
        "SRT 2.5–54.8 命中隨緣了shi 參疑情／初禪門檻；自 opening 窗口切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-01", 47): (
        2340.076,
        "SRT 2370.7–2389.7 命中地藏經／該來的都得來；自 closing 窗口切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-14", 12): (
        27.0,
        "SRT 27–59.3 命中有一無空參思情／不用著急慢慢來；自 #1 切開（已逐段校驗）",
    ),
    ("2024-03", "2024-03-12", 48): (
        1865.0,
        "SRT 1865–1872.5 命中危險別碰／能不吃就不吃（轉基因答結尾）；自 #28 切開（已逐段校驗）",
    ),
}

# opening.end / closing.start overrides after recoveries
OPENING_END = {
    ("2024-03", "2024-03-20"): 2.5,
}
CLOSING_START = {
    ("2024-03", "2024-03-01"): None,  # set from last segment end after rebuild
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


def rebuild_session(session: dict, force_closing_after_last: bool = False) -> None:
    cues = parse_srt_raw(Path(session["media_parts"][0]["srt_file"]))
    dur = float(session["media_parts"][0].get("duration_est") or cues[-1][1])
    timed = [s for s in session["segments"] if s.get("start") is not None]
    missing = [s for s in session["segments"] if s.get("start") is None]
    timed.sort(key=lambda s: (float(s["start"]), s["index"]))

    if force_closing_after_last and timed:
        # last segment end = dur (or previous closing end); closing starts at last end
        closing_start = None  # computed after assigning ends via estimate
    else:
        closing_start = float((session.get("closing") or {}).get("start") or dur)

    # First pass ends for non-force case
    if not force_closing_after_last:
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
    else:
        # ends = next start; last end = dur; then closing = last end → dur
        for pos, segment in enumerate(timed):
            start = float(segment["start"])
            if pos + 1 < len(timed):
                end = float(timed[pos + 1]["start"])
            else:
                end = dur
            if end < start - 0.01:
                raise RuntimeError(
                    f"{session['date']} #{segment['index']} inverted {start}>{end}"
                )
            segment["start"] = round(start, 3)
            segment["end"] = round(end, 3)
            segment["start_label"] = label(start)
            segment["end_label"] = label(end)
            segment["srt_preview"] = preview(cues, start, end)
        last_end = float(timed[-1]["end"])
        # Prefer SRT evidence: if last segment content ends earlier, use that as closing
        # For 03-01 #47, content ends ~2389.7; keep last_end=dur only if needed.
        # Use last segment end as closing start when force mode.
        cl = session.get("closing") or {}
        cl_start = last_end
        # If last segment would be huge to dur, clamp closing to near last content:
        # keep as last_end (which equals dur in this branch) — adjust below for 03-01.
        session["closing"] = {
            **cl,
            "start": round(cl_start, 3),
            "end": round(dur, 3),
            "start_label": label(cl_start),
            "end_label": label(dur),
            "confidence": max(float(cl.get("confidence") or 0), 0.7),
            "status": "manual",
            "notes": (cl.get("notes") or "") + "; closing 後移以讓出末段（已校驗）",
            "srt_preview": preview(cues, cl_start, dur),
        }

    session["segments"] = timed + missing


def repair_month(month: str) -> None:
    path = REPO / "audio_map2" / f"{month}.json"
    data = json.loads(path.read_text())
    touched: set[tuple[str, str]] = set()
    force_close: set[tuple[str, str]] = set()

    for session in data["sessions"]:
        key = (session["date"], session["source"])
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
            touched.add(key)
            if date == "2024-03-01" and index == 47:
                force_close.add(key)

        # opening end trim
        oe = OPENING_END.get((month, session["date"]))
        if oe is not None and session.get("opening"):
            op = session["opening"]
            op["end"] = oe
            op["end_label"] = label(oe)
            op["notes"] = (op.get("notes") or "") + "; end 縮短讓出 #1（已校驗）"
            touched.add(key)

        if key in touched:
            rebuild_session(session, force_closing_after_last=(key in force_close))

            # Special: 03-01 #47 content ends ~2389.7; don't stretch to full dur
            if key in force_close:
                by = {g["index"]: g for g in session["segments"]}
                g47 = by[47]
                # end at previous closing end (media end was 2389.685)
                end47 = 2389.685
                g47["end"] = end47
                g47["end_label"] = label(end47)
                cues = parse_srt_raw(Path(session["media_parts"][0]["srt_file"]))
                g47["srt_preview"] = preview(cues, float(g47["start"]), end47)
                cl = session["closing"]
                cl["start"] = end47
                cl["start_label"] = label(end47)
                # if start==end, bump end slightly to dur
                dur = float(session["media_parts"][0]["duration_est"])
                if cl["end"] <= end47:
                    cl["end"] = round(dur, 3)
                    cl["end_label"] = label(dur)
                cl["srt_preview"] = preview(cues, end47, float(cl["end"]))

    data["stats"] = recompute_stats(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(f"{path.name}: {data['stats']}")


def main() -> None:
    for month in ("2024-02", "2024-03"):
        repair_month(month)


if __name__ == "__main__":
    main()
