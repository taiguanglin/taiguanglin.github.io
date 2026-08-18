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
| `01d-search-perform.js` | `performSearch` (MiniSearch + scope `filter`), `displayPagedResults`, `loadMoreResults` |
| `01e-search-ui.js` | `getSearchElements`, `initSearch`, search event bindings (input, scope buttons, clear, collapse, load-more) |
| `02-reader-ux.js` | Q&A ID generation, reading toolbar, floating TOC creation, action buttons, Q&A action overlays |
| `03a-bookmark-data.js` | Bookmark storage/migration, CRUD, chapter detection, visual indicators, `toggleBookmark` |
| `03b-bookmark-render.js` | `showBookmarkAddedFeedback`, `initializeHomepageTOC`, `renderBookmarkChaptersBatch`, toast messages |
| `03c-bookmark-ui.js` | `renderIndexTOC`, `showBookmarkLoadingIndicator`, `renderBookmarks`, `updateBookmarkCount` |
| `03d-reading-settings.js` | `getDefaultFontSize`, `applyReadingSettings`, font/line-height/width updates, `updateReadingProgress`, `updateCurrentSection`, `showToast`, `copyText`, `handleInitialAnchor` |
| `04-events.js` | Click delegation, scroll/resize handlers, component initialisation on load |
| `05-search-btn-visibility.js` | Smart show/hide of top/bottom search activation buttons on scroll |
| `06-toc-collapse.js` | TOC expand/collapse, level display buttons, `renderIndexTOC` |
| `07-floating-controls.js` | Floating TOC level-control panel, scroll/resize synchronisation |
| `08-qa-audio.js` | QA per-segment audio playback: wires `.qa-play` buttons, builds the bottom floating mini-player (seekable progress bar, ±5s skip, play/pause toggle, Bilibili-style volume control — speaker button toggling a popup with a vertical slider persisted in `localStorage`), seeks to each segment's start and auto-stops at its end; shows loading/buffer progress on the play button and mini-player until playback can start |
| `09-image-lightbox.js` | Same-page image lightbox for `img[src*="assets/images/"]`: open original, zoom/pan, prev/next within the HTML page; keyboard Esc/arrows/+/-; isolated IIFE |

### Requirement: Single Output File
`StaticAssetsManager` SHALL concatenate all `modules/*.js` files (sorted by
name) and wrap them in one `DOMContentLoaded` listener to produce the single
`script.js` that is copied to the ebook output.

#### Scenario: Module concatenation
- GIVEN `assets/js/modules/` contains ordered `.js` module files
- WHEN `StaticAssetsManager.get_full_js_content()` is called
- THEN the returned string SHALL start with `document.addEventListener('DOMContentLoaded'`
- AND the returned string SHALL contain the content of every module file

### Requirement: Search Scope State
Search SHALL keep a session state variable `searchScope` with values
`question`, `answer`, or `both` (default `both`). Scope buttons with
`data-scope` SHALL update this state, toggle `is-active` / `aria-pressed`, and
re-invoke `performSearch` when the current query is at least 2 characters.
`clearSearch` SHALL NOT reset `searchScope`. The scope control SHALL stay hidden
until `performSearch` yields at least one result (`setSearchScopeVisible(true)`);
empty query, short query, zero hits, clear, and collapse SHALL hide it again.

#### Scenario: Scope change re-searches
- GIVEN an active query of length ≥ 2 and `searchScope` is `both`
- WHEN the user activates the `answer` scope button
- THEN `searchScope` SHALL become `answer` and `performSearch` SHALL run again
  with an answer-only filter

#### Scenario: Scope hidden until results exist
- GIVEN search has finished loading and the user has not yet produced results
- WHEN the search panel is shown
- THEN `.search-scope` SHALL NOT have class `is-visible`

### Requirement: Search Index Download Progress
When the index page downloads `search_index.json` / `search_index_trad.json`
over the network, the UI SHALL show a progress bar (same `.search-progress-*`
pattern as index building) with downloaded / total megabytes and a percentage.
The total byte count SHALL come from the companion `.hash` file's `size` field
(uncompressed JSON size), NOT from HTTP `Content-Length` (which reflects the
gzip-encoded transfer size under GitHub Pages). UI updates SHALL be throttled
(about every 100ms or when the percentage changes). When `size` is unavailable,
the UI SHALL show downloaded megabytes with an indeterminate progress bar.
When the index is loaded from IndexedDB cache, the download progress UI SHALL
be skipped and a short cache-loading message MAY be shown instead.

#### Scenario: Network download shows percentage from hash size
- GIVEN `.hash` reports `size` equal to the uncompressed index byte length
- WHEN `loadSearchIndexWithProgress` streams the index body
- THEN the status text SHALL include loaded MB, total MB, and a percentage
  that reaches 100% when the stream completes

#### Scenario: Missing hash size shows bytes only
- GIVEN no usable `.hash` `size`
- WHEN the index is downloaded
- THEN the status text SHALL show downloaded MB without a percentage denominator

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
- A volume control in Bilibili style: the only visible element is a speaker
  button (an inline pink SVG speaker icon at roughly 3/4 the size of the original
  emoji, with sound waves hidden when muted); clicking it SHALL toggle a popup
  containing a vertical volume slider (0–100 scale) that sets `audio.volume` /
  `audio.muted`. The popup SHALL show a numeric readout (0–100) of the current
  volume above the slider and SHALL fill the reached portion of the track (from
  the bottom up to the current level) with the primary colour. The popup SHALL
  close when the user clicks outside it, presses `Esc`, or closes the
  mini-player. The volume value SHALL persist in `localStorage['qa-volume']` and
  be restored on page load (default 1). Dragging the slider to 0 SHALL mute;
  dragging above 0 while muted SHALL unmute.
- Keyboard support on the progress bar: Left/Right arrows for ±5s, Space/Enter for
  play/pause

Clicking a segment's button SHALL seek and play that segment; reaching `data-end`
SHALL auto-stop; clicking the active segment again SHALL pause. Switching between
segments of the **same** audio file SHALL seek without reloading the source. The
audio filename SHALL be decoded for display with `decodeURIComponent`. The module
SHALL no-op on pages without `.qa-play` buttons. This module is isolated in its own
IIFE so its identifiers do not collide with the shared `DOMContentLoaded` scope.

While the audio resource is buffering (first load, mid-file seek, or a stall during
playback), the system SHALL show a loading state so the user can tell the wait is
intentional:

- The active `.qa-play` button SHALL gain a `loading` class, replace its speaker
  icon with a spinner (restoring the SVG via saved `innerHTML` when loading ends),
  and MAY fill a progress overlay from `--qa-load-pct` when buffer percent is known
- The mini-player SHALL gain `is-loading`, show a spinner on the toggle, display a
  loading message (with percent when available) in place of the time-range label,
  and treat the progress track as a buffer indicator (indeterminate pulse when
  percent is unknown)
- Seek / skip controls SHALL be inert while loading
- Loading UI SHOULD be delayed briefly (~100–150ms) to avoid flicker when the
  audio is already cached
- Loading SHALL clear on `playing`; an `error` event SHALL clear loading and show
  a failure message

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

#### Scenario: Loading feedback on first play
- GIVEN a QA chapter page whose audio file is not yet buffered
- WHEN the user clicks a `.qa-play` button
- THEN the play button and mini-player SHALL enter a loading state (spinner /
  loading message, optional buffer percent) until the `playing` event fires
  (or an `error` clears loading with a failure message)

#### Scenario: Volume control and persistence
- GIVEN a QA chapter page with the mini-player
- WHEN the user clicks the speaker button
- THEN a popup with a vertical volume slider SHALL appear and the button SHALL
  have `aria-expanded="true"`
- WHEN the user drags the slider to 80
- THEN `audio.volume` SHALL become 0.8, the numeric readout SHALL show `80`, the
  filled portion of the track SHALL cover 80% (from the bottom), and
  `localStorage['qa-volume']` SHALL be `"0.8"`
- WHEN the user clicks outside the control or presses `Esc`
- THEN the popup SHALL close and `aria-expanded` SHALL become `"false"`
- WHEN the user reloads the page with `localStorage['qa-volume']` set
- THEN the mini-player SHALL restore `audio.volume` from that value (defaulting to 1)

### Requirement: Same-Page Image Lightbox
On chapter pages, clicking an `img` whose `src` contains `assets/images/` SHALL
open a full-screen lightbox showing that image at its file resolution (not
constrained by the in-flow `max-width: 100%`). The lightbox SHALL:

- Fit the image to the viewport on open
- Allow zoom in/out via toolbar buttons, mouse wheel, and pinch-to-zoom
- Allow panning by drag when zoomed
- Toggle between fit-to-viewport and 1:1 via double-click / reset control
- Navigate previous/next among all matching images **on the same HTML page**
  (DOM order); prev/next SHALL be disabled at the ends (no wrap)
- Provide a control to jump to the image's Q&A context: close the lightbox and
  smooth-scroll to the enclosing `.question` / `.answer` (or the image itself
  if it is outside a card)
- Close on backdrop click, close button, or `Esc`
- Support keyboard: `←`/`→` for prev/next, `+`/`-` for zoom, `0` for fit
- Lock `body` scroll while open
- No-op on pages with no matching images
- Be isolated in its own IIFE so identifiers do not collide with the shared
  `DOMContentLoaded` scope

#### Scenario: Open original from chapter image
- GIVEN a chapter page with at least one `img[src*="assets/images/"]`
- WHEN the user clicks that image
- THEN an `.img-lightbox.is-open` overlay SHALL appear showing the same `src`
  fitted to the viewport

#### Scenario: Prev/next within the page
- GIVEN the lightbox is open on image 2 of 5 on the page
- WHEN the user activates next (button or `→`)
- THEN image 3 SHALL be shown and the counter SHALL read `3 / 5`
- WHEN on the last image
- THEN the next control SHALL be disabled

#### Scenario: Jump to Q&A from lightbox
- GIVEN the lightbox is open on an image inside a `.question` card
- WHEN the user activates the jump-to-Q&A control
- THEN the lightbox SHALL close and the page SHALL smooth-scroll to that
  `.question` element

#### Scenario: Zoom and close
- GIVEN the lightbox is open
- WHEN the user zooms in and then presses `Esc`
- THEN the overlay SHALL close and page scrolling SHALL be restored

## Technical Notes

- Source modules: `assets/js/modules/`
- Build step: `StaticAssetsManager.get_full_js_content()` in `templates/static_assets.py`
- The `DOMContentLoaded` wrapper open/close strings are defined as module-level
  constants `JS_WRAPPER_OPEN` and `JS_WRAPPER_CLOSE` in `static_assets.py`
