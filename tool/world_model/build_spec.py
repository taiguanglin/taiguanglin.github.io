#!/usr/bin/env python3
"""Build a COMPACT drawing-spec compilation for the 三千大千世界 model diagram.

Unlike build_doc.py (which is an exhaustive archive), this keeps only the
passages that state *structural* facts — layer names, counts, geometry,
scale ratios, destruction mechanics — i.e. exactly what an LLM needs to lay
out a labelled schematic. Target size: well under 150 k characters.
"""
import json
import os
import re
import collections

from filters import is_superseded

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "build")
SITE = "https://taiguanglin.info"

# ------------------------------------------------------------------ corpus
def load_units():
    recs = [json.loads(l) for l in open(os.path.join(OUTDIR, "corpus.jsonl"), encoding="utf-8")]
    recs = [r for r in recs if r["kind"] != "_heading"]
    by_file = collections.OrderedDict()
    for r in recs:
        by_file.setdefault((r["corpus"], r["file"]), []).append(r)

    units = []
    for (corpus, fname), rs in by_file.items():
        cur = None
        for r in rs:
            if r["kind"] == "question":
                cur = {"unit": "qa", "corpus": corpus, "file": fname, "book": r["book"],
                       "section": r["section"], "anchor": r["anchor"], "blocks": [r]}
                units.append(cur)
            elif r["kind"] in ("answer", "content"):
                if cur is not None and cur["book"] == r["book"] and cur["section"] == r["section"]:
                    cur["blocks"].append(r)
                else:
                    cur = None
                    units.append({"unit": "solo", "corpus": corpus, "file": fname,
                                  "book": r["book"], "section": r["section"],
                                  "anchor": r["anchor"], "blocks": [r]})
            else:
                cur = None
                units.append({"unit": "para", "corpus": corpus, "file": fname,
                              "book": r["book"], "section": r["section"],
                              "anchor": r["anchor"], "blocks": [r]})

    merged, idx = [], {}
    for u in units:
        base = re.sub(r"-\d+$", "", u["anchor"])
        key = (u["corpus"], u["file"], base, tuple(u["section"]))
        if u["unit"] == "qa" and key in idx:
            idx[key]["blocks"].extend(u["blocks"])
            continue
        if u["unit"] == "qa":
            idx[key] = u
        merged.append(u)
    for u in merged:
        u["text"] = "\n".join(b["text"] for b in u["blocks"]).strip()
        q = next((b for b in u["blocks"] if b["kind"] == "question"), None)
        u["meta"] = q["meta"] if q else (u["blocks"][0].get("meta") or {})
    return merged


def url_of(u):
    d = "wenda2_ebook" if u["corpus"] == "問答錄2" else "ebook"
    return f"{SITE}/{d}/{u['file']}#{u['anchor']}"


Q, B = "問答錄2", "九本書"


def P(c, f, *path):
    return (c, f, tuple(path))


# The systematic construction accounts. They answer layer order (S1), geometry (S3)
# and scale (S4) at the same time, so they are deliberately repeated in those three
# groups rather than forced into one.
CONSTRUCTION = [
    P(B, "03_trad.html", "03《坐禪2》", "創世", "第01節 創造"),
    P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "世界的基本構造"),
    P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "佛創世"),
]

PARTICLE = [
    P(B, "03_trad.html", "03《坐禪2》", "創世", "第01節 創造"),
    P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "世界的基本構造"),
]

LAYER_ORDER = [
    P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第01節 終極佛法",
      "2、三界二十八天——無色界四天"),
    P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第01節 終極佛法",
      "3、三界二十八天——色界十八天"),
    P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第01節 終極佛法",
      "4、三界二十八天——欲界六天"),
]


# ------------------------------------------------- structural-fact phrases
# Phrases that mark a passage as stating geometry / counts / scale / placement.
GEOM = ["球體", "球面", "層層包", "層層往裡包", "洋蔥", "糖葫蘆", "複眼",
        "大球", "1000 個", "1000個", "一千個", "正四面體", "平面三角形",
        "啞鈴狀", "中間層", "球心", "旋臂", "懸臂", "圓錐", "圓盤"]

SCALE = ["能量單位", "光子", "四倍", "4倍", "64倍", "六十四倍", "428", "429",
         "四的光子", "最小的粒子", "最小光子", "虛光子", "比例", "倍大",
         "一立方", "4*4*4", "4³"]

LAYER = ["非想非非想", "無所有處", "識無邊處", "空無邊處", "無色界", "色界十八天",
         "欲界六天", "四禪九天", "三禪三天", "二禪三天", "初禪三天",
         "四天王天", "忉利天", "夜摩天", "迦毗羅天", "阿毘達婆天", "化樂天",
         "他化自在天", "少淨天", "光音天", "少光天", "無量光天", "遍淨天",
         "無想天", "二十八天", "三界"]

PLACE = ["須彌山", "須彌", "帝釋天宮", "山頂", "山腰", "山腳", "四大部洲",
         "南贍部洲", "銀河系", "銀河", "黑洞", "旋臂", "地球", "十億個小世界",
         "小世界", "三千大千", "娑婆世界", "世界中心", "地獄", "人間", "天界",
         "下方", "往上", "最低層", "最外層", "最裡面"]

DIE = ["火劫", "水劫", "風劫", "格式化", "劫", "燒", "涸", "癈", "毀滅",
       "水火風", "貪嗔痴", "新佛出世", "新世界"]

ALL = GEOM + SCALE + LAYER + PLACE + DIE


# ------------------------------------------------------------------ sections
def spec_sections():
    """Ordered groups; each group is a drawing-spec chapter."""
    return [
        ("S1", "世界是什麼：球體、由外而內層層包裹",
         "畫圖最外框與分層依據。",
         CONSTRUCTION + LAYER_ORDER),

        ("S2", "各層的天名與由外而內的順序",
         "同心圓由外到內的層名、層數、與禪定的對應。",
         [P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第02節 色界十八天"),
          P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第03節 欲界六天——四天王天、忉利天"),
          P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第05節 陽神"),
          P(B, "03_trad.html", "03《坐禪2》", "創世", "第03節 眾生的輪轉", "1. 天道眾生"),
          P(B, "03_trad.html", "03《坐禪2》", "創世", "第03節 眾生的輪轉", "2. 人道、畜生道、餓鬼道眾生"),
          P(B, "03_trad.html", "03《坐禪2》", "創世", "第03節 眾生的輪轉", "3. 地獄道眾生")]),

        ("S3", "幾何：球面上的複眼排列、糖葫蘆串與中間層",
         "圖中黃圈、綠圈、白圈的形狀依據：1000 個小球佈在球面；三禪／二禪／初禪串成糖葫蘆；"
         "中間層由能量單位 2、3 的光子構成。（本組重複收錄 S1 的構造章節，因為幾何細節就寫在裡面）",
         CONSTRUCTION),

        ("S4", "尺度：光子能量 4ⁿ 與空間 64⁻ⁿ",
         "圖下方那兩排數字的依據：每下一層光子四倍大、所以外層至少大 64 倍；"
         "人間級別的光子能量單位。（同 S3，重複收錄構造章節）",
         PARTICLE),

        ("S5", "須彌山：貫穿世界的中柱、山頂帝釋天宮",
         "圖中央那條柱子的依據。",
         []),

        ("S6", "須彌山與銀河系的對應（座標定位）",
         "《坐禪1》舊說與後續修正一併保留。",
         []),

        ("S7", "人間與地獄的位置",
         "圖下方人間層與地獄層的位置依據。",
         []),

        ("S8", "毀滅：火劫、水劫、風劫與格式化",
         "圖上那四支箭頭。",
         [P(B, "03_trad.html", "03《坐禪2》", "創世", "第02節 毀滅"),
          P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "毀滅與格式化"),
          P(B, "03_trad.html", "03《坐禪2》", "創世", "第03節 眾生的輪轉", "4. 消業的去處")]),
    ]


# Structural-phrase groups per spec chapter for the catch-all pass.
CATCH = {
    "S3": GEOM + ["糖葫蘆", "複眼", "1000", "球面", "正四面體", "中間層"],
    "S4": SCALE,
    "S5": ["須彌山", "須彌", "帝釋天宮", "山頂", "山腰", "山腳", "山王"],
    "S6": ["銀河系", "銀河", "黑洞", "旋臂", "懸臂", "十億個小世界", "三千大千",
           "娑婆世界", "教化區", "南贍部洲", "四大部洲", "星團"],
    "S7": ["地獄在", "人間在", "世界中心", "往下", "向下", "山腳", "山腰",
           "最裡面", "地獄道", "人間道", "在須彌山", "須彌山山"],
    "S1": ["世界的基本構造", "球體", "洋蔥", "層層包"],
    "S2": LAYER,
}

MIN_HITS = {"S3": 3, "S4": 3, "S5": 3, "S6": 3, "S7": 3, "S1": 4, "S2": 4}

# Sections that are about practice / ritual / biography rather than cosmology.
# Applied to catch-all hits only; curated sections are never filtered.
OFF_TOPIC = ["傳法", "發大願", "求願", "感應", "功課", "懺悔", "超度", "臨終",
             "往生", "治病", "紅塵瑡事", "高僧", "高僧大德", "經咒", "道場",
             "迴向", "加持", "擇師", "善知識", "法會", "捐款", "往生信願行"]


def off_topic(u):
    sec = " > ".join(u["section"])
    return any(w in sec for w in OFF_TOPIC)


def build():
    units = load_units()
    by_section = collections.defaultdict(list)
    for u in units:
        by_section[(u["corpus"], u["file"], tuple(u["section"]))].append(u)

    groups = spec_sections()
    out = collections.OrderedDict((g[0], []) for g in groups)
    taken = set()

    for gid, _t, _b, curated in groups:
        for _c, fname, path in curated:
            for (c, f, sec), us in by_section.items():
                if c != _c or f != fname:
                    continue
                if len(sec) < len(path) or tuple(sec[:len(path)]) != path:
                    continue
                for u in us:
                    if is_superseded(u["text"]):
                        continue
                    out[gid].append(u)
                    taken.add(id(u))

    # catch-all: structural-phrase density
    for u in units:
        if id(u) in taken:
            continue
        t = u["text"]
        best, best_hits = None, 0
        for gid, words in CATCH.items():
            h = sum(t.count(w) for w in words)
            if h > best_hits:
                best, best_hits = gid, h
        if best and best_hits >= MIN_HITS[best] and not off_topic(u) \
                and not is_superseded(u["text"]):
            out[best].append(u)
            taken.add(id(u))

    order = {id(u): i for i, u in enumerate(units)}
    for gid in out:
        out[gid].sort(key=lambda u: order[id(u)])
    return units, out, groups


def render_unit(f, u):
    meta = u.get("meta") or {}
    bits = []
    if meta.get("questioner"):
        bits.append(f"提問：{meta['questioner']}")
    if meta.get("question-time"):
        bits.append(f"時間：{meta['question-time']}")
    anchors, seen = [], set()
    for b in u["blocks"]:
        a = b.get("id", "")
        if a and a not in seen:
            seen.add(a)
            anchors.append(a)
    if anchors:
        bits.append("錨點：" + "、".join(f"`{a}`" for a in anchors))
    f.write(f"<sub>{'　｜　'.join(bits)}</sub>\n\n")
    if u["unit"] in ("qa", "solo"):
        for b in u["blocks"]:
            lbl = {"question": "**問：**", "answer": "**答：**"}.get(b["kind"], "")
            f.write((lbl + " " if lbl else "") + b["text"] + "\n\n")
    else:
        f.write(u["text"] + "\n\n")


# 圖上標籤 → 對應章節（給畫圖時快速定位用）
LABEL_MAP = [
    ("最外圈：無色界 4 天", "S2", "非想非非想／無所有處／識無邊處／空無邊處，由外而內"),
    ("浮居 5 天、四禪下 4 天", "S2", "四禪九天與其下方層次（名稱依《坐禪》原文）"),
    ("三禪 3 天／二禪 3 天／初禪 3 天", "S2", "色界十八天逐層的天名與壽命"),
    ("欲界 6 天", "S2", "四天王天／忉利天／夜摩天／迦毗羅天／阿毘達婆天／化樂天／他化自在天"),
    ("人間 1 層", "S7", "須彌山山腳到海；地球所在"),
    ("地獄 18 層", "S7", "在世界中心往下；地獄不是消業之處"),
    ("中間層：小粒子", "S3", "能量單位 2（啞鈴狀）與 3（平面三角形）光子的中間層"),
    ("黃圈：三禪／二禪／初禪的糖葫蘆串", "S3", "三禪天球面上 1000 串，每串三球，全指向世界中心"),
    ("綠圈：球面上密佈的小球", "S3", "1000 個小球如昆蟲複眼鑲嵌在一個大球面上"),
    ("中心柱＋向上箭頭：須彌山", "S5", "貫穿世界的中柱，山頂帝釋天宮"),
    ("光子能量 4⁰…4⁴⁶", "S4", "每下一層光子四倍大：1→4→16→64→256"),
    ("空間範圍 64⁰…64⁻⁴⁶", "S4", "外層至少比內層大 64 倍（4³）"),
    ("火劫(燒、涸)", "S8", "大光子進入小光子區域被擊碎"),
    ("水劫(食)", "S8", "往世界中心拉、形成霧"),
    ("風劫(癈)", "S8", "快速旋轉產生碰撞"),
    ("格式化(新佛出世)", "S8", "新佛出世時整個世界格式化"),
    ("坐標：銀河系／黑洞／旋臂", "S6", "一個銀河系＝一個小世界；黑洞處是須彌山穿入的位置"),
]


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    units, out, groups = build()
    md = os.path.join(OUTDIR, "world_model_spec.md")
    jsonl = os.path.join(OUTDIR, "world_model_spec.jsonl")

    total = sum(len(v) for v in out.values())
    chars = sum(len(u["text"]) for v in out.values() for u in v)
    print(f"selected {total} units / {chars} chars")
    for gid, title, _b, _c in groups:
        us = out[gid]
        print(f"  {gid} {len(us):>4} units {sum(len(u['text']) for u in us):>7}ch  {title}")

    with open(jsonl, "w", encoding="utf-8") as f:
        for gid, title, _b, _c in groups:
            for u in out[gid]:
                f.write(json.dumps({
                    "group": gid, "group_title": title,
                    "corpus": u["corpus"], "book": u["book"],
                    "section": list(u["section"]), "file": u["file"],
                    "anchor": u["anchor"], "url": url_of(u),
                    "kind": u["unit"], "meta": u.get("meta", {}),
                    "text": u["text"],
                }, ensure_ascii=False) + "\n")

    with open(md, "w", encoding="utf-8") as f:
        f.write("# 三千大千世界模型圖 —— 繪圖用結構規格（逐字）\n\n")
        f.write(
            "這份是**畫示意圖用的精簡集**，不是全文彙整。只保留描述**結構**的段落："
            "層名與層數、球與串的幾何、光子能量與空間尺度、須彌山的位置、劫與格式化。\n\n"
            "- 逐字原文，未改寫、未刪節、未摘要；每則標示出處與錨點。\n"
            "- 順序即**畫圖順序**：S1 由外框開始，一路畫到 S8 的毀滅箭頭。\n"
            "- 需要更大量詞彙（新增說法、細節例子）時，改用 `world_model_source.md`。\n"
            "- **已排除《坐禪1》的舊說**：須彌山＝銀河系（黑洞＝須彌山頂）。"
            "本檔只保留修正後的說法——須彌山是穿透銀河系、串接上下世界的那根柱子。"
            "過濾規則見 `filters.py`。\n\n"
            f"統計：{total} 則／約 {chars:,} 字。\n\n"
            "## 畫圖元素 → 出處速查\n\n"
            "| 圖上元素 | 見本文 | 內容 |\n|---|---|---|\n"
            + "".join(f"| {a} | **{b}** | {c} |\n" for a, b, c in LABEL_MAP)
            + "\n## 章節索引\n\n")
        for gid, title, blurb, _c in groups:
            f.write(f"- **{gid} {title}**（{len(out[gid])} 則）—— {blurb}\n")
        f.write("\n---\n")
        for gid, title, blurb, _c in groups:
            us = out[gid]
            if not us:
                continue
            f.write(f"\n## {gid}　{title}\n\n> {blurb}\n\n")
            last = None
            for u in us:
                sec = " > ".join(x for x in u["section"] if x and x != "本章目錄")
                key = (u["corpus"], u["file"], sec)
                if key != last:
                    f.write(f"\n### ▸ {u['book']}｜{sec}\n\n")
                    last = key
                render_unit(f, u)

    print("\nwrote", md, os.path.getsize(md))
    print("wrote", jsonl, os.path.getsize(jsonl))


if __name__ == "__main__":
    main()