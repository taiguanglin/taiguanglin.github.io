# Search Specification

## Purpose

The search domain generates JSON search indexes from the produced HTML pages and
provides a client-side search UI powered by MiniSearch and optional Jieba WASM
segmentation for Chinese text.

## Requirements

### Requirement: Search Index Generation
The system SHALL produce `search_index.json` (simplified) and
`search_index_trad.json` (traditional) in the output root.

#### Scenario: Index structure
- GIVEN generated chapter HTML files
- WHEN `SearchIndexGenerator.generate_search_indexes` is called
- THEN each JSON file SHALL be a top-level JSON array where every element
  contains at minimum the fields `id`, `content`, `type`, and `url`

### Requirement: Item Types
The search index SHALL contain items of type `heading`, `question`, `answer`,
and `content`. Short paragraphs (below `Settings.search_min_paragraph_length`)
MUST be excluded from the content items.

### Requirement: Question and Answer Result Titles
Question search items SHALL use a title of `questioner | question-time` when
both are present (falling back to whichever exists, or
`Constants.DEFAULT_QUESTION_TITLE`). Answer search items SHALL use a title of
`{answerer display name}的回答`, and when the immediately preceding sibling
`.question` has a `.question-time`, SHALL append that same timestamp as
` | {question-time}` so answer results show the related question's time.

When a question has no `.question-time`, and the nearest preceding `<h2>` is a
PDF date+source section (`YYYY年M月D日` plus `贴吧` / `官网` / `微信公众号`, or
their traditional forms), both the question and its answer search titles SHALL
append that section label (without the `.chapter-qa-count` badge) after ` | `,
so results identify which day's Tieba / official-site / WeChat Q&A they belong
to. Topical Word-chapter `<h2>` headings MUST NOT be used for this fallback.

#### Scenario: Answer title includes related question time
- GIVEN HTML with a `.question` that has `.question-time` `2024-01-15 10:30`
  immediately followed by a `.answer` whose `.answerer` is `Taiguanglin`
- WHEN the content extractor runs
- THEN the answer item `title` SHALL be `Tai師父的回答 | 2024-01-15 10:30`

#### Scenario: Answer title without question time
- GIVEN HTML with a `.question` that has no `.question-time`, followed by a
  `.answer`, and no PDF date+source `<h2>` before them
- WHEN the content extractor runs
- THEN the answer item `title` SHALL be `Tai師父的回答` with no trailing
  timestamp

#### Scenario: PDF section label fallback when question has no time
- GIVEN HTML with `<h2>2025年11月10日 官網<span class="chapter-qa-count">(138)</span></h2>`
  followed by a `.question` (questioner `印龍`, no `.question-time`) and
  `.answer` (`Taiguanglin`)
- WHEN the content extractor runs
- THEN the question item `title` SHALL be `印龍 | 2025年11月10日 官網`
- AND the answer item `title` SHALL be `Tai師父的回答 | 2025年11月10日 官網`

#### Scenario: Topical Word heading is not used as fallback
- GIVEN HTML with `<h2>初始設定1.自性恆常</h2>` followed by a question with no
  `.question-time` and an answer
- WHEN the content extractor runs
- THEN neither title SHALL append that topical heading

### Requirement: Deduplication of QA from Content
Paragraphs that are direct children of `.question` or `.answer` elements SHALL
NOT be duplicated as `content` items.

#### Scenario: QA paragraph not duplicated
- GIVEN HTML with a `.question` div containing a `<p>` child
- WHEN the content extractor runs
- THEN the `<p>` SHALL appear as a `question` item only, not also as a `content` item

### Requirement: Index Hash File
Alongside each index file the system SHALL write a `.md5` hash file named
`search_index.json.md5` (and `search_index_trad.json.md5`) containing the
MD5 hex digest of the JSON content, used by the client-side cache invalidation.

### Requirement: Ensure Index Files
When `--skip-index` is passed, the system SHALL call `ensure_search_index_files`
which creates empty (`[]`) JSON files only if the files do not already exist,
preserving any pre-existing index.

#### Scenario: Existing index preserved
- GIVEN `search_index.json` already exists in the output folder
- WHEN `ensure_search_index_files` is called
- THEN the existing file SHALL NOT be overwritten

### Requirement: Client-Side Search
The index pages SHALL load MiniSearch from the self-hosted bundle
`assets/js/minisearch.min.js` via a deferred `<script>` (no third-party origin,
so the site works on networks where public CDNs are unreachable). If the local
bundle is missing or fails, `ensureMiniSearchLoaded` (01e-search-ui.js) SHALL
dynamically inject the CDN fallbacks from `Constants.MINISEARCH_CDN_PRIMARY`
then `MINISEARCH_CDN_BACKUP` before search init; when all sources fail the
search input SHALL be disabled with a localized status message.
Chinese text search SHALL use the Jieba WASM segmenter when available; the
system SHALL fall back to substring matching when Jieba is unavailable.
The segmenter SHALL be initialized concurrently with index download/cache
checks, and awaited only after the index is loaded (parallel startup).

#### Scenario: Local bundle unavailable
- GIVEN `assets/js/minisearch.min.js` fails to load (or `MiniSearch` is undefined)
- WHEN `initSearch` runs
- THEN the loader SHALL inject the primary CDN script, then the backup on failure
- AND search SHALL work normally after either succeeds

### Requirement: Index Fields Exclude Context
The index items SHALL contain `id`, `title`, `type`, `content`, `url` — and
SHALL NOT contain a `context` field (it duplicated `content` and inflated the
index ~30%). Search-result snippets SHALL be derived live from `content` via
`getBestContextForHighlight` (exact-match window first, then multi-keyword
window, then head-window) and `trimSnippet` (~160 chars, sentence-aware trim).

### Requirement: Search Result Navigation
Selecting a search result SHALL open the target in a new tab
(`window.open(url, '_blank', 'noopener')`). The index page (query, results,
scope, scroll position) therefore stays intact — going back to it MUST NOT
re-download the search index. Before opening, the current manual TOC expand
state SHALL be snapshotted to `sessionStorage` (same as TOC links) so that a
browser configured to open `target=_blank` in the same tab still restores the
TOC state on return.

#### Scenario: Result opens in a new tab
- GIVEN an index page with active search results
- WHEN the user clicks a `.search-result-item`
- THEN the target URL SHALL open in a new tab
- AND the index page SHALL keep displaying the same results

### Requirement: Search State Persists Across Navigation
`performSearch` SHALL mirror the active query and scope into the URL hash as
`#q=<encoded>&scope=<encoded>` via `history.replaceState` (scope only when not
`both`); an empty query clears the hash. No new history entry SHALL be created.

When the index page loads with a `#q=` hash (or the module-load check sees one),
the search UI SHALL auto-activate (skip the enable button), restore the query
input and scope buttons from the hash, and re-run the search once the index is
ready — so browser-back from a chapter returns the user to their results without
a manual re-query. Manual clear/collapse SHALL still wipe the hash.

#### Scenario: Back navigation restores results
- GIVEN the user searched `自性` on the index page and opened a result in a new tab
- WHEN the user returns to the index page via browser back
- THEN the search panel SHALL be active with `自性` in the input
- AND the previous results SHALL be re-displayed without user action

### Requirement: Search State Snapshot with Scroll and Pagination
The index page SHALL persist `{q, scope, displayed, scrollY}` to
`sessionStorage` (per-tab, key `w2eSearchSnapshot`) whenever results, the
displayed count, or the scroll position change (throttled for scroll, exact on
`pagehide` and load-more clicks). Clearing or collapsing the search SHALL
remove the snapshot. When restoring, the displayed count SHALL be replayed
(`displayPagedResults(query, targetDisplayedCount)` shows results 1..N in one
pass) and the saved scroll position SHALL be re-applied after layout settles.

#### Scenario: Displayed count survives back navigation
- GIVEN the user clicked 「显示更多」 twice (60 displayed) then left the page
- WHEN the search state is restored on return
- THEN 60 results SHALL be displayed without extra clicks

#### Scenario: Scroll position survives back navigation
- GIVEN the snapshot recorded a scroll position of 2400px
- WHEN the search state is restored on return
- THEN the page SHALL scroll back to approximately 2400px after results render

### Requirement: Search Return Button (removed)
~~Chapter pages show a fixed「回到搜尋結果」button.~~ REMOVED 2026-09: the
button's visibility depended on the `w2eSearchSnapshot` sessionStorage entry
surviving into a `_blank`-opened tab, which is unreliable, so the button
rarely appeared. `10-search-return.js` now only keeps the index-page snapshot
capture (used by `restoreSearchFromHash`); users return via the browser's
back button or the chapter's home link. No chapter page SHALL inject a
`#search-return-btn` element, and the bundled CSS SHALL contain no
`.search-return-btn` rules. On the index page the `?q=`/`?scope=` query
parameters SHALL still be honoured like the hash and auto-activate search.

### Requirement: Configurable Default Scope Types
The client `both` scope SHALL read its allow-list from
`window.W2E_SEARCH_SCOPE_TYPES` when present (set by a deployment-specific
`w2e-config.js`), defaulting to `['question', 'answer']`. The books2ebook
deployment sets `['question', 'answer', 'content', 'heading']` so prose
paragraphs are searchable.

### Requirement: Index Download Progress Uses Hash Size
The client SHALL use the `.hash` file's `size` field (uncompressed UTF-8 byte
length of the JSON) as the progress denominator when streaming the search index.
It MUST NOT use HTTP `Content-Length` for percentage progress, because GitHub
Pages serves the JSON with `Content-Encoding: gzip` while `fetch` exposes the
decompressed body stream.

### Requirement: Search Scope Filter
The index-page search UI SHALL provide a mutually exclusive scope control with
three modes: `question` (only `type=question`), `answer` (only `type=answer`),
and `both` (default; `question` and `answer`). MiniSearch queries SHALL apply a
`filter` that keeps only results whose `type` is in the active mode's allow-list.
`heading` and `content` items SHALL NOT match any of these three modes. Changing
scope while the query has at least 2 characters SHALL re-run the search.
Clearing the search SHALL reset the query and results but SHALL preserve the
active scope.

The scope control (`.search-scope`) SHALL remain hidden during index loading and
while the input is empty / shorter than the minimum query length. It SHALL become
visible (`.is-visible`) after a successful search that returns at least one
result, so the initial search box stays uncluttered. Once visible for the current
query, it SHALL stay visible even if a scope change yields zero hits (so the user
can switch back); clearing the query or collapsing search SHALL hide it again.

#### Scenario: Answer-only scope
- GIVEN the search scope is set to `answer` and the query matches both question
  and answer documents
- WHEN `performSearch` runs
- THEN the result list SHALL contain only items with `type` equal to `answer`

#### Scenario: Both scope excludes headings
- GIVEN the search scope is `both` and a heading also matches the query
- WHEN `performSearch` runs
- THEN heading and content items SHALL NOT appear in the results

## Technical Notes

- Server-side: `generators/search_generator.py::SearchIndexGenerator`
- Content extraction: `core/content_processor.py::ContentProcessor.extract_search_content`
- Client-side: `assets/js/modules/01a-search-init.js` … `01e-search-ui.js`
- MiniSearch: local self-host `assets/js/minisearch.min.js` (copied to output by
  `main.py::_generate_static_assets`); CDN fallbacks for runtime injection only:
  `config/settings.py::Constants.MINISEARCH_CDN_PRIMARY` / `MINISEARCH_CDN_BACKUP`
  (mirrored in `01e-search-ui.js::ensureMiniSearchLoaded` — keep in sync)
- Jieba WASM assets: `assets/js/jieba_rs_wasm.js` + `assets/js/jieba_rs_wasm_bg.wasm`
