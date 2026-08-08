#!/usr/bin/env python3
"""Backfill ``closing`` onto existing audio_map JSON from ebook HTML + SRT."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Optional

from closing import attach_closing_to_session, closing_text_from_section
from common import EBOOK_DIR, H2_RE, MAP_DIR, QUESTION_BLOCK_RE


def _sections_by_id(ebook_dir: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for path in sorted(ebook_dir.glob("[0-9][0-9].html")):
        html = path.read_text(encoding="utf-8")
        matches = list(H2_RE.finditer(html))
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
            out[m.group(1)] = html[m.start() : end]
    return out


def closing_text_for_session(session: dict, sections: Dict[str, str]) -> str:
    existing = (session.get("closing") or {}).get("text") or ""
    if existing:
        return existing
    sid = session.get("section_id") or ""
    section = sections.get(sid) or ""
    if not section:
        return ""
    q_matches = list(QUESTION_BLOCK_RE.finditer(section))
    if not q_matches:
        return ""
    return closing_text_from_section(section, q_matches[-1].start())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", action="append")
    parser.add_argument("--session", action="append")
    parser.add_argument("--ebook-dir", type=Path, default=EBOOK_DIR)
    parser.add_argument("--force", action="store_true", help="Overwrite manual closing ranges")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    months = args.month or [
        p.stem
        for p in sorted(MAP_DIR.glob("*.json"))
        if re.fullmatch(r"\d{4}-\d{2}", p.stem)
    ]
    sections = _sections_by_id(args.ebook_dir)
    print(f"ebook sections indexed: {len(sections)}")

    grand = {"sessions": 0, "ok": 0, "missing": 0, "skipped": 0}

    for month in months:
        path = MAP_DIR / f"{month}.json"
        if not path.exists():
            print(f"[{month}] missing map")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        new_sessions = []
        month_n = 0
        for session in data.get("sessions") or []:
            if args.session and session.get("session_id") not in args.session:
                new_sessions.append(session)
                continue
            grand["sessions"] += 1
            text = closing_text_for_session(session, sections)
            updated = attach_closing_to_session(
                session, closing_text=text or None, force=args.force
            )
            cl = updated.get("closing") or {}
            st = cl.get("start")
            status = cl.get("status")
            if st is not None and status != "missing":
                grand["ok"] += 1
                tag = "OK"
            elif cl.get("text"):
                grand["missing"] += 1
                tag = "TEXT-NO-RANGE"
            else:
                grand["skipped"] += 1
                tag = "NO-TEXT"
            print(
                f"  {session.get('session_id')}: {tag} "
                f"start={st} end={cl.get('end')} "
                f"text={(cl.get('text') or '')[:36]!r}"
            )
            month_n += 1
            new_sessions.append(updated)
        data["sessions"] = new_sessions
        # refresh stats if present
        if "stats" in data and isinstance(data["stats"], dict):
            data["stats"]["closing_ok"] = sum(
                1
                for s in new_sessions
                if (s.get("closing") or {}).get("start") is not None
                and (s.get("closing") or {}).get("status") != "missing"
            )
        if args.apply and month_n:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"[{month}] wrote {path}")
        else:
            print(f"[{month}] dry-run ({month_n} sessions)")

    print(
        f"TOTAL sessions={grand['sessions']} ok={grand['ok']} "
        f"text_no_range={grand['missing']} no_text={grand['skipped']}"
    )
    if not args.apply:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
