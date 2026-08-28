# HTML Generation Specification

## Purpose

The HTML generation domain converts `Chapter` objects into navigable HTML pages,
producing one simplified and one traditional Chinese variant of each chapter page
and two index pages (`index.html`, `index_trad.html`).

## Requirements

### Requirement: Chapter Page Generation
The system SHALL generate one HTML file per chapter (e.g. `01.html`, `02.html`)
for the simplified Chinese version and one `*_trad.html` file for traditional Chinese.

#### Scenario: Simplified chapter page
- GIVEN a list of `Chapter` objects and `generate_simplified=True`
- WHEN `HTMLGenerator.generate_chapter_pages` is called
- THEN files `01.html`, `02.html`, … SHALL exist in the output folder

#### Scenario: Traditional chapter page
- GIVEN `generate_traditional=True`
- WHEN `HTMLGenerator.generate_chapter_pages` is called
- THEN files `01_trad.html`, `02_trad.html`, … SHALL exist

### Requirement: Navigation Links
Each chapter page SHALL include:
- A link to the previous chapter (or none if it is the first chapter)
- A link to the next chapter (or none if it is the last chapter)
- A link back to the index page
- A language-switch link to the other variant (simplified ↔ traditional)

The page header (`<div class="header-nav">`) SHALL lay the navigation links in a
left-hand `<div class="nav-home">` and keep only the language-switch
(`<div class="lang-switch">`) on the right, on both chapter pages and index pages.
On chapter pages, the nav-home group SHALL contain two links:
- `📖 問答錄2總目錄` → the current ebook's own index (`index.html` /
  `index_trad.html`, same directory), via the `{home_link}` template slot and
  labelled by i18n `navigation.ebook_toc`.
- `<cross>` → the sibling ebook (`../ebook/index.html` /
  `../ebook/index_trad.html`), via `{cross_href}` — labelled `📚 坐禅系列` /
  `📚 坐禪系列`.

Chapter pages SHALL NOT link directly to the site landing page. On index pages,
the nav-home group SHALL instead contain:
- `🏠 網站首頁` → the single site landing page at `../index.html`, for both
  simplified and traditional variants.
- The same language-appropriate sibling-ebook link described above.

The `.index-header` index-page style SHALL keep the same `space-between`
alignment so navigation links sit left and the language switch right.

### Requirement: Index Page Generation
The system SHALL generate `index.html` (simplified) and `index_trad.html` (traditional)
containing the full table of contents with chapter links.

#### Scenario: Index TOC contains all chapters
- GIVEN N chapters
- WHEN `HTMLGenerator.generate_index_pages` is called
- THEN `index.html` SHALL contain links to all N chapter files

### Requirement: Source File Download Links
The homepage footer (`<p class="source-filename">`) SHALL list every source file
(the input Word document plus any `--pdf` extra sources) as a downloadable
hyperlink. Each link SHALL:
- Use an `href` pointing to the source file path **relative to the output folder**
  (computed with `os.path.relpath`, POSIX separators), so the link resolves to the
  original file deployed alongside the ebook.
- Carry a `download` attribute so clicking saves the file instead of navigating.
- Show the original file name as its visible text.

The source-link HTML SHALL NOT be passed through simplified/traditional
conversion, so that real file names and folder paths (e.g. the traditionally named
`問答錄2` folder) are preserved identically on both `index.html` and
`index_trad.html`. Link styling SHALL keep the surrounding text colour (inherit)
and add only an underline.

When a `--qa` source is supplied, the footer SHALL additionally include a third
link to the online proofreading tool at `Constants.QA_INDEX_LINK`
(`../qa/index.html`). Unlike the file links this is a plain link (no `download`
attribute); its visible label comes from i18n key `qa.source_label` and therefore
DOES vary by language variant, while its ASCII `href` stays constant.

#### Scenario: Homepage lists sources as download links
- GIVEN an input `book.docx` and an extra `answers.pdf`, output folder a sibling of the sources
- WHEN `HTMLGenerator.generate_index_pages` is called
- THEN the generated `index.html` SHALL contain `<a … href="../book.docx" download="book.docx">book.docx</a>` and a matching anchor for `answers.pdf`, joined by `、`

#### Scenario: Homepage adds the QA proofreading link
- GIVEN the generator was constructed with `include_qa_source=True`
- WHEN `HTMLGenerator.generate_index_pages` is called
- THEN the footer SHALL include a third `、`-joined link `<a class="source-link"
  href="../qa/index.html">…</a>` with no `download` attribute

### Requirement: QA Chapter Source Banner
For chapters with `is_qa = True`, the chapter page SHALL render a source banner
(`<div class="qa-source-banner">`) immediately below the chapter title, linking to
`Constants.QA_INDEX_LINK` so readers can see the transcript source and proofreading
progress. Non-QA chapters SHALL render no banner (the template `{qa_banner}` slot
defaults to an empty string). The banner HTML SHALL be assembled after body
OpenCC conversion (its text comes pre-localized from i18n key `qa.banner`), so it
is not double-converted.

#### Scenario: Banner only on QA chapters
- GIVEN a Word chapter and a QA chapter
- WHEN chapter pages are generated
- THEN the QA chapter page SHALL contain exactly one `qa-source-banner` and the
  Word chapter page SHALL contain none

### Requirement: QA Proofreading Badge Placeholders
The system SHALL substitute the `{{qa_proofread}}` and `{{qa_unproofread}}`
placeholders embedded by the QA parser with the localized text from i18n keys
`qa.proofread` / `qa.unproofread` **before** the body OpenCC simplified/traditional
conversion, so each badge ends up in the correct script without double-conversion.

#### Scenario: Placeholders replaced per variant
- GIVEN a QA chapter body containing `{{qa_proofread}}` and `{{qa_unproofread}}`
- WHEN the simplified and traditional pages are generated
- THEN no `{{qa_*}}` placeholder SHALL remain, and each badge text SHALL be in the
  page's script (simplified on `index.html` pages, traditional on `_trad` pages)

### Requirement: Asset References
Every generated HTML page SHALL reference:
- `assets/css/style.css` via a `<link>` tag
- `assets/js/script.js` via a `<script>` tag
- `assets/js/i18n-text.js`, `assets/js/search-cache.js` via `<script>` tags
- Favicon via a `<link rel="icon">` tag if a favicon was found

### Requirement: Favicon Handling
The system SHALL search for a favicon file in the same directory as the input
`.docx` file (patterns: `favicon.ico`, `favicon.png`, `favicon.svg`) and copy it
to the output root. If not found the system SHOULD continue without a favicon and
print a warning.

## Technical Notes

- Implementation: `generators/html_generator.py::HTMLGenerator` (orchestrator);
  `include_qa_source` ctor flag toggles the homepage QA link; `_build_qa_banner`
  builds the per-chapter banner; `_process_i18n_placeholders` substitutes the
  `{{qa_*}}` badge placeholders before OpenCC.
- TOC logic: `generators/toc_generator.py::TOCGenerator` (TOC HTML + QA count metadata)
- Templates: `templates/i18n_templates.py::I18nTemplateManager` (sole template
  source; chapter template exposes a `{qa_banner}` slot defaulting to empty;
  chapter nav uses `{home_link}` and `{cross_href}`, while index nav uses
  `{site_home_href}` and `{cross_href}`; variant labels and targets are resolved
  in `_get_chapter_i18n_kwargs`/`_get_index_i18n_kwargs`;
  `html_templates.py` has been deleted)
- Chapter file naming: zero-padded index (`utils/file_utils.py::safe_filename`)
- Traditional conversion: `utils/i18n_utils.py::I18nProcessor.to_traditional`
- Simplified/traditional page pairs are generated by the same parameterised methods (`_generate_chapters`, `_generate_index`) — avoid duplicating logic for the two variants
