#!/usr/bin/env python3
"""Resplit QA proofing txt files into finer question-level segments.

The source QA files are Traditional Chinese edited transcripts. The SRT files
are Simplified Chinese ASR output with accurate cue timestamps. This script
keeps the edited transcript text, uses the SRT only to refine time boundaries,
and writes parser-friendly QA txt files.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import re
import sys
from pathlib import Path
from typing import Iterable

try:
    from opencc import OpenCC
except Exception:  # pragma: no cover - opencc is optional for validation-only use
    OpenCC = None


ROOT = Path(__file__).resolve().parents[2]
QA_DIR = ROOT / "qa"
AUDIO_ROOT = Path.home() / "Documents"
ANSWER_LABEL = "Taiguanglin："

HEADING_RE = re.compile(r"^###\s+(\d+)\.\s*(.*?)\s*$", re.M)
TIME_RE = re.compile(
    r"時間：\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})"
)
OPEN_TIME_RE = re.compile(
    r"開場時間：\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})"
)
META_RE = re.compile(r"^最後(?:播放|編輯)：.*$", re.M)
QUESTION_LINE_RE = re.compile(r"^[ \t]*(?P<label>提問|追加問題)[:：][ \t]*(?P<text>.*)$", re.M)
ANSWER_MARKER_RE = re.compile(r"^(?:Tai師父答疑|Taiguanglin|答)[:：]\s*$", re.M)
SRT_BLOCK_RE = re.compile(
    r"\s*(\d+)\s*\n"
    r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n"
    r"(.*?)(?=\n\s*\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->|$)",
    re.S,
)


@dataclasses.dataclass
class Cue:
    idx: int
    start: float
    end: float
    text: str
    norm: str


@dataclasses.dataclass
class RawSegment:
    title: str
    start: float
    end: float
    body: str


@dataclasses.dataclass
class NewSegment:
    title: str
    start: float
    end: float
    question: str
    answer: str
    source_title: str
    prefer_answer_time: bool = False
    confidence: float = 0.0


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def parse_timecode(value: str) -> float:
    value = value.replace(",", ".")
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def format_timecode(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    millis_total = int(round(seconds * 1000))
    hours, rem = divmod(millis_total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    whole, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole:02d}.{millis:03d}"


def get_converter():
    if OpenCC is None:
        return None
    return OpenCC("t2s")


def normalize_text(text: str, converter=None) -> str:
    if converter is not None:
        text = converter.convert(text)
    text = text.lower()
    return re.sub(r"[\s\W_，。？！、；：：“”‘’「」『』（）()《》〈〉—…·\-]+", "", text)


def srt_path_for(qa_path: Path) -> Path:
    year = qa_path.name[:4]
    return AUDIO_ROOT / f"{year}答疑音頻" / f"{qa_path.stem}.srt"


def parse_srt(path: Path, converter=None) -> list[Cue]:
    text = read_text(path).replace("\r\n", "\n")
    cues: list[Cue] = []
    for match in SRT_BLOCK_RE.finditer(text):
        idx = int(match.group(1))
        cue_text = " ".join(line.strip() for line in match.group(4).strip().splitlines())
        cues.append(
            Cue(
                idx=idx,
                start=parse_timecode(match.group(2)),
                end=parse_timecode(match.group(3)),
                text=cue_text,
                norm=normalize_text(cue_text, converter),
            )
        )
    return cues


def normalize_malformed_headings(text: str) -> str:
    # Headings occasionally got pasted onto the previous answer line. Parser.js
    # only sees headings at line start, so always isolate them.
    text = re.sub(r"(?<!^)(?<!\n)(###\s+\d+\.\s*)", r"\n\n\1", text)
    text = re.sub(r"\n{3,}(###\s+\d+\.)", r"\n\n\1", text)
    return text


def parse_raw_segments(text: str) -> tuple[str, list[RawSegment]]:
    text = normalize_malformed_headings(text)
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return text, []
    header = text[: matches[0].start()]
    segments: list[RawSegment] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        raw = text[start:end].strip("\n")
        time_match = TIME_RE.search(raw)
        if not time_match:
            continue
        body_start = time_match.end()
        body = raw[body_start:].strip("\n")
        body = META_RE.sub("", body)
        body = re.sub(r"^時間：.*$", "", body, flags=re.M)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        segments.append(
            RawSegment(
                title=match.group(2).strip(),
                start=parse_timecode(time_match.group(1)),
                end=parse_timecode(time_match.group(2)),
                body=body,
            )
        )
    return header, segments


def clean_header(header: str) -> str:
    header = META_RE.sub("", header)
    header = normalize_malformed_headings(header)
    return header.strip("\n") + "\n\n"


def normalize_answer_markers(text: str) -> str:
    text = re.sub(r"^[ \t]*Tai師父答疑[:：][ \t]*", ANSWER_LABEL + "\n\n", text, flags=re.M)
    text = re.sub(r"^[ \t]*Taiguanglin[:：][ \t]*", ANSWER_LABEL + "\n\n", text, flags=re.M)
    text = re.sub(r"^[ \t]*答[:：][ \t]*", ANSWER_LABEL + "\n\n", text, flags=re.M)
    return text


def split_question_text(question: str) -> list[str]:
    prefix = ""
    body = question.strip()
    bracket = re.match(r"^(\[[^\]]+\]\s*)(.*)$", body)
    if bracket:
        prefix = bracket.group(1)
        body = bracket.group(2).strip()

    # Split explicit multi-question summaries. Keep punctuation on each part.
    parts = re.split(r"(?<=[？?])\s*|[；;]\s*|(?<!，)還有|以及", body)
    cleaned: list[str] = []
    for part in parts:
        part = part.strip(" ，,。；;")
        if not part:
            continue
        if prefix and not part.startswith("["):
            part = prefix + part
        cleaned.append(part)

    # Avoid turning a comma-separated title-like summary into too many tiny
    # parts. Aggressive splitting is for clear separate questions/topics.
    return cleaned if len(cleaned) > 1 else [question.strip()]


def split_answer_paragraphs(answer: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", answer.strip()) if p.strip()]
    return paragraphs or [answer.strip()]


def ensure_answer_marker(unit_text: str) -> tuple[str, str]:
    unit_text = normalize_answer_markers(unit_text).strip()
    question_match = QUESTION_LINE_RE.search(unit_text)
    if not question_match:
        return "", unit_text

    question = question_match.group("text").strip()
    after_question = unit_text[question_match.end() :].strip()
    marker = re.search(rf"^{re.escape(ANSWER_LABEL)}\s*$", after_question, flags=re.M)
    if marker:
        answer = after_question[marker.end() :].strip()
    else:
        answer = after_question.strip()
    return question, answer


def extract_units(segment: RawSegment) -> list[tuple[str, str]]:
    text = normalize_answer_markers(segment.body)
    matches = list(QUESTION_LINE_RE.finditer(text))
    if not matches:
        marker = re.search(rf"^{re.escape(ANSWER_LABEL)}\s*$", text, flags=re.M)
        if marker:
            return [("", text[marker.end() :].strip())]
        return [("", text.strip())]

    units: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        unit_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        units.append(ensure_answer_marker(text[match.start() : unit_end]))
    return units


def title_from_question(question: str, fallback: str) -> str:
    text = re.sub(r"^\[[^\]]+\]\s*", "", question).strip()
    text = re.sub(r"^(第[一二三四五六七八九十百千零〇兩\d]+個問題[，,：:\s]*)", "", text)
    text = re.split(r"[。？?；;，,]", text)[0].strip()
    if not text:
        text = fallback
    text = re.sub(r"^(關於|问|問)", "", text).strip()
    if len(text) > 22:
        text = text[:22]
    return f"關於{text}" if text else fallback


def split_segment(segment: RawSegment) -> list[NewSegment]:
    result: list[NewSegment] = []
    for question, answer in extract_units(segment):
        question_parts = split_question_text(question) if question else [""]
        answer_paragraphs = split_answer_paragraphs(answer)

        should_split = len(question_parts) > 1 and len(answer_paragraphs) > 1
        if not should_split:
            result.append(
                NewSegment(
                    title=title_from_question(question, segment.title),
                    start=segment.start,
                    end=segment.end,
                    question=question,
                    answer=answer.strip(),
                    source_title=segment.title,
                )
            )
            continue

        # Pair early answer paragraphs with early question parts and attach the
        # remaining paragraphs to the last question part. This favors useful
        # audio boundaries while preserving all edited answer text.
        groups: list[list[str]] = [[] for _ in question_parts]
        for idx, paragraph in enumerate(answer_paragraphs):
            target = min(idx, len(groups) - 1)
            groups[target].append(paragraph)
        for idx, q in enumerate(question_parts):
            answer_text = "\n\n".join(groups[idx]).strip()
            if not answer_text:
                continue
            result.append(
                NewSegment(
                    title=title_from_question(q, segment.title),
                    start=segment.start,
                    end=segment.end,
                    question=q,
                    answer=answer_text,
                    source_title=segment.title,
                    prefer_answer_time=idx > 0,
                )
            )
    return result


def cue_window_text(cues: list[Cue], start_idx: int, size: int) -> str:
    return "".join(cue.norm for cue in cues[start_idx : start_idx + size])


def best_cue_time(
    needle: str,
    cues: list[Cue],
    lo: float,
    hi: float,
    converter=None,
) -> tuple[float | None, float]:
    norm = normalize_text(needle, converter)
    if len(norm) < 6:
        return None, 0.0
    norm = norm[:80]
    candidates = [c for c in cues if c.start >= lo - 0.25 and c.start <= hi + 0.25]
    if not candidates:
        return None, 0.0

    best_start: float | None = None
    best_score = 0.0
    for i, cue in enumerate(candidates):
        # Try short cue windows because a phrase often spans ASR cue boundaries.
        for size in (1, 2, 3, 4, 5):
            text = cue_window_text(candidates, i, size)
            if not text:
                continue
            if norm in text:
                score = 1.0
            else:
                score = difflib.SequenceMatcher(None, norm, text[: max(len(norm) + 20, 40)]).ratio()
            if score > best_score:
                best_score = score
                best_start = cue.start
    if best_score < 0.34:
        return None, best_score
    return best_start, best_score


def first_answer_phrase(answer: str) -> str:
    text = re.sub(r"\s+", "", answer.strip())
    return text[:60]


def align_times(new_segments: list[NewSegment], raw_segments: list[RawSegment], cues: list[Cue], converter=None) -> None:
    # Align within each original raw segment so unrelated repeated phrases do
    # not steal timestamps from other parts of the audio.
    by_source: dict[str, list[NewSegment]] = {}
    for segment in new_segments:
        key = f"{segment.source_title}|{segment.start:.3f}|{segment.end:.3f}"
        by_source.setdefault(key, []).append(segment)

    for raw in raw_segments:
        key = f"{raw.title}|{raw.start:.3f}|{raw.end:.3f}"
        children = by_source.get(key, [])
        if not children:
            continue
        starts: list[float] = []
        prev = raw.start
        for idx, child in enumerate(children):
            if idx == 0:
                starts.append(raw.start)
                prev = raw.start
                continue
            answer_needle = first_answer_phrase(child.answer)
            question_needle = child.question
            if child.prefer_answer_time:
                found, score = best_cue_time(answer_needle, cues, prev + 0.05, raw.end, converter)
                if found is None:
                    found, score = best_cue_time(question_needle, cues, prev + 0.05, raw.end, converter)
            else:
                found, score = best_cue_time(question_needle, cues, prev + 0.05, raw.end, converter)
                if found is None:
                    found, score = best_cue_time(answer_needle, cues, prev + 0.05, raw.end, converter)
            if found is None or found <= prev:
                # Fall back to a proportional split, then keep it monotonic.
                span = max(raw.end - raw.start, len(children) * 0.5)
                found = raw.start + span * idx / len(children)
                score = 0.0
            starts.append(found)
            child.confidence = score
            prev = found
        starts = make_monotonic(starts, raw.start, raw.end)
        for i, child in enumerate(children):
            child.start = starts[i]
            child.end = starts[i + 1] if i + 1 < len(starts) else raw.end


def make_monotonic(starts: list[float], lo: float, hi: float) -> list[float]:
    fixed: list[float] = []
    prev = lo - 0.001
    for value in starts:
        value = max(lo, min(value, hi))
        if value <= prev:
            value = min(hi, prev + 0.001)
        fixed.append(value)
        prev = value
    return fixed


def serialize(header: str, segments: list[NewSegment]) -> str:
    parts = [clean_header(header)]
    for idx, segment in enumerate(segments, 1):
        # Format A: the question is the heading; no standalone 提問 line.
        heading_text = (segment.question or segment.title or "").strip()
        parts.append(
            "\n".join(
                [
                    f"### {idx}. {heading_text}",
                    f"時間：{format_timecode(segment.start)} - {format_timecode(segment.end)}",
                    "最後播放：",
                    "最後編輯：",
                    ANSWER_LABEL,
                    segment.answer.strip(),
                    "",
                ]
            )
        )
    return "\n".join(parts).rstrip() + "\n"


def process_file(path: Path, apply: bool = False) -> tuple[str, int, int]:
    converter = get_converter()
    srt = srt_path_for(path)
    if not srt.exists():
        raise FileNotFoundError(f"Missing SRT for {path.name}: {srt}")
    original = read_text(path)
    header, raw_segments = parse_raw_segments(original)
    cues = parse_srt(srt, converter)
    new_segments: list[NewSegment] = []
    for raw in raw_segments:
        new_segments.extend(split_segment(raw))
    align_times(new_segments, raw_segments, cues, converter)
    output = serialize(header, new_segments)
    if apply and output != original:
        write_text(path, output)
    return path.name, len(raw_segments), len(new_segments)


def qa_files(paths: Iterable[str]) -> list[Path]:
    if paths:
        return [Path(p) if Path(p).is_absolute() else ROOT / p for p in paths]
    return sorted(QA_DIR.glob("*.txt"), reverse=True)


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = read_text(path)
    for lineno, line in enumerate(text.splitlines(), 1):
        if "Tai師父答疑" in line:
            errors.append(f"{path.name}:{lineno}: old answer marker")
        if "###" in line and not line.startswith("###"):
            errors.append(f"{path.name}:{lineno}: heading not at line start")
        if line.strip() in {"Taiguanglin:", "Taiguanglin："} and line != ANSWER_LABEL:
            errors.append(f"{path.name}:{lineno}: nonstandard answer marker")

    headings = list(HEADING_RE.finditer(text))
    ranges = []
    for line in text.splitlines():
        if line.startswith("時間："):
            match = TIME_RE.search(line)
            if match:
                ranges.append(match)
    if len(headings) != len(ranges):
        errors.append(f"{path.name}: headings={len(headings)} time_ranges={len(ranges)}")
    for i, heading in enumerate(headings):
        start = heading.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        raw = text[start:end]
        if raw.count(ANSWER_LABEL) != 1:
            errors.append(f"{path.name}: segment {i + 1} answer_marker_count={raw.count(ANSWER_LABEL)}")
        # Format A: the question lives in the heading; the old standalone 提問
        # line must be gone, and the heading text must be non-empty.
        question_lines = QUESTION_LINE_RE.findall(raw)
        if len(question_lines) != 0:
            errors.append(f"{path.name}: segment {i + 1} stray_提問_line={len(question_lines)}")
        if not heading.group(2).strip():
            errors.append(f"{path.name}: segment {i + 1} empty_heading_question")
        last_played_lines = len(re.findall(r"^最後播放：.*$", raw, flags=re.M))
        last_edited_lines = len(re.findall(r"^最後編輯：.*$", raw, flags=re.M))
        if last_played_lines != 1:
            errors.append(f"{path.name}: segment {i + 1} last_played_line_count={last_played_lines}")
        if last_edited_lines != 1:
            errors.append(f"{path.name}: segment {i + 1} last_edited_line_count={last_edited_lines}")
    last_start = -1.0
    for match in ranges:
        start = parse_timecode(match.group(1))
        end = parse_timecode(match.group(2))
        if end < start:
            errors.append(f"{path.name}: negative range {match.group(0)}")
        if start < last_start:
            errors.append(f"{path.name}: non-monotonic range {match.group(0)}")
        last_start = start
    return errors


def coverage(files: list[Path]) -> int:
    missing = []
    for path in files:
        srt = srt_path_for(path)
        if not srt.exists():
            missing.append((path, srt))
    print(f"qa_txt_count={len(files)}")
    print(f"missing_srt_count={len(missing)}")
    for path, srt in missing:
        print(f"MISSING\t{path.relative_to(ROOT)}\t{srt}")
    return 1 if missing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", help="Specific qa txt files; defaults to all qa/*.txt")
    parser.add_argument("--apply", action="store_true", help="Write changes")
    parser.add_argument("--coverage", action="store_true", help="Check matching SRT coverage")
    parser.add_argument("--validate", action="store_true", help="Validate parser-facing format")
    args = parser.parse_args(argv)

    files = qa_files(args.paths)
    if args.coverage:
        return coverage(files)
    if args.validate:
        errors: list[str] = []
        for path in files:
            errors.extend(validate_file(path))
        if errors:
            print("\n".join(errors))
            return 1
        print(f"validated_files={len(files)}")
        return 0

    for path in files:
        name, old_count, new_count = process_file(path, apply=args.apply)
        print(f"{name}\t{old_count}->{new_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
