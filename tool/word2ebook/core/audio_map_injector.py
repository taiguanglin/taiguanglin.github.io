"""Inject ``.qa-play`` buttons into PDF chapter HTML from audio_map JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.qa_play_markup import (
    audio_url,
    render_closing_meta_bar,
    render_opening_meta_bar,
    render_segment_meta_bar,
)
from models.document_models import Chapter


DEFAULT_MAP_DIR = Path(__file__).resolve().parent.parent / "data" / "audio_map"
DEFAULT_WORD_MAP_DIR = Path(__file__).resolve().parent.parent / "data" / "audio_map_word"

H2_RE = re.compile(
    r'<h2 id="([^"]+)">\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s+([^<]+?)'
    r'(?:<span[^>]*>.*?</span>)?\s*</h2>',
    re.S,
)
QUESTION_OPEN_RE = re.compile(r'<div class="question"(?=[\s>])')
QUESTION_ID_RE = re.compile(r'<div class="question" id="([^"]+)"')
# A meta bar directly preceding a question div (already-injected marker)
TRAILING_BAR_RE = re.compile(r'<div class="qa-meta-bar[^"]*"[^>]*>.*?</div>\s*\Z', re.S)


def _has_been_listened(item: Optional[dict]) -> bool:
    """True when audio_map editorial UI recorded a listen (``meta.lastPlayed``)."""
    if not item or not isinstance(item, dict):
        return False
    meta = item.get("meta")
    if not isinstance(meta, dict):
        return False
    return bool(meta.get("lastPlayed"))


def _is_confirmed(item: Optional[dict]) -> bool:
    """True when a human signed off this word-map segment.

    Word chapters follow a proofread-gated flow: play buttons appear only
    after the segment was confirmed in ``/audio_map/index.html``
    (``meta.confirmed``) — ``meta.lastPlayed`` counts too, mirroring the PDF
    convention.
    """
    if not item or not isinstance(item, dict):
        return False
    if _has_been_listened(item):
        return True
    meta = item.get("meta")
    return isinstance(meta, dict) and bool(meta.get("confirmed"))


def _range_tuple(item: Optional[dict]) -> Optional[Tuple[float, float, str]]:
    if not item:
        return None
    if item.get("status") == "missing":
        return None
    start = item.get("start")
    end = item.get("end")
    if start is None or end is None:
        return None
    label = item.get("start_label") and item.get("end_label")
    if label:
        label = f"{item['start_label']} - {item['end_label']}"
    else:
        label = f"{float(start):.3f} - {float(end):.3f}"
    return (float(start), float(end), label)


def load_maps(map_dir: Path = DEFAULT_MAP_DIR) -> Dict[str, dict]:
    """Load all month maps keyed by ``section_id`` → session dict."""
    by_section: Dict[str, dict] = {}
    if not map_dir.is_dir():
        return by_section
    for path in sorted(map_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for session in data.get("sessions") or []:
            sid = session.get("section_id")
            if sid:
                by_section[sid] = session
    return by_section


def inject_html(content: str, by_section: Dict[str, dict]) -> str:
    """Insert qa-meta-bar markup into chapter body HTML."""
    if not by_section or not content:
        return content

    matches = list(H2_RE.finditer(content))
    if not matches:
        return content

    parts: List[str] = []
    cursor = 0
    for i, m in enumerate(matches):
        section_id = m.group(1)
        section_start = m.start()
        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        parts.append(content[cursor:section_start])

        section = content[section_start:section_end]
        session = by_section.get(section_id)
        if session:
            section = _inject_section(section, session)
        parts.append(section)
        cursor = section_end

    parts.append(content[cursor:])
    return "".join(parts)


def _inject_section(section: str, session: dict) -> str:
    # Strip any previously injected meta bars so rebuild is idempotent
    section = re.sub(
        r'<div class="qa-meta-bar[^"]*"[^>]*>.*?</div>\s*',
        "",
        section,
        flags=re.S,
    )

    audio_rel = audio_url(session.get("audio_file") or "")
    segments = session.get("segments") or []
    # Opening play button follows whether the first Q&A segment was listened to.
    first_segment_listened = _has_been_listened(segments[0] if segments else None)

    opening = session.get("opening")
    opening_range = _range_tuple(opening) if first_segment_listened else None
    opening_bar = render_opening_meta_bar(
        opening_range, audio_rel, hide_if_missing=True
    )
    if opening_bar:
        section = re.sub(
            r"(</h2>\s*)",
            r"\1" + opening_bar + "\n",
            section,
            count=1,
        )

    # Build lookup by question_id and by index order
    by_qid = {s.get("question_id"): s for s in segments if s.get("question_id")}

    # Walk questions in document order
    out = []
    pos = 0
    q_index = 0
    for qm in QUESTION_OPEN_RE.finditer(section):
        out.append(section[pos:qm.start()])
        q_index += 1
        # Identify question id
        id_m = re.match(r'<div class="question" id="([^"]+)"', section[qm.start():])
        qid = id_m.group(1) if id_m else None
        seg = by_qid.get(qid)
        if seg is None and q_index <= len(segments):
            seg = segments[q_index - 1]
        bar = ""
        if seg and _has_been_listened(seg):
            bar = render_segment_meta_bar(
                str(seg.get("index") or q_index),
                _range_tuple(seg),
                audio_rel,
                hide_if_missing=True,
            )
        if bar:
            out.append(bar + "\n")
        out.append(section[qm.start():qm.end()])
        pos = qm.end()
    out.append(section[pos:])
    section = "".join(out)

    # Closing play button: require closing itself to have been listened to.
    # Insert *above* the closing paragraph(s), mirroring opening (bar then text).
    closing = session.get("closing")
    if closing and _has_been_listened(closing):
        closing_bar = render_closing_meta_bar(
            _range_tuple(closing), audio_rel, hide_if_missing=True
        )
        if closing_bar:
            section = _insert_closing_bar(section, closing_bar)
    return section


def _insert_closing_bar(section: str, closing_bar: str) -> str:
    """Place closing meta bar immediately before trailing closing ``<p>`` prose."""
    # Content after the last question block (answer + optional trailing <p>).
    last_q = None
    for m in QUESTION_OPEN_RE.finditer(section):
        last_q = m
    if last_q is None:
        m_nav = re.search(r'<div class="(?:back-to-top|nav-footer)"', section)
        if m_nav:
            return section[: m_nav.start()] + closing_bar + "\n" + section[m_nav.start() :]
        return section.rstrip() + "\n" + closing_bar + "\n"

    after_q = section[last_q.start() :]
    # Prefer first bare <p> after the last answer closes (closing prose).
    ans = re.search(r'class="answer-text"', after_q)
    search_from = 0
    if ans:
        close = re.search(r"</div>\s*</div>", after_q[ans.start() :])
        if close:
            search_from = ans.start() + close.end()
    trailing = after_q[search_from:]
    p_m = re.search(r"<p(?:\s[^>]*)?>", trailing)
    if p_m:
        abs_pos = last_q.start() + search_from + p_m.start()
        return section[:abs_pos] + closing_bar + "\n" + section[abs_pos:]

    m_nav = re.search(r'<div class="(?:back-to-top|nav-footer)"', section)
    if m_nav:
        return section[: m_nav.start()] + closing_bar + "\n" + section[m_nav.start() :]
    return section.rstrip() + "\n" + closing_bar + "\n"


def inject_chapters(chapters: List[Chapter], map_dir: Optional[Path] = None) -> int:
    """Apply audio maps to chapter contents in-place. Returns #chapters modified."""
    by_section = load_maps(map_dir or DEFAULT_MAP_DIR)
    if not by_section:
        return 0
    changed = 0
    for ch in chapters:
        if not ch.content:
            continue
        # Only PDF month chapters contain date+source h2s we map
        new_content = inject_html(ch.content, by_section)
        if new_content != ch.content:
            ch.content = new_content
            changed += 1
    return changed


# ---------------------------------------------------------------------------
# Word-chapter injection (keyed by stable question id, no date h2 sections)
# ---------------------------------------------------------------------------


def load_word_maps(map_dir: Path = DEFAULT_WORD_MAP_DIR) -> Dict[str, dict]:
    """Load word maps keyed by ``question_id`` → segment dict.

    Word chapters have no per-date ``<h2>`` sections, so unlike
    :func:`load_maps` the lookup key is the stable question id embedded in the
    chapter HTML (``<div class="question" id="question-…">``).
    """
    by_qid: Dict[str, dict] = {}
    if not map_dir.is_dir():
        return by_qid
    for path in sorted(map_dir.glob("word-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for seg in data.get("segments") or []:
            qid = seg.get("question_id")
            if not qid:
                continue
            # First occurrence wins; duplicates share one range anyway.
            by_qid.setdefault(qid, seg)
    return by_qid


def inject_word_html(content: str, by_qid: Dict[str, dict]) -> str:
    """Insert a meta bar before every mapped question div in ``content``.

    - Unmapped questions get nothing (they stay buttonless by design).
    - A question already preceded by a meta bar is left untouched, so the pass
      is idempotent and never disturbs PDF-injected bars.
    """
    if not by_qid or not content:
        return content

    out: List[str] = []
    pos = 0
    number = 0
    inserted = False
    for m in QUESTION_ID_RE.finditer(content):
        number += 1
        prefix = content[pos : m.start()]
        out.append(prefix)
        seg = by_qid.get(m.group(1))
        # Proofread-gated flow: only confirmed auto segments get a button.
        # status "review" (borderline alignment), "none" (human-confirmed no
        # audio) and unconfirmed autos all stay buttonless.
        if (
            seg
            and seg.get("status") == "auto"
            and _is_confirmed(seg)
            and not TRAILING_BAR_RE.search(out[-1][-2500:])
        ):
            bar = render_segment_meta_bar(
                str(seg.get("index") or number),
                _range_tuple(seg),
                audio_url(seg.get("audio_file") or ""),
                hide_if_missing=True,
            )
            if bar:
                out.append(bar + "\n")
                inserted = True
        out.append(content[m.start() : m.end()])
        pos = m.end()
    if not inserted:
        return content
    out.append(content[pos:])
    return "".join(out)


def inject_word_chapters(
    chapters: List[Chapter], map_dir: Optional[Path] = None
) -> int:
    """Apply word maps to chapter contents in-place. Returns #chapters modified."""
    by_qid = load_word_maps(map_dir or DEFAULT_WORD_MAP_DIR)
    if not by_qid:
        return 0
    changed = 0
    for ch in chapters:
        if not ch.content or 'class="question"' not in ch.content:
            continue
        new_content = inject_word_html(ch.content, by_qid)
        if new_content != ch.content:
            ch.content = new_content
            changed += 1
    return changed
