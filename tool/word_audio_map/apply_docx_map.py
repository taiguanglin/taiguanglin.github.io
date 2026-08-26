#!/usr/bin/env python3
"""v2 R3 — wipe legacy alignment fields, then fill directly from D1+bridge.

Order per segment:
  1. protected states (locked/manual/none/meta.confirmed) are skipped;
  2. ALL timing fields are wiped (legacy json alignment is discarded);
  3. if the question is bridged AND its docx block has a real placed start,
     times/status/notes/session refs are written from docx_audio_map.json.

Also writes build/v2_diff_report.md comparing against build/pre_v2_snapshot/.
"""
from __future__ import annotations

import collections
import json
import sys
from collections import Counter
from pathlib import Path

TOOL = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL))
from wcommon import WORD_MAP_DIR, BUILD_DIR  # noqa: E402

PROTECT_STATUS = {"manual", "none"}
TIMING_KEYS = ("start", "end", "start_label", "end_label", "srt_preview",
               "session_id", "audio_file", "srt_file")


def main():
    D1 = json.loads((BUILD_DIR / "docx_audio_map.json").read_text())
    bridge = json.loads((BUILD_DIR / "qid_bridge_v2.json").read_text())["bridge"]

    # qid -> fill payload (only real placements)
    place = {}          # (sid, seq) -> {seg, run}
    for date, e in D1.items():
        for run in e.get("runs", []):
            for sg in run["segments"]:
                if sg.get("start") is None:
                    continue
                place[(run["sid"], sg["seq"])] = (sg, run)

    # ---- global per-session chaining (runs from different chapters of the
    # same audio file were chained independently and can interleave) --------
    from collections import defaultdict
    bysid = defaultdict(list)
    for (sid, seq), (sg, run) in place.items():
        bysid[sid].append((sg["start"], sg))
    demoted_collapsed = 0
    for sid, lst in bysid.items():
        lst.sort(key=lambda t: t[0])
        for j, (st0, sg) in enumerate(lst):
            if j + 1 < len(lst):
                cap = round(lst[j + 1][0] - 0.01, 3)
                if (sg.get("end") or 0) > cap:
                    sg["end"] = cap
            if (sg.get("end") or 0) <= st0 + 1.0:
                sg["end"] = None
                sg["_collapsed"] = True
                demoted_collapsed += 1

    fill = {}
    for qid, br in bridge.items():
        hit = place.get((br["session_id"], br["block_seq"]))
        if not hit:
            continue
        sg, run = hit
        collapsed = sg.pop("_collapsed", False)
        st = "auto" if (sg.get("status") == "auto" and not collapsed) else "review"
        if collapsed:
            demoted_collapsed += 0  # counted above
        fill[qid] = {
            "f_sid": run["sid"],
            "audio_file": run["audio_file"], "srt_file": run["srt_file"],
            "start": sg["start"], "end": sg.get("end"),
            "start_label": sg.get("start_label"), "end_label": sg.get("end_label"),
            "status": st,
            "confidence": sg.get("confidence", 0.0),
            "notes": f"docx1(r={sg.get('r')},cov={sg.get('coverage')},"
                     f"named={int(bool(sg.get('named')))},"
                     f"marker={int(bool(sg.get('marker')))})",
            "srt_preview": sg.get("srt_preview", ""),
        }

    pending = []
    snap_dir = BUILD_DIR / "pre_v2_snapshot"
    old_b, new_b = Counter(), Counter()
    wiped = filled = kept_missing = protected = sid_changed = 0
    moved = []

    def bucket(seg):
        st = seg.get("status")
        c = seg.get("confidence")
        if st != "auto":
            return st or "None"
        return ">=0.8" if isinstance(c, (int, float)) and c >= .8 else \
            "0.5-0.8" if isinstance(c, (int, float)) and c >= .5 else "<0.5"

    for mf in sorted(WORD_MAP_DIR.glob("word-*.json")):
        data = json.loads(mf.read_text())
        for seg in data["segments"]:
            old_b[bucket(seg)] += 1
            old_sid = seg.get("session_id")
            if seg.get("locked") or seg.get("status") in PROTECT_STATUS \
                    or (seg.get("meta") or {}).get("confirmed"):
                protected += 1
                new_b[bucket(seg)] += 1
                continue
            for k in TIMING_KEYS:
                seg[k] = None
            seg["confidence"] = 0.0
            seg["status"] = "missing"
            seg["notes"] = ""
            for stray in ("sid", "date"):
                if stray in seg:
                    del seg[stray]
            f = fill.get(seg.get("question_id"))
            if f:
                f_sid = f["f_sid"]
                seg.update({k: v for k, v in f.items() if k != "f_sid"})
                filled += 1
                seg["session_id"] = f_sid
                if old_sid and old_sid != f_sid:
                    sid_changed += 1
                o = None
                if old_sid == f_sid:
                    try:
                        snap = json.loads((snap_dir / mf.name).read_text())
                        for s2 in snap["segments"]:
                            if s2.get("question_id") == seg["question_id"]:
                                o = s2
                                break
                    except Exception:
                        o = None
                if o and o.get("start") is not None:
                    d = abs((o["start"] or 0) - (seg["start"] or 0))
                    if d > 120:
                        moved.append((seg.get("stable_key"), round(d)))
            else:
                seg["notes"] = "no-docx-counterpart"
                kept_missing += 1
            new_b[bucket(seg)] += 1
        st = Counter()
        for seg in data["segments"]:
            if seg.get("status") == "auto":
                st["matched"] += 1
            elif seg.get("status") == "review":
                st["review"] += 1
            elif seg.get("status") == "none":
                st["none"] += 1
            else:
                st["missing"] += 1
        data["stats"] = dict(st)
        data["version"] = int(data.get("version", 1)) + 1
        data["_mf"] = str(mf)
        pending.append(data)

    # ---- final overlap sweep across ALL files (same-session duplicates) ----
    refs = collections.defaultdict(list)
    for data in pending:
        for seg in data["segments"]:
            if seg.get("status") == "auto" and seg.get("start") is not None:
                refs[seg["session_id"]].append((seg["start"], seg))
    swept = 0
    from common import fmt_tc  # noqa: E402
    for sid, lst in refs.items():
        lst.sort(key=lambda t: t[0])
        for (ta, sga), (tb, sgb) in zip(lst, lst[1:]):
            end_a = sga.get("end") or 0
            if tb < end_a - 0.05:
                deg_b = (sgb.get("end") or 0) - tb < 1.0
                if deg_b or (sga.get("confidence") or 0) >= (sgb.get("confidence") or 0):
                    drop = sgb
                else:
                    drop = sga
                drop["status"] = "review"
                drop["notes"] = (drop.get("notes") or "") + ";v2-overlap-demote"
                swept += 1
            elif end_a > tb + 0.05:
                sga["end"] = round(tb - 0.01, 3)
                sga["end_label"] = fmt_tc(sga["end"])
                swept += 1
        for ta, sga in lst:
            if sga.get("status") == "auto" and (sga.get("end") or 0) <= ta + 1.0:
                sga["status"] = "review"
                sga["notes"] = (sga.get("notes") or "") + ";v2-degenerate"
                swept += 1
    for data in pending:
        mf = Path(data.pop("_mf"))
        st2 = Counter()
        for seg in data["segments"]:
            if seg.get("status") == "auto":
                st2["matched"] += 1
            elif seg.get("status") == "review":
                st2["review"] += 1
            elif seg.get("status") == "none":
                st2["none"] += 1
            else:
                st2["missing"] += 1
        data["stats"] = dict(st2)
        mf.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")

    lines = [
        "# v2 寫回 diff 報告",
        "",
        f"- 清空並填充：{filled}；清空後無對應（missing）：{kept_missing}；保護跳過：{protected}",
        f"- 場次變更（vs 舊 sid）：{sid_changed}",
        f"- |Δstart|>120s（vs 快照）：{len(moved)}；終掃修正：{swept}",
        "",
        "| 等級 | v1後快照 | v2 |", "|---|---|---|",
    ]
    for k in ("auto>=0.8", ">=0.8", "auto0.5-0.8", "0.5-0.8", "auto<0.5", "<0.5",
              "review", "missing", "none", "manual"):
        o, n = old_b.get(k, 0), new_b.get(k, 0)
        if o or n:
            lines.append(f"| {k} | {o} | {n} |")
    lines.append("")
    lines.append("- 大位移樣本：")
    for k, d in sorted(moved, key=lambda t: -t[1])[:40]:
        lines.append(f"  - {k} Δ{d}s")
    (BUILD_DIR / "v2_diff_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"filled={filled} missing={kept_missing} protected={protected} "
          f"sid_changed={sid_changed}")
    print("new buckets:", {k: v for k, v in sorted(new_b.items())})
    ok = filled >= 4000 and protected == 0
    print("GATE:", "PASS" if ok else "CHECK")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
