"""Shared markup for per-segment audio play buttons.

Used by :class:`~core.qa_parser.QAParser` and :mod:`core.audio_map_injector`.
"""

from __future__ import annotations

from html import escape
from typing import Optional, Tuple
from urllib.parse import quote

from config.settings import Constants

# Inline speaker icon (currentColor) — ebook play buttons only; audio_map keeps ms labels.
_SPEAKER_SVG = (
    '<svg class="qa-play-speaker" viewBox="0 0 24 24" width="1em" height="1em" '
    'aria-hidden="true" focusable="false">'
    '<path fill="currentColor" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29'
    '-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s'
    '-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>'
    '</svg>'
)


def audio_url(stem_or_filename: str, audio_base: Optional[str] = None) -> str:
    """Build percent-encoded ``../audio/<stem>.opus`` URL."""
    base = audio_base or getattr(Constants, "QA_AUDIO_BASE", "../audio/")
    name = stem_or_filename
    if not name.lower().endswith(".opus"):
        name = f"{name}.opus"
    return f"{base}{quote(name)}"


def format_hms(seconds: float) -> str:
    """Format seconds as ``HH:MM:SS`` (milliseconds truncated for ebook display)."""
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_range_label(start: float, end: float) -> str:
    """Human-readable range for ebook play buttons (no milliseconds)."""
    return f"{format_hms(start)} - {format_hms(end)}"


def render_play(
    range_tuple: Optional[Tuple[float, float, str]],
    audio_rel: str,
    *,
    disabled_if_missing: bool = True,
) -> Optional[str]:
    """Return play-button HTML, or ``None`` when range is missing and hiding.

    Args:
        range_tuple: ``(start_sec, end_sec, label)`` or ``None``.
            The third element is ignored for display; the visible label is always
            ``HH:MM:SS - HH:MM:SS`` derived from start/end.
        audio_rel: already-encoded audio URL
        disabled_if_missing: if True (QA parser legacy), emit disabled span;
            if False (PDF audio map), return ``None`` so the caller omits the bar
    """
    if not range_tuple:
        if disabled_if_missing:
            return (
                '<span class="qa-play qa-play--disabled" aria-disabled="true">'
                f"{_SPEAKER_SVG}</span>"
            )
        return None
    start, end, _ignored_label = range_tuple
    label = format_range_label(start, end)
    return (
        f'<button class="qa-play" type="button" '
        f'data-audio="{escape(audio_rel, quote=True)}" '
        f'data-start="{start:.3f}" data-end="{end:.3f}" '
        f'data-label="{escape(label, quote=True)}">'
        f'<span class="qa-play-icon">{_SPEAKER_SVG}</span>'
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


def render_closing_meta_bar(
    range_tuple: Optional[Tuple[float, float, str]],
    audio_rel: str,
    *,
    hide_if_missing: bool = False,
) -> str:
    play = render_play(range_tuple, audio_rel, disabled_if_missing=not hide_if_missing)
    if play is None:
        return ""
    return (
        f'<div class="qa-meta-bar qa-meta-bar--closing">'
        f'<span class="qa-closing-label">收場</span>{play}</div>'
    )


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
