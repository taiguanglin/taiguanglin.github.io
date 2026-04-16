"""Tests for utils/file_utils.py"""

import pytest
from pathlib import Path
from utils.file_utils import safe_filename, FileManager, ImageHandler


# ---------------------------------------------------------------------------
# safe_filename
# ---------------------------------------------------------------------------

class TestSafeFilename:
    def test_zero_padded_index(self):
        assert safe_filename("任何標題", 1) == "01.html"
        assert safe_filename("任何標題", 9) == "09.html"
        assert safe_filename("任何標題", 10) == "10.html"

    def test_html_extension(self):
        assert safe_filename("Chapter", 5).endswith(".html")


# ---------------------------------------------------------------------------
# FileManager
# ---------------------------------------------------------------------------

class TestFileManager:
    def test_setup_creates_directory_structure(self, tmp_path):
        fm = FileManager(tmp_path / "out")
        fm.setup_output_directory(clean_existing=False)

        assert (tmp_path / "out").exists()
        assert (tmp_path / "out" / "assets" / "css").exists()
        assert (tmp_path / "out" / "assets" / "js").exists()
        assert (tmp_path / "out" / "assets" / "images").exists()

    def test_clean_existing_removes_contents(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        existing = out / "old_file.txt"
        existing.write_text("old")

        fm = FileManager(out)
        fm.setup_output_directory(clean_existing=True)

        assert not existing.exists()

    def test_write_file_creates_file(self, tmp_path):
        fm = FileManager(tmp_path / "out")
        fm.setup_output_directory(clean_existing=False)
        fm.write_file("assets/css/style.css", "body { color: red; }")

        result = (tmp_path / "out" / "assets" / "css" / "style.css").read_text()
        assert "body { color: red; }" in result

    def test_write_binary_file(self, tmp_path):
        fm = FileManager(tmp_path / "out")
        fm.setup_output_directory(clean_existing=False)
        fm.write_binary_file("assets/js/test.wasm", b"\x00\x01\x02")

        data = (tmp_path / "out" / "assets" / "js" / "test.wasm").read_bytes()
        assert data == b"\x00\x01\x02"

    def test_file_exists_true(self, tmp_path):
        fm = FileManager(tmp_path / "out")
        fm.setup_output_directory(clean_existing=False)
        fm.write_file("test.html", "<html/>")
        assert fm.file_exists("test.html") is True

    def test_file_exists_false(self, tmp_path):
        fm = FileManager(tmp_path / "out")
        fm.setup_output_directory(clean_existing=False)
        assert fm.file_exists("nonexistent.html") is False

    def test_get_file_path(self, tmp_path):
        fm = FileManager(tmp_path / "out")
        p = fm.get_file_path("assets/css/style.css")
        assert p == tmp_path / "out" / "assets" / "css" / "style.css"

    def test_get_assets_path(self, tmp_path):
        fm = FileManager(tmp_path / "out")
        p = fm.get_assets_path("images")
        assert p == tmp_path / "out" / "assets" / "images"

    def test_copy_file(self, tmp_path):
        src = tmp_path / "source.txt"
        src.write_text("hello")
        fm = FileManager(tmp_path / "out")
        fm.setup_output_directory(clean_existing=False)
        fm.copy_file(src, "copied.txt")
        assert (tmp_path / "out" / "copied.txt").read_text() == "hello"

    def test_incremental_keeps_existing_file(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        existing = out / "keep_me.txt"
        existing.write_text("preserve")

        fm = FileManager(out)
        fm.setup_output_directory(clean_existing=False)

        assert existing.read_text() == "preserve"
