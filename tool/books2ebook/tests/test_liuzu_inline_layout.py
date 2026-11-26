"""《六祖壇經》第 19 講起「經文與講解同行」排版的碎片修正（合成區塊）。

PDF 從第 19 期起把經文（KaiTi）與講解（MicrosoftYaHei）排在同一視覺行，
字型交界切段會留下「那么，」「说」這類一、兩個字的孤立段落，或把開引號
切到經文尾端。`parsers._fix_inline_sutra_layout()` 只合併相鄰區塊、搬動
標點，文字順序與總字數必須不變（段落跟播要與音檔對得上），且第 18 講以前
一個區塊都不能動（已校對講次的 pid 是段落文字＋段序的雜湊）。
"""

from parsers import _fix_inline_sutra_layout


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
    ]
    assert "".join(t for _, t in _texts(out)) == "".join(t for _, t in _texts(blocks))


def test_lectures_before_19_are_untouched():
    blocks = _lecture(18, ("para", "是这个意思吧？"), ("para", "那么，"),
                      ("quote", "直与曲对，“"), ("para", "直”是直心。"))
    assert _fix_inline_sutra_layout(blocks) == blocks
