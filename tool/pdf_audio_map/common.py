"""Shared helpers for PDF ↔ audio mapping."""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

try:
    from opencc import OpenCC
except Exception:  # pragma: no cover
    OpenCC = None

ROOT = Path(__file__).resolve().parents[2]
EBOOK_DIR = ROOT / "wenda2_ebook"
QA_DIR = ROOT / "qa"
MAP_DIR = ROOT / "tool" / "word2ebook" / "data" / "audio_map"
DEFAULT_SRT_ROOT = (
    Path.home()
    / "Documents"
    / "backup_2026-07-16_13inch_macbook"
)
DEFAULT_AUDIO_DIR = Path.home() / "tai" / "audio"
SENSE_VOICE_PYTHON = ROOT / "tool" / "sense_voice" / ".venv" / "bin" / "python"
SENSE_VOICE_TRANSCRIBE = ROOT / "tool" / "sense_voice" / "transcribe.py"

# PDF simplified source → traditional stem used in audio/SRT/qa filenames
SOURCE_TO_AUDIO = {
    "贴吧": "貼吧",
    "貼吧": "貼吧",
    "微信公众号": "微信公眾號",
    "微信公眾號": "微信公眾號",
    "官网": "官網",
    "官網": "官網",
}

SOURCE_SLUG = {
    "贴吧": "tieba",
    "貼吧": "tieba",
    "微信公众号": "wechat",
    "微信公眾號": "wechat",
    "官网": "guanwang",
    "官網": "guanwang",
}

# Months that bootstrap times from qa/*.txt rather than raw SRT
QA_TXT_MONTHS = {
    (2025, 11),
    (2025, 12),
    (2026, 1),
    (2026, 2),
    (2026, 3),
}

SRT_BLOCK_RE = re.compile(
    r"(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)",
    re.S,
)
PUNCT_RE = re.compile(r"[\s\W_，。？！、；：“”‘’「」『』（）()《》〈〉—…·\-]+")
H2_RE = re.compile(
    r'<h2 id="([^"]+)">\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s+([^<]+?)'
    r'(?:<span[^>]*>.*?</span>)?\s*</h2>',
    re.S,
)
QUESTION_BLOCK_RE = re.compile(
    r'<div class="question" id="([^"]+)">\s*'
    r'(?:<div class="question-meta">\s*'
    r'(?:<span class="questioner">([^<]*)</span>\s*)?'
    r'(?:<span class="question-time">([^<]*)</span>\s*)?'
    r'</div>\s*)?'
    r'(?:<div class="question-text">(.*?)</div>\s*)+'
    r'</div>',
    re.S,
)
QUESTION_TEXT_RE = re.compile(r'<div class="question-text">(.*?)</div>', re.S)
ANSWER_AFTER_Q_RE = re.compile(
    r'<div class="answer"[^>]*>.*?<div class="answer-text">(.*?)</div>',
    re.S,
)
TAG_RE = re.compile(r"<[^>]+>")
HEADING_RE = re.compile(r"^###\s+(\d+)\.\s*(.*?)\s*$", re.M)
TIME_LINE_RE = re.compile(
    r"^(?:開場時間|時間)[：:]\s*"
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s*[-–—]\s*"
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})",
    re.M,
)
OPENING_TIME_RE = re.compile(
    r"^開場時間[：:]\s*"
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s*[-–—]\s*"
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})",
    re.M,
)


def get_converter():
    return OpenCC("t2s") if OpenCC is not None else None


def normalize(text: str, converter=None) -> str:
    if not text:
        return ""
    if converter is not None:
        text = converter.convert(text)
    return PUNCT_RE.sub("", text.lower())


def strip_html(html: str) -> str:
    text = TAG_RE.sub("", html or "")
    return (
        text.replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("<br/>", "\n")
        .replace("<br>", "\n")
        .strip()
    )


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


def audio_stem(year: int, month: int, day: int, source: str) -> str:
    audio_src = SOURCE_TO_AUDIO.get(source, source)
    return f"{year}年{month}月{day}日Tai師父{audio_src}答疑"


def session_id(year: int, month: int, day: int, source: str) -> str:
    slug = SOURCE_SLUG.get(source, re.sub(r"\W+", "", source) or "src")
    return f"{year:04d}-{month:02d}-{day:02d}-{slug}"


def srt_path_for(stem: str, srt_root: Path = DEFAULT_SRT_ROOT) -> Path:
    year = stem[:4]
    return srt_root / f"{year}答疑音頻" / f"{stem}.srt"


def mp3_path_for(stem: str, srt_root: Path = DEFAULT_SRT_ROOT) -> Path:
    year = stem[:4]
    return srt_root / f"{year}答疑音頻" / f"{stem}.mp3"


def opus_path_for(stem: str, audio_dir: Path = DEFAULT_AUDIO_DIR) -> Path:
    return audio_dir / f"{stem}.opus"


def _media_candidate(year: int, month: int, day: int, source: str, srt_root: Path, audio_dir: Path) -> dict:
    stem = audio_stem(year, month, day, source)
    srt = srt_path_for(stem, srt_root)
    mp3 = mp3_path_for(stem, srt_root)
    opus = opus_path_for(stem, audio_dir)
    return {
        "stem": stem,
        "audio_src": SOURCE_TO_AUDIO.get(source, source),
        "audio_file": f"{stem}.opus",
        "srt_file": str(srt),
        "mp3_path": str(mp3),
        "opus_path": str(opus),
        "srt_exists": srt.exists(),
        "mp3_exists": mp3.exists(),
        "opus_exists": opus.exists(),
    }


def resolve_media(
    year: int,
    month: int,
    day: int,
    source: str,
    srt_root: Path = DEFAULT_SRT_ROOT,
    audio_dir: Path = DEFAULT_AUDIO_DIR,
) -> dict:
    """Resolve audio/SRT paths for a PDF source.

    官网/官網 with no media falls back to the same day's 貼吧 files (Aug–Sep
    transition period used interchangeable names).
    """
    primary = _media_candidate(year, month, day, source, srt_root, audio_dir)
    has_any = primary["srt_exists"] or primary["mp3_exists"] or primary["opus_exists"]
    if has_any:
        return {**primary, "fallback_from": None, "resolved_source": SOURCE_TO_AUDIO.get(source, source)}

    audio_src = SOURCE_TO_AUDIO.get(source, source)
    if audio_src == "官網":
        fb = _media_candidate(year, month, day, "貼吧", srt_root, audio_dir)
        if fb["srt_exists"] or fb["mp3_exists"] or fb["opus_exists"]:
            return {
                **fb,
                "fallback_from": "官網",
                "resolved_source": "貼吧",
            }

    return {**primary, "fallback_from": None, "resolved_source": audio_src}


def month_map_path(year: int, month: int) -> Path:
    return MAP_DIR / f"{year:04d}-{month:02d}.json"


def parse_srt(path: Path, converter=None) -> List[Tuple[float, float, str]]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    cues = []
    for m in SRT_BLOCK_RE.finditer(text):
        body = " ".join(line.strip() for line in m.group(4).splitlines() if line.strip())
        cues.append((parse_tc(m.group(2)), parse_tc(m.group(3)), normalize(body, converter)))
    return cues


def parse_srt_raw(path: Path) -> List[Tuple[float, float, str]]:
    """Parse SRT keeping original (non-normalized) cue text for previews."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    cues = []
    for m in SRT_BLOCK_RE.finditer(text):
        body = " ".join(line.strip() for line in m.group(4).splitlines() if line.strip())
        cues.append((parse_tc(m.group(2)), parse_tc(m.group(3)), body))
    return cues


def srt_preview(cues_raw: List[Tuple[float, float, str]], start: float, end: float, limit: int = 220) -> str:
    parts = [body for (cs, ce, body) in cues_raw if cs < end and ce > start]
    joined = "".join(parts)
    return joined if len(joined) <= limit else joined[:limit] + "…"


def _window(cues, i, need_len):
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
    """Find cue where needle is first read aloud. Returns (start, cue_idx, size) or None.

    Important: the sliding window may *contain* a later match while starting on an
    earlier cue. Always return the cue that *owns* the matched span, not the
    window's first cue (otherwise Q1 can start ~20s early when the window
    reaches into the real answer).
    """
    if len(needle) < min_len:
        return None
    n = len(needle)
    # best: (priority, size, owner_idx) — prefer needle-aligned matches
    best = None
    end_idx = min(len(cues), cursor_idx + max_scan)
    for i in range(cursor_idx, end_idx):
        win, owners = _window(cues, i, n)
        if not win:
            continue
        m = difflib.SequenceMatcher(None, win, needle, autojunk=False).find_longest_match(
            0, len(win), 0, n
        )
        min_accept = max(min_len, min_block - 2)
        if m.size < min_accept:
            continue
        # Map match back to the cue that speaks those characters
        qpos = max(0, m.a - m.b) if m.b <= 4 else m.a
        owner = owners[qpos] if qpos < len(owners) else i
        # Priority: needle starts near match (m.b small) > mid-needle hit
        priority = 2 if m.b <= 4 else (1 if m.b <= 12 else 0)
        cand = (priority, m.size, owner)
        if best is None or cand > best:
            best = cand
        # Fast path: strong prefix alignment
        if m.size >= min_block and m.b <= 4:
            return cues[owner][0], owner, m.size
    min_accept = max(min_len, min_block - 2)
    if best is None or best[1] < min_accept:
        return None
    _priority, size, owner = best
    return cues[owner][0], owner, size


# Arabic digits → common spoken forms in ASR (1 often becomes 幺)
_DIGIT_CN = str.maketrans("0123456789", "零一二三四五六七八九")
_DIGIT_YAO = str.maketrans("0123456789", "零幺二三四五六七八九")

HONORIFIC_RE = re.compile(
    r"^(顶礼|頂禮)?(tai)?(师父|師父|老师|老師)?(好|吉祥)?",
    re.I,
)


def spoken_name_variants(name: str, converter=None) -> List[str]:
    """Normalize a questioner name into ASR-friendly variants.

    Spoken digit forms (五七幺) are tried before Arabic digits, because
    SenseVoice/Paraformer usually reads IDs that way.

    Digit runs of length ≥ 4 (years like 2025) are **not** expanded — otherwise
    ``明月2025`` becomes ``明月二零二五`` and false-hits the opening date.
    """
    if not name:
        return []
    base = normalize(name, converter)
    if not base:
        return []

    def _expand(s: str, table) -> str:
        out = []
        i = 0
        while i < len(s):
            if s[i].isdigit():
                j = i
                while j < len(s) and s[j].isdigit():
                    j += 1
                run = s[i:j]
                if len(run) >= 4:
                    out.append(run)  # keep years / long ids as digits
                else:
                    out.append(run.translate(table))
                i = j
            else:
                out.append(s[i])
                i += 1
        return "".join(out)

    cn = _expand(base, _DIGIT_CN)
    yao = _expand(base, _DIGIT_YAO)
    out: List[str] = []
    for v in (yao, cn, base):
        if v and v not in out:
            out.append(v)
    # Prefer variants that keep a non-digit prefix (≥2 chars) for anchoring
    out.sort(key=lambda v: (0 if re.search(r"\D{2,}", v) else 1, -len(v)))
    return out


def question_needles(q_text: str, converter=None) -> List[str]:
    """Distinctive needles from a PDF question (strip honorifics; prefer body)."""
    raw = normalize(q_text or "", converter)
    if not raw:
        return []
    stripped = HONORIFIC_RE.sub("", raw)
    needles = []
    for cand in (stripped, raw):
        if len(cand) >= 8:
            needles.append(cand[:80])
        if len(cand) >= 24:
            # Mid-question block avoids shared openings like 顶礼师父
            mid = cand[8:8 + 60]
            if len(mid) >= 12:
                needles.append(mid)
    # de-dupe preserving order
    seen = set()
    uniq = []
    for n in needles:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def title_coverage(title: str, question: str) -> float:
    """How much of a short title appears as a contiguous block inside a longer question."""
    if not title or not question:
        return 0.0
    m = difflib.SequenceMatcher(None, title, question, autojunk=False).find_longest_match(
        0, len(title), 0, len(question)
    )
    return m.size / len(title)


def match_ordered(
    needles: List[str],
    haystacks: List[str],
    min_ratio: float = 0.42,
    scorer=None,
    window: int = 12,
) -> List[Optional[int]]:
    """Greedy ordered fuzzy match: each needle maps to a later haystack index or None."""
    score_fn = scorer or text_similarity
    result: List[Optional[int]] = []
    used = set()
    cursor = 0
    for needle in needles:
        best_i = None
        best_score = 0.0
        end = min(len(haystacks), cursor + window)
        for i in range(cursor, end):
            if i in used:
                continue
            score = score_fn(needle, haystacks[i])
            if score > best_score:
                best_score = score
                best_i = i
        if best_i is not None and best_score >= min_ratio:
            result.append(best_i)
            used.add(best_i)
            cursor = best_i + 1
            continue
        # Global re-anchor for drifted sequences
        best_i = None
        best_score = 0.0
        for i in range(len(haystacks)):
            if i in used:
                continue
            score = score_fn(needle, haystacks[i])
            if score > best_score:
                best_score = score
                best_i = i
        if best_i is not None and best_score >= min_ratio + 0.08:
            result.append(best_i)
            used.add(best_i)
            cursor = best_i + 1
        else:
            result.append(None)
    return result


def chapter_html_files(ebook_dir: Path = EBOOK_DIR) -> Iterable[Path]:
    for path in sorted(ebook_dir.glob("[0-9][0-9].html")):
        # Skip traditional variants (NN_trad.html) — glob already excludes them
        yield path


def empty_range_fields() -> dict:
    return {
        "start": None,
        "end": None,
        "start_label": None,
        "end_label": None,
        "confidence": 0.0,
        "status": "missing",
        "locked": False,
        "notes": "",
        "srt_preview": "",
    }


def range_fields(start: float, end: float, confidence: float, status: str, preview: str = "") -> dict:
    return {
        "start": round(float(start), 3),
        "end": round(float(end), 3),
        "start_label": fmt_tc(start),
        "end_label": fmt_tc(end),
        "confidence": round(float(confidence), 3),
        "status": status,
        "locked": False,
        "notes": "",
        "srt_preview": preview or "",
    }
