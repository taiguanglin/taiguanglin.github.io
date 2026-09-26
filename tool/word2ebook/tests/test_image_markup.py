"""Tests for utils/image_markup.py"""

import struct

import pytest

from utils.image_markup import (
    png_dimensions,
    jpeg_dimensions,
    image_dimensions,
    render_img_tag,
    alt_from_context,
)



def _write_png(path, width, height):
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">I", 13) + b"IHDR" + struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(sig + ihdr + b"\x00\x00\x00\x00")


class TestPngDimensions:
    def test_reads_png_dimensions(self, tmp_path):
        f = tmp_path / "a.png"
        _write_png(f, 640, 480)
        assert png_dimensions(f) == (640, 480)

    def test_non_png_returns_none(self, tmp_path):
        f = tmp_path / "b.png"
        f.write_bytes(b"not a png at all........")
        assert png_dimensions(f) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert png_dimensions(tmp_path / "nope.png") is None


class TestRenderImgTag:
    def test_lazy_and_alt_present(self):
        tag = render_img_tag("assets/images/image_1.png", "打坐姿勢配圖")
        assert tag.startswith('<img loading="lazy" src="assets/images/image_1.png"')
        assert 'alt="打坐姿勢配圖"' in tag
        assert 'width=' not in tag  # 無絕對路徑 → 省略寬高

    def test_dimensions_included_when_file_exists(self, tmp_path):
        f = tmp_path / "image_1.png"
        _write_png(f, 800, 600)
        tag = render_img_tag("assets/images/image_1.png", "配圖", abs_path=f)
        assert 'width="800"' in tag
        assert 'height="600"' in tag

    def test_alt_is_escaped(self):
        tag = render_img_tag("a.png", 'a"b<c')
        assert '"' in tag and "<" in tag


class TestAltFromContext:
    MARKER = "__PDF_IMG__:assets/images/image_1.png"

    def test_uses_nearest_following_text(self):
        paras = ["前文。", TestAltFromContext.MARKER, "後文續句。"]
        assert alt_from_context(paras, 1) == "後文續句。配圖"

    def test_falls_back_to_previous_text(self):
        paras = ["前文。", TestAltFromContext.MARKER, TestAltFromContext.MARKER]
        assert alt_from_context(paras, 1) == "前文。配圖"

    def test_fallback_when_no_text(self):
        paras = [TestAltFromContext.MARKER]
        assert alt_from_context(paras, 0, fallback="提問配圖") == "提問配圖"

    def test_snippet_truncated_to_40_chars(self):
        paras = ["字" * 100, TestAltFromContext.MARKER]
        assert len(alt_from_context(paras, 1)) == len("字" * 40 + "配圖")


class TestJpegDimensions:
    """手工構造最小 JPEG marker 流，不依賴真圖檔。"""

    @staticmethod
    def _build_jpeg(width: int, height: int) -> bytes:
        # SOI + APP0 + DQT（供掃描略過）+ SOF0（含寬高）+ EOI
        sof = struct.pack(">H", 15) + bytes([8]) + struct.pack(
            ">HH", height, width) + bytes([1, 0x11, 0])
        parts = [
            b"\xff\xd8",                                        # SOI
            b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01",
            b"\xff\xdb" + struct.pack(">H", 132) + b"\x00" * 128,  # DQT
            b"\xff\xc0" + sof,                                  # SOF0
            b"\xff\xd9",                                        # EOI
        ]
        return b"".join(parts)

    def test_parses_jpeg_sof(self, tmp_path):
        img = tmp_path / "img.jpeg"
        img.write_bytes(TestJpegDimensions._build_jpeg(640, 480))
        assert jpeg_dimensions(img) == (640, 480)

    def test_rejects_non_jpeg(self, tmp_path):
        img = tmp_path / "img.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        assert jpeg_dimensions(img) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert jpeg_dimensions(tmp_path / "nope.jpg") is None

    def test_image_dimensions_dispatch(self, tmp_path):
        jpg = tmp_path / "img.jpg"
        jpg.write_bytes(TestJpegDimensions._build_jpeg(320, 200))
        png = tmp_path / "img.png"
        _write_png(png, 1, 1)
        assert image_dimensions(jpg) == (320, 200)
        assert image_dimensions(png) == (1, 1)

    def test_render_img_tag_with_jpeg_dims(self, tmp_path):
        jpg = tmp_path / "img.jpg"
        jpg.write_bytes(TestJpegDimensions._build_jpeg(800, 600))
        tag = render_img_tag("assets/img/b1/img_9.jpeg", "配圖", jpg)
        assert 'width="800"' in tag and 'height="600"' in tag
