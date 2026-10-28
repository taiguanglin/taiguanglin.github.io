#!/usr/bin/env python3
"""2024-11-11-main#29「監獄」題：把黏在「師父說」收場句後的題幹搬回 q_text。

成因（Word 原文，全庫只此一處）
--------------------------------
`問答錄2/wenda2_250810_截止25年5月17日答疑_含图版.docx` 第 9519 段
（音檔對應用的 `問答錄2/2024-2025 TAI师父答疑汇总 - 截止2025年7月12日.docx`
第 22876 段，文字相同）逐字是：

    师父说：贴吧的问题到这里结束了，11月11号微信的问题，从这边显示的从下面开始回答。
    1、还有想问下在监狱的环境没有《地藏经》读，是让他每天念地藏王菩萨名号好，
    还是念阿弥陀佛好呢？ 主要是想让他以后能顺利往生。

→ `tool/word_audio_map2/build_maps.py` 把任何以「师父说」開頭的行判成 open/close
  marker，**整行剩餘文字都變成 closing.text** → 題幹被吞進收場句，原本沒有
  「監獄」這一題的段。2026-10-18 的 length-fix 才把原 #30 拆成 #29／#30，
  notes 寫「彙總只有答案 → q_text 依彙總留空」——那句不精確：題幹就在彙總裡，
  只是黏在收場句後面。

→ 拆出的 #29 因此長相很怪：`q_text` 空、`questioner`/`question_time` 沿用上一段
  貼吧題（離垢地 2024-09-17 05:08 的歡喜心題）。

本腳本只做「文字搬位」（字元多重集不變，只是從 closing 搬到 q_text）
--------------------------------------------------------------------
  - #29.q_text        ← 原 closing.text 裡的「1、還有想問下在監獄…」
  - #29.questioner    ← ''（Word 該題沒有姓名行；微信編號題沿用提問人是誤植）
  - #29.question_time ← '2024-11-11'（本場日期；Word 轉場句「11月11號微信的問題」）
  - #29.question_id   ← 依 build_maps.py 的 question_id() 重算（sha1(sid#index#q_text[:80])）
  - #29.q_preview     ← 重算
  - closing.text      ← 只留轉場句；closing.text_preview 重算
  - notes             ← 記錄本次文字修正

時間窗／start／end／confidence／status／meta.lastPlayed／章節對應
（chapter_question_ids／chapter_answer_ids／chapter_indexes）**一律不動**。

用法（預設 dry-run）：
    .venv/bin/python ../../audio_map2/tools/fix_2024_11_seg29_prison_q.py [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MONTH_JSON = ROOT / "audio_map2" / "2024-11.json"
SESSION_ID = "2024-11-11-main"
SEG_INDEX = 29

# 轉場句（closing.text 的前半段）與題幹起點的判別字串
TRANSITION = "贴吧的问题到这里结束了，11月11号微信的问题，从这边显示的从下面开始回答。"
QUESTION_MARK = "1、还有想问下在监狱的环境没有"


def question_id(session_id: str, index: int, q_text: str) -> str:
    """與 build_maps.py / apply_resplit.py / resplit_by_html.py 同式。"""
    h = hashlib.sha1(f"{session_id}#{index}#{q_text[:80]}".encode()).hexdigest()[:12]
    return f"question-{h}"


def preview(text: str, limit: int) -> str:
    return text[:limit] + ("…" if len(text) > limit else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    data = json.loads(MONTH_JSON.read_text(encoding="utf-8"))
    session = next(s for s in data["sessions"] if s["session_id"] == SESSION_ID)
    seg = next(s for s in session["segments"] if s["index"] == SEG_INDEX)
    closing = session["closing"]

    ctext = closing.get("text") or ""
    if TRANSITION not in ctext or QUESTION_MARK not in ctext:
        print(f"❌ closing.text 不符合預期形狀，未修改：{ctext[:80]!r}")
        return 1
    if seg.get("q_text"):
        print(f"ℹ️ #29.q_text 已有文字（{seg['q_text'][:40]!r}），不重複套用")
        return 0

    head, _, tail = ctext.partition(QUESTION_MARK)
    q_text = QUESTION_MARK + tail                      # 題幹（自 closing 搬過來）
    transition = head.rstrip()                          # 轉場句（含句號）

    before = {
        "closing.text": ctext,
        "#29.q_text": seg.get("q_text"),
        "#29.questioner": seg.get("questioner"),
        "#29.question_time": seg.get("question_time"),
        "#29.question_id": seg.get("question_id"),
        "start": seg.get("start"),
        "end": seg.get("end"),
        "lastPlayed": (seg.get("meta") or {}).get("lastPlayed"),
    }

    seg["q_text"] = q_text
    seg["questioner"] = ""
    seg["question_time"] = "2024-11-11"
    seg["question_id"] = question_id(SESSION_ID, SEG_INDEX, q_text)
    seg["q_preview"] = preview(q_text, 100)
    seg["notes"] = (
        (seg.get("notes") or "")
        + "｜2026-10-28 text-fix：題幹原黏在 closing 段（Word 第 9519 段／"
          "22876 段「师父说：…从下面开始回答。 1、还有想问下在监狱…」），build_maps.py "
          "把整行判成 close marker → 題幹被吞進 closing.text。現把題幹搬回 q_text、"
          "closing.text 只留轉場句（字元多重集不變）；questioner 清空（Word 無姓名行）、"
          "question_time 改本場日期 2024-11-11；question_id 依 question_id() 重算。"
          "start/end/confidence/status/lastPlayed/章節對應一律未動。"
    )

    closing["text"] = transition
    closing["text_preview"] = transition[:80]
    closing["notes"] = (
        (closing.get("notes") or "")
        + "｜2026-10-28 text-fix：closing.text 原本含「1、还有想问下在监狱…」題幹"
          "（與轉場白同一 Word 段），題幹已搬至 2024-11-11-main#29.q_text；"
          "本 closing 只留轉場白，start/end（釘在檔尾）不動。"
    )

    after = {
        "closing.text": closing["text"],
        "#29.q_text": seg["q_text"],
        "#29.questioner": seg["questioner"],
        "#29.question_time": seg["question_time"],
        "#29.question_id": seg["question_id"],
        "start": seg.get("start"),
        "end": seg.get("end"),
        "lastPlayed": (seg.get("meta") or {}).get("lastPlayed"),
    }

    print("── before ──")
    for k, v in before.items():
        print(f"  {k}: {v!r}")
    print("── after ──")
    for k, v in after.items():
        print(f"  {k}: {v!r}")

    # 字元守恆檢查（只搬位，不增刪）
    assert len(ctext) == len(transition) + len(q_text) + (len(head) - len(head.rstrip())), \
        "closing.text 拆解後字數對不上"
    assert seg["start"] == before["start"] and seg["end"] == before["end"], "時間窗被改動"
    assert (seg.get("meta") or {}).get("lastPlayed") == before["lastPlayed"], "lastPlayed 被改動"

    if args.apply:
        MONTH_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(f"✅ WRITTEN {MONTH_JSON}")
    else:
        print("(dry-run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
