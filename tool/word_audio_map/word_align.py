#!/usr/bin/env python3
"""Align Word-ebook questions to audio time ranges; write word map JSON.

Matching model (calibrated on real 2024–2025 transcripts)
---------------------------------------------------------
In these recordings the teacher usually speaks the asker's name and then
answers in his own words — the written question is often NOT read aloud, and
the written answer is a lightly edited version of the spoken answer. ASR adds
homophone noise (业→夜, 自性→自信). Therefore matching runs on **toneless
pinyin streams**:

1. locate the asker's name (pinyin) inside a session stream
2. verify with the longest common block (LCB) between the candidate's
   answer/question pinyin and the window right after that name occurrence;
   when the name is never spoken, fall back to an answer-text LCB over the
   whole stream (guarded by a cheap substring prefilter)
3. accept when the score clears :data:`T_ACCEPT`; inside one session claims
   are accepted greedily by score with exclusive stream regions, so the
   teacher answering out of submission order still works

Questions are only tried on the first ``MAX_SESSIONS_PER_QUESTION`` sessions
from their submission date (45-day cap), so recording gaps still work while
retry cost stays bounded. A global sweep with a higher bar picks up leftovers.
Sessions are independent → aligned in a process pool.

No interpolation: segments without a confident match simply get no button.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time as _time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

from wcommon import (  # noqa: E402
    BUILD_DIR,
    DEFAULT_SRT_ROOT,
    WORD_MAP_DIR,
    SessionStream,
    empty_range_fields,
    get_converter,
    inventory_sessions,
    load_questions,
    parse_srt,
    parse_srt_raw,
    py_norm,
    range_fields,
    srt_preview,
)

WINDOW_DAYS_DEFAULT = 45
MAX_SESSIONS_PER_QUESTION = 14

# Acceptance thresholds (longest common block, in pinyin characters)
T_ACCEPT = 16          # name-anchored verification must reach this
T_STRONG = 48          # early-exit / no-need-to-look-further
T_NONAME = 20          # no usable name → answer-text-only search needs more
T_REVIEW_FLOOR = 15    # answer-LCB above this (but below accept) → review tier
SWEEP_MARGIN = 6       # extra LCB required by the global sweep
VERIFY_WINDOW = 1400   # chars of stream inspected after a name hit
OCCUPANCY = 240        # stream chars a claim reserves (conflict exclusion)
ANSWER_SKIP_HEAD = 16  # pinyin chars of formulaic answer opening to skip

# Placeholder / answerer names that are never spoken as an asker's name.
GENERIC_NAMES = {
    "无名", "無名", "匿名", "问题丢失", "問題丟失",
    "其他地方收集的问题", "其他地方收集的問題",
    "taiguanglin", "tai師父", "师父", "師父", "老师", "老師",
}

_EMBEDDED_DATE_RE = re.compile(r"\s*\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\s*")
_EMBEDDED_TIME_RE = re.compile(r"\s*\d{1,2}:\d{2}(?::\d{2})?\s*")


def clean_questioner(name: str) -> str:
    name = _EMBEDDED_DATE_RE.sub(" ", name or "")
    name = _EMBEDDED_TIME_RE.sub(" ", name)
    return name.strip()


def usable_name(raw: str) -> str:
    name = clean_questioner(raw)
    if not name or len(py_norm(name)) < 3:
        return ""
    if name.lower() in GENERIC_NAMES or name in GENERIC_NAMES:
        return ""
    return name


def lcb(a: str, b: str) -> int:
    if not a or not b:
        return 0
    from difflib import SequenceMatcher

    m = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(
        0, len(a), 0, len(b)
    )
    return m.size


def _verify(stream: str, pos: int, ap: str, qp: str) -> float:
    win = stream[pos : pos + VERIFY_WINDOW]
    score = 0.0
    if ap:
        score = lcb(win, ap)
    if qp:
        score = max(score, lcb(win, qp) * 0.9)
    return score


def annotate_questions(questions: List[dict], converter) -> None:
    for q in questions:
        name = usable_name(q.get("questioner") or "")
        q["_np"] = py_norm(name, converter) if name else ""
        q["_ap"] = py_norm((q.get("a_text") or "")[:220], converter)[:150]
        q["_qp"] = py_norm((q.get("q_text") or "")[:220], converter)[:150]


def _cheap_prefilter(stream: str, needle: str) -> bool:
    """Fast substring probe before an expensive full-stream LCB."""
    n = len(needle)
    if n < 12:
        return True
    step = max((n - 8) // 6, 6)
    for i in range(0, n - 8, step):
        if needle[i : i + 8] in stream:
            return True
    return needle[-8:] in stream


def locate_in_stream(
    q: dict, ss: SessionStream,
    *, t_accept: Optional[float] = None, t_noname: Optional[float] = None,
) -> Optional[Tuple[float, int, str]]:
    """Best claim for ``q`` anywhere inside ``ss``.

    ``t_accept`` / ``t_noname`` override module defaults (the date-constrained
    convergence passes can safely go lower).

    Returns ``(score, char_pos, method)`` or ``None``.
    """
    ta = T_ACCEPT if t_accept is None else t_accept
    tn = T_NONAME if t_noname is None else t_noname
    stream = ss.py
    np_, ap, qp = q["_np"], q["_ap"], q["_qp"]
    best: Optional[Tuple[float, int]] = None

    if len(np_) >= 3:
        pos = 0
        occ: List[int] = []
        while len(occ) < 40:
            i = stream.find(np_, pos)
            if i < 0:
                break
            occ.append(i)
            pos = i + max(len(np_), 1)
        for o in occ[:12]:
            sc = _verify(stream, o, ap, qp)
            if best is None or sc > best[0]:
                best = (sc, o)
            if best[0] >= T_STRONG:
                break
        if best and best[0] >= ta:
            return best[0], best[1], "name+verify"

    # Name never spoken (or unusable): search the answer text directly.
    # Use a mid-portion needle (formulaic openings like 下一个问题 collide
    # across answers) and take the position of the longest common block
    # itself — `stream.find(needle_head)` lands on unrelated boilerplate.
    needle = ap if len(ap) >= 20 else qp
    if len(needle) > ANSWER_SKIP_HEAD + 24:
        probe = needle[ANSWER_SKIP_HEAD:]
    else:
        probe = needle
    if len(probe) >= 20 and _cheap_prefilter(stream, probe):
        from difflib import SequenceMatcher

        m = SequenceMatcher(None, stream, probe, autojunk=False).find_longest_match(
            0, len(stream), 0, len(probe)
        )
        if m.size >= tn:
            return float(m.size), m.a, "answer-only"
    return None


def _annotate_session_ranges(questions: List[dict], sessions: List[dict]) -> None:
    """Attach ``_lo``/``_hi`` session-index bounds to each dated question."""
    import bisect
    import datetime as _dt

    dates = [s["date"] for s in sessions]
    for q in questions:
        q["_lo"] = -1
        q["_hi"] = -1
        qd = q.get("date")
        if not qd:
            continue
        i = bisect.bisect_left(dates, qd)
        hi = min(i + MAX_SESSIONS_PER_QUESTION, len(sessions))
        cap_date = (
            _dt.date.fromisoformat(qd) + _dt.timedelta(days=WINDOW_DAYS_DEFAULT)
        ).isoformat()
        while hi > i and dates[hi - 1] > cap_date:
            hi -= 1
        q["_lo"] = i
        q["_hi"] = hi


# ---------------------------------------------------------------------------
# Multiprocess session alignment
# ---------------------------------------------------------------------------

_WORKER: dict = {}


def _init_worker(questions_path: str, busy_json: Optional[str] = None) -> None:
    conv = get_converter()
    qs = load_questions(Path(questions_path))
    annotate_questions(qs, conv)
    _WORKER["by_id"] = {q["question_id"]: q for q in qs}
    _WORKER["by_stable_key"] = {
        f"{q['chapter_index']:02d}#q{q['number']}": q for q in qs
    }
    _WORKER["converter"] = conv
    # {session_id: [[start, end], …]} of already-mapped ranges — near-pass
    # retries must never double-book an existing button's region
    _WORKER["busy"] = json.loads(busy_json) if busy_json else {}


def _time_overlaps(ranges: List[List[float]], start_t: float, dur: float = 75.0) -> bool:
    """True when ``start_t`` lands on an existing button's *start zone*.

    Only each existing segment's opening (~``dur`` seconds) is protected:
    segment ``end`` values extend to the next accepted question, so treating
    whole spans as occupied would block legitimate retries for questions
    whose answers sit between two mapped neighbours.
    """
    for es, _ee in ranges:
        if es - 2.0 <= start_t < es + dur:
            return True
    return False


def _near_session_task(args):
    """Worker: retry missing questions on given sessions.

    ``args = (label, si_list, items, thr)`` with
    ``thr = (t_accept, t_noname, t_review_floor)``. Scores ≥ accept produce
    ``auto`` segments; borderline answer-text hits (review_floor…accept)
    produce ``review`` segments (stored, buttonless until confirmed). Auto
    always wins over review; existing buttons' regions are never re-booked.
    """
    from difflib import SequenceMatcher

    date, si_list, items, thr = args
    t_accept, t_noname, t_review = thr
    by_id = _WORKER["by_id"]
    by_key = _WORKER["by_stable_key"]
    conv = _WORKER["converter"]
    busy_all: Dict[str, List[List[float]]] = _WORKER.get("busy") or {}

    streams: Dict[str, SessionStream] = {}
    patches = []
    batch: Dict[str, List[List[float]]] = {}

    def _emit(qid, stable_key, session, st, char_pos, score, method, status):
        start_t = st.cue_start_time(char_pos)
        key = session["srt_file"]
        existing = list(busy_all.get(session["session_id"]) or ()) + list(
            batch.get(key) or ()
        )
        if _time_overlaps(existing, start_t):
            return False
        later = [es for es, ee in existing if es >= start_t]
        end_t = min([start_t + 300.0, st.audio_end] + later)
        if end_t <= start_t:
            end_t = start_t + 30.0
        fields = range_fields(
            start_t, end_t, round(min(1.0, score / 60.0), 3), status,
            srt_preview(st.raw_cues, start_t, end_t),
        )
        fields["notes"] = f"method={method}"
        patches.append(
            {
                "question_id": qid,
                "stable_key": stable_key,
                **fields,
                "session_id": session["session_id"],
                "session_date": session["date"],
                "source": session["source"],
                "audio_file": session["audio_file"],
                "srt_file": session["srt_file"],
            }
        )
        batch.setdefault(key, []).append([start_t, end_t])
        return True

    for item in items:
        qid, stable_key = item
        q = by_id.get(qid) or by_key.get(stable_key)
        if q is None:
            continue
        np_, ap, qp = q["_np"], q["_ap"], q["_qp"]
        if len(ap) < 20 and len(qp) < 20 and len(np_) < 3:
            continue
        needle = ap if len(ap) >= 20 else qp
        probe = (
            needle[ANSWER_SKIP_HEAD:]
            if len(needle) > ANSWER_SKIP_HEAD + 24
            else needle
        )

        review_hit = None  # (score, char_pos, st, session)
        matched = False
        for si in si_list:
            session = _WORKER.setdefault("sessions", inventory_sessions())[si]
            key = session["srt_file"]
            st = streams.get(key)
            if st is None:
                path = Path(key)
                cues = parse_srt(path, conv)
                if not cues:
                    continue
                st = SessionStream(session, cues, conv, parse_srt_raw(path))
                streams[key] = st

            hit = locate_in_stream(q, st, t_accept=t_accept, t_noname=t_noname)
            if hit is not None:
                score, char_pos, method = hit
                if _emit(qid, stable_key, session, st, char_pos, score,
                         f"near-fwd({method})", "auto"):
                    matched = True
                    break
                continue

            # borderline answer-text evidence → review candidate
            if review_hit is None and len(probe) >= 20 \
                    and _cheap_prefilter(st.py, probe):
                m = SequenceMatcher(
                    None, st.py, probe, autojunk=False
                ).find_longest_match(0, len(st.py), 0, len(probe))
                if m.size >= t_review:
                    review_hit = (float(m.size), m.a, st, session)

        if not matched and review_hit is not None:
            score, char_pos, st, session = review_hit
            _emit(qid, stable_key, session, st, char_pos, score,
                  "near-review", "review")
    return date, patches



def near_forward_pass(
    targets: List[Tuple[str, str, str]],  # (qid, stable_key, date)
    sessions: List[dict],
    converter=None,
    questions_path: Optional[Path] = None,
    workers: int = 6,
    near_days: int = 3,
    busy: Optional[Dict[str, List]] = None,
    mode: str = "calendar",
    max_answer_dates: int = 2,
    thr: Tuple[float, float, float] = (T_ACCEPT, T_NONAME, T_REVIEW_FLOOR + 1),
) -> List[dict]:
    """Retry missing questions on nearby sessions.

    mode ``"calendar"``: sessions within ``near_days`` calendar days after the
    question date.

    mode ``"answer-days"``: the teacher answers on a few fixed days per month,
    so candidates are the first ``max_answer_dates`` distinct *answer days*
    at/after the question date — per user domain knowledge the answer is on
    the FIRST such day (wechat or tieba file alike).

    ``thr`` = (t_accept, t_noname, t_review_floor) threshold overrides.

    Returns segment patches for recovered questions.
    """
    if not targets:
        return []
    import bisect
    import datetime as _dt
    from concurrent.futures import ProcessPoolExecutor

    dates = [s["date"] for s in sessions]
    by_date_idx: Dict[str, List[int]] = {}
    for i, s in enumerate(sessions):
        by_date_idx.setdefault(s["date"], []).append(i)
    ordered_days = sorted(by_date_idx)

    groups: Dict[str, List] = {}
    for qid, stable_key, qdate in targets:
        if not qdate:
            continue
        if mode == "answer-days":
            di = bisect.bisect_left(ordered_days, qdate)
            cand_days = ordered_days[di : di + max_answer_dates]
            idxs = [i for d in cand_days for i in by_date_idx[d]]
            # process day-by-day so the FIRST answer date wins
            for gi, d in enumerate(cand_days):
                day_idxs = sorted(by_date_idx[d])
                key = f"g{gi}:" + ",".join(dates[i] for i in day_idxs)
                entry = groups.setdefault(key, ([], [], []))
                entry[0].append((qid, stable_key))
                entry[1].append(gi)
                entry[2].extend(day_idxs)
        else:
            d0 = _dt.date.fromisoformat(qdate)
            idxs: List[int] = []
            for k in range(0, near_days + 1):
                day = (d0 + _dt.timedelta(days=k)).isoformat()
                idxs.extend(by_date_idx.get(day, []))
            if not idxs:
                continue
            key = ",".join(dates[i] for i in sorted(idxs))
            groups.setdefault(key, (sorted(idxs), [], []))[1].append(
                (qid, stable_key)
            )
            groups[key][2].extend(sorted(idxs))

    keys = list(groups.keys())
    tasks = [
        (keys_i.split(":")[-1].split(",")[0], sorted(set(groups[keys_i][2])),
         groups[keys_i][0], thr)
        for keys_i in keys
    ]
    patches: List[dict] = []
    busy_json = json.dumps(busy or {}, ensure_ascii=False)
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_worker,
        initargs=(str(questions_path), busy_json),
    ) as ex:
        for key, (_, ps) in zip(keys, ex.map(_near_session_task, tasks, chunksize=1)):
            gi = int(key[1:].split(":", 1)[0]) if key.startswith("g") and ":" in key else 0
            for p in ps:
                p["_gi"] = gi
            patches.extend(ps)

    if mode == "answer-days":
        # one patch per question: auto beats review, then earliest answer-day
        def _rank(p):
            return (0 if p.get("status") == "auto" else 1,
                    p["_gi"], -float(p.get("confidence") or 0))

        best_by_q: Dict[str, Tuple[tuple, dict]] = {}
        for p in patches:
            prev = best_by_q.get(p["question_id"])
            if prev is None or _rank(p) < prev[0]:
                best_by_q[p["question_id"]] = (_rank(p), p)
        out = []
        for _, p in best_by_q.values():
            p.pop("_gi", None)
            out.append(p)
        return out
    for p in patches:
        p.pop("_gi", None)
    return patches


def _align_session_task(args) -> Tuple[int, List[dict]]:
    """Align one session against its candidate qids. Returns (si, segments)."""
    si, session, qids = args
    conv = _WORKER["converter"]
    by_id = _WORKER["by_id"]

    path = Path(session["srt_file"])
    cues = parse_srt(path, conv)
    if not cues:
        return si, []
    raw = parse_srt_raw(path)
    ss = SessionStream(session, cues, conv, raw)

    claims: List[Tuple[float, int, dict, str]] = []
    for qid in qids:
        q = by_id.get(qid)
        if q is None:
            continue
        hit = locate_in_stream(q, ss)
        if hit is None:
            continue
        score, char_pos, method = hit
        if score >= T_ACCEPT:
            claims.append((float(score), char_pos, q, method))
    if not claims:
        return si, []

    # Greedy by score; reject overlapping regions (two questions claiming the
    # same spoken answer region — usually boilerplate phrasing).
    claims.sort(key=lambda t: (-t[0], t[1]))
    occupied: List[Tuple[int, int]] = []
    accepted: List[Tuple[int, float, dict, str]] = []
    for score, char_pos, q, method in claims:
        lo, hi = char_pos, char_pos + OCCUPANCY
        if any(lo < e and hi > s for s, e in occupied):
            continue
        occupied.append((lo, hi))
        accepted.append((char_pos, score, q, method))
    accepted.sort(key=lambda t: t[0])

    audio_end = ss.audio_end
    segs: List[dict] = []
    for i, (char_pos, score, q, method) in enumerate(accepted):
        start_t = ss.cue_start_time(char_pos)
        next_pos = accepted[i + 1][0] if i + 1 < len(accepted) else None
        end_t = (
            ss.cue_start_time(max(next_pos - 1, 0)) if next_pos is not None else audio_end
        )
        if end_t <= start_t:
            end_t = min(start_t + 300.0, audio_end)
        conf = min(1.0, score / 60.0)
        fields = range_fields(
            start_t, end_t, round(conf, 3), "auto", srt_preview(raw, start_t, end_t)
        )
        fields.pop("locked", None)
        segs.append(
            {
                "question_id": q["question_id"],
                **fields,
                "notes": f"method={method}",
                "session_id": session["session_id"],
                "session_date": session["date"],
                "source": session["source"],
                "audio_file": session["audio_file"],
                "srt_file": session["srt_file"],
                "_score": score,
                "_method": method,
            }
        )
    return si, segs


def align_pass(
    questions: List[dict],
    sessions: List[dict],
    questions_path: Path,
    workers: int = 6,
    session_limit: int = 0,
    log_every: int = 25,
) -> Tuple[Dict[str, dict], Dict[str, dict], List[Tuple[float, str]]]:
    """Parallel main pass. Returns ({qid: result}, {qid: miss}, samples)."""
    _annotate_session_ranges(questions, sessions)

    groups: Dict[int, List[str]] = {}
    for q in questions:
        if not q["date"]:
            continue
        lo = max(q["_lo"], 0)
        for si in range(lo, min(q["_hi"], len(sessions))):
            groups.setdefault(si, []).append(q["question_id"])

    tasks = [
        (si, sessions[si], qids)
        for si, qids in sorted(groups.items())
        if not session_limit or si < session_limit
    ]

    results: Dict[str, dict] = {}
    score_samples: List[Tuple[float, str]] = []
    t0 = _time.time()

    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(
        max_workers=workers, initializer=_init_worker, initargs=(str(questions_path),)
    ) as ex:
        for done, (si, segs) in enumerate(ex.map(_align_session_task, tasks, chunksize=2)):
            for seg in segs:
                qid = seg["question_id"]
                if qid in results:
                    continue  # earliest session wins
                score = seg.pop("_score")
                method = seg.pop("_method")
                results[qid] = seg
                score_samples.append((score, method))
            if log_every and (done + 1) % log_every == 0:
                print(
                    f"  … {done + 1}/{len(tasks)} sessions matched_total="
                    f"{len(results)} elapsed={_time.time() - t0:.0f}s",
                    flush=True,
                )

    misses: Dict[str, dict] = {}
    for q in questions:
        if q["date"] and q["question_id"] not in results:
            misses[q["question_id"]] = {
                "reason": "no_match",
                "note": "no confident match in any allowed session",
            }
    return results, misses, score_samples


def write_score_histogram(scores: List[Tuple[float, str]], out: Path) -> None:
    buckets = {}
    for sc, method in scores:
        b = int(min(sc, 120) // 10) * 10
        key = (b, method.split("-")[0])
        buckets[key] = buckets.get(key, 0) + 1
    lines = ["# score histogram (score bucket × method)", ""]
    for (b, method), n in sorted(buckets.items()):
        lines.append(f"- {b:3d}+ {method}: {n}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sweep_task(part):
    """Worker: sweep a chunk of pending questions; nearest matching session wins."""
    from difflib import SequenceMatcher

    by_id = _WORKER["by_id"]
    conv = _WORKER["converter"]
    streams = _WORKER.setdefault("streams", {})
    sessions = _WORKER.setdefault("sessions", inventory_sessions())

    segs = []
    for qid, lo, hi in part:
        q = by_id.get(qid)
        if q is None or (len(q["_ap"]) < 20 and len(q["_qp"]) < 20):
            continue
        np_, ap, qp = q["_np"], q["_ap"], q["_qp"]
        hit = None
        for si in range(lo, hi):
            session = sessions[si]
            key = session["srt_file"]
            st = streams.get(key)
            if st is None:
                path = Path(key)
                cues = parse_srt(path, conv)
                if not cues:
                    streams[key] = SessionStream(session, [], conv)
                    continue
                st = SessionStream(session, cues, conv, parse_srt_raw(path))
                streams[key] = st
            stream = st.py
            # 1) name-anchored with a raised bar
            if len(np_) >= 3:
                pos = 0
                for _ in range(20):
                    i = stream.find(np_, pos)
                    if i < 0:
                        break
                    sc = _verify(stream, i, ap, qp)
                    if sc >= T_ACCEPT + SWEEP_MARGIN:
                        hit = (sc, i, st, session, "sweep-name")
                        break
                    pos = i + max(len(np_), 1)
            # 2) answer-text with an even higher bar
            if hit is None:
                needle = ap if len(ap) >= 20 else qp
                probe = (
                    needle[ANSWER_SKIP_HEAD:]
                    if len(needle) > ANSWER_SKIP_HEAD + 24
                    else needle
                )
                if len(probe) >= 20 and _cheap_prefilter(stream, probe):
                    m = SequenceMatcher(None, stream, probe, autojunk=False).find_longest_match(
                        0, len(stream), 0, len(probe)
                    )
                    if m.size >= T_NONAME + SWEEP_MARGIN:
                        hit = (float(m.size), m.a, st, session, "sweep-answer")
            if hit:
                break  # chronological order: nearest answer-day wins
        if hit is None:
            continue
        sc, char_pos, st, session, method = hit
        start_t = st.cue_start_time(char_pos)
        busy = (_WORKER.get("busy") or {}).get(session["session_id"]) or []
        if _time_overlaps(busy, start_t):
            continue  # already covered by an existing button
        end_t = min(start_t + 240.0, st.audio_end)
        conf = min(1.0, sc / 70.0)
        fields = range_fields(
            start_t, end_t, round(conf, 3), "auto",
            srt_preview(st.raw_cues, start_t, end_t),
        )
        fields["notes"] = f"method={method}"
        segs.append(
            {
                "question_id": qid,
                **fields,
                "session_id": session["session_id"],
                "session_date": session["date"],
                "source": session["source"],
                "audio_file": session["audio_file"],
                "srt_file": session["srt_file"],
            }
        )
    return segs


def global_sweep(
    questions: List[dict],
    sessions: List[dict],
    results: Dict[str, dict],
    misses: Dict[str, dict],
    converter=None,
    questions_path: Optional[Path] = None,
    workers: int = 6,
    sweep_days: int = 150,
    busy: Optional[Dict[str, List]] = None,
) -> int:
    """Parallel high-threshold pass over sessions after the question date.

    Each pending question takes the FIRST (nearest) session that clears the
    raised thresholds; workers keep per-process stream caches. Regions already
    owned by existing buttons (``busy``) are off-limits.
    """
    pending = [q for q in questions if q["question_id"] not in results]
    if not pending:
        return 0
    print(f"Global sweep over {len(pending)} pending questions…", flush=True)

    import bisect
    import datetime as _dt
    from concurrent.futures import ProcessPoolExecutor

    dates = [s["date"] for s in sessions]
    indexed = []
    CH = 20
    for i in range(0, len(pending), CH):
        part = []
        for q in pending[i : i + CH]:
            qid, qd = q["question_id"], q["date"]
            if qd:
                lo = bisect.bisect_left(dates, qd)
                cap = (_dt.date.fromisoformat(qd) + _dt.timedelta(days=sweep_days)).isoformat()
                hi = len(sessions)
                while hi > lo and dates[hi - 1] > cap:
                    hi -= 1
            else:
                lo, hi = 0, len(sessions)
            part.append((qid, lo, hi))
        indexed.append(part)

    found_total = 0
    done = 0
    busy_json = json.dumps(busy or {}, ensure_ascii=False)
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_worker,
        initargs=(str(questions_path), busy_json),
    ) as ex:
        for part, segs in zip(indexed, ex.map(_sweep_task, indexed, chunksize=1)):
            done += len(part)
            for seg in segs:
                results[seg["question_id"]] = seg
                misses.pop(seg["question_id"], None)
            found_total += len(segs)
            print(f"  sweep {done}/{len(pending)} +{len(segs)}", flush=True)
    return found_total


def write_maps(
    questions: List[dict], results: Dict[str, dict],
    misses: Dict[str, dict], out_dir: Path,
) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_chapter: Dict[int, List[dict]] = {}
    for q in questions:
        by_chapter.setdefault(q["chapter_index"], []).append(q)

    written = []
    total_stats = {"matched": 0, "missing": 0}
    for ch_idx in sorted(by_chapter):
        segs = []
        stats = {"matched": 0, "missing": 0}
        for q in by_chapter[ch_idx]:
            r = results.get(q["question_id"])
            if r and r.get("start") is not None:
                seg = {
                    "index": q["number"],
                    "question_id": q["question_id"],
                    "stable_key": f"{ch_idx:02d}#q{q['number']}",
                    "chapter_index": ch_idx,
                    "chapter_title": q["chapter_title"],
                    "questioner": q["questioner"],
                    "question_time": q["time_raw"],
                    "question_date": q["date"],
                    "q_preview": (q.get("q_text") or "")[:160],
                    **r,
                }
                stats["matched"] += 1
            else:
                miss = misses.get(q["question_id"], {})
                seg = {
                    "index": q["number"],
                    "question_id": q["question_id"],
                    "stable_key": f"{ch_idx:02d}#q{q['number']}",
                    "chapter_index": ch_idx,
                    "chapter_title": q["chapter_title"],
                    "questioner": q["questioner"],
                    "question_time": q["time_raw"],
                    "question_date": q["date"],
                    "q_preview": (q.get("q_text") or "")[:160],
                    **empty_range_fields(),
                    "notes": miss.get("reason", ""),
                    "miss_note": miss.get("note", ""),
                }
                stats["missing"] += 1
            segs.append(seg)
        payload = {
            "book": "word",
            "chapter": f"{ch_idx:02d}",
            "version": 1,
            "stats": stats,
            "segments": segs,
        }
        path = out_dir / f"word-{ch_idx:02d}.json"
        existed = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if existed:
            payload = _merge_locked(existed, payload)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        written.append(path)
        total_stats["matched"] += stats["matched"]
        total_stats["missing"] += stats["missing"]
        print(f"  wrote {path.name}: matched={stats['matched']} missing={stats['missing']}")
    print(f"TOTAL matched={total_stats['matched']} missing={total_stats['missing']}")
    return written


def _merge_locked(old: dict, new: dict) -> dict:
    """Preserve manual edits (locked/manual status) across re-alignment."""
    old_by_key = {s.get("stable_key"): s for s in old.get("segments") or []}
    for seg in new.get("segments") or []:
        prev = old_by_key.get(seg.get("stable_key"))
        if prev and (prev.get("locked") or prev.get("status") == "manual"):
            for k in ("start", "end", "start_label", "end_label",
                      "confidence", "status", "locked", "notes"):
                if k in prev:
                    seg[k] = prev[k]
            if prev.get("audio_file"):
                seg["audio_file"] = prev["audio_file"]
            if prev.get("meta"):
                seg["meta"] = prev["meta"]
    return new


def write_review_report(
    questions: List[dict], results: Dict[str, dict], misses: Dict[str, dict], out: Path
) -> None:
    by_id = {q["question_id"]: q for q in questions}
    lines = ["# word_audio_map review report", ""]
    low = [
        (qid, r) for qid, r in results.items()
        if (r.get("confidence") or 0) < 0.5
    ]
    lines.append(f"## Low confidence auto-matches ({len(low)})")
    for qid, r in sorted(low, key=lambda kv: kv[1].get("confidence") or 0):
        q = by_id.get(qid, {})
        lines.append(
            f"- conf={r.get('confidence'):.2f} {r.get('session_date')} "
            f"[{r.get('notes')}] ch{q.get('chapter_index')}#{q.get('number')} "
            f"{q.get('questioner')}: {(q.get('q_text') or '')[:60]}"
        )
    lines.append("")
    reason_counts: Dict[str, int] = {}
    for m in misses.values():
        reason_counts[m["reason"]] = reason_counts.get(m["reason"], 0) + 1
    lines.append(f"## Missing segments ({sum(reason_counts.values())}) by reason")
    for reason, count in sorted(reason_counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {reason}: {count}")
    lines.append("")
    lines.append("## Missing detail (first 200)")
    shown = 0
    for qid, m in misses.items():
        if shown >= 200:
            break
        q = by_id.get(qid, {})
        lines.append(
            f"- {m['reason']} ch{q.get('chapter_index')}#{q.get('number')} "
            f"{q.get('date') or 'undated'} {q.get('questioner')}: "
            f"{(q.get('q_text') or '')[:50]}"
        )
        shown += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Review report → {out}")


def _load_busy(map_dir: Path = WORD_MAP_DIR) -> Dict[str, List]:
    """Existing mapped ranges per session: {session_id: [[start, end], …]}."""
    busy: Dict[str, List] = {}
    for path in sorted(map_dir.glob("word-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for s in data.get("segments") or []:
            if s.get("start") is not None and s.get("session_id"):
                busy.setdefault(s["session_id"], []).append(
                    [float(s["start"]), float(s["end"] or s["start"])]
                )
    return busy


def _load_missing_from_maps(map_dir: Path = WORD_MAP_DIR) -> List[Tuple[str, str, str]]:
    """Collect (question_id, stable_key, question_date) for missing segments."""
    targets = []
    for path in sorted(map_dir.glob("word-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for s in data.get("segments") or []:
            if s.get("start") is None and not s.get("locked") \
                    and s.get("status") != "manual":
                targets.append(
                    (s["question_id"], s["stable_key"], s.get("question_date") or "")
                )
    return targets


def apply_near_patches(patches: List[dict], map_dir: Path = WORD_MAP_DIR) -> int:
    """Patch missing segments in word-*.json in place; returns #patched."""
    if not patches:
        return 0
    by_key = {(p["question_id"], p["stable_key"]): p for p in patches}
    patched_total = 0
    for path in sorted(map_dir.glob("word-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        stats = {"matched": 0, "review": 0, "missing": 0}
        patched_here = 0
        for s in data.get("segments") or []:
            p = by_key.get((s["question_id"], s["stable_key"]))
            if p and s.get("start") is None and not s.get("locked"):
                for k in ("start", "end", "start_label", "end_label",
                          "confidence", "status", "notes", "srt_preview",
                          "session_id", "session_date", "source",
                          "audio_file", "srt_file"):
                    if k in p:
                        s[k] = p[k]
                s.pop("miss_note", None)
                changed = True
                patched_here += 1
            if s.get("start") is None:
                stats["missing"] += 1
            elif s.get("status") == "review":
                stats["review"] += 1
            else:
                stats["matched"] += 1
        if changed:
            data["stats"] = stats
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
            )
            print(f"  patched {path.name}: matched={stats['matched']} "
                  f"review={stats['review']} missing={stats['missing']}")
            patched_total += patched_here
    return patched_total


def _busy_from_results(results: Dict[str, dict]) -> Dict[str, List]:
    busy: Dict[str, List] = {}
    for r in results.values():
        if r.get("session_id") and r.get("start") is not None:
            busy.setdefault(r["session_id"], []).append(
                [float(r["start"]), float(r.get("end") or r["start"])]
            )
    return busy


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--questions", type=Path, default=BUILD_DIR / "questions.json")
    ap.add_argument("--srt-root", type=Path, default=DEFAULT_SRT_ROOT)
    ap.add_argument("--session-limit", type=int, default=0, help="debug: first N sessions only")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-sweep", action="store_true", help="skip the global fallback sweep")
    ap.add_argument("--near-days", type=int, default=3,
                    help="forward-day window for the near pass (default 3)")
    ap.add_argument("--mode", choices=["calendar", "answer-days"], default="calendar",
                    help="near-pass candidate selection mode")
    ap.add_argument("--max-answer-dates", type=int, default=2,
                    help="answer-days mode: how many distinct answer days to try")
    ap.add_argument("--t-accept", type=float, default=None,
                    help="override auto acceptance threshold (name path)")
    ap.add_argument("--t-noname", type=float, default=None,
                    help="override auto acceptance threshold (answer path)")
    ap.add_argument("--t-review", type=float, default=None,
                    help="override review-tier floor")
    ap.add_argument("--no-near", action="store_true",
                    help="skip the near-forward retry pass")
    ap.add_argument("--near-only", action="store_true",
                    help="maintenance mode: patch existing maps' missing "
                         "segments with the near-forward pass only")
    ap.add_argument("--apply", action="store_true", help="write word-*.json maps")
    ap.add_argument("--report-only", action="store_true", help="dry run, no writes at all")
    args = ap.parse_args(argv)

    converter = get_converter()
    if converter is None:
        print("warning: OpenCC unavailable; matching quality may drop")

    sessions = inventory_sessions(args.srt_root)
    playable = sum(1 for s in sessions if s["opus_exists"])

    if args.near_only:
        targets = _load_missing_from_maps()
        busy = _load_busy()
        thr = (
            args.t_accept if args.t_accept is not None else T_ACCEPT,
            args.t_noname if args.t_noname is not None else T_NONAME,
            args.t_review if args.t_review is not None else T_REVIEW_FLOOR + 1,
        )
        print(f"{len(targets)} missing segments loaded from maps; "
              f"{len(sessions)} SRT sessions ({playable} with opus); "
              f"mode={args.mode} thr={thr}")
        patches = near_forward_pass(
            targets, sessions, converter,
            questions_path=args.questions, workers=args.workers,
            near_days=args.near_days, busy=busy,
            mode=args.mode, max_answer_dates=args.max_answer_dates, thr=thr,
        )
        n_auto = sum(1 for p in patches if p.get("status") == "auto")
        n_rev = sum(1 for p in patches if p.get("status") == "review")
        print(f"Near-forward pass recovered {len(patches)} segments "
              f"(auto={n_auto}, review={n_rev})")
        n = apply_near_patches(patches)
        print(f"Done: {n} segment(s) written")
        return 0

    questions = load_questions(args.questions)
    print(
        f"{len(questions)} questions, {len(sessions)} SRT sessions "
        f"({playable} with opus)", flush=True,
    )

    results, misses, scores = align_pass(
        questions, sessions, args.questions,
        workers=args.workers, session_limit=args.session_limit,
    )
    print(f"After main pass: matched={len(results)} missing={len(misses)}")
    write_score_histogram(scores, BUILD_DIR / "score_histogram.md")

    if not args.no_near:
        targets = [
            (q["question_id"], f"{q['chapter_index']:02d}#q{q['number']}", q["date"])
            for q in questions
            if q["question_id"] in misses
        ]
        busy = _busy_from_results(results)
        patches = near_forward_pass(
            targets, sessions, converter,
            questions_path=args.questions, workers=args.workers,
            near_days=args.near_days, busy=busy,
        )
        for p in patches:
            results[p["question_id"]] = {
                k: v for k, v in p.items() if k != "stable_key"
            }
            misses.pop(p["question_id"], None)
        print(f"Near-forward pass recovered {len(patches)}")

    if not args.no_sweep:
        found = global_sweep(
            questions, sessions, results, misses,
            converter, questions_path=args.questions, workers=args.workers,
            busy=_busy_from_results(results),
        )
        print(f"Global sweep recovered {found}")

    matched = len(results)
    total_dated = sum(1 for q in questions if q["date"])
    print(
        f"Coverage: {matched}/{len(questions)} = {matched / len(questions):.1%} "
        f"(dated: {matched}/{total_dated} = "
        f"{(matched / total_dated if total_dated else 0):.1%})"
    )

    if args.report_only:
        write_review_report(questions, results, misses, BUILD_DIR / "review_report.md")
        return 0
    if args.apply:
        write_maps(questions, results, misses, WORD_MAP_DIR)
        write_review_report(questions, results, misses, BUILD_DIR / "review_report.md")
    else:
        print("(dry-run; pass --apply to write maps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
