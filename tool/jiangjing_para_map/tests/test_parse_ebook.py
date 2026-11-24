#!/usr/bin/env python3
"""parse_ebook 的巢狀 sutra-pin 包層與全系列 pid/text 契約。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "jiangjing_para_map"))
from build_maps import SERIES, parse_ebook  # noqa: E402


class ParseEbookTests(unittest.TestCase):
    def test_nested_pin_wrappers_keep_all_blocks_in_document_order(self):
        html = """<html><body>
        <h2 id="x">壇經<button data-audio="/audio/jiangjing/demo.opus" data-end="9.5">▶</button></h2>
        <div class="sutra-pin-group"><div class="sutra-pin-host">
          <div class="sutra-text para-block" id="p-saaaaaaa1">第一段<br>同一行</div>
          <div class="sutra-text para-block" id="p-saaaaaaa2">第二段</div>
        </div></div>
        <p class="para-block" id="p-saaaaaaa3">第三<span>段</span></p>
        </body></html>"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "demo.html"
            path.write_text(html, encoding="utf-8")
            lectures = parse_ebook(path)
        self.assertEqual(len(lectures), 1)
        ps = lectures[0]["paragraphs"]
        self.assertEqual([p["pid"] for p in ps],
                         ["p-saaaaaaa1", "p-saaaaaaa2", "p-saaaaaaa3"])
        self.assertEqual([p["text"] for p in ps], ["第一段同一行", "第二段", "第三段"])
        self.assertIn("sutra-text", ps[0]["cls"])

    def test_all_series_pid_and_text_match_source_of_truth(self):
        compared = 0
        for series, cfg in SERIES.items():
            doc = json.loads((ROOT / "audio_map3" / f"{series}.json").read_text(encoding="utf-8"))
            ebook = ROOT / cfg["ebook"]
            by_base = {x["basename"]: x for x in parse_ebook(ebook)}
            for number, lecture in doc["lectures"].items():
                with self.subTest(series=series, lecture=number):
                    parsed = by_base[lecture["audio"][:-5]]["paragraphs"]
                    mapped = lecture["paragraphs"]
                    self.assertEqual(len(parsed), len(mapped))
                    for expected, actual in zip(mapped, parsed):
                        self.assertEqual(expected["pid"], actual["pid"])
                        self.assertEqual(expected["text"], actual["text"])
                    compared += len(mapped)
        self.assertEqual(compared, 11772)


if __name__ == "__main__":
    unittest.main()
