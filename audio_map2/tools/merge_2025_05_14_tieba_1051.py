#!/usr/bin/env python3
"""One-off surgical fix: merge audio_map2/2025-05.json, 2025-05-14-tieba #20 + #21.

Word 解析器把同一個電子書問答塊（question-2d1611c48721：主問
「6、另外，师父12日的答疑是否遗漏了1051楼的问题？」＋括注的
「（以下为1051楼问题内容：…）」）拆成兩個段：

  - #20：只有主問（問：12日答疑是否漏了 1051 樓），answer_text 為空，
    span 只有 0.1s（2016.358–2016.458）—— 師父口頭只說
    「幺零五一楼的问题，我往上翻一翻看看吧」（約 2018.9–2023.2），
    並未逐字朗讀該問題；notes 已誠實記錄此狀態。
  - #21：問答本體，questioner 誤填為括注文字「（以下为1051楼问题内容」，
    start 與 #20 end 縫合（2016.458）。

電子書（04.html / 02.html）視之為「一個」問題塊、單一答案
（answer-36bb6bb5ad8d）；本 session 的 2025-05-14-wechat#11→#12 已用
merge_split_pairs.py 做過同型合併（notes 帶 merged:<shell_key> 標籤），
本腳本沿用同一套慣例：

  - 刪除殼段 #20（不重編號 —— index 誠實記錄移除，穩定鍵不變）
  - #21（merge 後成為該 session 唯一 20 號段）承接：
      questioner  = 貼吧用戶_QUDy8Na（殼段攜帶的真實提問人）
      question_time = 殼段的 2025-05-14 10:16
      start / start_label = 殼段的 2016.358（包絡）
      chapter_question_ids / chapter_indexes / chapter_answer_ids
        = 殼段的（指向 question-2d1611c48721 / answer-36bb6bb5ad8d）
      html_verbatim = true（合併後即為電子書塊的逐字內容）
  - 時間：保留 #21 自己的 start/end（2016.458–2254.3，已聽檔校對）；殼段
    的 0.1s span 是拆分殘留的假邊界，不併入包絡（其起點反而落在前段
    #19 的已校對區間內）。
  - meta：保留 #21 自己的 lastPlayed/lastEdited（實際聽到答案本體的時間）；
    殼段的 lastPlayed 記錄併入 notes 溯源（note 僅寫入 notes，文字欄位不動）。
  - 重算頂層 stats。
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MAP = HERE / "2025-05.json"

SESSION = "2025-05-14-tieba"
SHELL_KEY = f"{SESSION}#20"
CONTENT_KEY = f"{SESSION}#21"
MERGE_TAG = f"merged:{SHELL_KEY}"


def recompute_stats(d):
    st = {"sessions": 0, "segments": 0, "matched": 0, "low_conf": 0, "interpolated": 0,
          "pending": 0, "missing": 0, "openings_ok": 0, "closings_ok": 0}
    for s in d['sessions']:
        st['sessions'] += 1
        st['segments'] += len(s['segments'])
        for seg in s['segments']:
            if seg.get('start') is None:
                st['missing'] += 1
            else:
                st['matched'] += 1
                if (seg.get('confidence') or 0) < 0.5:
                    st['low_conf'] += 1
                if 'interpolated' in (seg.get('notes') or ''):
                    st['interpolated'] += 1
                if 'no-anchor:clamped' in (seg.get('notes') or '') or '待人工' in (seg.get('notes') or ''):
                    st['pending'] += 1
        if s.get('opening') is not None and s['opening'].get('start') is not None:
            st['openings_ok'] += 1
        if s.get('closing') is not None and s['closing'].get('start') is not None:
            st['closings_ok'] += 1
    return st


def main() -> int:
    d = json.loads(MAP.read_text(encoding="utf-8"))
    sess = next(s for s in d["sessions"] if s["session_id"] == SESSION)
    segs = sess["segments"]

    def find(key):
        return next((i for i, s in enumerate(segs) if s.get("stable_key") == key), None)

    si = find(SHELL_KEY)
    if si is None:
        # 幂等重跑：殼已併入
        content = segs[find(CONTENT_KEY)]
        assert MERGE_TAG in (content.get("notes") or ""), \
            f"{SHELL_KEY}: shell gone but content not previously merged"
        print(f"skip {SHELL_KEY} (already merged)")
        return 0
    assert si + 1 == find(CONTENT_KEY), "shell/content not adjacent"
    shell, content = segs[si], segs[si + 1]

    assert not (shell.get("answer_text") or "").strip(), \
        f"{SHELL_KEY}: shell unexpectedly has answer_text"
    q_shell = (shell.get("questioner") or "").strip()
    assert q_shell and not q_shell.startswith("（"), \
        f"{SHELL_KEY}: unexpected shell questioner {q_shell!r}"
    pseudo_q = (content.get("questioner") or "").strip()
    assert pseudo_q.startswith("（"), f"{CONTENT_KEY}: unexpected pseudo questioner {pseudo_q!r}"
    assert not (content.get("chapter_question_ids") or []), \
        f"{CONTENT_KEY}: content already carries chapter ids"

    # ---- 重組問題文字：回復 docx 原始單一問題塊 ----
    # docx 原文（同一塊）：主問 + 「（以下为1051楼问题内容：」 + 引述內容 + 「）」
    # 解析器把後半切成 questioner=（以下为1051楼问题内容 / q_text=引述內容；
    # 合併時照 docx 順序接回（\n 對應電子書 <br/>），answer_text 不動。
    merged_q = (shell.get("q_text") or "").strip() + "\n" + pseudo_q + "：\n" \
        + (content.get("q_text") or "").strip()
    content["q_text"] = merged_q
    content["q_preview"] = merged_q[:100] + ("…" if len(merged_q) > 100 else "")

    # ---- 元資料：只搬殼段的到 content ----
    # 時間：沿用 merge_split_pairs.py「keep the content segment's span」—— 殼段
    # 的 0.1s span（2016.358–2016.458）是拆分殘留的假邊界（且起點戳進
    # #19 的已校對區間內），不採用；content 自己的 start/end（使用者
    # 已聽檔校對過）保持不動。
    content["questioner"] = q_shell
    if shell.get("question_time") and not content.get("question_time"):
        content["question_time"] = shell["question_time"]
    for k in ("chapter_question_ids", "chapter_indexes", "chapter_answer_ids"):
        if shell.get(k) and not content.get(k):
            content[k] = shell[k]
    if shell.get("html_verbatim") is not None and "html_verbatim" not in content:
        content["html_verbatim"] = shell["html_verbatim"]

    # html_verbatim：合併後 q_text == 電子書 question-text（04.html 逐字，<br/>→\n）
    assert merged_q.startswith("6、另外，师父12日的答疑是否遗漏了1051楼的问题"), \
        f"unexpected merged q_text head: {merged_q[:40]!r}"
    assert merged_q.endswith("请师父指点。）"), \
        f"unexpected merged q_text tail: {merged_q[-40:]!r}"
    content["html_verbatim"] = True

    # 溯源標籤（僅 notes）
    note = ("主問段（#20）為殼段：師父僅口頭帶過『1051楼的问题 我往上翻一翻看看吧』，"
            "未逐字念主問；問答本體（原#21）括注問題內容與殼段主問同屬電子書同一問題塊")
    # meta：保留 content 自己的 lastPlayed/lastEdited（那是實際聽到答案本體的時間）；
    # 殼段的 lastPlayed（僅 0.1s 殼）只留在 notes 供溯源。
    m_shell = shell.get("meta") or {}
    if m_shell.get("lastPlayed"):
        note += f"（殼段 lastPlayed={m_shell['lastPlayed']}）"
    old = (content.get("notes") or "").strip()
    if MERGE_TAG not in old:
        content["notes"] = " | ".join(x for x in (old, note, MERGE_TAG) if x)

    segs.pop(si)

    # ---- 結構驗證（merge 點附近）----
    keys = [s.get("stable_key") for s in segs]
    assert len(keys) == len(set(keys)), "duplicate stable_key after merge"
    assert find(SHELL_KEY) is None and find(CONTENT_KEY) is not None
    st, en = content.get("start"), content.get("end")
    assert st is not None and en is not None and en > st, "merged span inverted"
    prev_end = None
    for s in segs:
        if s.get("start") is None:
            continue
        if prev_end is not None and s["start"] < prev_end - 0.5:
            print(f"warn: overlap at {s.get('stable_key')} ({prev_end} -> {s['start']})")
        if s.get("end") is not None:
            prev_end = max(prev_end, s["end"]) if prev_end is not None else s["end"]

    d["stats"] = recompute_stats(d)
    MAP.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"merged {SHELL_KEY} -> {CONTENT_KEY} (questioner={q_shell})")
    print(f"  merged q_text: {len(merged_q)} chars, head={merged_q[:30]!r} tail={merged_q[-20:]!r}")
    print(f"  content span: {content['start']}–{content['end']}  "
          f"chapter_qids={content.get('chapter_question_ids')}")
    print(f"  stats: {json.dumps(d['stats'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
