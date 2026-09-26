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
        # 00-base.js content (darkMode init) comes before 01-search-init.js content
        pos_darkmode = js.find("darkMode")
        pos_minisearch = js.find("searchIndex")
        assert pos_darkmode < pos_minisearch, "base module should come before search module"

    def test_real_js_has_search_init_content(self):
        js = StaticAssetsManager().get_full_js_content()
        assert "activateSearch" in js
        assert "loadSearchIndexWithProgress" in js
        assert "segmentWithJieba" in js

    def test_real_js_has_search_core_content(self):
        js = StaticAssetsManager().get_full_js_content()
        assert "initSearch" in js
        assert "updateLoadMoreButtons" in js

    def test_real_js_has_reader_ux_content(self):
        js = StaticAssetsManager().get_full_js_content()
        assert "createReadingToolbar" in js
        assert "createFloatingTOC" in js
        assert "addQAActions" in js

    def test_real_js_search_results_open_new_tab(self):
        js = StaticAssetsManager().get_full_js_content()
        # Search results open in a new tab (keeps index page + results intact)
        assert "window.open(openUrl, '_blank', 'noopener')" in js  # 01e 改以 openUrl（含 ?q= 高亮參數）開啟
        assert "window.location.href = item.dataset.url" not in js

    def test_real_js_search_state_hash_roundtrip(self):
        js = StaticAssetsManager().get_full_js_content()
        # performSearch mirrors query/scope into URL hash; init restores it
        assert "updateSearchQueryHash" in js
        assert "readSearchStateFromHash" in js
        assert "restoreSearchFromHash" in js
        assert "history.replaceState" in js

    def test_real_js_toc_expand_snapshot(self):
        js = StaticAssetsManager().get_full_js_content()
        # TOC manual expand state is snapshotted to sessionStorage and restored
        assert "saveTocExpandSnapshot" in js
        assert "restoreTocExpandSnapshot" in js
        assert "sessionStorage.setItem(key, JSON.stringify(expanded))" in js
        assert "tocExpandState:" in js
        # Snapshot hook fires before page unload and on toggle
        assert "pagehide" in js
        # Only the index page writes TOC snapshots (chapter pages must not pollute)
        assert "if (!isIndexPage()) return;" in js

    def test_real_js_search_return_module(self):
        js = StaticAssetsManager().get_full_js_content()
        # 「回到搜尋結果」按鈕已移除（2026-09）；index 快照機制保留
        assert "initSearchReturnButton" not in js
        assert "captureSearchSnapshot" in js
        assert "restoreSearchScroll" in js

    def test_real_js_search_state_restores_displayed_and_scroll(self):
        js = StaticAssetsManager().get_full_js_content()
        # performSearch accepts a target displayed count; restore path uses it
        assert "function performSearch(query, targetDisplayedCount)" in js
        assert "captureSearchSnapshot" in js
        assert "restoreSearchScroll" in js
        # index honours ?q= query params (return button deep link)
        assert "location.search" in js

    def test_real_css_has_no_search_return_button(self):
        # 「回到搜尋結果」浮動按鈕已於 2026-09 移除（快照跨分頁複製不穩）
        css = StaticAssetsManager().get_full_css_content()
        assert ".search-return-btn" not in css
        js = StaticAssetsManager().get_full_js_content()
        assert "initSearchReturnButton" not in js

    def test_real_css_has_qa_audio_module(self):
        css = StaticAssetsManager().get_full_css_content()
        assert ".qa-source-banner" in css
        assert ".qa-play" in css
        assert ".qa-status" in css
        assert ".qa-player" in css
        assert ".qa-player-skip" in css
        assert ".qa-player-progress-thumb" in css
        assert ".qa-play.loading" in css
        assert "qa-play-icon--spinner" in css
        assert ".qa-player.is-loading" in css
        assert "body.dark-mode .qa-play.loading" in css
        assert "body.dark-mode .qa-play-icon--spinner" in css
        assert "body.dark-mode .qa-player-toggle.is-loading" in css
        assert "body.dark-mode .qa-player.is-loading .qa-player-range" in css
        assert "body.dark-mode .qa-player-progress.is-indeterminate" in css

    def test_real_js_has_qa_audio_module(self):
        js = StaticAssetsManager().get_full_js_content()
        # 08-qa-audio.js 內容（逐段播放 + 底部浮動播放器 + 拖拉/±5s + 載入進度）
        assert "qa-play" in js
        assert "qa-player" in js
        assert "qa-player-skip" in js
        assert "seekFromClientX" in js
        assert "decodeURIComponent" in js
        assert "beginLoading" in js
        assert "getBufferPercent" in js
        assert "qaAudio.loading" in js

    def test_real_css_has_image_lightbox_module(self):
        css = StaticAssetsManager().get_full_css_content()
        assert ".img-lightbox" in css
        assert ".img-lightbox.is-open" in css
        assert "img[src*=\"assets/images/\"]" in css
        assert "cursor: zoom-in" in css

    def test_real_js_has_image_lightbox_module(self):
        js = StaticAssetsManager().get_full_js_content()
        assert "img-lightbox" in js
        assert "openImageLightbox" in js
        assert "assets/images/" in js
        assert "jumpToSource" in js
        assert "跳到问答" in js or "跳到問答" in js

    def test_real_js_has_bookmark_ui_content(self):
        js = StaticAssetsManager().get_full_js_content()
        assert "renderBookmarks" in js
        assert "updateBookmarkCount" in js
        assert "showBookmarkLoadingIndicator" in js

    def test_real_js_has_reading_settings_content(self):
        js = StaticAssetsManager().get_full_js_content()
        assert "getDefaultFontSize" in js
        assert "applyReadingSettings" in js
        assert "handleInitialAnchor" in js
        assert "classList.add('anchor-target-highlight')" in js

    def test_real_css_has_anchor_target_highlight(self):
        css = StaticAssetsManager().get_full_css_content()
        assert ".anchor-target-highlight" in css
        assert "@keyframes anchor-target-pulse" in css
        assert "inset 0 0 0 9999px" in css

    def test_real_js_module_order_search_init_before_core(self):
        js = StaticAssetsManager().get_full_js_content()
        # Use function definitions to verify 01a-search-init.js < 01b-search-core.js
        pos_activate = js.find("async function activateSearch")
        pos_update_load_more = js.find("function updateLoadMoreButtons")
        assert pos_activate < pos_update_load_more, "01a-search-init.js should come before 01b-search-core.js"

    def test_real_js_module_order_bookmarks_before_bookmark_ui(self):
        js = StaticAssetsManager().get_full_js_content()
        # Use function definitions to verify 03a-bookmarks.js < 03b-bookmark-ui.js
        pos_migrate = js.find("function migrateOldBookmarks")
        pos_render_index = js.find("function renderIndexTOC")
        assert pos_migrate < pos_render_index, "03a-bookmarks.js should come before 03b-bookmark-ui.js"

    def test_real_js_module_order_bookmark_ui_before_reading_settings(self):
        js = StaticAssetsManager().get_full_js_content()
        # Use function definitions to verify 03b-bookmark-ui.js < 03c-reading-settings.js
        pos_render_index = js.find("function renderIndexTOC")
        pos_font = js.find("function getDefaultFontSize")
        assert pos_render_index < pos_font, "03b-bookmark-ui.js should come before 03c-reading-settings.js"

    def test_real_js_has_para_track_after_qa_audio(self):
        """09b-para-track.js（講經段落跟播）串接在 08-qa-audio.js 之後，
        且 qa-audio 暴露 W2E.qaAudio 介面供其掛接。"""
        js = StaticAssetsManager().get_full_js_content()
        assert "09b-para-track.js" in js
        assert "W2E.qaAudio = {" in js
        pos_api = js.find("W2E.qaAudio = {")
        pos_track = js.find("paraTrackEnabled")
        assert pos_api < pos_track, "08-qa-audio.js exposure must precede 09b-para-track.js"

    def test_real_css_has_para_track_styles(self):
        css = StaticAssetsManager().get_full_css_content()
        assert ".para-track-toggle" in css
        assert ".para-block.para-active" in css
        assert "body.dark-mode .para-block.para-active" in css

    def test_real_js_has_sutra_pin_after_para_track(self):
        """09c-sutra-pin.js（講經經文置頂）串接在 09b-para-track.js 之後。"""
        js = StaticAssetsManager().get_full_js_content()
        assert "09c-sutra-pin.js" in js
        assert "sutraPinEnabled" in js
        assert "sutra-pin-group" in js
        assert "W2E.sutraPin" in js
        # 過長經文放棄置頂的門檻，以及高度變化後重新量測的機制
        assert "TALL_RATIO = 0.45" in js
        assert "ResizeObserver" in js
        assert "MutationObserver" in js
        assert "document.fonts.ready" in js
        pos_track = js.find("paraTrackEnabled")
        pos_pin = js.find("sutraPinEnabled")
        assert pos_track != -1
        assert pos_pin != -1
        assert pos_track < pos_pin, "09b-para-track.js must precede 09c-sutra-pin.js"

    def test_real_css_has_sutra_pin_styles(self):
        css = StaticAssetsManager().get_full_css_content()
        assert ".sutra-pin-host" in css
        assert "position: sticky" in css
        assert ".sutra-pin-group" in css
        assert ".sutra-pin-toggle" in css
        assert "body.sutra-pin-off .sutra-pin-host" in css
        assert "body.sutra-pin-suppress .sutra-pin-host" in css
        assert "body.dark-mode .sutra-pin-toggle" in css


class TestRealVendorAssets:
    """本地自架 vendor 檔（不進模組串接，由 main.py 直接複製到輸出）。"""

    def test_minisearch_vendor_file_exists(self):
        vendor = (
            Path(__file__).resolve().parent.parent
            / "assets" / "js" / "minisearch.min.js"
        )
        assert vendor.exists(), "assets/js/minisearch.min.js 應隨 repo 自架"
        head = vendor.read_text(encoding="utf-8")[:400]
        assert "MiniSearch" in head or "minisearch" in head.lower()

    def test_js_modules_have_aria_expanded_sync(self):
        """TOC 展開鈕 aria-expanded 同步（P2-17）。"""
        js = StaticAssetsManager().get_full_js_content()
        assert "setTocIconState" in js
        assert "aria-expanded" in js

    def test_js_modules_have_ensure_minisearch_fallback(self):
        """本地 MiniSearch 失蹤時的 CDN 動態兜底（P1-7）。"""
        js = StaticAssetsManager().get_full_js_content()
        assert "ensureMiniSearchLoaded" in js

    def test_css_has_print_and_reduced_motion(self):
        css = StaticAssetsManager().get_full_css_content()
        assert "@media print" in css
        assert "prefers-reduced-motion" in css

    def test_css_has_content_visibility(self):
        css = StaticAssetsManager().get_full_css_content()
        assert "content-visibility: auto" in css
        assert "contain-intrinsic-size" in css

    def test_css_has_cjk_font_stack(self):
        css = StaticAssetsManager().get_full_css_content()
        assert "PingFang" in css and "Microsoft JhengHei" in css


# ---------------------------------------------------------------------------
# 2026-09 UX 改善：新模組必須出現在串接產物中（真實 assets 樹）
# ---------------------------------------------------------------------------



def test_real_js_bundle_contains_ux_modules():
    mgr = StaticAssetsManager()  # 預設即真實 assets 目錄
    js = mgr.get_full_js_content()
    for marker in [
        "w2e:readpos",          # 11-reading-resume
        "w2e:playerState",      # 13-player-persist
        "w2e-audio-resume",     # 13-player-persist
        "kb-focus",             # 14-search-plus 鍵盤導覽
        "w2e-toc-backdrop",     # 15-mobile-toc
        "no-audio-note",        # 16-jump-share（ebook 無音檔提示）
        "anchor-share",         # 16-jump-share（標題錨點分享）
        "theme-dark-neutral",   # 02-reader-ux／04-events（墨夜主題鈕）
        "sw.js",                # 17-theme-pwa（PWA 註冊）
    ]:
        assert marker in js, f"串接後的 script.js 缺少 {marker}"


def test_real_css_bundle_contains_ux_module():
    mgr = StaticAssetsManager()  # 預設即真實 assets 目錄
    css = mgr.get_full_css_content()
    for marker in [
        ".dark-neutral",        # 墨夜面板
        ".w2e-resume-bar",
        ".w2e-audio-resume",
        ".no-audio-note",
        ".anchor-share",
        "mark.w2e-hl",
    ]:
        assert marker in css, f"串接後的 style.css 缺少 {marker}"


def test_homepage_bookmark_manager_block_is_removed():
    """首頁（總目錄）底部的「我的書籤」管理區塊已移除（12-bookmarks-manager.js 刪除）。

    浮動目錄面板的書籤分頁（02-reader-ux 的分頁標籤）不在此限，仍應存在。
    """
    mgr = StaticAssetsManager()
    for bundle in (mgr.get_full_js_content(), mgr.get_full_css_content()):
        assert "w2e-bm-" not in bundle, "殘留首頁書籤管理區塊（.w2e-bm-*）樣式/腳本"
    # 模組檔本身已刪除（編號 12 保留空缺、不重排）
    assert not (Path(__file__).resolve().parents[1]
                / "assets" / "js" / "modules" / "12-bookmarks-manager.js").exists()
    # 側邊浮動目錄的書籤分頁仍在
    assert "bookmarks-list" in mgr.get_full_js_content()


def test_real_bundles_drop_persistent_backtop_button():
    """常駐回到頂端鈕已移除：回到頂端只留功能選單（data-action="top"）內的 ↑。"""
    mgr = StaticAssetsManager()
    assert "w2e-backtop" not in mgr.get_full_js_content()
    assert "w2e-backtop" not in mgr.get_full_css_content()
    assert 'data-action="top"' in mgr.get_full_js_content()


def test_reading_resume_skips_toc_only_index_pages():
    """總目錄頁只有目錄、沒有正文，不得出現「上次讀到 XX%」提示條。"""
    js = StaticAssetsManager().get_full_js_content()
    assert "isTocOnlyPage" in js          # 11-reading-resume 的頁面類型判斷
    assert "pruneTocOnlyEntries" in js   # 清除舊版殘留的目錄頁紀錄
    # 兩道關卡：儲存時不寫、顯示前不彈
    assert "if (isTocOnlyPage()) return;" in js
    assert "if (isTocOnlyPage()) { pruneTocOnlyEntries(); return; }" in js
