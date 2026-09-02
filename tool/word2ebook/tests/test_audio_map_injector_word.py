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
             audio="2024年3月1日Tai師父答疑.opus"):
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
