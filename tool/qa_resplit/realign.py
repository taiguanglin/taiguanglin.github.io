#!/usr/bin/env python3
"""Re-derive each QA segment's start time from the SRT.

師父 reads every question aloud right before answering, so each segment's true
start is where its question text appears in the subtitle timeline. The original
auto-split aligned *within* each raw segment, which made grouped questions
(several sub-questions sharing one spoken answer) cascade-drift every later
boundary. This tool matches each segment's question (then answer opening as a
fallback) against the whole SRT, in order, and rewrites only the 時間：lines.

Report-only by default; pass --apply to write. Text is never touched.
"""

from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path

try:
    from opencc import OpenCC
except Exception:  # pragma: no cover
    OpenCC = None

ROOT = Path(__file__).resolve().parents[2]
QA_DIR = ROOT / "qa"
AUDIO_ROOT = Path.home() / "Documents"

HEADING_RE = re.compile(r"^###\s+(\d+)\.\s*(.*?)\s*$", re.M)
TIME_LINE_RE = re.compile(
    r"^(時間：\s*)(\d{2}:\d{2}:\d{2}[.,]\d{3})(\s*-\s*)(\d{2}:\d{2}:\d{2}[.,]\d{3})(\s*)$",
    re.M,
)
QUESTION_RE = re.compile(r"^[ \t]*(?:提問|追加問題)[:：][ \t]*(.*)$", re.M)
ANSWER_RE = re.compile(r"^Taiguanglin[:：]\s*$", re.M)
SRT_BLOCK_RE = re.compile(
    r"(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)",
    re.S,
)
PUNCT_RE = re.compile(r"[\s\W_，。？！、；：“”‘’「」『』（）()《》〈〉—…·\-]+")


def get_converter():
    return OpenCC("t2s") if OpenCC is not None else None


def normalize(text: str, converter=None) -> str:
    if converter is not None:
        text = converter.convert(text)
    return PUNCT_RE.sub("", text.lower())


def parse_tc(value: str) -> float:
    value = value.replace(",", ".")
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def fmt_tc(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def srt_path_for(qa_path: Path) -> Path:
    year = qa_path.name[:4]
    return AUDIO_ROOT / f"{year}答疑音頻" / f"{qa_path.stem}.srt"


def parse_srt(path: Path, converter=None):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    cues = []
    for m in SRT_BLOCK_RE.finditer(text):
        body = " ".join(line.strip() for line in m.group(4).splitlines() if line.strip())
        cues.append((parse_tc(m.group(2)), parse_tc(m.group(3)), normalize(body, converter)))
    return cues


class Segment:
    __slots__ = ("number", "title", "time_match", "start", "end", "question", "answer", "_new")

    def __init__(self, number, title, time_match, start, end, question, answer):
        self.number = number
        self.title = title
        self.time_match = time_match
        self.start = start
        self.end = end
        self.question = question
        self.answer = answer


def parse_segments(text: str):
    headings = list(HEADING_RE.finditer(text))
    segments = []
    for i, h in enumerate(headings):
        block_start = h.start()
        block_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[block_start:block_end]
        tm = TIME_LINE_RE.search(block)
        if not tm:
            continue
        # Format A: the question is the heading text. Fall back to a legacy
        # 提問 line if the heading happens to be empty.
        question = h.group(2).strip()
        if not question:
            qm = QUESTION_RE.search(block)
            question = qm.group(1).strip() if qm else ""
        am = ANSWER_RE.search(block)
        answer = block[am.end():].strip() if am else ""
        segments.append(
            Segment(
                number=h.group(1),
                title=h.group(2),
                time_match=(block_start + tm.start(), block_start + tm.end(), tm.groups()),
                start=parse_tc(tm.group(2)),
                end=parse_tc(tm.group(4)),
                question=question,
                answer=answer,
            )
        )
    return segments


def strip_prefix(question: str) -> str:
    return re.sub(r"^\s*\[[^\]]*\]\s*", "", question)


def _window(cues, i, need_len):
    """Concatenate cues[i:] until we cover need_len chars (max 8 cues).

    Returns (window_text, cue_indices) where cue_indices[k] is the cue that
    window char k belongs to.
    """
    text = []
    owners = []
    j = i
    wl = 0
    while j < len(cues) and wl < need_len + 14 and j < i + 8:
        norm = cues[j][2]
        text.append(norm)
        owners.extend([j] * len(norm))
        wl += len(norm)
        j += 1
    return "".join(text), owners


def match_start(cues, cursor_idx, needle, min_len, min_block=6, max_scan=340):
    """Find the cue where `needle` (a question) is first read aloud.

    師父 reads the question's opening right at the segment boundary, then often
    paraphrases. So we look for the EARLIEST cue whose window contains a long
    contiguous block aligned to the START of the needle (block offset in needle
    near 0). This locks onto the question's first reading and ignores later
    keyword recurrences inside a long answer.

    Returns (start_time, cue_index, block_size) or None.
    """
    if len(needle) < min_len:
        return None
    n = len(needle)
    best = None  # (size, cue_idx)
    end_idx = min(len(cues), cursor_idx + max_scan)
    for i in range(cursor_idx, end_idx):
        win, owners = _window(cues, i, n)
        if not win:
            continue
        m = difflib.SequenceMatcher(None, win, needle, autojunk=False).find_longest_match(
            0, len(win), 0, n
        )
        if best is None or m.size > best[0]:
            best = (m.size, i)
        # Block aligned to needle start => this is where the question begins.
        if m.size >= min_block and m.b <= 4:
            qpos = max(0, m.a - m.b)
            owner = owners[qpos] if qpos < len(owners) else i
            return cues[owner][0], owner, m.size
    if best is None or best[0] < max(4, min_block - 2):
        return None
    return cues[best[1]][0], best[1], best[0]


def realign(path: Path, converter, apply: bool):
    text = path.read_text(encoding="utf-8")
    segments = parse_segments(text)
    srt = srt_path_for(path)
    if not srt.exists():
        return None, [f"{path.name}: 找不到 SRT {srt.name}"]
    cues = parse_srt(srt, converter)
    if not cues:
        return None, [f"{path.name}: SRT 無 cue"]
    audio_end = cues[-1][1]

    rows = []
    cursor_idx = 0
    new_starts: list[float | None] = []
    for seg in segments:
        q = normalize(strip_prefix(seg.question), converter)[:70]
        res = match_start(cues, cursor_idx, q, min_len=6)
        if res is None and seg.answer:
            a = normalize(seg.answer, converter)[:60]
            res = match_start(cues, cursor_idx, a, min_len=8)
        if res is None:
            # Global re-anchor. The forward cursor can lose the thread when
            # questions are answered out of the order they appear in the txt
            # (common in 貼吧 sessions) or were crammed at a single timestamp by
            # the original splitter. Search the WHOLE SRT, but require a long
            # contiguous block aligned to the start so we only re-anchor on
            # genuine transcript text (username-only 提問 stay unmatched).
            gq = normalize(strip_prefix(seg.question), converter)[:80]
            res = match_start(cues, 0, gq, min_len=12, min_block=12, max_scan=len(cues))
            if res is None and seg.answer:
                ga = normalize(seg.answer, converter)[:90]
                res = match_start(cues, 0, ga, min_len=14, min_block=14, max_scan=len(cues))
        if res is None:
            new_starts.append(None)
            rows.append((seg, None, 0))
            continue
        start_time, cue_idx, score = res
        new_starts.append(start_time)
        cursor_idx = cue_idx + 1
        rows.append((seg, start_time, round(score, 2)))

    # Fill unmatched starts by interpolation, keep monotonic.
    resolved = []
    for i, s in enumerate(new_starts):
        if s is None:
            s = segments[i].start  # keep original if unmatched
        resolved.append(s)
    for i in range(1, len(resolved)):
        if resolved[i] <= resolved[i - 1]:
            resolved[i] = resolved[i - 1] + 0.05

    # End of each segment = start of next; last = audio end.
    warnings = []
    changes = 0
    for i, seg in enumerate(segments):
        ns = resolved[i]
        ne = resolved[i + 1] if i + 1 < len(segments) else max(audio_end, ns + 0.5)
        old = f"{fmt_tc(seg.start)}-{fmt_tc(seg.end)}"
        new = f"{fmt_tc(ns)}-{fmt_tc(ne)}"
        moved = abs(ns - seg.start) > 1.0 or abs(ne - seg.end) > 1.0
        gap = ne - ns
        flag = ""
        if rows[i][1] is None:
            flag = "  ⚠ 未匹配(保留原值)"
            warnings.append(f"{path.name}: 第{seg.number}段問題未匹配字幕")
        if gap < 1.0:
            flag += "  ⚠ 區間過短(疑似應合併)"
        if moved or flag:
            changes += 1
            mark = "*" if moved else " "
            print(f"  {mark}[{seg.number:>2}] {old}  ->  {new}  (score={rows[i][2]}){flag}")
        seg._new = (ns, ne)  # type: ignore[attr-defined]

    if apply:
        # Rewrite time lines from the back so offsets stay valid.
        new_text = text
        for seg in reversed(segments):
            ns, ne = seg._new  # type: ignore[attr-defined]
            s_abs, e_abs, groups = seg.time_match
            replacement = f"{groups[0]}{fmt_tc(ns)}{groups[2]}{fmt_tc(ne)}{groups[4]}"
            new_text = new_text[:s_abs] + replacement + new_text[e_abs:]
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")

    return changes, warnings


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    converter = get_converter()
    if converter is None:
        print("warning: OpenCC not available; matching will be poor")

    total = 0
    all_warnings: list[str] = []
    for p in args.paths:
        path = Path(p) if Path(p).is_absolute() else ROOT / p
        print(f"===== {path.name} =====")
        changes, warnings = realign(path, converter, args.apply)
        if changes is None:
            print("  " + "\n  ".join(warnings))
            continue
        total += changes
        all_warnings.extend(warnings)
        print(f"  {'applied' if args.apply else 'proposed'} changes: {changes}")
    if all_warnings:
        print("\n--- warnings ---")
        print("\n".join(all_warnings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
