"""《六祖壇經》第 19 講起「經文與講解同行」排版的碎片修正（合成區塊）。

PDF 從第 19 期起把經文（KaiTi）與講解（MicrosoftYaHei）排在同一視覺行，
字型交界切段會留下「那么，」「说」這類一、兩個字的孤立段落，或把開引號
切到經文尾端。`parsers._fix_inline_sutra_layout()` 只合併相鄰區塊、搬動
標點，文字順序與總字數必須不變（段落跟播要與音檔對得上），且第 18 講以前
一個區塊都不能動（已校對講次的 pid 是段落文字＋段序的雜湊）。

第二輪 `parsers._merge_sutra_clauses()` 把逐句念、逐句講的半句經文接回一行：
S1 E1 S2 E2 → (S1S2) (E1E2)，經文與講解各自的字序不變，只是兩句經文排到一起。
段數仍超過 130 的講次再逐級接起中間只隔一段短講解的整句（偈頌、引出偈頌的行、
跨越講次開頭整段經文分段處除外），每講只用到剛好壓到 130 段以內的級別。
"""

from parsers import _fix_inline_sutra_layout, _merge_sutra_clauses


def _lecture(n, *blocks):
    return [{"kind": "h2", "text": "坛经（%d）" % n, "lecture": n}] + [
        {"kind": k, "text": t} for k, t in blocks]


def _texts(blocks):
    return [(b["kind"], b["text"]) for b in blocks if b["kind"] != "h2"]


def test_fragments_are_folded_from_lecture_19():
    blocks = _lecture(
        19,
        ("para", "是这个意思吧？"),
        ("para", "那么，"),                       # lead-in → previous para
        ("quote", "师曰：“汝曾作什么来？”"),
        ("para", "你以前做了什么呢？"),
        ("quote", "直与曲对，“"),                 # trailing open quote → next para
        ("para", "直”是直心。"),
        ("quote", "痴与慧对，痴"),                # stray KaiTi char → next para
        ("para", "是不懂因果。"),
        ("para", "先说，“"),                      # inline citation → one para
        ("quote", "吾所见戒定慧又别"),
        ("para", "”，我见到的。"),
        ("quote", "对曰：“不是。”"),               # genuine short explanation stays
        ("para", "我不是啊。"),
        ("para", "不去这把注意力"),                 # sentence split mid-way → rejoined
        ("para", "放到静上。"),
    )
    out = _fix_inline_sutra_layout(blocks)
    assert _texts(out) == [
        ("para", "是这个意思吧？那么，"),
        ("quote", "师曰：“汝曾作什么来？”"),
        ("para", "你以前做了什么呢？"),
        ("quote", "直与曲对，"),
        ("para", "“直”是直心。"),
        ("quote", "痴与慧对，"),
        ("para", "痴是不懂因果。先说，“吾所见戒定慧又别”，我见到的。"),
        ("quote", "对曰：“不是。”"),
        ("para", "我不是啊。"),
        ("para", "不去这把注意力放到静上。"),
    ]
    assert "".join(t for _, t in _texts(out)) == "".join(t for _, t in _texts(blocks))


def test_lectures_before_19_are_untouched():
    blocks = _lecture(18, ("para", "是这个意思吧？"), ("para", "那么，"),
                      ("quote", "直与曲对，“"), ("para", "直”是直心。"))
    assert _fix_inline_sutra_layout(blocks) == blocks


def test_sutra_clauses_merge_into_one_line_from_lecture_19():
    long_a, long_b = "讲" * 200, "解" * 100
    blocks = _lecture(
        23,
        ("quote", "有一童子，"),                   # lecture-top full text stays
        ("para", "我们看原文。"),
        ("quote", "有一童子，名神会。"),
        ("para", "他叫神会。"),
        ("quote", "无生无灭，"),                   # user's example (L23)
        ("para", "自性就是无生无灭的。"),
        ("quote", "是如来清净禅；"),
        ("para", "这就是如来的清净禅。"),
        ("quote", "听吾偈。”曰："),                # verse intro keeps its own line
        ("para", "下面是偈。"),
        ("quote", "天与地对，"),                   # 三十六對 list item keeps its line
        ("para", "这个也知道。"),
        ("quote", "日与月对。"),
        ("para", "也知道。"),
        ("quote", "积以为池，"),                   # joined explanation too long → two paras
        ("para", long_a),
        ("quote", "乃跪膝浣衣石上。"),
        ("para", long_b),
    )
    out = _merge_sutra_clauses(blocks)
    assert _texts(out) == [
        ("quote", "有一童子，"),
        ("para", "我们看原文。"),
        ("quote", "有一童子，名神会。"),
        ("para", "他叫神会。"),
        ("quote", "无生无灭，是如来清净禅；"),
        ("para", "自性就是无生无灭的。这就是如来的清净禅。"),
        ("quote", "听吾偈。”曰："),
        ("para", "下面是偈。"),
        ("quote", "天与地对，"),
        ("para", "这个也知道。"),
        ("quote", "日与月对。"),
        ("para", "也知道。"),
        ("quote", "积以为池，乃跪膝浣衣石上。"),
        ("para", long_a),
        ("para", long_b),
    ]
    for kind in ("quote", "para"):
        assert ("".join(t for k, t in _texts(out) if k == kind)
                == "".join(t for k, t in _texts(blocks) if k == kind))


def test_long_lectures_also_merge_whole_sentences():
    head = [
        ("quote", "甲曰：“一。”乙曰：“二。”"),       # lecture-top full text, paragraph 1
        ("quote", "丙曰：“三。”"),                  # paragraph 2
        ("para", "我们看原文。"),
        ("quote", "甲曰：“一。”"),
        ("para", "甲说一。"),
        ("quote", "乙曰：“二。”"),                  # same full-text paragraph → joins 甲
        ("para", "乙说二。"),
        ("quote", "丙曰：“三。”"),                  # next full-text paragraph → own line
        ("para", "丙说三。"),
        ("quote", "偈曰："),
        ("para", "下面是偈。"),
        ("quote", "菩提本无树，明镜亦非台。"),       # verse line stays alone
        ("para", "没有树。"),
    ]
    filler = [("quote", "师曰：“善。”"), ("para", "说好。")] * 64
    blocks = _lecture(20, *head, *filler)
    out = _texts(_merge_sutra_clauses(blocks))
    assert out[:11] == [
        ("quote", "甲曰：“一。”乙曰：“二。”"),
        ("quote", "丙曰：“三。”"),
        ("para", "我们看原文。"),
        ("quote", "甲曰：“一。”乙曰：“二。”"),
        ("para", "甲说一。乙说二。"),
        ("quote", "丙曰：“三。”"),
        ("para", "丙说三。"),
        ("quote", "偈曰："),
        ("para", "下面是偈。"),
        ("quote", "菩提本无树，明镜亦非台。"),
        ("para", "没有树。"),
    ]
    assert len(out) <= 130
    for kind in ("quote", "para"):
        assert ("".join(t for k, t in out if k == kind)
                == "".join(t for k, t in _texts(blocks) if k == kind))
    short = _lecture(20, *head[2:])                     # ≤ 130 paras: whole sentences stay apart
    assert _merge_sutra_clauses(short) == short


def test_sutra_clauses_before_19_are_untouched():
    blocks = _lecture(18, ("para", "我们看原文。"), ("quote", "无生无灭，"),
                      ("para", "自性无生无灭。"), ("quote", "是如来清净禅；"),
                      ("para", "这是清净禅。"))
    assert _merge_sutra_clauses(blocks) == blocks
