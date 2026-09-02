"""Inject ``.qa-play`` buttons into ebook chapter HTML from audio map JSON.

PDF chapters (13–21) come from ``data/audio_map/*.json``; Word chapters
(01–12) come from the reviewed chronological maps in ``audio_map2/*.json``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.qa_play_markup import (
    audio_url,
    render_closing_meta_bar,
    render_inline_answerer_play,
    render_opening_meta_bar,
)
from models.document_models import Chapter


DEFAULT_MAP_DIR = Path(__file__).resolve().parent.parent / "data" / "audio_map"
# Reviewed chronological Word↔audio maps (audio_map2/) are the source for Word
# chapters 01–12. The legacy data/audio_map_word/*.json flow has been removed.
DEFAULT_AUDIO_MAP2_DIR = Path(__file__).resolve().parents[3] / "audio_map2"

H2_RE = re.compile(
    r'<h2 id="([^"]+)">\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s+([^<]+?)'
    r'(?:<span[^>]*>.*?</span>)?\s*</h2>',
    re.S,
)
QUESTION_OPEN_RE = re.compile(r'<div class="question"(?=[\s>])')
QUESTION_ID_RE = re.compile(r'<div class="question" id="([^"]+)"')
# The answerer name span (Taiguanglin) inside an answer block; the play button is
# inserted inline right after it, on the same line, adding no vertical height.
ANSWERER_RE = re.compile(r'<span class="answerer">([^<]*)</span>')


def _has_been_listened(item: Optional[dict]) -> bool:
    """True when audio_map editorial UI recorded a listen (``meta.lastPlayed``)."""
    if not item or not isinstance(item, dict):
        return False
    meta = item.get("meta")
    if not isinstance(meta, dict):
        return False
    return bool(meta.get("lastPlayed"))


def _is_audio_map2_reviewed(item: Optional[dict]) -> bool:
    """True when a human actually listened to this audio_map2 segment.

    audio_map2 completion is now keyed on the editorial UI's 「最後播放」 record
    (``meta.lastPlayed``), not on ``status``: machine-aligned (``status=auto``/
    ``manual``) segments without a listen record must NOT show a button.
      ``meta.lastPlayed`` present  → human listened → show button
      ``meta.lastPlayed`` absent   → not yet listened → no button
    """
    if not item or not isinstance(item, dict):
        return False
    if item.get("start") is None:
        return False
    return _has_been_listened(item)


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
    # Strip any previously injected meta bars and inline answerer buttons so
    # rebuild is idempotent.
    section = re.sub(
        r'<div class="qa-meta-bar[^"]*"[^>]*>.*?</div>\s*',
        "",
        section,
        flags=re.S,
    )
    section = re.sub(
        r'<button class="qa-play qa-play--inline"[^>]*>.*?</button>\s*',
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

    # Walk questions in document order. For each listened segment, insert an
    # inline play button right after the answerer name (Taiguanglin) of the
    # answer that follows that question — no separate meta-bar line, no number.
    q_matches = list(QUESTION_OPEN_RE.finditer(section))
    injections: List[Tuple[int, str]] = []
    for q_index, qm in enumerate(q_matches, start=1):
        id_m = re.match(r'<div class="question" id="([^"]+)"', section[qm.start():])
        qid = id_m.group(1) if id_m else None
        seg = by_qid.get(qid)
        if seg is None and q_index <= len(segments):
            seg = segments[q_index - 1]
        if not (seg and _has_been_listened(seg)):
            continue
        answer_end = q_matches[q_index].start() if q_index < len(q_matches) else len(section)
        answer_region = section[qm.end():answer_end]
        am = ANSWERER_RE.search(answer_region)
        if not am:
            continue
        button = render_inline_answerer_play(
            _range_tuple(seg), audio_rel, hide_if_missing=True
        )
        if button:
            abs_pos = qm.end() + am.end()
            injections.append((abs_pos, button))
    # Apply in reverse order so earlier offsets stay valid
    for pos, button in sorted(injections, reverse=True):
        section = section[:pos] + button + section[pos:]

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


def load_word_maps_from_audio_map2(
    map_dir: Path = DEFAULT_AUDIO_MAP2_DIR,
) -> Dict[str, dict]:
    """Load the reviewed chronological maps (audio_map2/*.json) keyed by ebook
    ``question_id`` → segment (with ``audio_file`` resolved from its session).

    audio_map2 segments carry ``chapter_question_ids`` (a list of ebook theme-
    chapter question ids, already frozen into the JSONs — the script that wrote
    them, ``tool/word_audio_map2/link_chapters.py``, has been removed).
    Every question id in that list maps to the same reviewed segment/range.
    """
    by_qid: Dict[str, dict] = {}
    if not map_dir.is_dir():
        return by_qid
    for path in sorted(map_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for session in data.get("sessions") or []:
            audio_file = session.get("audio_file") or ""
            media_parts = session.get("media_parts") or []
            if not audio_file and media_parts:
                audio_file = media_parts[0].get("audio_file") or ""
            for seg in session.get("segments") or []:
                qids = seg.get("chapter_question_ids") or []
                if not qids:
                    continue
                resolved = dict(seg)
                resolved["audio_file"] = audio_file
                for qid in qids:
                    # First occurrence wins; duplicates share one range anyway.
                    by_qid.setdefault(qid, resolved)
    return by_qid


def inject_word_html_from_audio_map2(content: str, by_qid: Dict[str, dict]) -> str:
    """Insert an inline play button after every mapped answer's answerer name.

    The gate is the audio_map2 review state: a segment counts only when a human
    actually listened to it (``meta.lastPlayed``) and it has a non-null range.
    The button is placed directly after ``<span class="answerer">Taiguanglin</span>``
    — no separate meta-bar line, no number — so page height is unchanged.
    """
    if not by_qid or not content:
        return content

    # Strip any previously injected inline buttons for idempotency.
    content = re.sub(
        r'<button class="qa-play qa-play--inline"[^>]*>.*?</button>\s*',
        "",
        content,
        flags=re.S,
    )

    # Collect (absolute position, button) injections keyed to answers that
    # follow a matched question, then apply in reverse order.
    q_matches = list(QUESTION_ID_RE.finditer(content))
    injections: List[Tuple[int, str]] = []
    for i, m in enumerate(q_matches):
        seg = by_qid.get(m.group(1))
        if not (seg and _is_audio_map2_reviewed(seg)):
            continue
        answer_end = q_matches[i + 1].start() if i + 1 < len(q_matches) else len(content)
        answer_region = content[m.end():answer_end]
        am = ANSWERER_RE.search(answer_region)
        if not am:
            continue
        button = render_inline_answerer_play(
            _range_tuple(seg),
            audio_url(seg.get("audio_file") or ""),
            hide_if_missing=True,
        )
        if button:
            injections.append((m.end() + am.end(), button))

    if not injections:
        return content
    for pos, button in sorted(injections, reverse=True):
        content = content[:pos] + button + content[pos:]
    return content


def inject_word_chapters(chapters: List[Chapter]) -> int:
    """Apply audio_map2 word maps to chapter contents in-place.

    Returns the number of chapters modified. Word chapters 01–12 always source
    play buttons from the reviewed chronological maps (audio_map2/).
    """
    by_qid = load_word_maps_from_audio_map2(DEFAULT_AUDIO_MAP2_DIR)
    if not by_qid:
        return 0
    changed = 0
    for ch in chapters:
        if not ch.content or 'class="question"' not in ch.content:
            continue
        new_content = inject_word_html_from_audio_map2(ch.content, by_qid)
        if new_content != ch.content:
            ch.content = new_content
            changed += 1
    return changed
