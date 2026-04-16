# Overview Specification

## Purpose

word2ebook is a Python CLI tool that converts a single `.docx` input file into a
collection of HTML pages forming a navigable ebook. The output includes a landing
index page, per-chapter pages, JSON search indexes, and static assets (CSS/JS).

## Requirements

### Requirement: CLI Entry Point
The system SHALL expose a command-line interface via `main.py` that accepts
`input_file` (positional), `output_folder` (positional), and optional flags
`--skip-index`, `--skip-traditional`, `--skip-simplified`, and `--fast`.

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
3. Parse the Word document into chapters
4. Generate HTML pages for each chapter (simplified and/or traditional)
5. Generate HTML index pages
6. Generate or ensure existence of search index JSON files
7. Write static assets (CSS, JS, and auxiliary JS files)

### Requirement: Fast Mode
When `--fast` is passed, the system SHALL skip both the search index generation
and the traditional Chinese version.

## Technical Notes

- Entry point: `main.py::main()`
- Core converter class: `main.Word2EBookConverter`
- Pipeline orchestration: `Word2EBookConverter.convert()`
- Dependencies: python-docx, opencc-python-reimplemented, beautifulsoup4, PyYAML, jieba
