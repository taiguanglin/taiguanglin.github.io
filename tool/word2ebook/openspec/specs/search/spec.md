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
The generated HTML pages SHALL load MiniSearch from CDN with a fallback URL.
Chinese text search SHALL use the Jieba WASM segmenter when available; the
system SHALL fall back to substring matching when Jieba is unavailable.

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
- MiniSearch CDN: `config/settings.py::Constants.MINISEARCH_CDN_PRIMARY` / `MINISEARCH_CDN_BACKUP`
- Jieba WASM assets: `assets/js/jieba_rs_wasm.js` + `assets/js/jieba_rs_wasm_bg.wasm`
