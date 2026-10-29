"""圖片保留的回歸測試（stage 2 / stage 3）。

背景（2026-10-29）：
發布版電子書的 ``<img>`` 數量長期為 **0**，但 ``assets/images/`` 裡有 64 個
WebP 檔——所有插圖都在建置流程中遺失。原因是圖片放在
``question`` / ``answer`` div 的**外面**（Word 章，word2ebook 的
``_append_image`` 把圖接在區塊之後）或**裡面但不在 question-text 內**
（PDF 章，pdf_parser 的排版），而 stage 2 只取 inner HTML、stage 3 只
序列化 div 本體，兩處都看不到圖。

本檔鎖住三件事：
1. stage 2 的 ``sibling_imgs`` 能收齊三種位置的圖；
2. stage 3 的 ``_attach_imgs`` 會把圖插回它所屬的 Q&A 區塊；
3. 產物層守門：發布版每個 ``<img>`` 都指向存在的檔案，且每個資產檔都被
   引用到；來源（Word / PDF）的每一張圖都真的出現在發布版裡。
"""

import hashlib
import os
import re
from pathlib import Path

import pytest
from lxml import html as lhtml

import extract
import gen_classified


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _parse(html: str):
    """把片段包進一層 div——lxml 的 ``.//`` 不含根元素，不包起來
    ``.//div[@class="question"]`` 會找不到根節點自己。"""
    return lhtml.fromstring("<div>" + html + "</div>")


def _img_tags(html: str):
    return re.findall(r'<img[^>]*src="([^"]+)"', html)


# --------------------------------------------------------------------------- #
# stage 2：extract.sibling_imgs
# --------------------------------------------------------------------------- #

class TestSiblingImgs:
    """圖片有三種位置，三種都必須收得到。"""

    def test_collects_images_after_the_block(self):
        """Word 章：圖是 question/answer div 的兄弟節點。"""
        doc = _parse(
            '<div class="question" id="q1">'
            '<div class="question-text">文字</div></div>'
            '<img src="assets/images/a.webp"/>'
            '<img src="assets/images/b.webp"/>'
            '<div class="answer" id="a1"><div class="answer-text">答</div></div>'
        )
        q = doc.xpath('.//div[@class="question"]')[0]
        got = extract.sibling_imgs(q)
        assert len(got) == 2
        assert "a.webp" in got[0] and "b.webp" in got[1]

    def test_collects_images_inside_the_block(self):
        """PDF 章：圖在 div 內、但在 question-text 之外。"""
        doc = _parse(
            '<div class="question" id="q1">'
            '<div class="question-text">文字</div>'
            '<img src="assets/images/a.webp"/>'
            '<img src="assets/images/b.webp"/>'
            '</div>'
        )
        q = doc.xpath('.//div[@class="question"]')[0]
        got = extract.sibling_imgs(q)
        assert len(got) == 2
        assert "a.webp" in got[0] and "b.webp" in got[1]

    def test_collects_both_positions(self):
        """同一區塊同時有內、外面兩種位置 → 都要收。"""
        doc = _parse(
            '<div class="question" id="q1">'
            '<div class="question-text">文字</div>'
            '<img src="assets/images/inside.webp"/>'
            '</div>'
            '<img src="assets/images/outside.webp"/>'
        )
        q = doc.xpath('.//div[@class="question"]')[0]
        got = extract.sibling_imgs(q)
        assert len(got) == 2
        assert any("inside.webp" in g for g in got)
        assert any("outside.webp" in g for g in got)

    def test_no_images_returns_empty(self):
        doc = _parse(
            '<div class="question" id="q1">'
            '<div class="question-text">文字</div></div>'
        )
        q = doc.xpath('.//div[@class="question"]')[0]
        assert extract.sibling_imgs(q) == []

    def test_stops_at_next_non_image_sibling(self):
        """兄弟節點遇到非 <img> 就停——不能把後面的圖也吃進來。"""
        doc = _parse(
            '<div class="question" id="q1">'
            '<div class="question-text">文字</div></div>'
            '<img src="assets/images/mine.webp"/>'
            '<div class="answer" id="a1"><div class="answer-text">答</div></div>'
            '<img src="assets/images/other.webp"/>'
        )
        q = doc.xpath('.//div[@class="question"]')[0]
        got = extract.sibling_imgs(q)
        assert len(got) == 1 and "mine.webp" in got[0]


# --------------------------------------------------------------------------- #
# stage 3：gen_classified._attach_imgs / extract_word_blocks
# --------------------------------------------------------------------------- #

class TestAttachImgs:
    """stage 3 把 stage 2 收來的圖插回它所屬的 Q&A 區塊。"""

    def test_inserts_before_the_closing_div(self):
        html = ('<div class="question" id="q1">'
                '<div class="question-meta"><span class="questioner">甲</span></div>'
                '<div class="question-text">文字</div></div>')
        out = gen_classified._attach_imgs(html, ['<img src="a.webp"/>'])
        assert "a.webp" in out
        # 圖必須在 question div 的「最後一個 </div>」之前 → 在 div 內
        assert out.index("a.webp") < out.rindex("</div>")
        assert out.count("</div>") == html.count("</div>")

    def test_multiple_images_keep_order(self):
        html = '<div class="answer" id="a1"><div class="answer-text">答</div></div>'
        out = gen_classified._attach_imgs(
            html, ['<img src="one.webp"/>', '<img src="two.webp"/>'])
        assert out.index("one.webp") < out.index("two.webp")

    def test_no_images_is_identity(self):
        html = '<div class="answer" id="a1"><div class="answer-text">答</div></div>'
        assert gen_classified._attach_imgs(html, []) == html
        assert gen_classified._attach_imgs(html, None) == html

    def test_empty_html_is_safe(self):
        assert gen_classified._attach_imgs("", ['<img src="a.webp"/>']) == ""


class TestExtractWordBlocks:
    """stage 3 讀 Word 章底稿時，圖片不能被序列化過程丟掉。"""

    def _write_chapter(self, tmp_path, body: str) -> Path:
        src = tmp_path / "wenda2_ebook"
        src.mkdir(exist_ok=True)
        (src / "01.html").write_text(
            '<html><body><main>' + body + '</main></body></html>',
            encoding="utf-8")
        return src

    def test_keeps_images_next_to_the_question(self, tmp_path, monkeypatch):
        body = (
            '<article class="qa-pair">'
            '<div class="question" id="question-1">'
            '<div class="question-meta">'
            '<span class="questioner">甲</span>'
            '<span class="question-time">2025-03-10 18:29</span>'
            '</div>'
            '<div class="question-text">請看附圖</div>'
            '</div>'
            '<img src="assets/images/image_1.webp"/>'
            '<img src="assets/images/image_2.webp"/>'
            '<div class="answer" id="answer-1">'
            '<div class="answer-meta"><span class="answerer">TaiGuanglin</span></div>'
            '<div class="answer-text">答</div>'
            '</div>'
            '</article>'
        )
        src = self._write_chapter(tmp_path, body)
        monkeypatch.setattr(gen_classified, "SRC", src)

        blocks, _toc = gen_classified.extract_word_blocks(1)
        joined = "\n".join(blocks)
        assert "image_1.webp" in joined
        assert "image_2.webp" in joined
        # 圖要跟著 question 區塊走（不是散落在外）
        qblock = next(b for b in blocks if 'class="question"' in b)
        assert "image_1.webp" in qblock
        assert "image_2.webp" in qblock


# --------------------------------------------------------------------------- #
# 產物層守門：發布版的圖片必須完整且可用
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(not (Path(__file__).resolve().parents[3] / "wenda2_ebook").exists(),
                    reason="wenda2_ebook/ 未建置")
class TestPublishedEbookImages:
    """發布版電子書的圖片守門。"""

    def _chapter_files(self, ebook_dir: Path):
        return sorted(ebook_dir.glob("[0-9][0-9].html"))

    def test_every_img_points_to_an_existing_file(self, ebook_dir):
        missing = []
        for f in self._chapter_files(ebook_dir):
            for src in _img_tags(f.read_text(encoding="utf-8")):
                if src.startswith("http"):
                    continue
                if not (ebook_dir / src).exists():
                    missing.append((f.name, src))
        assert not missing, f"指向不存在檔案的圖片: {missing[:5]}"

    def test_every_asset_is_referenced(self, ebook_dir):
        assets = ebook_dir / "assets" / "images"
        if not assets.is_dir():
            pytest.skip("assets/images/ 不存在")
        referenced = set()
        for f in self._chapter_files(ebook_dir):
            for src in _img_tags(f.read_text(encoding="utf-8")):
                if src.startswith("assets/images/"):
                    referenced.add(os.path.basename(src))
        orphans = sorted(set(os.listdir(assets)) - referenced)
        assert not orphans, f"未被任何章節引用的圖檔: {orphans[:5]}"

    def test_published_book_actually_has_images(self, ebook_dir):
        total = sum(len(_img_tags(f.read_text(encoding="utf-8")))
                    for f in self._chapter_files(ebook_dir))
        assert total > 0, "發布版完全沒有圖片——stage 2/3 又把圖弄丟了"


# --------------------------------------------------------------------------- #
# 來源 ↔ 發布版 對帳：原檔有的圖，發布版一定要有
# --------------------------------------------------------------------------- #

def _webp_hash(data: bytes) -> str:
    from utils.image_markup import encode_webp
    return hashlib.sha256(encode_webp(data)).hexdigest()


def _published_asset_hashes(ebook_dir: Path):
    assets = ebook_dir / "assets" / "images"
    if not assets.is_dir():
        return {}
    return {n: hashlib.sha256((assets / n).read_bytes()).hexdigest()
            for n in os.listdir(assets)}


class TestSourceImagesReachTheBook:
    """逐張核對：來源（Word / PDF）的圖 → 發布版的資產檔 → 被章節引用。"""

    def _assert_referenced(self, ebook_dir: Path, hashes):
        asset_by_hash = {v: k for k, v in _published_asset_hashes(ebook_dir).items()}
        referenced = set()
        for f in sorted(ebook_dir.glob("[0-9][0-9].html")):
            for src in _img_tags(f.read_text(encoding="utf-8")):
                if src.startswith("assets/images/"):
                    referenced.add(os.path.basename(src))
        missing = []
        for h in hashes:
            asset = asset_by_hash.get(h)
            if asset is None:
                missing.append("(無對應資產檔)")
            elif asset not in referenced:
                missing.append(f"{asset}(未被引用)")
        return missing

    def test_word_images_all_published(self, ebook_dir, source_dir):
        docx = source_dir / "wenda2_250810_截止25年5月17日答疑_含图版.docx"
        if not docx.exists() or not ebook_dir.exists():
            pytest.skip("來源或產物不存在")
        import docx as docx_mod
        d = docx_mod.Document(str(docx))
        hashes = []
        for p in d.paragraphs:
            for blip in p._element.findall(
                    './/{http://schemas.openxmlformats.org/drawingml/2006/main}blip'):
                rId = blip.get(
                    '{http://schemas.openxmlformats.org/officeDocument/2006/'
                    'relationships}embed')
                hashes.append(_webp_hash(d.part.rels[rId].target_part.blob))
        assert hashes, "Word 原始檔裡找不到圖片"
        missing = self._assert_referenced(ebook_dir, hashes)
        assert not missing, f"Word 圖片未進入發布版: {missing[:5]}"

    def test_pdf_images_all_published(self, ebook_dir, source_dir):
        pdfs = sorted(source_dir.glob("*.pdf"))
        if not pdfs or not ebook_dir.exists():
            pytest.skip("來源 PDF 或產物不存在")
        fitz = pytest.importorskip("fitz")
        from core.pdf_parser import IMG_MIN_SIDE

        hashes = []
        for pdf in pdfs:
            doc = fitz.open(str(pdf))
            seen = set()
            try:
                for page in doc:
                    for img in page.get_images(full=True):
                        xref = img[0]
                        if xref in seen:
                            continue
                        try:
                            rects = page.get_image_rects(xref)
                        except Exception:
                            rects = []
                        if not rects:
                            continue
                        r = rects[0]
                        if abs(r.width) < IMG_MIN_SIDE and abs(r.height) < IMG_MIN_SIDE:
                            continue
                        try:
                            pix = fitz.Pixmap(doc, xref)
                            if pix.n - pix.alpha >= 4:
                                pix = fitz.Pixmap(fitz.csRGB, pix)
                            if pix.width < IMG_MIN_SIDE and pix.height < IMG_MIN_SIDE:
                                continue
                            hashes.append(_webp_hash(pix.tobytes("png")))
                        except Exception:
                            continue
                        seen.add(xref)
            finally:
                doc.close()
        assert hashes, "PDF 原始檔裡找不到可保留的圖片"
        missing = self._assert_referenced(ebook_dir, hashes)
        assert not missing, f"PDF 圖片未進入發布版: {missing[:5]}"
