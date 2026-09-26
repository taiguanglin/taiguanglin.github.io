# Static Assets Specification

## Purpose

The static-assets domain manages the discovery, concatenation, and delivery of
CSS and JavaScript source files. It abstracts the build step that transforms
modular source files into single deployable assets.

## Requirements

### Requirement: Module-First Resolution
`StaticAssetsManager` SHALL resolve CSS and JS content using the following
priority order:

**CSS:**
1. If `assets/css/modules/` exists → concatenate all `*.css` files sorted by filename
2. Else if `assets/css/style.css` exists → read that file directly
3. Else → return the `CSSAssets` inline stub

**JS:**
1. If `assets/js/modules/` exists → concatenate all `*.js` files sorted by filename,
   wrapped in a `DOMContentLoaded` listener
2. Else if `assets/js/script.js` exists → read that file directly
3. Else → return the `JSAssets` inline stub

#### Scenario: Modules directory present
- GIVEN `assets/js/modules/` contains `00-base.js` and `01-search.js`
- WHEN `StaticAssetsManager.get_full_js_content()` is called
- THEN the returned string SHALL start with `document.addEventListener('DOMContentLoaded'`
- AND contain the content of both files in order

#### Scenario: Fallback to single file
- GIVEN `assets/js/modules/` does not exist but `assets/js/script.js` does
- WHEN `get_full_js_content()` is called
- THEN the content of `script.js` SHALL be returned verbatim

#### Scenario: New feature modules are auto-included
- GIVEN `assets/css/modules/04c-qa-audio.css` and `assets/js/modules/08-qa-audio.js`
- WHEN `get_full_css_content()` / `get_full_js_content()` are called
- THEN the bundled CSS SHALL contain the QA audio selectors (`.qa-player`,
  `.qa-source-banner`) and the bundled JS SHALL contain the QA audio behaviour
  (`qa-play`, `qa-player`), with no build-config change required

#### Scenario: Para-track follow-play module is auto-included
- GIVEN `assets/js/modules/09b-para-track.js`
- WHEN `get_full_js_content()` is called
- THEN the bundled JS SHALL contain the para-track behaviour
  (`paraTrackEnabled`, `para-block[data-start]`) AFTER the `08-qa-audio.js`
  block (`W2E.qaAudio = {`), and the bundled CSS SHALL contain
  `.para-track-toggle` / `.para-block.para-active`, with no build-config
  change required

#### Scenario: Sutra-pin module is auto-included after para-track
- GIVEN `assets/js/modules/09c-sutra-pin.js`
- WHEN `get_full_js_content()` / `get_full_css_content()` are called
- THEN the bundled JS SHALL contain the sutra-pin behaviour
  (`sutraPinEnabled`, `sutra-pin-group`) AFTER the `09b-para-track.js`
  block (`paraTrackEnabled`), and the bundled CSS SHALL contain the sticky
  `.sutra-pin-host` / bounding `.sutra-pin-group` / `.sutra-pin-toggle`
  rules (incl. `body.sutra-pin-off` / `body.sutra-pin-suppress` static
  fallbacks), with no build-config change required

#### Scenario: Image lightbox modules are auto-included
- GIVEN `assets/css/modules/04d-image-lightbox.css` and
  `assets/js/modules/09-image-lightbox.js`
- WHEN `get_full_css_content()` / `get_full_js_content()` are called
- THEN the bundled CSS SHALL contain `.img-lightbox` and the bundled JS SHALL
  contain `img-lightbox` / `openImageLightbox`, with no build-config change
  required

#### Scenario: 2026-09 UX modules are auto-included
- GIVEN `assets/js/modules/11-reading-resume.js`, `13-player-persist.js` …
  `17-theme-pwa.js` (no `12-bookmarks-manager.js` — 首頁「我的書籤」區塊已移除)
  and `assets/css/modules/06-ux-plus.css`
- WHEN `get_full_css_content()` / `get_full_js_content()` are called
- THEN the bundled JS SHALL contain the reading-resume (`w2e:readpos`),
  player-persist (`w2e:playerState`), search-plus (`kb-focus`, `w2e-hl`),
  mobile-TOC (`w2e-toc-backdrop`), jump-share (`anchor-share`), and
  theme/PWA (`theme-dark-neutral`, `sw.js`) behaviours AFTER the
  `10-search-return.js` block, the bundled CSS SHALL
  contain `.dark-neutral` / `.w2e-resume-bar` / `.w2e-audio-resume` /
  `.no-audio-note` / `.anchor-share` rules, NEITHER bundle SHALL contain any
  `w2e-bm-*` / `我的書籤` rule or markup, and no build-config change is required

### Requirement: Concatenation Ordering
When concatenating module files, files SHALL be sorted lexicographically by
filename. The numeric prefix (`00-`, `01-`, …) enforces the correct order.

### Requirement: JS Wrapper
When building JS from modules, the concatenated inner content SHALL be
wrapped exactly as:
```
document.addEventListener('DOMContentLoaded', function() {
<inner content>
});
```
The wrapper constants are `JS_WRAPPER_OPEN` and `JS_WRAPPER_CLOSE` defined in
`templates/static_assets.py`.

### Requirement: Auxiliary JS Files
In addition to `script.js` and `style.css`, the converter SHALL copy:
- `assets/js/i18n-text.js`
- `assets/js/search-cache.js`
- `assets/js/jieba_rs_wasm.js`
- `assets/js/jieba_rs_wasm_bg.wasm` (binary)

These files are copied verbatim from the source `assets/js/` directory.

### Requirement: Test Isolation
`StaticAssetsManager` SHALL expose an `_assets_base` attribute that tests can
override to point at a temporary directory, enabling module-concatenation
tests without modifying the real source tree.

## Technical Notes

- Implementation: `templates/static_assets.py::StaticAssetsManager`
- Source assets: `assets/css/modules/`, `assets/js/modules/`
- `_concat_files(directory, pattern)` is a static method that globs, sorts, reads, and joins

### Requirement: Standalone Vendor JavaScript
Vendor libraries that must NOT enter the module bundle (they define their own
globals and are referenced by `<script src>` directly) live beside `modules/`
under `assets/js/` and are copied verbatim to the output by
`main.py::_generate_static_assets`. The bundle currently contains
`minisearch.min.js` (MiniSearch 6.3.0 UMD, self-hosted so the site has no
runtime third-party dependency). New vendor files SHALL be added to the copy
step, not to `modules/`.

#### Scenario: minisearch vendor copy
- GIVEN `assets/js/minisearch.min.js` exists
- WHEN static assets are generated
- THEN the output SHALL contain `assets/js/minisearch.min.js` byte-identical to
  the source, and it SHALL NOT be wrapped in the DOMContentLoaded listener

### Requirement: books2ebook Consumes the SoT Directly
`tool/books2ebook/main.py::copy_assets` SHALL assemble `ebook/assets/` from the
same source of truth (`StaticAssetsManager` via importlib) instead of copying the
stale `wenda2_ebook/assets` build output: `style.css`/`script.js` are
concatenated fresh, other standalone files under `assets/js/` are copied, and
`assets/js/w2e-config.js` (deployment search scope for 01d) is generated from
`config.EBOOK_SEARCH_SCOPE_TYPES`. books2ebook SHALL NOT string-patch
`script.js`.

#### Scenario: Rebuild ebook without rebuilding wenda2_ebook
- GIVEN `wenda2_ebook/` is stale or missing
- WHEN `tool/books2ebook/gen_all.py` runs
- THEN `ebook/assets/css/style.css` and `ebook/assets/js/script.js` SHALL reflect
  the current `tool/word2ebook/assets/` modules
  AND `ebook/assets/js/w2e-config.js` SHALL exist with the ebook scope types
