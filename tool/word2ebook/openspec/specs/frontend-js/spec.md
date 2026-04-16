# Frontend JavaScript Specification

## Purpose

The frontend JS provides all reader interactivity: dark mode, search, reading
toolbar, floating TOC, bookmarks, Q&A actions, and TOC level controls. All
modules execute within a single `DOMContentLoaded` closure and share the same
lexical scope.

## Requirements

### Requirement: Module File Structure
Source JavaScript SHALL be split into ordered module files under
`assets/js/modules/`. Files SHALL be named with a two-digit numeric prefix
(`00-`, `01-`, …) so that lexicographic sort equals execution order.

| File | Responsibility |
|---|---|
| `00-base.js` | Dark mode init, page-type detection helpers |
| `01a-search-init.js` | Search state variables, `activateSearch`, loading/error UI, `loadSearchIndexWithProgress`, Jieba WASM init, `segmentWithJieba` |
| `01b-search-core.js` | `initSearch` and all inner closures: MiniSearch setup, query handler, result rendering, paging, highlighting, `collapseSearch`, search event listener |
| `02-reader-ux.js` | Q&A ID generation, reading toolbar, floating TOC creation, action buttons, Q&A action overlays |
| `03a-bookmarks.js` | Bookmark storage/migration, CRUD, visual indicators, homepage bookmarks, toggle, clear |
| `03b-bookmark-ui.js` | `renderIndexTOC`, `showBookmarkLoadingIndicator`, `renderBookmarks`, `updateBookmarkCount` |
| `03c-reading-settings.js` | `getDefaultFontSize`, `applyReadingSettings`, font/line-height/width updates, `updateReadingProgress`, `updateCurrentSection`, `showToast`, `copyText`, `handleInitialAnchor` |
| `04-events.js` | Click delegation, scroll/resize handlers, component initialisation on load |
| `05-search-btn-visibility.js` | Smart show/hide of top/bottom search activation buttons on scroll |
| `06-toc-collapse.js` | TOC expand/collapse, level display buttons, `renderIndexTOC` |
| `07-floating-controls.js` | Floating TOC level-control panel, scroll/resize synchronisation |

### Requirement: Single Output File
`StaticAssetsManager` SHALL concatenate all `modules/*.js` files (sorted by
name) and wrap them in one `DOMContentLoaded` listener to produce the single
`script.js` that is copied to the ebook output.

#### Scenario: Module concatenation
- GIVEN `assets/js/modules/` contains ordered `.js` module files
- WHEN `StaticAssetsManager.get_full_js_content()` is called
- THEN the returned string SHALL start with `document.addEventListener('DOMContentLoaded'`
- AND the returned string SHALL contain the content of every module file

### Requirement: Dark Mode Persistence
The system SHALL read `localStorage['darkMode']` on page load and add the
`dark-mode` class to `<body>` if the value is `'true'`.

### Requirement: Stable Q&A IDs
JavaScript IDs for Q&A elements SHALL be computed using the same algorithm as
the Python side: `MD5(questioner + normalized_time + first_50_chars)[0:12]`.

#### Scenario: ID consistency
- GIVEN a question with questioner "甲", time "2024-01-15 10:30", and text "內容"
- WHEN the JavaScript `generateStableContentId` function runs
- THEN the resulting hash SHALL match the Python `IDGenerator.generate_stable_qa_id` output

### Requirement: Bookmark Persistence
Bookmarks SHALL be stored in `localStorage` under language-specific keys:
- `ebook-bookmarks-simplified` for simplified pages
- `ebook-bookmarks-traditional` for traditional pages

## Technical Notes

- Source modules: `assets/js/modules/`
- Build step: `StaticAssetsManager.get_full_js_content()` in `templates/static_assets.py`
- The `DOMContentLoaded` wrapper open/close strings are defined as module-level
  constants `JS_WRAPPER_OPEN` and `JS_WRAPPER_CLOSE` in `static_assets.py`
