"""Tests for utils/favicon_utils.py"""

import shutil
import pytest
from pathlib import Path

from utils.favicon_utils import FaviconManager, process_favicon_for_conversion


@pytest.fixture
def source_dir(tmp_path):
    return tmp_path / "source"


@pytest.fixture
def output_dir(tmp_path):
    d = tmp_path / "output"
    d.mkdir()
    return d


@pytest.fixture
def fake_input_file(source_dir):
    source_dir.mkdir()
    f = source_dir / "book.docx"
    f.touch()
    return f


class TestFaviconManager:
    def test_find_favicon_finds_ico(self, fake_input_file, source_dir, output_dir):
        ico = source_dir / "favicon.ico"
        ico.write_bytes(b"\x00\x00\x01\x00")  # minimal ICO header
        mgr = FaviconManager(fake_input_file, output_dir)
        result = mgr.find_favicon()
        assert result == ico

    def test_find_favicon_returns_none_when_missing(self, fake_input_file, output_dir):
        mgr = FaviconManager(fake_input_file, output_dir)
        result = mgr.find_favicon()
        assert result is None

    def test_find_favicon_priority_ico_over_png(self, fake_input_file, source_dir, output_dir):
        (source_dir / "favicon.ico").write_bytes(b"\x00")
        (source_dir / "favicon.png").write_bytes(b"\x89PNG")
        mgr = FaviconManager(fake_input_file, output_dir)
        found = mgr.find_favicon()
        assert found.suffix == ".ico"

    def test_copy_favicon_without_find_returns_false(self, fake_input_file, output_dir):
        mgr = FaviconManager(fake_input_file, output_dir)
        assert mgr.copy_favicon_to_output() is False

    def test_copy_favicon_copies_file(self, fake_input_file, source_dir, output_dir):
        ico = source_dir / "favicon.ico"
        ico.write_bytes(b"\x01\x02")
        mgr = FaviconManager(fake_input_file, output_dir)
        mgr.find_favicon()
        result = mgr.copy_favicon_to_output()
        assert result is True
        assert (output_dir / "favicon.ico").exists()

    def test_get_favicon_html_tag_ico(self, fake_input_file, source_dir, output_dir):
        ico = source_dir / "favicon.ico"
        ico.write_bytes(b"\x00")
        mgr = FaviconManager(fake_input_file, output_dir)
        mgr.find_favicon()
        tag = mgr.get_favicon_html_tag()
        assert 'image/x-icon' in tag
        assert 'favicon.ico' in tag

    def test_get_favicon_html_tag_png(self, fake_input_file, source_dir, output_dir):
        png = source_dir / "favicon.png"
        png.write_bytes(b"\x89PNG")
        mgr = FaviconManager(fake_input_file, output_dir, search_patterns=["favicon.png"])
        mgr.find_favicon()
        tag = mgr.get_favicon_html_tag()
        assert 'image/png' in tag

    def test_get_favicon_html_tag_svg(self, fake_input_file, source_dir, output_dir):
        svg = source_dir / "favicon.svg"
        svg.write_text("<svg/>")
        mgr = FaviconManager(fake_input_file, output_dir, search_patterns=["favicon.svg"])
        mgr.find_favicon()
        tag = mgr.get_favicon_html_tag()
        assert 'image/svg+xml' in tag

    def test_get_favicon_html_tag_empty_when_no_favicon(self, fake_input_file, output_dir):
        mgr = FaviconManager(fake_input_file, output_dir)
        assert mgr.get_favicon_html_tag() == ""

    def test_process_favicon_full_flow(self, fake_input_file, source_dir, output_dir):
        ico = source_dir / "favicon.ico"
        ico.write_bytes(b"\x00")
        mgr = FaviconManager(fake_input_file, output_dir)
        tag = mgr.process_favicon()
        assert "favicon.ico" in tag
        assert (output_dir / "favicon.ico").exists()


class TestProcessFaviconConvenienceFunction:
    def test_returns_empty_when_no_favicon(self, fake_input_file, output_dir):
        tag = process_favicon_for_conversion(fake_input_file, output_dir)
        assert tag == ""

    def test_returns_tag_when_favicon_present(self, fake_input_file, source_dir, output_dir):
        ico = source_dir / "favicon.ico"
        ico.write_bytes(b"\x00")
        tag = process_favicon_for_conversion(fake_input_file, output_dir)
        assert "favicon.ico" in tag
