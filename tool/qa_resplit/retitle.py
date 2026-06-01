#!/usr/bin/env python3
"""Apply curated, content-accurate segment titles to QA txt files.

Titles are stored as per-file JSON maps in tool/qa_resplit/titles/<stem>.json,
shaped {"<segment number>": "<title>"}. Only the heading lines
(### N. ...) are rewritten; question/answer text is never touched.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QA_DIR = ROOT / "qa"
TITLES_DIR = Path(__file__).resolve().parent / "titles"
HEADING_RE = re.compile(r"^(###\s+)(\d+)(\.\s*)(.*?)(\s*)$", re.M)


def title_map_for(path: Path) -> Path:
    return TITLES_DIR / f"{path.stem}.json"


def apply_titles(path: Path, titles: dict[str, str], apply: bool) -> tuple[int, list[str]]:
    text = path.read_text(encoding="utf-8")
    warnings: list[str] = []
    seen: set[str] = set()
    changed = 0

    def replace(match: re.Match) -> str:
        nonlocal changed
        number = match.group(2)
        seen.add(number)
        new_title = titles.get(number)
        if new_title is None:
            warnings.append(f"{path.name}: 第 {number} 段沒有新標題")
            return match.group(0)
        if not new_title.strip():
            warnings.append(f"{path.name}: 第 {number} 段標題為空")
            return match.group(0)
        old_title = match.group(4)
        if old_title != new_title:
            changed += 1
        return f"{match.group(1)}{number}{match.group(3)}{new_title}"

    updated = HEADING_RE.sub(replace, text)
    for number in titles:
        if number not in seen:
            warnings.append(f"{path.name}: JSON 有第 {number} 段，但檔案沒有此標題")
    if apply and updated != text:
        path.write_text(updated, encoding="utf-8")
    return changed, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", help="qa txt files; defaults to every file with a titles JSON")
    parser.add_argument("--apply", action="store_true", help="write changes")
    args = parser.parse_args(argv)

    if args.paths:
        files = [Path(p) if Path(p).is_absolute() else ROOT / p for p in args.paths]
    else:
        files = sorted(
            QA_DIR / f"{json_path.stem}.txt"
            for json_path in TITLES_DIR.glob("*.json")
        )

    total_changed = 0
    all_warnings: list[str] = []
    for path in files:
        map_path = title_map_for(path)
        if not map_path.exists():
            all_warnings.append(f"{path.name}: 找不到標題對照檔 {map_path.name}")
            continue
        titles = json.loads(map_path.read_text(encoding="utf-8"))
        changed, warnings = apply_titles(path, titles, args.apply)
        total_changed += changed
        all_warnings.extend(warnings)
        print(f"{'updated' if args.apply else 'would update'}\t{path.name}\tchanged={changed}")

    if all_warnings:
        print("\n".join(all_warnings))
    print(f"files={len(files)} total_changed={total_changed} apply={args.apply} warnings={len(all_warnings)}")
    return 1 if all_warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
