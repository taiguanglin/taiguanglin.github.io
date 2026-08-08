"""Detect and attach session closing (收場) ranges from PDF text + SRT."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from common import (
    empty_range_fields,
    normalize,
    parse_srt_raw,
    range_fields,
    srt_preview,
)

# Spoken / PDF outro cues (simplified Chinese; ASR often inserts extra 的).
CLOSING_CUE_RE = re.compile(
    r"(?:"
    r"今天.{0,40}(?:回答到这|答到这|讲到这|说到这|就到这|就到这里|就讲到|就说完|回到这里)"
    r"|好了.{0,20}今天"
    r"|回答完了"
    r"|好像今天的问题"
    r"|官网的问题今天"
    r"|公众.?号.{0,30}(?:问题|回答)"
    r"|贴吧.{0,12}到这"
    r"|到这里就结束"
    r"|今天就回答到"
    r"|今天就讲到"
    r"|今天就说到"
    r"|今天的回答就到"
    r"|今天的问题就回答"
    r"|今天的这个.{0,12}就到"
    r"|回答到这里"
    r"|回答到这儿"
    r"|答疑就到这"
    r"|答疑到这里"
    r"|录完了"
    r")"
)


def resolve_srt_path(path_str: Optional[str]) -> Optional[Path]:
    """Resolve srt_file, trying backup_on_ ↔ backup_ alternate roots."""
    if not path_str:
        return None
    p = Path(path_str)
    if p.is_file():
        return p
    s = str(p)
    alts = []
    if "backup_on_" in s:
        alts.append(Path(s.replace("backup_on_", "backup_", 1)))
    if re.search(r"/backup_\d", s) and "backup_on_" not in s:
        alts.append(Path(s.replace("/backup_", "/backup_on_", 1)))
    for a in alts:
        if a.is_file():
            return a
    return None


# Trailing bare <p> after last answer (ebook HTML).
_TRAILING_P_RE = re.compile(r"<p(?:\s[^>]*)?>(.*?)</p>", re.S)


def _strip_html_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw or "")
    return (
        text.replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("<br/>", "\n")
        .replace("<br>", "\n")
        .strip()
    )


def closing_text_from_section(section_html: str, last_question_start: int) -> str:
    """Collect trailing ``<p>`` after the last question's answer block."""
    chunk = section_html[last_question_start:]
    chunk = re.split(r'<div class="(?:back-to-top|nav-footer)"', chunk, maxsplit=1)[0]
    # Prefer content after the last answer-text closing tags.
    idx = chunk.rfind('class="answer-text"')
    if idx >= 0:
        rest_m = re.search(r"</div>\s*</div>", chunk[idx:])
        trailing = chunk[idx + rest_m.end() :] if rest_m else ""
    else:
        # No answer block — anything after the question wrapper.
        trailing = re.sub(r"^.*?</div>\s*", "", chunk, count=1, flags=re.S)
    paras = []
    for raw in _TRAILING_P_RE.findall(trailing):
        text = _strip_html_text(raw)
        if text:
            paras.append(text)
    return "\n".join(paras)


def _cue_matches_closing(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    return bool(CLOSING_CUE_RE.search(compact))


def _soft_norm(text: str, converter=None) -> str:
    """Normalize and drop filler 的 for ASR/PDF fuzzy match."""
    return normalize(text, converter).replace("的", "")


def detect_closing_onset(
    cues: List[Tuple[float, float, str]],
    *,
    after: float,
    closing_text: str = "",
    converter=None,
) -> Optional[float]:
    """Return start time of spoken closing, or None."""
    if not cues:
        return None
    audio_end = float(cues[-1][1])
    floor = float(after) + 2.0
    long_closing = len(closing_text or "") > 80

    def _with_hao_le(onset: float) -> float:
        for i, (st, en, raw) in enumerate(cues):
            if abs(st - onset) < 0.05:
                if i > 0:
                    pst, pen, praw = cues[i - 1]
                    compact = re.sub(r"\s+", "", praw or "")
                    if compact.startswith("好了") and (en - pst) < 4.0 and pst >= floor:
                        return float(pst)
                break
        return onset

    # Prefer matching PDF closing text (first sentence) after last Q.
    if closing_text:
        first_sent = re.split(r"[。！？\n]", closing_text, maxsplit=1)[0].strip()
        needles = []
        for raw_n in (first_sent, closing_text[:60]):
            n = _soft_norm(raw_n, converter)
            if len(n) >= 8:
                needles.append(n[:18])
                needles.append(n[:12])
        # Also a loose key: 今天…回答到这
        soft_full = _soft_norm(closing_text[:100], converter)
        if "回答到这" in soft_full or "就到这" in soft_full:
            needles.append("回答到这")
        seen = set()
        needles = [n for n in needles if n and not (n in seen or seen.add(n))]

        best = None
        for st, en, raw in cues:
            if st < floor:
                continue
            blob = _soft_norm(raw, converter)
            for needle in needles:
                if needle in blob:
                    # For short outros prefer later hits; long outros take first.
                    if best is None:
                        best = float(st)
                    elif not long_closing:
                        best = float(st)
                    break
            if best is not None and long_closing:
                break
        if best is not None:
            return _with_hao_le(best)

        # Sliding window near end / after floor
        win_start = floor if long_closing else max(floor, audio_end - 300)
        tail = [(st, en, raw) for st, en, raw in cues if st >= win_start]
        joined = ""
        starts = []
        for st, en, raw in tail:
            starts.append((len(joined), st))
            joined += _soft_norm(raw, converter)
        for needle in needles:
            pos = joined.find(needle)
            if pos >= 0:
                for off, st in reversed(starts):
                    if off <= pos:
                        return _with_hao_le(float(st))
                break

    hits = [
        float(st)
        for st, en, raw in cues
        if st >= floor and _cue_matches_closing(raw)
    ]
    if not hits:
        # Join near-EOF cues (outro often split: 「官网的问题」+「今天就答完了」)
        tail = [(st, en, raw) for st, en, raw in cues if st >= max(floor, audio_end - 45)]
        if tail:
            joined = _soft_norm("".join(t for _, _, t in tail), converter)
            if (
                ("答完了" in joined or "回答到这" in joined or "就到这" in joined)
                and ("今天" in joined or "官网" in joined or "公众" in joined or "贴吧" in joined)
            ):
                for st, en, raw in reversed(tail):
                    compact = re.sub(r"\s+", "", raw or "")
                    if compact.startswith("好了"):
                        return float(st)
                for st, en, raw in reversed(tail):
                    compact = re.sub(r"\s+", "", raw or "")
                    if "今天" in compact or "官网" in compact or "公众" in compact:
                        return _with_hao_le(float(st))
                return float(tail[0][0])
        for i, (st, en, raw) in enumerate(cues):
            if st < floor:
                continue
            compact = re.sub(r"\s+", "", raw or "")
            if compact.startswith("好了") or compact in ("好了啊", "好了。", "好了，"):
                nxt = cues[i + 1][2] if i + 1 < len(cues) else ""
                if "今天" in (nxt or "") or "今天" in compact:
                    return float(st)
        return None
    onset = hits[0] if long_closing else hits[-1]
    return _with_hao_le(onset)


def build_closing(
    *,
    text: str,
    start: Optional[float],
    end: float,
    cues: Optional[List[Tuple[float, float, str]]] = None,
    status: str = "auto",
    confidence: float = 0.85,
    notes: str = "",
) -> dict:
    base = {
        "text": text or "",
        "text_preview": (text or "")[:200],
    }
    if start is None or end is None or float(end) <= float(start or 0):
        return {**base, **empty_range_fields(), "notes": notes or "closing-missing"}
    preview = srt_preview(cues or [], start, end) if cues is not None else ""
    fields = range_fields(start, end, confidence, status, preview)
    fields["notes"] = notes or fields.get("notes") or ""
    return {**base, **fields}


def attach_closing_to_session(
    session: dict,
    *,
    closing_text: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Add/update ``closing`` and chain last segment end → closing start → audio end.

    Preserves locked / manual closing unless ``force``.
    """
    segs = list(session.get("segments") or [])
    if not segs:
        return session

    text = closing_text
    if text is None:
        existing = session.get("closing") or {}
        text = existing.get("text") or existing.get("text_preview") or ""

    srt_path = resolve_srt_path(session.get("srt_file"))
    cues = []
    audio_end = float(segs[-1].get("end") or 0)
    if srt_path is not None:
        cues = parse_srt_raw(srt_path)
        if cues:
            audio_end = float(cues[-1][1])
        # Keep resolved path on session for later tooling.
        session = {**session, "srt_file": str(srt_path)}

    old = dict(session.get("closing") or {})
    protected = (not force) and (
        bool(old.get("locked"))
        or (
            old.get("status") in ("manual", "from_qa_txt")
            and old.get("start") is not None
        )
    )

    if protected:
        closing = old
        if text and not closing.get("text"):
            closing = {
                **closing,
                "text": text,
                "text_preview": text[:200],
            }
    else:
        last_start = float(segs[-1].get("start") or 0)
        onset = detect_closing_onset(
            cues, after=last_start, closing_text=text or ""
        )
        if onset is None and old.get("start") is not None:
            onset = float(old["start"])
        # If still none but trailing gap exists after last content, use soft tail:
        # keep missing status with text only.
        closing = build_closing(
            text=text or old.get("text") or "",
            start=onset,
            end=audio_end,
            cues=cues,
            status="auto" if onset is not None else "missing",
            confidence=0.85 if onset is not None else 0.0,
            notes="leadin:closing|auto" if onset is not None else "closing-missing",
        )
        # Preserve meta from old
        if old.get("meta"):
            closing["meta"] = old["meta"]
        if old.get("locked"):
            closing["locked"] = old["locked"]

    # Chain: last segment ends at closing start (when closing has a range)
    new_segs = [dict(s) for s in segs]
    cl_start = closing.get("start")
    if cl_start is not None and closing.get("status") != "missing":
        last = dict(new_segs[-1])
        if not last.get("locked"):
            st = float(last.get("start") or 0)
            end = float(cl_start)
            if end > st:
                last.update(
                    range_fields(
                        st,
                        end,
                        last.get("confidence") or 0.9,
                        last.get("status") or "manual",
                        last.get("srt_preview") or "",
                    )
                )
                # keep prior notes / meta
                if segs[-1].get("notes"):
                    last["notes"] = segs[-1]["notes"]
                if segs[-1].get("meta"):
                    last["meta"] = segs[-1]["meta"]
                if segs[-1].get("locked"):
                    last["locked"] = segs[-1]["locked"]
                new_segs[-1] = last
        closing = {
            **closing,
            **range_fields(
                float(cl_start),
                audio_end,
                closing.get("confidence") or 0.85,
                closing.get("status") or "auto",
                closing.get("srt_preview")
                or (srt_preview(cues, cl_start, audio_end) if cues else ""),
            ),
            "text": closing.get("text") or text or "",
            "text_preview": (closing.get("text") or text or "")[:200],
            "notes": closing.get("notes") or "",
        }
        if old.get("meta"):
            closing["meta"] = old["meta"]
        if closing_text is None and old.get("text"):
            closing["text"] = old["text"]
            closing["text_preview"] = old.get("text_preview") or old["text"][:200]

    return {**session, "segments": new_segs, "closing": closing}
