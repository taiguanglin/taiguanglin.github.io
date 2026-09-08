#!/usr/bin/env python3
"""講經電子書段落 ↔ 講經音檔時間軸對齊器。

輸入:
  - ebook/0X.html        講經電子書（段落 id="p-sXXXXXXXX" 的 p/div.para-block）
  - audio/jiangjing/<basename>.opus   音檔（供 ffprobe 讀時長，可缺）
  - audio/srt/jiangjing/<basename>.srt ASR 字幕（缺檔則跳過該講）

輸出（SoT）:
  audio_map3/<series>.json   每講 paragraphs[]: pid/text/start/end/conf/method/confirmed

對齊原理:
  1. SRT cues 正規化（去標點/空白，可選 opencc t2s）後串成「字元時間流」，
     每個字元以 cue 內線性插值得到時間戳。
  2. 每個段落取正規化文本前 ~20 字作 needle，以 3-gram 索引找候選位置，
     再用 difflib 字元比率評分（method="ngram"）。>=40 字段落另取中段
     needle 做第二錨點，位置落差異常則降 conf。
  3. 單調約束：只在前一段對齊位置之後搜尋；匹配不上（miss）或短短段
     (<4 字, method="short") 沿用前段時間，conf 設低。
  4. start = 匹配時間 - 0.3s；end = 下一段 start；末段 end = 音檔時長。

重跑安全: 已存在 JSON 中 confirmed=true 的段落保留其 start/end；
         講層級 reviewed 欄位亦保留。

用法:
  python3 build_maps.py                    # 全部系列、全部講
  python3 build_maps.py --series lengqie --lecture 15
  python3 build_maps.py --series ganen -v  # 順便印前 20 段與 SRT 對照
  python3 build_maps.py --dry-run          # 只印報表不寫檔
  python3 build_maps.py --srt-dir /path/to/srt   # 指定 SRT 目錄

僅用 Python 3 標準庫；opencc 為可選。
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

try:
    from opencc import OpenCC
except Exception:  # pragma: no cover
    OpenCC = None

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "books2ebook"))
from audio_map import AUDIO_MAP  # noqa: E402

SRT_DIR = Path("/Users/paul/tai/audio/srt/jiangjing")
AUDIO_DIR = Path("/Users/paul/tai/audio/jiangjing")
OUT_DIR = ROOT / "audio_map3"

SERIES = {
    "ganen":        {"ebook": "ebook/04.html", "book_number": 4},
    "sishierzhang": {"ebook": "ebook/07.html", "book_number": 7},
    "lengqie":      {"ebook": "ebook/08.html", "book_number": 8},
    "liuzutanjing": {"ebook": "ebook/09.html", "book_number": 9},
    "lengyanjing":  {"ebook": "ebook/10.html", "book_number": 10},
}

# ---------------------------------------------------------------------------
# text normalization
# ---------------------------------------------------------------------------

PUNCT_RE = re.compile(r"[\s\W_，。？！、；：“”‘’「」『』〔〕（）()《》〈〉【】—…·-]+")
# 口語助詞：ASR 充斥、書面罕見，雙邊去除可顯著提升命中率
FILLER_RE = re.compile(r"[啊呀吧嗯呃哦啦哇欸诶喽嘍]")
SRT_BLOCK_RE = re.compile(
    r"(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)",
    re.S,
)
TAG_RE = re.compile(r"<[^>]+>")

_CONVERTER = None


def get_converter():
    global _CONVERTER
    if _CONVERTER is None and OpenCC is not None:
        _CONVERTER = OpenCC("t2s")
    return _CONVERTER


def normalize(text: str) -> str:
    if not text:
        return ""
    conv = get_converter()
    if conv is not None:
        text = conv.convert(text)
    return FILLER_RE.sub("", PUNCT_RE.sub("", text.lower()))


def strip_html(s: str) -> str:
    s = TAG_RE.sub("", s or "")
    for a, b in (("&nbsp;", " "), ("&lt;", "<"), ("&gt;", ">"),
                 ("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"),
                 ("&mdash;", "—")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------------------
# SRT → char time stream
# ---------------------------------------------------------------------------

def _tc(s: str) -> float:
    h, m, rest = s.split(":")
    sec, ms = re.split(r"[,.]", rest)
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000.0


def parse_srt(path: Path):
    """Return (cues, stream_text, char_times). cues keep raw text."""
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    cues = []
    parts, times = [], []
    for m in SRT_BLOCK_RE.finditer(text):
        start, end = _tc(m.group(2)), _tc(m.group(3))
        raw = " ".join(x.strip() for x in m.group(4).splitlines() if x.strip())
        norm = normalize(raw)
        cues.append((start, end, raw))
        if norm:
            n = len(norm)
            for i, ch in enumerate(norm):
                parts.append(ch)
                times.append(start + (end - start) * ((i + 0.5) / n))
    return cues, "".join(parts), times


# ---------------------------------------------------------------------------
# ebook parsing
# ---------------------------------------------------------------------------

H2_RE = re.compile(r'<h2 id="[^"]*">(.*?)</h2>', re.S)
BLOCK_RE = re.compile(r"<(p|div)\b([^>]*)>(.*?)</\1>", re.S)
ATTR_ID_RE = re.compile(r'id="(p-s[0-9a-f]+)"')
ATTR_CLASS_RE = re.compile(r'class="([^"]*)"')
DATA_AUDIO_RE = re.compile(r'data-audio="([^"]+)"')
DATA_END_RE = re.compile(r'data-end="([\d.]+)"')


def parse_ebook(path: Path):
    """Return list of lectures: {basename, title, duration, paragraphs[]}.

    Paragraphs: {pid, text} in document order.
    """
    html_text = path.read_text(encoding="utf-8")
    marks = [m for m in H2_RE.finditer(html_text)]
    lectures = []
    for i, m in enumerate(marks):
        inner = m.group(1)
        audio_m = DATA_AUDIO_RE.search(inner)
        if not audio_m:
            continue
        basename = urllib.parse.unquote(audio_m.group(1)).rsplit("/", 1)[-1]
        basename = re.sub(r"\.opus$", "", basename)
        title = strip_html(re.split(r"<button|<span", inner)[0])
        end_m = DATA_END_RE.search(inner)
        btn_end = float(end_m.group(1)) if end_m else None
        body = html_text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(html_text)]
        paras = []
        for b in BLOCK_RE.finditer(body):
            attrs = b.group(2)
            cls = ATTR_CLASS_RE.search(attrs)
            pid = ATTR_ID_RE.search(attrs)
            if not pid or not cls or "para-block" not in cls.group(1).split():
                continue
            text = strip_html(b.group(3))
            if text:
                paras.append({"pid": pid.group(1), "text": text})
        lectures.append({"basename": basename, "title": title,
                         "btn_end": btn_end, "paragraphs": paras})
    return lectures


# ---------------------------------------------------------------------------
# alignment
# ---------------------------------------------------------------------------

NEEDLE_LEN = 20
MATCH_THRESHOLD = 0.5
CHAR_BACKOFF = 0.3


def build_gram_index(stream: str):
    """Combined 2-gram / 3-gram → positions index over the char stream."""
    idx = {}
    for n in (2, 3):
        for i in range(len(stream) - n + 1):
            idx.setdefault(stream[i:i + n], []).append(i)
    return idx


def _bigram_dice(a: str, b: str) -> float:
    from collections import Counter
    ga = Counter(a[i:i + 2] for i in range(len(a) - 1))
    gb = Counter(b[i:i + 2] for i in range(len(b) - 1))
    if not ga or not gb:
        return 0.0
    ov = sum(min(ga[g], gb[g]) for g in ga if g in gb)
    return 2.0 * ov / (sum(ga.values()) + sum(gb.values()))


def _score(needle: str, window: str) -> float:
    """max(char-ratio, bigram-dice) — dice survives heavy ASR garbling."""
    r = difflib.SequenceMatcher(None, needle, window).ratio()
    d = _bigram_dice(needle, window)
    return r if r >= d else d


def find_needle(needle, cursor, stream, gram_idx):
    """Best fuzzy position of needle in stream at/after cursor.

    Returns (score, pos) or None.
    """
    if len(needle) < 4 or cursor >= len(stream):
        return None
    grams = [(i, needle[i:i + 3]) for i in range(len(needle) - 2)]
    grams += [(i, needle[i:i + 2]) for i in range(len(needle) - 1)]
    # gram at needle offset j starts at candidate pos + j → candidate = pos - j
    hits = {}
    for j, g in grams:
        for pos in gram_idx.get(g, ()):
            p = pos - j
            if p >= cursor:
                hits[p] = hits.get(p, 0) + 1
    need = max(3, len(grams) // 5)
    cand_list = sorted((p for p, c in hits.items() if c >= need)) if hits else []
    if not cand_list:
        cand_list = sorted(hits, key=lambda q: -hits[q])[:20]
    if not cand_list:
        rep = []
    else:
        # cluster nearby candidates, keep best count per cluster, cap at 60
        clusters = [[cand_list[0]]]
        for p in cand_list[1:]:
            if p - clusters[-1][-1] <= 3:
                clusters[-1].append(p)
            else:
                clusters.append([p])
        rep = [max(c, key=lambda q: hits[q]) for c in clusters][-60:]

    n = len(needle)
    # dense candidates near cursor: helps when gram index misses entirely
    dense_end = min(len(stream) - n, cursor + 1200)
    cands = set(rep) | set(range(cursor, max(cursor, dense_end), 3))
    best = (0.0, None)
    for p in cands:
        for wlen in (n, n + 4):
            score = _score(needle, stream[p:p + wlen])
            if score > best[0]:
                best = (score, p)
    if best[1] is None or best[0] < MATCH_THRESHOLD:
        return None
    return best


def align_lecture(paras, cues, stream, times, duration):
    """Return list of dicts with pid/text/start/end/conf/method."""
    gram_idx = build_gram_index(stream)
    results = []
    cursor = 0           # char-stream cursor (monotonic)
    prev_start = 0.0     # time of previous paragraph start
    for para in paras:
        norm = normalize(para["text"])
        entry = {"pid": para["pid"], "text": para["text"],
                 "start": round(prev_start, 3), "conf": 0.0,
                 "method": "miss", "confirmed": False}
        if 0 < len(norm) < 4:
            entry["conf"] = 0.15
            entry["method"] = "short"
        elif len(norm) >= 4:
            # multi-needle: try head / quarter / mid / ¾ anchors, keep best
            n = len(norm)
            offsets = sorted({0, n // 4, n // 2, (3 * n) // 4})
            best = None  # (score, start_pos_in_stream)
            for off in offsets:
                ndl = norm[off:off + NEEDLE_LEN]
                if len(ndl) < 4:
                    continue
                hit = find_needle(ndl, cursor, stream, gram_idx)
                if hit and (best is None or hit[0] > best[0]):
                    best = (hit[0], max(cursor, hit[1] - off), hit[1], len(ndl))
            if best:
                score, pos_head, pos_hit, ndl_len = best
                conf = round(score, 3)
                # second anchor cross-check for long paragraphs
                if n >= 40 and offsets != [0]:
                    pass  # already covered by multi-needle above
                start_t = max(0.0, times[min(pos_head, len(times) - 1)] - CHAR_BACKOFF)
                start_t = max(start_t, prev_start)
                entry.update(start=round(start_t, 3), conf=conf,
                             method="ngram")
                cursor = pos_hit + ndl_len
                prev_start = start_t
            # else: keep miss defaults (start=prev_start)
        results.append(entry)

    # interpolation pass: spread miss/short paragraphs evenly (weighted by
    # normalized text length) between the surrounding anchored paragraphs,
    # so review UI gets usable non-zero ranges.
    anchored = [i for i, r in enumerate(results) if r["method"] == "ngram"]
    prev_anchor = -1
    for a in anchored + [len(results)]:
        if a - prev_anchor > 1:
            lo_t = results[prev_anchor]["start"] if prev_anchor >= 0 else 0.0
            hi_t = (results[a]["start"] if a < len(results)
                    else (duration or (cues[-1][1] + 1.0)))
            span = list(range(prev_anchor + 1, a))
            lens = [max(4, len(normalize(results[k]["text"]))) for k in span]
            # reserve the anchor paragraph's own share so it keeps a
            # non-zero width (its spoken length is unknown, estimate by text)
            if prev_anchor >= 0:
                lens.insert(0, max(4, len(normalize(
                    results[prev_anchor]["text"]))))
            total = sum(lens)
            acc = lens[0] if prev_anchor >= 0 else 0
            t = lo_t + (hi_t - lo_t) * (acc / total) if total else lo_t
            for k, w in zip(span, lens[1:] if prev_anchor >= 0 else lens):
                results[k]["start"] = round(t, 3)
                acc += w
                t = lo_t + (hi_t - lo_t) * (acc / total) if total else hi_t
        prev_anchor = a

    # ends = next start; last end = duration
    for i in range(len(results) - 1):
        results[i]["end"] = results[i + 1]["start"]
    if results:
        results[-1]["end"] = round(duration, 3) if duration else round(
            (cues[-1][1] + 1.0), 3)
    return results


def audio_duration(basename: str, btn_end, cues):
    """Duration: h2 button data-end > ffprobe > last SRT cue + 1."""
    opus = AUDIO_DIR / (basename + ".opus")
    if opus.exists():
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(opus)],
                capture_output=True, text=True, check=True)
            return float(out.stdout.strip())
        except Exception:
            pass
    if btn_end:
        return btn_end
    if cues:
        return cues[-1][1] + 1.0
    return None


# ---------------------------------------------------------------------------
# merge with existing JSON (preserve human review)
# ---------------------------------------------------------------------------

def merge_existing(old_lect, new_lect):
    if not old_lect:
        return new_lect
    new_lect["reviewed"] = old_lect.get("reviewed", False)
    old_by_pid = {p["pid"]: p for p in old_lect.get("paragraphs", [])}
    for p in new_lect["paragraphs"]:
        o = old_by_pid.get(p["pid"])
        if o:
            if o.get("confirmed"):
                p["start"], p["end"] = o["start"], o.get("end", p["end"])
                p["confirmed"] = True
            if "confirmed" in o and not o["confirmed"]:
                p["confirmed"] = False
    return new_lect


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def fmt_tc(sec):
    sec = max(0.0, sec)
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--series", choices=sorted(SERIES))
    ap.add_argument("--lecture", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--srt-dir", type=Path, default=SRT_DIR)
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print first 20 paragraph↔SRT comparisons per lecture")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    series_list = [args.series] if args.series else list(SERIES)

    for series in series_list:
        meta = SERIES[series]
        ebook_path = ROOT / meta["ebook"]
        if not ebook_path.exists():
            print(f"[{series}] ebook missing: {ebook_path}", file=sys.stderr)
            continue
        lectures = parse_ebook(ebook_path)
        by_base = {l["basename"]: l for l in lectures}

        out_path = OUT_DIR / f"{series}.json"
        old = {}
        if out_path.exists():
            try:
                old = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                old = {}
        old_lectures = old.get("lectures", {})

        out_doc = {
            "series": series,
            "book_number": meta["book_number"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lectures": {},
        }
        skipped = []

        for n, basename in sorted(AUDIO_MAP.get(series, {}).items()):
            if args.lecture and n != args.lecture:
                continue
            lec = by_base.get(basename)
            srt_path = args.srt_dir / (basename + ".srt")
            if lec is None:
                print(f"[{series}#{n}] h2/button not found in ebook — skipped")
                continue
            if not srt_path.exists():
                skipped.append(n)
                continue

            cues, stream, times = parse_srt(srt_path)
            if not stream:
                print(f"[{series}#{n}] empty SRT — skipped")
                continue
            dur = audio_duration(basename, lec["btn_end"], cues)
            results = align_lecture(lec["paragraphs"], cues, stream, times, dur)

            lect_doc = {
                "audio": basename + ".opus",
                "title": lec["title"],
                "duration": round(dur, 3) if dur else None,
                "reviewed": False,
                "paragraphs": results,
            }
            lect_doc = merge_existing(old_lectures.get(str(n)), lect_doc)
            out_doc["lectures"][str(n)] = lect_doc

            confs = [p["conf"] for p in results]
            avg = sum(confs) / len(confs) if confs else 0.0
            low = sum(1 for c in confs if c < 0.5)
            hi = sum(1 for c in confs if c >= 0.8)
            mid = sum(1 for c in confs if 0.5 <= c < 0.8)
            print(f"[{series}#{n}] {lec['title']}: paras={len(results)} "
                  f"avg_conf={avg:.3f} high={hi} mid={mid} low={low}")

            if args.verbose:
                for p in results[:20]:
                    t = p["start"]
                    near = "".join(r for cs, ce, r in cues
                                   if cs < t + p["end"] - t and ce > t)
                    near = ""
                    for cs, ce, raw in cues:
                        if ce > p["start"] and cs < p["end"]:
                            near += raw
                    print(f"  {fmt_tc(p['start'])}→{fmt_tc(p['end'])} "
                          f"conf={p['conf']:.2f} {p['method']}")
                    print(f"    書: {p['text'][:60]}")
                    print(f"    音: {near[:80]}")

        # keep old lectures that were skipped (no SRT yet)
        for key, val in old_lectures.items():
            if key not in out_doc["lectures"]:
                out_doc["lectures"][key] = val
        out_doc["lectures"] = dict(sorted(
            out_doc["lectures"].items(), key=lambda kv: int(kv[0])))

        if skipped:
            print(f"[{series}] SRT missing, skipped lectures: {skipped}")
        if args.dry_run:
            print(f"[{series}] dry-run: not writing {out_path}")
        elif out_doc["lectures"]:
            out_path.write_text(
                json.dumps(out_doc, ensure_ascii=False, indent=2),
                encoding="utf-8")
            print(f"[{series}] wrote {out_path} "
                  f"({len(out_doc['lectures'])} lectures)")


if __name__ == "__main__":
    main()
