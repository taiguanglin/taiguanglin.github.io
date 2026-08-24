"""Tests for word-chapter audio map injection (question-id keyed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.audio_map_injector import (
    inject_word_chapters,
    inject_word_html,
    load_word_maps,
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


def _seg(qid, index, start, end, audio="2024年3月1日Tai師父答疑.opus", confirmed=True):
    seg = {
        "index": index,
        "question_id": qid,
        "stable_key": f"01#q{index}",
        "audio_file": audio,
        "start": start,
        "end": end,
        "start_label": f"00:00:{start:06.3f}" if start is not None else None,
        "end_label": f"00:00:{end:06.3f}" if end is not None else None,
        "confidence": 0.9,
        "status": "auto",
        "locked": False,
        "notes": "",
    }
    if confirmed:
        seg["meta"] = {"confirmed": "2026-08-24 12:00"}
    return seg


def _map_dir(tmp_path: Path, segments, name="word-01.json") -> Path:
    d = tmp_path / "audio_map_word"
    d.mkdir(parents=True, exist_ok=True)
    payload = {"book": "word", "chapter": "01", "version": 1, "segments": segments}
    (d / name).write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return d


class TestLoadWordMaps:
    def test_loads_by_question_id(self, tmp_path):
        d = _map_dir(tmp_path, [_seg("question-aaa", 1, 10.0, 20.0)])
        maps = load_word_maps(d)
        assert "question-aaa" in maps
        assert maps["question-aaa"]["start"] == 10.0

    def test_merges_files_and_first_wins(self, tmp_path):
        _map_dir(tmp_path, [_seg("question-aaa", 1, 10.0, 20.0)], "word-01.json")
        _map_dir(tmp_path, [_seg("question-aaa", 1, 99.0, 100.0)], "word-02.json")
        maps = load_word_maps(tmp_path / "audio_map_word")
        assert maps["question-aaa"]["start"] == 10.0

    def test_missing_dir_returns_empty(self, tmp_path):
        assert load_word_maps(tmp_path / "nope") == {}

    def test_invalid_json_skipped(self, tmp_path):
        d = tmp_path / "audio_map_word"
        d.mkdir()
        (d / "word-01.json").write_text("{broken", encoding="utf-8")
        assert load_word_maps(d) == {}


class TestInjectWordHtml:
    def test_inserts_bar_before_mapped_question(self, tmp_path):
        d = _map_dir(tmp_path, [_seg("question-aaa", 1, 10.0, 20.0)])
        maps = load_word_maps(d)
        out = inject_word_html(WORD_CHAPTER, maps)
        assert '<button class="qa-play"' in out
        # bar sits before the question div
        assert out.index('qa-meta-bar') < out.index('<div class="question" id="question-aaa">')
        assert "data-start=&quot;10.000&quot;" in out or 'data-start="10.000' in out

    def test_unmapped_question_gets_no_bar(self, tmp_path):
        d = _map_dir(tmp_path, [_seg("question-aaa", 1, 10.0, 20.0)])
        maps = load_word_maps(d)
        out = inject_word_html(WORD_CHAPTER, maps)
        head, tail = out.split('id="question-bbb"', 1)
        assert "qa-play" not in tail[:200]

    def test_idempotent_second_run(self, tmp_path):
        d = _map_dir(tmp_path, [_seg("question-aaa", 1, 10.0, 20.0)])
        maps = load_word_maps(d)
        once = inject_word_html(WORD_CHAPTER, maps)
        twice = inject_word_html(once, maps)
        assert once == twice

    def test_existing_pdf_bar_not_duplicated(self):
        content = WORD_CHAPTER.replace(
            '<div class="question" id="question-aaa">',
            '<div class="qa-meta-bar qa-meta-bar--opening"><button class="qa-play"></button></div>\n'
            '<div class="question" id="question-aaa">',
            1,
        )
        maps = {"question-aaa": _seg("question-aaa", 1, 10.0, 20.0)}
        out = inject_word_html(content, maps)
        assert out.count('<div class="qa-meta-bar') == 1

    def test_missing_range_renders_nothing(self, tmp_path):
        seg = _seg("question-aaa", 1, None, None)
        seg["start"] = None
        seg["end"] = None
        seg["status"] = "missing"
        d = _map_dir(tmp_path, [seg])
        maps = load_word_maps(d)
        out = inject_word_html(WORD_CHAPTER, maps)
        assert "qa-play" not in out

    def test_review_status_renders_no_button(self, tmp_path):
        d = _map_dir(tmp_path, [_seg("question-aaa", 1, 10.0, 20.0)])
        maps = load_word_maps(d)
        maps["question-aaa"]["status"] = "review"
        out = inject_word_html(WORD_CHAPTER, maps)
        assert "qa-play" not in out

    def test_unconfirmed_auto_renders_no_button(self, tmp_path):
        d = _map_dir(tmp_path, [_seg("question-aaa", 1, 10.0, 20.0)])
        maps = load_word_maps(d)
        del maps["question-aaa"]["meta"]["confirmed"]
        out = inject_word_html(WORD_CHAPTER, maps)
        assert "qa-play" not in out

    def test_lastplayed_counts_as_confirmed(self, tmp_path):
        d = _map_dir(tmp_path, [_seg("question-aaa", 1, 10.0, 20.0)])
        maps = load_word_maps(d)
        del maps["question-aaa"]["meta"]["confirmed"]
        maps["question-aaa"]["meta"]["lastPlayed"] = "2026-08-24 11:00"
        out = inject_word_html(WORD_CHAPTER, maps)
        assert '<button class="qa-play"' in out

    def test_none_status_renders_no_button(self, tmp_path):
        seg = _seg("question-aaa", 1, None, None)
        seg["status"] = "none"  # human-confirmed: no audio exists
        d = _map_dir(tmp_path, [seg])
        maps = load_word_maps(d)
        out = inject_word_html(WORD_CHAPTER, maps)
        assert "qa-play" not in out


class TestInjectWordChapters:
    def test_chapter_modified_count(self, tmp_path):
        d = _map_dir(tmp_path, [_seg("question-aaa", 1, 10.0, 20.0)])
        ch = Chapter(
            title="01自性与意识",
            filename="01.html",
            content=WORD_CHAPTER,
        )
        changed = inject_word_chapters([ch], d)
        assert changed == 1
        assert "qa-play" in ch.content

    def test_chapter_without_questions_untouched(self, tmp_path):
        d = _map_dir(tmp_path, [_seg("question-aaa", 1, 10.0, 20.0)])
        ch = Chapter(title="前言", filename="00.html", content="<p>无问答</p>")
        assert inject_word_chapters([ch], d) == 0

    def test_empty_map_dir_noop(self, tmp_path):
        ch = Chapter(title="01", filename="01.html", content=WORD_CHAPTER)
        assert inject_word_chapters([ch], tmp_path / "nope") == 0
