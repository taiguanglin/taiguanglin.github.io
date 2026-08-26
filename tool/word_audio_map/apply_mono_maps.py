#!/usr/bin/env python3
"""Phase 5 — write mono-alignment results back into data/audio_map_word/*.json.

Rules (PLAN §5):
  - only segments whose question_id is bridged AND whose chrono segment has a
    start are rewritten;
  - locked / manual / none / meta.confirmed segments are never touched;
  - question_id / stable_key / index / chapter fields / q_text / a_text stay
    exactly as they were (ebook text comes from the thematic docx only);
  - unbridged segments keep their previous mapping (counted in the report).

Writes build/diff_report.md too.
"""
from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path

TOOL = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL))
from wcommon import WORD_MAP_DIR, BUILD_DIR  # noqa: E402

PROTECT_STATUS = {"manual", "none"}
BIG_MOVE = 120.0


def load_json(p: Path):
    return json.loads(p.read_text())


def main():
    bridge = load_json(BUILD_DIR / "qid_bridge.json")["bridge"]
    align = load_json(BUILD_DIR / "session_alignment.json")
    # index alignment: (session_id, seq) -> segment
    seg_index = {}
    for date, e in align.items():
        for part in e.get("parts", []):
            for s in part["segments"]:
                seg_index[(part["session_id"], s["seq"])] = s

    map_files = sorted(WORD_MAP_DIR.glob("word-*.json"))
    if not map_files:
        print("no maps found"); return 1
    backup_dir = BUILD_DIR / "pre_mono_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    old_buckets, new_buckets = Counter(), Counter()
    changed = kept_old = protected = 0
    big_moves = []

    def bucket(seg):
        c = seg.get("confidence")
        st = seg.get("status")
        if st != "auto":
            return st or "None"
        return ">=0.8" if isinstance(c, (int, float)) and c >= .8 else \
            "0.5-0.8" if isinstance(c, (int, float)) and c >= .5 else "<0.5"

    for mf in map_files:
        data = load_json(mf)
        (backup_dir / mf.name).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8")
        for seg in data["segments"]:
            old_buckets[bucket(seg)] += 1
            qid = seg.get("question_id")
            br = bridge.get(qid)
            if seg.get("locked") or seg.get("status") in PROTECT_STATUS \
                    or (seg.get("meta") or {}).get("confirmed"):
                protected += 1
                new_buckets[bucket(seg)] += 1
                continue
            if not br:
                kept_old += 1
                new_buckets[bucket(seg)] += 1
                continue
            asg = seg_index.get((br["session_id"], br["block_seq"]))
            if asg is None or asg.get("start") is None:
                kept_old += 1
                new_buckets[bucket(seg)] += 1
                continue
            old_start = seg.get("start")
            new_status = asg["status"]           # auto | review
            seg["start"] = asg["start"]
            seg["end"] = asg.get("end")
            seg["start_label"] = asg.get("start_label")
            seg["end_label"] = asg.get("end_label")
            seg["confidence"] = asg.get("confidence", 0.0)
            prev_notes = seg.get("notes") or ""
            base_notes = prev_notes.split(";cal2")[0].split(";mono")[0]
            seg["notes"] = f"{base_notes};mono(lcb={asg.get('lcb')},named={int(asg.get('named', False))})" \
                if new_status == "auto" else f"{base_notes};mono-review(no-anchor)" \
                if asg.get("reason") == "no-anchor" else f"{base_notes};mono-review(low-conf)"
            seg["status"] = new_status
            seg["session_id"] = br["session_id"]
            sess_date = br["session_date"]
            # audio_file/srt_file from the session part
            part_src = None
            for part in align[sess_date]["parts"]:
                if part["session_id"] == br["session_id"]:
                    part_src = part
                    break
            if part_src:
                seg["audio_file"] = part_src["audio_file"]
                seg["srt_file"] = part_src["srt_file"]
            seg["srt_preview"] = asg.get("srt_preview", "")
            if old_start is not None and abs((asg["start"] or 0) - old_start) > BIG_MOVE:
                big_moves.append({
                    "stable_key": seg.get("stable_key"), "qid": qid,
                    "old": {"start": old_start, "sid": seg.get("session_id")},
                    "new": {"start": asg["start"], "sid": br["session_id"]},
                })
            changed += 1
            new_buckets[bucket(seg)] += 1
        data["version"] = int(data.get("version", 1)) + 1
        st = Counter()
        for seg in data["segments"]:
            if seg.get("status") == "auto" and seg.get("start") is not None:
                st["matched"] += 1
            elif seg.get("status") == "review":
                st["review"] += 1
            elif seg.get("status") == "none":
                st["none"] += 1
            else:
                st["missing"] += 1
        data["stats"] = dict(st)
        mf.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")

    lines = [
        "# mono 写回 diff 報告",
        "",
        f"- 更新段數：{changed}；保留舊值（未橋接/無錨點）：{kept_old}；受保護跳過：{protected}",
        f"- confidence 分佈 old → new：",
    ]
    for k in ("auto>=0.8", ">=0.8", "auto0.5-0.8", "0.5-0.8", "auto<0.5", "<0.5",
              "review", "missing", "none", "manual"):
        o, n = old_buckets.get(k, 0), new_buckets.get(k, 0)
        if o or n:
            lines.append(f"  - {k}: {o} → {n}")
    lines.append("")
    lines.append(f"- |Δstart|>{BIG_MOVE:.0f}s 的段（{len(big_moves)} 筆，人工抽查優先）：")
    for mv in big_moves[:60]:
        lines.append(f"  - {mv['stable_key']} {mv['qid'][-8:]} "
                     f"{mv['old']['sid']}@{mv['old']['start']:.0f}s → "
                     f"{mv['new']['sid']}@{mv['new']['start']:.0f}s")
    (BUILD_DIR / "diff_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"changed={changed} kept_old={kept_old} protected={protected}")
    print("new buckets:", dict(new_buckets))
    ok = changed > 4000 and protected == 0
    print("GATE:", "PASS" if ok else "CHECK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
