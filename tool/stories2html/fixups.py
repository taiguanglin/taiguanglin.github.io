# -*- coding: utf-8 -*-
"""逐篇的收尾修正。

抽取器負責通用版面判讀，這裡只處理各篇獨有、無法一般化的問題：
標題重覆、圖片位置與原文引用不符、被版面切碎的行等。
所有修正都只搬移或標記既有內容，不新增或刪除任何原文文字。
"""
import re


def _find(blocks, pred, start=0):
    for i in range(start, len(blocks)):
        if pred(blocks[i]):
            return i
    return -1


def _is_p(b, text):
    return b["t"] == "p" and b["text"] == text


def _key(s):
    return re.sub(r"\s+", "", s)


def front_matter(blocks, texts):
    """把原檔的標題頁文字標成 front，一字不刪，但排版上與正文區隔。

    頁面自己的 H1 用的是繁體標題，這些行是原檔的簡體題名與署名。
    """
    keys = {_key(t) for t in texts}
    for i, b in enumerate(blocks):
        if i > 8:
            break
        if b["t"] in ("p", "h2") and _key(b.get("text", "")) in keys:
            b["t"] = "p"
            b["front"] = True
            b.pop("quote", None)
    return blocks


# --------------------------------------------------------------------------
def meiqin(blocks):
    blocks = front_matter(blocks, {"快速突破双盘两小时的阶梯法", "——美乐琴心初稿"})

    # 原文在「如图所示。」之後才引用階梯圖，但排版把圖插在下一頁的段落中間，
    # 把圖搬到它被引用的位置，並把被圖切斷的段落接回去
    i = _find(blocks, lambda b: b["t"] == "img")
    img = blocks.pop(i)
    img["caption"] = "階梯法推算示意圖"
    if blocks[i - 1]["t"] == "p" and blocks[i]["t"] == "p":
        blocks[i - 1]["text"] += blocks.pop(i)["text"]
    anchor = _find(blocks, lambda b: _is_p(b, "如图所示。"))
    blocks.insert(anchor + 1, img)

    # QQ 群連結被字體切成三行
    i = _find(blocks, lambda b: _is_p(b, "①欢迎加入Tai"))
    if i >= 0:
        blocks[i]["text"] = "".join(b["text"] for b in blocks[i:i + 3])
        del blocks[i + 1:i + 3]
    return blocks


def shanhui(blocks):
    blocks = front_matter(blocks, {"Tai群善慧师兄磕大头百日期30万圆满分享"})
    return mark_qa(blocks)


def mark_qa(blocks):
    """把「N、問：…」與「答：…」標記成問答組。"""
    for b in blocks:
        if b["t"] != "p":
            continue
        if re.match(r"^\d+[、.]\s*问[：:]", b["text"]):
            b["qa"] = "q"
        elif re.match(r"^答[：:]", b["text"]):
            b["qa"] = "a"
    return blocks


def zhancha(blocks):
    return front_matter(blocks, {"学习《占察善恶业报经》与再读《坐禅》之心得"})


def attach_captions(blocks):
    """把圖說併進圖片。

    並排的圖在原檔裡是「圖、圖、圖說、圖說」的順序，
    所以要一次抓一整組連續的圖與緊跟其後的連續圖說，再一對一配起來。
    """
    out, i = [], 0
    while i < len(blocks):
        if blocks[i]["t"] != "img":
            out.append(blocks[i])
            i += 1
            continue
        imgs = []
        while i < len(blocks) and blocks[i]["t"] == "img":
            imgs.append(blocks[i])
            i += 1
        caps = []
        while i < len(blocks) and blocks[i]["t"] == "caption":
            caps.append(blocks[i])
            i += 1
        if len(caps) == 1 and len(imgs) > 1:
            # 一段說明講的是並排的好幾張圖
            for img in imgs:
                img["caption"] = caps[0]["text"]
            caps = []
        for img, cap in zip(imgs, caps):
            img["caption"] = cap["text"]
        out.extend(imgs)
        out.extend({"t": "caption", "text": c["text"]} for c in caps[len(imgs):])
    return out


def weile_shuangpan(blocks):
    blocks = front_matter(blocks, {"为了能双盘而奋斗的那些日子里"})

    blocks = attach_captions(blocks)

    # 附圖：原文說「見本文最後的附圖」，這裡補一個章節標題把 12 張掃描檔收在一起
    i = _find(blocks, lambda b: b["t"] == "img" and b["w"] > 1000 and b["h"] > 800)
    if i > 0:
        blocks.insert(i, {"t": "h2", "text": "附圖：每月修行計劃（2015 年 6 月～2016 年 5 月）"})
    return blocks


def kedatou_xiaojie(blocks):
    blocks = blocks[:]

    # 「下圖就是加厚版的樣子」後面是兩張並排的瑜伽墊照片
    i = _find(blocks, lambda b: b["t"] == "img")
    if i >= 0 and blocks[i + 1]["t"] == "img":
        blocks[i]["caption"] = "加厚版瑜伽墊（20mm）"
        blocks[i + 1]["caption"] = "加厚版瑜伽墊（20mm）"

    # 「磕大头统计」是附錄 1 的表名，留成一個小標題
    i = _find(blocks, lambda b: _is_p(b, "磕大头统计"))
    if i >= 0:
        blocks[i]["t"] = "h3"

    # 附錄 1 是 6 個月併排的一張大表，拆成每月一張，手機上才讀得下去
    i = _find(blocks, lambda b: b["t"] == "table" and len(b["rows"][0]) == 18)
    if i >= 0:
        blocks[i:i + 1] = split_monthly(blocks[i])
    return blocks


def split_monthly(table):
    rows = table["rows"]
    months = [rows[0][c] for c in range(0, 18, 3)]
    out = []
    for m, col in enumerate(range(0, 18, 3)):
        body = []
        for r in rows[2:]:
            cells = ["" if r[col + k] is None else str(r[col + k]).strip() for k in range(3)]
            if any(cells):
                body.append(cells)
        if body:
            out.append({"t": "table", "caption": "%s 磕大頭紀錄" % (months[m] or "").replace(" ", ""),
                        "rows": [[str(rows[1][col + k]) for k in range(3)]] + body,
                        "compact": True})
    return out


ANHUI_CAPTIONS = {
    "绿色的小袋，是干活时用来装手机听经用，包包是女儿淘汰的，接着用。",
    "丈夫平时拿这串念珠念观音圣号",
    "这是去年治病期间的一张检查报告（当时的资料不全了）。时至今年3月，复查各项指标都正常了。现在肺部还剩一些轻微的炎症。",
    "丈夫平时抄的经和画的画",
    "平时磕头的垫子",
    "平时的念经本",
    "出于隐私，安徽师兄留给了我们一个背影，但可以看出，她体态轻盈，身材苗条，脊椎也挺直，这都是多年实修的结果。",
}


def anhui(blocks):
    blocks = front_matter(blocks, {
        "实修故事", "历时5年多完成3000遍地藏经",
        "其中半年发愿1000遍助丈夫治愈癌症", "分享者：Tai群内安徽师兄"})

    # 照片說明原本是圖片後面的獨立一行，改掛成圖說
    keys = {_key(t) for t in ANHUI_CAPTIONS}
    for i, b in enumerate(blocks):
        if b["t"] == "p" and _key(b["text"]) in keys:
            blocks[i] = {"t": "caption", "text": b["text"]}
    return mark_qa(attach_captions(blocks))


def docx_headings(blocks, heads):
    keys = {_key(h) for h in heads}
    for b in blocks:
        if b["t"] == "p" and _key(b["text"]) in keys:
            b["t"] = "h2"
            b.pop("bold", None)
    return blocks


def tianxi(blocks):
    blocks = front_matter(blocks, {
        "【Tai人说】",
        "“总之大家一起经营，多发自己修行中的感应和体悟——这些都是给新人最好的兴奋剂。”——taiguanglin",
        "3年磕大头20多万", "因剖腹产二胎身体差到极点到身心脱胎换骨", "作者：天禧"})
    return docx_headings(blocks, {
        "剖腹产2胎 身体状态差到谷底",
        "磕头一年：脱发停止、身体大有好转",
        "打坐太精进 磕头太少身体又出状况",
        "磕头二十多万后 家人称赞自己变年轻并跟着磕大头"})


def wuganzi(blocks):
    blocks = front_matter(blocks, {
        "【Tai人说】第二篇",
        "“总之大家一起经营，多发自己修行中的感应和体悟——这些都是给新人最好的兴奋剂。”——taiguanglin",
        "第一次共修10万大头", "从巨大的压力中走过来 时间让我遇见了该遇见的", "作者：握杆子"})
    return docx_headings(blocks, {
        "目标太大有压力？分解目标并做好长线坚持的心理准备",
        "共修前每次磕头很少且难持续  共修后突破自己每天磕头三组",
        "工作、磕头都累：工作拖垮身体 磕头修复身体又很舒服",
        "预防特殊原因耽误时间  有条件的时候多打提前量",
        "在磕大头中修行 一定会遇见该遇见的"})


def buxu(blocks):
    blocks = front_matter(blocks, {"双盘120分钟心得总结", "作者：湖南-不虚"})
    return docx_headings(blocks, {
        "一、时间选择", "二、身体准备", "三、情绪", "四、环境",
        "五、关键技巧", "六、身体变化", "七、突破过程"})


def geren(blocks):
    return front_matter(blocks, {"个人双盘总结"})


def wenyang(blocks):
    blocks = front_matter(blocks, {"大礼拜后必须温养"})
    for b in blocks:
        if b["t"] == "img":
            b["alt"] = "原檔配圖：修行人在海邊夕陽下行大禮拜"
    return blocks


def fushi_huxi(blocks):
    return docx_headings(blocks, {"一，呼吸篇", "二。改变身体的基础物质的产生与运行"})


def xiaoxi(blocks):
    """封面說明與逐篇日記標題。"""
    blocks = front_matter(blocks, {
        "From 30 to 180分钟", "小夕双盘日记", "作者：小夕", "资料整理：话头禅",
        "资料来源：小夕养生记录的博客",
        "博客网址：http://blog.sina.com.cn/sixicheng1014"})

    # 封面上整理者話頭禪的說明，標成引言
    for b in blocks[:12]:
        if b["t"] == "p" and not b.get("front"):
            b["quote"] = True
        if b["t"] == "h2":
            break

    # 每篇日記的標題是「日期＋題目」排在同一行，拆開後日期單獨呈現
    for b in blocks:
        if b["t"] != "h2":
            continue
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\s*(.+)$", b["text"])
        if m:
            b["date"], b["text"] = m.group(1), m.group(2)
    return blocks


FIXUPS = {
    "shuangpan-jieti-fa-meiqin": meiqin,
    "shuangpan-120-buxu": buxu,
    "geren-shuangpan-zongjie": geren,
    "xiaoxi-shuangpan-riji": xiaoxi,
    "shanhui-bairi-30wan": shanhui,
    "tianxi-kedatou": tianxi,
    "wuganzi-kedatou": wuganzi,
    "huatouchan-kedatou-xiaojie": kedatou_xiaojie,
    "dalibai-wenyang": wenyang,
    "fushi-huxi": fushi_huxi,
    "zhancha-zuochan-xinde": zhancha,
    "anhui-3000-dizangjing": anhui,
    "huatouchan-weile-shuangpan": weile_shuangpan,
}


def apply(slug, blocks):
    fn = FIXUPS.get(slug)
    return fn(blocks) if fn else blocks
