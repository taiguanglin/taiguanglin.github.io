"""Unit tests for pdf_audio_map matching helpers (imported from sibling package)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PDF_AUDIO_MAP = Path(__file__).resolve().parents[2] / "pdf_audio_map"
sys.path.insert(0, str(PDF_AUDIO_MAP))

from common import get_converter, match_ordered, normalize, resolve_media, title_coverage  # noqa: E402
from align import _interpolate_starts  # noqa: E402

CONV = get_converter()


class TestTitleCoverage:
    def test_short_title_inside_long_question(self):
        title = normalize("未斷淫慾為何不可入初禪", CONV)
        question = normalize(
            "1、Tai师好！未断淫欲不可入初禅的原因是什么呢？打坐到四个小时就可自动练精化气么？",
            CONV,
        )
        assert title_coverage(title, question) >= 0.45


class TestMatchOrdered:
    def test_ordered_coverage_match(self):
        titles = [
            normalize("未斷淫慾為何不可入初禪", CONV),
            normalize("上坐前有無建議的預備動作", CONV),
        ]
        pdfs = [
            normalize("1、Tai师好！未断淫欲不可入初禅的原因是什么呢？", CONV),
            normalize("无关问题abcdef", CONV),
            normalize("2、末学想问，上坐前有无建议的预备动作，更重要的是什么", CONV),
        ]
        mapping = match_ordered(titles, pdfs, min_ratio=0.4, scorer=title_coverage, window=8)
        assert mapping[0] == 0
        assert mapping[1] == 2


class TestResolveMedia:
    def test_guanwang_falls_back_to_tieba_when_missing(self):
        m = resolve_media(2025, 8, 8, "官网")
        assert m["fallback_from"] == "官網"
        assert m["resolved_source"] == "貼吧"
        assert "貼吧" in m["audio_file"]
        assert m["srt_exists"]

    def test_guanwang_keeps_primary_when_present(self):
        m = resolve_media(2025, 11, 10, "官网")
        assert m["fallback_from"] is None
        assert "官網" in m["audio_file"]


class TestInterpolate:
    def test_fills_interior_gap(self):
        starts = [10.0, None, None, 40.0]
        scores = [8.0, 0.0, 0.0, 8.0]
        resolved, notes = _interpolate_starts(starts, scores, 100.0)
        assert resolved[0] == 10.0
        assert resolved[-1] == 40.0
        assert 10.0 < resolved[1] < resolved[2] < 40.0
        assert "interpolated" in notes[1]
