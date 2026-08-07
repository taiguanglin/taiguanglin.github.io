# PDF Audio Map Specification

## Purpose

Attach per-question (and opening) audio playback to PDF-sourced ebook chapters
for 2025-06…09 and 2025-11…2026-03 without replacing PDF prose with `qa/`
transcripts. A JSON mapping under `data/audio_map/` stores time ranges; the
build injects `.qa-play` buttons; a browser tool at `/audio_map/` allows manual
refinement.

## Requirements

### Requirement: Independent Mapping Store
The system SHALL store month-level JSON files at
`tool/word2ebook/data/audio_map/YYYY-MM.json`. Mapping SHALL NOT write back to
`qa/*.txt`. Re-alignment SHALL preserve entries with `locked: true` or
`status: "manual"`.

#### Scenario: Manual times survive re-align
- GIVEN a segment with `status: "manual"` and `locked: true`
- WHEN `align.py --apply` runs for that month
- THEN that segment's `start`/`end` SHALL remain unchanged

### Requirement: One Range Per Question Plus Opening
Each PDF question SHALL map to at most one `[start, end]` range on a single
`.opus` file. When an opening paragraph exists, it SHALL also have a range.
After a complete align (`--require-complete` / `fill_misses.py`), **no** segment
or opening SHALL remain `status: "missing"`. Gaps with no direct SRT hit SHALL
be filled by monotonic interpolation (`notes` containing `interpolated`).

#### Scenario: Unmatched gap is interpolated
- GIVEN a PDF question with no direct SRT hit but neighbors matched
- WHEN alignment finishes
- THEN the segment SHALL have non-null `start`/`end` and a note indicating
  interpolation

### Requirement: Official-Site Media Fallback
When resolving media for PDF source `官网`/`官網`, if that day's 官网 mp3/srt/opus
are absent, the system SHALL fall back to the same day's `贴吧`/`貼吧` files and
record `media_fallback` / `resolved_source` on the session. The emitted
`audio_file` SHALL be the resolved opus stem so playback works.

#### Scenario: Aug 2025 官网 uses 贴吧 audio
- GIVEN `2025-08-08` PDF section `官网` with no 官网 media
- WHEN `resolve_media` runs
- THEN `audio_file` SHALL be `2025年8月8日Tai師父貼吧答疑.opus`

### Requirement: Build-Time Injection
After Word/PDF/QA parsing, the converter SHALL call `inject_chapters` before
HTML generation. Injection SHALL insert
`<div class="qa-meta-bar">…<button class="qa-play" …>` before each matched
`.question` **that has been listened to** in `/audio_map/`
(`meta.lastPlayed` present) and has a valid time range, and an opening meta bar
after the section `<h2>` when the opening has a range **and** the first Q&A
segment of that session has been listened to. Unmatched questions, missing
ranges, and unlistened segments SHALL receive **no** play control (not a
disabled button). Injection SHALL be idempotent (strips prior meta bars first).

#### Scenario: Matched listened question gets play data
- GIVEN a mapping segment with start=10.5 end=20.0, audio `X.opus`, and
  `meta.lastPlayed` set
- WHEN the chapter HTML is injected
- THEN a `.qa-play` button SHALL appear before that question with
  `data-start="10.500"`, `data-end="20.000"`, and percent-encoded `data-audio`

#### Scenario: Missing segment omitted
- GIVEN a mapping segment with `status: "missing"`
- WHEN injected
- THEN no `.qa-play` and no `.qa-meta-bar` SHALL be inserted for that question

#### Scenario: Unlistened segment omitted even with a range
- GIVEN a mapping segment with valid `start`/`end` but no `meta.lastPlayed`
- WHEN injected
- THEN no `.qa-play` and no `.qa-meta-bar` SHALL be inserted for that question

#### Scenario: Opening follows first segment listen state
- GIVEN an opening with a valid range and a first Q&A segment without
  `meta.lastPlayed`
- WHEN injected
- THEN no opening `.qa-meta-bar` SHALL be inserted
- GIVEN the same opening and a first Q&A segment with `meta.lastPlayed`
- WHEN injected
- THEN an opening `.qa-meta-bar` with `.qa-play` SHALL be inserted after `<h2>`

### Requirement: Shared Play Markup
Play-button HTML SHALL be produced by `core/qa_play_markup.py` so QA chapters
and PDF audio-map injection share the same `data-*` contract consumed by
`08-qa-audio.js`. Visible labels SHALL use `HH:MM:SS` (no milliseconds); the
editorial `/audio_map/` UI keeps millisecond precision. Each `.qa-play` button
SHALL include a speaker SVG icon (`.qa-play-speaker`).

### Requirement: Alignment Sources
For months 2025-11 through 2026-03, alignment SHALL prefer times from
`qa/*.txt` when a QA title covers a PDF question, and SHALL fall back to SRT
matching for remaining questions. For 2025-06 through 2025-09, alignment SHALL
use SRT matching against PDF question text. Audio filenames SHALL use
traditional source stems (`官網` / `微信公眾號` / `貼吧`).

## Related Modules

- CLI: `tool/pdf_audio_map/align.py`, `extract_sessions.py`
- Injector: `core/audio_map_injector.py`
- Markup: `core/qa_play_markup.py`
- Editor: `/audio_map/`
- Frontend player: `assets/js/modules/08-qa-audio.js`
