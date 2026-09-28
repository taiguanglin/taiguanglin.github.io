#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`tool/wenda2_knowledge/` 兩本複習電子書的共用基礎設施。

三個職責
--------
1. **載入語料**：`data/corpus.json`（由 `extract_corpus.py` 從 `wenda2_ebook/` 抽出）。
2. **逐字驗證引文**：`src/*.py` 裡每條師父原話都必須是語料中該則回答的
   **逐字子字串**。對不到就 `exit 1`——複習書的骨頭是原話，
   改寫、簡繁混用、AI「順手潤稿」都不允許。
3. **繁簡與深連結**：編輯文字（章節標題、導言）SoT 只寫繁體，簡體由
   `word2ebook` 的 i18n 工具轉出；引文則直接取語料裡對應的簡體原文，不經轉換。

深連結格式
----------
`/wenda2_ebook/{NN}[_trad].html#{question-dom-id}`
語料的 `qid` 就是 `{章號:02d}/{question-dom-id}`，所以回原書只要把前綴換掉。

語料慣例注意
------------
`qa["a"]`／`qa["at"]` 是**回答的第一段**（萃取規則見 `extract_corpus.py`），
多段回答只收最後一個回答區塊的首段——引文與句號都以這個範圍為準。
"""

from __future__ import annotations

import json
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
    "keypoints": ROOT / "hidden" / "wenda2_keypoints",
    "lens": ROOT / "hidden" / "wenda2_lens",
}

AI_NOTICE = "本書由 AI 整理自《坐禪之問答錄2》，內容僅供參考，請以 Tai 師父原文教導為準。"


# --------------------------------------------------------------------------
# 語料
# --------------------------------------------------------------------------
class Corpus:
    """`corpus.json` 的查詢介面（依 qid / 依章節 / 依小節）。"""

    def __init__(self, path: Path = CORPUS_PATH) -> None:
        if not path.exists():
            sys.exit(
                f"找不到語料 {path}\n"
                f"請先跑：python3 {HERE / 'extract_corpus.py'}"
            )
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.chapters = raw["chapters"]
        self.by_qid: dict[str, dict] = {}
        self.by_dom: dict[str, dict] = {}
        for ch in self.chapters:
            for qa in ch["qa"]:
                self.by_qid[qa["qid"]] = qa
                self.by_dom.setdefault(qa["qid"].split("/", 1)[1], qa)
        # 章名／小節名：繁簡各一份，出處標籤按頁面語言取用
        self.chapter_title = {
            c["num"]: (c["title_s"], c["title_t"]) for c in self.chapters
        }
        self.section_title = {
            s["id"]: (s["title_s"], s["title_t"])
            for c in self.chapters for s in c["sections"]
        }

    def get(self, qid: str) -> dict:
        if qid in self.by_qid:
            return self.by_qid[qid]
        tail = qid.split("/", 1)[-1]
        if tail in self.by_dom:
            return self.by_dom[tail]
        raise KeyError(f"語料裡沒有這個 qid：{qid}")


# --------------------------------------------------------------------------
# 引文驗證
# --------------------------------------------------------------------------
class QuoteError(Exception):
    pass


def verify_quote(corpus: Corpus, qid: str, text_t: str, text_s: str,
                 where: str) -> dict:
    """確認一條引文的繁簡兩版都逐字存在於語料中；回傳可直接落頁的 dict。"""
    try:
        qa = corpus.get(qid)
    except KeyError as exc:
        raise QuoteError(f"{where}: {exc}") from exc

    if text_t not in qa["at"]:
        raise QuoteError(
            f"{where}: 繁體引文在 {qid} 的回答中找不到（逐字比對失敗）\n"
            f"  引用：{text_t[:60]}…"
        )
    if text_s not in qa["a"]:
        raise QuoteError(
            f"{where}: 簡體引文在 {qid} 的回答中找不到（逐字比對失敗）\n"
            f"  引用：{text_s[:60]}…"
        )
    return {
        "qid": qa["qid"],
        "at": text_t,
        "a": text_s,
        "ch": qa["ch"],
        "section": qa["section"],
        "asker": qa["asker"],
        "time": qa["time"],
    }


def walk_quotes(node, path: str = "$"):
    """遞迴找出資料裡所有形如 `{"qid":…, "at":…, "a":…}` 的引文節點。"""
    if isinstance(node, dict):
        if "qid" in node and "at" in node and "a" in node:
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
            verify_quote(corpus, node["qid"], node["at"], node["a"], f"{label}{path}")
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
            f"  {VENV_PY.relative_to(ROOT)} tool/wenda2_knowledge/build_all.py"
        )


def to_simplified(text: str) -> str:
    return converter().to_simplified(text)


def pick(text: str, trad: bool) -> str:
    """單一 SoT（繁體）→ 目標語言。"""
    return text if trad else to_simplified(text)


# --------------------------------------------------------------------------
# 深連結與出處標籤
# --------------------------------------------------------------------------
def ebook_link(trad: bool, qid: str) -> str:
    """回原書的深連結（跳到那一則問答）。"""
    dom = qid.split("/", 1)[-1]
    ch = int(qid.split("/", 1)[0])
    name = f"{ch:02d}_trad.html" if trad else f"{ch:02d}.html"
    return f"/wenda2_ebook/{name}#{dom}"


def source_label(corpus: Corpus, quote: dict, trad: bool) -> str:
    """引文出處標籤：`第01章 自性與意識｜初始設定1.自性恆常(50)｜2024-03-01 13:18`。"""
    i = 1 if trad else 0
    ch = quote["ch"]
    sec = corpus.section_title.get(quote["section"], ("", ""))[i]
    when = (quote.get("time") or "").strip()
    label = f"第{ch:02d}章 {corpus.chapter_title.get(ch, ('', ''))[i]}｜{sec}"
    if when:
        label += f"｜{when}"
    return label


# --------------------------------------------------------------------------
# HTML 小工具
# --------------------------------------------------------------------------
def esc(text: str) -> str:
    return escape(text, quote=False)


def rich(text: str) -> str:
    """把純文字轉成段落 HTML，保留原問答裡的換行。"""
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    return "\n".join(f"<p>{esc(p)}</p>" for p in paras) if paras else ""
