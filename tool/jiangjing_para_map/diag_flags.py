#!/usr/bin/env python3
"""Diagnose audit span_bad rows: does an exact verbatim occurrence of the
paragraph head (or a head fragment) exist inside the span? If yes the stored
position is RIGHT and the audit threshold is too strict; if no the row needs
a look at the raw ASR text around the span."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
from realign_dtw import load_dump, FILLER_RE  # noqa: E402

MAP = ROOT / "audio_map3" / "lengqie.json"
REPORT = ROOT / "tool" / "jiangjing_para_map" / "reports" / "span_audit_lengqie.json"


_PUNCT = set("，。、；：？！…—·“”‘’《》〈〉()[]【】\"'！？｡，．：；＿（）＆＃＊＋－／＜＞＝＠＼＾＄％｜～")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", "", s)
    s = FILLER_RE.sub("", s)
    return "".join(ch for ch in s if ch not in _PUNCT)


def main() -> None:
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    amap = json.loads(MAP.read_text(encoding="utf-8"))
    flagged = []
    for lec in rep["rows"]:
        for d in lec["details"]:
            if d["verdict"] in ("span_bad", "unknown"):
                flagged.append((lec["lecture"], d))
    print(f"flagged rows: {len(flagged)}")

    stats = Counter()
    examples = {"bad_exact_in": [], "bad_frag_in": [], "bad_none": [],
                "unk_exact_in": [], "unk_frag_in": [], "unk_none": []}
    by_lec = {}
    for lec_n, d in flagged:
        lec = amap["lectures"][str(lec_n)]
        para = next((p for p in lec["paragraphs"] if p["pid"] == d["pid"]),
                    None)
        if para is None:
            stats["no_para"] += 1
            continue
        n = lec_n.zfill(2)
        import numpy  # noqa: F401  (load_dump returns arrays built here)
        raw = json.loads(Path(f"/tmp/funasr_cache/lengqie/{lec_n}.json")
                         .read_text(encoding="utf-8"))
        snorm = norm(raw["text"])
        times = raw["timestamp"]
        s_t, e_t = d["start"], d["end"]
        # char index window for the span
        starts = [t[0] for t in times]
        import bisect
        c_lo = bisect.bisect_left(starts, s_t - 1.0)
        c_hi = bisect.bisect_left(starts, e_t + 1.0)
        # text and stream are both norm'd from the same raw string; use it
        # directly as the stream text.
        s_pos = max(0, c_lo - 5)
        e_pos = min(len(snorm), c_hi + 40)
        win = snorm[s_pos:e_pos]
        pnorm = norm(para["text"])
        head24 = pnorm[:24]
        verdict = d["verdict"]
        key = "bad" if verdict == "span_bad" else "unk"
        # exact head in window?
        exact = head24 and head24 in win
        # fragment (10-char) in window?
        frag = any(pnorm[o:o+10] in win for o in range(0, max(1, len(pnorm)-9), 6))
        if exact:
            stats[f"{key}_exact_in"] += 1
            examples[f"{key}_exact_in"].append((lec_n, d["i"], head24[:18], s_t, e_t))
        elif frag:
            stats[f"{key}_frag_in"] += 1
            examples[f"{key}_frag_in"].append((lec_n, d["i"], head24[:18], s_t, e_t))
        else:
            stats[f"{key}_none"] += 1
            if len(examples[f"{key}_none"]) < 400:
                examples[f"{key}_none"].append((lec_n, d["i"], head24[:18], s_t, e_t, d.get("ev", {}).get("d_head"), d.get("ev", {}).get("d_blk")))
        by_lec.setdefault(lec_n, Counter())[f"{key}_{'exact' if exact else ('frag' if frag else 'none')}"] += 1

    print(json.dumps(stats, ensure_ascii=False, indent=1))
    for k in ("bad_exact_in", "bad_frag_in", "unk_exact_in", "unk_frag_in"):
        print(f"\n--- {k} ({len(examples[k])}) ---")
        for row in examples[k][:12]:
            print("   ", row)
    print(f"\n--- bad_none ({len(examples['bad_none'])}) first 25 ---")
    for row in examples["bad_none"][:25]:
        print("   ", row)


if __name__ == "__main__":
    main()
