"""Shared helpers for the Word-ebook audio alignment tool.

Reuses the proven primitives from :mod:`pdf_audio_map.common` (SRT parsing,
OpenCC normalisation, fuzzy matching) and adds Word-specific pieces:
timestamp normalisation and an SRT-session inventory.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

_TOOL_DIR = Path(__file__).resolve().parent
_PDF_TOOL_DIR = _TOOL_DIR.parent / "pdf_audio_map"
if str(_PDF_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_PDF_TOOL_DIR))
if str(_TOOL_DIR.parent / "word2ebook") not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR.parent / "word2ebook"))

from common import (  # noqa: E402,F401  (re-exported primitives)
    DEFAULT_AUDIO_DIR,
    DEFAULT_SRT_ROOT,
    empty_range_fields,
    fmt_tc,
    get_converter,
    match_start,
    normalize,
    parse_srt,
    parse_srt_raw,
    parse_tc,
    question_needles,
    range_fields,
    srt_preview,
    spoken_name_variants,
    strip_html,
    text_similarity,
)

ROOT = Path(__file__).resolve().parents[2]
W2E_TOOL_DIR = ROOT / "tool" / "word2ebook"
WORD_MAP_DIR = W2E_TOOL_DIR / "data" / "audio_map_word"
BUILD_DIR = _TOOL_DIR / "build"

DOCX_FILE = ROOT / "問答錄2" / "wenda2_250810_截止25年5月17日答疑_含图版.docx"

SRT_YEAR_DIRS = ("2024答疑音頻", "2025答疑音頻")

_SRT_NAME_RE = re.compile(
    r"^(\d{4})年(\d{1,2})月(\d{1,2})日(.+?)\.srt$"
)

_SOURCE_SLUG = {
    "微信公眾號": "wechat",
    "公眾號": "wechat",
    "貼吧": "tieba",
    "官网": "guanwang",
    "官網": "guanwang",
}


def detect_source(name_suffix: str) -> str:
    """Map an SRT filename suffix (e.g. ``Tai師父微信公眾號答疑（上）``) to a source."""
    for token, src in _SOURCE_SLUG.items():
        if token in name_suffix:
            return src
    return "main"


def normalize_question_time(raw: str) -> tuple:
    """Normalise Word question-time strings to ``(YYYY-MM-DD|None, time_part)``.

    Handles ``2025-5-12``, ``2025-05-12 13:18`` and the occasional
    day-first ``15-07-2024`` form. Returns ``(None, "")`` when unparseable.
    """
    raw = (raw or "").strip()
    if not raw:
        return None, ""
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*(.*)$", raw)
    if m:
        y, mo, d, rest = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
    else:
        m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\s*(.*)$", raw)
        if not m:
            return None, ""
        d, mo, y, rest = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
    if not (1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= 2100):
        return None, ""
    return f"{y:04d}-{mo:02d}-{d:02d}", rest.strip()


def inventory_sessions(srt_root: Path = DEFAULT_SRT_ROOT) -> List[dict]:
    """Scan the backup dirs and return chronological SRT session descriptors."""
    sessions: List[dict] = []
    seen_stems: Dict[str, int] = {}
    for year_dir in SRT_YEAR_DIRS:
        folder = srt_root / year_dir
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.srt")):
            m = _SRT_NAME_RE.match(path.name)
            if not m:
                continue
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            suffix = m.group(4)
            source = detect_source(suffix)
            stem = path.stem
            # unique session id per (date, source); parts （上/下） get -2/-3
            base_sid = f"{y:04d}-{mo:02d}-{d:02d}-{source}"
            n = seen_stems.get(base_sid, 0)
            seen_stems[base_sid] = n + 1
            sid = base_sid if n == 0 else f"{base_sid}-{n + 1}"
            opus = DEFAULT_AUDIO_DIR / f"{stem}.opus"
            sessions.append(
                {
                    "session_id": sid,
                    "year": y,
                    "month": mo,
                    "day": d,
                    "date": f"{y:04d}-{mo:02d}-{d:02d}",
                    "source": source,
                    "name_suffix": suffix,
                    "audio_file": f"{stem}.opus",
                    "stem": stem,
                    "srt_file": str(path),
                    "mp3_path": str(path.with_suffix(".mp3")),
                    "opus_exists": opus.exists(),
                    "opus_path": str(opus),
                }
            )
    sessions.sort(key=lambda s: (s["date"], s["source"], s["session_id"]))
    return sessions


def load_questions(path: Optional[Path] = None) -> List[dict]:
    path = path or (BUILD_DIR / "questions.json")
    return json.loads(path.read_text(encoding="utf-8"))


class CueCache:
    """Lazily parse and cache SRT cues (normalised + raw) per session."""

    def __init__(self, converter):
        self.converter = converter
        self._norm: Dict[str, list] = {}
        self._raw: Dict[str, list] = {}

    def cues(self, srt_file: str) -> list:
        if srt_file not in self._norm:
            self._norm[srt_file] = parse_srt(Path(srt_file), self.converter)
        return self._norm[srt_file]

    def cues_raw(self, srt_file: str) -> list:
        if srt_file not in self._raw:
            self._raw[srt_file] = parse_srt_raw(Path(srt_file))
        return self._raw[srt_file]


# --------------------------------------------------------------------------
# Pinyin normalisation (homophone-tolerant matching for ASR text)
# --------------------------------------------------------------------------
try:
    from pypinyin import lazy_pinyin as _lazy_pinyin
except Exception:  # pragma: no cover
    _lazy_pinyin = None


def py_norm(text: str, converter=None) -> str:
    """Normalise ``text`` to toneless pinyin (OpenCC → strip → pypinyin).

    Collapses ASR homophone errors (业/夜 → ye, 自性/自信 partially, …) so the
    written ebook text can be fuzzy-matched against spoken transcripts.
    """
    t = normalize(text, converter)
    if not t:
        return ""
    if _lazy_pinyin is None:
        return t
    return "".join(_lazy_pinyin(t))


class SessionStream:
    """A session's transcript as one pinyin string + char→cue index mapping."""

    def __init__(self, session: dict, cues: list, converter=None, raw_cues: list = None):
        self.session = session
        self.cues = cues
        self.raw_cues = raw_cues or []
        parts = []
        owners: List[int] = []
        for ci, (_s, _e, body) in enumerate(cues):
            py = py_norm(body, converter)
            parts.append(py)
            owners.extend([ci] * len(py))
        self.py = "".join(parts)
        self.owners = owners
        self.boundaries = None
        if owners:
            # first char index of each cue
            bounds = [0]
            for i in range(1, len(owners)):
                if owners[i] != owners[i - 1]:
                    bounds.append(i)
            self.boundaries = bounds

    def cue_index(self, char_pos: int) -> int:
        if not self.boundaries or char_pos <= 0:
            return 0
        import bisect

        i = bisect.bisect_right(self.boundaries, char_pos) - 1
        if i < 0 or i >= len(self.boundaries):
            return max(len(self.cues) - 1, 0)
        return self.owners[self.boundaries[i]]

    def cue_start_time(self, char_pos: float) -> float:
        idx = self.cue_index(int(char_pos))
        return self.cues[idx][0]

    @property
    def audio_end(self) -> float:
        return self.cues[-1][1] if self.cues else 0.0


class StreamCache:
    """Cache :class:`SessionStream` objects per srt file."""

    def __init__(self, converter):
        self.converter = converter
        self._cues = CueCache(converter)
        self._streams: Dict[str, SessionStream] = {}

    def stream(self, srt_file: str) -> SessionStream:
        if srt_file not in self._streams:
            self._streams[srt_file] = SessionStream(
                {"srt_file": srt_file},
                self._cues.cues(srt_file),
                self.converter,
                self._cues.cues_raw(srt_file),
            )
        return self._streams[srt_file]

    def cues_raw(self, srt_file: str) -> list:
        return self._cues.cues_raw(srt_file)
