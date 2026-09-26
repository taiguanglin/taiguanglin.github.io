"""Tests for word-chapter audio map injection (audio_map2 chapter-id keyed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.audio_map_injector import (
    inject_word_chapters,
    inject_word_html_from_audio_map2,
    load_word_maps_from_audio_map2,
    _is_audio_map2_reviewed,
)
from models.document_models import Chapter


WORD_CHAPTER = """<h2 id="chu-shi-she-ding">初始设定1.自性恒常</h2>
<p id="content-intro">章节开头。</p>
<div class="question" id="question-aaa">
<div class="question-meta">
<span class="questioner">慧日永明</span>
<span class="question-time">2024-03-01 13:18</span>
</div>
<div class="question-text">自性和阿赖耶识不能等同吧？</div>
</div>
<div class="answer" id="answer-aaa">
<div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
<div class="answer-text">答一</div>
</div>
<hr/>
<div class="question" id="question-bbb">
<div class="question-text">问题二</div>
</div>
<div class="answer" id="answer-bbb">
<div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
<div class="answer-text">答二</div>
</div>
"""


# ---------------------------------------------------------------------------
# audio_map2 chronological maps (chapter_question_ids keyed)
# ---------------------------------------------------------------------------


def _am2_seg(qids, index, start, end, status="manual", listened=False,
             audio="2024年3月1日Tai師父答疑.opus", aids=None):
    seg = {
        "index": index,
        "chapter_question_ids": qids,
        "chapter_indexes": [1] * len(qids),
        "start": start,
        "end": end,
        "start_label": f"00:00:{start:06.3f}" if start is not None else None,
        "end_label": f"00:00:{end:06.3f}" if end is not None else None,
        "confidence": 0.9,
        "status": status,
        "notes": "",
    }
    if aids:
        seg["chapter_answer_ids"] = list(aids)
    if listened:
        seg["meta"] = {"lastPlayed": "2026-08-24 11:00"}
    return seg


def _am2_dir(tmp_path: Path, sessions, name="2024-03.json") -> Path:
    d = tmp_path / "audio_map2"
    d.mkdir(parents=True, exist_ok=True)
    payload = {"month": "2024-03", "version": 1, "sessions": sessions}
    (d / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return d


def _am2_session(segments, audio="2024年3月1日Tai師父答疑.opus"):
    return {
        "session_id": "2024-03-01-main",
        "date": "2024-03-01",
        "audio_file": audio,
        "media_parts": [],
        "segments": segments,
    }


class TestAudioMap2Injection:
    def _seg(self, **kw):
        start = kw.pop("start", 10.0)
        end = kw.pop("end", 20.0)
        seg = _am2_seg(["question-aaa"], 1, start, end, **kw)
        return seg

    def test_review_state_gate(self):
        # Reviewed = human actually listened → meta.lastPlayed present
        assert _is_audio_map2_reviewed(self._seg(listened=True))
        # machine-aligned status does NOT count (no listened record)
        assert not _is_audio_map2_reviewed(self._seg(status="manual"))
        assert not _is_audio_map2_reviewed(self._seg(status="reviewed"))
        assert not _is_audio_map2_reviewed(self._seg(status="auto"))
        assert not _is_audio_map2_reviewed(self._seg(status="missing"))
        # listened but no start → no button
        assert not _is_audio_map2_reviewed(self._seg(listened=True, start=None))

    def test_loads_by_chapter_question_id(self, tmp_path):
        d = _am2_dir(tmp_path, [_am2_session([_am2_seg(["question-aaa"], 1, 10.0, 20.0)])])
        maps = load_word_maps_from_audio_map2(d)
        assert "question-aaa" in maps
        assert maps["question-aaa"]["start"] == 10.0
        assert maps["question-aaa"]["audio_file"] == "2024年3月1日Tai師父答疑.opus"

    def test_multiple_questions_share_one_segment(self, tmp_path):
        seg = _am2_seg(["question-aaa", "question-bbb"], 1, 10.0, 20.0)
        d = _am2_dir(tmp_path, [_am2_session([seg])])
        maps = load_word_maps_from_audio_map2(d)
        assert maps["question-aaa"]["start"] == maps["question-bbb"]["start"] == 10.0

    def test_inject_only_reviewed(self, tmp_path):
        segs = [
            _am2_seg(["question-aaa"], 1, 10.0, 20.0, listened=True),
            _am2_seg(["question-bbb"], 2, 30.0, 40.0),
        ]
        d = _am2_dir(tmp_path, [_am2_session(segs)])
        maps = load_word_maps_from_audio_map2(d)
        out = inject_word_html_from_audio_map2(WORD_CHAPTER, maps)
        assert out.count('class="qa-play qa-play--inline"') == 1
        # only question-aaa's answer gets an inline button after its answerer
        assert 'class="qa-number"' not in out
        head, _ = out.split('id="question-bbb"', 1)
        assert 'class="qa-play qa-play--inline"' in head

    def test_inject_word_chapters_defaults_to_audio_map2(self, tmp_path, monkeypatch):
        # monkeypatch the default dir to a temp audio_map2 directory
        d = _am2_dir(tmp_path, [_am2_session([_am2_seg(["question-aaa"], 1, 10.0, 20.0, listened=True)])])
        import core.audio_map_injector as ami
        monkeypatch.setattr(ami, "DEFAULT_AUDIO_MAP2_DIR", d)
        ch = Chapter(title="01", filename="01.html", content=WORD_CHAPTER)
        changed = inject_word_chapters([ch])
        assert changed == 1
        assert "qa-play" in ch.content

    def test_missing_dir_empty(self, tmp_path):
        assert load_word_maps_from_audio_map2(tmp_path / "nope") == {}
        from core.audio_map_injector import load_word_answer_maps_from_audio_map2
        assert load_word_answer_maps_from_audio_map2(tmp_path / "nope") == {}


class TestAnswerIdDisambiguation:
    """One Word question split by the ebook into two same-qid blocks in two
    chapters: each block must play its own half (chapter_answer_ids keyed)."""

    DUP_QID = "question-aaa"

    TWO_BLOCKS = """<h2 id="ch">章</h2>
<div class="question" id="question-aaa">
<div class="question-text">問一（前半）</div>
</div>
<div class="answer" id="answer-1">
<div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
<div class="answer-text">答一</div>
</div>
<hr/>
<div class="question" id="question-aaa">
<div class="question-text">問一（後半）</div>
</div>
<div class="answer" id="answer-2">
<div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
<div class="answer-text">答二</div>
</div>
"""

    def _two_segments(self):
        # Same chapter_question_ids entry (the ebook really reuses the qid);
        # only the answer ids tell the two blocks apart.
        return [
            _am2_seg([self.DUP_QID], 74, 10.5, 20.5, listened=True,
                     aids=["answer-1"]),
            _am2_seg([self.DUP_QID], 75, 30.5, 40.5, listened=True,
                     aids=["answer-2"]),
        ]

    def test_answer_map_keyed_by_answer_id(self, tmp_path):
        from core.audio_map_injector import load_word_answer_maps_from_audio_map2
        d = _am2_dir(tmp_path, [_am2_session(self._two_segments())])
        by_answer = load_word_answer_maps_from_audio_map2(d)
        assert set(by_answer) == {"answer-1", "answer-2"}
        assert by_answer["answer-1"]["start"] == 10.5
        assert by_answer["answer-2"]["start"] == 30.5

    def test_same_qid_two_blocks_play_own_half(self, tmp_path):
        d = _am2_dir(tmp_path, [_am2_session(self._two_segments())])
        maps = load_word_maps_from_audio_map2(d)
        from core.audio_map_injector import load_word_answer_maps_from_audio_map2
        by_answer = load_word_answer_maps_from_audio_map2(d)
        out = inject_word_html_from_audio_map2(self.TWO_BLOCKS, maps, by_answer)
        assert out.count('class="qa-play qa-play--inline"') == 2
        head, rest = out.split('id="answer-1"', 1)
        _, tail = rest.split('id="answer-2"', 1)
        assert 'data-start="10.500"' in head + rest.split('id="answer-2"')[0]
        assert 'data-start="30.500"' in tail

    def test_fallback_to_qid_without_answer_map(self, tmp_path):
        # Legacy call signature (no by_answer): both blocks fall back to the
        # qid map (first occurrence wins) — old behaviour preserved.
        d = _am2_dir(tmp_path, [_am2_session(self._two_segments())])
        maps = load_word_maps_from_audio_map2(d)
        out = inject_word_html_from_audio_map2(self.TWO_BLOCKS, maps)
        assert out.count('class="qa-play qa-play--inline"') == 2
        assert out.count('data-start="10.500"') == 2


class TestQuestionlessAnswerBlocks:
    """圖片題 /「問題丟失」block：沒有 ``<div class="question">``，只能靠自己的
    ``answer-…`` id（``chapter_answer_ids``）取得播放鈕。"""

    CHAPTER = """<h2 id="ch">章</h2>
<div class="question" id="question-aaa">
<div class="question-text">問一</div>
</div>
<div class="answer" id="answer-aaa">
<div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
<div class="answer-text">答一</div>
</div>
<hr/>
<img alt="心的选择：2025-03-12 18:42 师父，目前双盘只能一二十分钟" src="assets/images/x.png"/>
<div class="answer" id="answer-orphan">
<div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
<div class="answer-text">下一個問題，你的姿勢是挺好的。</div>
</div>
<hr/>
<div class="question" id="question-bbb">
<div class="question-text">問二</div>
</div>
<div class="answer" id="answer-bbb">
<div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
<div class="answer-text">答二</div>
</div>
"""

    def _orphan_seg(self, **kw):
        kw.setdefault("listened", True)
        kw.setdefault("start", 314.6)
        kw.setdefault("end", 415.37)
        return _am2_seg([], 4, kw["start"], kw["end"],
                        listened=kw["listened"],
                        audio="2025年3月12日Tai師父貼吧答疑.opus")

    def test_orphan_block_injected_from_answer_id_only(self):
        seg = self._orphan_seg()
        out = inject_word_html_from_audio_map2(
            self.CHAPTER, {}, by_answer={"answer-orphan": seg}
        )
        assert out.count('class="qa-play qa-play--inline"') == 1
        # the button belongs to the orphan block, with the orphan's own range
        head, tail = out.split('id="answer-orphan"', 1)
        assert 'data-start="314.600"' not in head
        assert 'data-start="314.600"' in tail
        assert 'data-end="415.370"' in tail
        # injected right after the orphan's own answerer name
        assert 'class="answerer">Taiguanglin</span><button' in tail

    def test_orphan_block_respects_review_gate(self):
        seg = self._orphan_seg(listened=False)
        out = inject_word_html_from_audio_map2(
            self.CHAPTER, {}, by_answer={"answer-orphan": seg}
        )
        assert "qa-play--inline" not in out

    def test_orphan_and_normal_block_coexist_once_each(self):
        normal = _am2_seg(["question-aaa"], 3, 10.0, 20.0, listened=True)
        orphan = self._orphan_seg()
        out = inject_word_html_from_audio_map2(
            self.CHAPTER, {"question-aaa": normal},
            by_answer={"answer-aaa": normal, "answer-orphan": orphan},
        )
        assert out.count('class="qa-play qa-play--inline"') == 2
        assert 'data-start="10.000"' in out
        assert 'data-start="314.600"' in out

    def test_idempotent(self):
        normal = _am2_seg(["question-aaa"], 3, 10.0, 20.0, listened=True)
        orphan = self._orphan_seg()
        maps = {"question-aaa": normal}
        by_answer = {"answer-aaa": normal, "answer-orphan": orphan}
        once = inject_word_html_from_audio_map2(self.CHAPTER, maps, by_answer)
        twice = inject_word_html_from_audio_map2(once, maps, by_answer)
        assert twice.count('class="qa-play qa-play--inline"') == 2
        assert once == twice

    def test_answerer_lookup_stays_inside_its_own_block(self):
        # An unreviewed orphan must not steal the next block's answerer span.
        orphan = self._orphan_seg(listened=False)
        out = inject_word_html_from_audio_map2(
            self.CHAPTER, {}, by_answer={"answer-orphan": orphan}
        )
        assert "qa-play--inline" not in out
        # the orphan's answerer stays untouched (no button spliced in)
        assert out.count('<span class="answerer">Taiguanglin</span></div>') == 3

    def test_base_id_fallback(self):
        html = self.CHAPTER.replace('id="answer-orphan"', 'id="answer-orphan-2"')
        seg = self._orphan_seg()
        out = inject_word_html_from_audio_map2(
            html, {}, by_answer={"answer-orphan": seg}
        )
        assert out.count('class="qa-play qa-play--inline"') == 1
        assert 'data-start="314.600"' in out


class TestWordSkipsPdfChapters:
    def test_pdf_month_chapter_not_stripped(self, tmp_path, monkeypatch):
        # A PDF chapter carries a date+source h2 and an already-injected inline
        # button from the PDF pass; the word pass must leave it untouched.
        pdf_chapter = """<h2 id="2025nian-6yue-9ri-tie-ba">2025年6月9日 贴吧</h2>
<div class="question" id="question-x">
<div class="question-text">q</div>
</div>
<div class="answer" id="answer-x">
<div class="answer-meta"><span class="answerer">Taiguanglin</span><button class="qa-play qa-play--inline" data-audio="../audio/x.opus" data-start="1.0" data-end="2.0" type="button">x</button></div>
<div class="answer-text">a</div>
</div>
"""
        d = _am2_dir(tmp_path, [_am2_session([_am2_seg(["question-x"], 1, 10.0, 20.0, listened=True)])])
        import core.audio_map_injector as ami
        monkeypatch.setattr(ami, "DEFAULT_AUDIO_MAP2_DIR", d)
        ch = Chapter(title="13", filename="13.html", content=pdf_chapter)
        changed = inject_word_chapters([ch])
        assert changed == 0
        # the PDF-pass inline button is preserved (not stripped by the word pass)
        assert ch.content.count("qa-play--inline") == 1


class TestSuffixedIdBaseFallback:
    """IDGenerator 對重複基底 id 追加 -2/-3 後綴；映射凍結的是基底 id → 未中時以基底重試。"""

    SUFFIXED = (
        WORD_CHAPTER
        .replace('id="question-aaa"', 'id="question-aaa-2"')
        .replace('id="answer-aaa"', 'id="answer-aaa-2"')
    )

    def test_by_qid_base_fallback(self):
        # 章節 HTML 的 id 帶去重後綴；audio_map2 凍結的是基底 qid → 仍應注入
        seg = _am2_seg(["question-aaa"], 1, 10.0, 20.0, listened=True)
        out = inject_word_html_from_audio_map2(self.SUFFIXED, {"question-aaa": seg})
        assert out.count('class="qa-play qa-play--inline"') == 1
        assert 'data-start="10.000"' in out

    def test_by_answer_base_fallback(self):
        # by_qid 兩層都未中 → 用 answer id 的基底重試 chapter_answer_ids
        seg = _am2_seg(["question-zzz"], 1, 30.0, 40.0, listened=True)
        out = inject_word_html_from_audio_map2(
            self.SUFFIXED, {"question-zzz": seg}, by_answer={"answer-aaa": seg}
        )
        assert out.count('class="qa-play qa-play--inline"') == 1
        assert 'data-start="30.000"' in out

    def test_exact_suffixed_hit_wins_over_base(self):
        # map 同時含後綴 id 與基底 id → 精確命中優先，不被基底遮蔽
        exact = _am2_seg(["question-aaa-2"], 1, 50.0, 60.0, listened=True)
        base = _am2_seg(["question-aaa"], 1, 10.0, 20.0, listened=True)
        out = inject_word_html_from_audio_map2(
            self.SUFFIXED, {"question-aaa-2": exact, "question-aaa": base}
        )
        assert 'data-start="50.000"' in out
        assert 'data-start="10.000"' not in out
