"""圖片 HTML 標記共用工具。

所有解析器（Word / PDF）產生 ``<img>`` 時一律經過 :func:`render_img_tag`，
統一提供：

- ``loading="lazy"``（離視窗圖片不立即下載）
- ``width`` / ``height``（瀏覽器預留版面，消除 CLS）
- 語意化 ``alt``（由呼叫端從上下文文字推導，取代無意義的 "Image"）

寬高直接解析 PNG IHDR / JPEG SOF marker，不依賴 PIL／PyMuPDF；其他格式或
檔案不存在時優雅省略（不影響生成）。
"""

import struct
from html import escape
from pathlib import Path
from typing import Optional, Tuple

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


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


def image_dimensions(path) -> Optional[Tuple[int, int]]:
    """依檔案內容自動選擇 PNG/JPEG 解析；失敗回傳 ``None``。"""
    dims = png_dimensions(path)
    if dims is None:
        dims = jpeg_dimensions(path)
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
