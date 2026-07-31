#!/usr/bin/env python3
"""Align PDF ebook questions to audio time ranges; write audio_map JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from common import (
    DEFAULT_SRT_ROOT,
    EBOOK_DIR,
    HEADING_RE,
    MAP_DIR,
    OPENING_TIME_RE,
    QA_DIR,
    QA_TXT_MONTHS,
    TIME_LINE_RE,
    empty_range_fields,
    get_converter,
    match_ordered,
    match_start,
    month_map_path,
    normalize,
    parse_srt,
    parse_srt_raw,
    parse_tc,
    question_needles,
    range_fields,
    resolve_media,
    spoken_name_variants,
    srt_path_for,
    srt_preview,
    title_coverage,
)
from extract_sessions import extract_all


def _is_protected(item: Optional[dict]) -> bool:
    if not item:
        return False
    return bool(item.get("locked")) or item.get("status") == "manual"


def _merge_preserve(old: Optional[dict], new: dict) -> dict:
    """Keep locked/manual fields from old; otherwise take new."""
    if _is_protected(old):
        return old
    return new


def _load_existing(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {s["session_id"]: s for s in data.get("sessions") or []}


def _qa_txt_path(stem: str) -> Path:
    return QA_DIR / f"{stem}.txt"


def _parse_qa_txt(path: Path) -> Tuple[Optional[Tuple[float, float]], List[dict]]:
    """Return (opening_range, segments[{number,title,start,end,question}])."""
    text = path.read_text(encoding="utf-8")
    opening = None
    om = OPENING_TIME_RE.search(text)
    if om:
        opening = (parse_tc(om.group(1)), parse_tc(om.group(2)))

    headings = list(HEADING_RE.finditer(text))
    segments = []
    for i, h in enumerate(headings):
        block_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[h.start() : block_end]
        tm = TIME_LINE_RE.search(block)
        if not tm:
            continue
        segments.append(
            {
                "number": h.group(1),
                "title": h.group(2).strip(),
                "start": parse_tc(tm.group(1)),
                "end": parse_tc(tm.group(2)),
                "question": h.group(2).strip(),
            }
        )
    return opening, segments


def align_from_qa_txt(session: dict, converter, cues_raw, srt_root: Path) -> dict:
    """Map qa/*.txt times onto PDF questions (QA titles are short summaries).

    Strategy:
    1. Match each QA title → PDF question by title-coverage (ordered).
    2. Run full SRT align and use it only where qa.txt did not match.
    """
    stem = session["audio_file"].replace(".opus", "")
    txt = _qa_txt_path(stem)
    srt_result = align_from_srt(session, converter, srt_root)
    if not txt.exists():
        return srt_result

    opening_range, qa_segs = _parse_qa_txt(txt)
    if not qa_segs:
        return srt_result

    qa_titles = [normalize(s["question"], converter) for s in qa_segs]
    pdf_hay = [
        normalize(seg.get("q_text") or seg.get("q_preview") or "", converter)
        for seg in session["segments"]
    ]
    # QA (fewer, short titles) → PDF (more, full questions)
    qa_to_pdf = match_ordered(
        qa_titles,
        pdf_hay,
        min_ratio=0.45,
        scorer=title_coverage,
        window=16,
    )

    new_segments = [dict(seg) for seg in srt_result["segments"]]
    for qi, pdf_i in enumerate(qa_to_pdf):
        if pdf_i is None:
            continue
        qs = qa_segs[qi]
        conf = title_coverage(qa_titles[qi], pdf_hay[pdf_i])
        preview = srt_preview(cues_raw, qs["start"], qs["end"]) if cues_raw else ""
        fields = range_fields(qs["start"], qs["end"], max(0.7, conf), "from_qa_txt", preview)
        fields["notes"] = f"qa segment {qs['number']}"
        # Prefer human-tuned qa.txt times over SRT
        new_segments[pdf_i].update(fields)

    opening = srt_result.get("opening")
    if opening_range:
        preview = (
            srt_preview(cues_raw, opening_range[0], opening_range[1]) if cues_raw else ""
        )
        fields = range_fields(
            opening_range[0], opening_range[1], 0.9, "from_qa_txt", preview
        )
        base = session.get("opening") or srt_result.get("opening") or {}
        opening = {**base, **fields}

    return {**srt_result, "opening": opening, "segments": new_segments}


def _mark_all_missing(session: dict, note: str) -> dict:
    segs = []
    for seg in session["segments"]:
        fields = empty_range_fields()
        fields["notes"] = note
        segs.append({**seg, **fields})
    opening = session.get("opening")
    if opening:
        fields = empty_range_fields()
        fields["notes"] = note
        opening = {**opening, **fields}
    return {**session, "opening": opening, "segments": segs}


def _interpolate_starts(
    starts: List[Optional[float]],
    scores: List[float],
    audio_end: float,
) -> Tuple[List[float], List[str]]:
    """Fill None starts by monotonic interpolation between neighbors."""
    n = len(starts)
    if n == 0:
        return [], []
    resolved: List[Optional[float]] = list(starts)
    notes = [""] * n

    known = [i for i, s in enumerate(resolved) if s is not None]
    if not known:
        # Nothing matched — spread evenly across the audio
        step = max(audio_end / max(n, 1), 0.5)
        for i in range(n):
            resolved[i] = min(i * step, max(audio_end - 0.5, 0.0))
            notes[i] = "interpolated evenly (no SRT hits)"
        return [float(x) for x in resolved], notes  # type: ignore[misc]

    # Leading gap: before first known
    first = known[0]
    if first > 0:
        t0 = 0.0
        t1 = float(resolved[first])  # type: ignore[arg-type]
        for k in range(first):
            resolved[k] = t0 + (t1 - t0) * (k + 1) / (first + 1)
            notes[k] = "interpolated"
            scores[k] = max(scores[k], 2.0)

    # Interior gaps
    for a, b in zip(known, known[1:]):
        if b == a + 1:
            continue
        t0 = float(resolved[a])  # type: ignore[arg-type]
        t1 = float(resolved[b])  # type: ignore[arg-type]
        gap = b - a
        for k in range(1, gap):
            idx = a + k
            resolved[idx] = t0 + (t1 - t0) * k / gap
            notes[idx] = "interpolated"
            scores[idx] = max(scores[idx], 2.0)

    # Trailing gap: after last known
    last = known[-1]
    if last < n - 1:
        t0 = float(resolved[last])  # type: ignore[arg-type]
        t1 = max(audio_end, t0 + 0.5 * (n - last))
        gap = n - last
        for k in range(1, gap):
            idx = last + k
            resolved[idx] = t0 + (t1 - t0) * k / gap
            notes[idx] = "interpolated"
            scores[idx] = max(scores[idx], 2.0)

    # Enforce monotonic
    out: List[float] = []
    for i, s in enumerate(resolved):
        val = float(s)  # type: ignore[arg-type]
        if out and val <= out[-1]:
            val = out[-1] + 0.05
            if not notes[i]:
                notes[i] = "monotonic adjust"
        out.append(val)
    return out, notes


def align_from_srt(session: dict, converter, srt_root: Path) -> dict:
    stem = session["audio_file"].replace(".opus", "")
    srt = Path(session.get("srt_file") or srt_path_for(stem, srt_root))
    if not srt.exists():
        srt = srt_root / f"{stem[:4]}答疑音頻" / f"{stem}.srt"
    if not srt.exists():
        return _mark_all_missing(session, f"SRT missing: {srt.name}")

    cues = parse_srt(srt, converter)
    cues_raw = parse_srt_raw(srt)
    if not cues:
        return _mark_all_missing(session, "SRT empty")

    audio_end = cues[-1][1]
    cursor_idx = 0
    starts: List[Optional[float]] = []
    scores: List[float] = []

    for seg in session["segments"]:
        res = None
        via_name = False
        # 1) Questioner name (ASR often reads 571 as 五七幺) — strongest anchor
        for name in spoken_name_variants(seg.get("questioner") or "", converter):
            if len(name) < 2:
                continue
            res = match_start(
                cues, cursor_idx, name, min_len=2, min_block=min(4, len(name)), max_scan=280
            )
            if res is not None:
                via_name = True
                break
        # 2) Distinctive question body (skip 顶礼师父… boilerplate)
        if res is None:
            for needle in question_needles(
                seg.get("q_text") or seg.get("q_preview") or "", converter
            ):
                res = match_start(
                    cues, cursor_idx, needle, min_len=6, min_block=6, max_scan=280
                )
                if res is not None and res[2] >= 6:
                    break
                res = None
        # 3) Answer opening
        if res is None and seg.get("answer_preview"):
            a = normalize(seg["answer_preview"], converter)[:60]
            res = match_start(cues, cursor_idx, a, min_len=6, min_block=5)
        # 4) Global re-anchor
        if res is None:
            for needle in question_needles(
                seg.get("q_text") or seg.get("q_preview") or "", converter
            ):
                res = match_start(
                    cues, 0, needle, min_len=8, min_block=8, max_scan=len(cues)
                )
                if res is not None:
                    break
        if res is None and seg.get("answer_preview"):
            ga = normalize(seg["answer_preview"], converter)[:90]
            res = match_start(cues, 0, ga, min_len=10, min_block=10, max_scan=len(cues))
        if res is None:
            starts.append(None)
            scores.append(0.0)
            continue
        start_time, cue_idx, score = res
        # Enforce monotonicity: never go backwards
        if starts and any(s is not None for s in starts):
            prev = max(s for s in starts if s is not None)
            if start_time < prev:
                starts.append(None)
                scores.append(0.0)
                continue
        starts.append(start_time)
        # Name hits are short but reliable — don't mark as low-conf
        scores.append(max(float(score), 12.0) if via_name else float(score))
        cursor_idx = cue_idx + 1

    resolved, fill_notes = _interpolate_starts(starts, scores, audio_end)

    new_segments = []
    for i, seg in enumerate(session["segments"]):
        end = resolved[i + 1] if i + 1 < len(resolved) else max(audio_end, resolved[i] + 0.5)
        if end <= resolved[i]:
            end = resolved[i] + 0.5
        conf = min(1.0, scores[i] / 12.0) if scores[i] else 0.25
        status = "auto"
        preview = srt_preview(cues_raw, resolved[i], end)
        fields = range_fields(resolved[i], end, conf, status, preview)
        note_parts = []
        if fill_notes[i]:
            note_parts.append(fill_notes[i])
        elif conf < 0.4:
            note_parts.append(f"low confidence score={scores[i]}")
        fields["notes"] = "; ".join(note_parts)
        new_segments.append({**seg, **fields})

    opening = session.get("opening")
    if opening or new_segments:
        end = new_segments[0]["start"] if new_segments else audio_end
        intro = normalize("今天是", converter)
        res = match_start(cues, 0, intro, min_len=3, min_block=3, max_scan=40)
        start = res[0] if res else 0.0
        if start >= end:
            start = 0.0
        preview = srt_preview(cues_raw, start, end)
        fields = range_fields(start, end, 0.6, "auto", preview)
        base = opening or {"text_preview": ""}
        opening = {**base, **fields}

    return {**session, "opening": opening, "segments": new_segments, "srt_file": str(srt)}


def merge_session(old: Optional[dict], new: dict) -> dict:
    if not old:
        return new
    out = {**new}
    out["opening"] = _merge_preserve(old.get("opening"), new.get("opening"))
    old_by_key = {}
    for seg in old.get("segments") or []:
        old_by_key[seg.get("stable_key") or f"#{seg.get('index')}"] = seg
    merged_segs = []
    for seg in new.get("segments") or []:
        key = seg.get("stable_key") or f"#{seg.get('index')}"
        prev = old_by_key.get(key)
        if _is_protected(prev):
            # Keep timing from prev, refresh text previews from new
            kept = {**seg, **{k: prev[k] for k in (
                "start", "end", "start_label", "end_label",
                "confidence", "status", "locked", "notes", "srt_preview",
            ) if k in prev}}
            merged_segs.append(kept)
        else:
            merged_segs.append(seg)
    out["segments"] = merged_segs
    return out


def _apply_resolve_media(session: dict, srt_root: Path) -> dict:
    media = resolve_media(
        session["year"], session["month"], session["day"], session["source"],
        srt_root=srt_root,
    )
    out = dict(session)
    out["audio_file"] = media["audio_file"]
    out["srt_file"] = media["srt_file"]
    out["mp3_path"] = media["mp3_path"]
    out["media_fallback"] = media.get("fallback_from")
    out["resolved_source"] = media.get("resolved_source")
    return out


def align_month(
    year: int,
    month: int,
    ebook_dir: Path,
    srt_root: Path,
    converter,
    existing: Dict[str, dict],
) -> dict:
    key = f"{year:04d}-{month:02d}"
    by_month = extract_all(ebook_dir=ebook_dir, srt_root=srt_root, months={key})
    sessions_in = by_month.get(key) or []
    use_qa = (year, month) in QA_TXT_MONTHS

    aligned = []
    stats = {"matched": 0, "missing": 0, "opening_ok": 0, "sessions": 0, "fallbacks": 0}

    for session in sessions_in:
        session = _apply_resolve_media(session, srt_root)
        if session.get("media_fallback"):
            stats["fallbacks"] += 1
        srt = Path(session["srt_file"])
        cues_raw = parse_srt_raw(srt) if srt.exists() else []

        if use_qa:
            result = align_from_qa_txt(session, converter, cues_raw, srt_root)
        else:
            result = align_from_srt(session, converter, srt_root)

        result = merge_session(existing.get(session["session_id"]), result)
        # After merge, force-fill any still-missing via SRT path (skip protected)
        result = _ensure_complete(result, converter, srt_root)
        aligned.append(result)
        stats["sessions"] += 1
        for seg in result["segments"]:
            if seg.get("start") is not None and seg.get("status") != "missing":
                stats["matched"] += 1
            else:
                stats["missing"] += 1
        op = result.get("opening")
        if op and op.get("start") is not None and op.get("status") != "missing":
            stats["opening_ok"] += 1

    return {
        "month": key,
        "version": 1,
        "stats": stats,
        "sessions": aligned,
    }


def _ensure_complete(session: dict, converter, srt_root: Path) -> dict:
    """Re-run SRT align for any unprotected missing segments / opening."""
    needs = False
    op = session.get("opening")
    if op is None or op.get("start") is None or op.get("status") == "missing":
        if not _is_protected(op):
            needs = True
    for seg in session.get("segments") or []:
        if (seg.get("start") is None or seg.get("status") == "missing") and not _is_protected(seg):
            needs = True
            break
    if not needs:
        return session

    srt_filled = align_from_srt(session, converter, srt_root)
    out = dict(session)
    if not _is_protected(session.get("opening")):
        out["opening"] = srt_filled.get("opening")
    segs = []
    filled_by_key = {
        s.get("stable_key") or f"#{s.get('index')}": s
        for s in srt_filled.get("segments") or []
    }
    for seg in session.get("segments") or []:
        if _is_protected(seg) and seg.get("start") is not None:
            segs.append(seg)
            continue
        if seg.get("start") is not None and seg.get("status") != "missing":
            segs.append(seg)
            continue
        key = seg.get("stable_key") or f"#{seg.get('index')}"
        segs.append(filled_by_key.get(key, seg))
    out["segments"] = segs
    out["srt_file"] = srt_filled.get("srt_file", session.get("srt_file"))
    return out


def print_report(payload: dict) -> None:
    stats = payload.get("stats") or {}
    print(
        f"[{payload['month']}] sessions={stats.get('sessions', 0)} "
        f"matched={stats.get('matched', 0)} missing={stats.get('missing', 0)} "
        f"opening_ok={stats.get('opening_ok', 0)} "
        f"fallbacks={stats.get('fallbacks', 0)}"
    )
    for session in payload.get("sessions") or []:
        miss = [s for s in session["segments"] if s.get("status") == "missing" or s.get("start") is None]
        low = [
            s for s in session["segments"]
            if s.get("start") is not None and (s.get("confidence") or 0) < 0.45
        ]
        flag = ""
        if miss:
            flag += f" missing={len(miss)}"
        if low:
            flag += f" low_conf={len(low)}"
        if session.get("media_fallback"):
            flag += f" fallback={session.get('resolved_source')}"
        srt_ok = Path(session.get("srt_file") or "").exists()
        print(
            f"  {session['session_id']}: segs={len(session['segments'])} "
            f"srt={'✓' if srt_ok else '✗'} audio={session.get('audio_file')}{flag}"
        )


def count_missing(payload: dict) -> int:
    n = 0
    for session in payload.get("sessions") or []:
        op = session.get("opening")
        if op is not None and (op.get("start") is None or op.get("status") == "missing"):
            n += 1
        for seg in session.get("segments") or []:
            if seg.get("start") is None or seg.get("status") == "missing":
                n += 1
    return n


def _strip_for_write(payload: dict) -> dict:
    """Drop bulky fields not needed at runtime inject (keep q_preview, drop q_text)."""
    sessions = []
    for s in payload.get("sessions") or []:
        sc = dict(s)
        segs = []
        for seg in sc.get("segments") or []:
            seg2 = {k: v for k, v in seg.items() if k not in ("q_text", "answer_preview")}
            segs.append(seg2)
        sc["segments"] = segs
        sessions.append(sc)
    return {
        "month": payload["month"],
        "version": payload.get("version", 1),
        "stats": payload.get("stats"),
        "sessions": sessions,
    }


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Align PDF sessions to audio ranges")
    parser.add_argument("--month", action="append", help="YYYY-MM (repeatable)")
    parser.add_argument("--ebook-dir", type=Path, default=EBOOK_DIR)
    parser.add_argument("--srt-root", type=Path, default=DEFAULT_SRT_ROOT)
    parser.add_argument("--apply", action="store_true", help="Write mapping JSON")
    parser.add_argument("--report", action="store_true", help="Print match report (default)")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Exit non-zero if any segment/opening is still missing",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore existing mapping (except locked/manual still skipped only if not --fresh)",
    )
    args = parser.parse_args(argv)

    converter = get_converter()
    if converter is None:
        print("warning: OpenCC unavailable; matching quality may drop")

    MAP_DIR.mkdir(parents=True, exist_ok=True)

    if args.month:
        months = []
        for m in args.month:
            y, mo = m.split("-")
            months.append((int(y), int(mo)))
    else:
        months = [
            (2025, 6), (2025, 7), (2025, 8), (2025, 9),
            (2025, 11), (2025, 12),
            (2026, 1), (2026, 2), (2026, 3),
        ]

    total_missing = 0
    for year, month in months:
        path = month_map_path(year, month)
        existing = {} if args.fresh else _load_existing(path)
        payload = align_month(year, month, args.ebook_dir, args.srt_root, converter, existing)
        print_report(payload)
        total_missing += count_missing(payload)
        if args.apply:
            out = _strip_for_write(payload)
            path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"  wrote {path}")

    if not args.apply:
        print("(dry-run; pass --apply to write)")
    print(f"TOTAL missing items: {total_missing}")
    if args.require_complete and total_missing:
        print(f"ERROR: --require-complete failed ({total_missing} missing)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
