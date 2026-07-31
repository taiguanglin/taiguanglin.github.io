# Overview Specification

## Purpose

word2ebook is a Python CLI tool that converts a single `.docx` input file into a
collection of HTML pages forming a navigable ebook. The output includes a landing
index page, per-chapter pages, JSON search indexes, and static assets (CSS/JS).
One or more optional `.pdf` sources can be appended as additional month-based
chapters (see `pdf-parsing/spec.md`); `--pdf` may be repeated. An optional `qa/`
folder of AI-transcribed Q&A text files can still be appended as further
month-based chapters with per-segment audio playback and proofreading-status
badges (see `qa-parsing/spec.md`). For 問答錄 2, Nov 2025–Mar 2026 comes from a
second PDF, not from `qa/`.

## Requirements

### Requirement: CLI Entry Point
The system SHALL expose a command-line interface via `main.py` that accepts
`input_file` (positional), `output_folder` (positional), and optional flags
`--skip-index`, `--skip-traditional`, `--skip-simplified`, `--fast`,
`--pdf <path>` (repeatable), `--qa <folder>`, `--only-word`, `--only-pdf`,
`--only-qa`, `--pdf-start-index <int>`, and `--qa-start-index <int>`.

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
   each `--pdf` month-chapter batch in order, then QA month-chapters (if `--qa`
   is supplied)
4. Inject per-segment audio play buttons from `data/audio_map/*.json` into PDF
   chapter HTML when mapping files exist (see `pdf-audio-map/spec.md`)
5. Generate HTML pages for each chapter (simplified and/or traditional)
6. Generate HTML index pages
7. Generate or ensure existence of search index JSON files
8. Write static assets (CSS, JS, and auxiliary JS files)

### Requirement: Fast Mode
When `--fast` is passed, the system SHALL skip both the search index generation
and the traditional Chinese version.

### Requirement: PDF Source Append
When one or more `--pdf <path>` flags are supplied (without a partial mode), the
system SHALL parse each PDF into month-based chapters in flag order and append
them after the Word chapters, with chapter indices continuing from the running
chapter count (each subsequent PDF starts after the previous PDF's months). The
homepage footer `Source:` line SHALL list the Word filename and every PDF
filename, joined by `、`, each as a downloadable link.

#### Scenario: Word plus PDF full build
- GIVEN a valid `.docx` and a valid `.pdf`
- WHEN the user runs `python main.py book.docx out/ --pdf answers.pdf`
- THEN the output SHALL contain the Word chapters followed by the PDF
  month-chapters, a merged index TOC, and search indexes covering all chapters

#### Scenario: Multiple PDFs
- GIVEN a valid `.docx` and two valid `.pdf` files
- WHEN the user runs `python main.py book.docx out/ --pdf a.pdf --pdf b.pdf`
- THEN chapters from `a.pdf` SHALL precede chapters from `b.pdf`, and the
  homepage `Source:` line SHALL list Word, `a.pdf`, and `b.pdf`

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

### Requirement: Site Full-Rebuild Script
The repository SHALL ship `gen_all.py` in the `tool/word2ebook/` directory as a
one-command full rebuild for the 問答錄 2 ebook. The script SHALL resolve all
source and output paths relative to the repository root (not the caller's cwd),
validate that the Word and both PDF sources exist, then invoke the same full
conversion pipeline as `main.py` with Word + Jun–Sep PDF + Nov–Mar PDF
(simplified + traditional + search index, no partial mode, no `qa/`).

#### Scenario: Full rebuild from Word and two PDFs
- GIVEN the default repo layout with `問答錄2/*.docx` and both monthly-Q&A PDFs
- WHEN the user runs `python3 gen_all.py` from `tool/word2ebook/`
- THEN the system SHALL write a complete `wenda2_ebook/` output (chapters 01–21,
  index pages, search indexes, and static assets) without a QA source link

#### Scenario: Missing source in gen_all
- GIVEN one of the hard-coded source paths does not exist
- WHEN the user runs `python3 gen_all.py`
- THEN the system SHALL print an error naming the missing path and exit with a
  non-zero status without starting conversion

### Requirement: Site Full-Rebuild and Push Script
The repository SHALL ship `gen_all_and_push.py` alongside `gen_all.py`. The script
SHALL sync remote changes to the local repository first (`git pull` from the repo
root), then run the full rebuild; on success it SHALL stage all changes
(`git add :/`), commit with a configurable message (default:
`New txt changes to new wenda2ebook`), and push to the remote. If `git pull` or
the rebuild fails, subsequent steps SHALL be skipped. If there are no changes
after staging, the script SHALL skip commit and push and exit successfully.

#### Scenario: Pull, rebuild, commit, and push after QA edits
- GIVEN the user has modified QA transcript files
- WHEN the user runs `python3 gen_all_and_push.py` from `tool/word2ebook/`
- THEN the system SHALL run `git pull`, rebuild `wenda2_ebook/`, commit all repo
  changes, and push to the remote

#### Scenario: Pull fails
- GIVEN `git pull` fails (e.g. merge conflict)
- WHEN the user runs `python3 gen_all_and_push.py`
- THEN the system SHALL abort without running the rebuild, commit, or push

#### Scenario: Rebuild succeeds with no diff
- GIVEN `gen_all.py` completes but produces no file changes
- WHEN the user runs `python3 gen_all_and_push.py`
- THEN the system SHALL report that there is nothing to commit and SHALL NOT run
  `git commit` or `git push`

## Technical Notes

- Entry point: `main.py::main()`
- Site full rebuild: `gen_all.py::main()` (問答錄 2 preset paths)
- Site full rebuild + git push: `gen_all_and_push.py::main()`
- Core converter class: `main.Word2EBookConverter`
- Pipeline orchestration: `Word2EBookConverter.convert()`; source parsing in
  `Word2EBookConverter._parse_chapters()`
- Dependencies: python-docx, PyMuPDF, opencc-python-reimplemented, beautifulsoup4, PyYAML, jieba
