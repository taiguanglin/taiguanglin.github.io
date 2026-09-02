#!/usr/bin/env python3
"""Build chronological Word → audio mapping JSONs under audio_map2/.

Source of text : 問答錄2/2024-2025 TAI师父答疑汇总 - 截止2025年7月12日.docx
                 (sessions ordered by date; Q&A blocks separated by —— lines,
                  answers introduced by 「Taiguanglin：」)
Source of time : AI-generated .srt under
                 ~/Documents/backup_on_2026-07-16_13inch_macbook/{year}答疑音頻/
Output         : audio_map2/YYYY-MM.json  (2024-02 … 2025-05)

Text fields (q_text / answer_text / questioner / question_time / opening /
closing text) come ONLY from the Word file.  The SRT is used exclusively to
derive play ranges (start/end) and srt_preview cross-reference strings.

Alignment strategy mirrors tool/pdf_audio_map/align.py:
  1. questioner spoken-name variant hit   (strongest anchor)
  2. distinctive question-body needle
  3. answer-opening needle
  4. global re-anchor, then monotonic interpolation for leftovers
Segment end = next segment start; last end = closing start or audio end.

Usage:
  .venv/bin/python build_maps.py --month 2024-02          # dry-run report
  .venv/bin/python build_maps.py --month 2024-02 --apply  # write JSON
  .venv/bin/python build_maps.py --all --apply            # 2024-02 … 2025-05
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import zipfile
import html as html_mod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "pdf_audio_map"))

from common import (  # noqa: E402
    DEFAULT_SRT_ROOT,
    PUNCT_RE,
    empty_range_fields,
    fmt_tc,
    get_converter,
    match_start,
    normalize,
    parse_srt,
    parse_srt_raw,
    question_needles,
    range_fields,
    spoken_name_variants,
    srt_preview,
)

DEFAULT_AUDIO_DIR = ROOT.parent / "audio"  # ~/tai/audio symlink
DOCX_PATH = ROOT / "問答錄2" / "2024-2025 TAI师父答疑汇总 - 截止2025年7月12日.docx"
OUT_DIR = ROOT / "audio_map2"
MONTH_RANGE = ("2024-02", "2025-05")

# ---------------------------------------------------------------------------
# docx parsing
# ---------------------------------------------------------------------------

PARA_RE = re.compile(r"<w:p[ >].*?</w:p>", re.S)
W_T_RE = re.compile(r"<w:t(?: [^>]*)?>(.*?)</w:t>", re.S)

SEPARATOR_RE = re.compile(r"^[—\-＿_]{5,}$")
SESSION_HEADING_RE = re.compile(
    r"^Tai师父(?P<y>\d{4})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日答疑(?:（文字版）)?\s*$"
)
WECHAT_LOG_HEADING_RE = re.compile(
    r"^\d{4}年\d{1,2}月\d{1,2}日Tai师.*?(微信记录|聊天记录).*?（文字版）\s*$"
)
MARKER_PREFIX = "师父说"

# Lines that introduce a spoken answer.  Content may be glued on the same line.
ANSWER_MARKER_RE = re.compile(r"^Taiguanglin\s*[:：]", re.I)
# Unanchored variant for markers glued mid-paragraph（「…有问题吗？Taiguanglin：」）
ANSWER_MARKER_ANYWHERE = re.compile(r"Taiguanglin\s*[:：]", re.I)

# A questioner line: short name + colon, optional trailing timestamp.
NAME_LINE_RE = re.compile(r"^(?P<name>[^：:]{1,30})[:：]\s*(?P<rest>.*)$", re.S)
TIME_PAT = (
    r"(?P<date>\d{4}[.\-/年]\s*\d{1,2}[.\-/月]\s*\d{1,2}日?"
    r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)"
)
TIME_RE = re.compile(TIME_PAT)


def _split_name_time(rest: str) -> Tuple[str, str]:
    """Strip a timestamp from a questioner-line remainder.

    Only when the timestamp sits at the very start or very end of the line —
    never from the middle of real question content (questions may cite dates).
    """
    m = TIME_RE.search(rest)
    if not m:
        return rest, ""
    near_start = m.start() <= 2
    near_end = m.end() >= len(rest) - 2
    if near_start or near_end:
        remaining = (rest[: m.start()] + rest[m.end():]).strip()
        return remaining, m.group("date").strip()
    return rest, ""

# Names that mean "the answer follows" rather than a questioner nickname.
ANSWER_NAME_BLACKLIST = {
    "taiguanglin", "tai師父", "taishi", "tai师", "师父", "師父", "师父说", "師父說",
    "大师父", "大師父",
}

# Label heads glued after a separator（「———心得：」）or numbering labels —
# they open a real block but are not nicknames; the block stays anonymous.
PSEUDO_NAME_RE = re.compile(
    r"^(心得|分享|感想|问题|問題|反馈|回饋|反馈|追問|追问|补充|補充|回复|回覆|"
    r"第[0-9一二三四五六七八九十\.]{1,8}[问問]|问?题?丢失|问?題?丟失|原问题丢失)$"
)


def docx_paragraphs(path: Path) -> List[str]:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    out = []
    for p in PARA_RE.findall(xml):
        text = html_mod.unescape("".join(W_T_RE.findall(p))).strip()
        out.append(text)
    return out


@dataclass
class Group:
    """One Taiguanglin： answer unit inside a chunk."""

    q_paras: List[str] = field(default_factory=list)
    a_paras: List[str] = field(default_factory=list)


@dataclass
class Chunk:
    name: str = ""
    question_time: str = ""
    groups: List[Group] = field(default_factory=list)
    raw_lines: List[str] = field(default_factory=list)


@dataclass
class Part:
    """A sub-session bound to one audio file (source channel)."""

    source: str  # main | 贴吧 | 微信公众号
    chunks: List[Chunk] = field(default_factory=list)
    opening_text: str = ""  # from 师父说 marker (Word text)
    closing_text: str = ""


@dataclass
class WordSession:
    year: int
    month: int
    day: int
    heading: str
    kind: str  # qa | wechat_log
    parts: List[Part] = field(default_factory=list)


CLOSE_WORDS = ("答完", "到这里", "結束", "结束")



def _classify_marker(text: str) -> Optional[Tuple[str, str]]:
    """Return ('open'|'close', source_or_'') for a 师父说 line."""
    body = text[len(MARKER_PREFIX):].lstrip("：:").strip()
    is_tieba = "贴吧" in body
    is_wechat = "公众号" in body
    src = "贴吧" if is_tieba else ("微信公众号" if is_wechat else "")
    if any(w in body for w in CLOSE_WORDS):
        return ("close", src)
    if is_tieba or is_wechat:
        return ("open", src)
    return None


HONOR_START_RE = re.compile(
    r"^(顶礼|頂禮|请问|請問|感恩|师父好|師父好|阿弥陀佛|阿彌陀佛|礼请|禮請|恭请|恭請)"
)
# Names that begin like a salutation AND carry glued content are quoted
# phrases, not nicknames (「顶礼Tai师父，请问：…」).  Name-only lines
# (empty remainder) can keep such names — real nicknames use them too.
HONOR_NAME_START_RE = re.compile(r"^(顶礼|頂禮|请问|請問|拜问|拜問|恭请|恭請)")
DIAG = {"blocks": 0, "anon_blocks": 0, "mid_strict": 0, "folded_groups": 0,
        "glued_sep": 0, "repaired": 0}


def _extract_questioner(line: str) -> Optional[Tuple[str, str]]:
    """Return (name, rest) when the line plausibly opens a question block."""
    if line.startswith(MARKER_PREFIX):
        return None
    m = NAME_LINE_RE.match(line)
    if not m:
        return None
    name = m.group("name").strip()
    nm = normalize(name)
    if not nm or nm in ANSWER_NAME_BLACKLIST:
        return None
    if ANSWER_MARKER_RE.match(line):
        return None
    if len(name) > 15:
        return None
    rest = m.group("rest").strip()
    if rest and HONOR_NAME_START_RE.match(name):
        return None
    # Salutation glue（「Tai师父好：1、…」）— greeting-form names are quoted
    # phrases even when they carry content.  Real nicknames like
    # 「Tai师父的小粉丝」「感恩Tai师父」 do not end in 好.
    if re.search(r"(师父好|師父好|老师好|老師好)$", nm):
        return None
    # Label heads（心得／分享／第N问…）open real blocks but are not nicknames.
    if PSEUDO_NAME_RE.match(nm):
        return None
    return name, rest


def _is_questioner_line(line: str) -> bool:
    """Strict test: a short Name： line that opens a question block.

    Allowed shapes: empty remainder, timestamp-only remainder, or an
    honorific-starting glued question.  Anything else is treated as content.
    """
    got = _extract_questioner(line)
    if not got:
        return False
    _name, rest = got
    if not rest:
        return True
    if TIME_RE.fullmatch(rest):
        return True
    if HONOR_START_RE.match(rest) and len(rest) <= 120:
        return True
    return False


QUESTION_TRAIL_RE = re.compile(r"[?？]$|[吗嗎呢呢吧啊呀么麼]$")
QUESTION_LEAD_RE = re.compile(r"^\s*(?:[0-9一二三四五六七八九十]{1,3}\s*[、.．,，)]|"
                              r"第[0-9一二三四五六七八九十]{1,3}\s*[问問])")
QUESTION_HINT_RE = re.compile(r"请问|請問|请教|請教|求教|怎么|怎麼|如何|为什么|為什麼|"
                              r"是吗|是嗎|对吗|對嗎|感恩|頂禮|顶礼|想确认|想確認|指点|指點")


def _is_followup_question(text: str) -> bool:
    """Heuristic: does this non-marker paragraph read like a NEW question
    (rather than a continuation of the current answer)?

    Used inside a multi-``Taiguanglin：`` block to decide whether a paragraph
    that appears after an answer but before the next marker should open a new
    group's ``q_paras`` instead of being glued onto the current answer.  This is
    what the original design intended ("paragraphs after an answer but before
    the next marker are the next follow-up question") but never implemented —
    the mode stayed "a" forever, which merged follow-up questions (and later
    even their answers) into one answer blob (audio_map2 2025-05-17 极乐是我家).
    """
    t = text.strip()
    if not t:
        return False
    if QUESTION_TRAIL_RE.search(t):
        return True
    if QUESTION_LEAD_RE.match(t) and not _looks_like_answer_continuation(t):
        return True
    if len(t) < 40 and QUESTION_HINT_RE.search(t):
        return True
    return False


def _looks_like_answer_continuation(text: str) -> bool:
    """Guard against mis-firing: numbered lines that are actually Tai's own
    enumerated explanation (「第一…第二…」) or answer-openers (「下一个问题…」).
    """
    t = text.strip()
    if re.match(r"^\s*下一个问题|^\s*下一個問題", t):
        return True
    # answers often restate the question as 「你说…」/「你问…」 then explain.
    if re.match(r"^\s*[你您][说說问问問]", t):
        return True
    return False


def _block_to_chunk(lines: List[str]) -> Chunk:
    """Split block lines into answer groups.

    Text before the first Taiguanglin： marker = question; each marker opens a
    new group whose text is the answer until the next marker.  Paragraphs that
    appear AFTER an answer but BEFORE the next marker are the next (follow-up)
    question — they open a new group's q_paras.  (Post-answer paragraphs are
    classified with :func:`_is_followup_question`; plain continuation prose is
    still appended to the current answer.)
    """
    nonempty = [l for l in lines if l.strip()]
    ch = Chunk(raw_lines=nonempty)
    idx = 0
    # first line: questioner?
    if nonempty:
        got = _extract_questioner(nonempty[0])
        if got:
            ch.name, rest = got
            rest, qtime = _split_name_time(rest)
            ch.question_time = qtime
            if rest:
                ch.groups.append(Group(q_paras=[rest]))
            else:
                ch.groups.append(Group())
            idx = 1
        else:
            ch.name = ""
            ch.groups.append(Group())
            # Label heads（「心得：师父吉祥…」）: strip the label prefix so the
            # question text starts clean.
            m0 = NAME_LINE_RE.match(nonempty[0])
            if m0 and PSEUDO_NAME_RE.match(normalize(m0.group("name").strip()) or " "):
                rest0 = m0.group("rest").strip()
                ch.groups[-1].q_paras = [rest0] if rest0 else []
                idx = 1
    mode = "q"  # collecting question paragraphs for the current group
    while idx < len(nonempty):
        line = nonempty[idx]
        if ANSWER_MARKER_RE.match(line):
            glued = ANSWER_MARKER_RE.sub("", line).strip()
            ch.groups.append(Group())
            mode = "a"
            if glued:
                ch.groups[-1].a_paras.append(glued)
        else:
            # Marker embedded mid-paragraph（「…有问题吗？Taiguanglin：」）:
            # split here — before-text stays with the current group, the
            # remainder opens the answer group.
            m_emb = ANSWER_MARKER_ANYWHERE.search(line)
            if m_emb and m_emb.start() > 0:
                pre = line[: m_emb.start()].strip()
                rest = line[m_emb.end():].strip()
                if pre:
                    if mode == "q":
                        ch.groups[-1].q_paras.append(pre)
                    else:
                        ch.groups[-1].a_paras.append(pre)
                ch.groups.append(Group())
                mode = "a"
                if rest:
                    ch.groups[-1].a_paras.append(rest)
            elif mode == "q":
                ch.groups[-1].q_paras.append(line)
            elif _is_followup_question(line):
                # Post-answer paragraph that reads like a NEW question (e.g. a
                # staggered multi-question post: Q1→A1→Q2→A2…).  Open a fresh
                # group so the next Taiguanglin： marker answers THIS question,
                # not the previous one.  Fixes 2025-05-17 极乐是我家 (Q2 熬腿
                # was glued onto A1 往生愿's answer, Q3/A3 dropped entirely).
                ch.groups.append(Group())
                mode = "q"
                ch.groups[-1].q_paras.append(line)
            else:
                ch.groups[-1].a_paras.append(line)
        idx += 1
    return ch


def _scan_body_events(body: List[str]) -> List[tuple]:
    """Scan session body → ordered events.

    ('block', [lines]) | ('open', source, text) | ('close', source, text)

    A new block starts at: session/separator head, any 师父说 marker, or a
    strict questioner line mid-flow.
    """
    events: List[tuple] = []
    pending: List[str] = []
    at_head = True

    def flush():
        nonlocal pending
        if pending:
            events.append(("block", pending))
            pending = []

    queue = list(body)
    while queue:
        raw = queue.pop(0)
        line = raw.strip()
        if not line:
            continue
        # Separator — pure or glued with the next block's head（「———心得：」、
        # 「———昵称：…」）.  Flush, then reprocess any remainder as its own line.
        dash_m = re.match(r"^([—\-＿_]{5,})(.*)$", line)
        if dash_m:
            flush()
            at_head = True
            DIAG["glued_sep"] += 1
            tail = dash_m.group(2).strip()
            if tail:
                queue.insert(0, tail)
            continue
        if line.startswith(MARKER_PREFIX) and "说" in line[:5]:
            flush()
            cls = _classify_marker(line)
            if cls is None:
                pending.append(line)  # unclassifiable → treat as content
                continue
            kind, src = cls
            text = line[len(MARKER_PREFIX):].lstrip("：:").strip()
            events.append(("open" if kind == "open" else "close", src, text))
            at_head = True
            continue
        got = _extract_questioner(line)
        name_only = bool(got) and not got[1].strip()
        # A bare 「Name：」 line right after a block head（「掌南飞：…」 then
        # 「Tai师父好：」）is salutation content, not a new questioner.
        if got and name_only and len(pending) <= 1 and not at_head:
            pending.append(line)
            continue
        if at_head or _is_questioner_line(line):
            flush()
            if at_head:
                DIAG["blocks"] += 1
            else:
                DIAG["mid_strict"] += 1
            pending = [line]
            at_head = False
            continue
        pending.append(line)
    flush()
    return events


def _discover_sessions(paras: List[str]) -> List[WordSession]:
    sessions: List[WordSession] = []
    i, n = 0, len(paras)
    while i < n:
        t = paras[i]
        hm = SESSION_HEADING_RE.match(t)
        wm = WECHAT_LOG_HEADING_RE.match(t)
        if not hm and not wm:
            i += 1
            continue
        j = i + 1
        while j < n and not (
            SESSION_HEADING_RE.match(paras[j]) or WECHAT_LOG_HEADING_RE.match(paras[j])
        ):
            j += 1
        if hm:
            sess = WordSession(
                year=int(hm.group("y")),
                month=int(hm.group("m")),
                day=int(hm.group("d")),
                heading=t,
                kind="qa",
            )
            sess._raw_body = [
                p for p in paras[i + 1 : j] if p and not p.startswith("完整音频请关注")
            ]  # type: ignore[attr-defined]
        else:
            sess = WordSession(year=0, month=0, day=0, heading=t, kind="wechat_log")
        sessions.append(sess)
        i = j
    return sessions


def parse_docx(path: Path) -> List[WordSession]:
    paras = docx_paragraphs(path)
    sessions = _discover_sessions(paras)

    for sess in sessions:
        if sess.kind != "qa":
            continue
        body: List[str] = sess._raw_body  # type: ignore[attr-defined]
        events = _scan_body_events(body)

        # Only split by source when the day actually has multiple audio files;
        # single-file days keep one main part (师父说 lines become opening /
        # closing text of that part instead of part boundaries).
        avail = {src for src in ("main", "贴吧", "微信公众号")
                 if resolve_media(sess.year, sess.month, sess.day, src)["kind"] != "none"}
        splitable = len(avail) > 1

        parts: List[Part] = [Part(source="main")]
        for ev in events:
            if ev[0] == "block":
                ch = _block_to_chunk(ev[1])
                parts[-1].chunks.append(ch)
                DIAG["anon_blocks"] += 1 if not ch.name else 0
            elif ev[0] == "open":
                _kind, src, text = ev
                cur = parts[-1]
                if splitable and src and cur.chunks and src != cur.source:
                    parts.append(Part(source=src))
                    parts[-1].opening_text = text
                else:
                    if splitable and src and not cur.chunks:
                        cur.source = src
                    if not cur.chunks and not cur.opening_text:
                        cur.opening_text = text
                    elif not cur.chunks:
                        cur.opening_text = text  # latest open before first chunk wins
            else:  # close
                _kind, src, text = ev
                cur = parts[-1]
                target = cur if cur.chunks else (
                    parts[-2] if len(parts) > 1 and parts[-2].chunks and not parts[-2].closing_text else cur
                )
                target.closing_text = text  # last close wins

        sess.parts = [p for p in parts if p.chunks]
    return sessions



# ---------------------------------------------------------------------------
# media resolution
# ---------------------------------------------------------------------------

SOURCE_ALIASES = {
    "main": ["主"],
    "贴吧": ["貼吧"],
    "微信公众号": ["微信公眾號", "公眾號"],
}


def resolve_media(y: int, m: int, d: int, source: str, srt_root: Path = DEFAULT_SRT_ROOT):
    """Find srt/mp3/opus for a session. Handles zero-padded days and （上）/（下）.

    Returns dict: {parts: [{stem,srt,mp3,opus,duration}], combined cues flag}
    """
    sub = f"{y}答疑音頻"
    alias_list = SOURCE_ALIASES.get(source, [source])
    days = [str(d), f"{d:02d}"]

    def find(sfx: str) -> Optional[dict]:
        for alias in alias_list:
            core = f"{alias}" if alias != "主" else ""
            for day in days:
                stems = [f"{y}年{m}月{day}日Tai師父{core}答疑{sfx}"]
                if sfx:
                    stems.append(f"{y}年{m}月{day}日Tai師父{core}答疑{sfx} ")
                else:
                    stems.append(f"{y}年{m}月{day}日Tai師父{core}答疑 ")
                for stem in stems:
                    srt = srt_root / sub / f"{stem}.srt"
                    mp3 = srt_root / sub / f"{stem}.mp3"
                    opus = DEFAULT_AUDIO_DIR / f"{stem}.opus"
                    if srt.exists():
                        return {
                            "stem": stem,
                            "srt_file": str(srt),
                            "mp3_path": str(mp3),
                            "opus_path": str(opus),
                            "audio_file": f"{stem}.opus",
                        }
        return None

    main = find("")
    if main:
        return {"kind": "single", "parts": [main]}
    # split 上/下 (only ever seen for 公眾號)
    up, down = find("（上）"), find("（下）")
    if up and down:
        return {"kind": "split", "parts": [up, down]}
    if up:
        return {"kind": "single", "parts": [up]}
    if down:
        return {"kind": "single", "parts": [down]}
    return {"kind": "none", "parts": []}


# ---------------------------------------------------------------------------
# alignment
# ---------------------------------------------------------------------------

def _collect_name_hits(cues, name: str, converter) -> List[Tuple[float, int]]:
    hits: List[Tuple[float, int]] = []
    seen = set()
    letterish = re.sub(r"\d+", "", normalize(name, converter) or "")
    min_block = 4 if len(letterish) >= 2 else 3
    for variant in spoken_name_variants(name, converter):
        if len(variant) < 2 or variant.isdigit():
            continue
        cursor = 0
        while cursor < len(cues):
            res = match_start(
                cues, cursor, variant,
                min_len=min(2, len(variant)),
                min_block=min(min_block, len(variant)),
                max_scan=len(cues) - cursor,
            )
            if res is None:
                break
            start_t, idx, size = res
            need = min(min_block, len(variant))
            if size >= need and idx not in seen:
                hits.append((start_t, idx))
                seen.add(idx)
            cursor = idx + 1
    hits.sort(key=lambda x: x[0])
    return hits


def _refine_starts_by_questioner(segs, cues, starts, scores, converter, snap_window=90.0):
    notes = [""] * len(starts)
    cache: Dict[str, List[Tuple[float, int]]] = {}
    cursors: Dict[str, int] = {}
    prev_t = 0.0
    for i, seg in enumerate(segs):
        name = (seg.get("questioner") or "").strip()
        if not name:
            if starts[i] is not None:
                prev_t = max(prev_t, float(starts[i]))
            continue
        if name not in cache:
            cache[name] = _collect_name_hits(cues, name, converter)
            cursors[name] = 0
        hits = cache[name]
        ci = cursors[name]
        while ci < len(hits) and hits[ci][0] < prev_t - 0.05:
            ci += 1
        cursors[name] = ci
        if ci >= len(hits):
            if starts[i] is not None:
                prev_t = max(prev_t, float(starts[i]))
            continue
        hit_t = hits[ci][0]
        cur = starts[i]
        near = cur is None or abs(float(cur) - hit_t) <= snap_window
        if near and (cur is None or abs(float(cur) - hit_t) > 1.0):
            starts[i] = hit_t
            scores[i] = max(scores[i], 12.0)
            notes[i] = "snapped to questioner name"
            cursors[name] = ci + 1
            prev_t = hit_t
        else:
            if near:
                cursors[name] = ci + 1
            if starts[i] is not None:
                prev_t = max(prev_t, float(starts[i]))
    return starts, scores, notes


def _interpolate_starts(starts, scores, audio_end):
    n = len(starts)
    if n == 0:
        return [], []
    resolved: List[Optional[float]] = list(starts)
    notes = [""] * n
    known = [i for i, s in enumerate(resolved) if s is not None]
    if not known:
        step = max(audio_end / max(n, 1), 0.5)
        for i in range(n):
            resolved[i] = min(i * step, max(audio_end - 0.5, 0.0))
            notes[i] = "interpolated evenly (no SRT hits)"
        return [float(x) for x in resolved], notes
    first = known[0]
    if first > 0:
        t0, t1 = 0.0, float(resolved[first])
        for k in range(first):
            resolved[k] = t0 + (t1 - t0) * (k + 1) / (first + 1)
            notes[k] = "interpolated"
            scores[k] = max(scores[k], 2.0)
    for a, b in zip(known, known[1:]):
        if b == a + 1:
            continue
        t0, t1 = float(resolved[a]), float(resolved[b])
        gap = b - a
        for k in range(1, gap):
            resolved[a + k] = t0 + (t1 - t0) * k / gap
            notes[a + k] = "interpolated"
            scores[a + k] = max(scores[a + k], 2.0)
    last = known[-1]
    if last < n - 1:
        t0 = float(resolved[last])
        t1 = max(audio_end, t0 + 0.5 * (n - last))
        gap = n - last
        for k in range(1, gap):
            resolved[last + k] = t0 + (t1 - t0) * k / gap
            notes[last + k] = "interpolated"
            scores[last + k] = max(scores[last + k], 2.0)
    out: List[float] = []
    for i, s in enumerate(resolved):
        val = float(s)
        if out and val <= out[-1]:
            val = out[-1] + 0.05
            if not notes[i]:
                notes[i] = "monotonic adjust"
        out.append(val)
    return out, notes


# ---------------------------------------------------------------------------
# duration-aware repair
# ---------------------------------------------------------------------------

METHOD_PRIOR = {"name": 1.0, "name-snap": 0.95, "q_body": 0.85,
                "answer_opening": 0.72, "answer(global)": 0.65, "q_body(global)": 0.7}
MIN_REPAIR_SCORE = 0.52


def _cue_text_between(cues, t0: float, t1: float) -> str:
    return "".join(t for (s, e, t) in cues if s < t1 and e > t0)


def _content_cov(window_text: str, probe: str) -> float:
    """Fraction of the probe covered by matching blocks in the window.

    Unlike a single longest-block measure this tolerates scattered ASR
    substitutions while still separating true reads (~0.7+) from unrelated
    Dharma-talk windows (~0.35-0.45).
    """
    if not window_text or not probe:
        return 0.0
    b = probe[:100]
    sm = difflib.SequenceMatcher(None, window_text, b, autojunk=False)
    total = sum(m.size for m in sm.get_matching_blocks())
    return min(1.0, total / max(1, len(b)))


def _estimate_char_rate(segs_in, resolved, methods) -> float:
    tot_chars = 0
    tot_dur = 0.0
    for i, seg in enumerate(segs_in):
        if i + 1 >= len(resolved):
            break
        # only trust name-anchored ranges for rate estimation
        if not (methods[i] or "").startswith("name"):
            continue
        dur = resolved[i + 1] - resolved[i]
        if dur < 20:
            continue
        chars = len(normalize(seg.get("q_text") or "")) + len(
            normalize(seg.get("answer_text") or "")
        )
        if chars < 200:
            continue
        tot_chars += chars
        tot_dur += dur
    rate = tot_chars / tot_dur if tot_dur > 60 else 4.2
    return max(3.0, min(6.5, rate))


def _rare_shingle_hits(cues, probe: str, top_k: int = 10) -> List[tuple]:
    """Find rare n-grams of the probe in the session cues (verbatim-ish hits).

    4-grams occurring ≤2 times plus ultra-rare 3-grams — the latter survive
    ASR output where runs longer than three chars are broken up.
    Returns [(time, shingle_len)].
    """
    if len(probe) < 4:
        return []
    from collections import Counter
    full = "".join(t for _s, _e, t in cues)
    freq4 = Counter(full[i:i + 4] for i in range(0, max(0, len(full) - 3), 2))
    freq3 = Counter(full[i:i + 3] for i in range(0, max(0, len(full) - 2), 2))
    shingles = []
    seen = set()
    for j in range(0, min(len(probe) - 3, 400), 3):
        g4 = probe[j:j + 4]
        if g4 not in seen and not any(ch in g4 for ch in "，。？！、 \xa0"):
            seen.add(g4)
            if 0 < freq4.get(g4, 0) <= 2:
                shingles.append(g4)
        g3 = probe[j:j + 3]
        if len(g3) == 3 and g3 not in seen and not any(
            ch in g3 for ch in "，。？！、 \xa0"
        ):
            seen.add(g3)
            if freq3.get(g3, 0) == 1:
                shingles.append(g3)
        if len(shingles) >= top_k:
            break
    hits: List[tuple] = []
    for g in shingles:
        res = match_start(cues, 0, g, min_len=len(g), min_block=len(g),
                          max_scan=len(cues))
        if res is not None:
            hits.append((res[0], len(g)))
    return hits


def _bigram_locate(cues, probe: str, t_lo: float, t_hi: float,
                   expect: float) -> Optional[List[tuple]]:
    """Fuzzy content search tolerant of heavy ASR distortion.

    Bigram-presence prescreen over cue offsets, difflib refinement of the
    best windows.  Returns a list of (time, ratio) candidate locations
    (possibly several per neighbourhood) sorted by ratio, or None.
    """
    if len(probe) < 12:
        return None
    times = [s for s, _e, _t in cues]
    texts = [t for _s, _e, t in cues]
    import bisect as _bs

    def to_idx(t: float) -> int:
        return min(len(cues) - 1, max(0, _bs.bisect_right(times, t)))

    i0 = to_idx(t_lo)
    i1 = max(i0 + 1, to_idx(t_hi))
    avg = (cues[-1][1] - cues[0][0]) / max(1, len(cues))
    w = max(3, int(expect / max(avg, 0.8)) + 2)
    pbi = {probe[k:k + 2] for k in range(min(len(probe), 110) - 1)}
    if not pbi:
        return None
    scored = []
    for i in range(i0, i1):
        win = "".join(texts[i:i + w])
        if len(win) < 6:
            continue
        wbi = {win[k:k + 2] for k in range(len(win) - 1)}
        sc = len(pbi & wbi) / len(pbi)
        if sc >= 0.22:
            scored.append((sc, i))
    if not scored:
        return None
    scored.sort(reverse=True)
    out = []
    for _sc, i in scored[:6]:
        lo_i = max(i0, i - w // 2)
        win = "".join(texts[lo_i:i + w])
        sm = difflib.SequenceMatcher(None, win, probe[:90], autojunk=False)
        r = sm.ratio()
        if r >= 0.26:
            out.append((times[i], r))
    if not out:
        return None
    out.sort(key=lambda x: -x[1])
    return out


def _duration_repair(segs_in, cues, converter, resolved, scores, methods,
                     fill_notes, closing_start, audio_end):
    """Re-anchor segments whose assigned time is implausible vs text volume.

    The reading order may differ from the Word order and ASR can mangle
    names, so suspicious segments are matched by content over the whole
    session (order-tolerant); the output order is then re-sorted by time.
    Returns (resolved, scores, methods, fill_notes, perm, n_repaired).
    """
    n = len(segs_in)
    if n == 0:
        return resolved, scores, methods, fill_notes, list(range(n)), 0

    def expected_dur(i: int, rate: float) -> float:
        seg = segs_in[i]
        chars = len(normalize(seg.get("q_text") or "", converter)) + len(
            normalize(seg.get("answer_text") or "", converter)
        )
        return max(4.0, chars / rate)

    rate = _estimate_char_rate(segs_in, resolved, methods)
    ends = []
    for i in range(n):
        nxt = resolved[i + 1] if i + 1 < n else (
            closing_start if closing_start else audio_end
        )
        ends.append(max(resolved[i] + 0.5, nxt))
    suspicious = [
        i for i in range(n)
        if (ends[i] - resolved[i]) < 0.45 * expected_dur(i, rate)
        or (scores[i] / 12.0 if scores[i] else 0.25) < 0.5
    ]

    repaired_total = 0
    name_hits_cache: dict = {}
    _shingle_cache: dict = {}
    used_times: List[float] = []

    def gather(i: int):
        """All evidence candidates for segment i (exact + fuzzy clusters)."""
        seg = segs_in[i]
        expect = expected_dur(i, rate)
        probe = normalize(
            (seg.get("q_text") or "") + " " + (seg.get("answer_text") or ""),
            converter,
        )[:150]
        cands: List[tuple] = []

        qname = seg.get("questioner") or ""
        if qname and qname not in name_hits_cache:
            name_hits_cache[qname] = _collect_name_hits(cues, qname, converter)
        for t, _idx in name_hits_cache.get(qname, []):
            cands.append((t, METHOD_PRIOR["name"], "name"))

        q_needles = question_needles(seg.get("q_text") or "", converter)[:4]
        for needle in q_needles:
            res = match_start(cues, 0, needle, min_len=4, min_block=3,
                              max_scan=len(cues))
            if res is not None:
                cands.append((res[0], METHOD_PRIOR["q_body"], "q_body"))

        a_norm = normalize(seg.get("answer_text") or "", converter)
        a_slices = [a_norm[:60], a_norm[len(a_norm) // 3: len(a_norm) // 3 + 50],
                    a_norm[2 * len(a_norm) // 3: 2 * len(a_norm) // 3 + 50]]
        for sl in a_slices:
            if len(sl) < 10:
                continue
            res = match_start(cues, 0, sl, min_len=6, min_block=3,
                              max_scan=len(cues))
            if res is not None:
                cands.append((res[0], METHOD_PRIOR["answer_opening"], "answer"))

        # Rare-shingle sweep: distinctive 4-grams of this Q&A that hardly
        # occur elsewhere in the session — robust to long-block distortion.
        if i not in _shingle_cache:
            _shingle_cache[i] = _rare_shingle_hits(
                cues, normalize(seg.get("q_text") or "", converter) + a_norm,
            )
        for t, _sz in _shingle_cache[i]:
            cands.append((t, METHOD_PRIOR["q_body"], "shingle"))

        # fuzzy content probes — survive mangled names / paraphrase / order.
        fuzzy_probes = [n for n in q_needles if len(n) >= 14]
        q_norm_full = normalize(seg.get("q_text") or "", converter)
        if len(q_norm_full) >= 20:
            fuzzy_probes.append(q_norm_full[:90])
        fuzzy_probes += [s for s in a_slices if len(s) >= 12]
        seen_probe = set()
        loc_hits: List[tuple] = []
        for pr in fuzzy_probes:
            key = pr[:30]
            if key in seen_probe:
                continue
            seen_probe.add(key)
            res = _bigram_locate(cues, pr, 0.0, audio_end, expect)
            if res:
                loc_hits.extend(res)
        return cands, loc_hits, probe, expect

    def _fuzzy_rescue(i: int):
        """Last-chance locate from the ANSWER's middle slice before clamping.

        The main loop probes question openings + answer thirds; heavily
        paraphrased openings sometimes only survive in the mid-answer text.
        A single strong bigram cluster (r>=0.55) is accepted as evidence.
        """
        a_n = normalize(segs_in[i].get("answer_text") or "", converter)
        if len(a_n) < 24:
            return None
        # window sized from the probe itself — an expect-based window
        # balloons for long answers and dilutes the similarity ratio.
        probes = [a_n[max(0, len(a_n) // 2 - 30):][:80]]
        if len(a_n) >= 40:
            probes.insert(0, a_n[:80])
        hits: List[tuple] = []
        for pr in probes:
            if len(pr) < 12:
                continue
            hits.extend(_bigram_locate(
                cues, pr, 0.0, audio_end, max(20.0, len(pr) / 3.0)
            ) or [])
        if not hits:
            return None
        clusters: dict = {}
        for t, r in hits:
            k = round(t / 45)
            c = clusters.setdefault(k, [t, r])
            if r > c[1]:
                c[1] = r
        ranked = sorted(clusters.values(), key=lambda c: -c[1])
        top = ranked[0]
        if top[1] >= 0.52:
            return round(top[0], 3), top[1]
        # two independent probes agreeing on one neighbourhood is evidence too
        if (
            len(ranked) >= 2
            and ranked[1][1] >= 0.33
            and abs(ranked[0][0] - ranked[1][0]) < 90.0
        ):
            t = min(ranked[0][0], ranked[1][0])
            return round(t, 3), max(top[1], 0.56)
        return None


    for i in suspicious:
        cands, loc_hits, probe, expect = gather(i)
        best_exact = None  # (score, t, label)
        all_scored = []  # (score, t) for runner-up margin
        seen_t = set()
        for t, prior, label in cands:
            key = round(t, 1)
            if key in seen_t:
                continue
            seen_t.add(key)
            win = _cue_text_between(cues, t, t + min(expect * 1.35, 240.0))
            cov = _content_cov(win, probe)
            in_win = resolved[max(i - 1, 0)] - 20 <= t <= ends[i] + 20
            score = 0.62 * cov + 0.33 * prior + (0.05 if in_win else 0.0)
            if any(abs(t - u) < 12.0 for u in used_times):
                score -= 0.18
            all_scored.append((score, t))
            if best_exact is None or score > best_exact[0]:
                best_exact = (score, t, label)

        chosen = None  # (t, label, conf_score)
        if best_exact and best_exact[0] >= MIN_REPAIR_SCORE:
            # demand separation from the best *distant* rival location
            runner = max(
                (s for s, t2 in all_scored if abs(t2 - best_exact[1]) >= 60.0),
                default=0.0,
            )
            if best_exact[0] >= 0.62 or best_exact[0] - runner >= 0.08:
                chosen = (best_exact[1], best_exact[2], best_exact[0])
        elif loc_hits:
            # cluster hits by location (±45s), evaluate per cluster
            clusters: List[dict] = []
            for t, r in sorted(loc_hits, key=lambda x: -x[1]):
                for cl in clusters:
                    if abs(t - cl["t"]) < 45.0:
                        cl["rs"].append(r)
                        break
                else:
                    clusters.append({"t": t, "rs": [r]})
            clusters.sort(key=lambda c: -max(c["rs"]))
            top_cl = clusters[0]
            top = max(top_cl["rs"])
            npro = len(top_cl["rs"])
            runner = max(
                (max(c["rs"]) for c in clusters[1:]), default=0.0
            )
            adj = top + 0.05 * min(3, npro - 1)
            strong = adj >= 0.44 or top >= 0.44
            consensus = npro >= 2 and adj >= 0.38 and (top - runner) >= 0.02
            free = not any(abs(top_cl["t"] - u) < 12.0 for u in used_times)
            if free and (strong or consensus):
                conf = max(0.52, min(0.88, 0.45 + top * 0.8))
                chosen = (top_cl["t"], f"fuzzy({top:.2f}x{npro})", conf)

        if chosen:
            t, label, conf = chosen
            resolved[i] = round(t, 3)
            scores[i] = round(conf * 12.0, 2)
            methods[i] = f"repaired:{label}"
            fill_notes[i] = ""
            used_times.append(t)
            repaired_total += 1
        elif (scores[i] / 12.0 if scores[i] else 0.25) < 0.5:
            resc = _fuzzy_rescue(i)
            if resc:
                t, r = resc
                resolved[i] = t
                scores[i] = round(max(0.56, 0.40 + r * 0.45) * 12.0, 2)
                methods[i] = f"repaired:fuzzy-mid({r:.2f})"
                fill_notes[i] = ""
                used_times.append(t)
                repaired_total += 1
            else:
                # No audio evidence found (question likely paraphrased away or
                # answered on another day).  Clamp into the neighbouring gap
                # proportionally so playback stays sane, and flag for review
                # instead of leaving a red low-conf.
                lo_b = resolved[i - 1] if i > 0 else 0.0
                hi_b = resolved[i + 1] if i + 1 < n else (
                    closing_start if closing_start else audio_end
                )
                gap = max(0.0, hi_b - lo_b)
                t = min(lo_b + max(2.0, gap * 0.25), max(lo_b + 0.5, hi_b - 3.0))
                resolved[i] = round(t, 3)
                scores[i] = round(0.5 * 12.0, 2)
                methods[i] = "no-anchor:clamped"
                fill_notes[i] = "未找到逐字對應，依前後段夾入（待人工確認）"
                repaired_total += 1

    # ── squeeze-fix sweep: anchors that still leave absurdly little time ──
    # (e.g. three high-conf anchors stacked within 0.4s).  Try alternative
    # candidates avoiding other segments' occupied windows; otherwise clamp
    # into the local gap regardless of confidence.
    def _cluster_end(i: int) -> int:
        """Extend cluster past SOFT members while it lacks room."""
        j = i
        while True:
            lo = resolved[i]
            nxt = resolved[j + 1] if j + 1 < n else (
                closing_start if closing_start else audio_end
            )
            tot = sum(e_all[i:j + 1])
            if tot <= max(nxt - lo, tot * 0.999) or j + 1 >= n:
                return j
            nxt_soft = (
                bool(methods[j + 1])
                and ("clamped" in methods[j + 1] or "layout-spread" in methods[j + 1]
                     or not fill_notes[j + 1] and methods[j + 1] == "")
            ) or not methods[j + 1]
            if not nxt_soft:
                return j
            j += 1

    CLAMP_NOTE = "未找到逐字對應，依前後段夾入（待人工確認）"
    ends = []
    for i in range(n):
        nxt = resolved[i + 1] if i + 1 < n else (
            closing_start if closing_start else audio_end
        )
        ends.append(max(resolved[i] + 0.5, nxt))
    squeezed = [
        i for i in range(n)
        if "clamped" not in (methods[i] or "")
        and (ends[i] - resolved[i]) < 0.30 * expected_dur(i, rate)
    ]
    for i in squeezed:
        cands, loc_hits, probe, expect = gather(i)
        occ = []
        for j in range(n):
            if j == i:
                continue
            e_j = expected_dur(j, rate)
            occ.append((resolved[j] + 4.0, resolved[j] + max(15.0, e_j * 0.6)))
        best = None  # (score, t, label)
        allsc = []
        seen_t = set()
        for t, prior, label in cands:
            key = round(t, 1)
            if key in seen_t:
                continue
            seen_t.add(key)
            win = _cue_text_between(cues, t, t + min(expect * 1.35, 240.0))
            cov = _content_cov(win, probe)
            pen = 0.0
            if any(lo <= t <= hi for lo, hi in occ):
                pen += 0.25
            if any(abs(t - u) < 12.0 for u in used_times):
                pen += 0.18
            sc = 0.62 * cov + 0.33 * prior - pen
            allsc.append((sc, t))
            if best is None or sc > best[0]:
                best = (sc, t, label)
        moved = False
        if best and best[0] >= MIN_REPAIR_SCORE:
            runner = max(
                (s for s, t2 in allsc if abs(t2 - best[1]) >= 60.0),
                default=0.0,
            )
            if best[0] >= 0.62 or best[0] - runner >= 0.08:
                resolved[i] = round(best[1], 3)
                scores[i] = round(min(1.0, best[0]) * 12.0, 2)
                methods[i] = f"squeeze-fix:{best[2]}"
                fill_notes[i] = ""
                used_times.append(best[1])
                repaired_total += 1
                moved = True
        if not moved:
            resc = _fuzzy_rescue(i)
            if resc:
                t, r = resc
                resolved[i] = t
                scores[i] = round(max(0.56, 0.40 + r * 0.45) * 12.0, 2)
                methods[i] = f"squeeze-fix:fuzzy-mid({r:.2f})"
                fill_notes[i] = ""
                used_times.append(t)
                repaired_total += 1
                moved = True
        if not moved:
            lo_b = resolved[i - 1] if i > 0 else 0.0
            hi_b = resolved[i + 1] if i + 1 < n else (
                closing_start if closing_start else audio_end
            )
            gap = max(0.0, hi_b - lo_b)
            e_prev = expected_dur(i - 1, rate) if i > 0 else 8.0
            base = lo_b + min(max(8.0, e_prev * 0.5), 60.0)
            t = min(base + gap * 0.15, max(lo_b + 1.0, hi_b - 2.0))
            resolved[i] = round(t, 3)
            scores[i] = round(0.5 * 12.0, 2)
            methods[i] = "squeeze-fix:clamped"
            fill_notes[i] = "錨點擠壓，依前後段夾入（待人工確認）"
            repaired_total += 1

    # ── name-refine: common-word nicknames (慢慢/松/醒…) false-hit early.
    # When several reads of the same name exist, keep the one whose
    # following window actually matches this segment's content. ──
    for i in range(n):
        if "name" not in (methods[i] or ""):
            continue
        seg = segs_in[i]
        qn = seg.get("questioner") or ""
        if not qn:
            continue
        key = ("NR", qn)
        if key not in name_hits_cache:
            name_hits_cache[key] = _collect_name_hits(
                cues, normalize(qn, converter), converter
            )
        hs = [t for t, _ in name_hits_cache[key]]
        if len(hs) < 2:
            continue
        probe_n = normalize(
            (seg.get("q_text") or "") + " " + (seg.get("answer_text") or ""),
            converter,
        )[:150]
        e_i = expected_dur(i, rate)
        win_len = min(e_i * 1.3, 240.0)

        def _cov(t):
            return _content_cov(_cue_text_between(cues, t, t + win_len), probe_n)

        best = None  # (cov, t)
        for t in hs:
            c = _cov(t)
            if best is None or c > best[0]:
                best = (c, t)
        cur_cov = _cov(resolved[i])
        if best and best[0] - cur_cov >= 0.12 and abs(best[1] - resolved[i]) > 25:
            resolved[i] = round(best[1], 3)
            used_times.append(resolved[i])
            methods[i] += "+name-refine"
            repaired_total += 1

    # ── sort to PLAYBACK (time) order BEFORE layout/donate: crushing pairs
    # only make sense on the timeline, not in Word document order. ──
    perm = sorted(range(n), key=lambda k: (resolved[k], k))
    resolved = [resolved[k] for k in perm]
    scores = [scores[k] for k in perm]
    methods = [methods[k] for k in perm]
    fill_notes = [fill_notes[k] for k in perm]

    # enforce strictly increasing starts
    for i in range(1, n):
        if resolved[i] <= resolved[i - 1]:
            resolved[i] = resolved[i - 1] + 0.05

    # ── layout pass: spread stacked clusters by text volume ──
    # When several anchors land within seconds of each other, later members
    # get ~0s playback.  Re-lay such clusters across their available span,
    # proportionally to expected duration, flagging them for review.
    # NOTE: arrays are in PLAYBACK order here but segs_in is still Word
    # order — map expectations through perm so text lengths pair with the
    # correct timeline slots.
    e_all = [expected_dur(perm[i], rate) for i in range(n)]
    i = 0
    while i < n:
        j = i
        while (
            j + 1 < n
            and (resolved[j + 1] - resolved[j])
            < max(3.0, 0.15 * e_all[j])
        ):
            j += 1
        j = _cluster_end(i) if _cluster_end(i) > j else j
        if j > i:
            lo = resolved[i]
            hi = resolved[j + 1] if j + 1 < n else (
                closing_start if closing_start else audio_end
            )
            tot = sum(e_all[i:j + 1])
            # distribute strictly within [lo, hi): proportional shares of the
            # available gap — never overshoot into the next segment's time.
            avail = max(hi - lo, 1.0)
            t = lo
            for k in range(i, j + 1):
                resolved[k] = round(t, 3)
                t += e_all[k] * (avail / tot)
                scores[k] = min(scores[k], 6.0)
                extra = "layout-spread（依文字量展開，待人工確認）"
                fill_notes[k] = f"{fill_notes[k]}; {extra}" if fill_notes[k] else extra
            repaired_total += 1
        i = j + 1

    # ── donate pass: a crushed segment borrows tail time from a neighbour ──
    # whose own span is generously longer than its text needs.  Iterated:
    # huge multi-question blocks may need several rounds of donations.
    for _donate_round in range(4):
        progressed = False
        for i in range(n):
            dur_i = (
                (resolved[i + 1] - resolved[i]) if i + 1 < n
                else ((closing_start if closing_start else audio_end) - resolved[i])
            )
            if dur_i >= 0.35 * e_all[i]:
                continue
            need = min(0.45 * e_all[i], 240.0)
            for nb in (i + 1, i - 1):
                if not (0 <= nb < n):
                    continue
                dur_nb = (
                    (resolved[nb + 1] - resolved[nb]) if nb + 1 < n
                    else ((closing_start if closing_start else audio_end) - resolved[nb])
                )
                if dur_nb < 1.25 * e_all[nb]:
                    continue
                give = min(need, dur_nb - 1.05 * e_all[nb])
                if give < 3.0:
                    continue
                if nb == i + 1:
                    # our end is neighbour's start — push it later
                    resolved[nb] = round(resolved[nb] + give, 3)
                else:
                    # pull our own start earlier into left neighbour's slack
                    resolved[i] = round(max(0.0, resolved[i] - give), 3)
                scores[i] = min(scores[i], 6.0)
                extra = "向相鄰段借時間（待人工確認）"
                fill_notes[i] = f"{fill_notes[i]}; {extra}" if fill_notes[i] else extra
                progressed = True
                break
        if not progressed:
            break

    # ── boundary-probe: when a soft segment's spoken answer bleeds into the
    # NEXT segment's slot, re-cut the boundary where the next segment's own
    # evidence begins (its question needle or its name being called). ──
    for i in range(n - 1):
        m_i = methods[i] or ""
        soft_i = (
            "clamped" in m_i or "fuzzy-mid" in m_i or "layout-spread" in m_i
            or bool(fill_notes[i])
        )
        if not soft_i:
            continue
        j = i + 1
        segj = segs_in[perm[j]]  # segs_in is Word-order; arrays here are playback-order
        lo = resolved[j] + 5.0
        hi_j = (
            resolved[j + 1] if j + 1 < n
            else (closing_start if closing_start else audio_end)
        )
        hi = min(resolved[j] + min(hi_j - resolved[j], 160.0), hi_j - 1.0)
        cands = []
        qn_j = segj.get("questioner") or ""
        if qn_j:
            key = ("BP", qn_j)
            if key not in name_hits_cache:
                name_hits_cache[key] = _collect_name_hits(
                    cues, normalize(qn_j, converter), converter
                )
            cands += [t for t, _ in name_hits_cache[key] if lo <= t <= hi]
        for needle in question_needles(segj.get("q_text") or "", converter)[:2]:
            nrm = normalize(needle, converter)
            if len(nrm) < 4:
                continue
            for cs, ce, ct in cues:
                if cs >= lo and cs <= hi and nrm[:4] in normalize(ct, converter):
                    cands.append(cs)
                    break
        if not cands:
            continue
        t_star = min(cands)
        if t_star - resolved[j] < 25.0:
            continue
        e_j = e_all[j]
        new_dur_j = hi_j - t_star
        dur_i = resolved[j] - resolved[i]
        ok = new_dur_j >= max(8.0, 0.40 * e_j) or (
            dur_i < 0.35 * e_all[i] and new_dur_j >= 0.25 * e_j
        )
        if not ok:
            continue
        resolved[j] = round(t_star, 3)
        scores[j] = min(scores[j], 6.0)
        extra = "邊界重切（待人工確認）"
        fill_notes[j] = f"{fill_notes[j]}; {extra}" if fill_notes[j] else extra
        methods[j] = (methods[j] or "") + "+bcut"
        repaired_total += 1

    # ── evidence-chain: a RUN of soft segments whose true answers lie
    # further ahead gets re-anchored at each segment's earliest needle /
    # name-read hit at-or-after a moving cursor; layout then resizes. ──
    def _soft_idx(k: int) -> bool:
        mk = methods[k] or ""
        return (
            "clamped" in mk or "fuzzy-mid" in mk or "layout-spread" in mk
            or bool(fill_notes[k])
        )

    i = 0
    while i < n:
        if not _soft_idx(i):
            i += 1
            continue
        j = i
        while j + 1 < n and _soft_idx(j + 1):
            j += 1
        if j > i:
            cursor = resolved[i]
            moved = False
            for k in range(i, j + 1):
                segk = segs_in[perm[k]]
                cands = []
                qnk = segk.get("questioner") or ""
                if qnk:
                    key = ("EC", qnk)
                    if key not in name_hits_cache:
                        name_hits_cache[key] = _collect_name_hits(
                            cues, normalize(qnk, converter), converter
                        )
                    cands = [t for t, _ in name_hits_cache[key] if t >= cursor]
                if not cands:
                    for nd in question_needles(
                        segk.get("q_text") or "", converter
                    )[:3]:
                        nrm = normalize(nd, converter)
                        if len(nrm) < 4:
                            continue
                        hit = None
                        for cs, _ce, ct in cues:
                            if cs >= cursor and nrm[:4] in normalize(ct, converter):
                                hit = cs
                                break
                        if hit is not None:
                            cands.append(hit)
                limit = resolved[k] + max(300.0, 2.0 * e_all[k])
                cands = [t for t in cands if t <= limit]
                if cands:
                    t = min(cands)
                    if abs(t - resolved[k]) > 15:
                        resolved[k] = round(t, 3)
                        methods[k] = (methods[k] or "") + "+echain"
                        scores[k] = min(scores[k], 6.0)
                        moved = True
                    cursor = max(cursor, t) + 5.0
                else:
                    cursor = resolved[k] + max(20.0, e_all[k] * 0.5)
            if moved:
                repaired_total += 1
        i = j + 1

    # ── final consistency: re-sort by time, monotonic, re-spread crushes ──
    order2 = sorted(range(n), key=lambda k: resolved[k])
    if order2 != list(range(n)):
        resolved = [resolved[k] for k in order2]
        scores = [scores[k] for k in order2]
        methods = [methods[k] for k in order2]
        fill_notes = [fill_notes[k] for k in order2]
        e_all = [e_all[k] for k in order2]
        perm = [perm[k] for k in order2]
    for i in range(1, n):
        if resolved[i] <= resolved[i - 1]:
            resolved[i] = resolved[i - 1] + 0.05
    i = 0
    while i < n:
        j = i
        while (
            j + 1 < n
            and (resolved[j + 1] - resolved[j])
            < max(3.0, 0.15 * e_all[j])
        ):
            j += 1
        j = _cluster_end(i) if _cluster_end(i) > j else j
        if j > i:
            lo = resolved[i]
            hi = resolved[j + 1] if j + 1 < n else (
                closing_start if closing_start else audio_end
            )
            tot = sum(e_all[i:j + 1])
            # distribute strictly within [lo, hi): proportional shares of the
            # available gap — never overshoot into the next segment's time.
            avail = max(hi - lo, 1.0)
            t = lo
            for k in range(i, j + 1):
                resolved[k] = round(t, 3)
                t += e_all[k] * (avail / tot)
                scores[k] = min(scores[k], 6.0)
                extra = "layout-spread（依文字量展開，待人工確認）"
                fill_notes[k] = f"{fill_notes[k]}; {extra}" if fill_notes[k] else extra
        i = j + 1

    # ── honesty sweeps: surface residual anomalies for human review ──
    for i in range(n):
        nxt_i = (
            resolved[i + 1] if i + 1 < n
            else (closing_start if closing_start else audio_end)
        )
        short = (nxt_i - resolved[i]) < 0.45 * e_all[i]
        if short:
            extra = "時長明顯短於文字量（待人工確認）"
            fill_notes[i] = f"{fill_notes[i]}; {extra}" if fill_notes[i] else extra
            scores[i] = min(scores[i], 6.0)
    for i in range(n - 1):
        win_j = _cue_text_between(
            cues, resolved[i + 1],
            resolved[i + 1] + min(e_all[i + 1] * 1.2, 200.0),
        )
        if len(win_j) < 20:
            continue
        probe_j = normalize(
            (segs_in[perm[i + 1]].get("q_text") or "")
            + " " + (segs_in[perm[i + 1]].get("answer_text") or ""),
            converter,
        )[:150]
        probe_i = normalize(
            (segs_in[perm[i]].get("q_text") or "")
            + " " + (segs_in[perm[i]].get("answer_text") or ""),
            converter,
        )[:150]
        cov_j = _content_cov(win_j, probe_j)
        cov_i = _content_cov(win_j, probe_i)
        if cov_i - cov_j >= 0.15:
            extra = "窗口開頭疑似前段內容（待人工確認）"
            fill_notes[i + 1] = (
                f"{fill_notes[i + 1]}; {extra}" if fill_notes[i + 1] else extra
            )
            scores[i + 1] = min(scores[i + 1], 6.0)

    return resolved, scores, methods, fill_notes, perm, repaired_total


def align_part(part: Part, media: dict, converter, session_id: str) -> dict:
    """Align one Part against its (possibly split) SRT timeline."""
    segs_in = []
    gi = 0
    for ch in part.chunks:
        # 時間序彙總的每個 chunk 直接對應一段（不再依章節版 word-*.json 拆子題；
        # 該索引已移除，build_maps.py 已凍結為不拆分）。
        for g in ch.groups:
            gi += 1
            q_text = "\n".join(g.q_paras).strip()
            a_text = "\n\n".join(g.a_paras).strip()
            segs_in.append(
                {
                    "index": gi,
                    "questioner": ch.name,
                    "question_time": ch.question_time,
                    "q_text": q_text,
                    "answer_text": a_text,
                }
            )

    result = {
        "session_id": session_id,
        "opening": None,
        "segments": [],
        "closing": None,
    }

    # merge consecutive groups with empty question AND empty answer guards:
    # a follow-up group whose q_text is empty means Tai kept answering — fold
    # it into the previous segment instead of emitting a blank card.
    merged: List[dict] = []
    for seg in segs_in:
        if merged and not seg["q_text"] and (
            not seg["questioner"] or seg["questioner"] == merged[-1]["questioner"]
        ):
            tail = seg["answer_text"]
            if tail:
                merged[-1]["answer_text"] = (
                    (merged[-1]["answer_text"] + "\n\n" + tail).strip()
                )
            continue
        merged.append(seg)
    segs_in = merged
    # re-number
    for i, seg in enumerate(segs_in, start=1):
        seg["index"] = i

    if media["kind"] == "none":
        out_segs = []
        for seg in segs_in:
            f = empty_range_fields()
            f["notes"] = "no SRT/audio found for this date+source"
            out_segs.append({**seg, **f})
        result["segments"] = out_segs
        result["_media_missing"] = True
        return result

    cues_norm: List[Tuple[float, float, str]] = []
    cues_raw_all: List[Tuple[float, float, str]] = []
    spans = []  # (offset, end_of_part)
    offset = 0.0
    for pinfo in media["parts"]:
        pcues = parse_srt(Path(pinfo["srt_file"]), converter)
        praw = parse_srt_raw(Path(pinfo["srt_file"]))
        dur = pcues[-1][1] if pcues else 0.0
        pinfo["duration_est"] = round(dur, 3)
        spans.append((offset, offset + dur, pinfo))
        cues_norm.extend([(s + offset, e + offset, t) for (s, e, t) in pcues])
        # apply the SAME part offset to raw cues so srt_preview lookups work
        # on the combined timeline (split 上/下 days previously showed blank
        # previews for every second-half segment).
        cues_raw_all.extend([(s + offset, e + offset, t) for s, e, t in praw])
        offset += dur
    audio_end = cues_norm[-1][1] if cues_norm else offset

    cues = cues_norm
    cursor_idx = 0
    starts: List[Optional[float]] = []
    scores: List[float] = []
    methods: List[str] = []

    for seg in segs_in:
        res = None
        via = ""
        for name in spoken_name_variants(seg.get("questioner") or "", converter):
            if len(name) < 2:
                continue
            res = match_start(
                cues, cursor_idx, name, min_len=2, min_block=min(4, len(name)), max_scan=300
            )
            if res is not None:
                via = "name"
                break
        if res is None:
            for needle in question_needles(seg.get("q_text") or "", converter):
                res = match_start(cues, cursor_idx, needle, min_len=6, min_block=6, max_scan=300)
                if res is not None and res[2] >= 6:
                    via = "q_body"
                    break
                res = None
        if res is None and seg.get("answer_text"):
            a = normalize(seg["answer_text"], converter)[:60]
            res = match_start(cues, cursor_idx, a, min_len=6, min_block=5)
            if res is not None:
                via = "answer_opening"
        if res is None:  # global re-anchor
            for needle in question_needles(seg.get("q_text") or "", converter):
                res = match_start(cues, 0, needle, min_len=8, min_block=8, max_scan=len(cues))
                if res is not None:
                    via = "q_body(global)"
                    break
        if res is None and seg.get("answer_text"):
            ga = normalize(seg["answer_text"], converter)[:90]
            res = match_start(cues, 0, ga, min_len=10, min_block=10, max_scan=len(cues))
            if res is not None:
                via = "answer(global)"
        if res is None:
            starts.append(None)
            scores.append(0.0)
            methods.append("")
            continue
        start_time, cue_idx, score = res
        if starts and any(s is not None for s in starts):
            prev = max(s for s in starts if s is not None)
            if start_time < prev:
                starts.append(None)
                scores.append(0.0)
                methods.append("")
                continue
        starts.append(start_time)
        scores.append(max(float(score), 12.0) if via == "name" else float(score))
        methods.append(via)
        cursor_idx = cue_idx + 1

    starts, scores, snap_notes = _refine_starts_by_questioner(
        segs_in, cues, starts, scores, converter
    )
    for i, sn in enumerate(snap_notes):
        if sn and "name" not in methods[i]:
            methods[i] = methods[i] + "+snap" if methods[i] else "name-snap"
    resolved, fill_notes = _interpolate_starts(starts, scores, audio_end)

    # closing range (search from the tail so 收場 phrasing wins over mid-text)
    closing_start = None
    if part.closing_text:
        needle = normalize(part.closing_text, converter)[:24]
        tail_begin = max(0, len(cues) - 400)
        while needle and closing_start is None and len(needle) >= 5:
            res = match_start(cues, tail_begin, needle, min_len=4, min_block=4,
                              max_scan=len(cues) - tail_begin)
            if res is not None:
                closing_start = res[0]
            else:
                needle = needle[: int(len(needle) * 0.7)]

    # Duration-aware repair: text volume vs assigned audio time must be
    # plausible; re-anchor suspicious segments by content over the whole
    # session (reading order may differ from Word order) and re-sort.
    def _valid_closing(cs: Optional[float], res_list: List[float]) -> Optional[float]:
        """A closing hit earlier than any segment start is a false positive."""
        if cs is not None and res_list and cs <= max(res_list):
            return None
        return cs

    closing_start = _valid_closing(closing_start, resolved)
    resolved, scores, methods, fill_notes, perm, n_repaired = _duration_repair(
        segs_in, cues, converter, resolved, scores, methods, fill_notes,
        closing_start, audio_end,
    )
    closing_start = _valid_closing(closing_start, resolved)
    DIAG["repaired"] += n_repaired
    if perm != list(range(len(segs_in))):
        segs_in = [segs_in[k] for k in perm]
        snap_notes = [snap_notes[k] for k in perm]
    # playback order = time order after repair
    for i, seg in enumerate(segs_in, start=1):
        seg["index"] = i

    out_segs = []
    for i, seg in enumerate(segs_in):
        end = resolved[i + 1] if i + 1 < len(resolved) else (
            closing_start if closing_start else max(audio_end, resolved[i] + 0.5)
        )
        if end <= resolved[i]:
            end = resolved[i] + 0.5
        conf = min(1.0, scores[i] / 12.0) if scores[i] else 0.25
        preview = srt_preview(cues_raw_all, resolved[i], end)
        fields = range_fields(resolved[i], end, conf, "auto", preview)
        note_parts = [m for m in [methods[i]] if m]
        if snap_notes[i]:
            note_parts.append(snap_notes[i])
        if fill_notes[i]:
            note_parts.append(fill_notes[i])
        elif conf < 0.4 and not snap_notes[i]:
            note_parts.append(f"low confidence score={scores[i]}")
        fields["notes"] = "; ".join(note_parts)
        out_segs.append({**seg, **fields})

    opening = None
    if part.opening_text or out_segs:
        end = out_segs[0]["start"] if out_segs else audio_end
        intro = normalize(part.opening_text or "今天是", converter)[:20] or normalize("今天是")
        scan = 60 if part.opening_text else 40
        res = match_start(cues, 0, intro, min_len=3, min_block=3, max_scan=scan)
        start = res[0] if res else 0.0
        if start >= end:
            start = 0.0
        preview = srt_preview(cues_raw_all, start, end)
        fields = range_fields(start, end, 0.6 if res else 0.3, "auto", preview)
        opening = {
            "text": part.opening_text,
            "text_preview": part.opening_text[:80],
            **fields,
        }

    closing = None
    if part.closing_text:
        cend = audio_end
        cstart = closing_start if closing_start is not None else max(
            out_segs[-1]["end"] if out_segs else 0.0, cend - 30
        )
        preview = srt_preview(cues_raw_all, cstart, cend)
        fields = range_fields(cstart, cend, 0.85 if closing_start is not None else 0.3,
                              "auto", preview)
        closing = {
            "text": part.closing_text,
            "text_preview": part.closing_text[:80],
            **fields,
        }

    result["opening"] = opening
    result["segments"] = out_segs
    result["closing"] = closing
    return result


# ---------------------------------------------------------------------------
# assembly + write
# ---------------------------------------------------------------------------


def question_id(session_id: str, index: int, q_text: str) -> str:
    h = hashlib.sha1(f"{session_id}#{index}#{q_text[:80]}".encode()).hexdigest()[:12]
    return f"question-{h}"


def build_session_payload(sess: WordSession, converter) -> Optional[dict]:
    date = f"{sess.year:04d}-{sess.month:02d}-{sess.day:02d}"
    sessions_out = []
    for part in sess.parts:
        slug = {"main": "main", "贴吧": "tieba", "微信公众号": "wechat"}.get(part.source, "src")
        sid = f"{date}-{slug}"
        media = resolve_media(sess.year, sess.month, sess.day, part.source)
        base_src = {"main": "主頻道", "贴吧": "貼吧", "微信公众号": "微信公眾號"}.get(
            part.source, part.source
        )
        # Word text failed to split by source (missing 师父说 transition) but the
        # day has both 贴吧 + 微信公众号 audio → align against a combined
        # tieba→wechat timeline; segments land in whichever span matched.
        if len(sess.parts) == 1 and part.source in ("贴吧", "微信公众号"):
            mt = resolve_media(sess.year, sess.month, sess.day, "贴吧")
            mw = resolve_media(sess.year, sess.month, sess.day, "微信公众号")
            if mt["kind"] != "none" and mw["kind"] != "none":
                media = {"kind": "split", "parts": mt["parts"] + mw["parts"]}
                base_src = "貼吧＋微信公眾號（文字檔未分段）"
                sid = f"{date}-main"
        aligned = align_part(part, media, converter, sid)
        payload = {
            "session_id": sid,
            "year": sess.year,
            "month": sess.month,
            "day": sess.day,
            "date": date,
            "source": part.source,
            "resolved_source": base_src,
            "docx_heading": sess.heading,
            "audio_file": media["parts"][0]["audio_file"] if media["parts"] else "",
            "srt_file": media["parts"][0]["srt_file"] if media["parts"] else "",
            "media_kind": media["kind"],
            "media_parts": [
                {k: p[k] for k in ("stem", "audio_file", "srt_file", "mp3_path", "opus_path")}
                | ({"duration_est": p.get("duration_est")} if p.get("duration_est") else {})
                for p in media["parts"]
            ],
            "opening": aligned.get("opening"),
            "segments": aligned.get("segments") or [],
            "closing": aligned.get("closing"),
        }
        for i, seg in enumerate(payload["segments"], start=1):
            seg.setdefault("index", i)
            seg["question_id"] = question_id(sid, i, seg.get("q_text") or "")
            seg["stable_key"] = f"{sid}#{i}"
            qp = seg.get("q_text") or ""
            ap = seg.get("answer_text") or ""
            seg["q_preview"] = qp[:100] + ("…" if len(qp) > 100 else "")
            seg["answer_preview"] = ap[:160] + ("…" if len(ap) > 160 else "")
        # `locked` is a dead legacy field (align 不再讀取、審核 UI 不再顯示)——
        # 硬性移除，避免誤導。
        for part in (payload["opening"], payload["closing"]):
            if part:
                part.pop("locked", None)
        for seg in payload["segments"]:
            seg.pop("locked", None)
        sessions_out.append(payload)
    return sessions_out


def months_iter(all_months: bool, month_args: List[str]):
    if month_args:
        for m in month_args:
            yield m
        return
    y0, m0 = map(int, MONTH_RANGE[0].split("-"))
    y1, m1 = map(int, MONTH_RANGE[1].split("-"))
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--month", action="append", help="YYYY-MM (repeatable)")
    ap.add_argument("--all", action="store_true", help=f"{MONTH_RANGE[0]} … {MONTH_RANGE[1]}")
    ap.add_argument("--docx", type=Path, default=DOCX_PATH)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--srt-root", type=Path, default=DEFAULT_SRT_ROOT)
    ap.add_argument("--apply", action="store_true", help="write JSON files")
    args = ap.parse_args(argv)

    if not args.all and not args.month:
        ap.error("pass --month YYYY-MM (repeatable) or --all")

    converter = get_converter()

    print(f"parsing {args.docx}")
    sessions = parse_docx(args.docx)
    qa = [s for s in sessions if s.kind == "qa"]
    logs = [s for s in sessions if s.kind == "wechat_log"]
    print(f"sessions: {len(qa)} QA + {len(logs)} wechat-log (skipped)")

    wanted = set(months_iter(args.all, args.month or []))
    total_stats: Dict[str, dict] = {}
    warnings: List[str] = []

    for sess in qa:
        key = f"{sess.year:04d}-{sess.month:02d}"
        if key not in wanted:
            continue
        built = build_session_payload(sess, converter)
        for payload in built:
            total_stats.setdefault(key, {"sessions": 0, "segments": 0, "matched": 0,
                                         "low_conf": 0, "interpolated": 0,
                                         "pending": 0,
                                         "missing": 0, "openings_ok": 0, "closings_ok": 0})
            st = total_stats[key]
            st["sessions"] += 1
            st["segments"] += len(payload["segments"])
            for seg in payload["segments"]:
                if seg.get("start") is None:
                    st["missing"] += 1
                else:
                    st["matched"] += 1
                    if (seg.get("confidence") or 0) < 0.5:
                        st["low_conf"] += 1
                    if "interpolated" in (seg.get("notes") or ""):
                        st["interpolated"] += 1
                    if "no-anchor:clamped" in (seg.get("notes") or "") or (
                        "待人工確認" in (seg.get("notes") or "")
                    ):
                        st["pending"] += 1
            if payload["opening"] and payload["opening"].get("start") is not None:
                st["openings_ok"] += 1
            if payload["closing"] and payload["closing"].get("start") is not None:
                st["closings_ok"] += 1
            if payload["media_kind"] == "none":
                warnings.append(
                    f"{payload['session_id']}: no SRT/audio found ({payload['source']})"
                )

    for key in sorted(total_stats):
        st = total_stats[key]
        print(
            f"[{key}] sessions={st['sessions']} segs={st['segments']} "
            f"matched={st['matched']} missing={st['missing']} "
            f"low_conf={st['low_conf']} interpolated={st['interpolated']} "
            f"pending={st.get('pending', 0)} "
            f"opening_ok={st['openings_ok']} closing_ok={st['closings_ok']}"
        )
    for w in warnings:
        print("WARN:", w)

    if args.apply:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        # regroup payloads per month and write
        per_month: Dict[str, list] = {}
        for sess in qa:
            key = f"{sess.year:04d}-{sess.month:02d}"
            if key not in wanted:
                continue
            per_month.setdefault(key, []).extend(build_session_payload(sess, converter))
        for key, sessions_out in sorted(per_month.items()):
            stats = total_stats.get(key, {})
            doc = {
                "month": key,
                "book": "word-chrono",
                "version": 1,
                "stats": stats,
                "sessions": sessions_out,
            }
            path = args.out_dir / f"{key}.json"
            path.write_text(
                json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
            )
            print(f"wrote {path}  ({len(sessions_out)} sessions)")
    else:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
