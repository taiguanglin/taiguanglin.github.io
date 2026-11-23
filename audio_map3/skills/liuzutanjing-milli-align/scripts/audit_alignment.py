#!/usr/bin/env python3
"""《壇經》逐講結構與人工 golden 保護稽核（只讀 SoT）。

用法：
  python3 audit_alignment.py --baseline /tmp/liuzutanjing_pre_L6_L27_r3.json \
    --lectures 6-27 --out /tmp/liuzutanjing_structural_r3.json
  --require-clean 會把目標講次的倒序、鏈破口、負長度、零寬旗標不一致、
  末段不等 duration 視為失敗；golden／confirmed／pid／text 改變永遠失敗。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SO_T = ROOT / "audio_map3" / "liuzutanjing.json"
GOLDEN = {str(n) for n in range(1, 6)}


def parse_lectures(spec: str) -> list[str]:
    out: list[str] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(str(n) for n in range(int(a), int(b) + 1))
        elif part:
            out.append(str(int(part)))
    return list(dict.fromkeys(out))


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def audit_lecture(number: str, lecture: dict) -> dict:
    ps = lecture["paragraphs"]
    duration = lecture.get("duration")
    reads = [i for i, p in enumerate(ps) if p["end"] > p["start"]]
    negative = [{"i": i, "start": p["start"], "end": p["end"]}
                for i, p in enumerate(ps) if p["end"] < p["start"]]
    inversions = [{"i": i, "previous_start": ps[i - 1]["start"], "start": ps[i]["start"]}
                  for i in range(1, len(ps)) if ps[i]["start"] < ps[i - 1]["start"]]
    chain = []
    for a, b in zip(reads, reads[1:]):
        delta = ps[a]["end"] - ps[b]["start"]
        if abs(delta) > 0.0005:
            chain.append({"i": a, "next_read": b, "delta": round(delta, 6),
                          "kind": "overlap" if delta > 0 else "gap"})
    wide_zero = [i for i, p in enumerate(ps) if p.get("zero") and p["end"] > p["start"]]
    unflagged_zero = [i for i, p in enumerate(ps)
                      if not p.get("zero") and p["end"] == p["start"]]
    last_error = None
    if reads and duration is not None and abs(ps[reads[-1]]["end"] - duration) > 0.0005:
        last_error = {"i": reads[-1], "end": ps[reads[-1]]["end"], "duration": duration}
    pids = [p["pid"] for p in ps]
    return {
        "lecture": int(number), "sha256": digest(lecture), "paragraphs": len(ps),
        "read": len(reads), "zero_flag": sum(bool(p.get("zero")) for p in ps),
        "zero_width": sum(p["end"] == p["start"] for p in ps),
        "confirmed": sum(bool(p.get("confirmed")) for p in ps),
        "reviewed": bool(lecture.get("reviewed")), "negative": negative,
        "inversions": inversions, "chain_defects": chain,
        "wide_zero": wide_zero, "unflagged_zero": unflagged_zero,
        "last_read_error": last_error, "duplicate_pids": sorted({p for p in pids if pids.count(p) > 1}),
        "defect_count": (len(negative) + len(inversions) + len(chain) + len(wide_zero)
                         + len(unflagged_zero) + int(last_error is not None)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--lectures", default="6-27")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--require-clean", action="store_true")
    args = ap.parse_args()
    current = json.loads(SO_T.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    targets = set(parse_lectures(args.lectures))
    report = {"source": str(SO_T), "baseline": str(args.baseline), "targets": sorted(targets, key=int),
              "lectures": {}, "protection_errors": [], "new_defects": []}
    fatal = False
    for number, lecture in current["lectures"].items():
        old = baseline["lectures"].get(number)
        if old is None:
            report["protection_errors"].append({"lecture": number, "kind": "lecture-added"})
            fatal = True
            continue
        before = audit_lecture(number, old)
        after = audit_lecture(number, lecture)
        after["baseline_sha256"] = before["sha256"]
        report["lectures"][number] = after
        old_ps, new_ps = old["paragraphs"], lecture["paragraphs"]
        if len(old_ps) != len(new_ps):
            report["protection_errors"].append({"lecture": number, "kind": "paragraph-count"})
            fatal = True
        else:
            for i, (a, b) in enumerate(zip(old_ps, new_ps)):
                if a["pid"] != b["pid"] or a["text"] != b["text"]:
                    report["protection_errors"].append({"lecture": number, "i": i, "kind": "pid/text"})
                    fatal = True
                if a.get("confirmed") or number in GOLDEN:
                    if canonical(a) != canonical(b):
                        report["protection_errors"].append({"lecture": number, "i": i, "kind": "confirmed/golden"})
                        fatal = True
        if old.get("reviewed") != lecture.get("reviewed"):
            report["protection_errors"].append({"lecture": number, "kind": "reviewed"})
            fatal = True
        if number not in targets and before["sha256"] != after["sha256"]:
            report["protection_errors"].append({"lecture": number, "kind": "non-target-changed"})
            fatal = True
        for key in ("negative", "inversions", "chain_defects", "wide_zero", "unflagged_zero"):
            old_count, new_count = len(before[key]), len(after[key])
            if new_count > old_count:
                report["new_defects"].append({"lecture": number, "kind": key,
                                              "before": old_count, "after": new_count})
                fatal = True
        if args.require_clean and number in targets:
            for key in ("negative", "inversions", "chain_defects", "wide_zero", "unflagged_zero"):
                if after[key]:
                    fatal = True
            if after["last_read_error"] or after["duplicate_pids"]:
                fatal = True
    for number in baseline["lectures"].keys() - current["lectures"].keys():
        report["protection_errors"].append({"lecture": number, "kind": "lecture-removed"})
        fatal = True
    report["ok"] = not fatal
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    for number in sorted(targets, key=int):
        r = report["lectures"][number]
        print(f"L{int(number):02d}: READ={r['read']} zero={r['zero_flag']} "
              f"defects={r['defect_count']} inv={len(r['inversions'])} "
              f"chain={len(r['chain_defects'])} unflagged={len(r['unflagged_zero'])}")
    print(f"protection_errors={len(report['protection_errors'])} new_defects={len(report['new_defects'])}")
    print(f"VERDICT: {'PASS' if not fatal else 'FAIL'}")
    if args.out:
        print(f"report → {args.out}")
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
