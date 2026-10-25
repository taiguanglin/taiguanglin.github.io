#!/usr/bin/env python3
"""qa_split_ebook 實驗管線 Step 1：抽取（extract）

把 wenda2_ebook/13–21.html（2025年6月後的未分類月度答疑，3,453 則）抽成
build/items.jsonl：每則一行，含 question/answer 的 HTML 與純文字、來源小節、
音檔段（鍵＝question_id，讀 audio_map1_sep/*.json——與線上 SoT
tool/word2ebook/data/audio_map/ 分離）。

本工具是實驗性質，獨立於線上 word2ebook 管線：不寫入 wenda2_ebook/、
不改 tool/word2ebook/ 任何檔案。

用法（用鎖版 venv）：
    ../../word_audio_map2/.venv/bin/python extract.py
"""
import json
import re
import sys
from pathlib import Path

from lxml import html as lhtml

# ── 日期補充（word2ebook 共用 SoT）─────────────────────────
_DATE_SUPPLEMENT = None
def date_supplement_lookup(qid: str) -> str:
    """question_id → 補充日期（來自音頻映射）；無映射回空字串。"""
    global _DATE_SUPPLEMENT
    if _DATE_SUPPLEMENT is None:
        supplement_file = ROOT / "tool/word2ebook" / "data" / "audio_dates_supplement.json"
        try:
            data = json.loads(supplement_file.read_text(encoding="utf-8"))
            _DATE_SUPPLEMENT = data.get("dates", {})
        except (FileNotFoundError, json.JSONDecodeError):
            _DATE_SUPPLEMENT = {}
    return _DATE_SUPPLEMENT.get(qid, "")

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "wenda2_ebook"
AUDIO_DIR = ROOT / "audio_map1_sep"
BUILD = ROOT / "tool/qa_split_ebook" / "build"
CHAPTERS = list(range(13, 22))


def inner_html(el) -> str:
    """元素 inner HTML（去掉最外層標籤）。"""
    s = lhtml.tostring(el, encoding="unicode")
    s = re.sub(r"^<[^>]+>", "", s)
    s = re.sub(r"<[^>]+>$", "", s.strip())
    return s.strip()


def plain_text(el) -> str:
    """給 LLM 用的純文字：<br/> → 換行、<img> → [配图]。"""
    for br in el.xpath(".//br"):
        br.text = "\n"
    for img in el.xpath(".//img"):
        img.text = "[配图]"
        for child in list(img):
            img.remove(child)
    t = "".join(el.itertext())
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def load_audio_map():
    """audio_map1_sep/*.json → {question_id: {file,start,end,sl,el}}。"""
    qmap = {}
    if not AUDIO_DIR.exists():
        sys.exit(f"[extract] 找不到 {AUDIO_DIR}，請先執行 sync_audio_map.py")
    for f in sorted(AUDIO_DIR.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for sess in data.get("sessions", []):
            audio_file = sess.get("audio_file") or ""
            for seg in sess.get("segments", []):
                qid = seg.get("question_id")
                if not qid or qid in qmap:
                    continue
                if seg.get("start") is None or seg.get("end") is None:
                    continue  # 未對位段（無時間）不建按鈕
                qmap[qid] = {
                    "file": audio_file,
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "sl": seg.get("start_label"),
                    "el": seg.get("end_label"),
                }
    return qmap


def audio_for(qid: str, qmap: dict):
    """先精確匹配；再剝 '-N' 後綴找母條目段（與線上注入器同邏輯）。"""
    if qid in qmap:
        return qmap[qid]
    base = re.sub(r"-\d+$", "", qid)
    return qmap.get(base)


def extract_chapter(ch: int, qmap: dict, stats: dict):
    path = SRC / f"{ch}.html"
    doc = lhtml.parse(str(path)).getroot()
    main = doc.xpath("//main")[0]
    items = []
    cur_sec = None
    for el in main:
        if not isinstance(el.tag, str):
            continue
        if el.tag == "h2" and el.get("id") != "chapter-toc-header":
            # h2 文字節點（避免吃到 span 計數）
            cur_sec = (el.text or "").strip()
        elif el.tag == "article" and "qa-pair" in (el.get("class") or ""):
            qs = el.xpath('./div[@class="question"]')
            ans = el.xpath('./div[@class="answer"]')
            if not qs or not ans:
                stats["no_qa_div"] += 1
                continue
            q, a = qs[0], ans[0]
            qid = q.get("id") or ""
            aid = a.get("id") or ""
            who_els = q.xpath('.//span[@class="questioner"]/text()')
            tm_els = q.xpath('.//span[@class="question-time"]/text()')
            qt_els = q.xpath('./div[@class="question-text"]')
            at_els = a.xpath('./div[@class="answer-text"]')
            if not qt_els or not at_els:
                stats["no_text_div"] += 1
                continue
            # 答案可能由多個 answer-text 段組成（實測 13.html 333 則對 1,397 段）
            q_parts = [inner_html(x) for x in qt_els]
            a_parts = [inner_html(x) for x in at_els]
            items.append({
                "seq": stats["seq"],
                "ch": ch,
                "qid": qid,
                "aid": aid,
                "sec": cur_sec or "",
                "who": (who_els[0].strip() if who_els else ""),
                "time": (tm_els[0].strip() if tm_els else "") or date_supplement_lookup(qid),
                "q_parts": q_parts,
                "a_parts": a_parts,
                "q_text": "\n".join(plain_text(x) for x in qt_els),
                "a_text": "\n".join(plain_text(x) for x in at_els),
                "img": len(el.xpath(".//img")),
                "audio": audio_for(qid, qmap),
            })
            stats["seq"] += 1
    return items


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    qmap = load_audio_map()
    stats = {"seq": 0, "no_qa_div": 0, "no_text_div": 0}
    all_items = []
    for ch in CHAPTERS:
        items = extract_chapter(ch, qmap, stats)
        with_audio = sum(1 for it in items if it["audio"])
        print(f"[extract] ch{ch:02d}: {len(items):4d} 則（含音檔 {with_audio}）")
        all_items.extend(items)
    out = BUILD / "items.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for it in all_items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    missing_audio = [it["qid"] for it in all_items if not it["audio"]]
    print(f"[extract] 合計 {len(all_items)} 則 → {out}")
    print(f"[extract] 無音檔對位：{len(missing_audio)} 則"
          + (f"（例：{missing_audio[:3]}）" if missing_audio else ""))
    if stats["no_qa_div"] or stats["no_text_div"]:
        print(f"[extract] ⚠ 結構異常：{stats}")


if __name__ == "__main__":
    main()
