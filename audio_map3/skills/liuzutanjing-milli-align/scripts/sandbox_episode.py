#!/usr/bin/env python3
"""在 /tmp 隔離套用單講裁決表並跑結構／證據驗收，不碰 repo SoT。

必須用 tool/sense_voice/.venv/bin/python。例：
  V=tool/sense_voice/.venv/bin/python
  $V sandbox_episode.py --lecture 6 --table /tmp/L6.json \
    --baseline /tmp/liuzutanjing_pre_L6_L27_r3.json \
    --workdir /tmp/l6_sandbox --require-clean
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SKILL = ROOT / "audio_map3" / "skills"
GENERIC = SKILL / "milli-align" / "scripts"
DEDICATED = SKILL / "liuzutanjing-milli-align" / "scripts"


def load_module(name: str, path: Path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric_stats(rows: list[dict]) -> dict:
    ds = [float(r["d"]) for r in rows]
    if not ds:
        return {"n": 0}
    return {
        "n": len(ds), "median": round(statistics.median(ds), 3),
        "mean": round(statistics.mean(ds), 3),
        "within_03": sum(abs(d) <= .3 for d in ds),
        "within_05": sum(abs(d) <= .5 for d in ds),
        "within_07": sum(abs(d) <= .7 for d in ds),
        "late_07": sum(d > .7 for d in ds), "early_07": sum(d < -.7 for d in ds),
        "outliers": [r for r in rows if abs(float(r["d"])) > .7],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lecture", required=True)
    ap.add_argument("--table", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--require-clean", action="store_true")
    args = ap.parse_args()
    n = str(int(args.lecture))
    args.workdir.mkdir(parents=True, exist_ok=True)
    target = args.workdir / "liuzutanjing.json"
    target.write_bytes(args.baseline.read_bytes())
    before_dir = args.workdir / "before"
    before_dir.mkdir(exist_ok=True)
    before_map = before_dir / "liuzutanjing.json"
    before_map.write_bytes(args.baseline.read_bytes())
    doc = json.loads(target.read_text(encoding="utf-8"))
    ps = doc["lectures"][n]["paragraphs"]
    table = json.loads(args.table.read_text(encoding="utf-8"))
    indices = [e["i"] for e in table]
    expected = {i for i, p in enumerate(ps) if not p.get("confirmed")}
    if len(indices) != len(set(indices)) or set(indices) != expected:
        print(f"FATAL: table coverage expected={len(expected)} actual={len(set(indices))} "
              f"missing={sorted(expected-set(indices))} extra={sorted(set(indices)-expected)}")
        return 2
    summary = {"lecture": int(n), "table": str(args.table), "baseline": str(args.baseline),
               "entries": len(table), "changed": 0, "over_2s": [], "zero_flips": []}
    for e in table:
        p = ps[e["i"]]
        delta = float(e["start"]) - p["start"]
        summary["changed"] += abs(delta) > .0005
        if abs(delta) > 2:
            summary["over_2s"].append({"i": e["i"], "old": p["start"], "new": e["start"]})
        if bool(p.get("zero")) != bool(e.get("zero", False)):
            summary["zero_flips"].append(e["i"])

    refine = load_module("sandbox_refine", GENERIC / "milli_refine.py")
    refine.AMAP_DIR = args.workdir
    hashes = []
    for run in (1, 2, 3):
        sys.argv = ["milli_refine.py", "--series", "liuzutanjing", "--lecture", n,
                    "--table", str(args.table), "--apply"]
        with (args.workdir / f"apply{run}.log").open("w", encoding="utf-8") as log:
            with contextlib.redirect_stdout(log):
                refine.main()
        hashes.append(sha(target))
    summary["apply_sha256"] = hashes
    if len(set(hashes)) != 1:
        print("FATAL: refiner 三次套用雜湊不一致（非冪等）")
        return 3

    audit = load_module("sandbox_structural", DEDICATED / "audit_alignment.py")
    audit.SO_T = target
    sys.argv = ["audit_alignment.py", "--baseline", str(args.baseline), "--lectures", n,
                "--out", str(args.workdir / "structural.json")]
    if args.require_clean:
        sys.argv.append("--require-clean")
    with (args.workdir / "structural.txt").open("w", encoding="utf-8") as log:
        with contextlib.redirect_stdout(log):
            structural_rc = audit.main()
    summary["structural_rc"] = structural_rc
    if structural_rc:
        print(f"FATAL: structural audit rc={structural_rc}；見 {args.workdir / 'structural.json'}")
        return 4

    seq = load_module("sandbox_seq", GENERIC / "seq_align.py")
    batch = load_module("sandbox_batch", GENERIC / "batch_verify.py")
    milli = load_module("sandbox_milli", GENERIC / "milli_audit.py")
    for label, amap in (("before", before_dir), ("after", args.workdir)):
        seq.AMAP_DIR = amap
        sys.argv = ["seq_align.py", "--series", "liuzutanjing", "--lecture", n,
                    "--mode", "metric", "--json", str(args.workdir / f"metric_{label}.json")]
        with (args.workdir / f"metric_{label}.txt").open("w", encoding="utf-8") as log:
            with contextlib.redirect_stdout(log):
                seq.main()
        summary[f"metric_{label}"] = metric_stats(
            json.loads((args.workdir / f"metric_{label}.json").read_text(encoding="utf-8")))
    batch.AMAP_DIR = args.workdir
    sys.argv = ["batch_verify.py", "--series", "liuzutanjing", "--lecture", n,
                "--json", str(args.workdir / "batch_after.json")]
    with (args.workdir / "batch_after.txt").open("w", encoding="utf-8") as log:
        with contextlib.redirect_stdout(log):
            batch.main()
    milli.AMAP_DIR = args.workdir
    sys.argv = ["milli_audit.py", "--series", "liuzutanjing", "--lecture", n,
                "--json", str(args.workdir / "milli_after.json")]
    with (args.workdir / "milli_after.txt").open("w", encoding="utf-8") as log:
        with contextlib.redirect_stdout(log):
            milli.main()
    summary["batch_suspects"] = json.loads((args.workdir / "batch_after.json").read_text(encoding="utf-8"))
    summary["ok"] = True
    out = args.workdir / "summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"VERDICT: PASS — L{n} sandbox entries={len(table)} changed={summary['changed']} "
          f"idempotent=3/3 structural=PASS")
    print(f"metric ±.3 {summary['metric_before'].get('within_03')}/{summary['metric_before'].get('n')} → "
          f"{summary['metric_after'].get('within_03')}/{summary['metric_after'].get('n')}；"
          f"±.7 {summary['metric_before'].get('within_07')}/{summary['metric_before'].get('n')} → "
          f"{summary['metric_after'].get('within_07')}/{summary['metric_after'].get('n')}")
    print(f"summary → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
