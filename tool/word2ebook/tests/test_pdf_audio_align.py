"""Unit tests for pdf_audio_map matching helpers (imported from sibling package)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PDF_AUDIO_MAP = Path(__file__).resolve().parents[2] / "pdf_audio_map"
sys.path.insert(0, str(PDF_AUDIO_MAP))

from common import (  # noqa: E402
    get_converter,
    match_ordered,
    match_start,
    normalize,
    resolve_media,
    spoken_name_variants,
    title_coverage,
)
from align import _interpolate_starts  # noqa: E402

CONV = get_converter()


class TestMatchStartOwner:
    def test_returns_cue_that_owns_match_not_window_start(self):
        """Window starting early must not steal a later cue's match time."""
        # Synthetic cues: filler then the real phrase
        cues = [
            (100.0, 110.0, normalize("只要贴吧不倒咱们继续发着玩", CONV)),
            (110.0, 120.0, normalize("从十五楼开始是正式问题", CONV)),
            (120.0, 130.0, normalize("牧羊少年五七幺这位朋友问是不是人的三观和思维方式", CONV)),
        ]
        needle = normalize("的三观和思维方式", CONV)
        start, idx, size = match_start(cues, 0, needle, min_len=4, min_block=4)
        assert idx == 2
        assert abs(start - 120.0) < 0.01
        assert size >= 6

    def test_spoken_name_variants_include_yao(self):
        variants = spoken_name_variants("牧羊少年571", CONV)
        assert any("五七幺" in v or "五七一" in v for v in variants)

    def test_year_digits_not_expanded_into_date_words(self):
        variants = spoken_name_variants("明月2025", CONV)
        joined = " ".join(variants)
        assert "二零二五" not in joined
        assert any("2025" in v for v in variants)


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
