#!/usr/bin/env python3
"""clip_probe 的標點／timestamp 對齊回歸（L11 長洞實證）。"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "clip_probe.py"
SPEC = importlib.util.spec_from_file_location("clip_probe_under_test", SCRIPT)
clip = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(clip)


class ClipTimestampAlignmentTests(unittest.TestCase):
    def test_filters_punctuation_before_indexing_timestamps(self):
        item = {"text": "達，啊。如", "timestamp": [[100, 200], [300, 400], [500, 600]]}
        buf, mode, warning = clip.aligned_clip_chars(item, 10.0)
        self.assertEqual(mode, "filtered-punctuation")
        self.assertIsNone(warning)
        self.assertEqual(buf, [(10.1, "達"), (10.3, "啊"), (10.5, "如")])

    def test_accepts_timestamp_that_includes_punctuation(self):
        item = {"text": "達，啊", "timestamp": [[100, 200], [200, 300], [300, 400]]}
        buf, mode, warning = clip.aligned_clip_chars(item, 10.0)
        self.assertEqual(mode, "raw-timestamp-includes-punctuation")
        self.assertIsNone(warning)
        self.assertEqual(buf, [(10.1, "達"), (10.2, "，"), (10.3, "啊")])

    def test_count_mismatch_invalidates_all_times_instead_of_shifting(self):
        item = {"text": "達，啊。如", "timestamp": [[100, 200]]}
        buf, mode, warning = clip.aligned_clip_chars(item, 10.0)
        self.assertEqual(mode, "invalid")
        self.assertIn("count mismatch", warning)
        self.assertEqual(buf, [(None, "達"), (None, "啊"), (None, "如")])

    def test_empty_input_is_valid_and_has_no_times(self):
        buf, mode, warning = clip.aligned_clip_chars({"text": "", "timestamp": []}, 0.0)
        self.assertEqual(buf, [])
        self.assertEqual(mode, "filtered-punctuation")
        self.assertIsNone(warning)


if __name__ == "__main__":
    unittest.main()
