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

## Technical Notes

- Server-side: `generators/search_generator.py::SearchIndexGenerator`
- Content extraction: `core/content_processor.py::ContentProcessor.extract_search_content`
- Client-side: `assets/js/modules/01-search.js`
- MiniSearch CDN: `config/settings.py::Constants.MINISEARCH_CDN_PRIMARY` / `MINISEARCH_CDN_BACKUP`
- Jieba WASM assets: `assets/js/jieba_rs_wasm.js` + `assets/js/jieba_rs_wasm_bg.wasm`
