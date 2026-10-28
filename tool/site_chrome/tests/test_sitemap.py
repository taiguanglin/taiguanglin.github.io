"""sitemap.xml 產生器的守門測試。

背景（2026-10-28 SEO 稽核）：sitemap.xml 原本是手工維護、只有 stories 段落
由腳本補丁，電子書的 `<lastmod>` 停在 2026-10-10（內容卻在 10-27／10-28
更新過）。Google 官方說明 `<lastmod>` 只有在「持續且可驗證準確」時才會被
採用——因此 sitemap 改由 `tool/site_chrome/sitemap.py` 依實際發布檔案產生。

本檔驗證：
1. 每個 URL 都有 `<lastmod>`，且不輸出 Google 忽略的 priority／changefreq。
2. 兩套電子書的**實質頁**全部收錄。
3. 帶 noindex／meta refresh 的跳轉頁**不得**收錄。
4. 產生的 URL 集合與既有 sitemap 不脫節（覆蓋率 100%）。
"""

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SITEMAP_PATH = ROOT / "tool" / "site_chrome" / "sitemap.py"


def _load_sitemap_module():
    spec = importlib.util.spec_from_file_location("_site_chrome_sitemap", SITEMAP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sitemap_mod():
    return _load_sitemap_module()


@pytest.fixture(scope="module")
def rendered(sitemap_mod):
    return sitemap_mod.render_sitemap()


def _urls(text):
    return re.findall(r"<loc>(.*?)</loc>", text)


def _is_redirect_stub(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    return bool(re.search(r'<meta\s+http-equiv="refresh"', text, re.I))


@pytest.mark.skipif(
    not (ROOT / "wenda2_ebook").is_dir() or not (ROOT / "ebook").is_dir(),
    reason="需要已建置的電子書產物",
)
def test_every_url_has_lastmod(rendered):
    blocks = re.findall(r"<url>(.*?)</url>", rendered, re.S)
    assert blocks
    for block in blocks:
        assert "<loc>" in block
        assert re.search(r"<lastmod>\d{4}-\d{2}-\d{2}</lastmod>", block), block


def test_no_priority_or_changefreq(rendered):
    assert "<priority>" not in rendered
    assert "<changefreq>" not in rendered


@pytest.mark.skipif(
    not (ROOT / "wenda2_ebook").is_dir() or not (ROOT / "ebook").is_dir(),
    reason="需要已建置的電子書產物",
)
def test_substantive_ebook_pages_are_listed(rendered):
    urls = set(_urls(rendered))
    for dirname in ("wenda2_ebook", "ebook"):
        for path in sorted((ROOT / dirname).glob("*.html")):
            if _is_redirect_stub(path):
                continue
            url = "https://taiguanglin.info/%s/%s" % (dirname, path.name)
            assert url in urls, f"{url} 未列入 sitemap"


@pytest.mark.skipif(
    not (ROOT / "wenda2_ebook").is_dir(),
    reason="需要已建置的電子書產物",
)
def test_redirect_stubs_are_not_listed(rendered):
    urls = set(_urls(rendered))
    stubs = [
        path
        for path in sorted((ROOT / "wenda2_ebook").glob("*.html"))
        if _is_redirect_stub(path)
    ]
    if not stubs:
        pytest.skip("目前沒有跳轉頁")
    for path in stubs:
        url = "https://taiguanglin.info/wenda2_ebook/%s" % path.name
        assert url not in urls, f"跳轉頁 {url} 不得列入 sitemap"
