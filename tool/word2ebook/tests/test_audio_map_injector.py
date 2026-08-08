"""Tests for audio_map injection and shared play markup."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.audio_map_injector import inject_chapters, inject_html, load_maps
from core.qa_play_markup import audio_url, render_play, render_segment_meta_bar
from models.document_models import Chapter


SAMPLE_SECTION = """
<h2 id="2025nian-11yue-10ri-guan-wang">2025年11月10日 官网<span class="chapter-qa-count">(2)</span></h2>
<p id="content-abc">今天是开场。</p>
<div class="question" id="question-aaa">
<div class="question-meta">
<span class="questioner">甲</span>
<span class="question-time">2025-01-01 00:00</span>
</div>
<div class="question-text">问题一内容</div>
</div>
<div class="answer" id="answer-aaa">
<div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
<div class="answer-text">答一</div>
</div>
<div class="question" id="question-bbb">
<div class="question-text">问题二内容</div>
</div>
<div class="answer" id="answer-bbb">
<div class="answer-meta"><span class="answerer">Taiguanglin</span></div>
<div class="answer-text">答二</div>
</div>
<p id="content-closing">今天就回答到这里。</p>
"""


def _session(**overrides):
    base = {
        "session_id": "2025-11-10-guanwang",
        "section_id": "2025nian-11yue-10ri-guan-wang",
        "audio_file": "2025年11月10日Tai師父官網答疑.opus",
        "opening": {
            "start": 1.0,
            "end": 10.0,
            "start_label": "00:00:01.000",
            "end_label": "00:00:10.000",
            "status": "auto",
        },
        "segments": [
            {
                "index": 1,
                "question_id": "question-aaa",
                "start": 10.0,
                "end": 20.5,
                "start_label": "00:00:10.000",
                "end_label": "00:00:20.500",
                "status": "from_qa_txt",
                "meta": {"lastPlayed": "2026-08-01 12:00"},
            },
            {
                "index": 2,
                "question_id": "question-bbb",
                "start": None,
                "end": None,
                "status": "missing",
            },
        ],
        "closing": {
            "text": "今天就回答到这里。",
            "text_preview": "今天就回答到这里。",
            "start": 30.0,
            "end": 40.0,
            "start_label": "00:00:30.000",
            "end_label": "00:00:40.000",
            "status": "auto",
        },
    }
    base.update(overrides)
    return base


class TestQaPlayMarkup:
    def test_audio_url_percent_encodes(self):
        url = audio_url("2025年11月10日Tai師父官網答疑.opus")
        assert url.startswith("../audio/")
        assert "%E5%B9%B4" in url  # 年
        assert " " not in url

    def test_hide_missing_returns_none(self):
        assert render_play(None, "../audio/x.opus", disabled_if_missing=False) is None
        assert render_segment_meta_bar("1", None, "../audio/x.opus", hide_if_missing=True) == ""

    def test_disabled_when_allowed(self):
        html = render_play(None, "../audio/x.opus", disabled_if_missing=True)
        assert "qa-play--disabled" in html
        assert "qa-play-speaker" in html

    def test_display_label_is_hms_without_ms(self):
        from core.qa_play_markup import format_hms, format_range_label

        assert format_hms(20.5) == "00:00:20"
        assert format_range_label(10.0, 20.5) == "00:00:10 - 00:00:20"
        html = render_play((10.0, 20.5, "ignored"), "../audio/x.opus")
        assert "qa-play-speaker" in html
        assert 'data-label="00:00:10 - 00:00:20"' in html
        assert ">00:00:10 - 00:00:20<" in html
        assert 'data-start="10.000"' in html  # playback attrs keep precision
        assert 'data-end="20.500"' in html
        assert ".500" not in html.split('data-label="')[1].split('"')[0]


class TestInjectHtml:
    def test_injects_opening_and_matched_question_only(self):
        by_section = {"2025nian-11yue-10ri-guan-wang": _session()}
        out = inject_html(SAMPLE_SECTION, by_section)
        assert 'class="qa-meta-bar qa-meta-bar--opening"' in out
        assert out.count('button class="qa-play"') == 2  # opening + q1 (listened)
        assert 'data-start="10.000"' in out
        assert 'data-end="20.500"' in out
        # question-bbb is missing → no meta bar immediately before it
        idx_b = out.index('id="question-bbb"')
        before = out[max(0, idx_b - 120) : idx_b]
        assert "qa-meta-bar" not in before

    def test_hides_unlistened_segment_even_with_range(self):
        session = _session(
            segments=[
                {
                    "index": 1,
                    "question_id": "question-aaa",
                    "start": 10.0,
                    "end": 20.5,
                    "start_label": "00:00:10.000",
                    "end_label": "00:00:20.500",
                    "status": "manual",
                    # no meta.lastPlayed
                },
                {
                    "index": 2,
                    "question_id": "question-bbb",
                    "start": 20.5,
                    "end": 30.0,
                    "start_label": "00:00:20.500",
                    "end_label": "00:00:30.000",
                    "status": "manual",
                    "meta": {"lastPlayed": "2026-08-01 12:00"},
                },
            ]
        )
        out = inject_html(SAMPLE_SECTION, {"2025nian-11yue-10ri-guan-wang": session})
        # First segment not listened → no opening, no play before question-aaa
        assert "qa-meta-bar--opening" not in out
        idx_a = out.index('id="question-aaa"')
        before_a = out[max(0, idx_a - 160) : idx_a]
        assert "qa-play" not in before_a
        # Second segment listened → play before question-bbb
        idx_b = out.index('id="question-bbb"')
        before_b = out[max(0, idx_b - 800) : idx_b]
        assert 'class="qa-play"' in before_b
        assert out.count('button class="qa-play"') == 1

    def test_opening_follows_first_segment_listened(self):
        session = _session(
            segments=[
                {
                    "index": 1,
                    "question_id": "question-aaa",
                    "start": 10.0,
                    "end": 20.5,
                    "start_label": "00:00:10.000",
                    "end_label": "00:00:20.500",
                    "status": "manual",
                    "meta": {"lastPlayed": "2026-08-01 12:00"},
                },
                {
                    "index": 2,
                    "question_id": "question-bbb",
                    "start": 20.5,
                    "end": 30.0,
                    "start_label": "00:00:20.500",
                    "end_label": "00:00:30.000",
                    "status": "manual",
                    # unlistened
                },
            ]
        )
        out = inject_html(SAMPLE_SECTION, {"2025nian-11yue-10ri-guan-wang": session})
        assert "qa-meta-bar--opening" in out
        assert out.count('button class="qa-play"') == 2  # opening + q1 only
        assert "qa-meta-bar--closing" not in out

    def test_closing_requires_own_listen(self):
        session = _session(
            segments=[
                {
                    "index": 1,
                    "question_id": "question-aaa",
                    "start": 10.0,
                    "end": 20.5,
                    "status": "manual",
                    "meta": {"lastPlayed": "2026-08-01 12:00"},
                },
                {
                    "index": 2,
                    "question_id": "question-bbb",
                    "start": 20.5,
                    "end": 30.0,
                    "status": "manual",
                    "meta": {"lastPlayed": "2026-08-01 12:01"},
                },
            ],
            closing={
                "text": "今天就回答到这里。",
                "start": 30.0,
                "end": 40.0,
                "status": "auto",
                "meta": {"lastPlayed": "2026-08-01 12:02"},
            },
        )
        out = inject_html(SAMPLE_SECTION, {"2025nian-11yue-10ri-guan-wang": session})
        assert "qa-meta-bar--closing" in out
        assert "收場" in out
        assert 'data-start="30.000"' in out
        # unlistened closing → no bar
        session2 = _session(
            segments=session["segments"],
            closing={
                "text": "今天就回答到这里。",
                "start": 30.0,
                "end": 40.0,
                "status": "auto",
            },
        )
        out2 = inject_html(SAMPLE_SECTION, {"2025nian-11yue-10ri-guan-wang": session2})
        assert "qa-meta-bar--closing" not in out2

    def test_idempotent(self):
        by_section = {"2025nian-11yue-10ri-guan-wang": _session()}
        once = inject_html(SAMPLE_SECTION, by_section)
        twice = inject_html(once, by_section)
        assert once.count("qa-meta-bar") == twice.count("qa-meta-bar")

    def test_inject_chapters(self, tmp_path: Path):
        map_dir = tmp_path / "maps"
        map_dir.mkdir()
        import json

        (map_dir / "2025-11.json").write_text(
            json.dumps({"month": "2025-11", "sessions": [_session()]}, ensure_ascii=False),
            encoding="utf-8",
        )
        ch = Chapter(title="t", filename="17.html", content=SAMPLE_SECTION)
        assert inject_chapters([ch], map_dir=map_dir) == 1
        assert "qa-play" in ch.content


class TestLoadMaps:
    def test_empty_dir(self, tmp_path: Path):
        assert load_maps(tmp_path) == {}
