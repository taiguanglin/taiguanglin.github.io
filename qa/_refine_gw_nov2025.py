#!/usr/bin/env python3
"""Conservative polish of recovered Nov 2025 官網 QA files."""
import re
from pathlib import Path

QA = Path("/Users/paul/tai/taiguanglin.github.io/qa")
FILES = [
    "2025年11月10日Tai師父官網答疑.txt",
    "2025年11月12日Tai師父官網答疑.txt",
    "2025年11月13日Tai師父官網答疑.txt",
    "2025年11月14日Tai師父官網答疑.txt",
    "2025年11月15日Tai師父官網答疑.txt",
]

# Order matters: longer / specific patterns first
REPLACEMENTS = [
    (r"軌道學校", "鬼道學校"),
    (r"軌道重傷|軌道重伤", "鬼道眾生"),
    (r"軌道眾生|轨道众生", "鬼道眾生"),
    (r"冤親寨主|冤亲寨主|冤經戰士|冤经战士|元軍戰士|元军战士|元親債主|愿親|願親|原清債|边亲|邊親|邊境債主|边境债主", "冤親債主"),
    (r"預決定|預接近|预决定|预接近", "欲界定"),
    (r"預界定|预界定", "欲界定"),
    (r"婆菩薩|伯菩薩|博菩薩", "佛菩薩"),
    (r"阿富汗", "阿羅漢"),
    (r"阿勒汗|阿勒陀羅|阿亂", "阿羅漢"),
    (r"初殘|初層|出倉|出層|出殘|初蚕|初產|初产|出产|出產|出蚕|出差(?=以上|以下|的|時|时|境界|定|就|後|后|，|,|。|？|\?| )", "初禪"),
    (r"二殘|二層|二產|二产", "二禪"),
    (r"三殘|三層|三產|三产", "三禪"),
    (r"四殘|四層|四產|四产|四場(?=是|的|，|,|。|沒|没)", "四禪"),
    (r"(?<=[修到入進在達到])市場(?=的|，|,|。|就|開|开)", "四禪"),
    (r"司佛|思婆|丝破|私破|四波|四破|撕脖|撕破", "思佛"),
    (r"移情|怡情|丝情|世情(?=是|的|，|,|。|一)", "私情"),
    (r"摻(?=移|事|话|話|私)", "參"),
    (r"回降|回鄉(?=给|給|他|她|母|父|親|亲|冤|法|眾|众|地|童|嬰|墮|堕|鬼|亡|故|先)", "回向"),
    (r"回想(?=给|給|他|她|母|父|親|亲|冤|法|眾|众|地|童|嬰|墮|堕|鬼|亡|故|先)", "回向"),
    (r"銀欲|银欲|盈欲|陰鬱(?=的|，|,|。|就)", "淫欲"),
    (r"出學", "初學"),
    (r"胸圍(?=已|到了|到|夠|够|達|达|高|低|一|二|三|四|五|六|七|八|九|十|\d)", "修為"),
    (r"軌道的那個學校|軌道學校", "鬼道學校"),
    (r"軌道中生|軌道終生|轨道众生", "鬼道眾生"),
    (r"軌道呢(?=下|更)", "鬼道呢"),
    (r"軌道重傷", "鬼道眾生"),
    (r"下坐詩", "下坐時"),
    (r"噻酸根|曬酸根", "色根"),
    (r"上山歌|上山關", "上根"),
    (r"郭經理", "過去七鬘經"),  # 語音近似，待人工核對
    (r"生氣尬經理", "《雜阿含經》"),
    (r"蘭德佛", "燃燈佛"),
    (r"發夫", "發法"),
    (r"超佛", "成佛"),
    (r"協議(?=，|,|。|那|也)", "邪淫"),
    (r"諧雲|諧音(?=是|，|,|。|就)", "邪淫"),
    (r"諧淫", "邪淫"),
    (r"葉報|页报", "業報"),
    (r"葉障|页障", "業障"),
    (r"葉(?=是|和|的|邏|回|消|造|完|緣)", "業"),
    (r"宵業|宵夜(?=度|杜|时|時|和|，|,|。|的)", "消業"),
    (r"鬼道重傷", "鬼道眾生"),
    (r"邊青菜", "冤親債主"),
    (r"三m影|三命(?=這|这|手|印)", "三昧印"),
    (r"共和黨(?=，|,|。|而)", "三昧印"),
    (r"關丹田(?=五|十|等|再|就)", "觀丹田"),
    (r"關(?=佛|丹田|呼吸|想|照)", "觀"),
    (r"念波|唸波", "念咒"),
    (r"念聖", "念咒"),
    (r"做餐|作餐", "坐禪"),
    (r"預接近", "欲界定"),
]

FILLER_START = re.compile(r"^(?:啊|嗯|哈|呃|哦|哎|唉)+[，,、\s]*")
FILLER_TAIL = re.compile(r"[，,、\s]*(?:啊|嗯|哈|呃|哦|好吧|是不是啊|对吧|對吧)+[，,。！？\s]*$")
MULTI_FILLER = re.compile(r"(?<=[，。！？\s])(?:嗯+|啊+|哈+|呃+|哦+)(?=[，。！？\s])")
REPEAT = re.compile(r"([，。])\1+")
DUP_PHRASE = re.compile(r"(.{4,12}?)\1{1,2}")


def apply_fixes(text):
    for pat, rep in REPLACEMENTS:
        text = re.sub(pat, rep, text)
    return text


def clean_filler(text):
    if not text:
        return text
    text = FILLER_START.sub("", text)
    text = FILLER_TAIL.sub("", text)
    text = MULTI_FILLER.sub("", text)
    text = REPEAT.sub(r"\1", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[，,]{2,}", "，", text)
    text = re.sub(r"。{2,}", "。", text)
    return text.strip()


def normalize_asker_tag(q):
    q = re.sub(r"\[(\d+)樓：([^\]]*?)(?:嗯|哈|啊|呃|哦|問|问|說|说|第一個問題|第一个问题|題|题)\s*\]", r"[\1樓：\2]", q)
    q = re.sub(r"\[(\d+)樓：([^\]]*?)嗯問", r"[\1樓：\2]", q)
    q = re.sub(r"\[(\d+)樓：\s*\]", r"[\1樓]", q)
    q = re.sub(r"\]\s*([^\[]+)\]", r"] \1", q)  # fix ] duplicate
    q = re.sub(r"(\[[^\]]+\])\s*\1\s*", r"\1 ", q)
    return q.strip()


def ensure_question_mark(q):
    core = re.sub(r"^\[[^\]]+\]\s*", "", q)
    if core and not core.endswith("？") and not core.endswith("?"):
        if re.search(r"(吗|嗎|呢|什么|什麼|怎么|怎麼|如何|为何|為何|是不是|是否|么|麼|嗎)$", core):
            return q.rstrip("。.! ") + "？"
        if "？" not in core and "?" not in core:
            return q.rstrip("。.! ") + "？"
    return q


def clean_punctuation(text):
    text = re.sub(r"。，", "。", text)
    text = re.sub(r"，，", "，", text)
    text = re.sub(r"。{2,}", "。", text)
    text = re.sub(r"^[，,]+", "", text)
    return text


def trim_question(q, a):
    """Remove answer bleed from question field."""
    q = normalize_asker_tag(q)
    core = re.sub(r"^\[[^\]]+\]\s*", "", q)

    # If question contains obvious answer voice ("你靠这个" "我建议")
    cut_markers = [
        r"你靠這個是沒有辦法",
        r"這個你打坐的時候",
        r"如果你是每次都能做",
        r"你只要靜下心來",
        r"這個沒有什麼明確",
        r"從地藏菩薩角度看",
        r"你說諧音就是",
        r"japp any嗯問",
        r"練腹式呼吸。嗯，這個這個已經說過",
        r"嗯，地藏增長輪",
        r"夜是眾生對自己的壞情緒，夜是眾生對他人的壞情緒，也是互動",
    ]
    for m in cut_markers:
        hit = re.search(m, core)
        if hit:
            core = core[: hit.start()].strip("，,。 ")
            break

    # Truncate at first clear answer sentence if Q too long
    if len(core) > 120:
        m = re.search(
            r"^(.{10,120}?[？?。])(?:\s|$)",
            core,
        )
        if m:
            core = m.group(1).rstrip("。.") + "？"

    # Dedupe if answer repeats question opening
    if a.startswith(core[: min(40, len(core))]):
        pass  # answer ok
    elif len(core) > 80 and a[:60] == core[:60]:
        a = a[len(core) :].lstrip("，,。 ")

    prefix = ""
    m = re.match(r"^(\[[^\]]+\])\s*", q)
    if m:
        prefix = m.group(1) + " "
    core = core.strip("，,。 ")
    if core and not core.endswith("？") and not core.endswith("?"):
        if re.search(r"(吗|嗎|呢|什么|什麼|怎么|怎麼|如何|为何|為何|是不是|是否)", core):
            core += "？"
        elif "？" not in core:
            core += "？"
    return prefix + core, a


def title_from_question(q):
    core = re.sub(r"^\[[^\]]+\]\s*", "", q)
    core = re.sub(r"\]+", "", core)
    core = re.sub(r"^\[+", "", core)
    core = re.sub(r"[？?。！!，,].*$", "", core).strip()
    core = re.sub(r"^(?:嗯|啊|哈|呃|哦|這個|这个)\s*", "", core)
    # drop floor echo
    core = re.sub(r"^(?:一百|二百)?[零一二三四五六七八九十\d]+樓\s*", "", core)
    if len(core) > 28:
        core = core[:28] + "…"
    return core or "相關問題"


def split_answer_paragraphs(text):
    """Light paragraph breaks for very long answers."""
    if len(text) < 380:
        return text
    parts = re.split(r"(?<=[。！？])", text)
    paras, buf, n = [], [], 0
    for s in parts:
        if not s.strip():
            continue
        buf.append(s)
        n += 1
        if n >= 3 and len("".join(buf)) > 180:
            paras.append("".join(buf).strip())
            buf, n = [], 0
    if buf:
        paras.append("".join(buf).strip())
    return "\n\n".join(paras) if len(paras) > 1 else text


def parse_file(text):
    lines = text.splitlines()
    header = []
    i = 0
    while i < len(lines) and not lines[i].startswith("### "):
        header.append(lines[i])
        i += 1
    items = []
    while i < len(lines):
        if not lines[i].startswith("### "):
            i += 1
            continue
        title = lines[i]
        i += 1
        qline = a_lines = []
        if i < len(lines) and lines[i].startswith("提問："):
            qline = [lines[i]]
            i += 1
        if i < len(lines) and lines[i].startswith("Tai師父答疑："):
            i += 1
            while i < len(lines) and not lines[i].startswith("### "):
                a_lines.append(lines[i])
                i += 1
        items.append((title, qline, a_lines))
    return header, items


def format_item(n, title, q, a):
    a = split_answer_paragraphs(a)
    return [
        f"### {n}. 關於{title}",
        f"提問： {q}",
        "Tai師父答疑：",
        a,
        "",
    ]


def refine_file(path):
    header, items = parse_file(path.read_text(encoding="utf-8"))
    out_lines = list(header)
    if out_lines and out_lines[-1].strip():
        out_lines.append("")
    new_items = []
    for _, qline, alines in items:
        q = qline[0].replace("提問：", "").strip() if qline else ""
        a = "\n".join(alines).strip()
        q, a = apply_fixes(q), apply_fixes(a)
        q, a = trim_question(q, a)
        q = ensure_question_mark(q)
        q, a = clean_filler(q), clean_filler(a)
        q, a = clean_punctuation(q), clean_punctuation(a)
        # remove duplicate Q at start of A
        qcore = re.sub(r"^\[[^\]]+\]\s*", "", q)
        if a.startswith(qcore[: min(50, len(qcore))]):
            a = a[len(qcore) :].lstrip("，,。 ")
            a = clean_filler(a)
        title = title_from_question(q)
        new_items.append((title, q, a))
    for n, (title, q, a) in enumerate(new_items, 1):
        out_lines.extend(format_item(n, title, q, a))
    path.write_text("\n".join(out_lines).strip() + "\n", encoding="utf-8")
    return len(new_items)


def main():
    for fn in FILES:
        n = refine_file(QA / fn)
        print(f"{fn}: {n} questions")


if __name__ == "__main__":
    main()
