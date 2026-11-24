#!/usr/bin/env python3
"""span_audit 不得把短實念當 zero（L6[48] 回歸）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
from span_audit import zero_span  # noqa: E402


class SpanZeroTests(unittest.TestCase):
    def test_short_read_is_not_zero(self):
        self.assertFalse(zero_span(857.875, 858.760))

    def test_exact_or_negative_zero_width_is_zero(self):
        self.assertTrue(zero_span(1102.590, 1102.590))
        self.assertTrue(zero_span(10.0, 9.0))


if __name__ == "__main__":
    unittest.main()
