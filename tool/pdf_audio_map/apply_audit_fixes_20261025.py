#!/usr/bin/env python3
"""【2026-10-25 全量稽核】套用逐段稽核後確定可安全修正的項目。

【2026-10-26 註記】audio_map 的 SoT 已收斂為站台根目錄 `audio_map/`
單一副本（`tool/word2ebook/data/audio_map/` 已移除）。本腳本當時的
「UI → SoT 回寫」用途已不存在，僅為歷史紀錄，**勿再執行**。

修正項目（皆有 SRT 證據）：

1. SoT 落後：`audio_map/`（校稿 UI，使用者最新校對結果）與
   `tool/word2ebook/data/audio_map/`（canonical SoT）有 6 個月不一致，
   SoT 仍含舊的零長段、缺值段、缺 lastPlayed。→ 以 UI 副本回寫 SoT。

2. `2025-06-09-wechat` #18→#19 之間 12.705s 無人負責：該段是師父回答尾聲
   （SRT 1776.399–1789.4「但他就是该有的样子了 哈啊」，
    answer_text 末句即「那就是它该有的样子」）→ #18.end 延到 #19.start。

3. `2025-06-10-tieba` #27 end=2954.86 與 #28 start=2954.689 重疊 0.171s
   （下一題「下一个问题」cue 起點 2954.93）→ #28.start 對齊 #27.end。

4. 收場（closing）異常 4 個 session：
   - `2025-07-09-wechat`：無獨立收場語（PDF closing 文字為空）→ 明確標記
     `zero: true` + `no-spoken-session-close`。
   - `2026-01-07-guanwang`：SRT 有明確收場語「这个问题你的问题就回答到这里吧」
     （4761.4–4763.685），但被算在最後一段 → 切出為 closing，最後一段 end 收斂。
   - `2026-02-05-guanwang`：SRT 有收場語「好了啊／你的事就先说到这里吧哈」
     （2617.54–2619.995），但 closing 缺值 → 補上並串接最後一段。
   - `2026-02-07-guanwang`：確實沒有收場語 → 明確標記
     `zero: true` + `no-spoken-session-close`（原本 start/end 為 null）。

5. 各月頂層 `stats` 過時（matched/sessions/opening_ok/closing_ok/missing）→ 重算。

用法：tool/word_audio_map2/.venv/bin/python tool/pdf_audio_map/apply_audit_fixes_20261025.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "pdf_audio_map"))
from common import fmt_tc, parse_srt_raw, srt_preview  # noqa: E402

UI_DIR = ROOT / "audio_map"
SOT_DIR = ROOT / "tool" / "word2ebook" / "data" / "audio_map"
MONTHS = ["2025-06", "2025-07", "2025-08", "2025-09", "2025-11",
          "2025-12", "2026-01", "2026-02", "2026-03"]
# 只有這幾個月 UI 有較新的校對結果，需要回寫 SoT
SYNC_MONTHS = ["2025-06", "2025-07", "2025-11", "2026-01", "2026-02", "2026-03"]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_session(data: dict, sid: str) -> dict:
    for s in data["sessions"]:
        if s["session_id"] == sid:
            return s
    raise KeyError(sid)


def set_seg_end(seg: dict, end: float, cues) -> None:
    seg["end"] = round(float(end), 3)
    seg["end_label"] = fmt_tc(end)
    if cues is not None:
        seg["srt_preview"] = srt_preview(cues, seg["start"], seg["end"])


def set_seg_start(seg: dict, start: float, cues) -> None:
    seg["start"] = round(float(start), 3)
    seg["start_label"] = fmt_tc(start)
    if cues is not None:
        seg["srt_preview"] = srt_preview(cues, seg["start"], seg["end"])


def fix_2025_06(data: dict) -> list[str]:
    notes = []
    sess = get_session(data, "2025-06-09-wechat")
    cues = parse_srt_raw(Path(sess["srt_file"]))
    seg18 = next(s for s in sess["segments"] if s["index"] == 18)
    seg19 = next(s for s in sess["segments"] if s["index"] == 19)
    if abs(seg18["end"] - seg19["start"]) > 0.001:
        set_seg_end(seg18, seg19["start"], cues)
        notes.append(f"2025-06-09-wechat #18.end → {seg18['end']}（補上 12.705s 回答尾聲）")

    sess = get_session(data, "2025-06-10-tieba")
    cues = parse_srt_raw(Path(sess["srt_file"]))
    seg27 = next(s for s in sess["segments"] if s["index"] == 27)
    seg28 = next(s for s in sess["segments"] if s["index"] == 28)
    if abs(seg27["end"] - seg28["start"]) > 0.001:
        set_seg_start(seg28, seg27["end"], cues)
        notes.append(f"2025-06-10-tieba #28.start → {seg28['start']}（消除 0.171s 重疊）")

    # ⑤ `2025-06-13-tieba` #15 本身沒有回答（PDF 答案＝「上一回答里。」，
    #    SRT 該區只有 #16 的提問提示「然后嗯第六个问题…」）：
    #    #15 標記為「師父未念」（zero），#16 起點回到提問起點 1580.485。
    sess = get_session(data, "2025-06-13-tieba")
    cues = parse_srt_raw(Path(sess["srt_file"]))
    seg15 = next(s for s in sess["segments"] if s["index"] == 15)
    seg16 = next(s for s in sess["segments"] if s["index"] == 16)
    onset = 1580.485
    if not seg15.get("zero"):
        seg15.update({
            "start": round(float(seg15["start"]), 3),
            "end": round(onset, 3),
            "start_label": fmt_tc(seg15["start"]),
            "end_label": fmt_tc(onset),
            "zero": True,
            "notes": (seg15.get("notes") or "") + "|no-own-answer|answer-in-prev-question",
            "srt_preview": "",
        })
        notes.append("2025-06-13-tieba #15 → zero（師父未念，答案在上一題）")
    if abs(seg16["start"] - onset) > 0.001:
        set_seg_start(seg16, onset, cues)
        notes.append(f"2025-06-13-tieba #16.start → {seg16['start']}（接回第 6 題提示起點）")
    return notes


def fix_dec_2025(data: dict) -> list[str]:
    """2025-12-09-guanwang：#31 的補充回答（3381–3440）被算進 #32 的窗口。"""
    notes = []
    sess = get_session(data, "2025-12-09-guanwang")
    cues = parse_srt_raw(Path(sess["srt_file"]))
    seg31 = next(s for s in sess["segments"] if s["index"] == 31)
    seg32 = next(s for s in sess["segments"] if s["index"] == 32)
    boundary = 3442.09  # 「下一个这位冷咖啡的问题啊」cue 起點＝第 32 題真正起點
    if abs(seg31["end"] - boundary) > 0.001:
        set_seg_end(seg31, boundary, cues)
        set_seg_start(seg32, boundary, cues)
        notes.append(
            f"2025-12-09-guanwang #31.end / #32.start → {boundary}"
            "（把 3381–3440s 的補充回答歸回第 31 題）")
    return notes


def fix_closing(data: dict, month: str) -> list[str]:
    notes = []

    # ① 無獨立收場語 → 明確零音標記
    if month == "2025-07":
        sess = get_session(data, "2025-07-09-wechat")
        cl = sess["closing"]
        if not cl.get("zero"):
            cl["zero"] = True
            cl["notes"] = "no-spoken-session-close"
            cl["srt_preview"] = ""
            notes.append("2025-07-09-wechat closing → zero（無獨立收場語）")

    # ② 有收場語但混在最後一段 → 切出
    if month == "2026-01":
        sess = get_session(data, "2026-01-07-guanwang")
        cues = parse_srt_raw(Path(sess["srt_file"]))
        last = sess["segments"][-1]
        cl = sess["closing"]
        if cl.get("start") == cl.get("end") and cl.get("start") is not None:
            onset = 4761.4
            end = float(cues[-1][1])
            set_seg_end(last, onset, cues)
            cl.update({
                "start": round(onset, 3), "end": round(end, 3),
                "start_label": fmt_tc(onset), "end_label": fmt_tc(end),
                "confidence": 0.9, "status": "manual", "locked": False,
                "notes": "leadin:closing|manual-20261025",
                "srt_preview": srt_preview(cues, onset, end),
            })
            cl.pop("zero", None)
            notes.append(f"2026-01-07-guanwang closing → [{onset}, {end}]，最後一段 end → {onset}")

    # ③ closing 缺值但 SRT 有收場語 → 補上
    if month == "2026-02":
        sess = get_session(data, "2026-02-05-guanwang")
        cues = parse_srt_raw(Path(sess["srt_file"]))
        last = sess["segments"][-1]
        cl = sess["closing"]
        if cl.get("start") is None:
            onset = 2617.54
            end = float(cues[-1][1])
            set_seg_end(last, onset, cues)
            cl.update({
                "start": round(onset, 3), "end": round(end, 3),
                "start_label": fmt_tc(onset), "end_label": fmt_tc(end),
                "confidence": 0.9, "status": "manual", "locked": False,
                "notes": "leadin:closing|manual-20261025",
                "srt_preview": srt_preview(cues, onset, end),
            })
            notes.append(f"2026-02-05-guanwang closing → [{onset}, {end}]，最後一段 end → {onset}")

        # ④ 確實無收場語 → 明確零音標記（原 start/end 為 null）
        sess = get_session(data, "2026-02-07-guanwang")
        cl = sess["closing"]
        if cl.get("start") is None:
            last = sess["segments"][-1]
            pos = round(float(last["end"]), 3)
            cl.update({
                "start": pos, "end": pos,
                "start_label": fmt_tc(pos), "end_label": fmt_tc(pos),
                "confidence": 0.0, "status": "manual", "locked": False,
                "notes": "no-spoken-session-close", "srt_preview": "",
                "zero": True,
            })
            notes.append(f"2026-02-07-guanwang closing → zero（無收場語，標記於 {pos}）")
    return notes


def recompute_stats(data: dict) -> dict:
    stats = data.get("stats")
    if not isinstance(stats, dict):
        return {}
    sessions = data.get("sessions") or []
    seg_count = sum(len(s.get("segments") or []) for s in sessions)
    missing = sum(
        1 for s in sessions for seg in (s.get("segments") or [])
        if seg.get("start") is None or seg.get("end") is None
    )
    opening_ok = sum(
        1 for s in sessions
        if (s.get("opening") or {}).get("start") is not None
        and (s.get("opening") or {}).get("end") is not None
    )
    closing_ok = sum(
        1 for s in sessions
        if (s.get("closing") or {}).get("start") is not None
        and (s.get("closing") or {}).get("status") != "missing"
    )
    new = dict(stats)
    new.update({
        "matched": seg_count,
        "missing": missing,
        "opening_ok": opening_ok,
        "closing_ok": closing_ok,
        "sessions": len(sessions),
    })
    return new


def main() -> int:
    changed_months = []
    all_notes = []
    for month in MONTHS:
        ui_path = UI_DIR / f"{month}.json"
        data = load(ui_path)
        notes = []
        if month == "2025-06":
            notes += fix_2025_06(data)
        if month in ("2025-07", "2026-01", "2026-02"):
            notes += fix_closing(data, month)
        if month == "2025-12":
            notes += fix_dec_2025(data)
        new_stats = recompute_stats(data)
        if new_stats != data.get("stats"):
            old = data.get("stats") or {}
            diff = {k: (old.get(k), new_stats[k]) for k in new_stats if old.get(k) != new_stats[k]}
            data["stats"] = new_stats
            notes.append(f"stats 更新：{diff}")
        if notes:
            save(ui_path, data)
            changed_months.append(month)
            all_notes += [f"[{month}] {n}" for n in notes]
            print(f"[fix] {month}: " + "；".join(notes))

    # UI → canonical SoT 回寫（以使用者最新校對結果為準）
    for month in MONTHS:
        src = UI_DIR / f"{month}.json"
        dst = SOT_DIR / f"{month}.json"
        if not dst.exists():
            print(f"[fix] {month}: SoT 不存在，略過")
            continue
        if json.dumps(load(src), sort_keys=True) != json.dumps(load(dst), sort_keys=True):
            shutil_copy(src, dst)
            print(f"[fix] {month}: 已回寫 canonical SoT（tool/word2ebook/data/audio_map/）")

    print(f"\n[fix] 變更月份：{', '.join(changed_months) or '無'}")
    for n in all_notes:
        print("  -", n)
    return 0


def shutil_copy(src: Path, dst: Path) -> None:
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
