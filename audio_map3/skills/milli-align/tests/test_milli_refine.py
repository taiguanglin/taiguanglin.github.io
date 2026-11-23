#!/usr/bin/env python3
"""milli_refine 的 zero 鏈與單調安全網回歸測試（標準庫 unittest）。"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "milli_refine.py"
SPEC = importlib.util.spec_from_file_location("milli_refine_under_test", SCRIPT)
refine = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(refine)


def para(start, end, *, zero=False, confirmed=False):
    p = {"pid": f"p-{start}-{end}", "text": "測試", "start": start,
         "end": end, "conf": 0.8, "method": "ngram"}
    if zero:
        p["zero"] = True
    if confirmed:
        p["confirmed"] = True
    return p


class MilliRefineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / "demo.json"
        self.table = self.root / "table.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write_doc(self, paragraphs):
        doc = {
            "series": "demo", "generated_at": "test",
            "lectures": {
                "1": {"duration": 30.0, "reviewed": False, "paragraphs": paragraphs},
                "2": {"duration": 5.0, "reviewed": True,
                      "paragraphs": [para(0.0, 5.0, confirmed=True)]},
            },
        }
        self.path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

    def apply(self, table):
        self.table.write_text(json.dumps(table), encoding="utf-8")
        argv = ["milli_refine.py", "--series", "demo", "--lecture", "1",
                "--table", str(self.table), "--apply"]
        with patch.object(refine, "AMAP_DIR", self.root), patch.object(sys, "argv", argv):
            with contextlib.redirect_stdout(io.StringIO()):
                refine.main()

    def test_read_to_zero_leaves_no_wide_zero_and_is_idempotent(self):
        self.write_doc([para(0.0, 10.0), para(10.0, 20.0), para(20.0, 30.0)])
        other_before = json.loads(self.path.read_text())["lectures"]["2"]
        table = [{"i": 1, "start": 10.0, "zero": True},
                 {"i": 2, "start": 15.0, "zero": False}]
        self.apply(table)
        doc = json.loads(self.path.read_text())
        ps = doc["lectures"]["1"]["paragraphs"]
        self.assertEqual((ps[0]["start"], ps[0]["end"]), (0.0, 15.0))
        self.assertEqual((ps[1]["start"], ps[1]["end"]), (15.0, 15.0))
        self.assertTrue(ps[1]["zero"])
        self.assertEqual((ps[2]["start"], ps[2]["end"]), (15.0, 30.0))
        self.assertEqual(doc["lectures"]["2"], other_before)
        second = self.path.read_text(encoding="utf-8")
        self.apply(table)
        self.assertEqual(self.path.read_text(encoding="utf-8"), second)

    def test_preserve_end_allows_documented_overlap_and_is_idempotent(self):
        self.write_doc([para(0.0, 10.0), para(10.0, 20.0), para(20.0, 30.0)])
        table = [{"i": 0, "start": 0.0, "end": 12.0, "preserve_end": True,
                  "note": "音訊插講交疊 2 秒"},
                 {"i": 1, "start": 10.0, "zero": False}]
        self.apply(table)
        ps = json.loads(self.path.read_text())["lectures"]["1"]["paragraphs"]
        self.assertEqual((ps[0]["start"], ps[0]["end"]), (0.0, 12.0))
        self.assertEqual((ps[1]["start"], ps[1]["end"]), (10.0, 20.0))
        second = self.path.read_text(encoding="utf-8")
        self.apply(table)
        self.assertEqual(self.path.read_text(encoding="utf-8"), second)

    def test_new_inversion_behind_confirmed_zero_aborts_without_write(self):
        self.write_doc([para(0.0, 10.0), para(10.0, 10.0, zero=True, confirmed=True),
                        para(20.0, 30.0)])
        before = self.path.read_text(encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self.apply([{"i": 2, "start": 5.0, "zero": False}])
        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
