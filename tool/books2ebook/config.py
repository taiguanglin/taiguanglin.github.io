"""books2ebook — 全域設定與書籍註冊表"""

import os

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TOOL_DIR, "..", ".."))

DEFAULT_BOOKS_DIR = os.path.join(REPO_ROOT, "books")
DEFAULT_OUTPUT_DIR = os.path.join(REPO_ROOT, "ebook")
# 樣式資產的來源：直接沿用 wenda2_ebook 的 CSS/JS bundle（單一風格來源）
STYLE_ASSETS_SRC = os.path.join(REPO_ROOT, "wenda2_ebook", "assets")

SITE_TITLE = "坐禅系列电子书"

# 搜尋類型（與 word2ebook 的 search_index.json 相容）
TYPE_HEADING = "heading"
TYPE_QUESTION = "question"
TYPE_ANSWER = "answer"
TYPE_CONTENT = "content"


class BookConfig:
    """單本書的設定與解析器名稱。

    title      : 電子書顯示標題
    pdf        : books/ 底下的檔名
    parser     : parsers.py 對應的解析函式 key
    skip_pages :略過前面 N 頁（封面/裝飾頁）
    """

    def __init__(self, number, title, pdf, parser, skip_pages=0):
        self.number = number            # 1-based 序號
        self.title = title
        self.pdf = pdf
        self.parser = parser
        self.skip_pages = skip_pages

    @property
    def filename(self):
        return "%02d.html" % self.number

    @property
    def filename_trad(self):
        return "%02d_trad.html" % self.number


BOOKS = [
    BookConfig(1, "01《坐禅》", "01《坐禅》.pdf", "zuochan"),
    BookConfig(2, "02《坐禅之问答录》", "02《坐禅之问答录》.pdf", "wendalu"),
    BookConfig(3, "03《坐禅2》", "03《坐禅2·次世代版终极佛法》.pdf", "zuochan2",
               skip_pages=3),
    BookConfig(4, "讲《金刚经 心经》", "04《次世代版终极佛法·TaiGuangLin禅师讲金刚经 心经》.pdf", "jingang"),
    BookConfig(5, "讲《圆觉经》", "05 TaiGuangLin禅师讲《圆觉经》最终版.pdf", "yuanjue"),
]
