"""Tests for templates/static_assets.py"""

import pytest
from pathlib import Path

from templates.static_assets import (
    StaticAssetsManager,
    CSSAssets,
    JSAssets,
    JS_WRAPPER_OPEN,
    JS_WRAPPER_CLOSE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def assets_root(tmp_path):
    """Create a minimal asset directory tree."""
    css_dir = tmp_path / "assets" / "css"
    js_dir = tmp_path / "assets" / "js"
    css_dir.mkdir(parents=True)
    js_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def module_assets(assets_root):
    """Split module files in assets/css/modules/ and assets/js/modules/."""
    css_mods = assets_root / "assets" / "css" / "modules"
    js_mods = assets_root / "assets" / "js" / "modules"
    css_mods.mkdir()
    js_mods.mkdir()

    (css_mods / "00-base.css").write_text(":root { --c: red; }\n", encoding="utf-8")
    (css_mods / "01-layout.css").write_text(".header { display: flex; }\n", encoding="utf-8")
    (css_mods / "02-search.css").write_text(".search { color: blue; }\n", encoding="utf-8")

    (js_mods / "00-base.js").write_text("// base\nlet x = 1;\n", encoding="utf-8")
    (js_mods / "01-search.js").write_text("// search\nlet y = 2;\n", encoding="utf-8")

    return assets_root


@pytest.fixture
def single_file_assets(assets_root):
    """No modules/ directory – only monolithic files."""
    (assets_root / "assets" / "css" / "style.css").write_text(
        "body { color: red; }\n", encoding="utf-8"
    )
    (assets_root / "assets" / "js" / "script.js").write_text(
        "document.addEventListener('DOMContentLoaded', function() { });\n",
        encoding="utf-8",
    )
    return assets_root


def _make_mgr(assets_root: Path) -> StaticAssetsManager:
    mgr = StaticAssetsManager()
    mgr._assets_base = assets_root / "assets"
    return mgr


# ---------------------------------------------------------------------------
# CSSAssets
# ---------------------------------------------------------------------------

class TestCSSAssets:
    def test_get_css_content_returns_string(self):
        result = CSSAssets().get_css_content()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_css_content_cached(self):
        css = CSSAssets()
        first = css.get_css_content()
        second = css.get_css_content()
        assert first is second

    def test_css_contains_body_selector(self):
        assert "body" in CSSAssets().get_css_content()


# ---------------------------------------------------------------------------
# JSAssets
# ---------------------------------------------------------------------------

class TestJSAssets:
    def test_get_js_content_returns_string(self):
        result = JSAssets().get_js_content()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_js_content_cached(self):
        js = JSAssets()
        first = js.get_js_content()
        second = js.get_js_content()
        assert first is second

    def test_js_contains_domcontentloaded(self):
        assert "DOMContentLoaded" in JSAssets().get_js_content()


# ---------------------------------------------------------------------------
# StaticAssetsManager – module-based loading
# ---------------------------------------------------------------------------

class TestStaticAssetsManagerModules:
    def test_css_from_modules_contains_all_modules(self, module_assets):
        mgr = _make_mgr(module_assets)
        css = mgr.get_full_css_content()
        assert ":root" in css
        assert ".header" in css
        assert ".search" in css

    def test_css_modules_in_sorted_order(self, module_assets):
        mgr = _make_mgr(module_assets)
        css = mgr.get_full_css_content()
        pos_base = css.index(":root")
        pos_layout = css.index(".header")
        pos_search = css.index(".search")
        assert pos_base < pos_layout < pos_search

    def test_js_from_modules_wrapped_in_domcontentloaded(self, module_assets):
        mgr = _make_mgr(module_assets)
        js = mgr.get_full_js_content()
        assert js.startswith(JS_WRAPPER_OPEN)
        assert js.endswith(JS_WRAPPER_CLOSE)

    def test_js_from_modules_contains_inner_content(self, module_assets):
        mgr = _make_mgr(module_assets)
        js = mgr.get_full_js_content()
        assert "let x = 1" in js
        assert "let y = 2" in js

    def test_js_modules_in_sorted_order(self, module_assets):
        mgr = _make_mgr(module_assets)
        js = mgr.get_full_js_content()
        pos_base = js.index("// base")
        pos_search = js.index("// search")
        assert pos_base < pos_search

    def test_adding_new_css_module_appears_in_output(self, module_assets):
        new_mod = module_assets / "assets" / "css" / "modules" / "99-extra.css"
        new_mod.write_text(".extra { display: none; }\n", encoding="utf-8")
        mgr = _make_mgr(module_assets)
        css = mgr.get_full_css_content()
        assert ".extra" in css

    def test_concat_files_static_method(self, module_assets):
        css_dir = module_assets / "assets" / "css" / "modules"
        result = StaticAssetsManager._concat_files(css_dir, "*.css")
        assert ":root" in result
        assert ".header" in result


# ---------------------------------------------------------------------------
# StaticAssetsManager – fallback to single file
# ---------------------------------------------------------------------------

class TestStaticAssetsManagerSingleFile:
    def test_css_fallback_to_single_file(self, single_file_assets):
        mgr = _make_mgr(single_file_assets)
        css = mgr.get_full_css_content()
        assert "body { color: red; }" in css

    def test_js_fallback_to_single_file(self, single_file_assets):
        mgr = _make_mgr(single_file_assets)
        js = mgr.get_full_js_content()
        assert "DOMContentLoaded" in js

    def test_fallback_to_stub_when_nothing_exists(self, assets_root):
        mgr = _make_mgr(assets_root)
        css = mgr.get_full_css_content()
        js = mgr.get_full_js_content()
        assert isinstance(css, str) and len(css) > 0
        assert isinstance(js, str) and len(js) > 0


# ---------------------------------------------------------------------------
# StaticAssetsManager – integration with real source modules
# ---------------------------------------------------------------------------

class TestStaticAssetsManagerRealModules:
    """Verify the real assets/js/modules and assets/css/modules produce correct output."""

    def test_real_css_content_length(self):
        mgr = StaticAssetsManager()
        css = mgr.get_full_css_content()
        assert len(css) > 50_000

    def test_real_js_content_length(self):
        mgr = StaticAssetsManager()
        js = mgr.get_full_js_content()
        assert len(js) > 100_000

    def test_real_css_has_body_selector(self):
        css = StaticAssetsManager().get_full_css_content()
        assert "body {" in css or "body{" in css

    def test_real_js_starts_with_domcontentloaded(self):
        js = StaticAssetsManager().get_full_js_content()
        assert js.startswith(JS_WRAPPER_OPEN)

    def test_real_js_ends_with_wrapper_close(self):
        js = StaticAssetsManager().get_full_js_content()
        assert js.rstrip().endswith("});")

    def test_real_css_has_dark_mode(self):
        css = StaticAssetsManager().get_full_css_content()
        assert "dark-mode" in css

    def test_real_js_has_minisearch_reference(self):
        js = StaticAssetsManager().get_full_js_content()
        assert "MiniSearch" in js or "minisearch" in js.lower()

    def test_real_js_module_order_base_before_search(self):
        js = StaticAssetsManager().get_full_js_content()
        # 00-base.js content (darkMode init) comes before 01-search.js content
        pos_darkmode = js.find("darkMode")
        pos_minisearch = js.find("searchIndex")
        assert pos_darkmode < pos_minisearch, "base module should come before search module"
