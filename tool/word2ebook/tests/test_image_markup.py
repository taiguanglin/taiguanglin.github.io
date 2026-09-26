"""Tests for utils/image_markup.py"""

import struct
import shutil

import pytest

from utils.image_markup import (
    png_dimensions,
    jpeg_dimensions,
    webp_dimensions,
    image_dimensions,
    encode_webp,
    file_to_webp,
    render_img_tag,
    alt_from_context,
)


def _has_webp_encoder() -> bool:
    """cwebp CLI 或 Pillow 任一可用即可（對應 encode_webp 的後備順序）。"""
    if shutil.which("cwebp"):
        return True
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


needs_webp_encoder = pytest.mark.skipif(
    not _has_webp_encoder(),
    reason="需要 cwebp（brew install webp）或 Pillow 才能編碼 WebP",
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


class TestWebpDimensions:
    """WebP 為 RIFF 容器；三種 chunk 各建一個最小樣本，無需真 WebP 編碼器。"""

    @staticmethod
    def _riff(chunk: bytes) -> bytes:
        """組出最小 RIFF 容器：``RIFF<size>WEBP`` + ``fourcc<size><body>``。"""
        fourcc, body = chunk[:4], chunk[4:]
        payload = b"WEBP" + fourcc + struct.pack("<I", len(body)) + body
        return b"RIFF" + struct.pack("<I", len(payload)) + payload

    def test_parses_lossy_vp8(self, tmp_path):
        # 3-byte frame tag + 3-byte sync + 2x14-bit size
        body = b"\x00\x00\x00" + b"\x9d\x01\x2a" + (320).to_bytes(2, "little") + (200).to_bytes(2, "little")
        f = tmp_path / "a.webp"
        f.write_bytes(TestWebpDimensions._riff(b"VP8 " + body))
        assert webp_dimensions(f) == (320, 200)

    def test_parses_lossless_vp8l(self, tmp_path):
        bits = (99) | ((199) << 14)  # 寬-1 / 高-1
        f = tmp_path / "b.webp"
        f.write_bytes(TestWebpDimensions._riff(
            b"VP8L" + b"\x2f" + bits.to_bytes(4, "little")))
        assert webp_dimensions(f) == (100, 200)

    def test_parses_extended_vp8x(self, tmp_path):
        body = b"\x00" * 4 + (799).to_bytes(3, "little") + (599).to_bytes(3, "little")
        f = tmp_path / "c.webp"
        f.write_bytes(TestWebpDimensions._riff(b"VP8X" + body))
        assert webp_dimensions(f) == (800, 600)

    def test_rejects_non_webp(self, tmp_path):
        f = tmp_path / "d.webp"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        assert webp_dimensions(f) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert webp_dimensions(tmp_path / "nope.webp") is None

    def test_image_dimensions_dispatch_webp(self, tmp_path):
        body = b"\x00" * 4 + (639).to_bytes(3, "little") + (479).to_bytes(3, "little")
        f = tmp_path / "e.webp"
        f.write_bytes(TestWebpDimensions._riff(b"VP8X" + body))
        assert image_dimensions(f) == (640, 480)

    def test_render_img_tag_with_webp_dims(self, tmp_path):
        body = b"\x00" * 4 + (799).to_bytes(3, "little") + (599).to_bytes(3, "little")
        f = tmp_path / "image_1.webp"
        f.write_bytes(TestWebpDimensions._riff(b"VP8X" + body))
        tag = render_img_tag("assets/images/image_1.webp", "配圖", f)
        assert 'src="assets/images/image_1.webp"' in tag
        assert 'width="800"' in tag and 'height="600"' in tag


@needs_webp_encoder
class TestEncodeWebp:
    """encode_webp / file_to_webp —— 電子書圖片統一轉 WebP 的入口。"""

    def test_png_bytes_become_webp(self, tmp_path):
        src = tmp_path / "a.png"
        src.write_bytes(_real_png())
        out = encode_webp(src.read_bytes())
        assert out[:4] == b"RIFF" and out[8:12] == b"WEBP"

    def test_is_idempotent_on_webp_input(self):
        webp = encode_webp(_real_png())
        assert encode_webp(webp) is webp

    def test_garbage_input_raises(self):
        with pytest.raises(RuntimeError, match="WebP"):
            encode_webp(b"definitely not an image")

    def test_file_to_webp_converts_and_removes_source(self, tmp_path):
        src = tmp_path / "image_12.png"
        src.write_bytes(_real_png())
        dst = file_to_webp(src)
        assert dst.name == "image_12.webp" and dst.exists()
        assert not src.exists()  # 輸出目錄不留 PNG
        assert webp_dimensions(dst) == (64, 48)

    def test_file_to_webp_passthrough(self, tmp_path):
        f = tmp_path / "a.webp"
        f.write_bytes(encode_webp(_real_png()))
        assert file_to_webp(f) == f


def _real_png() -> bytes:
    """一張真 PNG（8x8 棋盤，含 alpha）——需要 Pillow 或 cwebp 產生。"""
    try:
        from PIL import Image
        import io
        img = Image.new("RGBA", (64, 48))
        for y in range(48):
            for x in range(64):
                img.putpixel((x, y), (255, 0, 0, 255) if (x + y) % 2 else (0, 0, 255, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        import subprocess
        import tempfile
        import os
        ppm = b"P6\n64 48\n255\n" + bytes([200, 100, 50]) * (64 * 48)
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "a.ppm")
            png = os.path.join(d, "a.png")
            with open(src, "wb") as fh:
                fh.write(ppm)
            subprocess.run(["cwebp", "-quiet", "-o", png, src], check=True)
            with open(png, "rb") as fh:
                return fh.read()
