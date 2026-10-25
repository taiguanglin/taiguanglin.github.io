#!/usr/bin/env python3
"""qa_split_ebook 自制產出展開＋驗證（expand_classified）

把我在 build/self_classified/batch_NNN.compact 寫的緊湊分類
（格式：i|ch-L2-L3(-L4)|conf|rule[|flags]，flags：nr／d／ru=…）與可選的
batch_NNN.splits.jsonl（拆分行，含 q/a 切分文）展開成 gen_all.py 讀的
完整 build/classified/batch_NNN.jsonl，並驗證：
- 批次內每一則輸入恰好一行輸出（或一組拆分行），無缺漏
- path 必須命中 12 章樹的實際節點（嚴格）
更新 build/self_classified/progress.json。

用法：../../word_audio_map2/.venv/bin/python expand_classified.py 001 002 …（或 --all）
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "tool/qa_split_ebook/build"
SELF = BUILD / "self_classified"
CLS = BUILD / "classified"
CONF_MAP = {"h": "high", "m": "medium", "l": "low",
            "high": "high", "medium": "medium", "low": "low"}


def load_names():
    tree = json.loads((BUILD / "section_tree.json").read_text(encoding="utf-8"))
    names = {}
    for ch_s in sorted(tree):
        l2i = l3i = l4i = 0
        for e in tree[ch_s]["entries"]:
            if e["level"] == 2:
                l2i += 1; l3i = l4i = 0
                names[f"{ch_s}-{l2i:02d}"] = (int(ch_s), l2i, None, None, e["name"])
            elif e["level"] == 3:
                l3i += 1; l4i = 0
                names[f"{ch_s}-{l2i:02d}-{l3i:02d}"] = (int(ch_s), l2i, l3i, None, e["name"])
            else:
                l4i += 1
                names[f"{ch_s}-{l2i:02d}-{l3i:02d}-{l4i:02d}"] = (int(ch_s), l2i, l3i, l4i, e["name"])
    return names


def expand(batch_no: str, names: dict):
    src = BUILD / "batches" / f"batch_{batch_no}.jsonl"
    comp_f = SELF / f"batch_{batch_no}.compact"
    splits_f = SELF / f"batch_{batch_no}.splits.jsonl"
    if not comp_f.exists():
        return None, f"compact 缺檔 batch_{batch_no}"
    inputs = {}
    for line in src.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            inputs[d["i"]] = d["qid"]
    split_rows = {}
    if splits_f.exists():
        for line in splits_f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            split_rows.setdefault(r["i"], []).append(r)
    covered = {}
    errors, rows_out = [], []
    for line in comp_f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 4:
            errors.append(f"格式不良：{line[:60]}")
            continue
        i, path, conf, rule = parts[0], parts[1], parts[2], parts[3]
        flags = parts[4:] if len(parts) > 4 else []
        i = int(i)
        if i not in inputs:
            errors.append(f"i={i} 不屬於此批次")
            continue
        if i in covered:
            errors.append(f"i={i} 重複輸出")
            continue
        if i in split_rows:
            errors.append(f"i={i} 同時出現在 compact 與 splits")
            continue
        if path not in names:
            errors.append(f"i={i} path={path} 不在樹中")
            continue
        ch, l2, l3, l4, name = names[path]
        conf_full = CONF_MAP.get(conf)
        if not conf_full:
            errors.append(f"i={i} conf={conf} 無效")
            continue
        ru = None
        nr = conf_full == "low"
        deferred = False
        for fl in flags:
            if fl == "nr":
                nr = True
            elif fl == "d":
                deferred = True
            elif fl.startswith("ru="):
                ru = fl[3:]
                if ru not in names:
                    errors.append(f"i={i} runner_up={ru} 不在樹中")
        covered[i] = True
        rows_out.append({"i": i, "qid": inputs[i], "sub": 0, "split": False,
                         "ch": ch, "l2": l2, "l2n": names[f"{ch:02d}-{l2:02d}"][4],
                         "l3": l3, "l3n": (names[f"{ch:02d}-{l2:02d}-{l3:02d}"][4] if l3 else None),
                         "l4": l4, "l4n": (names[f"{ch:02d}-{l2:02d}-{l3:02d}-{l4:02d}"][4] if l4 else None),
                         "conf": conf_full, "rule": rule, "ru": ru, "nr": nr,
                         "deferred": deferred})
    for i, srows in split_rows.items():
        if i not in inputs:
            errors.append(f"splits i={i} 不屬於此批次")
            continue
        if i in covered:
            continue
        subs = sorted(srows, key=lambda r: r.get("sub") or 0)
        for k, r in enumerate(subs, start=1):
            if r.get("sub") != k:
                errors.append(f"i={i} splits sub 不連續")
                break
            path = r.get("path")
            if path not in names:
                errors.append(f"i={i} splits path={path} 不在樹中")
                break
            ch, l2, l3, l4, _ = names[path]
            conf_full = CONF_MAP.get(r.get("conf", "m"), "medium")
            covered[i] = True
            rows_out.append({"i": i, "qid": inputs[i], "sub": k, "split": True,
                             "ch": ch, "l2": l2, "l2n": names[f"{ch:02d}-{l2:02d}"][4],
                             "l3": l3, "l3n": (names[f"{ch:02d}-{l2:02d}-{l3:02d}"][4] if l3 else None),
                             "l4": l4, "l4n": (names[f"{ch:02d}-{l2:02d}-{l3:02d}-{l4:02d}"][4] if l4 else None),
                             "conf": conf_full, "rule": r.get("rule", ""),
                             "ru": r.get("ru"), "nr": bool(r.get("nr")) or conf_full == "low",
                             "deferred": bool(r.get("deferred")),
                             "q": r.get("q"), "a": r.get("a")})
    missing = [i for i in inputs if i not in covered]
    if missing:
        errors.append(f"缺 {len(missing)} 則：{missing[:12]}{'…' if len(missing) > 12 else ''}")
    if errors:
        return None, "；".join(errors[:12])
    rows_out.sort(key=lambda r: (r["i"], r["sub"]))
    out = CLS / f"batch_{batch_no}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in rows_out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ns = sum(1 for r in rows_out if not r["split"])
    sp = len(rows_out) - ns
    nrn = sum(1 for r in rows_out if r["nr"])
    return {"batch": batch_no, "in": len(inputs), "out": len(rows_out),
            "split": len(split_rows), "nr": nrn,
            "low": sum(1 for r in rows_out if r["conf"] == "low")}, None


def main():
    names = load_names()
    CLS.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args == ["--all"]:
        args = [f.name.split("_")[1].split(".")[0]
                for f in (BUILD / "batches").glob("batch_*.jsonl")]
    done, failed = [], []
    for b in sorted(args):
        res, err = expand(b, names)
        if res:
            done.append(res)
            print(f"[expand] batch_{b}: in={res['in']} out={res['out']} "
                  f"split={res['split']} nr={res['nr']} low={res['low']}")
        else:
            failed.append(b)
            print(f"[expand] batch_{b} ✗ {err}")
    (SELF / "progress.json").write_text(json.dumps(
        {"done": [d["batch"] for d in done], "failed": failed},
        ensure_ascii=False, indent=1), encoding="utf-8")
    rem = 47 - len(done)
    print(f"[expand] 完成 {len(done)} 批，剩 {rem} 批")


if __name__ == "__main__":
    main()
