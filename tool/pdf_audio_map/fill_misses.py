#!/usr/bin/env python3
"""Fill all audio_map misses: align → retranscribe miss sessions → realign → verify."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

from align import align_month, count_missing, print_report, _load_existing, _strip_for_write
from common import (
    DEFAULT_SRT_ROOT,
    EBOOK_DIR,
    MAP_DIR,
    SENSE_VOICE_PYTHON,
    SENSE_VOICE_TRANSCRIBE,
    get_converter,
    month_map_path,
)


DEFAULT_MONTHS = [
    (2025, 6), (2025, 7), (2025, 8), (2025, 9),
    (2025, 11), (2025, 12),
    (2026, 1), (2026, 2), (2026, 3),
]


def _months_from_args(month_args: Optional[List[str]]) -> List[Tuple[int, int]]:
    if not month_args:
        return list(DEFAULT_MONTHS)
    out = []
    for m in month_args:
        y, mo = m.split("-")
        out.append((int(y), int(mo)))
    return out


def _write_month(payload: dict) -> Path:
    path = MAP_DIR / f"{payload['month']}.json"
    path.write_text(
        json.dumps(_strip_for_write(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _sessions_needing_retranscribe(payload: dict) -> List[dict]:
    """Only sessions with hard misses (null start / missing status) need ASR."""
    need = []
    for session in payload.get("sessions") or []:
        hard = [
            s for s in session.get("segments") or []
            if s.get("start") is None or s.get("status") == "missing"
        ]
        op = session.get("opening") or {}
        op_bad = bool(op) and (op.get("start") is None or op.get("status") == "missing")
        if hard or op_bad:
            need.append(session)
    return need


def _retranscribe(mp3: Path) -> bool:
    if not mp3.exists():
        print(f"  SKIP retranscribe — mp3 missing: {mp3}")
        return False
    if not SENSE_VOICE_PYTHON.exists():
        print(f"  ERROR: sense_voice venv missing: {SENSE_VOICE_PYTHON}")
        return False
    out_base = mp3.with_suffix("")  # same dir / stem
    cmd = [
        str(SENSE_VOICE_PYTHON),
        str(SENSE_VOICE_TRANSCRIBE),
        str(mp3),
        "-o",
        str(out_base),
    ]
    print(f"  sense_voice: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"  ERROR: retranscribe failed ({exc.returncode}): {mp3.name}")
        return False
    srt = out_base.with_suffix(".srt")
    if not srt.exists():
        print(f"  ERROR: SRT not produced: {srt}")
        return False
    print(f"  wrote {srt}")
    return True


def run_pass(
    months: List[Tuple[int, int]],
    ebook_dir: Path,
    srt_root: Path,
    converter,
    fresh: bool,
) -> Tuple[int, List[dict]]:
    """Align all months; return (total_missing, payloads)."""
    payloads = []
    total = 0
    for year, month in months:
        path = month_map_path(year, month)
        existing = {} if fresh else _load_existing(path)
        payload = align_month(year, month, ebook_dir, srt_root, converter, existing)
        print_report(payload)
        _write_month(payload)
        print(f"  wrote {path}")
        total += count_missing(payload)
        payloads.append(payload)
    return total, payloads


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Fill audio_map misses via sense_voice + realign")
    parser.add_argument("--month", action="append", help="YYYY-MM (repeatable)")
    parser.add_argument("--ebook-dir", type=Path, default=EBOOK_DIR)
    parser.add_argument("--srt-root", type=Path, default=DEFAULT_SRT_ROOT)
    parser.add_argument("--max-rounds", type=int, default=2, help="Retranscribe rounds")
    parser.add_argument("--skip-retranscribe", action="store_true", help="Only realign, no ASR")
    parser.add_argument("--fresh", action="store_true", help="Ignore prior mapping on first pass")
    args = parser.parse_args(argv)

    months = _months_from_args(args.month)
    converter = get_converter()
    MAP_DIR.mkdir(parents=True, exist_ok=True)

    print("=== pass 0: align ===")
    missing, payloads = run_pass(months, args.ebook_dir, args.srt_root, converter, fresh=args.fresh)
    print(f"missing after align: {missing}")

    retranscribed: Set[str] = set()
    for round_i in range(1, args.max_rounds + 1):
        if missing == 0:
            break
        if args.skip_retranscribe:
            print("skip retranscribe requested")
            break

        print(f"=== pass {round_i}: retranscribe ===")
        todo_mp3: List[Path] = []
        for payload in payloads:
            for session in _sessions_needing_retranscribe(payload):
                mp3 = Path(session.get("mp3_path") or "")
                key = str(mp3)
                if key in retranscribed:
                    continue
                if not mp3.exists():
                    # try resolve from audio_file stem
                    stem = (session.get("audio_file") or "").replace(".opus", "")
                    year = stem[:4]
                    mp3 = args.srt_root / f"{year}答疑音頻" / f"{stem}.mp3"
                if mp3.exists():
                    todo_mp3.append(mp3)
                    retranscribed.add(str(mp3))
                else:
                    print(f"  no mp3 for {session.get('session_id')}")

        # unique preserve order
        seen = set()
        unique = []
        for p in todo_mp3:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        print(f"  retranscribing {len(unique)} files")
        for mp3 in unique:
            _retranscribe(mp3)

        print(f"=== pass {round_i}: realign ===")
        missing, payloads = run_pass(
            months, args.ebook_dir, args.srt_root, converter, fresh=True
        )
        print(f"missing after round {round_i}: {missing}")

    print(f"FINAL missing items: {missing}")
    if missing:
        print("ERROR: still have misses — inspect audio_map JSON")
        for payload in payloads:
            for session in payload.get("sessions") or []:
                hard = [
                    s for s in session.get("segments") or []
                    if s.get("start") is None or s.get("status") == "missing"
                ]
                op = session.get("opening") or {}
                if hard or op.get("start") is None:
                    print(
                        f"  {session['session_id']}: hard_miss={len(hard)} "
                        f"srt={session.get('srt_file')} mp3={session.get('mp3_path')}"
                    )
        return 1

    print("OK: zero misses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
