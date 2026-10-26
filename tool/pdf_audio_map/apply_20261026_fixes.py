#!/usr/bin/env python3
"""【一次性資料修訂】2026-10-26 兩項使用者指示：

1. 2025-07-07 貼吧 #38「一千萬彩票」交錯作答 → 兩段式播放
   ----------------------------------------------------------
   師父先答 #38 的前半（4406.59–4451.31），接著先回答 #39（盤古／女媧，
   4451.31–4469.53），再回頭補完 #38（「再呃再回到這一千萬的問題啊…
   曾經我也有過這樣的想法…」，4473.110–4530.760）。SRT 逐字佐證：
   cue 4473.110「再呃再回到这个一千万的问题啊」起、4527.140–4530.760
   「这对人的修行也是有帮助的啊」止（#40 自 4530.760 起）。

   處理（比照 audio_map2 2024-03-26 唐偉 two_part_group 先例）：
   * #38 加 `parts` = [[4406.59, 4451.31], [4473.11, 4530.76]]，
     注入器據此發 `data-segments`，播放鈕兩段式連播。
   * #38/#39 的 notes 加註，方便未來辨識這是特殊情況。
   * #39 的範圍刻意不切開（維持「段 i end == 段 i+1 start」鏈不變）。

2. 2025-07-12 貼吧 #10「苏小雅Helen」師父跳過 → 徹底刪除
   --------------------------------------------------------
   PDF 標「无回答」；音檔只有「下一个问题，苏小雅Helen啊，」
   （506.63–510.44，SRT cue 507.250–510.440），師父接著直接回答下一題
   （510.460「你可以那么理解啊，」＝多杰扎西2007 的答案開頭）。
   使用者指示：沒回答的提問不應出現在問答錄裡。

   處理（PDF 來源檔已由 `tool/fix_20250712_suxiaoya_remove.py` 刪卡）：
   * 刪除映射段（qid question-5bfed135e642）。
   * 提示語 2.5 秒依資料集慣例歸 #9 段尾：#9.end 與下一段 start
     同步移到 510.44（cue 邊界，鏈保持連續）。
   * 後續段 index／stable_key 末段序號順減 1（與刪卡後 PDF 解析一致）。
   * `qid_to_sep_chapter.json`、`audio_dates_supplement.json` 移除該 qid。
   * 分類資料列（classified/batch_010.jsonl）由
     `tool/qa_split_ebook/realign_classified_seq.py` 另行處理
     （刪卡使 items seq 全體後移，分類行須以 qid 重對位）。

用法：tool/word_audio_map2/.venv/bin/python tool/pdf_audio_map/apply_20261026_fixes.py
腳本可重複執行（已套用時會略過）。--check 只顯示將做的事。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SESSION_TWOPART = "2025-07-07-tieba"
QID_TWOPART = "question-738a5527115f"
QID_NEXT = "question-e59ae93fd61c"
PARTS = [[4406.59, 4451.31], [4473.11, 4530.76]]
NOTE_TWOPART = (
    "two-part-playback:師父先答 #39（4451.31–4469.53）再回頭補完本題；"
    "part2=4473.110–4530.760 經 data-segments 兩段式連播"
    "（比照 audio_map2 2024-03-26 唐偉 two_part_group 先例）"
)
NOTE_NEXT = (
    "interleaved-answer:4473.110–4530.760 為 #38 的補答（#38 以兩段式播放涵蓋），"
    "本段範圍刻意不切開以維持鏈連續"
)

SESSION_REMOVE = "2025-07-12-tieba"
QID_REMOVE = "question-5bfed135e642"
BOUNDARY = 510.44            # cue 4473... 之外的蘇小雅提示語尾＝多杰扎西答案前的 cue 邊界
BOUNDARY_LABEL = "00:08:30.440"
NOTE_ABSORB = (
    "removed-next-card-20260712:下一段（苏小雅Helen，師父未答、PDF 標「无回答」）"
    "已依使用者指示徹底刪除；其提示語「下一个问题，苏小雅Helen啊，」"
    "506.63–510.44 依慣例歸本段尾，end 507.25→510.44"
)
NOTE_SHIFT = (
    "start 509.785→510.44:前一段（苏小雅Helen，師父未答）已刪除，"
    "邊界移至「你可以那么理解啊」cue 起（510.460），鏈保持連續"
)

MAP_PATHS = [
    REPO_ROOT / "audio_map" / "2025-07.json",
]
QID_MAP_PATH = REPO_ROOT / "audio_map" / "qid_to_sep_chapter.json"
DATES_PATH = REPO_ROOT / "tool" / "word2ebook" / "data" / "audio_dates_supplement.json"


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  updated {path.relative_to(REPO_ROOT)}")


def _session(data: dict, session_id: str) -> dict:
    s = next((x for x in data.get("sessions", []) if x.get("session_id") == session_id), None)
    if s is None:
        raise RuntimeError(f"找不到 session {session_id}")
    return s


def _seg(session: dict, qid: str) -> tuple[int, dict]:
    for i, seg in enumerate(session["segments"]):
        if seg.get("question_id") == qid:
            return i, seg
    return -1, {}


def _append_note(seg: dict, note: str, marker: str) -> None:
    notes = seg.get("notes") or ""
    if marker in notes:
        return
    seg["notes"] = (notes + " | " + note).strip(" |") if notes else note


def fix_two_part(path: Path, check: bool) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    session = _session(data, SESSION_TWOPART)
    i38, seg38 = _seg(session, QID_TWOPART)
    if i38 < 0:
        print(f"  skip {path.relative_to(REPO_ROOT)}: 找不到 #38（已套用？）")
        return
    if seg38.get("parts") == PARTS:
        print(f"  skip {path.relative_to(REPO_ROOT)}: #38 parts 已套用")
        return
    _, seg39 = _seg(session, QID_NEXT)
    if not seg39:
        raise RuntimeError("找不到 #39")
    print(f"  {path.relative_to(REPO_ROOT)}: #38 加 parts={PARTS}")
    if check:
        return
    # 插在 end_label 之後，鍵序與其他數值欄一致
    out = {}
    for k, v in seg38.items():
        out[k] = v
        if k == "end_label":
            out["parts"] = PARTS
    seg38.clear()
    seg38.update(out)
    _append_note(seg38, NOTE_TWOPART, "two-part-playback")
    _append_note(seg39, NOTE_NEXT, "interleaved-answer")
    _write_json(path, data)


def fix_remove(path: Path, check: bool) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    session = _session(data, SESSION_REMOVE)
    i_rm, seg_rm = _seg(session, QID_REMOVE)
    if i_rm < 0:
        print(f"  skip {path.relative_to(REPO_ROOT)}: 蘇小雅段已刪除")
        return
    if seg_rm.get("index") != 10:
        raise RuntimeError(f"預期 index 10，實際 {seg_rm.get('index')}")
    print(f"  {path.relative_to(REPO_ROOT)}: 刪除 #10 蘇小雅段＋重編號＋邊界 510.44")
    if check:
        return
    segments = session["segments"]
    # 邊界：#9.end → 510.44（吸收提示語）；刪除後的第一段 start → 510.44
    seg9 = next(s for s in segments if s.get("index") == 9)
    if seg9["end"] != BOUNDARY:
        seg9["end"] = BOUNDARY
        seg9["end_label"] = BOUNDARY_LABEL
        _append_note(seg9, NOTE_ABSORB, "removed-next-card-20260712")
    nxt = next(s for s in segments if s.get("index") == 11)
    if nxt["start"] != BOUNDARY:
        nxt["start"] = BOUNDARY
        nxt["start_label"] = BOUNDARY_LABEL
        _append_note(nxt, NOTE_SHIFT, "start 509.785→510.44")
    segments.pop(i_rm)
    for pos, seg in enumerate(segments, start=1):
        seg["index"] = pos
        key = seg.get("stable_key")
        if isinstance(key, str) and key.rsplit("|", 1)[-1].isdigit():
            seg["stable_key"] = f"{key.rsplit('|', 1)[0]}|{pos}"
    stats = data.get("stats")
    if isinstance(stats, dict) and isinstance(stats.get("matched"), int):
        stats["matched"] = max(0, stats["matched"] - 1)
    _write_json(path, data)


def fix_qid_map(check: bool) -> None:
    data = json.loads(QID_MAP_PATH.read_text(encoding="utf-8"))
    changed = False
    for name in ("chapters", "aids"):
        table = data.get(name)
        if isinstance(table, dict) and QID_REMOVE in table:
            print(f"  qid_to_sep_chapter.json: 移除 {name}[{QID_REMOVE}] = {table[QID_REMOVE]}")
            if not check:
                table.pop(QID_REMOVE)
                changed = True
    if changed:
        _write_json(QID_MAP_PATH, data)
    elif not check:
        print("  skip qid_to_sep_chapter.json: 蘇小雅 qid 已移除")


def fix_dates(check: bool) -> None:
    data = json.loads(DATES_PATH.read_text(encoding="utf-8"))
    dates = data.get("dates", {})
    if QID_REMOVE not in dates:
        print("  skip audio_dates_supplement.json: 蘇小雅 qid 已移除")
        return
    print(f"  audio_dates_supplement.json: 移除 dates[{QID_REMOVE}] = {dates[QID_REMOVE]}")
    if not check:
        dates.pop(QID_REMOVE)
        _write_json(DATES_PATH, data)


def main() -> int:
    ap = argparse.ArgumentParser(description="2026-10-26 映射資料修訂")
    ap.add_argument("--check", action="store_true", help="只顯示將做的事，不修改")
    args = ap.parse_args()
    print("[apply-20261026] 開始（--check）" if args.check else "[apply-20261026] 開始")
    for path in MAP_PATHS:
        fix_two_part(path, args.check)
    for path in MAP_PATHS:
        fix_remove(path, args.check)
    fix_qid_map(args.check)
    fix_dates(args.check)
    print("[apply-20261026] 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
