#!/usr/bin/env python3
"""Phase 1 — parse the chronological Q&A docx into per-session chapter structures.

Source: 問答錄2/2024-2025 TAI师父答疑汇总 - 截止2025年7月12日.docx
Spec:   PLAN_mono_realignment.md §Phase 1 (block model, ghost-heading rule,
        historical-annotation rule, chat-log whitelist).

Output:
  build/chrono_sessions.json          — chapters with ordered QA blocks
  build/chrono_parse_anomalies.md     — anomaly report
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

TOOL = Path(__file__).resolve().parent
ROOT = TOOL.parents[1]
DOCX = ROOT / "問答錄2" / "2024-2025 TAI师父答疑汇总 - 截止2025年7月12日.docx"
BUILD = TOOL / "build"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

TITLE_RE = re.compile(r"^Tai师父(20\d{2})年(\d{1,2})月(\d{1,2})日答疑（文字版）?$")
CHATLOG_RE = re.compile(r"^(20\d{2})年(\d{1,2})月(\d{1,2})日Tai师父微信记录完整版（文字版）?$")
DATE_IN_TITLE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
SEP_RE = re.compile(r"^[—_]{10,}$")
MARKER_RE = re.compile(r"^Taiguanglin\s*[：:]\s*(.*)$", re.S)
NICK_RE = re.compile(r"^([^：:\n]{1,30})[：:]\s*(.*)$", re.S)
ASK_TIME_RE = re.compile(r"(20\d{2})[-.](\d{1,2})[-.](\d{1,2})(?:\s+(\d{1,2}:\d{2}))?")
TIME_ONLY_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
PROMO_RE = re.compile(r"^完整音频请关注微信公众号")
YEAR_NOTE_RE = re.compile(r"[（(]20\d{2}\s*年[^）)]*[）)]")  # historical annotation
TRANSITION_RE = re.compile(r"^师父说[：:]")

EXCLUDE_NICK = {"taiguanglin", "师父说", "目录", "taiguanglin："}
# greeting/politeness openers commonly glued before the real question
BAD_NICK_SUBSTR = ("顶礼", "感恩", "请问", "南无", "阿弥陀佛", "弟子", "师父")
BAD_NICK_PREFIX = ("tai师父", "tai师", "taiguanglin", "师父")


def bad_nick(nick: str) -> bool:
    lo = nick.lower().strip("：: ")
    return (
        lo in EXCLUDE_NICK
        or any(s in lo for s in BAD_NICK_SUBSTR)
        or lo.startswith(BAD_NICK_PREFIX)
    )


def para_text(p) -> str:
    """Ordered text of a paragraph; w:br → '\n', w:tab → ' '."""
    out = []
    for r in p.iter():
        if r.tag == W + "t":
            out.append(r.text or "")
        elif r.tag == W + "br":
            out.append("\n")
        elif r.tag == W + "tab":
            out.append(" ")
    return "".join(out)


def clean(s: str) -> str:
    s = (s or "").replace("\u00a0", " ").replace("\u3000", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def has_bookmark_toc(p) -> str | None:
    for b in p.iter(W + "bookmarkStart"):
        nm = b.get(W + "name") or ""
        if nm.startswith("_Toc"):
            return nm
    return None


def is_title_styled(p) -> bool:
    """rStyle '标题 2 字符' (=20) and/or bold run — used for ghost headings."""
    for r in p.iter(W + "rStyle"):
        if (r.get(W + "val") or "") == "20":
            return True
    return False


def load_document():
    xml = zipfile.ZipFile(DOCX).read("word/document.xml")
    tree = ET.fromstring(xml)
    body = tree.find(W + "body")
    paras = []
    for child in body:
        if child.tag == W + "p":
            paras.append(child)
        # skip the TOC <w:sdt> here; extract_toc scans the whole tree instead
    return tree, paras


def extract_toc(tree):
    """anchor -> title text from TOC hyperlinks (page numbers are dead cache)."""
    toc = []
    for p in tree.iter(W + "p"):
        styles = [s.get(W + "val") for s in p.iter(W + "pStyle")]
        if not any(s in ("TOC", "TOC1", "TOC2", "TOC3") for s in styles):
            continue
        for h in p.iter(W + "hyperlink"):
            anchor = h.get(W + "anchor") or ""
            txt = "".join(t.text or "" for t in h.iter(W + "t"))
            txt = re.sub(r"\d+$", "", txt.strip())  # strip cached page number
            if anchor:
                toc.append((anchor, txt))
    return toc


def new_block(seq, asker_raw, ask_time):
    return {
        "seq": seq,
        "asker_raw": asker_raw or "",
        "ask_time": ask_time or "",
        "q_text": "",
        "a_text": "",
        "no_answer": False,
    }


class Chapter:
    def __init__(self, idx, date_iso, title, genre, bookmark):
        self.index = idx
        self.session_date = date_iso
        self.title = title
        self.genre = genre          # 'qa' | 'chat-log'
        self.bookmark = bookmark    # _Toc name or None (ghost)
        self.blocks: list[dict] = []
        self.transitions: list[str] = []
        self.loose_chars = 0        # text not captured by any block

    def to_dict(self):
        return {
            "index": self.index,
            "session_date": self.session_date,
            "title": self.title,
            "genre": self.genre,
            "bookmark": self.bookmark,
            "n_blocks": len(self.blocks),
            "transitions": self.transitions,
            "loose_chars": self.loose_chars,
            "blocks": self.blocks,
        }


def parse_chapter_lines(ch: Chapter, lines_with_idx):
    """State machine over cleaned non-empty lines of one chapter."""
    state = "idle"           # idle | question | answer | appendix
    cur = None
    last_asker = ""

    def close():
        nonlocal cur, state
        if cur is not None:
            cur["no_answer"] = not cur["a_text"].strip()
            cur["seq"] = len(ch.blocks) + 1
            ch.blocks.append(cur)
        cur = None
        state = "idle"

    def norm_tail(t):  # collapse internal newlines to space, trim
        return clean(t.replace("\n", " "))

    for raw, _idx in lines_with_idx:
        line = clean(raw)
        if not line:
            continue
        if PROMO_RE.match(line):
            continue
        m = MARKER_RE.match(line)
        if m:
            tail = m.group(1) or ""
            if YEAR_NOTE_RE.search(tail):
                # historical annotation → append to previous block's a_text
                if cur is not None:
                    cur["a_text"] += f"\n〔历史注记〕{norm_tail(line)}"
                    state = "appendix"
                else:
                    ch.loose_chars += len(line)
                continue
            if state == "answer":
                # merged multi-question unit: each numbered follow-up gets its
                # own Taiguanglin marker → close answered block, inherit asker
                close()
                cur = new_block(len(ch.blocks) + 1, last_asker, "")
            elif cur is None:
                cur = new_block(len(ch.blocks) + 1, last_asker, "")
            if tail:
                cur["a_text"] = norm_tail(tail)
            state = "answer"
            continue
        if SEP_RE.match(line):
            if cur is not None:
                close()
            continue
        if TRANSITION_RE.match(line):
            ch.transitions.append(norm_tail(line))
            close()
            continue
        tm = ASK_TIME_RE.search(line)
        num_re = re.compile(r"^(?:\d{1,2}[、.．,，]|[一二三四五六七八九十]{1,3}[、.．])")
        num_open = state == "answer" and bool(num_re.match(line))
        nm = NICK_RE.match(line)
        nick_open = False
        nick = rest = ""
        if nm:
            nick = nm.group(1).strip()
            rest = nm.group(2) or ""
            ok_len = len(line) <= 40 or (state in ("idle", "appendix") and len(nick) <= 25)
            nick_open = (
                not bad_nick(nick)
                and not TIME_ONLY_RE.match(nick)
                and (tm or ok_len)
                and not nick.startswith("<")
            )
        if nick_open:
            close()
            at = ""
            if tm:
                at = f"{tm.group(1)}-{int(tm.group(2)):02d}-{int(tm.group(3)):02d}"
                if tm.group(4):
                    at += f" {tm.group(4)}"
                rest = ASK_TIME_RE.sub("", rest).strip()
            last_asker = nick
            cur = new_block(len(ch.blocks) + 1, nick, at)
            if rest:
                cur["q_text"] = norm_tail(rest)
            state = "question"
            continue
        if num_open:
            # swallowed numbered question inside an answer → its own segment
            close()
            cur = new_block(len(ch.blocks) + 1, last_asker, "")
            cur["q_text"] = norm_tail(line)
            state = "question"
            continue
        # plain content line
        if cur is None:
            ch.loose_chars += len(line)
            continue
        if state == "answer":
            cur["a_text"] = (cur["a_text"] + "\n" + line).strip()
        else:
            cur["q_text"] = (cur["q_text"] + "\n" + line).strip()
    close()


def main():
    tree, paras = load_document()
    toc = extract_toc(tree)

    # ---- scan body: find boundaries -------------------------------------
    boundaries = []  # (para_index, date_iso, title, bookmark|None, genre)
    for i, p in enumerate(paras):
        txt = clean(para_text(p))
        if not txt or len(txt) > 60:
            continue
        bm = has_bookmark_toc(p)
        m = TITLE_RE.match(txt) or CHATLOG_RE.match(txt)
        if not m:
            continue
        genre = "qa"
        if CHATLOG_RE.match(txt):
            genre = "chat-log"
        dm = DATE_IN_TITLE.search(txt)
        date_iso = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
        boundaries.append((i, date_iso, txt, bm, bool(bm), genre))

    real = [b for b in boundaries if b[4]]
    ghosts = [b for b in boundaries if not b[4]]
    # ---- TOC ↔ body order validation ------------------------------------
    toc_dates = []
    for anchor, t in toc:
        dm = DATE_IN_TITLE.search(t)
        toc_dates.append(f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}" if dm else "?")
    body_dates = [b[1] for b in real]
    order_ok = toc_dates == body_dates
    if not order_ok:
        diffs = [(i, a, b) for i, (a, b) in enumerate(zip(toc_dates, body_dates)) if a != b]
        print(f"[debug] toc={len(toc_dates)} body_real={len(body_dates)} first_diffs={diffs[:6]}")

    # ---- build chapters: merge consecutive same-date (ghost+real) -------
    chapters: list[Chapter] = []
    merged_ghosts = []
    for i, date_iso, txt, bm, is_real, genre in boundaries:
        if chapters and chapters[-1].session_date == date_iso:
            merged_ghosts.append((date_iso, txt, bool(bm)))
            continue  # same-day continuation (ghost heading precedes real one)
        ch = Chapter(len(chapters) + 1, date_iso, txt, genre, bm)
        chapters.append(ch)

    # ---- slice paragraphs into chapters & run block parser --------------
    starts = [b[0] for b in boundaries]
    for ci, ch in enumerate(chapters):
        lo = starts[[b for b in boundaries if b[1] == ch.session_date][0]] if False else None
    # simpler: walk boundaries again aligned with chapters
    ch_by_first_boundary = {}
    ci = 0
    slices = []
    for bi, (i, date_iso, *_rest) in enumerate(boundaries):
        if bi == 0:
            cur_ch = chapters[0]
        elif date_iso != boundaries[bi - 1][1]:
            ci += 1
            cur_ch = chapters[ci]
        slices.append(cur_ch)
    assert len(slices) == len(boundaries)

    for bi, (i, date_iso, txt, bm, is_real, genre) in enumerate(boundaries):
        ch = slices[bi]
        hi = boundaries[bi + 1][0] if bi + 1 < len(boundaries) else len(paras)
        lines = []
        for j in range(i + 1, hi):
            t = clean(para_text(paras[j]))
            if t:
                lines.append((t, j))
        if ch.genre == "chat-log":
            ch.loose_chars = sum(len(t) for t, _ in lines)
            continue
        parse_chapter_lines(ch, lines)

    # ---- outputs ---------------------------------------------------------
    BUILD.mkdir(exist_ok=True)
    out = {
        "source_docx": DOCX.name,
        "n_chapters": len(chapters),
        "toc_order_matches_body": order_ok,
        "blocks_total": sum(len(c.blocks) for c in chapters),
        "chapters": [c.to_dict() for c in chapters],
    }
    (BUILD / "chrono_sessions.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    anom = ["# chrono docx 解析異常報告", ""]
    anom.append(f"- 章節數（含 chat-log）：**{len(chapters)}**；總塊數：**{out['blocks_total']}**")
    anom.append(f"- TOC 順序與正文書籤順序一致：**{order_ok}**")
    anom.append(f"- 幽靈標題（無書籤、已併入同日章）：{len(ghosts)} 個 — "
                + "; ".join(f"{g[1]}@body#{g[0]}" for g in ghosts))
    anom.append(f"- 同日合併邊界：{len(merged_ghosts)} 處")
    zero = [c.title for c in chapters if c.genre == "qa" and len(c.blocks) == 0]
    anom.append(f"- 無塊的 qa 章：{zero if zero else '無'}")
    loose = [(c.title, c.loose_chars) for c in chapters if c.loose_chars > 400]
    anom.append(f"- loose_chars>400 的章：{loose if loose else '無'}")
    trans50 = sum(1 for c in chapters if c.transitions)
    anom.append(f"- 含過場句的章：{trans50}")
    multi = sum(1 for c in chapters for b in c.blocks if not b['asker_raw'])
    anom.append(f"- 繼承前昵称的塊（合併多問）：{multi}")
    (BUILD / "chrono_parse_anomalies.md").write_text("\n".join(anom), encoding="utf-8")

    print(f"chapters={len(chapters)} blocks={out['blocks_total']} toc_order_ok={order_ok}")
    print("first-of-2024-03-01:", json.dumps(
        next(c for c in chapters if c.session_date == '2024-03-01').blocks[0],
        ensure_ascii=False)[:300])
    gate = 5890 <= out["blocks_total"] <= 6510 and len(chapters) == 128 and order_ok
    print("GATE:", "PASS" if gate else "FAIL")
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
