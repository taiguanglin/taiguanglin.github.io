# Word Audio Map Specification

## Purpose

Attach per-question audio playback to Word-sourced ebook chapters
(`wenda2_ebook/01.html`–`12.html`, the categorised Word document) without
changing their prose.

As of the reviewed-chronological workflow, the **injection source of truth is
`audio_map2/*.json`** (the chronological Word 彙總 alignment reviewed in
`/audio_map2/index.html`), not the older thematic `data/audio_map_word/`
maps. `tool/word_audio_map2/link_chapters.py` writes `chapter_question_ids`
(the ebook's stable question ids) onto the reviewed audio_map2 segments, and
`inject_word_chapters()` keys off those. The legacy `data/audio_map_word/`
path is retained only when an explicit `map_dir` is passed (tests / the old
`word_audio_map` flow, which still produces those files).

## Requirements

### Requirement: Reviewed Chronological Mapping Store
The system SHALL read reviewed play ranges from `audio_map2/*.json`. Each
segment that maps to one or more theme-chapter questions SHALL carry
`chapter_question_ids` (a list of ebook stable question ids) and
`chapter_indexes`, produced by `tool/word_audio_map2/link_chapters.py`. A
segment's review state is encoded by the editorial UI's listen record in
`meta.lastPlayed` (present = human actually listened; absent = not yet
listened / only machine-aligned). The legacy `status` field (`manual` /
`reviewed` / `auto` / `missing`) remains produced by the aligner but is **no
longer the injection gate**.

#### Scenario: One chronological segment maps to several chapter questions
- GIVEN the 彙總 docx merged two sub-questions the chapter version keeps separate
- WHEN `link_chapters.py --apply` runs
- THEN both stable question ids SHALL appear in that segment's
  `chapter_question_ids` and SHALL share the segment's reviewed range

### Requirement: Reviewed-Gated Injection
`inject_word_chapters()` SHALL insert a `.qa-play` `qa-meta-bar` **only** for
segments that a human actually listened to **and** carry a non-null range
(`meta.lastPlayed` present and `start` is not null). Machine-aligned segments
without a listen record (`meta.lastPlayed` absent — regardless of `status`)
SHALL produce no button.

#### Scenario: Listened segment gets a button
- GIVEN an audio_map2 segment with `chapter_question_ids` = `["question-X"]`,
  a `meta.lastPlayed` listen record, and a non-null range, resolved to an opus
  `audio_file`
- WHEN the chapter containing `question-X` is built
- THEN a `.qa-play` button with `data-audio`/`data-start`/`data-end` SHALL
  appear immediately before that question div

#### Scenario: Unlistened segment stays buttonless
- GIVEN an audio_map2 segment lacking `meta.lastPlayed` (never listened) with a range
- WHEN the chapter is built
- THEN no play button SHALL be emitted for that question

### Requirement: Question-ID Keyed Injection (legacy fallback)
When an explicit `map_dir` is passed, `inject_word_chapters()` SHALL retain the
legacy `data/audio_map_word/word-NN.json` flow: key by `question_id`, gate on
`status == "auto"` plus `meta.confirmed`/`lastPlayed`, and insert the same
`qa-meta-bar` markup via `core/qa_play_markup.py`.

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

### Requirement: Fine Boundary Calibration
`tool/word_audio_map/calibrate.py` SHALL refine every mapped segment's start
to the spoken onset with **sub-cue fractional precision**: prefer the
「下一个问题」transition character; else a pinyin name occurrence (homophone
names included); else the LCB-block onset of answer/question text on the
session pinyin stream. Adaptive lead-in follows the preceding pause;
`end_i = start_{i+1}`. Locked/manual segments SHALL be preserved, per-segment
corrections clamped to `--limit` seconds (default 30) around the existing
boundary, and provenance recorded in `notes` (`;cal2(…)`). Repeated runs
SHALL converge (residual recalibrations approach zero).

#### Scenario: Start lands on the spoken transition
- GIVEN a segment whose previous start was mid-cue
- WHEN calibration runs on its session
- THEN the new start SHALL sit at (or just before) the「下一个问题」/ name
  onset per the pause-based lead-in, and `end` SHALL equal the next
  segment's refined start

#### Scenario: Repeated runs converge
- GIVEN calibration has been applied once
- WHEN it runs again without other map edits
- THEN the number of recalibrated segments SHALL be near zero
