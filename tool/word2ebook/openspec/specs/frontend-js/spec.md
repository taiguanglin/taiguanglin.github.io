# Frontend JavaScript Specification

## Purpose

The frontend JS provides all reader interactivity: dark mode, search, reading
toolbar, floating TOC, bookmarks, Q&A actions, and TOC level controls. All
modules execute within a single `DOMContentLoaded` closure and share the same
lexical scope. Cross-module communication is mediated through the `W2E` global
namespace object (defined in `00-base.js`) — assign exported functions to `W2E`
properties rather than relying on implicit global leakage.

## Requirements

### Requirement: Module File Structure
Source JavaScript SHALL be split into ordered module files under
`assets/js/modules/`. Files SHALL be named with a two-digit numeric prefix
(`00-`, `01-`, …) so that lexicographic sort equals execution order.

| File | Responsibility |
|---|---|
| `00-base.js` | `W2E` global namespace, dark mode init, page-type helpers (`isIndexPage`, `isTraditionalChinesePage`, `getText`) |
| `01a-search-init.js` | Search state variables, `activateSearch`, loading/error UI, `loadSearchIndexWithProgress`, Jieba WASM init, `segmentWithJieba` |
| `01b-search-index.js` | `createSearchConfig`, `buildSearchIndexInBatches`, `buildSearchIndexInBatchesWithCache` |
| `01c-search-highlight.js` | `escapeHtml`, `getBestContextForHighlight`, `highlightSearchTerm` |
| `01d-search-perform.js` | `performSearch`, `displayPagedResults`, `loadMoreResults` |
| `01e-search-ui.js` | `getSearchElements`, `initSearch`, search event bindings (input, clear, collapse, load-more) |
| `02-reader-ux.js` | Q&A ID generation, reading toolbar, floating TOC creation, action buttons, Q&A action overlays |
| `03a-bookmark-data.js` | Bookmark storage/migration, CRUD, chapter detection, visual indicators, `toggleBookmark` |
| `03b-bookmark-render.js` | `showBookmarkAddedFeedback`, `initializeHomepageTOC`, `renderBookmarkChaptersBatch`, toast messages |
| `03c-bookmark-ui.js` | `renderIndexTOC`, `showBookmarkLoadingIndicator`, `renderBookmarks`, `updateBookmarkCount` |
| `03d-reading-settings.js` | `getDefaultFontSize`, `applyReadingSettings`, font/line-height/width updates, `updateReadingProgress`, `updateCurrentSection`, `showToast`, `copyText`, `handleInitialAnchor` |
| `04-events.js` | Click delegation, scroll/resize handlers, component initialisation on load |
| `05-search-btn-visibility.js` | Smart show/hide of top/bottom search activation buttons on scroll |
| `06-toc-collapse.js` | TOC expand/collapse, level display buttons, `renderIndexTOC` |
| `07-floating-controls.js` | Floating TOC level-control panel, scroll/resize synchronisation |
| `08-qa-audio.js` | QA per-segment audio playback: wires `.qa-play` buttons, builds the bottom floating mini-player (seekable progress bar, ±5s skip, play/pause toggle), seeks to each segment's start and auto-stops at its end |

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

### Requirement: QA Per-Segment Audio Playback
On pages containing `.qa-play` buttons, the system SHALL play the segment's audio
clip from `data-start` to `data-end` (seconds) using the URL in `data-audio`, and
SHALL display a bottom floating mini-player showing the decoded audio filename and
the `data-label` time range. The mini-player SHALL provide:

- A play/pause toggle button
- A draggable progress bar (pointer drag on the track) to seek within the current
  segment bounds (`data-start` … `data-end`)
- `−5s` and `+5s` skip buttons that adjust playback within the same segment bounds
- Keyboard support on the progress bar: Left/Right arrows for ±5s, Space/Enter for
  play/pause

Clicking a segment's button SHALL seek and play that segment; reaching `data-end`
SHALL auto-stop; clicking the active segment again SHALL pause. Switching between
segments of the **same** audio file SHALL seek without reloading the source. The
audio filename SHALL be decoded for display with `decodeURIComponent`. The module
SHALL no-op on pages without `.qa-play` buttons. This module is isolated in its own
IIFE so its identifiers do not collide with the shared `DOMContentLoaded` scope.

#### Scenario: Play and auto-stop a segment
- GIVEN a QA chapter page with `.qa-play` buttons
- WHEN the user clicks a segment's play button
- THEN the mini-player SHALL appear, playback SHALL start at `data-start`, and it
  SHALL stop automatically when `currentTime` reaches `data-end`

#### Scenario: Seek and skip within a segment
- GIVEN the mini-player is visible for an active segment
- WHEN the user drags the progress bar or clicks `−5s` / `+5s`
- THEN `audio.currentTime` SHALL be clamped to `[data-start, data-end]` and the
  progress UI SHALL update accordingly

## Technical Notes

- Source modules: `assets/js/modules/`
- Build step: `StaticAssetsManager.get_full_js_content()` in `templates/static_assets.py`
- The `DOMContentLoaded` wrapper open/close strings are defined as module-level
  constants `JS_WRAPPER_OPEN` and `JS_WRAPPER_CLOSE` in `static_assets.py`
