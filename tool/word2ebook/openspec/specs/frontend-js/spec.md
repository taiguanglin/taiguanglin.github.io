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
| `01d-search-perform.js` | `performSearch` (MiniSearch + scope `filter`) + URL-hash mirroring (`#q=…&scope=…` via `history.replaceState`), `displayPagedResults`, `loadMoreResults` |
| `01e-search-ui.js` | `getSearchElements`, `initSearch`, search event bindings (input, scope buttons, clear, collapse, load-more), hash-based search-state restore + auto-activate on back, result items open in new tab |
| `02-reader-ux.js` | Q&A ID generation, reading toolbar, floating TOC creation, action buttons, Q&A action overlays |
| `03a-bookmark-data.js` | Bookmark storage/migration, CRUD, chapter detection, visual indicators, `toggleBookmark` |
| `03b-bookmark-render.js` | `showBookmarkAddedFeedback`, `initializeHomepageTOC`, `renderBookmarkChaptersBatch`, toast messages |
| `03c-bookmark-ui.js` | `renderIndexTOC`, `showBookmarkLoadingIndicator`, `renderBookmarks`, `updateBookmarkCount` |
| `03d-reading-settings.js` | 閱讀設置的**事件接線**（`applyReadingSettings`、`updateFontSize`/`updateLineHeight`/`updateContentWidth`、轉呼叫 `window.W2EReading`）＋跨模組共用的狀態變數（`fontStep`/`fontSize`/`lineHeight`/`contentWidth`，供 02 按鈕狀態與 04 重設讀寫）＋`updateReadingProgress`, `updateCurrentSection`, `showToast`, `copyText`, `handleInitialAnchor`。**字級引擎本身已搬到 `assets/js/reading-prepaint.js`**（見下），此處不得再留第二份 |
| `04-events.js` | Click delegation, scroll/resize handlers, component initialisation on load |
| `05-search-btn-visibility.js` | Smart show/hide of top/bottom search activation buttons on scroll |
| `06-toc-collapse.js` | TOC expand/collapse, level display buttons, `renderIndexTOC`, manual expand-state snapshot/restore (`sessionStorage` per book, `data-id` stable keys) |
| `07-floating-controls.js` | Floating TOC level-control panel, scroll/resize synchronisation |
| `08-qa-audio.js` | QA per-segment audio playback: wires `.qa-play` buttons, builds the bottom floating mini-player (seekable progress bar, ±5s skip, play/pause toggle, Bilibili-style volume control — hovering the speaker button shows a popup with a vertical slider persisted in `localStorage`, moving away hides it, clicking the speaker toggles mute/unmute), seeks to each segment's start and auto-stops at its end; shows loading/buffer progress on the play button and mini-player until playback can start |
| `09-image-lightbox.js` | Same-page image lightbox for `img[src*="assets/images/"]`: open original, zoom/pan, prev/next within the HTML page; keyboard Esc/arrows/+/-; isolated IIFE |
| `09b-para-track.js` | 講經「段落跟播」（講經書頁，段落帶 `data-start`/`data-end` 時啟動；經 `08-qa-audio.js` 暴露的 `W2E.qaAudio` 掛接）：講次 h2 旁插入「段落跟播」toggle（`paraTrackEnabled`，預設 ON）— ON 時播放中依 `audio.currentTime` 高亮當前段落（`.para-active`，上一段不做任何視覺改變）並平滑捲動（目標 = min(當前段頂 − 22% 視窗高, 當前段頂 − 上一段高 − 24px)；若目標段落屬於經文置頂 sticky 群，另以「當前段頂 − `W2E.sutraPin.reserveFor(el)` − 24px」為捲動上限，使高亮段落永遠落在停留經文下方不被蓋住，僅段落切換時觸發，timeupdate 節流 250ms）；跟播 ON 時點擊段落即播放所屬講次並 seek 至段首，之後一路順播到底（無段末自停；拖選／反白選取文字、點擊段落內按鈕連結時不觸發）；isolated IIFE |
| `09c-sutra-pin.js` | 講經「經文置頂」（原經文原尺寸停留，頁面含 `.sutra-text` 時啟動）：向下捲動時讓「即將捲出視窗頂」的那段原經文以原生 `position: sticky; top: 0` 停在視窗最上方——停留中的經文就是原版經文本身（原尺寸、原樣式、無白邊），講解段落從其下方滑過（Confluence 固定表頭概念）。為每段經文包 `.sutra-pin-host`（只包層、不搬動順序），再以「經文 → 下一邊界」包 `.sutra-pin-group` 限制 sticky 範圍：邊界 = 下一段經文、任何 h1–h6（章節名/品名小節名）、任何 figure/img 圖片（取文件順序最先者；無邊界則到下一經文頂層節點/章節尾）——因此停留中的經文天生不會蓋住下一段經文、章節名或圖片，會遮住之前先讓位歸位（隨畫面捲走），進入新章節亦自然失效。過長（> 45% 視窗高）的經文整段不停留（`.sutra-pin-tall`），且經文高度隨閱讀設定（字級／行距／版面寬）、視窗縮放或字型載入改變時會重新量測（`ResizeObserver` + `<html>/<body>` inline style `MutationObserver` + `document.fonts.ready`），避免放大字級後接近滿版的經文仍卡在置頂、蓋住講解；講次 h2 旁「經文置頂」toggle（`sutraPinEnabled`，預設 ON；關閉 → `body.sutra-pin-off` 全部照常捲動）；錨點跳轉（`hashchange`／帶 hash 載入／攔截 `scrollIntoView`）時 `body.sutra-pin-suppress` 短暫停停留避免蓋住跳轉目標；把「停留經文高 + 16px 間隙」寫進群的 `--w2e-pin-reserve`（inline style，與 `applyTallClasses` 同一次量測；置頂關閉或 `.sutra-pin-tall` 時歸零，切換 toggle 時重算），CSS 據此轉成群內目標的 `scroll-margin-top`，使所有把目標對齊視窗頂的跳轉（外部連結的原生片段錨點導覽、章節錨點、浮動目錄、書籤、`.toc-count` 直跳）都停在停留經文下方；暴露 `W2E.sutraPin.reserveFor(el)`（回傳同一個「經文高 + 間隙」）供 09b 跟播捲動取捲動上限（高亮段落永遠在停留經文下方）與 03d 錨點讓位使用；isolated IIFE |
| `10-search-return.js` | ~~「回到搜尋結果」浮動按鈕~~（2026-09 移除：依賴快照跨分頁複製，出現時機不穩）。現僅保留 index 頁持續快照 `{q, scope, displayed, scrollY}`（`w2eSearchSnapshot`，sessionStorage），供上一頁返回時由 01e 還原查詢、已顯示筆數與捲動位置；另負責**簡繁切換原位恢復**——消化 `/lang-switch.js` 寫入的 `w2e:langjump`（優先同 id 錨點，其次比例，讀完即清） |
| `11-reading-resume.js` | **已移除（2026-10）**：閱讀位置記憶（`w2e:readpos`）與「上次讀到 XX%」提示條功能裁撤；簡繁切換原位恢復由 10 消化 `w2e:langjump` 承接 |
| `13-player-persist.js` | 音檔跨頁續播：定時（3s）與 `pagehide` 把 `{src, t, file, range, page, anchor}` 快照進 `sessionStorage w2e:playerState`（經 `W2E.qaAudio` 讀取）；任何頁載入後若有 12 小時內快照，左下浮出續播膠囊——同頁交回 08 播放器重播並 `seekAbs`，他頁自建 `Audio` 從斷點續播；✕ 丟棄 |
| `14-search-plus.js` | 搜尋補強：`/` 或 Ctrl/Cmd+K 啟用並聚焦搜尋框；結果區 ↓/↑ 移動 `.kb-focus`、Enter 開啟、Esc 取消，結果列表重繪（換搜尋/換頁）時以 `MutationObserver`（childList/subtree）重置鍵盤焦點（不得使用已棄用的 `DOMSubtreeModified`）；章節頁帶 `?q=`（01e 開新頁時附加）且有錨點時，於錨點所在區塊以 `<mark class="w2e-hl">` 標出查詢詞 |
| `15-mobile-toc.js` | 行動版目錄操作：≤768px 開啟浮動目錄時鋪 `.w2e-toc-backdrop`（點擊即關）；左緣 ≤28px 起右滑開啟、目錄內左滑關閉。**不**再建立常駐的 `.w2e-backtop` 回到頂端鈕——「回到頂端」只由右下角功能選單（`02-reader-ux.js` 的 `data-action="top"`）提供 |
| `16-jump-share.js` | `.toc-count` 可點：直跳該主題第一則 `.question`（無則退回錨點）；章節頁 h2/h3[id] hover/focus 出現 🔗 錨點鈕複製「頁面#錨點」 |
| `17-theme-pwa.js` | 深色第二面板「墨夜」：`localStorage w2e:darkPalette=neutral` 時 `body.dark-neutral`（防閃爍由模板 prepaint 掛 `<html>`）；供 04-events.js 的 `theme-dark-neutral` 動作呼叫；`/wenda2_ebook/`、`/ebook/` 下註冊根 `/sw.js`（PWA 離線） |

> 編號 `12-bookmarks-manager.js`（首頁總目錄底部的「我的書籤」跨章節管理區塊）已移除，
> 編號保留空缺、不重排。書籤本體功能（03a/03b/03c：章節頁加書籤、浮動目錄書籤分頁、
> 書籤計數）不受影響；書籤改由浮動目錄面板的書籤分頁檢視與管理。

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
`dark-mode` class to `<body>` if the value is `'true'` (`shouldUseDarkMode`);
when the key is unset, first paint SHALL honor the OS preference via
`matchMedia('(prefers-color-scheme: dark)')` (the inline head script applies
`dark-mode` to `<html>` pre-paint; `00-base.js` re-applies it to `<body>` and
removes it from `<html>`).

### Requirement: Reading Settings Pre-Paint
Font size, line height, content width, and the TOC/search font sizes derived
from them SHALL be applied **before first paint**, not on `DOMContentLoaded`.

The single source of truth SHALL be `assets/js/reading-prepaint.js`
(standalone, copied verbatim, exposed as `window.W2EReading`). It SHALL execute
synchronously in `<head>` and apply itself on load. `03d-reading-settings.js`
SHALL only wire user interactions to `W2EReading` and SHALL NOT keep a second
copy of the ladder constants or the derived-CSS generation.

Rationale (measured): applying these from `DOMContentLoaded` painted chapter
pages at 16px/800px and then re-laid-out to 20px/834px, shifting the whole TOC
(indent 251px → 234px) and reporting CLS ≈ 0.005.

Because it runs before `<body>` exists, `reading-prepaint.js` SHALL write CSS
custom properties on `<html>` — `--w2e-font-size`, `--w2e-content-width`,
`--line-height` — which `00-base.css`'s `body` rule consumes, and SHALL NOT use
`document.body.style`.

#### Scenario: Script tag placement is load-bearing
- GIVEN `reading-prepaint.js` injects a `<style>` whose `.toc > ul > li`
  declaration has the same specificity as `04a-toc-levels.css`'s
  `.toc > ul > li { line-height: 1.4 !important }`, both `!important`
- WHEN the `<script src="assets/js/reading-prepaint.js">` tag precedes the
  stylesheet links in `<head>`
- THEN the injected style loses the cascade, TOC line height renders as 1.4
- AND when `03d` re-injects it later (now after the stylesheet) line height
  becomes 1.6, shifting every TOC row
- THEREFORE the template SHALL place the tag after the **last** stylesheet link,
  and SHALL NOT mark it `defer`

#### Scenario: No layout shift on load
- GIVEN any generated index or chapter page loaded with JS enabled
- WHEN measured under throttled network until the deferred bundle has run
- THEN cumulative layout shift SHALL be 0
- AND `body` width/font-size SHALL already equal the final values at first paint

### Requirement: Default Reading Font Size
The system SHALL derive the default body font size from the viewport width as
`base + FONT_SIZE_STEP × steps`, where one step is the A+/A- increment
(`FONT_SIZE_STEP = 2`). The per-device ladder SHALL be:

| Viewport | Base | Steps | Default |
|----------|------|-------|---------|
| ≤400px (small phone) | 19 | 0 | 19px |
| ≤600px (phone) | 18 | 0 | 18px |
| ≤768px (tablet) | 17 | 1 | 19px |
| >768px, fine pointer (desktop) | 16 | 2 | 20px |
| >768px, coarse pointer (handheld) | 17 | 1 | 19px |

The desktop default SHALL equal the size reached by pressing A+ twice, the
tablet default by pressing A+ once, and phones SHALL keep their former defaults.
A touch-primary device (`matchMedia('(pointer: coarse)')`) SHALL resolve to the
tablet tier at any width, so a landscape phone or tablet does not inherit the
desktop's base and +2 boost. A touchscreen laptop keeps the desktop tier because
its primary pointer is still a mouse.

On TOC pages (`isIndexPage()` — `index.html` / `index_trad.html` of either
book) the boost SHALL NOT apply at any width: `getDefaultFontSize` SHALL return
the bare base value (19 / 18 / 17 / 16), because a larger TOC font wraps more
titles onto extra lines and doubles the scrolling needed to scan the book.

A reader-stored preference SHALL still win over the default (the load path must
not persist a default on its own), so a size chosen on a TOC page carries over to
chapter pages unchanged. See "Font Preference Stored as a Step Offset" for the
storage format and the legacy migration.

`updateFontSize` SHALL clamp to `[FONT_SIZE_MIN, FONT_SIZE_MAX]` = `[14, 28]`.
The floor is 14px rather than 12px because Latin script stays marginally legible
at 12px while Chinese glyph strokes merge together. The ceiling stays three
steps above the boosted desktop default, and the A+ / A- handlers SHALL move by
`FONT_SIZE_STEP` rather than a hard-coded 2.

### Requirement: Font Preference Stored as a Step Offset
`localStorage['fontStep']` SHALL hold the reader's font size as a signed count
of steps relative to the current page default, not as an absolute pixel value.
`fontSize` SHALL be `clampFontSize(getDefaultFontSize() + fontStep ×
FONT_SIZE_STEP)`. An absolute value ties the preference to the device it was
chosen on — 22px on a desktop becomes oversized on a 390px phone — while a step
count ("two steps above the default") holds on every device.

A legacy absolute `localStorage['fontSize']` SHALL be migrated once on load:
`step = round((legacy − getBaseFontSize()) / FONT_SIZE_STEP)`, measured against
the device-independent base (16/17/18/19) because that is what the old absolute
values were derived from. The migration SHALL write `fontStep` and SHALL remove
the legacy key so it cannot re-run on every load. A step of `0` is a legitimate
value and SHALL NOT be treated as "unset". A reader who never touched the
setting SHALL have no `fontStep` key written, so a future change to the default
ladder still reaches them.

`updateFontSize` SHALL recompute the step from the resulting size
(`round((fontSize − getDefaultFontSize()) / FONT_SIZE_STEP)`) and persist it.
The `A` (`font-normal`) button SHALL set the step to `0` and persist that; it
no longer needs a page-type guard, because `0` means "the default" on both page
types rather than the compact TOC size. The `A` button's selected state SHALL be
driven by `fontStep === 0` instead of comparing against a hard-coded pixel
value. The size is resolved once at load and SHALL NOT be recomputed on resize,
matching the previous behaviour.

#### Scenario: A desktop preference travels to a phone
- GIVEN `fontStep` is `2`, recorded on a desktop
- WHEN the same reader opens a chapter page on a 500px-wide phone
- THEN the body font size SHALL be 22px (18px phone default + two steps)
- AND NOT the 24px that the old absolute storage would have produced

#### Scenario: Legacy absolute value migrates once
- GIVEN `localStorage['fontSize']` is `16` and no `fontStep`, on a desktop
- WHEN the page loads
- THEN `fontStep` SHALL be written as `0`
- AND `localStorage['fontSize']` SHALL be removed
- AND the chapter page SHALL render at the 20px default

#### Scenario: Resetting writes a portable step
- GIVEN `fontStep` is `2` on a TOC page
- WHEN the user presses `A`
- THEN `fontStep` SHALL be `0`
- AND the TOC SHALL render at its 16px default
- AND a chapter page opened afterwards SHALL render at 20px, not 16px

### Requirement: Measure-Linked Content Width
`getDefaultContentWidth()` SHALL size the column from the font size rather than
from the viewport: `min(max(MEASURE_TARGET_CHARS × fontSize + CONTENT_CHROME_PX,
CONTENT_WIDTH_MIN), CONTENT_WIDTH_MAX)` with `MEASURE_TARGET_CHARS = 40` and
`CONTENT_CHROME_PX = 34` (the `.question`/`.answer` horizontal padding and
border). This keeps the CJK measure at 40 characters per line — inside the
30–45 comfortable band — for every default font size, and still ≥34 characters
at the 28px ceiling.

In-paragraph overlays (ebook's top-right `⋯` bubble and bookmark mark) SHALL NOT be given room by shrinking the text column: they sit outside the paragraph box so the measure is untouched.

The previous rule (`innerWidth >= 1400 ? 1000 : 800`) SHALL no longer exist: at
20px it produced a 48-character measure on wide screens. TOC pages SHALL keep a
fixed 800px column, since chapter titles are short labels rather than prose and
the existing layout is established. An explicit 窄/中/寬 choice stored in
`localStorage['contentWidth']` SHALL still win; with only an automatic width no
width button shows as selected, which correctly means "no explicit choice".

#### Scenario: Wide screen no longer over-uses the line
- GIVEN no stored `fontSize` or `contentWidth` and a 1920px viewport
- WHEN a chapter page applies reading settings
- THEN the content width SHALL be 834px
- AND the measure SHALL be 40 characters per line

#### Scenario: Measure holds at the largest font
- GIVEN the user has raised the font to 28px
- WHEN the page re-applies reading settings with no stored width
- THEN the content width SHALL be capped at 1000px
- AND the measure SHALL be at least 34 characters per line

#### Scenario: First visit on a desktop viewport
- GIVEN no `localStorage['fontSize']` and a viewport wider than 768px
- WHEN a chapter page applies reading settings
- THEN the body font size SHALL be 20px
- AND pressing A+ twice from the former 16px base would have produced the same size

#### Scenario: Tablet gets one step, phone gets none
- GIVEN no `localStorage['fontSize']`
- WHEN a chapter page applies reading settings on a 700px-wide viewport
- THEN the body font size SHALL be 19px
- AND on a 390px-wide viewport it SHALL be 19px (unchanged from the old default)

#### Scenario: TOC page stays compact
- GIVEN no `localStorage['fontSize']` and a viewport wider than 768px
- WHEN `/ebook/index.html` or `/wenda2_ebook/index.html` applies reading settings
- THEN the body font size SHALL be 16px
- AND `/ebook/chapter_01.html` on the same viewport and same session SHALL be 20px

#### Scenario: Stored preference is kept
- GIVEN `fontStep` is `1`
- WHEN a chapter page applies reading settings on a desktop
- THEN the body font size SHALL be 22px
- AND the `A` button SHALL NOT be shown as selected

#### Scenario: Landscape phone is not treated as a desktop
- GIVEN a touch-primary device reporting an 844px-wide viewport
- WHEN a chapter page applies reading settings
- THEN the body font size SHALL be 19px (tablet tier), not 20px

### Requirement: Initial Anchor Highlight
When a chapter page loads with a valid URL fragment, `handleInitialAnchor`
SHALL scroll the matching element into view and apply the
`anchor-target-highlight` class for three seconds. The highlight SHALL be
class-based so it remains visible on elements such as `.sutra-text` that
already have a gradient background.

The element's resting offset SHALL be `anchorTargetOffset(el)`: when the
element sits inside a sticky 經文置頂 group the offset SHALL be
`W2E.sutraPin.reserveFor(el)` (pinned-sutra height + gap) so the pinned sutra
never hides it; otherwise the element SHALL be vertically centred. Because
`content-visibility: auto` + `contain-intrinsic-size` makes the document height
change while scrolling (estimated heights are replaced by real ones as blocks
enter/leave the viewport), a single scroll lands off-target — `settleAnchorTo`
SHALL re-measure and correct every 150ms until the position is stable twice in
a row (max ~6s), and SHALL stop immediately when the user scrolls
(wheel/touchstart/arrow/page/home/end/space) so it never fights the reader.

#### Scenario: Search result opens a scripture paragraph
- GIVEN a search result URL targets a `.sutra-text` element in a new tab
- WHEN the chapter page loads
- THEN the scripture paragraph SHALL scroll into view
- AND a temporary red highlight SHALL remain visible for three seconds

#### Scenario: External link jumps into a lectured paragraph
- GIVEN a讲经 page and a link `NN.html?q=…#p-xxx` whose target paragraph is
  inside a sticky 經文置頂 group
- WHEN the page finishes loading
- THEN the paragraph SHALL rest below the pinned sutra (offset ≥ sutra height
  + gap) and no pixel of it SHALL be hidden behind the pinned sutra
- AND the same clearance SHALL apply to in-page jumps that align the target to
  the viewport top (floating TOC, bookmarks, `.toc-count`, in-page anchors),
  because 09c writes the reserve as `scroll-margin-top` on the group

#### Scenario: Page without sutra pinning
- GIVEN a chapter page with no `.sutra-text`
- WHEN it loads with a fragment
- THEN the target SHALL be vertically centred with `scroll-margin-top: 0`

#### Scenario: In-page TOC anchor click lands on target
- GIVEN any chapter page and an in-page `#…` anchor link (TOC, back-links)
- WHEN the link is clicked and the smooth scroll finishes
- THEN `05-search-btn-visibility.js` SHALL re-measure and correct the
  position every 150ms until stable twice in a row (same convergence rules
  as `settleAnchorTo`: max ~6s, user input cancels), because
  `content-visibility` height estimates change the document height mid-scroll
  and a one-shot scroll lands off-target (observed ±600px in both books)

### Requirement: Stable Q&A IDs
JavaScript IDs for Q&A elements SHALL be computed using the same algorithm as
the Python side: `MD5(questioner + normalized_time + first_50_chars)[0:12]`.
`02-reader-ux.js` SHALL compute this with a full MD5 implementation
(`md5Hex`, UTF-8 via TextEncoder) so JS and Python digests match exactly;
`simpleHash` is `md5Hex(str).substring(0, 12)`. Legacy fallback id schemes and
their multi-id lookups are removed.

#### Scenario: ID consistency
- GIVEN a question with questioner "甲", time "2024-01-15 10:30", and text "內容"
- WHEN the JavaScript `generateStableContentId` function runs
- THEN the resulting hash SHALL match the Python `IDGenerator.generate_stable_qa_id` output

### Requirement: Bookmark Navigation
`jumpToBookmark` SHALL navigate in the same tab (`window.location.href`),
consistent with search-result and TOC navigation (no tab accumulation).

### Requirement: Bookmark Persistence
Bookmarks SHALL be stored in `localStorage` under language-specific keys:
- `ebook-bookmarks-simplified` for simplified pages
- `ebook-bookmarks-traditional` for traditional pages

### Requirement: QA Per-Segment Audio Playback
On pages containing `.qa-play` buttons, the system SHALL play the segment's audio
clip from `data-start` to `data-end` (seconds) using the URL in `data-audio`, and
SHALL display a bottom floating mini-player showing the decoded audio filename and
the `data-label` time range. During playback the time-range label SHALL update to
the current playback position followed by the segment end time (e.g.
`00:12:34 - 00:36:39`), replacing the static start–end label so the user always
sees the live position; when loading it SHALL temporarily show a loading message
instead. The mini-player SHALL provide:

- A play/pause toggle button
- A draggable progress bar (pointer drag on the track) to seek within the current
  segment bounds (`data-start` … `data-end`)
- `−5s` and `+5s` skip buttons that adjust playback within the same segment bounds
- A volume control in Bilibili style: the only visible element is a speaker
  button (an inline pink SVG speaker icon at roughly 3/4 the size of the original
  emoji, with sound waves hidden and a slash shown when muted). Hovering the
  speaker button SHALL show a popup containing a vertical volume slider (0–100
  scale) that sets `audio.volume` / `audio.muted`; moving the pointer away from
  the button and popup SHALL hide it. Clicking the speaker button SHALL toggle
  mute: muting SHALL remember the current volume and unmuting SHALL restore it
  (falling back to 1 when unmuting from 0). The popup SHALL show a numeric
  readout (0–100) of the current volume above the slider and SHALL fill the
  reached portion of the track (from the bottom up to the current level) with the
  primary colour. The popup SHALL also close when the user clicks outside it,
  presses `Esc`, or closes the mini-player. The volume value SHALL persist in
  `localStorage['qa-volume']` and be restored on page load (default 1). Dragging
  the slider to 0 SHALL mute; dragging above 0 while muted SHALL unmute.
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

#### Scenario: Live playback position in the time-range label
- GIVEN the mini-player is visible and audio is playing
- WHEN the audio emits `timeupdate`
- THEN the time-range label SHALL show `HH:MM:SS - HH:MM:SS` where the left value
  is the current playback position (formatted from `audio.currentTime`) and the
  right value is the segment end time (`data-end`, falling back to the audio
  duration when `data-end` is absent)

#### Scenario: Volume control, mute toggle, and persistence
- GIVEN a QA chapter page with the mini-player
- WHEN the user moves the pointer over the speaker button
- THEN a popup with a vertical volume slider SHALL appear and the button SHALL
  have `aria-expanded="true"`
- WHEN the user moves the pointer away from the button and popup
- THEN the popup SHALL close and `aria-expanded` SHALL become `"false"`
- WHEN the user drags the slider to 80
- THEN `audio.volume` SHALL become 0.8, the numeric readout SHALL show `80`, the
  filled portion of the track SHALL cover 80% (from the bottom), and
  `localStorage['qa-volume']` SHALL be `"0.8"`
- WHEN the user clicks the speaker button while audible
- THEN the audio SHALL mute, the icon SHALL hide the sound waves and show the
  muted slash, and the current volume SHALL be remembered
- WHEN the user clicks the speaker button again
- THEN the audio SHALL unmute and the previous volume SHALL be restored
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

### Requirement: Toolbar Button Semantics
Toolbar control groups (`.toolbar-controls`) SHALL carry `role="group"` with
`aria-label`; state-toggle option buttons SHALL reflect their state via
`aria-pressed` (synchronized by `syncToolbarAriaPressed` on theme/reading
updates). Action buttons (e.g. font-adjust) SHALL NOT carry `aria-pressed`.

### Requirement: Escape Closes Floating Panels
Pressing the `Escape` key SHALL close all floating panels (action menu,
floating TOC, reading toolbar) via `closeSidebars()`.

### Requirement: TOC Icon State Sync
All TOC expand-icon mutations SHALL go through `setTocIconState(icon, expanded)`
which toggles the collapsed class, swaps ▼/▶, and keeps `aria-expanded` in sync
(`06-toc-collapse.js`). The handler MUST be delegated and idempotent for
`<button>` icons (no double-toggle).

### Requirement: TOC Level Resolution Agrees With the Server
`selectValidLevel()` and the generators' `resolve_display_level()` SHALL agree,
because JS re-applies the level on startup and any disagreement causes a visible
reflow of an already-correct server-rendered TOC:
- default level — index 2, chapter 3 (`DEFAULT_TOC_LEVEL_INDEX` /
  `DEFAULT_TOC_LEVEL_CHAPTER` in `toc_generator.py` mirror
  `defaultLevel = isChapterPage ? '3' : '2'`);
- snapping — when the default level has no items, the *nearest* level that has
  both items and a level button wins, ties resolving to the smaller level;
- `setTocDisplayLevel()` visibility — items with `data-level` greater than the
  target level get `.hidden`, matching the server-emitted `hidden` class;
- icon state — items *below* the target level expand, items *at* it collapse.

JS SHALL treat the server-rendered state as the baseline and only override it
with the user's stored preference; `initializeTocExpandableItems()` SHALL remain
a no-op re-assertion of the already-present `toc-expandable` class.

### Requirement: QA Play Button Accessibility
Rendered QA play buttons SHALL include
`aria-label="播放 {HH:MM:SS - HH:MM:SS}"` (server-side in `qa_play_markup`);
the client mini-player SHALL continue announcing via the label element.

### Requirement: Image Markup Contract
All `<img>` tags in generated HTML SHALL carry `loading="lazy"`, a meaningful
`alt` (nearest text context, e.g. `alt_from_context`), and, when the file is
readable, explicit `width`/`height` (from `image_dimensions`, which detects
PNG/JPEG/WebP) to prevent layout
shift (`utils/image_markup.py::render_img_tag` — shared by document_parser,
pdf_parser and books2ebook).
