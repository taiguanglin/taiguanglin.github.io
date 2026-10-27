#!/usr/bin/env python3
"""Build the 三千大千世界 world-model source compilation.

Design
------
* `curated`  – whole subsections of the source ebooks, taken verbatim.
               A subsection may appear in more than one theme on purpose
               (e.g. the physics of 光子 is part of both T04 and T13).
* `strong`   – diagnostic phrases; one hit is enough to pull a Q&A in.
* `weak`     – supporting phrases; two hits are needed.

Everything is emitted verbatim with full provenance. Nothing is summarised,
paraphrased or truncated.
"""
import json
import os
import re
import collections

from filters import is_superseded

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "build")
SITE = "https://taiguanglin.info"


# ------------------------------------------------------------------ units
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
                cur = {"unit": "qa", "corpus": corpus, "file": fname,
                       "book": r["book"], "section": r["section"],
                       "anchor": r["anchor"], "blocks": [r]}
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

    # merge split questions that share a base anchor (generator appends -2, -3)
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


def P(corpus, fname, *path):
    return (corpus, fname, tuple(path))


Q = "問答錄2"
B = "九本書"

THEMES = [
    dict(
        id="T01",
        title="宇宙總綱：世界如何存在、創造與消解",
        blurb="佛與等覺菩薩以執著心創造世界；世界是超大幻覺；一真法界、世界海；"
              "世界的解散與歸屬；毀滅與格式化。",
        curated=[
            P(Q, "04_trad.html", "04世界起源與輪轉", "起源", "三個初始設定"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "起源", "初佛的跌落"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "起源", "跌落的原因"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "佛創世"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "一真法界與不同世界"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "世界解散"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "世界歸屬"),
            P(Q, "01_trad.html", "01自性與意識", "初始設定2.初妄無因", "意識的結構/萬物唯心造"),
            P(Q, "01_trad.html", "01自性與意識", "初始設定2.初妄無因", "自性遍虛空與妄想的侷限"),
            P(B, "03_trad.html", "03《坐禪2》", "創世", "第01節 創造"),
            P(B, "03_trad.html", "03《坐禪2》", "創世", "第02節 毀滅"),
            P(B, "03_trad.html", "03《坐禪2》", "真相", "第02節 初妄無因"),
            P(B, "03_trad.html", "03《坐禪2》", "起源", "第01節 最初的佛的跌落"),
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第01節 終極佛法", "1、妄想、分別、執著"),
        ],
        strong=["一真法界", "世界海", "世界的基本構造", "三千大千世界", "小世界",
                "娑婆世界", "創造世界", "世界解散", "世界歸屬", "佛創世", "化現一個世界",
                "化成現一個世界", "世界是怎麼來的", "世界怎麼來的", "世界怎麼組成的",
                "宇宙的組成", "宇宙的構造", "宇宙怎麼", "宇宙是怎麼", "萬物唯心造"],
        weak=["宇宙", "法界", "化現", "變現", "毀滅", "格式化", "世界球", "幻境",
              "超大幻覺", "成住壞空"],
    ),
    dict(
        id="T02",
        title="娑婆世界＝三千大千世界：一個銀河系＝一個小世界",
        blurb="一個三千大千世界＝一個佛的教化區；含十億個小世界；每個小世界＝一個銀河系；"
              "銀河系之間平行但無法溝通。",
        curated=[
            P(Q, "04_trad.html", "04世界起源與輪轉", "娑婆世界"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "解脫與成佛", "成佛的時空", "順序與何處成佛"),
        ],
        strong=["銀河", "星系", "星團", "黑洞", "旋臂", "懸臂", "仙女座", "獵戶臂",
                "三千大千", "十億個小世界", "十億個銀河", "教化區", "大千世界",
                "小世界", "可觀測宇宙", "巨引源", "平行宇宙", "平行世界", "仙女座星系"],
        weak=["太陽系", "月球", "河外星系", "外星", "宇宙", "平行"],
    ),
    dict(
        id="T03",
        title="須彌山：世界之柱、山頂帝釋天宮與四大部洲",
        blurb="須彌山不是銀河系，而是穿透銀河系、串接上下世界的柱子（《坐禪1》舊說的修正）；"
              "山頂帝釋天宮、山腰至山腳四天王天、山腳至海是人間；四大部洲對應銀河系四條旋臂。",
        curated=[
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第03節 欲界六天——四天王天、忉利天"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "娑婆世界", "娑婆世界的菩薩"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "娑婆世界", "釋迦牟尼佛"),
        ],
        strong=["須彌", "帝釋", "忉利天", "四天王", "四大部洲", "南贍部洲", "東勝神洲",
                "西牛賀洲", "北俱盧洲", "贔屨", "香水海", "七金山", "閻浮提",
                "須彌山", "山頂", "山腰", "山腳", "山王", "須彌頂"],
        weak=["柱", "山", "頂上", "帝釋天宮", "旋臂", "獵戶臂", "十洲"],
    ),
    dict(
        id="T04",
        title="世界的基本構造：球層、洋蔥包裹、糖葫蘆串與複眼球面",
        blurb="**核心章節。** 一個世界是一個巨大球體；由外而內自非想非非想處天層層包裹到四禪天"
              "（像洋蔥）；三禪天球面上密佈 1000 個小球（如昆蟲複眼）；三禪／二禪／初禪層串成"
              "糖葫蘆狀的 1000 串，全部指向大世界中心點；四天王天到人間只有須彌山一根柱子。",
        curated=[
            P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "世界的基本構造"),
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第01節 終極佛法",
              "2、三界二十八天——無色界四天"),
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第01節 終極佛法",
              "3、三界二十八天——色界十八天"),
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第01節 終極佛法",
              "4、三界二十八天——欲界六天"),
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第05節 陽神"),
            P(B, "03_trad.html", "03《坐禪2》", "創世", "第01節 創造"),
        ],
        strong=["糖葫蘆", "複眼", "洋蔥", "層層包", "球面", "三禪三天", "二禪三天",
                "初禪三天", "三禪一天", "二禪一天", "初禪一天", "世界球", "1000個光音天球"],
        weak=["球體", "小球", "串", "包裹", "排列", "分佈", "分布", "圓錐", "圓盤", "球上"],
    ),
    dict(
        id="T05",
        title="無色界四天（世界最外層）",
        blurb="非想非非想處天 → 無所有處天 → 識無邊處天 → 空無邊處天；對應四空定；"
              "無物質、無認識的客觀物件，只有虛空。",
        curated=[
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第01節 終極佛法",
              "2、三界二十八天——無色界四天"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "六道輪迴", "天人天界"),
            P(Q, "11_trad.html", "11禪定", "禪定入門"),
        ],
        strong=["無色界", "非想非非想", "無所有處天", "識無邊處天", "空無邊處天",
                "非想非非想處天", "四空定", "無色界四天", "空無邊處定", "識無邊處定",
                "無所有處定", "非想非非想處定"],
        weak=["無色", "四天", "虛空", "分段生死"],
    ),
    dict(
        id="T06",
        title="色界十八天（初禪／二禪／三禪／四禪）",
        blurb="初禪三天、二禪三天、三禪三天、四禪九天，共十八天；色界有物質、有肉身；"
              "執著對象是死物；禪定次第即天界門檻。",
        curated=[
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第02節 色界十八天"),
            P(B, "01_trad.html", "01《坐禪》", "第三章 From 欲界禪定 to 四禪",
              "第06節 禪定次第"),
            P(B, "01_trad.html", "01《坐禪》", "第三章 From 欲界禪定 to 四禪",
              "第04節 From 初禪 to 四禪"),
            P(Q, "11_trad.html", "11禪定", "禪定次第"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "六道輪迴", "天人天界"),
        ],
        strong=["色界", "四禪九天", "四禪天", "少淨天", "光音天", "少光天", "無量光天",
                "遍淨天", "常淨天", "喜樂天", "生歡喜天", "壽命天", "長壽天", "無想天",
                "色界十八天", "四禪九天", "四禪定", "色界天", "初禪三天", "二禪三天"],
        weak=["初禪", "二禪", "三禪", "四禪", "禪定次第", "天界", "天人"],
    ),
    dict(
        id="T07",
        title="欲界六天與人間在天界中的位置",
        blurb="四天王天、忉利天、夜摩天、迦毗羅天、阿毘達婆天、化樂天、他化自在天；"
              "欲界天與人間的相對位置；四天王天在須彌山山腰到山腳。",
        curated=[
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第03節 欲界六天——四天王天、忉利天"),
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第01節 終極佛法",
              "4、三界二十八天——欲界六天"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "六道輪迴", "人道"),
        ],
        strong=["欲界六天", "欲界天", "四天王天", "忉利天", "夜摩天", "迦毗羅天",
                "阿毘達婆天", "阿毘達婆", "化樂天", "他化自在天", "欲界", "第四天",
                "四大天"],
        weak=["人間", "六天"],
    ),
    dict(
        id="T08",
        title="人間世界：地球、南贍部洲與人類文明",
        blurb="人間位於須彌山山腳到海；地球在銀河系最邊遠處、某一條旋臂的末端；"
              "文明的設計與劇本、人治文明三千年、主角國與科技點。",
        curated=[
            P(Q, "04_trad.html", "04世界起源與輪轉", "設計"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "娑婆世界", "娑婆劇本"),
            P(B, "03_trad.html", "03《坐禪2》", "創世", "第03節 眾生的輪轉", "5. 人間"),
            P(B, "03_trad.html", "03《坐禪2》", "創世", "第03節 眾生的輪轉", "6. 文明"),
            P(B, "03_trad.html", "03《坐禪2》", "設計", "第01節 文明設計的 B 計劃"),
            P(B, "03_trad.html", "03《坐禪2》", "設計", "第02節 人治文明三千年"),
            P(B, "03_trad.html", "03《坐禪2》", "設計", "第03節 分場設計"),
            P(B, "03_trad.html", "03《坐禪2》", "設計", "第04節 三千年文明的上半場"),
            P(B, "03_trad.html", "03《坐禪2》", "設計", "第05節 三千年文明的下半場"),
            P(B, "03_trad.html", "03《坐禪2》", "設計", "第06節 改劇本之緣起"),
            P(B, "03_trad.html", "03《坐禪2》", "設計", "第07節 修改劇本"),
            P(B, "03_trad.html", "03《坐禪2》", "設計", "第08節 劇本補丁"),
            P(B, "03_trad.html", "03《坐禪2》", "設計", "第09節 專制與民主"),
            P(B, "03_trad.html", "03《坐禪2》", "設計", "第10節 科技點、第四文明"),
            P(B, "03_trad.html", "03《坐禪2》", "設計", "第11節 主角國的設計"),
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第09節 凡夫的歸宿"),
        ],
        strong=["地球", "南贍部洲", "三星堆", "亞特蘭蒂斯", "文明設計", "動物時代",
                "主角國", "科技點", "第四文明", "人治文明", "神治文明", "三千年的文明",
                "劇本", "命運劇本", "文明", "人類歷史", "世界末日"],
        weak=["國家", "城市", "人類", "劇本"],
    ),
    dict(
        id="T09",
        title="地獄：位置、類型、作用與脫出",
        blurb="地獄在世界中心往下，越靠中心越深；地獄不是消業之處，而是消磨惡念與壞情緒、"
              "令人悔改之所；殺 100 人需死 1 萬次仍不消業；地藏經所述流程。",
        curated=[
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "六道輪迴", "地獄道"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "起源", "無限地獄世界"),
            P(B, "02_trad.html", "02《坐禪之問答錄》", "第17章 地獄、輪迴"),
            P(B, "03_trad.html", "03《坐禪2》", "創世", "第03節 眾生的輪轉", "3. 地獄道眾生"),
            P(B, "03_trad.html", "03《坐禪2》", "創世", "第03節 眾生的輪轉", "4. 消業的去處"),
            P(B, "01_trad.html", "01《坐禪》", "第一章 總論", "第09節 凡夫的歸宿"),
        ],
        strong=["地獄", "十八層地獄", "八大地獄", "無間地獄", "刀山", "油鍋", "鑊湯",
                "鐵床", "銅柱", "劍樹", "毒蛇", "寒冰", "烊銅", "阿鼻地獄", "黑繩地獄",
                "糞尿地獄", "地獄道", "受報地獄", "無間", "地獄變"],
        weak=["地獄", "地藏經", "受苦", "惡報"],
    ),
    dict(
        id="T10",
        title="餓鬼道、畜生道與昆蟲世界",
        blurb="餓鬼道的外在與內在飢餓；畜生道與飛蟲、蟲類眾生；昆蟲也有意識、也是眾生；"
              "金石草木是否有情。",
        curated=[
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "六道輪迴", "餓鬼道"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "六道輪迴", "畜牲/金石草木"),
            P(B, "03_trad.html", "03《坐禪2》", "創世", "第03節 眾生的輪轉", "2. 人道、畜生道、餓鬼道眾生"),
        ],
        strong=["餓鬼", "鬼道", "畜生", "六畜", "昆蟲", "螞蟻", "蚊子", "蒼蠅", "蟑螂",
                "蚜蟲", "蝴蝶", "蜻蜓", "飛蟲", "蟲卵", "昆蟲世界", "昆蟲的複眼",
                "金石草木", "禽獸", "畜牲"],
        weak=["草木", "昆蟲"],
    ),
    dict(
        id="T11",
        title="六道輪迴與眾生輪轉的規律",
        blurb="六道的秩序與管理、中陰身與入胎、來世去處、天龍八部與修羅、鬼王與神仙。",
        curated=[
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "輪轉規律"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "輪迴管理/管理員/漏洞"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "中陰身/入胎"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "來世去處"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "六道輪迴", "天龍八部/修羅"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "眾生輪轉", "六道輪迴", "神仙妖精鬼王"),
            P(B, "03_trad.html", "03《坐禪2》", "創世", "第03節 眾生的輪轉", "1. 天道眾生"),
            P(B, "01_trad.html", "01《坐禪》", "第八章 業力"),
        ],
        strong=["六道", "五道", "天龍八部", "阿修羅", "修羅", "鬼王", "閻王", "閻羅",
                "判官", "酆都", "中陰", "中陰身", "六道輪迴", "輪迴管理", "管理員",
                "陽神被打", "轉世", "輪轉規律"],
        weak=["輪迴", "輪轉", "轉世", "投生", "投胎"],
    ),
    dict(
        id="T12",
        title="佛國與極樂世界（不在銀河系之內）",
        blurb="極樂世界是四聖界佛所建的另一個世界，遠在銀河系之外；九品蓮臺與環境；"
              "東方淨琉璃世界；四聖佛與四聖界；分家成佛與繼承成佛；一個世界同時只能出一尊佛。",
        curated=[
            P(Q, "04_trad.html", "04世界起源與輪轉", "極樂世界"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "解脫與成佛", "解脫後的境界"),
            P(B, "03_trad.html", "03《坐禪2》", "起源", "第04節 四聖佛和四聖界"),
            P(B, "03_trad.html", "03《坐禪2》", "起源", "第05節 極樂世界"),
            P(B, "03_trad.html", "03《坐禪2》", "羯磨", "第02節 業與世界", "2. 新創世界與繼承世界"),
            P(B, "03_trad.html", "03《坐禪2》", "羯磨", "第02節 業與世界", "3. 娑婆世界的魔王"),
        ],
        strong=["極樂世界", "西方極樂", "淨土", "佛國", "佛剎", "十萬億國土", "九品蓮臺",
                "蓮臺", "淨琉璃", "四聖佛", "四聖界", "分家成佛", "分家", "新創世界",
                "繼承世界", "一佛一世界", "毗盧遮那", "法藏比丘", "賢劫", "持國",
                "密集海", "無量壽", "十萬億", "蓮華藏"],
        weak=["極樂", "佛剎", "世界", "淨土", "成佛", "佛國土"],
    ),
    dict(
        id="T13",
        title="物理層：光子、正四面體與能量單位的四倍遞增",
        blurb="一切基本粒子都是光子；四個光子結成正四面體＝能量單位 4；每下一層四倍；"
              "中間層是能量單位 2（啞鈴狀）與 3（平面三角形）；人間級別為 428／429；"
              "肉眼、恆星、三昧真火、引力點與振動。",
        curated=[
            P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "佛創世"),
            P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "世界的基本構造"),
            P(B, "03_trad.html", "03《坐禪2》", "創世", "第01節 創造"),
        ],
        strong=["光子", "能量單位", "正四面體", "基本粒子", "微塵", "極微塵", "最小粒子",
                "最小光子", "三昧真火", "引力點", "核聚變", "半透明", "霧氣", "虛光子",
                "啞鈴狀", "平面三角形", "四個光子", "陽神", "疊加", "叠加"],
        weak=["粒子", "原子", "分子", "振動", "頻率", "波長", "光速", "能量", "物理學"],
    ),
    dict(
        id="T14",
        title="感官層：六根、十二臺機器與昆蟲複眼的取景",
        blurb="注意力是駕駛員，六根＋六根思考能力是十二臺機器；眼根與複眼；"
              "認識的客觀物件從無到虛空到具體物質；萬物唯心造與取景譬喻。",
        curated=[
            P(B, "03_trad.html", "03《坐禪2》", "真相", "第03節 六根"),
            P(B, "03_trad.html", "03《坐禪2》", "真相", "第04節 初禪"),
            P(B, "03_trad.html", "03《坐禪2》", "真相", "第02節 分別"),
            P(Q, "01_trad.html", "01自性與意識", "初始設定2.初妄無因",
              "阿羅漢的分別心", "七識/分別心"),
            P(Q, "01_trad.html", "01自性與意識", "初始設定2.初妄無因",
              "阿羅漢的分別心", "人我/能所分別"),
            P(Q, "01_trad.html", "01自性與意識", "初始設定2.初妄無因",
              "阿羅漢的分別心", "空間/世界分別"),
            P(Q, "01_trad.html", "01自性與意識", "初始設定2.初妄無因",
              "阿羅漢的分別心", "用分別心觀/照"),
            P(Q, "01_trad.html", "01自性與意識", "初始設定2.初妄無因",
              "阿羅漢的分別心", "時間分別與生死"),
            P(Q, "01_trad.html", "01自性與意識", "初始設定2.初妄無因",
              "凡夫的執著", "見取執/習氣"),
            P(Q, "01_trad.html", "01自性與意識", "初始設定2.初妄無因",
              "凡夫的執著", "神識與六根注意力"),
        ],
        strong=["六根", "五根", "眼根", "耳根", "鼻根", "舌根", "身根", "意根", "根塵",
                "複眼", "昆蟲的複眼", "眼球", "網膜", "視網膜", "瞳孔", "小眼",
                "十二臺機器", "六根思考能力", "色聲香味觸法", "萬物唯心造",
                "認識的客觀物件", "認知的客觀物件", "感官"],
        weak=["分別心", "視覺", "聽覺", "味覺", "嗅覺", "觸覺", "注意力", "眼根"],
    ),
    dict(
        id="T15",
        title="時間、劫與世界的毀滅重生",
        blurb="時間是在認知中產生的，不同世界時間尺度不同；劫與成住壞空；"
              "世界的毀滅、格式化與重新整理。",
        curated=[
            P(Q, "04_trad.html", "04世界起源與輪轉", "創世", "毀滅與格式化"),
            P(B, "03_trad.html", "03《坐禪2》", "創世", "第02節 毀滅"),
        ],
        strong=["時間分別", "成住壞空", "劫火", "水火風", "格式化", "世界重新整理",
                "時間變快", "無始無終", "過去現在未來", "劫", "時間的尺度", "時間尺度",
                "一個劫", "毀滅"],
        weak=["時間分別", "無始無終"],
    ),
    dict(
        id="T16",
        title="神通所見：天眼通與一念跳世界",
        blurb="阿羅漢以一念跳一個世界、入定成菩薩狀態可一念穿行；不同世界時間流速不同；"
              "阿羅漢所見的無數世界球。",
        curated=[
            P(B, "01_trad.html", "01《坐禪》", "第七章 神通"),
            P(Q, "12_trad.html", "12佛門修行", "修行要領", "正視神通"),
        ],
        strong=["天眼通", "天眼", "神足通", "一念跳", "跳世界", "世界球", "無數個球",
                "一念穿行", "世界球消失", "跳到其他", "天耳通", "他心通",
                "宿命通", "神足"],
        weak=["神通", "天眼", "入定"],
    ),
]


def build():
    units = load_units()
    by_section = collections.defaultdict(list)
    for u in units:
        by_section[(u["corpus"], u["file"], tuple(u["section"]))].append(u)

    core = collections.defaultdict(list)      # theme -> curated + high-confidence Q&A
    extended = collections.defaultdict(list)  # theme -> incidental mentions

    # ---- pass 1: curated subsections (may repeat across themes by design)
    for th in THEMES:
        for _c, fname, path in th["curated"]:
            for (c, f, sec), us in by_section.items():
                if c != _c or f != fname:
                    continue
                if len(sec) < len(path) or tuple(sec[:len(path)]) != path:
                    continue
                core[th["id"]].extend(u for u in us if not is_superseded(u["text"]))

    taken = set()
    for tid in core:
        taken.update(id(u) for u in core[tid])

    # ---- pass 2: phrase catch-all, each unit to exactly one theme.
    # Only themes with a genuine strong-phrase hit are eligible; ranking is by
    # number of strong hits, then by supporting-phrase score.
    for u in units:
        if id(u) in taken:
            continue
        text = u["text"]
        best, best_key = None, None
        for th in THEMES:
            hits = sum(text.count(w) for w in th["strong"])
            if hits < 1:
                continue
            sup = sum(text.count(w) for w in th["weak"])
            key = (hits, sup)
            if best_key is None or key > best_key:
                best, best_key = th, key
        if best is None or is_superseded(u["text"]):
            continue
        hits = best_key[0]
        # core: the unit genuinely discusses the topic (>=2 strong-phrase hits)
        if hits >= 2:
            core[best["id"]].append(u)
        else:
            extended[best["id"]].append(u)
        taken.add(id(u))

    order = {id(u): i for i, u in enumerate(units)}
    for d in (core, extended):
        for tid in d:
            d[tid].sort(key=lambda u: order[id(u)])
    return units, core, extended


def render_unit(f, u):
    meta = u.get("meta") or {}
    bits = []
    if meta.get("questioner"):
        bits.append(f"提問：{meta['questioner']}")
    if meta.get("question-time"):
        bits.append(f"時間：{meta['question-time']}")
    anchors = [b.get("id", "") for b in u["blocks"] if b.get("id")]
    seen, uniq = set(), []
    for a in anchors:
        if a not in seen:
            seen.add(a)
            uniq.append(a)
    if uniq:
        bits.append("錨點：" + "、".join(f"`{a}`" for a in uniq))
    f.write(f"<sub>{'　｜　'.join(bits)}</sub>\n\n")
    if u["unit"] in ("qa", "solo"):
        # render EVERY block in document order — split questions must not be dropped
        for b in u["blocks"]:
            lbl = {"question": "**問：**", "answer": "**答：**"}.get(b["kind"], "**（原文段落）**")
            f.write(lbl + " " + b["text"] + "\n\n")
    else:
        f.write(u["text"] + "\n\n")


def render_group(f, units, title_suffix=""):
    last = None
    for u in units:
        sec = " > ".join(x for x in u["section"] if x and x != "本章目錄")
        key = (u["corpus"], u["file"], sec)
        if key != last:
            f.write(f"\n#### ▸ {u['book']}｜{sec}{title_suffix}\n\n")
            last = key
        render_unit(f, u)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    units, core, extended = build()
    jsonl = os.path.join(OUTDIR, "world_model_source.jsonl")
    md = os.path.join(OUTDIR, "world_model_source.md")

    ncore = sum(len(v) for v in core.values())
    next_ = sum(len(v) for v in extended.values())
    chars = sum(len(u["text"]) for d in (core, extended) for v in d.values() for u in v)
    print(f"units {len(units)}  core {ncore}  extended {next_}  chars {chars}")
    for th in THEMES:
        c = core.get(th["id"], [])
        e = extended.get(th["id"], [])
        cc = sum(len(u["text"]) for u in c)
        ec = sum(len(u["text"]) for u in e)
        print(f"  {th['id']} core {len(c):>5}/{cc:>8}ch   ext {len(e):>5}/{ec:>8}ch   {th['title']}")

    with open(jsonl, "w", encoding="utf-8") as f:
        for th in THEMES:
            for tier, dd in (("核心", core), ("延伸", extended)):
                for u in dd.get(th["id"], []):
                    blocks = [{"kind": b["kind"], "anchor": b.get("id", ""), "text": b["text"]}
                              for b in u["blocks"]]
                    f.write(json.dumps({
                        "theme": th["id"], "theme_title": th["title"], "tier": tier,
                        "corpus": u["corpus"], "book": u["book"],
                        "section": list(u["section"]), "file": u["file"],
                        "anchor": u["anchor"], "url": url_of(u),
                        "kind": u["unit"], "meta": u.get("meta", {}),
                        "text": u["text"], "blocks": blocks,
                    }, ensure_ascii=False) + "\n")

    def write_md(path, tiers, title, note):
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(
                "本檔是**逐字原文**彙整，供餵給大模型繪製「三千大千世界模型圖」使用。\n\n"
                "- 內容來源：`問答錄2`（12 個主題章）＋九本著作＋《感恩與講經》卷首（`ebook/` 10 卷）。\n"
                "- **未經改寫、刪節、摘要或翻譯**；每一則都標註出處（書／章節／錨點）。\n"
                "- 每則的「問／答」分段原樣保留，方便判斷哪一段是提問、哪一段是開示。\n"
                "- 同一則原文可能出現在多個主題章（內容確實橫跨主題），這是刻意保留的。\n"
                f"- {note}\n\n")
            tot = sum(len(dd.get(th["id"], [])) for dd in tiers for th in THEMES)
            ch = sum(len(u["text"]) for dd in tiers for th in THEMES
                     for u in dd.get(th["id"], []))
            f.write(f"統計：{tot} 則／約 {ch} 字；語料總單元 {len(units)} 則。\n\n")
            f.write("## 目錄\n\n")
            for th in THEMES:
                n = sum(len(dd.get(th["id"], [])) for dd in tiers)
                f.write(f"- **{th['id']} {th['title']}** — {n} 則　{th['blurb']}\n")
            f.write("\n---\n")
            for th in THEMES:
                us = []
                for dd in tiers:
                    us.extend(dd.get(th["id"], []))
                if not us:
                    continue
                f.write(f"\n## {th['id']}　{th['title']}\n\n")
                f.write(f"> {th['blurb']}\n\n")
                if len(tiers) > 1:
                    f.write(f"### 核心（{len(tiers[0].get(th['id'], []))} 則）\n")
                render_group(f, us)
                if len(tiers) > 1:
                    e = tiers[1].get(th["id"], [])
                    if e:
                        f.write(f"\n### 延伸（{len(e)} 則）\n")
                        render_group(f, e, "（延伸）")

    write_md(os.path.join(OUTDIR, "world_model_source.md"), [core, extended],
             "三千大千世界模型圖 —— Tai 師父敘述原始素材（逐字彙整）",
             "分「核心／延伸」兩層：**核心＝宇宙觀章節整節收錄＋高度相關問答（畫圖主要用這一層）**；"
             "延伸＝其餘零星提及。")
    write_md(os.path.join(OUTDIR, "world_model_core.md"), [core],
             "三千大千世界模型圖 —— Tai 師父敘述原始素材（核心版）",
             "只含**核心**層，可直接整份餵給大模型。")
    print("\nwrote", jsonl, os.path.getsize(jsonl))
    for n in ("world_model_source.md", "world_model_core.md"):
        print("wrote", n, os.path.getsize(os.path.join(OUTDIR, n)))


if __name__ == "__main__":
    main()