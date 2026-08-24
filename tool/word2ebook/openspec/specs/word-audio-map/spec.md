# Word Audio Map Specification

## Purpose

Attach per-question audio playback to Word-sourced ebook chapters
(`wenda2_ebook/01.html`–`12.html`, the categorised Word document) without
changing their prose. A JSON mapping under `data/audio_map_word/` stores time
ranges keyed by stable question id; the build injects `.qa-play` buttons.
Alignment is produced by `tool/word_audio_map/` (see its README for the
pinyin-stream matching model).

## Requirements

### Requirement: Independent Mapping Store
The system SHALL store chapter-level JSON files at
`tool/word2ebook/data/audio_map_word/word-NN.json` (one per Word chapter).
Each segment SHALL carry `question_id`, `stable_key`
(`"<chapter>#q<number>"`), timing fields (`start`, `end`, `start_label`,
`end_label`), `confidence`, `status`, `locked`, `notes`, and the resolved
`audio_file` (an opus stem). Re-alignment (`word_align.py --apply`) SHALL
preserve segments with `locked: true` or `status: "manual"`.

#### Scenario: Manual times survive re-align
- GIVEN a segment with `locked: true`
- WHEN `word_align.py --apply` runs again
- THEN that segment's `start`/`end` and `audio_file` SHALL remain unchanged

### Requirement: Question-ID Keyed Injection
The build (`main.py`) SHALL call `inject_word_chapters()` after the PDF
`inject_chapters()` step. The injector SHALL scan chapter HTML for
`<div class="question" id="…">`, look each id up in the word maps, and insert
a `qa-meta-bar` with a `.qa-play` button **before** the question div. The bar
SHALL use the shared markup from `core/qa_play_markup.py` so styling and the
mini-player behave exactly like PDF/QA play buttons.

#### Scenario: Mapped question gets a button
- GIVEN a word map contains a segment with a non-null range for `question-X`
- WHEN the chapter containing `question-X` is built
- THEN a `.qa-play` button with `data-audio`/`data-start`/`data-end` SHALL
  appear immediately before that question div

#### Scenario: Unmapped question stays buttonless
- GIVEN no word-map segment (or a `missing` one) exists for `question-Y`
- WHEN the chapter is built
- THEN no bar or disabled button SHALL be emitted for `question-Y`

### Requirement: Injection Is Idempotent And Non-Destructive
Injecting twice SHALL NOT duplicate bars. A question already preceded by a
meta bar (e.g. injected by the PDF pass) SHALL NOT receive a second bar.

#### Scenario: Re-run adds nothing
- GIVEN chapter content already processed by `inject_word_html`
- WHEN `inject_word_html` runs again on it
- THEN the output SHALL be byte-identical

### Requirement: No Interpolation For Word Chapters
Unlike the PDF maps, alignment SHALL NOT interpolate ranges for unmatched
Word questions. Segments without a confident match SHALL have
`status: "missing"` with a machine-readable reason in `notes`
(`no_match` / `no_text` / `global_miss`) and SHALL produce no button.
Borderline alignments (`status: "review"`) MAY store a range but SHALL also
produce no button until manually confirmed (status flipped to `"auto"` /
`"locked": true`).

#### Scenario: Answer audio absent
- GIVEN a question whose answer session was never recorded
- WHEN alignment finishes
- THEN that segment SHALL be `missing` and the built HTML SHALL show no
  play button for it

#### Scenario: Review-tier alignment stays buttonless
- GIVEN a segment with `status: "review"` and a stored range
- WHEN the chapter is built
- THEN no play button SHALL be emitted for it

### Requirement: Stable Question Identity Across Builds
Question ids used by maps and injector SHALL come from
`IDGenerator.generate_stable_qa_id` (hash of questioner + time + content
prefix) as embedded by `core/document_parser.py`, so maps survive full
rebuilds of the ebook.

#### Scenario: Full rebuild keeps buttons
- GIVEN a word map built against the current docx
- WHEN `gen_all.py` rebuilds the whole ebook
- THEN the same questions SHALL be matched by id and keep their play buttons
