# word2ebook — Agent / LLM Maintenance Guide

> Read this file first before editing anything in this project.  
> It is the single authoritative map of the codebase.

---

## What this project does

Converts a `.docx` file (and, optionally, a monthly-Q&A `.pdf` and/or a `qa/`
folder of AI-transcribed Q&A text files) into a static HTML ebook with:
- Bilingual output (Simplified + Traditional Chinese)
- Full-text search via [MiniSearch](https://lucaong.github.io/minisearch/) + jieba WASM
- Collapsible TOC, bookmarks, reading settings, floating controls
- All output files are plain HTML/CSS/JS — no runtime server needed

Entry point: `python main.py <input.docx> <output_dir> [--pdf <answers.pdf>] [--qa <qa_folder>]`

A `--pdf` source is parsed into month-based chapters (date + source sub-headings)
and appended after the Word chapters. A `--qa` folder is likewise parsed into
month-based chapters appended after the PDF chapters, but with two extra,
QA-only features: a per-segment audio player (cued `.opus` clip) and a
proofreading-status badge. Dev-only `--only-word` / `--only-pdf` / `--only-qa`
modes regenerate just one source's chapter pages (skipping index + search
rebuild); `--only-qa` does not need a `.docx` (relaxed validation) so QA layout
can be previewed without the Word/PDF parse cost.

---

## Pipeline (execution order)

```
main.py
  Word2EBookConverter.convert()
    1. _setup_output_directory()          → FileManager cleans/creates output dir
    2. copy_favicon_after_setup()         → FaviconManager copies favicon
    3. _parse_chapters()                  → DocumentParser (.docx) + PDFParser (.pdf) + QAParser (qa/) → List[Chapter]
    4. HTMLGenerator.generate_chapter_pages()   → writes chapter .html files
    5. HTMLGenerator.generate_index_pages()     → writes index.html / index_trad.html  (skipped in partial mode)
    6. SearchIndexGenerator.generate_search_indexes()  → writes search_index*.json     (skipped in partial mode)
    7. _generate_static_assets()          → copies CSS/JS bundle to output/assets/
```

`DocumentParser`, `PDFParser`, and `QAParser` all build their chapters through the
shared `core/chapter_finalizer.py` (`finalize_chapter`), so Word, PDF, and QA
chapters have identical markup, TOC, Q&A counts, and search behaviour. QA chapters
additionally set `Chapter.is_qa = True`, which triggers the per-chapter source
banner and (for the per-segment audio/badge UI) the `qa-meta-bar` markup.

---

## Python file map

| File | Responsibility | Lines |
|------|---------------|-------|
| `main.py` | CLI entry, `Word2EBookConverter` orchestrator; `_parse_chapters` concatenates Word + PDF + QA; `--pdf`/`--qa`/`--only-word`/`--only-pdf`/`--only-qa` flags | ~340 |
| `models/document_models.py` | Dataclasses: `Chapter` (incl. `is_qa`), `TOCItem`, `QAPair`, `SearchItem`, `QACountMetadata`, `ConversionConfig` (incl. `pdf_file`, `qa_folder`, `only_word`, `only_pdf`, `only_qa`, `pdf_start_index`, `qa_start_index`) | ~200 |
| `config/settings.py` | `Settings` dataclass, `Constants` (CDN URLs, filenames, search weights, answerer names, heading ranges, `QA_AUDIO_BASE`, `QA_INDEX_LINK`) | ~135 |
| `core/document_parser.py` | Parses `.docx` → `List[Chapter]`; builds HTML content; delegates chapter finalize to `chapter_finalizer` | ~300 |
| `core/pdf_parser.py` | Parses monthly-Q&A `.pdf` → month-based `List[Chapter]` (date+source `<h2>` sections); x0-indent paragraph reflow; detects timestamped **and** no-time questioners (separator- or 师父说-introduced); shares `chapter_finalizer` | ~415 |
| `core/qa_parser.py` | Parses `qa/*.txt` (AI transcripts) → month-based `List[Chapter]` across years; filename→date/source; per-segment `qa-meta-bar` (play button with percent-encoded `data-audio` + `{{qa_proofread}}`/`{{qa_unproofread}}` badge); shares `chapter_finalizer` | ~415 |
| `core/chapter_finalizer.py` | Shared block→`Chapter` finalize (QA merge, back-to-top, QA counts, chapter TOC) used by the Word, PDF, and QA parsers | ~190 |
| `core/content_processor.py` | Extracts search items from HTML; assigns element IDs | 216 |
| `generators/html_generator.py` | `HTMLGenerator` — renders chapter/index pages via `I18nTemplateManager`; simplified/traditional variants unified via `_generate_chapters`/`_generate_index`; QA banner + `{{qa_*}}` placeholder substitution + homepage QA source link | ~250 |
| `generators/toc_generator.py` | `TOCGenerator` — builds TOC HTML; public `generate_qa_count_metadata()` API | ~260 |
| `generators/search_generator.py` | `SearchIndexGenerator` — reads HTML, calls `ContentProcessor`, writes `search_index*.json` | 176 |
| `templates/i18n_templates.py` | `I18nTemplateManager` — sole template source; renders chapter + index pages for both languages | 306 |
| `templates/static_assets.py` | `StaticAssetsManager` — concatenates CSS/JS module files for output | 162 |
| `utils/config_utils.py` | Reads `config.yaml` (book title, i18n strings, favicon) | 144 |
| `utils/favicon_utils.py` | `FaviconManager` — finds and copies favicon | 127 |
| `utils/file_utils.py` | `FileManager` — wraps all disk I/O | 112 |
| `utils/i18n_utils.py` | `I18nProcessor` — Simplified↔Traditional conversion, filename transforms | 107 |
| `utils/text_segmentation.py` | Jieba-based Chinese text segmentation | 125 |
| `utils/text_utils.py` | `TextProcessor` (formats paragraphs to HTML), `IDGenerator` (stable element IDs) | 177 |

---

## JavaScript file map

All JS modules live in `assets/js/modules/` and are concatenated (in numeric order) by `StaticAssetsManager` into `assets/js/script.js` in the output. There are no imports/exports — all modules share one `DOMContentLoaded` scope via a wrapper.

| File | Responsibility |
|------|---------------|
| `00-base.js` | `W2E` global namespace, dark mode init, shared helpers: `isIndexPage`, `isTraditionalChinesePage`, `getText` |
| `01a-search-init.js` | Search state variables, `activateSearch`, loading/error UI, `loadSearchIndexWithProgress`, Jieba WASM init, `segmentWithJieba` |
| `01b-search-index.js` | `createSearchConfig`, `buildSearchIndexInBatches`, `buildSearchIndexInBatchesWithCache` |
| `01c-search-highlight.js` | `escapeHtml`, `getBestContextForHighlight`, `highlightSearchTerm` |
| `01d-search-perform.js` | `performSearch`, `displayPagedResults`, `loadMoreResults` |
| `01e-search-ui.js` | `getSearchElements`, `initSearch`, search event bindings (input, clear, collapse, load-more) |
| `02-reader-ux.js` | Reading toolbar, floating TOC creation, DOM setup, action buttons, Q&A action overlays |
| `03a-bookmark-data.js` | Bookmark CRUD, localStorage persistence, chapter detection, visual indicators, `toggleBookmark` |
| `03b-bookmark-render.js` | `showBookmarkAddedFeedback`, `initializeHomepageTOC`, `renderBookmarkChaptersBatch`, toast messages |
| `03c-bookmark-ui.js` | Bookmark panel UI helpers: `renderIndexTOC`, `showBookmarkLoadingIndicator`, `renderBookmarks`, `updateBookmarkCount` |
| `03d-reading-settings.js` | Font/line-height/width/theme persistence via localStorage; `updateReadingProgress`, `showToast`, `copyText` |
| `04-events.js` | Global event listeners that wire all modules together |
| `05-search-btn-visibility.js` | Shows/hides the bottom search button based on scroll |
| `06-toc-collapse.js` | TOC expand/collapse and level filtering |
| `07-floating-controls.js` | Floating action button menu, floating level controls |
| `08-qa-audio.js` | QA per-segment audio: wires `.qa-play` buttons, bottom floating mini-player, seek-to-start + auto-stop-at-end (isolated IIFE) |

**Standalone JS files** (copied directly to output, not concatenated into `script.js`):

| File | Responsibility |
|------|---------------|
| `assets/js/i18n-text.js` | `window.I18N_TEXT` dictionary |
| `assets/js/search-cache.js` | `SearchCacheManager` class (IndexedDB cache for search index) |
| `assets/js/jieba_rs_wasm.js` | Auto-generated jieba WASM JS glue |
| `assets/js/jieba_rs_wasm_bg.wasm` | jieba WASM binary (~6.5 MB) — do not edit |

---

## CSS file map

All CSS modules live in `assets/css/modules/` and are concatenated (in numeric order) by `StaticAssetsManager` into `assets/css/style.css` in the output.

| File | Responsibility |
|------|---------------|
| `00-base.css` | CSS reset, `:root` design tokens (colors, radii, shadows), typography, `.question`/`.answer`, dark-mode base |
| `01a-layout.css` | Reading toolbar, progress bar, action buttons, Q&A overlays, toast notifications |
| `01b-floating-toc.css` | Floating TOC panel, header, content area, items, tabs |
| `01c-bookmarks.css` | Bookmark list items, homepage groups, visual indicators, current-chapter bar |
| `02-search-btn.css` | Search activation button styles |
| `03-search.css` | Search panel, results, highlight styles, dark-mode search overrides |
| `04a-toc-levels.css` | TOC level-display buttons, floating level panel, expand/collapse icons, level-specific link colours, collapse animations |
| `04b-toc-dark.css` | Dark-mode overrides for TOC controls, floating TOC, bookmark items inside the TOC panel |
| `04c-qa-audio.css` | QA source banner, `qa-meta-bar` (number + `.qa-play` + status badge), `qa-opening`, bottom floating `qa-player`; dark-mode variants. Loads before `05` so its responsive overrides win |
| `05-responsive.css` | **All** `@media` breakpoints: height-based toolbar, ≤768px tablet, ≥800px wide, ≤600px mobile (incl. QA player full-width), ≤400px small-phone |

**Design-token rule:** always use `var(--color-primary)`, `var(--radius-sm)`, etc. (defined in `00-base.css`) — never hardcode raw hex or pixel values in new CSS.

---

## OpenSpec docs

Behavioral specs live in `openspec/specs/<domain>/spec.md`. They define **what the code SHALL do** in GIVEN/WHEN/THEN format — keep them in sync after every code change.

| Spec | Covers |
|------|--------|
| `overview/spec.md` | CLI args, pipeline order, fast/skip modes, PDF + QA append, partial dev modes |
| `document-parsing/spec.md` | `.docx` parsing rules, QA merging |
| `pdf-parsing/spec.md` | `.pdf` → month chapters, date+source headings, reflow, source switching |
| `qa-parsing/spec.md` | `qa/*.txt` → month chapters, audio playback data, proofreading badges, encoded audio paths |
| `html-generation/spec.md` | Chapter/index HTML structure, QA banner + badge placeholders + QA source link |
| `search/spec.md` | Search index generation, content extraction |
| `frontend-js/spec.md` | JS module responsibilities |
| `frontend-css/spec.md` | CSS module responsibilities |
| `static-assets/spec.md` | CSS/JS concatenation pipeline |
| `i18n/spec.md` | Simplified/Traditional conversion rules |

---

## Key data-flow contracts

### Python: Chapter object

`DocumentParser` returns `List[Chapter]`. Every downstream consumer (HTML generator, search generator) operates on this list. The shape is:

```
Chapter
  .title          str         chapter heading (may contain HTML)
  .filename       str         e.g. "chapter_01.html"
  .content        str         full HTML body (all paragraphs, QA pairs, etc.)
  .chapter_toc    str         pre-rendered inner TOC HTML
  .toc_items      List[TOCItem]
  .qa_count_metadata  QACountMetadata | None
  .is_qa          bool        True for chapters from the qa/ folder (adds source banner + per-segment audio/badge UI)
```

### JS: module communication

Modules communicate through **shared lexical scope** (concatenated into one IIFE) and:
- `W2E` namespace (`window.W2E`) — defined in `00-base.js`; register exported functions here
- `window.I18N_TEXT` — i18n dictionary (from `i18n-text.js`)
- `window.searchCacheManager` — IndexedDB cache (from `search-cache.js`)
- Legacy bare globals (`searchIndex`, `miniSearch`, `currentSearchResults`, `displayedResultsCount`) — declared in `01a-search-init.js`, consumed in `01b-e` modules

Module **load order** matters — it is determined by filename numeric sort.

---

## Editing rules

1. **Never recreate** the monolithic `script.js` or `style.css` — edit the module files; `StaticAssetsManager` concatenates them.
2. **After any Python change** — run `python3 -m pytest tests/` from `tool/word2ebook/`.
3. **After any behavioral change** — update the matching `openspec/specs/<domain>/spec.md`.
4. **`I18nTemplateManager` is the sole template path** — `html_templates.py` has been deleted.
5. **`Constants` in `config/settings.py`** is the single source of truth for CDN URLs, index filenames, search weights, answerer names, and heading level ranges. Do not hardcode these elsewhere.
6. **Adding a new JS/CSS module**: create the file with the correct numeric prefix; `StaticAssetsManager` picks it up automatically; update `static-assets/spec.md`.
7. **i18n strings** shown in the UI should come from `config.yaml` (via `get_i18n_text`), not hardcoded in Python or JS.
8. **Simplified/Traditional generation**: use the parameterised `is_traditional` pattern — never duplicate logic for two language variants.
9. **CSS @media rules**: place all breakpoints in `05-responsive.css`; do not scatter `@media` blocks in component files.
10. **CSS design tokens**: use `var(--color-primary)` etc.; do not repeat raw hex/pixel values.
