#!/usr/bin/env python3
"""對齊 `audio_map3/<series>.json` 的段落 pid 與已建置的 `ebook/<book>.html`。

為什麼需要這支工具
------------------
電子書段落的 `id` 是**文字雜湊**：`p-` + `md5(段落文字 + 段序)`[:8]
（見 `html_generator.py` 的 `slug_id`）。所以任何改動段落文字的正規化
（空白掃描、標點、繁簡…）都會換掉 pid，而 `audio_map3` 裡已校對好的
`start/end/confirmed` 是掛在 **pid** 上 → 重建 `ebook/` 之後那幾段會
**靜默失去 `data-start`**：注入器只是查不到對應元素，不會報錯。
真實案例：`2251ec4`（時間戳／冒號格式掃描）改了十來段（`67 年`→`67年`），
四十二章有 10 個 confirmed 段就這樣失去跟播；後續 rebuild 又讓楞伽／六祖／
楞嚴共 25 段（皆為尚未 reviewed 的講次）pid 失效——不先修好，等那些講次
校對完成時同樣會整批漏掉。

用法
----
    # 只檢查（測試失敗時先跑這個，看要動哪幾筆）
    tool/word_audio_map2/.venv/bin/python tool/books2ebook/sync_para_pids.py

    # 確認無誤後套用（只改 pid 與 text，其餘欄位原封不動）
    ... sync_para_pids.py --apply
    ... sync_para_pids.py --series lengqie --apply

比對規則
--------
* 以「去掉所有空白後的文字完全相同」配對，且必須**唯一命中**；有歧義
  （同一段文字在書中出現多次）就不自動處理，印出交人判。
* 只改 `pid` 與 `text`：`start`／`end`／`conf`／`method`／`confirmed`／
  `zero` 一律不動。零寬段（`zero: true` 或 `end <= start`）照樣可以重新配對——
  它們的 pid 同樣會失效，只是沒有時間可注入。
* 套用後請重建 `ebook/`（`cd tool/books2ebook && python3 gen_all.py`）
  並跑 `pytest tool/books2ebook/tests` 驗收（`test_follow_along_build.py`
  會直接檢查「reviewed 講次的每一段都有 data-start」）。
"""

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TOOL_DIR, "..", ".."))

# series → ebook 書號（與 config.BOOKS 的 BookConfig.series / number 對應）
SERIES_BOOKS = {
    "ganen": "04",
    "sishierzhang": "07",
    "lengqie": "08",
    "liuzutanjing": "09",
    "lengyanjing": "10",
}

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}


def norm(text):
    """比對用正規化：去掉所有空白（PDF 抽取的換行／半形空白會漂移）。"""
    return re.sub(r"\s+", "", text or "")


class _ParagraphCollector(HTMLParser):
    """收集 `.para-block` 元素的 id → 純文字（只用標準庫，不依賴 lxml）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0          # 目前已開啟的 .para-block 層數（0 = 不在段內）
        self.pid = None
        self.buf = []
        self.paras = {}

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        a = dict(attrs)
        if tag in ("p", "div") and "para-block" in (a.get("class") or "").split():
            if self.depth == 0:
                self.pid = a.get("id")
                self.buf = []
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if tag in ("p", "div") and self.depth > 0:
            self.depth -= 1
            if self.depth == 0 and self.pid:
                self.paras[self.pid] = "".join(self.buf)

    def handle_data(self, data):
        if self.depth:
            self.buf.append(data)


def read_paragraph_index(html_path):
    p = _ParagraphCollector()
    with open(html_path, encoding="utf-8") as f:
        p.feed(f.read())
    return p.paras


def find_stale(series):
    """回傳 (json_path, html_path, stale)；stale 每筆為 dict。"""
    book = SERIES_BOOKS.get(series)
    if not book:
        raise SystemExit("未知系列：%s（沒有對應的電子書）" % series)
    json_path = os.path.join(REPO_ROOT, "audio_map3", "%s.json" % series)
    html_path = os.path.join(REPO_ROOT, "ebook", "%s.html" % book)
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    html_paras = read_paragraph_index(html_path)
    inv = {}
    for pid, text in html_paras.items():
        inv.setdefault(norm(text), []).append(pid)

    stale = []
    for num in sorted(data.get("lectures", {}), key=lambda x: int(x)):
        for para in data["lectures"][num].get("paragraphs") or []:
            pid = para.get("pid")
            if not pid or pid in html_paras:
                continue
            cands = inv.get(norm(para.get("text", "")), [])
            stale.append({"lecture": num, "pid": pid,
                          "text": para.get("text", ""),
                          "cands": cands,
                          "new_text": html_paras[cands[0]] if len(cands) == 1 else None})
    return json_path, html_path, stale


def _detect_indent(raw):
    """偵測原檔縮排（音校 UI 存回用 1 空格、build_maps.py 用 2 空格），
    照原樣寫回才不會整檔重排、產生數萬行無謂 diff。"""
    m = re.search(r"\n( +)\"", raw)
    return len(m.group(1)) if m else 2


def _dump(data, indent, trailing_newline):
    out = json.dumps(data, ensure_ascii=False, indent=indent)
    return out + ("\n" if trailing_newline else "")


def main(argv=None):
    ap = argparse.ArgumentParser(description="同步 audio_map3 段落 pid")
    ap.add_argument("--series", help="只處理某一系列（預設全部五系列）")
    ap.add_argument("--apply", action="store_true",
                    help="實際改寫 pid/text（預設只檢查）")
    args = ap.parse_args(argv)

    series_list = [args.series] if args.series else sorted(SERIES_BOOKS)
    total = ambiguous = applied = 0
    for series in series_list:
        json_path, html_path, stale = find_stale(series)
        book = SERIES_BOOKS[series]
        if not stale:
            print("OK  %s：pid 與 ebook/%s.html 完全一致" % (series, book))
            continue
        total += len(stale)
        print("WARN %s：%d 段 pid 對不上 ebook/%s.html" % (series, len(stale), book))
        fixable = {}
        for row in stale:
            if len(row["cands"]) != 1:
                ambiguous += 1
                print("  ?  L%-3s %s 命中 %d 個候選 %s，需人工判斷"
                      % (row["lecture"], row["pid"], len(row["cands"]), row["cands"][:5]))
                print("       %s" % row["text"][:40])
                continue
            fixable[row["pid"]] = (row["cands"][0], row["new_text"])
            print("  -  L%-3s %s -> %s" % (row["lecture"], row["pid"], row["cands"][0]))
        if not args.apply or not fixable:
            continue
        with open(json_path, encoding="utf-8") as f:
            raw = f.read()
        data = json.loads(raw)
        n = 0
        for lect in data.get("lectures", {}).values():
            for para in lect.get("paragraphs") or []:
                hit = fixable.get(para.get("pid"))
                if hit:
                    para["pid"], para["text"] = hit
                    n += 1
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(_dump(data, _detect_indent(raw), raw.endswith("\n")))
        applied += n
        print("  => 已改寫 %s：%d 筆（時間/confirmed/zero 未動）" % (json_path, n))
    if applied:
        print("\n下一步：cd tool/books2ebook && python3 gen_all.py"
              "（重建後再跑 pytest tool/books2ebook/tests）")
    elif total:
        print("\n合計 %d 筆待重新配對%s。"
              % (total, "，其中 %d 筆有歧義需人工判斷" % ambiguous if ambiguous else ""))
    return 1 if ambiguous else 0


if __name__ == "__main__":
    sys.exit(main())