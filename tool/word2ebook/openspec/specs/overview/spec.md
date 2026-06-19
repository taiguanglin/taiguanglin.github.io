# Overview Specification

## Purpose

word2ebook is a Python CLI tool that converts a single `.docx` input file into a
collection of HTML pages forming a navigable ebook. The output includes a landing
index page, per-chapter pages, JSON search indexes, and static assets (CSS/JS).
An optional `.pdf` source can be appended as additional month-based chapters
(see `pdf-parsing/spec.md`), and an optional `qa/` folder of AI-transcribed Q&A
text files can be appended as further month-based chapters with per-segment audio
playback and proofreading-status badges (see `qa-parsing/spec.md`).

## Requirements

### Requirement: CLI Entry Point
The system SHALL expose a command-line interface via `main.py` that accepts
`input_file` (positional), `output_folder` (positional), and optional flags
`--skip-index`, `--skip-traditional`, `--skip-simplified`, `--fast`,
`--pdf <path>`, `--qa <folder>`, `--only-word`, `--only-pdf`, `--only-qa`,
`--pdf-start-index <int>`, and `--qa-start-index <int>`.

#### Scenario: Successful conversion
- GIVEN a valid `.docx` file at `input_file`
- WHEN the user runs `python main.py input_file output_folder`
- THEN the output folder SHALL contain `index.html`, `index_trad.html`,
  per-chapter HTML files, `search_index.json`, `search_index_trad.json`,
  and `assets/css/style.css`, `assets/js/script.js`

#### Scenario: Missing input file
- GIVEN `input_file` does not exist on disk
- WHEN the user runs the CLI
- THEN the system SHALL print an error message and return without raising an unhandled exception

#### Scenario: Unsupported file extension
- GIVEN `input_file` has an extension other than `.docx` or `.doc`
- WHEN the user runs the CLI
- THEN the system SHALL print a format-error message and return early

### Requirement: Mutual Exclusion of Skips
The system SHALL reject `--skip-traditional` combined with `--skip-simplified`
because at least one language version MUST be generated.

#### Scenario: Both skips provided
- GIVEN the user passes both `--skip-traditional` and `--skip-simplified`
- WHEN the CLI parses arguments
- THEN the system SHALL call `sys.exit(1)` with a descriptive message

### Requirement: Conversion Pipeline
The system SHALL execute these steps in order:
1. Set up / clean the output directory
2. Copy favicon if present
3. Parse the source(s) into a single `List[Chapter]` — Word chapters first, then
   PDF month-chapters (if `--pdf` is supplied), then QA month-chapters (if `--qa`
   is supplied)
4. Generate HTML pages for each chapter (simplified and/or traditional)
5. Generate HTML index pages
6. Generate or ensure existence of search index JSON files
7. Write static assets (CSS, JS, and auxiliary JS files)

### Requirement: Fast Mode
When `--fast` is passed, the system SHALL skip both the search index generation
and the traditional Chinese version.

### Requirement: PDF Source Append
When `--pdf <path>` is supplied (without a partial mode), the system SHALL parse
the PDF into month-based chapters and append them after the Word chapters, with
chapter indices continuing from the Word chapter count. The homepage footer
`Source:` line SHALL list both the Word filename and the PDF filename, joined by
`、`.

#### Scenario: Word plus PDF full build
- GIVEN a valid `.docx` and a valid `.pdf`
- WHEN the user runs `python main.py book.docx out/ --pdf answers.pdf`
- THEN the output SHALL contain the Word chapters followed by the PDF
  month-chapters, a merged index TOC, and search indexes covering all chapters

#### Scenario: Missing or invalid PDF
- GIVEN `--pdf` points to a non-existent file or a non-`.pdf` extension
- WHEN the user runs the CLI
- THEN the system SHALL print an error message and return early

### Requirement: QA Source Append
When `--qa <folder>` is supplied (without a partial mode), the system SHALL parse
the folder's Q&A text files into month-based chapters and append them after the
Word and PDF chapters, with chapter indices continuing from the running chapter
count. The homepage footer `Source:` line SHALL add a third link pointing directly
to the online proofreading tool at `../qa/index.html` (label from i18n key
`qa.source_label`), joined to the existing links by `、`. This QA link is a plain
link (not a download).

#### Scenario: Word plus PDF plus QA full build
- GIVEN a valid `.docx`, a valid `.pdf`, and a `qa/` folder
- WHEN the user runs `python main.py book.docx out/ --pdf answers.pdf --qa qa/`
- THEN the output SHALL contain Word chapters, then PDF month-chapters, then QA
  month-chapters, a merged index TOC, search indexes covering all chapters, and a
  homepage `Source:` line with three links (Word file, PDF file, `../qa/index.html`)

#### Scenario: Missing or non-directory QA path
- GIVEN `--qa` points to a non-existent path or a non-directory
- WHEN the user runs the CLI
- THEN the system SHALL print an error message and return early

### Requirement: Partial Dev Modes
The system SHALL support mutually-exclusive `--only-word`, `--only-pdf`, and
`--only-qa` flags for fast iteration. In a partial mode the system SHALL
regenerate only that source's chapter pages, preserve all other output files, and
skip both the index page regeneration and the search index rebuild. `--only-pdf`
requires `--pdf` and numbers its chapters starting from `--pdf-start-index`
(default 12 → first PDF chapter is `13.html`). `--only-qa` requires `--qa` and
numbers its chapters starting from `--qa-start-index` (default 16 → first QA
chapter is `17.html`); it does not require a valid `.docx` (the docx existence and
extension checks SHALL be relaxed), so QA layout can be previewed without paying
the Word/PDF parse cost.

#### Scenario: Only-PDF preview
- GIVEN a previously built output folder
- WHEN the user runs `python main.py book.docx out/ --pdf answers.pdf --only-pdf`
- THEN only the PDF chapter pages SHALL be (re)written, and the existing index
  and search indexes SHALL be left untouched

#### Scenario: Only-PDF without --pdf
- GIVEN `--only-pdf` is passed without `--pdf`
- WHEN the CLI parses arguments
- THEN the system SHALL call `sys.exit(1)` with a descriptive message

#### Scenario: Only-QA preview without a docx
- GIVEN a previously built output folder and a `qa/` folder
- WHEN the user runs `python main.py - out/ --qa qa/ --only-qa`
- THEN only the QA chapter pages SHALL be (re)written (no docx is required), and
  the existing index and search indexes SHALL be left untouched

#### Scenario: Only-QA without --qa
- GIVEN `--only-qa` is passed without `--qa`
- WHEN the CLI parses arguments
- THEN the system SHALL call `sys.exit(1)` with a descriptive message

## Technical Notes

- Entry point: `main.py::main()`
- Core converter class: `main.Word2EBookConverter`
- Pipeline orchestration: `Word2EBookConverter.convert()`; source parsing in
  `Word2EBookConverter._parse_chapters()`
- Dependencies: python-docx, PyMuPDF, opencc-python-reimplemented, beautifulsoup4, PyYAML, jieba
