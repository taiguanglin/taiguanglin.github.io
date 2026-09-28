#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引文選取器：讓 `src/*.py` 只寫「哪一段原文的第幾句」，文字由語料現取。

為什麼不把引文直接寫死在資料裡
------------------------------
繁簡兩版引文只要手抄一次就會開始漂移（異體字、標點、漏字、錯行）。這裡把引文的
**定位**（pid + 斷句規則）當作 SoT，文字在建置時才從 `data/corpus.json` 取，
並且逐字驗證一定是原文的子字串。改語料 → 重跑建置，兩本書的引文自動跟上。

用法
----
    P("01/p-se5fc701c", 2, 4)     # 該段第 2、3、4 句
    P("01/p-se5fc701c", "樹根")    # 抓含此字串的句子（必須唯一命中）
    P("01/p-se5fc701c", 2, until="空")

    PT("01/p-se5fc701c", "別人講法先講樹葉…", topic="從樹根講起")
    # PT：直接貼繁體原文，簡體版由語料按字元對齊自動取出。適合整段引用。
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

# 斷句：句末標點 + 可能的收尾引號／括號
# 句尾標點＋緊跟其後的收尾引號／括號（』」）】」" 等）——
# 收尾符號必須跟著前一句，否則逐字引文會缺字（例：「…部分。」）的右括號會被吃掉）。
SENT_END = re.compile(r"[。！？；…](?:[”』」）])+")


def _split_sentences(para: str) -> list[str]:
    parts = []
    start = 0
    for m in SENT_END.finditer(para):
        parts.append(para[start:m.end()])
        start = m.end()
    if start < len(para):
        parts.append(para[start:])
    return [s for s in (p.strip() for p in parts) if s]

_SENT_CACHE: dict[str, tuple[list[str], list[str]]] = {}


def sentences(corpus, pid: str) -> tuple[list[str], list[str]]:
    """回傳 (繁體句列表, 簡體句列表)。兩份保證逐句對應。"""
    if pid in _SENT_CACHE:
        return _SENT_CACHE[pid]
    blk = corpus.get(pid)
    sents_t: list[str] = []
    for para in blk["t"].split("\n"):
        para = para.strip()
        if para:
            sents_t.extend(_split_sentences(para))
    sents_s: list[str] = []
    for para in blk["s"].split("\n"):
        para = para.strip()
        if para:
            sents_s.extend(_split_sentences(para))
    if len(sents_t) != len(sents_s):
        raise ValueError(
            f"{pid}: 繁簡句數不一致（{len(sents_t)} vs {len(sents_s)}），不可安全配對"
        )
    _SENT_CACHE[pid] = (sents_t, sents_s)
    return sents_t, sents_s


class Quote:
    """尚未解析的引文定位器。`resolve(corpus)` 才會變成真的 dict。"""

    __slots__ = ("pid", "spec")

    def __init__(self, pid: str, *spec, until: str | None = None, topic: str = "") -> None:
        self.pid = pid
        self.spec = (spec, until, topic)

    def __repr__(self) -> str:  # 讓建置錯誤好讀
        return f"Quote({self.pid!r}, {self.spec[0]!r})"

    def resolve(self, corpus) -> dict:
        spec, until, topic = self.spec
        sents_t, sents_s = sentences(corpus, self.pid)
        if spec and isinstance(spec[0], str):
            key = spec[0]
            hits = [i + 1 for i, s in enumerate(sents_t) if key in s]
            if len(hits) != 1:
                raise ValueError(
                    f"{self.pid}: 關鍵字「{key}」命中 {len(hits)} 句"
                    f"（{'；'.join(f'{i}:{sents_t[i-1][:24]}' for i in hits[:6])}）"
                    "——請改得更精確"
                )
            idx = [hits[0]]
        else:
            idx = [int(n) for n in spec]
        if until:
            try:
                start = idx[0]
            except IndexError:
                raise ValueError(f"{self.pid}: 未指定起始句") from None
            end = next(
                (i for i in range(start - 1, len(sents_t)) if until in sents_t[i]), None
            )
            if end is None:
                raise ValueError(f"{self.pid}: 找不到結束句關鍵字「{until}」") from None
            idx = list(range(start, end + 1))
        for n in idx:
            if not 1 <= n <= len(sents_t):
                raise ValueError(f"{self.pid}: 句號 {n} 超出範圍 1..{len(sents_t)}")
        # 引文必須是原文的**連續**子字串。跳句拼接出來的「引文」在原文裡根本
        # 不存在，`common.verify_book` 的逐字比對一定會失敗——在這裡擋掉，
        # 錯誤訊息才會直接指出是哪幾句中間隔了什麼。
        if sorted(idx) != list(range(min(idx), max(idx) + 1)):
            raise ValueError(
                f"{self.pid}: 句號 {sorted(idx)} 不連續，"
                f"中間漏掉 {[n for n in range(min(idx), max(idx) + 1) if n not in idx]}；"
                f"要嘛用 until=… 表達範圍，要嘛把中間的句子一起引用"
            )
        blk = corpus.get(self.pid)
        return {
            "pid": blk["pid"],
            "t": "".join(sents_t[n - 1] for n in idx),
            "s": "".join(sents_s[n - 1] for n in idx),
            "topic": topic,
            "book": blk["book"],
            "path": blk["path"],
            "kind": blk["kind"],
            "asker": blk.get("asker", ""),
            "time": blk.get("time", ""),
            "qt": blk.get("qt", ""),
        }


def P(pid: str, *spec, until: str | None = None, topic: str = "") -> Quote:
    return Quote(pid, *spec, until=until, topic=topic)


def PT(pid: str, text_t: str, topic: str = "") -> "TextQuote":
    """以「原文片段」定位引文：給一段繁體原文，簡體版由語料按字元對齊自動取出。

    什麼時候用這個而不是 `P()`
    --------------------------
    `P()` 要先數句子編號，適合「我要第 3 到第 5 句」這種精準選取。
    但要引用一段跨好幾句、又已經整理好的長段落時，數句號既慢又容易數錯。

    `PT()` 只需要貼對繁體原文：
      1. 驗證這段確實是該引用單位的**連續子字串**（不對就直接報錯）；
      2. 取它在 `t` 裡的字元起訖位置，再推出 `s` 裡對應位置的切片。

    第 2 步能成立是因為繁簡兩版是**逐字對齊**的：大部分引用單位的 `t` 與 `s`
    等長（簡繁轉換是一對一字），不等長者改走逐句對齊。兩條路徑取出的結果
    都會再被 `assert` 卡住，不會靜默產生錯配。
    """
    return TextQuote(pid, text_t, topic)


def _aligned_simplified(blk: dict, text_t: str) -> str:
    """給定 `blk["t"]` 的連續子字串 `text_t`，回傳 `blk["s"]` 中對齊的片段。"""
    start = blk["t"].index(text_t)
    end = start + len(text_t)

    # 路徑一：整段等長 → 直接按字元位置切
    if len(blk["t"]) == len(blk["s"]):
        return blk["s"][start:end]

    # 路徑二：不等長 → 逐句對齊，句內按字元比例裁切
    bounds, simple = sentences_offsets(blk)
    out: list[str] = []
    unsized: list[tuple[int, int, int]] = []
    for (s_start, s_end), s_text_s in zip(bounds, simple):
        if s_end <= start or s_start >= end:
            continue
        lo = max(start, s_start)
        hi = min(end, s_end)
        if len(s_text_s) == (s_end - s_start):
            out.append(s_text_s[lo - s_start:hi - s_start])
        else:
            # 這一句繁簡長度不同（例如某字轉換後長度變了）→ 記下**絕對**位置
            unsized.append((len(out), lo, hi))
            out.append("")
    if not unsized:
        return "".join(out)

    # 路徑三：仍有長度不一的句子 → 用 SequenceMatcher 逐字對齊整段文字。
    sm = SequenceMatcher(None, blk["t"], blk["s"], autojunk=False)
    mapping: list[tuple[int, int]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        for k in range(i2 - i1):
            if tag == "replace" and k < (j2 - j1):
                mapping.append((i1 + k, j1 + k))
            elif tag == "equal":
                mapping.append((i1 + k, j1 + k))
            else:
                # insert / delete：空缺記成同一個目標位置，位移由後續字元自然帶過
                mapping.append((i1 + k, j1))
    if not mapping:
        raise ValueError(f"{blk['pid']}: 無法對齊繁簡片段")

    for idx, src_start, src_end in unsized:
        lo_j = next((j for i, j in mapping if i >= src_start), None)
        tail = next(((i, j) for i, j in reversed(mapping) if i < src_end), None)
        if lo_j is None or tail is None:
            raise ValueError(f"{blk['pid']}: 這段原文的繁簡無法對齊")
        # 結尾要 +1：`tail[1]` 是片段最後一個字元的目標位置，還沒含在 slice 裡。
        out[idx] = blk["s"][lo_j:tail[1] + 1]
    return "".join(out)


def sentences_offsets(blk: dict) -> tuple[list[tuple[int, int]], list[str]]:
    """回傳 (每句在 `t` 裡的 (起, 訖) 字元位置, 對應的簡體句)。

    以**段落序號**平行前進兩份文字並累計位移，而不是在 `t` 裡搜尋段落文字——
    繁簡兩版偶爾會在某個字上長度不同，用 `index()` 找段落會直接失敗。
    """
    bounds: list[tuple[int, int]] = []
    simple: list[str] = []
    t_lines = blk["t"].split("\n")
    s_lines = blk["s"].split("\n")
    base = 0
    for i, t_text in enumerate(t_lines):
        s_text = s_lines[i] if i < len(s_lines) else ""
        st_list = _split_sentences(t_text)
        ss_list = _split_sentences(s_text)
        if len(st_list) != len(ss_list):
            # 段落層級就對不上（極少見）→ 放棄這一段，不讓它污染後面的位移
            base += len(t_text) + 1
            continue
        off = 0
        for st, ss in zip(st_list, ss_list):
            pos = t_text.index(st, off)
            bounds.append((base + pos, base + pos + len(st)))
            simple.append(ss)
            off = pos + len(st)
        base += len(t_text) + 1
    return bounds, simple


class TextQuote:
    """已帶原文的引文定位器（見 `PT()`）。"""

    __slots__ = ("pid", "text_t", "topic")

    def __init__(self, pid: str, text_t: str, topic: str = "") -> None:
        self.pid = pid
        self.text_t = text_t
        self.topic = topic

    def __repr__(self) -> str:
        return f"TextQuote({self.pid!r}, {self.text_t[:30]!r}…)"

    def resolve(self, corpus) -> dict:
        blk = corpus.get(self.pid)
        if self.text_t not in blk["t"]:
            raise ValueError(
                f"{self.pid}: 這段繁體原文不在該引用單位裡（逐字比對失敗）\n"
                f"  引用：{self.text_t[:60]}…"
            )
        text_s = _aligned_simplified(blk, self.text_t)
        if text_s not in blk["s"]:
            raise ValueError(
                f"{self.pid}: 簡體對齊失敗——取出的片段不在原文裡。"
                "請確認這段引文沒有跨段落或跨句中斷。"
            )
        return {
            "pid": blk["pid"],
            "t": self.text_t,
            "s": text_s,
            "topic": self.topic,
            "book": blk["book"],
            "path": blk["path"],
            "kind": blk["kind"],
            "asker": blk.get("asker", ""),
            "time": blk.get("time", ""),
            "qt": blk.get("qt", ""),
        }


def resolve_all(corpus, node: Any) -> Any:
    """把資料樹裡所有 `Quote` / `TextQuote` 換成已解析的 dict（重建，不改原物件）。"""
    if isinstance(node, (Quote, TextQuote)):
        return node.resolve(corpus)
    if isinstance(node, dict):
        return {k: resolve_all(corpus, v) for k, v in node.items()}
    if isinstance(node, list):
        return [resolve_all(corpus, v) for v in node]
    return node
