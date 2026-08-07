# QA Parsing Specification

## Purpose

The QA parser (`core/qa_parser.py`, class `QAParser`) converts the AI-transcribed
Q&A text files in the repository's `qa/` folder into month-based `Chapter`
objects that plug into the same pipeline as Word and PDF chapters. It shares
`core/chapter_finalizer.py` with the Word/PDF paths so layout, markup, TOC,
per-section Q&A counts, and search behaviour stay consistent.

The `qa/` transcripts run chronologically from 2025-11 to 2026-03. Each file is a
single day's session for one source (`官網` official site, or `微信公眾號` WeChat
official account). Some files have been manually proofread; others are still raw
AI transcripts.

Unlike Word/PDF chapters, QA chapters add two source-specific features:
per-segment **audio playback** (a `.opus` clip cued to the segment's time range)
and a **proofreading-status badge** per segment.

## Requirements

### Requirement: Month-Based Chapters Across Years
The parser SHALL group day sessions by `(year, month)` and emit one `Chapter`
per month, ordered chronologically ascending across year boundaries. Chapter
indices SHALL start at `start_index + 1`; the chapter title SHALL be
`{NN}{year-in-circle-zero-numerals}年{month-in-Chinese}` (e.g. `17二〇二五年十一月`).
Every emitted chapter SHALL have `is_qa = True`.

#### Scenario: Five month chapters from Nov to Mar
- GIVEN a `qa/` folder with files dated 2025-11 through 2026-03
- WHEN `QAParser.parse_folder(folder, start_index=16)` runs
- THEN it SHALL return chapters `17.html`..`21.html` titled `17二〇二五年十一月`,
  `18二〇二五年十二月`, `19二〇二六年一月`, `20二〇二六年二月`, `21二〇二六年三月`

### Requirement: Filename → Date + Source
The parser SHALL derive `(year, month, day, source)` from each filename of the
form `YYYY年M月D日Tai師父<source>答疑.txt`, where `<source>` is `官網` or
`微信公眾號`. Files not matching this pattern (e.g. `README.md`) and files whose
name begins with `_` SHALL be skipped.

#### Scenario: Official-site and WeChat files
- GIVEN `2025年11月10日Tai師父官網答疑.txt` and `2025年11月10日Tai師父微信公眾號答疑.txt`
- WHEN parsed
- THEN both SHALL be recognized with sources `官網` and `微信公眾號` respectively

### Requirement: Date + Source Sub-Headings
Within a month chapter, each file SHALL produce one level-2 heading (`<h2>`) with
text `YYYY年M月D日 <source>` and a stable, unique slug `id`. Sections SHALL be
ordered by day ascending, with `官網` before `微信公眾號` on the same day.

#### Scenario: TOC sub-entries ordering
- GIVEN a day with both official-site and WeChat files
- WHEN the month chapter is built
- THEN its `toc_items` SHALL list `YYYY年M月D日 官網` before `YYYY年M月D日 微信公眾號`

### Requirement: Opening Remarks
The header before the first `### N.` segment SHALL be parsed into an opening
block: the first line (the title) and any editorial note line (wrapped in
full-width parentheses) SHALL be dropped; the `開場時間：` range SHALL drive an
opening play button; the remaining prose SHALL be emitted as `<p class="qa-opening">`
paragraphs. The opening block SHALL NOT carry a proofreading badge.

### Requirement: Segment Parsing
Each `### N. <question>` SHALL produce one `<div class="question">` card (the
question text from the heading) and, when present, one `<div class="answer">`
card (paragraphs after `Taiguanglin：`, split on blank lines), using answerer raw
name `Taiguanglin` and matching the Word/PDF markup. The `時間：` line SHALL set
the segment's audio range. `最後播放：` lines SHALL be ignored and SHALL NOT leak
into the answer text.

#### Scenario: Answer paragraphs split on blank lines
- GIVEN an answer with two paragraphs separated by a blank line
- WHEN parsed
- THEN the answer card SHALL contain two `answer-text` paragraphs

### Requirement: Per-Segment Q&A Meta Bar
Each segment SHALL be preceded by a `<div class="qa-meta-bar">` containing the
segment number, a play control, and a status badge. The meta bar SHALL NOT be a
`<p>`, `.question`, or `.answer` element, so the search content extractor never
indexes the play-button label, timecodes, or badge text.

#### Scenario: Meta bar excluded from search
- GIVEN a built QA chapter
- WHEN the search index is generated
- THEN it SHALL contain the question/answer prose but SHALL NOT contain the
  badge text, the play icon, or the `HH:MM:SS` timecodes

### Requirement: Audio Playback Data
Each play control SHALL be a `<button class="qa-play">` carrying `data-audio`
(the segment's audio URL), `data-start`/`data-end` (segment bounds in seconds),
and `data-label` (the human-readable `HH:MM:SS - HH:MM:SS` range; milliseconds
are truncated for ebook display). Precise bounds remain in `data-start` /
`data-end`. The audio URL SHALL be `{QA_AUDIO_BASE}{percent-encoded(<txt-stem>.opus)}` where
`QA_AUDIO_BASE` defaults to `../audio/`. Percent-encoding keeps the URL ASCII so
OpenCC simplified/traditional conversion cannot corrupt the CJK filename. A
segment with no parseable time range SHALL render a disabled, non-button control.
Each play button SHALL include a speaker icon (`.qa-play-speaker`) so the control
is visually distinct from surrounding text.

#### Scenario: Audio filename derived from txt stem
- GIVEN `2025年11月10日Tai師父官網答疑.txt`
- WHEN parsed
- THEN the segment play buttons SHALL reference
  `../audio/<percent-encoded>2025年11月10日Tai師父官網答疑.opus`

#### Scenario: Encoded audio path survives i18n conversion
- GIVEN a `data-audio` value with percent-encoded CJK
- WHEN OpenCC simplified or traditional conversion runs over the chapter body
- THEN the `data-audio` value SHALL be byte-for-byte unchanged

### Requirement: Proofreading Status Badge
A segment that contains a `最後編輯：<timestamp>` line SHALL be marked manually
proofread and SHALL render a `qa-status--proofread` badge using the
`{{qa_proofread}}` i18n placeholder followed by the timestamp. A segment without
`最後編輯` SHALL render a `qa-status--ai` badge using the `{{qa_unproofread}}`
placeholder. Both placeholders SHALL be substituted by the HTML generator before
OpenCC conversion (see `html-generation/spec.md`).

#### Scenario: Proofread vs AI-only segments
- GIVEN one segment with `最後編輯：2026-06-16 15:16` and one without
- WHEN parsed
- THEN the first SHALL carry `{{qa_proofread}} 2026-06-16 15:16` and the second
  SHALL carry `{{qa_unproofread}}`

### Requirement: Shared Finalizer
The parser SHALL build each chapter via `core.chapter_finalizer.finalize_chapter`,
the same function used by `DocumentParser` and `PDFParser`, so back-to-top
insertion, Q&A count metadata, and the collapsible chapter TOC are produced
identically. The `qa-meta-bar` and `qa-opening` blocks SHALL pass through the
finalizer's Q&A merge step untouched (one `question` div per segment keeps
per-section counts accurate).

## Technical Notes

- Public API: `QAParser.parse_folder(folder, start_index=16)`; the pure, testable
  core methods are `parse_text(text)`, `build_section(...)`, and
  `_sections_to_chapters(sections, start_index)`.
- Helpers: `_timecode_to_seconds` (`HH:MM:SS.mmm` → float), `_year_to_cn`
  (Arabic year → circle-zero Chinese numerals).
- Constants: `QA_AUDIO_BASE` and `QA_INDEX_LINK` live in `config/settings.py`
  (`Constants`).
- Source labels `官網` / `微信公眾號` are already traditional in the filenames;
  the simplified build converts them via OpenCC like all other body text.
