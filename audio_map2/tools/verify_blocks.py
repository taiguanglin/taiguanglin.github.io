#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RESEG_LEDGER 34 段 → wenda2_ebook block 對應逐段檢查（ledger 檢查 2）。

對每一段驗證：
  1. chapter_question_ids 的每個 qid 都存在於 html_qa_simp.json，且 block 的
     chapter 章號 ∈ chapter_indexes。
  2. chapter_answer_ids 涵蓋每個 qid 對應 block 的 answer_id。
  3. 文字比對：seg(q_text/answer_text) vs block(question-text/answer-text)
     （kept-stream＋著→着摺疊，同 item_align.py）；不同時印 dq/da 與差異摘要。
  4. 注入閘門：meta.lastPlayed 有無＋start!=null → 重建後播放鈕是否會出現。

用法:
    tool/word_audio_map2/.venv/bin/python audio_map2/tools/verify_blocks.py
"""
from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "word_audio_map2"))
import split_missing_subquestions as sms  # noqa: E402

HTML_QA = json.loads((ROOT / "tool" / "word_audio_map2/build/html_qa_simp.json")
                     .read_text(encoding="utf-8"))

# extract_html_qa.py 的 BLOCK_RE 不含 `-2` 後綴 answer id（如 answer-77a986a7e6ae-2），
# 這種 block 會掉進 html_qa_issues.json。對這類 qid 直接解析 HTML 取配對。
import html as htmlmod  # noqa: E402

def _direct_block(qid: str):
    for ch in range(1, 13):
        p = ROOT / "wenda2_ebook" / f"{ch:02d}.html"
        raw = p.read_text(encoding="utf-8")
        i = raw.find(f'id="{qid}"')
        if i < 0:
            continue
        m = re.search(r'<div class="question-text">(.*?)</div>', raw[i:], re.S)
        qtext = htmlmod.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
        # 配對：同 article 內其後第一個 answer div（允許 -2 後綴）
        ma = re.search(r'<div class="answer" id="(answer-[0-9a-f]+(?:-2)?)">', raw[i:])
        aid = ma.group(1) if ma else ""
        m2 = re.search(r'<div class="answer-text">(.*?)</div>', raw[i + (ma.end() if ma else 0):], re.S) if ma else None
        atext = htmlmod.unescape(re.sub(r"<[^>]+>", "", m2.group(1))).strip() if m2 else ""
        return {"chapter": ch, "q_text": qtext, "answer_id": aid, "a_text": atext}
    return None

# ledger 主表 34 段（session → now index 清單）
CASES = {
    "2024-03": {"2024-03-02-main": [48], "2024-03-26-main": [32, 33, 34],
                "2024-03-28-main": [9]},
    "2024-04": {"2024-04-25-main": [18, 19, 20]},
    "2024-07": {"2024-07-15-main": [34, 35], "2024-07-17-main": [8, 9, 10]},
    "2024-08": {"2024-08-17-main": [15, 16]},
    "2024-09": {"2024-09-09-main": [14, 15], "2024-09-10-main": [23, 24],
                "2024-09-14-main": [45, 46, 47, 48]},
    "2024-11": {"2024-11-16-main": [2, 3, 4, 5, 6]},
    "2025-01": {"2025-01-17-wechat": [1, 2]},
    "2025-03": {"2025-03-11-tieba": [6, 7], "2025-03-15-tieba": [27, 29]},
}


def ks(s: str) -> str:
    """kept stream＋著→着摺疊（同 item_align.py）。"""
    return sms.kept_stream(s or "")[0].replace("著", "着")


def diff_summary(a: str, b: str) -> str:
    """difflib 找出 a 有 b 無 / b 有 a 無的代表性片段。"""
    sm = SequenceMatcher(None, a, b, autojunk=False)
    a_only, b_only = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "delete":
            a_only.append(a[i1:i2])
        elif tag == "insert":
            b_only.append(b[j1:j2])
        elif tag == "replace":
            a_only.append(a[i1:i2])
            b_only.append(b[j1:j2])
    fa = "…".join(x[:24] for x in a_only[:2])
    fb = "…".join(x[:24] for x in b_only[:2])
    return f"seg獨有[{fa}] block獨有[{fb}]"


def main() -> int:
    problems, infos = [], []
    for month, sessions in CASES.items():
        d = json.loads((ROOT / "audio_map2" / f"{month}.json").read_text(encoding="utf-8"))
        smap = {s["session_id"]: {g["index"]: g for g in s["segments"]}
                for s in d["sessions"]}
        for sid, idxs in sessions.items():
            for idx in idxs:
                seg = smap[sid][idx]
                tag = f"{sid}#{idx}"
                qids = seg.get("chapter_question_ids") or []
                aids = seg.get("chapter_answer_ids") or []
                chs = seg.get("chapter_indexes") or []
                if not qids:
                    problems.append(f"{tag} 無 chapter_question_ids")
                    continue
                for qid in qids:
                    h = HTML_QA.get(qid)
                    if h is None:
                        h = _direct_block(qid)  # -2 後綴等抽取器配不到的 block
                    if h is None:
                        problems.append(f"{tag} qid {qid} 不存在於 wenda2_ebook")
                        continue
                    if h["chapter"] not in chs:
                        problems.append(f"{tag} qid {qid} 在第 {h['chapter']} 章，"
                                        f"但 chapter_indexes={chs}")
                    if h["answer_id"] not in aids:
                        problems.append(f"{tag} block answer_id {h['answer_id']}"
                                        f" 不在 chapter_answer_ids={aids}")
                    sq, sa = ks(seg.get("q_text")), ks(seg.get("answer_text"))
                    bq, ba = ks(h["q_text"]), ks(h["a_text"])
                    dq, da = len(sq) - len(bq), len(sa) - len(ba)
                    if dq == 0 and da == 0:
                        infos.append(f"{tag} {qid} 文字 EXACT（q{len(sq)}/a{len(sa)}）")
                    else:
                        line = (f"{tag} {qid} 差異 dq={dq:+d} da={da:+d}：")
                        if dq:
                            line += " Q " + diff_summary(sq, bq) + "；"
                        if da:
                            line += " A " + diff_summary(sa, ba)
                        infos.append(line)
                gate = bool((seg.get("meta") or {}).get("lastPlayed")) and \
                    seg.get("start") is not None
                infos.append(f"{tag} 注入閘門：{'開（重建後有鈕）' if gate else '待複聽（無 lastPlayed，鈕不會出現）'}"
                             f"｜窗 {seg.get('start')}→{seg.get('end')}")
    print("=" * 72)
    for i in infos:
        print(" ", i)
    if problems:
        print(f"PROBLEMS ({len(problems)}):")
        for p in problems:
            print(" ✗", p)
        return 1
    print("block 對應全部通過（差異列見上方 infos）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
