#!/usr/bin/env python3
"""qa_split_ebook 實驗管線 Step 2：準則蒸餾（distill）

把 tool/qa_curation/ 的分類準則整理成分類 agent 的作業材料（全部只讀）：
- build/classify_guide.md        主指南（鐵律、拆分觸發表、12 章錨點、多義詞表、輸出規範）
- build/criteria_digest/chNN.md  逐章摘要（章定位、不收清單、R/N 規則、該章完整樹）
- build/criteria_digest/chNN_sections.md  該章「逐節準則」原文（下探 L3/L4 時按需讀）

章準則檔共 282KB，不可能讓每個分類 agent 全讀；蒸餾器只做兩個可靠動作：
(1) 把「逐節準則」段整段切出到 *_sections.md（單一切割點，格式差異不影響）；
(2) 其餘全文保留在 digest（含判別實例、灰色地帶、R/N 規則），並附上從
    wenda2_ebook 既有目錄抽出的該章完整主題樹（含編號與則數）。

用法：../../word_audio_map2/.venv/bin/python distill.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CRIT = ROOT / "tool/qa_curation"
BUILD = ROOT / "tool/qa_split_ebook" / "build"
TREE_JSON = BUILD / "section_tree.json"
SKILL = (CRIT / "SKILL.md").read_text(encoding="utf-8")
MAIN_CRIT = (CRIT / "wenda2_split_classify_criteria.md").read_text(encoding="utf-8")


def section_between(text: str, start_pat: str, end_pat: str | None = None) -> str:
    """取 start_pat 標題行到下一個 end_pat（或下一個 ^##）之間的內容。"""
    m = re.search(start_pat, text, re.M)
    if not m:
        return ""
    rest = text[m.start():]
    m2 = re.search(end_pat or r"^## ", rest[m.end() - m.start():], re.M)
    if not m2:
        return rest
    return rest[: (m.end() - m.start()) + m2.start()]


def cut_section(text: str, header_pat: str) -> tuple[str, str]:
    """把 header_pat 起的整個 ^## 段切出來，回傳 (剩餘, 切出的段)。"""
    m = re.search(header_pat, text, re.M)
    if not m:
        return text, ""
    m2 = re.search(r"^## ", text[m.end():], re.M)
    end = m.end() + (m2.start() if m2 else (len(text) - m.end()))
    return text[: m.start()] + text[end:], text[m.start():end]


def chapter_tree_lines(ch: int) -> list[str]:
    tree = json.loads(TREE_JSON.read_text(encoding="utf-8"))
    entry = tree[f"{ch:02d}"]
    lines = [f"### {ch:02d}{entry['title']} 全樹（章-L2-L3-L4，括號＝既有則數；新內容會改變數字，編號不變）"]
    l2i = l3i = l4i = 0
    for e in entry["entries"]:
        lvl = e["level"]
        if lvl == 2:
            l2i += 1
            l3i = l4i = 0
            lines.append(f"- {ch:02d}-{l2i:02d} {e['name']} ({e['count']})")
        elif lvl == 3:
            l3i += 1
            l4i = 0
            lines.append(f"  - {ch:02d}-{l2i:02d}-{l3i:02d} {e['name']} ({e['count']})")
        elif lvl == 4:
            l4i += 1
            lines.append(f"    - {ch:02d}-{l2i:02d}-{l3i:02d}-{l4i:02d} {e['name']} ({e['count']})")
    return lines


def main():
    out_dir = BUILD / "criteria_digest"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 逐章 digest / sections
    for ch in range(1, 13):
        src = CRIT / "chapters" / f"ch{ch:02d}.md"
        text = src.read_text(encoding="utf-8")
        rest, sections = cut_section(text, r"^#+ .*逐[节節]準則.*$")
        rest, _naming = cut_section(rest, r"^#+ .*命名慣例.*$")
        digest = rest.rstrip() + "\n\n## 該章完整主題樹（分類輸出的 l2/l3/l4 編號以此為準）\n"
        digest += "\n".join(chapter_tree_lines(ch)) + "\n"
        (out_dir / f"ch{ch:02d}.md").write_text(digest, encoding="utf-8")
        if sections:
            (out_dir / f"ch{ch:02d}_sections.md").write_text(sections, encoding="utf-8")

    # 主指南
    iron = section_between(SKILL, r"^## 1\. 鐵律", r"^## 2\.")
    triggers = section_between(MAIN_CRIT, r"^### 2\.2 ", r"^### 2\.3")
    anchors = section_between(MAIN_CRIT, r"^### 3\.1 ", r"^### 3\.2")
    polysemy = section_between(MAIN_CRIT, r"^### 3\.2 ", r"^### 3\.3")
    procedure = section_between(MAIN_CRIT, r"^### 3\.4 ", r"^### 3\.5")
    guide = f"""# 問答錄2 拆分＋分類 作業指南（實驗批次版）

> 目標：把 2025年6月後的未分類月度答疑（原 wenda2_ebook 13–21 章）分類到
> 既有 12 章主題樹。多數條目已被月度編輯預拆成原子問答；少數（批次標記
> sc=true）含多個編號子問題，需你拆開並對位切分答案。
> 準則 SoT：tool/qa_curation/wenda2_split_classify_criteria.md（本指南為其作業摘要）。

{iron}

## 拆分觸發表（僅對 sc=true 條目執行）
{triggers}

## 章級錨點（定章先讀這個）
{anchors}

## 多義詞判準（同名異章高頻詞——先查表，勿按字面定章）
{polysemy}

## 分類程序
{procedure}

## 逐章材料
- 章定位、不收清單、R/N 規則、完整樹：`tool/qa_split_ebook/build/criteria_digest/ch01.md` … `ch12.md`
- 逐節準則（下探 L3/L4 時讀）：同目錄 `chNN_sections.md`
- 12 章是 fallback：先排除專章（負規則）再落 12。

## 輸出規範（JSONL，一行一個 JSON 物件）
未拆條目：
{{"i":123,"qid":"question-xxxx","sub":0,"split":false,"ch":4,"l2":7,"l2n":"极乐世界","l3":4,"l3n":"往生极乐","l4":null,"l4n":null,"conf":"high","rule":"R6","ru":null,"nr":false,"deferred":false}}
拆分條目（每個子問題一行，sub=1..k，共用同一 qid；q/a＝切分後文字）：
{{"i":123,"qid":"question-xxxx","sub":1,"split":true,"ch":10,"l2":2,"l2n":"...","l3":null,"l3n":null,"l4":null,"l4n":null,"q":"2、...","a":"...","conf":"medium","rule":"...","ru":null,"nr":false,"deferred":false}}

欄位：
- ch：1–12（目標章，不是來源章）。
- l2：該章第幾個 L2；l3：該 L2 下第幾個 L3；l4：該 L3 下第幾個 L4。該層不存在則 null。
  ⚠ 樹裡該 L3 有 L4 子節時 l4 必填；該章/L2 沒有 L3 時 l3 必為 null。l2n/l3n/l4n 填節名（對帳用）。
- conf：high/medium/low。灰色地帶必填 ru（第二候選 path 字串如 "07-02-03"）。low 或孤兒片段 → nr=true。
- deferred：師父答「以後再講」。原文一律不改寫（簡體用語、編號、時間戳逐字保留）。
"""
    (BUILD / "classify_guide.md").write_text(guide, encoding="utf-8")
    print(f"[distill] guide → {BUILD/'classify_guide.md'}")
    print(f"[distill] digests → {out_dir}（12 章 × 2 檔）")


if __name__ == "__main__":
    main()
