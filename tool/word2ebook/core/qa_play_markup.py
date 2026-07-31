"""Shared markup for per-segment audio play buttons.

Used by :class:`~core.qa_parser.QAParser` and :mod:`core.audio_map_injector`.
"""

from __future__ import annotations

from html import escape
from typing import Optional, Tuple
from urllib.parse import quote

from config.settings import Constants


def audio_url(stem_or_filename: str, audio_base: Optional[str] = None) -> str:
    """Build percent-encoded ``../audio/<stem>.opus`` URL."""
    base = audio_base or getattr(Constants, "QA_AUDIO_BASE", "../audio/")
    name = stem_or_filename
    if not name.lower().endswith(".opus"):
        name = f"{name}.opus"
    return f"{base}{quote(name)}"


def render_play(
    range_tuple: Optional[Tuple[float, float, str]],
    audio_rel: str,
    *,
    disabled_if_missing: bool = True,
) -> Optional[str]:
    """Return play-button HTML, or ``None`` when range is missing and hiding.

    Args:
        range_tuple: ``(start_sec, end_sec, label)`` or ``None``
        audio_rel: already-encoded audio URL
        disabled_if_missing: if True (QA parser legacy), emit disabled span;
            if False (PDF audio map), return ``None`` so the caller omits the bar
    """
    if not range_tuple:
        if disabled_if_missing:
            return '<span class="qa-play qa-play--disabled" aria-disabled="true">▶</span>'
        return None
    start, end, label = range_tuple
    return (
        f'<button class="qa-play" type="button" '
        f'data-audio="{escape(audio_rel, quote=True)}" '
        f'data-start="{start:.3f}" data-end="{end:.3f}" '
        f'data-label="{escape(label, quote=True)}">'
        f'<span class="qa-play-icon">▶</span>'
        f'<span class="qa-play-label">{escape(label)}</span>'
        f"</button>"
    )


def render_opening_meta_bar(
    range_tuple: Optional[Tuple[float, float, str]],
    audio_rel: str,
    *,
    hide_if_missing: bool = False,
) -> str:
    play = render_play(range_tuple, audio_rel, disabled_if_missing=not hide_if_missing)
    if play is None:
        return ""
    return f'<div class="qa-meta-bar qa-meta-bar--opening">{play}</div>'


def render_segment_meta_bar(
    number: str,
    range_tuple: Optional[Tuple[float, float, str]],
    audio_rel: str,
    *,
    hide_if_missing: bool = False,
    status_html: str = "",
) -> str:
    play = render_play(range_tuple, audio_rel, disabled_if_missing=not hide_if_missing)
    if play is None:
        return ""
    number_html = f'<span class="qa-number">{escape(number)}.</span>' if number else ""
    return f'<div class="qa-meta-bar">{number_html}{play}{status_html}</div>'
