#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`tool/ebook_knowledge/` 兩本複習電子書的共用基礎設施。

三個職責
--------
1. **載入語料**：`data/corpus.json`（由 `extract_corpus.py` 從 `ebook/` 十本書抽出）。
2. **逐字驗證引文**：資料裡每條師父原話都必須是語料引用單位（段落／回答）的
   **逐字子字串**。對不到就 `exit 1`——複習書的骨頭是原話，改寫、簡繁混用、
   AI「順手潤稿」都不允許。
3. **繁簡與深連結**：編輯文字（章節標題、導言）SoT 只寫繁體，簡體由
   `word2ebook` 的 i18n 工具轉出；引文則直接取語料裡對應的簡體原文，不經轉換。

深連結格式
----------
`/ebook/{NN}[_trad].html#{dom-id}`
語料的 `pid` 就是 `{書號:02d}/{dom-id}`，所以回原書只要把前綴換掉。
"""

from __future__ import annotations

import json
import re
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / "data"
CORPUS_PATH = DATA / "corpus.json"

# 這兩本複習電子書不對外露出：輸出到 hidden/ 下，並在頁面加 noindex。
# WEB_BASE 同時是它們在站上的網址前綴。
WEB_BASE = "/hidden"

# 兩本電子書的輸出目錄（相對於 repo root）
BOOKS = {
    "keypoints": ROOT / "hidden" / "ebook_keypoints",
    "lens": ROOT / "hidden" / "ebook_lens",
}

AI_NOTICE = ("本書由 AI 整理自 Tai 師父《坐禪》《坐禪之問答錄》《坐禪2》"
             "與講經系列等十本書，內容僅供參考，請以 Tai 師父原文教導為準。")


# --------------------------------------------------------------------------
# 語料
# --------------------------------------------------------------------------
class Corpus:
    """`corpus.json` 的查詢介面（依 pid / 依書 / 依章節標題）。"""

    def __init__(self, path: Path = CORPUS_PATH) -> None:
        if not path.exists():
            sys.exit(
                f"找不到語料 {path}\n"
                f"請先跑：python3 {HERE / 'extract_corpus.py'}"
            )
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.books = raw["books"]
        self.by_pid: dict[str, dict] = {}
        self.by_dom: dict[str, dict] = {}
        for book in self.books:
            for blk in book["blocks"]:
                self.by_pid[blk["pid"]] = blk
                self.by_dom.setdefault(blk["pid"].split("/", 1)[1], blk)
        self.book_title = {b["num"]: (b["short_s"], b["short_t"]) for b in self.books}
        self.heading_title = {
            (b["num"], h["id"]): (h["title_s"], h["title_t"])
            for b in self.books for h in b["headings"]
        }

    def get(self, pid: str) -> dict:
        if pid in self.by_pid:
            return self.by_pid[pid]
        tail = pid.split("/", 1)[-1]
        if tail in self.by_dom:
            return self.by_dom[tail]
        raise KeyError(f"語料裡沒有這個 pid：{pid}")


# --------------------------------------------------------------------------
# 引文驗證
# --------------------------------------------------------------------------
class QuoteError(Exception):
    pass


def verify_quote(corpus: Corpus, pid: str, text_t: str, text_s: str,
                 where: str) -> dict:
    """確認一條引文的繁簡兩版都逐字存在於語料中；回傳可直接落頁的 dict。"""
    try:
        blk = corpus.get(pid)
    except KeyError as exc:
        raise QuoteError(f"{where}: {exc}") from exc

    if text_t not in blk["t"]:
        raise QuoteError(
            f"{where}: 繁體引文在 {pid} 的原文中找不到（逐字比對失敗）\n"
            f"  引用：{text_t[:60]}…"
        )
    if text_s not in blk["s"]:
        raise QuoteError(
            f"{where}: 簡體引文在 {pid} 的原文中找不到（逐字比對失敗）\n"
            f"  引用：{text_s[:60]}…"
        )
    return {
        "pid": blk["pid"],
        "t": text_t,
        "s": text_s,
        "book": blk["book"],
        "path": blk["path"],
        "kind": blk["kind"],
        "asker": blk.get("asker", ""),
        "time": blk.get("time", ""),
        "qt": blk.get("qt", ""),
    }


def walk_quotes(node, path: str = "$"):
    """遞迴找出資料裡所有形如 `{"pid":…, "t":…, "s":…}` 的引文節點。"""
    if isinstance(node, dict):
        if "pid" in node and "t" in node and "s" in node:
            yield path, node
        for k, v in node.items():
            yield from walk_quotes(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_quotes(v, f"{path}[{i}]")


def verify_book(corpus: Corpus, book: dict, label: str) -> int:
    """驗證整本書的引文，回傳驗證通過的條數。"""
    n = 0
    errors: list[str] = []
    for path, node in walk_quotes(book):
        try:
            verify_quote(corpus, node["pid"], node["t"], node["s"], f"{label}{path}")
            n += 1
        except QuoteError as exc:
            errors.append(str(exc))
    if errors:
        print(f"✗ {label}：{len(errors)} 條引文驗證失敗", file=sys.stderr)
        for e in errors[:40]:
            print("  -", e, file=sys.stderr)
        if len(errors) > 40:
            print(f"  … 另有 {len(errors) - 40} 條", file=sys.stderr)
        sys.exit(1)
    return n


# --------------------------------------------------------------------------
# 繁簡
# --------------------------------------------------------------------------
_CONVERTER = None


def converter():
    """取得 word2ebook 的簡繁轉換器（含一對多誤轉修正層：只/隻、發/髮、後/后、裡/里）。

    `i18n_utils.py` 內部用相對匯入（`from utils.…`），所以直接把 `tool/word2ebook`
    放進 sys.path 再以頂層模組名載入，而不是走 `tool.word2ebook.…` 套件路徑。
    """
    global _CONVERTER
    if _CONVERTER is None:
        pkg = ROOT / "tool" / "word2ebook"
        for p in (str(pkg), str(pkg.parent)):
            if p not in sys.path:
                sys.path.insert(0, p)
        from word2ebook.utils.i18n_utils import I18nProcessor  # type: ignore

        _CONVERTER = I18nProcessor()
    return _CONVERTER


VENV_PY = ROOT / "tool" / "word_audio_map2" / ".venv" / "bin" / "python"


def require_venv() -> None:
    """簡繁轉換需要 `opencc`，只裝在 `tool/word_audio_map2/.venv` 裡。

    在錯誤的直譯器下跑會得到令人費解的 ImportError，所以在讀任何資料前就先講清楚。
    """
    try:
        converter().to_simplified("測試")
    except ImportError as exc:
        sys.exit(
            f"缺少 opencc：{exc}\n"
            f"請改用 venv 的直譯器：\n"
            f"  {VENV_PY.relative_to(ROOT)} tool/ebook_knowledge/build_all.py"
        )


def to_simplified(text: str) -> str:
    return converter().to_simplified(text)


def pick(text: str, trad: bool) -> str:
    """單一 SoT（繁體）→ 目標語言。"""
    return text if trad else to_simplified(text)


# --------------------------------------------------------------------------
# 深連結與出處標籤
# --------------------------------------------------------------------------
def ebook_link(trad: bool, pid: str) -> str:
    """回原書的深連結（跳到那一段／那一則回答）。"""
    dom = pid.split("/", 1)[-1]
    num = int(pid.split("/", 1)[0])
    name = f"{num:02d}_trad.html" if trad else f"{num:02d}.html"
    return f"/ebook/{name}#{dom}"


def source_label(corpus: Corpus, quote: dict, trad: bool) -> str:
    """引文出處標籤：`《坐禪》｜第三章 From 欲界禪定 to 四禪·第04節 打通任督二脈`。

    問答體（書 02）：`《坐禪之問答錄》｜悠悠·2014-02-25 12:05`。
    """
    i = 1 if trad else 0
    num = quote["book"]
    book = corpus.book_title.get(num, ("", ""))[i]
    if quote.get("kind") == "qa":
        who = quote.get("asker") or ""
        when = (quote.get("time") or "").strip()
        label = f"{book}｜{who}" + (f"·{when}" if when else "")
        return label
    titles = []
    for hid in quote.get("path", []):
        pair = corpus.heading_title.get((num, hid))
        if pair and pair[i] not in titles and pair[i] != book:
            titles.append(pair[i])
    if titles:
        return f"{book}｜" + "·".join(titles)
    return book


# --------------------------------------------------------------------------
# HTML 小工具
# --------------------------------------------------------------------------
def esc(text: str) -> str:
    return escape(text, quote=False)


def rich(text: str) -> str:
    """把純文字轉成段落 HTML，保留原文裡的換行。"""
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    return "\n".join(f"<p>{esc(p)}</p>" for p in paras) if paras else ""
