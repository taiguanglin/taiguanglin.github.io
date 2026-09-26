"""圖片 HTML 標記共用工具（同時是電子書圖片格式的 SoT）。

所有解析器（Word / PDF）產生 ``<img>`` 時一律經過 :func:`render_img_tag`，
統一提供：

- ``loading="lazy"``（離視窗圖片不立即下載）
- ``width`` / ``height``（瀏覽器預留版面，消除 CLS）
- 語意化 ``alt``（由呼叫端從上下文文字推導，取代無意義的 "Image"）

**輸出格式一律 WebP**（:func:`encode_webp`）：全站支援率高、體積比 PNG 小
一個數量級，詳見 :data:`WEBP_QUALITY`。來源（Word/PDF 內嵌）幾乎都是 PNG，
直接落地會讓 `wenda2_ebook/`、`ebook/` 多出數十 MB。

寬高直接解析 PNG IHDR / JPEG SOF marker / WebP VP8 標頭，不依賴 PIL／
PyMuPDF；其他格式或檔案不存在時優雅省略（不影響生成）。

本模組**不得 import 任何站內其他模組**（``books2ebook`` 會以
``importlib`` 單檔載入），且只依賴標準庫。
"""

import os
import struct
import shutil
import subprocess
import tempfile
from html import escape
from pathlib import Path
from typing import Optional, Tuple

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: 電子書插圖的 WebP 品質。-1 = cwebp 預設（75）；85 兼顧文字截圖的清晰度
#: 與體積（實測大圖約為 PNG 的 5–8%）。alpha 通道另外用 100 避免透明邊緣劣化。
WEBP_QUALITY = 85

#: 若來源已經是 WebP 位元組就原樣沿用，不再重新編碼。
_WEBP_RIFF = b"RIFF"


def _is_webp(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == _WEBP_RIFF and data[8:12] == b"WEBP"


def encode_webp(data: bytes, quality: int = WEBP_QUALITY) -> bytes:
    """把任意圖片位元組（PNG/JPEG/GIF…）轉成 WebP。

    依序嘗試：

    1. 已是 WebP → 原樣回傳。
    2. ``cwebp`` CLI（``brew install webp``）——首選，無 Python 依賴。
    3. Pillow（``pip install pillow``）——備援。

    兩者都沒有時擲 ``RuntimeError``，訊息指明安裝方式；不靜默退回 PNG，
    免得生成出半套 PNG 半套 WebP 的混合產物。

    Args:
        data: 原始圖片位元組。
        quality: cwebp 品質 0–100（Pillow 走 ``quality`` 近似值）。

    Returns:
        WebP 位元組。
    """
    if _is_webp(data):
        return data

    errors = []
    cwebp = shutil.which("cwebp")

    def _cwebp(src_path: str, dst_path: str) -> Optional[bytes]:
        proc = subprocess.run(
            [cwebp, "-quiet", "-q", str(quality), "-m", "6",
             "-alpha_q", "100", src_path, "-o", dst_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if proc.returncode == 0 and os.path.exists(dst_path):
            with open(dst_path, "rb") as fh:
                return fh.read()
        errors.append("cwebp exit=%d %s" % (
            proc.returncode, proc.stderr.decode("utf-8", "replace").strip()[:120]))
        return None

    # cwebp 只接受檔案路徑（無 stdin 模式），故走暫存檔。
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.img")
        dst = os.path.join(tmp, "out.webp")
        with open(src, "wb") as fh:
            fh.write(data)

        if cwebp:
            try:
                out = _cwebp(src, dst)
                if out:
                    return out
            except OSError as exc:
                errors.append("cwebp %s" % exc)

            # CMYK / 4-component JPEG 會讓 cwebp 直接拒收（libjpeg
            # "Unsupported color conversion request"）。原書 PDF 裡這類插圖
            # 很常見，先轉成 RGB PNG 再試一次。
            rgb = os.path.join(tmp, "in_rgb.png")
            if _to_rgb(src, rgb):
                out = _cwebp(rgb, dst)
                if out:
                    return out
            else:
                errors.append("無法轉 RGB（sips/ffmpeg 皆不可用）")

    try:
        import io

        from PIL import Image  # type: ignore

        with Image.open(io.BytesIO(data)) as im:
            buf = io.BytesIO()
            # CMYK 模式 Pillow 需顯式轉 RGB，否則存檔會失敗。
            if im.mode not in ("RGB", "RGBA", "L", "LA"):
                im = im.convert("RGB")
            im.save(buf, format="WEBP", quality=quality, method=6)
            return buf.getvalue()
    except ImportError:
        errors.append("Pillow 未安裝")
    except Exception as exc:  # 解碼失敗等
        errors.append("Pillow %s" % exc)

    raise RuntimeError(
        "無法轉換為 WebP（%s）。請安裝其一：brew install webp（提供 cwebp）"
        "或 pip install pillow。" % " / ".join(errors)
    )


def _to_rgb(src: str, dst: str) -> bool:
    """把 CMYK／灰階等 cwebp 難以處理的來源轉成 RGB PNG，成功回傳 ``True``。

    依序嘗試 ``sips``（macOS 內建）與 ``ffmpeg``；兩者皆無或失敗回傳 ``False``，
    由呼叫端繼續走下一個後備方案。
    """
    attempts = [
        (["sips", "-s", "format", "png", src, "--out", dst]),
        (["ffmpeg", "-v", "error", "-y", "-i", src, "-pix_fmt", "rgb24", dst]),
    ]
    for cmd in attempts:
        if not shutil.which(cmd[0]):
            continue
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0:
                return True
        except OSError:
            continue
    return False


def file_to_webp(src, quality: int = WEBP_QUALITY):
    """把圖片檔轉成同目錄的 ``.webp``，回傳新路徑（已是 WebP 則沿用原檔）。

    轉碼成功後移除來源檔，讓輸出目錄只剩 WebP（體積是本工具存在的理由）。
    """
    src = Path(src)
    if src.suffix.lower() == ".webp":
        return src
    dst = src.with_suffix(".webp")
    dst.write_bytes(encode_webp(src.read_bytes(), quality))
    src.unlink()
    return dst


def png_dimensions(path) -> Optional[Tuple[int, int]]:
    """讀 PNG IHDR 取寬高；非 PNG、損壞或不存在回傳 ``None``。"""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
        if len(head) < 24 or head[:8] != _PNG_SIGNATURE or head[12:16] != b"IHDR":
            return None
        width, height = struct.unpack(">II", head[16:24])
        if 0 < width <= 100000 and 0 < height <= 100000:
            return width, height
    except OSError:
        pass
    return None


def jpeg_dimensions(path) -> Optional[Tuple[int, int]]:
    """掃 JPEG 各 marker 找 SOF（SOF0/1/2…）取寬高；失敗回傳 ``None``。

    只讀檔頭前 256 KB（SOF 在量化表/霍夫曼表之前）；無外部依賴。
    """
    try:
        with open(path, "rb") as f:
            data = f.read(256 * 1024)
        if len(data) < 4 or data[0] != 0xFF or data[1] != 0xD8:
            return None
        pos = 2
        while pos + 4 < len(data):
            if data[pos] != 0xFF:
                pos += 1
                continue
            marker = data[pos + 1]
            # 沒有長度的獨立 marker
            if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
                pos += 2
                continue
            if pos + 4 > len(data):
                break
            seg_len = struct.unpack(">H", data[pos + 2:pos + 4])[0]
            # SOF0–SOF15（不含 JPG/JPGn 漸層式 0xC4=DHT、0xC8=JPG）
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                if pos + 9 < len(data):
                    height, width = struct.unpack(
                        ">HH", data[pos + 5:pos + 9])
                    if 0 < width <= 100000 and 0 < height <= 100000:
                        return width, height
                return None
            pos += 2 + seg_len
    except (OSError, struct.error):
        pass
    return None


def webp_dimensions(path) -> Optional[Tuple[int, int]]:
    """讀 WebP 標頭取寬高（VP8 / VP8L / VP8X 三種 chunk）；失敗回傳 ``None``。

    WebP 為 RIFF 容器：``RIFF<size>WEBP`` 後接 chunk。常見三種變體：
    ``VP8 ``(lossy，寬高在 frame header)、``VP8L``(lossless，14 bits 位元組)、
    ``VP8X``(extended，24 bits canvas 小-1)。逐一試讀即可，不需外部依賴。
    """
    try:
        with open(path, "rb") as f:
            data = f.read(64 * 1024)
        if len(data) < 16 or not _is_webp(data):  # RIFF(12) + chunk header(4)
            return None

        pos = 12
        while pos + 8 <= len(data):
            fourcc = data[pos:pos + 4]
            (size,) = struct.unpack("<I", data[pos + 4:pos + 8])
            body = pos + 8

            if fourcc == b"VP8X" and body + 10 <= len(data):
                width = int.from_bytes(data[body + 4:body + 7], "little") + 1
                height = int.from_bytes(data[body + 7:body + 10], "little") + 1
            elif fourcc == b"VP8 " and body + 10 <= len(data):
                # frame header: 3-byte frame tag, 3-byte sync 0x9d012a, 2x14-bit size
                if data[body + 3:body + 6] != b"\x9d\x01\x2a":
                    return None
                width = int.from_bytes(data[body + 6:body + 8], "little") & 0x3FFF
                height = int.from_bytes(data[body + 8:body + 10], "little") & 0x3FFF
            elif fourcc == b"VP8L" and body + 5 <= len(data):
                if data[body] != 0x2F:
                    return None
                bits = int.from_bytes(data[body + 1:body + 5], "little")
                width = (bits & 0x3FFF) + 1
                height = ((bits >> 14) & 0x3FFF) + 1
            else:
                pos = body + size + (size & 1)  # chunk 依 2 位元組對齊
                continue

            if 0 < width <= 100000 and 0 < height <= 100000:
                return width, height
            return None
    except (OSError, struct.error):
        pass
    return None


def image_dimensions(path) -> Optional[Tuple[int, int]]:
    """依檔案內容自動選擇 PNG/JPEG/WebP 解析；失敗回傳 ``None``。"""
    dims = png_dimensions(path)
    if dims is None:
        dims = jpeg_dimensions(path)
    if dims is None:
        dims = webp_dimensions(path)
    return dims


def render_img_tag(rel_path: str, alt_text: str, abs_path=None) -> str:
    """產生 ``<img loading="lazy" src alt [width height]>``。"""
    attrs = [
        'loading="lazy"',
        f'src="{escape(rel_path, quote=True)}"',
        f'alt="{escape(alt_text, quote=True)}"',
    ]
    if abs_path is not None:
        dims = image_dimensions(abs_path)
        if dims:
            attrs.append(f'width="{dims[0]}"')
            attrs.append(f'height="{dims[1]}"')
    return "<img " + " ".join(attrs) + ">"


def alt_from_context(paras, img_index: int, fallback: str = "文章配圖") -> str:
    """以圖片前後最近的文字段落作為 alt 語意（截 40 字）。

    ``paras`` 為同一卡片內的內容清單；``img_index`` 是圖片所在位置。
    找不到任何文字時使用 ``fallback``（如「提問配圖」「回答配圖」）。
    """
    order = list(range(img_index + 1, len(paras))) + list(range(img_index - 1, -1, -1))
    for j in order:
        piece = paras[j]
        if piece is None:
            continue
        text = str(piece).strip()
        if not text or text.startswith("__PDF_IMG__:"):
            continue
        snippet = "".join(text.split())[:40]
        if snippet:
            return f"{snippet}配圖"
    return fallback
