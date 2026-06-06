# PDF Parsing Specification

## Purpose

The PDF parser (`core/pdf_parser.py`, class `PDFParser`) converts a combined
"monthly Q&A" PDF (e.g. June–September 2025) into month-based `Chapter` objects
that plug into the same pipeline as Word chapters. It shares
`core/chapter_finalizer.py` with the Word path so the resulting layout, markup,
TOC, per-section Q&A counts, and search behaviour are identical.

The PDF used during development is `Tai 师父` daily 答疑 sessions. Each daily
session begins with a day header, answers 贴吧 (Tieba) questions first, then
微信公众号 (WeChat official-account) questions.

## Requirements

### Requirement: Month-Based Chapters
The parser SHALL group daily sessions by the **month of the day-header date**
(not by PDF page order) and emit one `Chapter` per month, ordered ascending.
Chapter indices SHALL start at `start_index + 1`; the chapter title SHALL be
`{NN}{年-in-circle-zero-numerals}年{month-in-Chinese}` (e.g. `13二〇二五年六月`).

#### Scenario: Four month chapters
- GIVEN a PDF containing June–September day sessions
- WHEN `PDFParser.parse(pdf, start_index=12)` runs
- THEN it SHALL return chapters `13.html`..`16.html` titled
  `13二〇二五年六月`, `14二〇二五年七月`, `15二〇二五年八月`, `16二〇二五年九月`

#### Scenario: Out-of-order day grouped by date
- GIVEN a `7月12日` session physically located within the PDF's August page range
- WHEN the PDF is parsed
- THEN the `7月12日` session SHALL appear in the July chapter, not August

### Requirement: Date + Source Sub-Headings
Within a month chapter, each `(date, source)` pair SHALL produce one level-2
heading (`<h2>`) with text `YYYY年M月D日 <source>` (Arabic date), where source is
`贴吧` or `微信公众号`. Sections SHALL be ordered by date ascending, with `贴吧`
before `微信公众号` on the same day. Each `<h2>` SHALL receive a stable, unique
slug `id` so search results and the TOC link to the correct anchor.

#### Scenario: TOC sub-entries
- GIVEN a day with both Tieba and WeChat answers
- WHEN the month chapter is built
- THEN its `toc_items` SHALL include `YYYY年M月D日 贴吧` then `YYYY年M月D日 微信公众号`,
  each with a slug anchor present as an `id` in the chapter content

### Requirement: Artifact Stripping
The parser SHALL remove page-number lines (`N / M`), the repeated audio footer
(`完整音频请关注微信公众号：…`), and blank lines before reflow, so they never
appear in the output.

### Requirement: Paragraph Reflow via Indentation
The parser SHALL use the line's left x-coordinate to reconstruct paragraphs:
an indented first line (x0 above the indent threshold) starts a new paragraph,
while a left-margin continuation line is concatenated onto the current paragraph
without inserting a space. Spaces adjacent to CJK characters SHALL be removed.

#### Scenario: Wrapped lines joined
- GIVEN a question whose text wraps across several continuation lines
- WHEN parsed
- THEN the lines SHALL be joined into a single `question-text` paragraph

### Requirement: Question / Answer Detection
The parser SHALL emit `<div class="question">` cards (with `questioner` and
optional `question-time` meta) and `<div class="answer">` cards (answerer raw
name `Taiguanglin`), matching the Word output markup. A questioner line is
`名字：YYYY-MM-DD HH:MM`. An answer marker is `Taiguanglin：`. Numbered
sub-questions (`N、`, `问题N、`, …) SHALL each become their own question card and
reuse the questioner's name/time; an intro/greeting before the first number stays
with the first question card.

#### Scenario: Multiple numbered questions
- GIVEN one questioner who asks `1、`, `2、`, `3、`
- WHEN parsed
- THEN three separate question cards SHALL be produced, each carrying the same
  questioner name and time

### Requirement: Wrapped-Separator Questioner
The parser SHALL handle a questioner whose name is glued to a leading separator
line (`———…———名字：`) followed by a bare time line, splitting the separator off
and merging the name with the time into a single questioner.

### Requirement: Source Switching
A new day SHALL reset the current source to `贴吧`. A `师父说` line mentioning
`公众号` or `微信` SHALL switch the current source to `微信公众号`. Closing lines
(`…回答到这里`) SHALL NOT change the source.

### Requirement: Shared Finalizer
The parser SHALL build each chapter via `core.chapter_finalizer.finalize_chapter`,
the same function used by `DocumentParser`, so back-to-top insertion, Q&A count
metadata, and the collapsible chapter TOC are produced identically.

## Technical Notes

- Public API: `PDFParser.parse(pdf_path, start_index=12)` and the pure,
  testable core `PDFParser.parse_lines(lines, start_index=12)` where `lines`
  is a list of `(x0, text)` tuples.
- PyMuPDF (`fitz`) is imported lazily inside `_extract_lines`, so unit tests can
  exercise `parse_lines` without PyMuPDF installed.
- Source labels `贴吧` / `微信公众号` are simplified; the traditional build
  converts them to `貼吧` / `微信公眾號` via OpenCC, matching the `qa/` folder
  naming used for future content.
- Helpers: `_year_to_cn` (Arabic year → circle-zero Chinese numerals),
  `_normalize_spaces` (strip CJK-adjacent spaces).
