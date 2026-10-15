"""**段落跟播（讀者便利功能）的建置契約**——已校對講次必須真的能跟播。

為什麼這組測試特別重要
----------------------
`audio_map3/<series>.json` 是人工逐講校對出來的成果（聽音檔、對到毫秒），
`ebook/<book>.html` 是建置產物，兩者之間只靠 **pid（段落文字雜湊）** 關聯。
任何一環掉了都**不會報錯**，讀者只是「某幾段／某幾講沒有段落跟播」：

1. `pid` 是 `md5(段落文字 + 段序)` → 改動文字的正規化（空白掃描、標點…）
   就會讓已校對的 `start/end` 掛到不存在的元素上，該段**靜默失去跟播**。
   （真實案例：`2251ec4` 讓四十二章 10 個 confirmed 段失效。）
2. `ebook/` 沒重建 → 新勾「校對完成」的講次不會出現在頁面上。
3. 前端若退回「只認 h2 直接兄弟節點」，經文之後被 `.sutra-pin-group` 包住的
   段落整批認不到，toggle 不出現（`09b-para-track.js` 的 TreeWalker 契約）。

本模組直接讀**版控中的建置產物**做端到端斷言：SoT 有時間 ⇒ HTML 必須有
`data-start`/`data-end`；反向也不允許（HTML 不該有 SoT 沒核准的時間）。
"""

import json
import re
from html.parser import HTMLParser

import pytest

import para_audio_map
from conftest import book_html

# series → ebook 書號（與 config.BOOKS 的 BookConfig.series / number 對應；
# 與 tool/books2ebook/sync_para_pids.py 的 SERIES_BOOKS 同步）
SERIES_BOOKS = [
    ("ganen", "04"),
    ("sishierzhang", "07"),
    ("lengqie", "08"),
    ("liuzutanjing", "09"),
    ("lengyanjing", "10"),
]

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}

# <p id="p-sXXX" class="para-block" data-start="1.000" data-end="2.000">
_TIMED_RE = re.compile(
    r'id="(p-[^"]+)"[^>]*data-start="([0-9.]+)"\s+data-end="([0-9.]+)"')


def load_series_json(audio_map3_dir, series):
    path = audio_map3_dir / ("%s.json" % series)
    if not path.exists():
        pytest.skip("缺少 audio_map3/%s.json" % series)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def timed_map(html):
    """HTML 實際注入的 {pid: (start, end)}。"""
    return {pid: (float(s), float(e)) for pid, s, e in _TIMED_RE.findall(html)}


def para_pids(html):
    """HTML 中所有 .para-block 的 pid（id / class 兩種屬性順序都收）。"""
    found = set(re.findall(r'id="(p-[^"]+)"[^>]*class="[^"]*para-block', html))
    found |= set(re.findall(r'class="[^"]*para-block[^"]*"[^>]*id="(p-[^"]+)"', html))
    return found


def playable_paragraphs(lecture):
    """SoT 裡「應該被注入」的段落（注入器閘門：reviewed ∧ end>start ∧ 非 zero）。"""
    if not lecture.get("reviewed"):
        return {}
    out = {}
    for para in lecture.get("paragraphs") or []:
        pid = para.get("pid")
        start, end = para.get("start"), para.get("end")
        if not pid or para.get("zero") or start is None or end is None or end <= start:
            continue
        out[pid] = (float(start), float(end))
    return out


class FollowAlongScanner(HTMLParser):
    """模擬 `09b-para-track.js` 建立「講次 → 段落清單」的方式。

    以**文件順序**走訪（與 JS 的 `createTreeWalker(document.body)` 等價）：
    任何 h2 都是講次邊界，含 `.qa-play` 的 h2 開一個講次，其後的定時
    `.para-block` 歸屬該講次；不屬於任何講次的定時段落＝跟播看不到的孤兒。
    """

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.sections = []          # [{qa_play: bool, timed: [pid, …]}]
        self.orphans = []           # 任何講次都看不到的定時段落
        self._in_h2 = False
        self._pending_play = False
        self._active = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "h2":
            self._in_h2 = True
            self._pending_play = False
            return
        if "qa-play" in cls and self._in_h2:
            self._pending_play = True
            return
        if tag in ("p", "div") and "para-block" in cls:
            pid, start, end = a.get("id"), a.get("data-start"), a.get("data-end")
            if not (pid and start and end):
                return
            try:
                if float(end) <= float(start):
                    return
            except ValueError:
                return
            if self._active is None:
                self.orphans.append(pid)
            else:
                self._active["timed"].append(pid)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if tag == "h2":
            if self._pending_play:
                self._active = {"qa_play": True, "timed": []}
                self.sections.append(self._active)
            else:
                self._active = None
            self._in_h2 = False
            self._pending_play = False

    def lectures_with_paragraphs(self):
        return [s for s in self.sections if s["timed"]]


# --------------------------------------------------------------------- #
# 0. 掃描器本身：以最小 HTML 鎖定「文件順序 + 巢狀段落」的模擬語意
# --------------------------------------------------------------------- #
def test_scanner_collects_paragraphs_nested_in_sutra_pin_group():
    """經文與其後講解被 `.sutra-pin-group` 包住時仍要算進同一講——
    這正是只認 h2 直屬兄弟節點時會整批漏掉的形狀。"""
    html = (
        '<main><h2 id="L1"><button class="qa-play"></button></h2>'
        '<p class="para-block" id="p-s0" data-start="0.000" data-end="5.000">'
        '開場</p>'
        '<h3>小節</h3>'
        '<div class="sutra-pin-group"><div class="sutra-pin-host">'
        '<div class="sutra-text para-block" id="p-s1" data-start="5.000" '
        'data-end="9.000">經文</div></div>'
        '<p class="para-block" id="p-s2" data-start="9.000" data-end="12.000">'
        '講解</p></div>'
        '<h2 id="L2"><button class="qa-play"></button></h2>'
        '<p class="para-block" id="p-s3" data-start="1.000" data-end="2.000">'
        '第二講</p>'
        '</main>')
    scanner = FollowAlongScanner(html)
    assert [s["timed"] for s in scanner.sections] == [
        ["p-s0", "p-s1", "p-s2"], ["p-s3"]]
    assert len(scanner.lectures_with_paragraphs()) == 2
    assert scanner.orphans == []


def test_scanner_flags_timed_paragraph_outside_any_lecture():
    """沒有 `.qa-play` 的 h2 結束前一講；之前的定時段落就是孤兒（跟播看不到）。"""
    html = (
        '<main>'
        '<p class="para-block" id="p-s9" data-start="0.000" data-end="3.000">'
        '引言</p>'
        '<h2 id="toc">本章目录</h2>'
        '<div class="toc"></div>'
        '<h2 id="L1"><button class="qa-play"></button></h2>'
        '<p class="para-block" id="p-s1" data-start="3.000" data-end="6.000">'
        '正文</p>'
        '</main>')
    scanner = FollowAlongScanner(html)
    assert scanner.orphans == ["p-s9"]
    assert [s["timed"] for s in scanner.sections] == [["p-s1"]]


def test_scanner_ignores_zero_width_and_untimed_paragraphs():
    html = (
        '<main><h2 id="L1"><button class="qa-play"></button></h2>'
        '<div class="sutra-text para-block" id="p-z" data-start="1.000" '
        'data-end="1.000">師父沒念</div>'
        '<p class="para-block" id="p-n">沒有時間</p>'
        '</main>')
    scanner = FollowAlongScanner(html)
    assert scanner.lectures_with_paragraphs() == [], \
        "沒有可跟播段落的講次不該被算進來"
    assert scanner.orphans == []


# --------------------------------------------------------------------- #
# 1. SoT → HTML：已校對講次的每一段都必須真的注入
# --------------------------------------------------------------------- #
@pytest.mark.artifacts
@pytest.mark.parametrize("series,book", SERIES_BOOKS)
def test_reviewed_paragraphs_are_injected(ebook_dir, audio_map3_dir, series, book):
    """每個 reviewed 講次、每個可播段落都必須在 HTML 裡有 data-start/data-end。"""
    data = load_series_json(audio_map3_dir, series)
    actual = timed_map(book_html(ebook_dir, book))
    missing, total = [], 0
    reviewed_any = False
    for num, lecture in sorted(data["lectures"].items(), key=lambda kv: int(kv[0])):
        if lecture.get("reviewed"):
            reviewed_any = True
        for pid in playable_paragraphs(lecture):
            total += 1
            if pid not in actual:
                missing.append((num, pid))
    if not reviewed_any:
        pytest.skip("%s 尚無校對完成的講次（六祖壇經／楞嚴經待校對）" % series)
    assert not missing, (
        "%s：%d/%d 個已校對段落沒有注入 data-start（跟播會靜默消失）。"
        "常因 pid 漂移——pid 是段落文字雜湊，改動文字正規化後要跑 "
        "`python3 tool/books2ebook/sync_para_pids.py --apply` 再重建 ebook/。前幾筆：%s"
        % (series, len(missing), total, missing[:5]))


# --------------------------------------------------------------------- #
# 2. HTML → SoT：頁面上的時間必須都能在 SoT 找到出處（不得手改產物）
# --------------------------------------------------------------------- #
@pytest.mark.artifacts
@pytest.mark.parametrize("series,book", SERIES_BOOKS)
def test_html_times_match_source_of_truth(ebook_dir, audio_map3_dir, series, book):
    """用注入器的閘門（reviewed/zero/end>start）重算一份，與 HTML 逐筆比對。"""
    data = load_series_json(audio_map3_dir, series)
    actual = timed_map(book_html(ebook_dir, book))
    expected = {}
    for lecture in data["lectures"].values():
        expected.update(playable_paragraphs(lecture))
    extra = {p: v for p, v in actual.items() if p not in expected}
    wrong = {p: (v, expected[p]) for p, v in actual.items()
             if p in expected and (abs(v[0] - expected[p][0]) > 0.001
                                   or abs(v[1] - expected[p][1]) > 0.001)}
    assert not extra, (
        "%s：HTML 有 %d 段 SoT 未核准的時間 %s；生成物不得手改，"
        "請重建 ebook/（cd tool/books2ebook && python3 gen_all.py）"
        % (series, len(extra), list(extra)[:5]))
    assert not wrong, (
        "%s：%d 段的時間與 audio_map3 不符（HTML 值, SoT 值）：%s"
        % (series, len(wrong), list(wrong.items())[:5]))


# --------------------------------------------------------------------- #
# 3. 零寬 / 不念的段落：不該跟播（設計如此）
# --------------------------------------------------------------------- #
@pytest.mark.artifacts
@pytest.mark.parametrize("series,book", SERIES_BOOKS)
def test_zero_length_paragraphs_are_not_injected(ebook_dir, audio_map3_dir, series, book):
    """`zero: true` 或 `end <= start` 的段落不得有 data-start（師父沒念）。"""
    data = load_series_json(audio_map3_dir, series)
    actual = timed_map(book_html(ebook_dir, book))
    offenders = []
    for num, lecture in data["lectures"].items():
        if not lecture.get("reviewed"):
            continue
        for para in lecture.get("paragraphs") or []:
            pid = para.get("pid")
            start, end = para.get("start"), para.get("end")
            unplayable = (para.get("zero") or start is None or end is None
                          or end <= start)
            if unplayable and pid in actual:
                offenders.append((num, pid))
    assert not offenders, (
        "%s：%d 個零寬/零長度段落卻被注入時間（會點了沒反應）：%s"
        % (series, len(offenders), offenders[:5]))


# --------------------------------------------------------------------- #
# 4. pid 漂移：SoT 的每個 pid 都必須存在於書中（未校對的講次也要）
# --------------------------------------------------------------------- #
@pytest.mark.artifacts
@pytest.mark.parametrize("series,book", SERIES_BOOKS)
def test_every_source_pid_exists_in_ebook(ebook_dir, audio_map3_dir, series, book):
    """pid 是文字雜湊；重建電子書改了文字就會換 pid。漂移要**當下**發現，
    等到該講次校對完成才發現，整批已校對成果會白做。"""
    data = load_series_json(audio_map3_dir, series)
    html_pids = para_pids(book_html(ebook_dir, book))
    orphans = []
    for num, lecture in sorted(data["lectures"].items(), key=lambda kv: int(kv[0])):
        for para in lecture.get("paragraphs") or []:
            pid = para.get("pid")
            if pid and pid not in html_pids:
                orphans.append((num, pid))
    assert not orphans, (
        "%s：%d 個段落 pid 在 ebook/%s.html 中不存在（文字被改過、pid 已漂移）：%s。"
        "修法：python3 tool/books2ebook/sync_para_pids.py --apply（只改 pid/text），"
        "再重建 ebook/。"
        % (series, len(orphans), book, orphans[:5]))


# --------------------------------------------------------------------- #
# 5. 已校對講次一定要真的出現「段落跟播」（核心驗收）
# --------------------------------------------------------------------- #
@pytest.mark.artifacts
@pytest.mark.parametrize("series,book", SERIES_BOOKS)
def test_every_reviewed_lecture_has_follow_along(ebook_dir, audio_map3_dir, series, book):
    """用 09b 的文件順序掃描模擬：reviewed 的每一講都必須有可跟播的段落，
    且頁面上每一段注入的時間都要落在某個講次區段內（沒有「注入了卻跟不到」
    的段落）。這正是 2026-10 那個 bug 的守門點：`.sutra-pin-group` 讓經文之後
    的段落變成 h2 的孫節點，只認直屬兄弟節點時 L2 之後整講認不到。"""
    data = load_series_json(audio_map3_dir, series)
    html = book_html(ebook_dir, book)
    reviewed = [n for n, l in data["lectures"].items() if l.get("reviewed")]
    if not reviewed:
        pytest.skip("%s 尚無校對完成的講次" % series)

    scanner = FollowAlongScanner(html)
    injected = timed_map(html)
    scanned = {pid for sec in scanner.sections for pid in sec["timed"]}

    assert not scanner.orphans, (
        "%s：%d 段有 data-start 卻不屬於任何講次（前端看不到＝跟播無效）：%s"
        % (series, len(scanner.orphans), scanner.orphans[:5]))
    assert len(scanner.lectures_with_paragraphs()) == len(reviewed), (
        "%s：reviewed 講次 %d，但頁面上有可跟播段落的講次只有 %d（少 %d 講）"
        % (series, len(reviewed), len(scanner.lectures_with_paragraphs()),
           len(reviewed) - len(scanner.lectures_with_paragraphs())))
    assert scanned == set(injected), (
        "%s：前端看得到的段落 %d 段 ≠ 已注入的 %d 段（差 %s / %s）"
        % (series, len(scanned), len(injected),
           sorted(set(injected) - scanned)[:5], sorted(scanned - set(injected))[:5]))

    # 每個 reviewed 講次的可播段落都必須落在掃描結果裡
    expected = set()
    for num in reviewed:
        expected |= set(playable_paragraphs(data["lectures"][num]))
    assert expected <= scanned, (
        "%s：%d 個已校對段落前端看不到：%s"
        % (series, len(expected - scanned), sorted(expected - scanned)[:5]))


# --------------------------------------------------------------------- #
# 6. 繁簡兩版覆蓋率必須一致
# --------------------------------------------------------------------- #
@pytest.mark.artifacts
@pytest.mark.parametrize("series,book", SERIES_BOOKS)
def test_simplified_and_traditional_match(ebook_dir, audio_map3_dir, series, book):
    simple = timed_map(book_html(ebook_dir, book))
    trad = timed_map(book_html(ebook_dir, book, trad=True))
    assert set(simple) == set(trad), (
        "%s：繁簡版可跟播段落不一致（簡 %d 段 / 繁 %d 段）"
        % (series, len(simple), len(trad)))


# --------------------------------------------------------------------- #
# 7. 教學資料必須真的有 reviewed 講次（避免測試空轉）
# --------------------------------------------------------------------- #
@pytest.mark.artifacts
def test_known_series_have_reviewed_lectures(audio_map3_dir):
    """三個已校對系列必須維持非空：全部退成 reviewed=false ＝ 讀者功能消失。"""
    expected = {"ganen": 1, "sishierzhang": 14, "lengqie": 15}
    for series, minimum in expected.items():
        data = load_series_json(audio_map3_dir, series)
        reviewed = [n for n, l in data["lectures"].items() if l.get("reviewed")]
        assert len(reviewed) >= minimum, (
            "%s：reviewed 講次 %d < 預期的 %d" % (series, len(reviewed), minimum))


# --------------------------------------------------------------------- #
# 8. 前端契約：部署用的共用資產必須保有跟播邏輯
# --------------------------------------------------------------------- #
@pytest.mark.artifacts
def test_shipped_frontend_bundle_keeps_follow_along_contract(repo_root):
    """ebook/ 共用 wenda2_ebook/assets；那兩個檔案是 09b/04c 的實際部署版本。
    若改了 module 卻沒重建，讀者拿到的是舊邏輯（跟播缺段或游標假承諾）。"""
    js_path = repo_root / "wenda2_ebook" / "assets" / "js" / "script.js"
    css_path = repo_root / "wenda2_ebook" / "assets" / "css" / "style.css"
    if not js_path.exists() or not css_path.exists():
        pytest.skip("沒有 wenda2_ebook/assets（先跑 tool/word2ebook/gen_all.py）")
    js = js_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")
    assert "document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT)" in js, \
        "部署版 09b 必須以文件順序收集段落（經文被 .sutra-pin-group 包住時才算得到）"
    assert "classList.add('para-clickable')" in js, \
        "部署版 09b 必須標記 .para-clickable 供游標判斷"
    assert "body.para-track-on .para-block.para-clickable {" in css, \
        "部署版 CSS 的手形游標必須只掛在 .para-clickable 上"


@pytest.mark.artifacts
def test_ebook_pages_load_the_shared_bundle(ebook_dir):
    """講經書頁必須引用共用資產（跟播程式與樣式的來源），而非自己的副本。"""
    for book in ("04", "07", "08"):
        html = book_html(ebook_dir, book)
        assert "/wenda2_ebook/assets/js/script.js" in html
        assert "/wenda2_ebook/assets/css/style.css" in html


# --------------------------------------------------------------------- #
# 9. 注入器讀到的內容與 SoT／HTML 一致（books2ebook 建置時實際使用的路徑）
# --------------------------------------------------------------------- #
@pytest.mark.artifacts
def test_injector_agrees_with_artifact(ebook_dir, audio_map3_dir,
                                       series="sishierzhang", book="07"):
    """`para_audio_map.load_series()`（books2ebook 建置時實際使用的載入器）
    讀到的映射必須與 HTML 上的 data-start/data-end 相同。"""
    para_audio_map._CACHE.clear()
    loaded = para_audio_map.load_series(series)
    actual = timed_map(book_html(ebook_dir, book))
    assert set(loaded) == set(actual), (
        "注入器讀到的 %d 段與 HTML 上的 %d 段不一致（SoT 或 HTML 有異動、需重建）"
        % (len(loaded), len(actual)))
    for pid, span in loaded.items():
        assert abs(span[0] - actual[pid][0]) <= 0.001
        assert abs(span[1] - actual[pid][1]) <= 0.001