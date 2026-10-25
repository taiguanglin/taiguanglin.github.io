#!/usr/bin/env python3
"""qa_split_ebook：從 wenda2_ebook/01–12.html 的章內 TOC 抽 12 章完整主題樹
（含 L4 hidden 節點）→ build/section_tree.json。分類 path 編號以此為準。

用法：../../word_audio_map2/.venv/bin/python extract_tree.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "wenda2_ebook"
OUT = ROOT / "tool/qa_split_ebook/build/section_tree.json"


def main():
    tree = {}
    for ch in range(1, 13):
        html = (SRC / f"{ch:02d}.html").read_text(encoding="utf-8")
        h1 = re.search(r'<h1 id="([^"]+)">(\d+)([^<]*)<span class="chapter-qa-count">\((\d+)\)', html)
        toc_start = html.find('<div class="toc" id="chapter-toc">')
        toc_end = html.find("</main>")
        toc = html[toc_start:toc_end]
        entries = []
        # 注意：L4 的 class 是 toc-level-4 hidden（無 toc-expandable）——都要收
        for m in re.finditer(
                r'<li class="toc-item toc-level-(\d+)(?:[ \"]([^\""]*))?"[^>]*>'
                r'(?:<button[^>]*>[^<]*</button>)?'
                r'<a href="#([^"]+)">(.*?)</a>'
                r'(?:<span class="toc-count">\((\d+)\)</span>)?',
                toc):
            lvl, _cls, slug, name, cnt = m.groups()
            entries.append({"level": int(lvl), "slug": slug,
                           "name": re.sub(r"<[^>]+>", "", name).strip(),
                           "count": int(cnt) if cnt else 0})
        tree[f"{ch:02d}"] = {"h1_slug": h1.group(1), "title": h1.group(3).strip(),
                             "total": int(h1.group(4)), "entries": entries}
    OUT.write_text(json.dumps(tree, ensure_ascii=False, indent=1), encoding="utf-8")
    # 驗證準則 §6.3 範例：04-07-04-02＝往生信愿行；總節數
    ch4 = tree["04"]["entries"]
    l2i = l3i = l4i = 0
    names = {}
    for e in ch4:
        if e["level"] == 2:
            l2i += 1; l3i = l4i = 0
            names[f"04-{l2i:02d}"] = e["name"]
        elif e["level"] == 3:
            l3i += 1; l4i = 0
            names[f"04-{l2i:02d}-{l3i:02d}"] = e["name"]
        else:
            l4i += 1
            names[f"04-{l2i:02d}-{l3i:02d}-{l4i:02d}"] = e["name"]
    ok = names.get("04-07") == "极乐世界" and names.get("04-07-04") == "往生极乐" \
        and names.get("04-07-04-02") == "往生信愿行"
    total = sum(len(t["entries"]) for t in tree.values())
    print(f"[tree] 節點總數 {total}（準則基準 533）；04-07-04-02={'往生信愿行' if ok else '✗ 對不上: ' + str({k: v for k, v in names.items() if k.startswith('04-07-04')})}")
    for ch_s in sorted(tree):
        lv = [0, 0, 0, 0, 0]
        for e in tree[ch_s]["entries"]:
            lv[e["level"]] += 1
        print(f"[tree] {ch_s}: L2={lv[2]} L3={lv[3]} L4={lv[4]}")


if __name__ == "__main__":
    main()
