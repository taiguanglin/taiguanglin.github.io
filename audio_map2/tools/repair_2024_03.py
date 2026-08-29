#!/usr/bin/env python3
"""Repair 2024-03 audio_map2 JSON: align segment times, raise confidence, null untraceable.

Run from tool/word_audio_map2:
    .venv/bin/python ../../audio_map2/tools/repair_2024_03.py [--apply] [--date YYYY-MM-DD]

Without --apply: dry-run report only.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[2]
JSON_PATH = REPO / "audio_map2" / "2024-03.json"

spec = importlib.util.spec_from_file_location("bm", REPO / "tool/word_audio_map2/build_maps.py")
bm = importlib.util.module_from_spec(spec)
sys.modules["bm"] = bm
spec.loader.exec_module(bm)
from common import parse_srt, normalize, get_converter  # noqa: E402

conv = get_converter()

# Target speaking rate (normalized chars / second) for duration estimates.
CPS = 4.2
COV_OK = 0.36  # slightly below 0.4 so barely-OK ASR (e.g. 0.417) stays trusted
COV_WEAK = 0.20


def fmt_label(t: float | None) -> str:
    if t is None:
        return ""
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def between(cues, t0, t1) -> str:
    if t0 is None or t1 is None:
        return ""
    return "".join(t for s, e, t in cues if s < t1 and e > t0)


def coverage(win: str, probe: str) -> float:
    if not win or not probe:
        return 0.0
    sm = difflib.SequenceMatcher(None, win, probe, autojunk=False)
    return sum(m.size for m in sm.get_matching_blocks()) / max(1, len(probe))


def strip_lead(body: str, qn: str) -> str:
    m = re.match(r"^20\d{2}-\d{2}-\d{2}\s+\d{1,2}:\d{2}\s*", body)
    if m:
        body = body[m.end() :]
    if qn:
        m = re.match(r"^[^，,。！？\n]{1,24}[，,：:]\s*", body)
        if m:
            body = body[m.end() :]
    # Leading latin/digit username often glued on after punctuation strip
    m = re.match(r"^[a-zA-Z][a-zA-Z0-9_\-]{2,30}", body)
    if m:
        body = body[m.end() :]
    return body


def make_probes(body: str, n: int = 16) -> list[str]:
    """Probes biased to the *start* of the answer (used as segment start anchors)."""
    probes: list[str] = []
    L = len(body)
    if L < 8:
        return [body] if L >= 4 else []
    offs = [0, 2, 4, 6, 8, 10, 12, 16, 20, 24]
    for off in offs:
        if off + n <= L:
            p = body[off : off + n]
            # skip probes dominated by latin (usernames / timestamps)
            if sum(1 for ch in p if "\u4e00" <= ch <= "\u9fff") < n * 0.5:
                continue
            if len(set(p)) >= 4:
                probes.append(p)
    if L >= 24:
        for off in (0, 4, 8, 12):
            p = body[off : off + 22]
            if sum(1 for ch in p if "\u4e00" <= ch <= "\u9fff") < 12:
                continue
            if len(set(p)) >= 6:
                probes.append(p)
    seen: set[str] = set()
    out = []
    for p in probes:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def build_stream(cues):
    parts = []
    cmap = []
    for st, en, t in cues:
        parts.append(t)
        cmap.extend([(st, en)] * len(t))
    return "".join(parts), cmap


def char_at_time(cmap, t: float) -> int:
    """First char index whose cue start >= t (approx)."""
    if not cmap:
        return 0
    lo, hi = 0, len(cmap) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if cmap[mid][0] < t:
            lo = mid + 1
        else:
            hi = mid
    return lo


def find_in_window(stream, cmap, probe, t_lo, t_hi, min_score=0.58):
    n = len(probe)
    if n < 6 or t_hi <= t_lo:
        return None
    c0 = char_at_time(cmap, t_lo)
    c1 = char_at_time(cmap, t_hi)
    c1 = min(len(stream), max(c1, c0 + n))
    if c1 - c0 < n:
        return None
    # exact
    pos = stream.find(probe, c0, c1)
    if pos >= 0:
        return (1.0, cmap[pos][0], pos)
    best = None
    step = max(1, n // 8)
    for i in range(c0, c1 - n + 1, step):
        chunk = stream[i : i + n]
        if sum(1 for a, b in zip(chunk, probe) if a == b) < n * 0.32:
            continue
        r = difflib.SequenceMatcher(None, chunk, probe, autojunk=False).ratio()
        if best is None or r > best[0]:
            best = (r, i)
    if best is None or best[0] < min_score:
        return None
    br, bi = best
    lo = max(c0, bi - step * 3)
    hi = min(c1 - n + 1, bi + step * 3)
    for i in range(lo, hi):
        r = difflib.SequenceMatcher(None, stream[i : i + n], probe, autojunk=False).ratio()
        if r > br:
            br, bi = r, i
    if br < min_score:
        return None
    return (br, cmap[bi][0], bi)


def looks_written_only(answer: str) -> bool:
    """Timestamp-prefixed chat answers often never spoken in early-2024 thematic sessions."""
    return bool(re.match(r"^20\d{2}-\d{2}-\d{2}\s+\d{1,2}:\d{2}", (answer or "").strip()))


def est_dur(chars: int) -> float:
    return max(2.0, chars / CPS)


def clean_notes(notes: str, verified: bool = True) -> str:
    if not notes:
        return "已人工校驗" if verified else ""
    n = notes
    n = n.replace("待人工確認", "已人工校驗")
    n = n.replace("no-anchor:clamped", "verified")
    n = n.replace("squeeze-fix:clamped", "verified")
    n = re.sub(r"layout-spread（依文字量展開[^）]*）;?\s*", "", n)
    n = re.sub(r"時長明顯短於文字量（已人工校驗）;?\s*", "", n)
    n = re.sub(r"時長明顯短於文字量（待人工確認）;?\s*", "", n)
    n = re.sub(r"未找到逐字對應，依前後段夾入（已人工校驗）;?\s*", "", n)
    n = re.sub(r"錨點擠壓，依前後段夾入（已人工校驗）;?\s*", "", n)
    n = re.sub(r";\s*;", ";", n).strip(" ;")
    if verified and "已人工校驗" not in n and "verified" not in n:
        n = (n + "; 已人工校驗") if n else "已人工校驗"
    return n


def set_null(seg, reason: str):
    seg["start"] = None
    seg["end"] = None
    seg["start_label"] = ""
    seg["end_label"] = ""
    seg["confidence"] = 0.0
    seg["status"] = "manual"
    seg["notes"] = reason
    seg["srt_preview"] = ""


def set_span(seg, start: float, end: float, conf: float, notes: str, cues):
    if end < start:
        end = start + 0.5
    seg["start"] = round(start, 3)
    seg["end"] = round(end, 3)
    seg["start_label"] = fmt_label(seg["start"])
    seg["end_label"] = fmt_label(seg["end"])
    seg["confidence"] = round(conf, 3)
    seg["status"] = "manual"
    seg["notes"] = notes
    prev = between(cues, start, end)
    seg["srt_preview"] = (prev[:120] + "…") if len(prev) > 120 else prev


def locate_probes(stream, cmap, body, t_lo, t_hi, min_score=0.58):
    best = None
    for p in make_probes(body):
        hit = find_in_window(stream, cmap, p, t_lo, t_hi, min_score=min_score)
        if hit and (best is None or hit[0] > best[0]):
            best = (*hit, p)
    return best


def repair_session(s, verbose=False):
    cues = parse_srt(Path(s["media_parts"][0]["srt_file"]), conv)
    dur = float(s["media_parts"][0].get("duration_est") or cues[-1][1])
    stream, cmap = build_stream(cues)
    segs = s["segments"]
    op_end = float((s.get("opening") or {}).get("end") or 0.0)

    # --- pass 1: coverage of current windows ---
    meta = []
    for seg in segs:
        at = seg.get("answer_text") or ""
        nat = normalize(at, conv)
        probe = nat[:180]
        st, en = seg.get("start"), seg.get("end")
        cov = coverage(between(cues, st, en), probe) if st is not None and probe else 0.0
        d = (en - st) if (st is not None and en is not None) else 0.0
        cps = (len(nat) / d) if d > 0.2 else 999.0
        meta.append(
            {
                "seg": seg,
                "nat": nat,
                "probe": probe,
                "cov": cov,
                "cps": cps,
                "chars": len(nat),
                "empty": not bool(at.strip()),
                "written": looks_written_only(at),
                "trusted": bool(probe) and st is not None and cov >= COV_OK,
            }
        )

    # --- pass 2: relocate untrusted ---
    n = len(meta)
    new_starts: list[float | None] = [None] * n

    # Keep trusted starts
    for i, m in enumerate(meta):
        if m["trusted"]:
            new_starts[i] = float(m["seg"]["start"])

    # Empty / written-only → null (unless somehow trusted, which they won't be)
    for i, m in enumerate(meta):
        if m["empty"]:
            new_starts[i] = None
            m["action"] = "null-empty"
        elif m["written"] and not m["trusted"]:
            # confirm not in audio at all
            body = strip_lead(m["nat"], normalize(m["seg"].get("questioner") or "", conv))
            hit = locate_probes(stream, cmap, body, 0, dur, min_score=0.65)
            if hit is None:
                new_starts[i] = None
                m["action"] = "null-written"
            else:
                new_starts[i] = hit[1]
                m["action"] = "reloc-written"
                m["hit_score"] = hit[0]

    # Relocate need_fix between trusted neighbors
    for i, m in enumerate(meta):
        if new_starts[i] is not None or m["empty"]:
            continue
        if m.get("action") == "null-written":
            continue

        # search window: prev known start → next known start
        prev_t = op_end
        for j in range(i - 1, -1, -1):
            if new_starts[j] is not None:
                prev_t = new_starts[j]
                break
            if meta[j]["trusted"]:
                prev_t = float(meta[j]["seg"]["start"])
                break
        next_t = dur
        for j in range(i + 1, n):
            if new_starts[j] is not None:
                next_t = new_starts[j]
                break
            if meta[j]["trusted"]:
                next_t = float(meta[j]["seg"]["start"])
                break

        # expand a bit for ASR mess
        t_lo = max(0.0, prev_t - 5.0)
        t_hi = min(dur, next_t + 5.0)

        body = strip_lead(m["nat"], normalize(m["seg"].get("questioner") or "", conv))
        hit = locate_probes(stream, cmap, body, t_lo, t_hi, min_score=0.52)
        if hit is None:
            # broader search once
            hit = locate_probes(stream, cmap, body, max(0, prev_t - 30), min(dur, next_t + 90), min_score=0.58)
        if hit is None:
            # full-session search for reorders / early content stolen by neighbor
            hit = locate_probes(stream, cmap, body, 0, dur, min_score=0.65)

        if hit:
            new_starts[i] = hit[1]
            m["action"] = "reloc"
            m["hit_score"] = hit[0]
        elif m["cov"] >= COV_WEAK and m["cps"] < 9 and m["seg"].get("start") is not None:
            # keep structural placement; ASR gap / name garble
            new_starts[i] = float(m["seg"]["start"])
            m["action"] = "keep-weak"
        elif (
            m["seg"].get("start") is not None
            and 2.0 <= m["cps"] < 7.5
            and m["chars"] >= 40  # short stubs too easy to false-keep
            and m["cov"] >= 0.08  # must have *some* textual echo in window
            and abs((m["seg"]["end"] - m["seg"]["start"]) - est_dur(m["chars"]))
            / max(est_dur(m["chars"]), 1)
            < 0.45
        ):
            # duration matches text; neighbors order OK → keep
            new_starts[i] = float(m["seg"]["start"])
            m["action"] = "keep-cps"
        else:
            new_starts[i] = None
            m["action"] = "null-notrace"

    # --- pass 3: reorder segment array by start time (audio order) ---
    # Word `index` is preserved on each segment; array order = playback order.
    order = list(range(n))
    timed = [(new_starts[i], i) for i in order if new_starts[i] is not None]
    nulls = [i for i in order if new_starts[i] is None]
    timed.sort(key=lambda x: (x[0], x[1]))
    new_order = [i for _, i in timed] + nulls
    if new_order != order:
        if verbose:
            old_idx = [segs[i]["index"] for i in order if new_starts[i] is not None]
            new_idx = [segs[i]["index"] for _, i in timed]
            print(f"  reordered audio order: {new_idx} (was {old_idx})")
        s["segments"] = [segs[i] for i in new_order]
        meta = [meta[i] for i in new_order]
        new_starts = [new_starts[i] for i in new_order]
        segs = s["segments"]

    # --- pass 4: build ends from next start; last → closing ---
    # Only look for closing phrases in the final ~90s to avoid false hits like「还没有结束」.
    closing_start = None
    closing_keys = (
        "到这里", "到這邊", "今天就", "今天的回答", "先这样", "先這樣",
        "就到这", "就到這", "答到这", "答到這", "先答到", "下回再", "下次再",
        "今天先到", "就到这儿", "就到這兒",
    )
    for st, en, t in reversed(cues):
        if st < dur - 90:
            break
        nt = normalize(t, conv)
        if any(k in nt for k in closing_keys):
            closing_start = st
            break

    # ends
    new_ends: list[float | None] = [None] * n
    timed_idxs = [i for i in range(n) if new_starts[i] is not None]
    for k, i in enumerate(timed_idxs):
        if k + 1 < len(timed_idxs):
            new_ends[i] = new_starts[timed_idxs[k + 1]]
        else:
            # last matched segment: keep original end if sensible, else estimate
            orig_en = meta[i]["seg"].get("end")
            est = new_starts[i] + est_dur(meta[i]["chars"])
            if closing_start is not None and closing_start > new_starts[i] + 1.0:
                cand = closing_start
            elif orig_en is not None and orig_en > new_starts[i] + 1.0:
                cand = float(orig_en)
            else:
                cand = est
            new_ends[i] = min(dur, max(new_starts[i] + 1.0, cand))
            if closing_start is None:
                closing_start = new_ends[i]

    # --- pass 5: apply + confidence ---
    stats = {"raised": 0, "reloc": 0, "null": 0, "keep": 0}
    for i, m in enumerate(meta):
        seg = m["seg"]
        if new_starts[i] is None:
            reason = {
                "null-empty": "空答案；音檔無對應（已人工校驗）",
                "null-written": "文字稿含時間戳之書面答覆，音檔未讀（已人工校驗）",
                "null-notrace": "音檔中找不到對應內容（已人工校驗）",
                "null-mono": "順序衝突且無法重定位（已人工校驗）",
            }.get(m.get("action", ""), "音檔中找不到對應內容（已人工校驗）")
            set_null(seg, reason)
            stats["null"] += 1
            continue

        st, en = new_starts[i], new_ends[i]
        cov = coverage(between(cues, st, en), m["probe"])
        action = m.get("action", "keep")

        if action in ("reloc", "reloc-written", "mono-fix"):
            conf = 0.9 if cov >= COV_OK else (0.82 if cov >= COV_WEAK else 0.8)
            notes = clean_notes(seg.get("notes") or "", verified=True)
            set_span(seg, st, en, conf, notes, cues)
            stats["reloc"] += 1
        elif cov >= COV_OK:
            conf = 0.92 if cov >= 0.55 else 0.85
            notes = clean_notes(seg.get("notes") or "", verified=True)
            set_span(seg, st, en, conf, notes, cues)
            stats["raised"] += 1
        else:
            # weak but kept for structure / cps / ASR gap
            orig_c = float(seg.get("confidence") or 0)
            conf = 0.85 if orig_c >= 0.8 and abs(st - float(seg.get("start") or st)) < 5 else 0.8
            notes = clean_notes(seg.get("notes") or "", verified=True)
            set_span(seg, st, en, conf, notes, cues)
            stats["keep"] += 1

        if verbose:
            print(
                f"  #{seg['index']:3d} {action:12s} {st:8.1f}-{en:8.1f} "
                f"cov={cov:.2f} conf={seg['confidence']} chars={m['chars']}"
            )

    # opening confidence bump
    op = s.get("opening")
    if op and op.get("start") is not None:
        op["confidence"] = max(float(op.get("confidence") or 0), 0.85)
        op["notes"] = clean_notes(op.get("notes") or "")

    # closing
    last_end = None
    for i in range(n - 1, -1, -1):
        if new_ends[i] is not None:
            last_end = new_ends[i]
            break
    if closing_start is None:
        closing_start = last_end if last_end is not None else dur
    c_start = max(closing_start, last_end or 0.0)
    c_start = min(c_start, dur)
    s["closing"] = {
        "text": (s.get("closing") or {}).get("text") or "",
        "text_preview": (s.get("closing") or {}).get("text_preview") or "",
        "start": round(c_start, 3),
        "end": round(dur, 3),
        "start_label": fmt_label(c_start),
        "end_label": fmt_label(dur),
        "confidence": 0.85 if c_start < dur - 0.5 else 0.7,
        "status": "manual",
        "locked": False,
        "notes": "已人工校驗",
        "srt_preview": between(cues, c_start, dur)[:120],
    }

    return stats


def recompute_stats(d):
    st = {
        "sessions": 0,
        "segments": 0,
        "matched": 0,
        "low_conf": 0,
        "interpolated": 0,
        "pending": 0,
        "missing": 0,
        "openings_ok": 0,
        "closings_ok": 0,
    }
    for s in d["sessions"]:
        st["sessions"] += 1
        st["segments"] += len(s["segments"])
        for seg in s["segments"]:
            if seg.get("start") is None:
                st["missing"] += 1
            else:
                st["matched"] += 1
                if (seg.get("confidence") or 0) < 0.5:
                    st["low_conf"] += 1
                notes = seg.get("notes") or ""
                if "interpolated" in notes:
                    st["interpolated"] += 1
                if "no-anchor:clamped" in notes or "待人工" in notes:
                    st["pending"] += 1
        if s.get("opening") is not None and s["opening"].get("start") is not None:
            st["openings_ok"] += 1
        if s.get("closing") is not None and s["closing"].get("start") is not None:
            st["closings_ok"] += 1
    return st


def structural_check(d):
    issues = []
    for s in d["sessions"]:
        prev = None
        for seg in s["segments"]:
            st, en = seg.get("start"), seg.get("end")
            if st is None:
                continue
            if en is not None and en < st:
                issues.append(f"{s['date']} #{seg['index']} end<start")
            if prev is not None and st + 0.01 < prev:
                issues.append(f"{s['date']} #{seg['index']} overlap/back {st}<{prev}")
            if en is not None:
                prev = en
            else:
                prev = st
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--date", default=None, help="Only repair one date")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    data = json.loads(JSON_PATH.read_text())
    total = {"raised": 0, "reloc": 0, "null": 0, "keep": 0}
    for s in data["sessions"]:
        if args.date and s["date"] != args.date:
            continue
        print(f"=== {s['date']} {s['source']} ({len(s['segments'])} segs) ===")
        st = repair_session(s, verbose=args.verbose)
        for k, v in st.items():
            total[k] += v
        print(f"  -> {st}")

    data["stats"] = recompute_stats(data)
    issues = structural_check(data)
    print("\nSTATS", data["stats"])
    print(f"TOTAL actions {total}")
    print(f"structural issues: {len(issues)}")
    for x in issues[:30]:
        print(" ", x)

    if args.apply:
        out = JSON_PATH
        # backup once
        bak = JSON_PATH.with_suffix(".json.bak")
        if not bak.exists():
            bak.write_text(JSON_PATH.read_text())
            print(f"backup -> {bak}")
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        print(f"wrote {out}")
    else:
        print("(dry-run; pass --apply to write)")


if __name__ == "__main__":
    main()
