#!/usr/bin/env python3
"""【一次性資料修訂】把 2025-09-01 貼吧的第 4、5 段合併成一則。

背景
----
【2026-10-26 註記】audio_map 的 SoT 已收斂為站台根目錄 `audio_map/`
單一副本（`tool/word2ebook/data/audio_map/` 已移除）。本腳本當時的
「SoT＋UI 副本」雙路徑寫法僅為歷史紀錄，**勿再執行**。

來源 PDF 已由 `tool/fix_20250901_sunhong_merge.py` 合併（同一提問者的兩則提問，
師父只作一個回答）。本腳本把同一語意同步到：

1. `tool/word2ebook/data/audio_map/2025-09.json`（映射 SoT）
2. `audio_map/2025-09.json`（校稿 UI 副本）
3. `audio_map/qid_to_sep_chapter.json`（分類版 qid → 章節／答案元素對照）
4. `tool/qa_split_ebook/classified/batch_015.jsonl`（分類結果的 qid）

合併規則
--------
* 保留第 4 段的 qid（`question-7407d44bb3e2`；PDF 解析器的 qid 取提問文字前綴，
  合併後前綴不變）與提問時間（第一則提問的時間）。
* 提問文字＝第 4 段 ＋ 第 5 段；答案＝第 5 段（原本唯一的答案）。
* 時間＝第 5 段（`start == end` 的第 4 段時間本來就是錯的）。
* 刪除第 5 段後，後續段的 `index` 與 `stable_key` 末段序號順減 1，
  與合併後 PDF 解析出的段序一致。

用法：tool/word_audio_map2/.venv/bin/python tool/pdf_audio_map/merge_20250901_sunhong.py
腳本可重複執行（已合併時會略過）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_ID = "2025-09-01-tieba"
QID_OLD = "question-5e9975bc5d5b"   # 第二則提問（合併後消失）
QID_NEW = "question-7407d44bb3e2"   # 合併後保留的 qid
ANSWER_ID = "answer-242cafd439ed"

MAP_PATHS = [
    REPO_ROOT / "tool" / "word2ebook" / "data" / "audio_map" / "2025-09.json",
    REPO_ROOT / "audio_map" / "2025-09.json",
]
QID_MAP_PATH = REPO_ROOT / "audio_map" / "qid_to_sep_chapter.json"
CLASSIFIED_PATHS = [
    REPO_ROOT / "tool" / "qa_split_ebook" / "classified" / "batch_015.jsonl",
    REPO_ROOT / "tool" / "qa_split_ebook" / "build" / "classified" / "batch_015.jsonl",
]


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  updated {path.relative_to(REPO_ROOT)}")


def merge_map(path: Path) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    session = next((s for s in data.get("sessions", []) if s.get("session_id") == SESSION_ID), None)
    if session is None:
        raise RuntimeError(f"{path}: 找不到 session {SESSION_ID}")

    segments = session["segments"]
    old_ids = [s.get("question_id") for s in segments]
    if QID_OLD not in old_ids:
        print(f"  skip {path.relative_to(REPO_ROOT)}: 已合併（找不到 {QID_OLD}）")
        return False
    if QID_NEW not in old_ids:
        raise RuntimeError(f"{path}: 找不到 {QID_NEW}")

    i_new = old_ids.index(QID_NEW)
    i_old = old_ids.index(QID_OLD)
    if i_old != i_new + 1:
        raise RuntimeError(f"{path}: 兩段不相鄰（{i_new}, {i_old}），已中止")

    seg_new = segments[i_new]
    seg_old = segments[i_old]

    q_text = (seg_new.get("q_text") or "").rstrip()
    q_text += "\n" + (seg_old.get("q_text") or "").lstrip()
    seg_new["q_text"] = q_text
    seg_new["q_preview"] = q_text if len(q_text) <= 180 else q_text[:180]

    answer_text = seg_old.get("answer_text") or seg_new.get("answer_text") or ""
    seg_new["answer_text"] = answer_text
    seg_new["answer_preview"] = seg_old.get("answer_preview") or seg_new.get("answer_preview") or ""
    seg_new["srt_preview"] = seg_old.get("srt_preview") or seg_new.get("srt_preview") or ""

    seg_new["start"] = seg_old.get("start")
    seg_new["end"] = seg_old.get("end")
    seg_new["start_label"] = seg_old.get("start_label")
    seg_new["end_label"] = seg_old.get("end_label")
    seg_new["confidence"] = seg_old.get("confidence", seg_new.get("confidence"))
    notes = seg_old.get("notes") or seg_new.get("notes") or ""
    if "merged-q4-q5" not in notes:
        seg_new["notes"] = (notes + "|merged-q4-q5-teacher-answered-together").strip("|")
    seg_new["meta"] = seg_old.get("meta") or seg_new.get("meta") or {}

    segments.pop(i_old)
    for pos, seg in enumerate(segments, start=1):
        seg["index"] = pos
        key = seg.get("stable_key")
        if isinstance(key, str) and key.rsplit("|", 1)[-1].isdigit():
            head = key.rsplit("|", 1)[0]
            seg["stable_key"] = f"{head}|{pos}"

    stats = data.get("stats")
    if isinstance(stats, dict) and isinstance(stats.get("matched"), int):
        stats["matched"] = max(0, stats["matched"] - 1)

    _write_json(path, data)
    return True


def update_qid_map(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for name, value in (("chapters", 7), ("aids", ANSWER_ID)):
        table = data.get(name)
        if not isinstance(table, dict):
            continue
        if QID_OLD in table:
            table.pop(QID_OLD)
            table[QID_NEW] = value
            changed = True
    if not changed:
        print(f"  skip {path.relative_to(REPO_ROOT)}: qid 對照已是合併後狀態")
        return
    _write_json(path, data)


def update_classified(path: Path) -> None:
    if not path.exists():
        print(f"  skip {path.relative_to(REPO_ROOT)}: 不存在")
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    out = []
    for line in lines:
        if not line.strip():
            out.append(line)
            continue
        row = json.loads(line)
        if row.get("qid") == QID_OLD:
            row["qid"] = QID_NEW
            changed = True
        out.append(json.dumps(row, ensure_ascii=False))
    if not changed:
        print(f"  skip {path.relative_to(REPO_ROOT)}: 找不到 {QID_OLD}")
        return
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"  updated {path.relative_to(REPO_ROOT)}")


def main() -> int:
    print("[merge-20250901] 合併 2025-09-01 貼吧第 4、5 段")
    for path in MAP_PATHS:
        merge_map(path)
    update_qid_map(QID_MAP_PATH)
    for path in CLASSIFIED_PATHS:
        update_classified(path)
    print("[merge-20250901] 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
