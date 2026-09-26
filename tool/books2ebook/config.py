"""books2ebook — 全域設定與書籍註冊表"""

import os

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TOOL_DIR, "..", ".."))

DEFAULT_BOOKS_DIR = os.path.join(REPO_ROOT, "books")
DEFAULT_OUTPUT_DIR = os.path.join(REPO_ROOT, "ebook")
# 樣式資產的單一真相來源：word2ebook 的 assets 模組目錄（CSS/JS 由
# StaticAssetsManager 現場串接），不再複製 wenda2_ebook 的建置產物——
# 後者一旦未重建就會過期，且其 script.js 曾需事後字串 patch。
W2E_ASSETS_SRC = os.path.join(REPO_ROOT, "tool", "word2ebook", "assets")

# ebook 與 wenda2_ebook 內容完全相同的樣式/JS 資產：不再各輸出一份，
# ebook 以站點根絕對路徑引用 wenda2_ebook 的建置產物（兩者同源 SoT）。
# 取捨：改動 word2ebook 的 CSS/JS SoT 後必須重建 wenda2_ebook，ebook 才會
# 跟著更新；copy_assets() 會比對 SoT 內容並在落後時警告。
SHARED_ASSETS_BASE = "/wenda2_ebook/assets"
SHARED_ASSETS_DIR = os.path.join(REPO_ROOT, "wenda2_ebook", "assets")
SHARED_ASSET_FILES = (
    "css/style.css",
    "js/script.js",
    "js/i18n-text.js",
    "js/minisearch.min.js",
    "js/search-cache.js",
    "js/jieba_rs_wasm.js",
    "js/jieba_rs_wasm_bg.wasm",
)


def shared_asset_url(rel_path):
    """共用資產的站點絕對 URL（HTML 模板用）。"""
    return "%s/%s" % (SHARED_ASSETS_BASE, rel_path)


# ebook 專用搜尋範圍：全書搜尋的預設「兩者」範圍涵蓋 content/heading
# （寫入 assets/js/w2e-config.js，由 01d-search-perform.js 讀取）
EBOOK_SEARCH_SCOPE_TYPES = ["question", "answer", "content", "heading"]

SITE_TITLE = "坐禅与讲经系列电子书"

# SEO / 分享 meta（章節與首頁 head）
# 文字一律以簡體寫入模板；繁版由 convert_html_to_trad() 整頁轉換
# （屬性轉換清單含 content，meta 內文會跟著轉繁）。
SITE_BASE_URL = "https://taiguanglin.info"
EBOOK_URL_PATH = "ebook"
OG_IMAGE_PATH = "images/og-default.jpg"
SEO_HREFLANG_DEFAULT = "zh-Hant"   # x-default 指向繁體首選頁
SEO_SITE_NAME = "TaiGuangLin 禅师"
SEO_INDEX_DESCRIPTION = (
    "TaiGuangLin 禅师坐禅系列与讲经系列十本著作完整电子书，"
    "支持全文检索、书签与简繁切换。"
)
SEO_CHAPTER_DESCRIPTION = (
    "{title}——TaiGuangLin 禅师著述/讲经全文电子书，支持全文检索与简繁切换。"
)

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

    def __init__(self, number, title, pdf, parser, skip_pages=0, series=None):
        self.number = number            # 1-based 序號（決定檔名 01..10 與顯示順序）
        self.title = title
        self.pdf = pdf
        self.parser = parser
        self.skip_pages = skip_pages
        self.series = series            # 音檔系列 key（audio_map.AUDIO_MAP 的主鍵）; None=無音檔

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
    BookConfig(4, "感恩与讲经", "感恩与讲经（2024年4月14日）.pdf",
               "ganen", skip_pages=1, series="ganen"),
    BookConfig(5, "04 讲《金刚经 心经》", "04《次世代版终极佛法·TaiGuangLin禅师讲金刚经 心经》.pdf", "jingang"),
    BookConfig(6, "05 讲《圆觉经》", "05 TaiGuangLin禅师讲《圆觉经》最终版.pdf", "yuanjue"),
    BookConfig(7, "06 讲《四十二章经》", "06 Tai师父讲《四十二章经》.pdf",
               "sishierzhang", skip_pages=0, series="sishierzhang"),
    BookConfig(8, "07 讲《楞伽经》", "07 Tai师父讲《楞伽经》.pdf",
               "lengqie", skip_pages=1, series="lengqie"),
    BookConfig(9, "08 讲《六祖坛经》", "08 Tai师父讲《六祖坛经》.pdf",
               "liuzutanjing", skip_pages=1, series="liuzutanjing"),
    BookConfig(10, "09 讲《楞严经》(未完)", "09 Tai师父讲《楞严经》(未完).pdf",
               "lengyanjing", skip_pages=1, series="lengyanjing"),
]
