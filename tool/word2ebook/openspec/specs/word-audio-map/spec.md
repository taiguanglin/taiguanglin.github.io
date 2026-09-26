# Word Audio Map Specification

## Purpose

Attach per-question audio playback to Word-sourced ebook chapters
(`wenda2_ebook/01.html`–`12.html`, the categorised Word document) without
changing their prose.

The **injection source of truth is `audio_map2/*.json`** — the chronological
Word 彙總 alignments reviewed in `/audio_map2/index.html`. The older
thematic `data/audio_map_word/word-*.json` flow and its `tool/word_audio_map/`
aligner have been removed. `chapter_question_ids` (the ebook's stable question
ids) are now frozen onto the reviewed audio_map2 segments, and
`inject_word_chapters()` keys off those.

## Requirements

### Requirement: Reviewed Chronological Mapping Store
The system SHALL read play ranges from `audio_map2/*.json`. Each segment that
maps to one or more theme-chapter questions SHALL carry `chapter_question_ids`
(a list of ebook stable question ids) and `chapter_indexes`; these fields are
now frozen in the JSONs (the script that wrote them has been removed). A
segment's review state is encoded by
the editorial UI's listen record in `meta.lastPlayed` (present = human actually
listened; absent = not yet listened / machine-aligned only). The `status` field
(`manual` / `reviewed` / `auto` / `missing`) remains produced by the aligner but
is **not** the injection gate.

#### Scenario: One chronological segment maps to several chapter questions
- GIVEN the 彙總 docx merged two sub-questions the chapter version keeps separate
- WHEN the segment carries its frozen `chapter_question_ids`
- THEN both stable question ids SHALL appear in that segment's
  `chapter_question_ids` and SHALL share the segment's reviewed range

A segment that speaks several ebook blocks in a row (a merged Word segment) may
be linked to several of them.  Where such a link shares the segment's coarse
range, `notes` SHALL carry an `html-portion:` marker naming the block id, so the
shared range is not mistaken for a precise anchor.

### Requirement: Reviewed-Gated Injection
`inject_word_chapters()` SHALL insert an inline `.qa-play` button **only** for
segments that a human actually listened to **and** carry a non-null range
(`meta.lastPlayed` present and `start` is not null). Machine-aligned segments
without a listen record (no `meta.lastPlayed`, regardless of `status`) SHALL
produce no button.

#### Scenario: Listened segment gets a button
- GIVEN an audio_map2 segment with `chapter_question_ids` = `["question-X"]`,
  a `meta.lastPlayed` listen record, and a non-null range resolved to an opus
  `audio_file`
- WHEN the chapter containing `question-X` is built
- THEN a `.qa-play` button with `data-audio`/`data-start`/`data-end` SHALL
  appear inline immediately after the answer's `<span class="answerer">`
  (no number, no separate meta-bar line)

#### Scenario: Unlistened segment stays buttonless
- GIVEN an audio_map2 segment with no `meta.lastPlayed` (never listened) and a
  non-null range
- WHEN the chapter is built
- THEN no play button SHALL be emitted for that question

### Requirement: Deduplicated-ID Base Fallback
The ebook's `IDGenerator` appends a `-2`, `-3`, … suffix when the same base
id recurs in one parser run, but `audio_map2/*.json` froze **base** ids in
`chapter_question_ids` / `chapter_answer_ids`. `inject_word_html_from_audio_map2()`
SHALL therefore retry a miss (in both the `by_qid` and `by_answer` lookups)
against the id with any trailing `-<n>` suffix stripped. An exact match on the
full suffixed id SHALL take precedence over the base retry.

#### Scenario: Suffixed question id resolves via frozen base id
- GIVEN a chapter whose question block id is `question-X-2` and an audio_map2
  segment frozen with `chapter_question_ids` = `["question-X"]`
- WHEN the chapter is built
- THEN the segment SHALL be found for that question via the base id `question-X`
  and the button injected when the segment is reviewed

#### Scenario: Exact suffixed id wins over base
- GIVEN the segment maps contain both `question-X-2` and `question-X`
- WHEN injecting
- THEN the full-id lookup SHALL win and the base retry SHALL not shadow it

### Requirement: Questionless Blocks Are Addressed By Their Answer Id
Some ebook blocks have **no** `<div class="question">` of their own: the
question was submitted as a screenshot (`<img alt="提問人：日期 …">`) or was
replaced by a placeholder (`（此問題丟失或未收集到）` / `问题缺失` /
`(TAI師父自白)`).  Such blocks SHALL be mapped by the audio_map2 segment that
speaks them, recorded as `chapter_answer_ids` (the block's own `answer-…` id)
plus `chapter_indexes`, and `link_image_blocks.py` SHALL be the tool that
derives those links by content.

`inject_word_html_from_audio_map2()` SHALL run a second pass over the answer
blocks that the question-driven pass never reached, resolving them through
`by_answer` alone.  A block already reached by the question-driven pass SHALL be
skipped so no block receives two buttons, and the answerer-name lookup SHALL be
bounded by the block's own answer div (never reaching into the next question
block).  The same `meta.lastPlayed` review gate SHALL apply.

#### Scenario: Screenshot-question block gets its button
- GIVEN a chapter containing `<hr/><img alt="心的選擇：2025-03-12 18:42 …"/>` followed
  by `<div class="answer" id="answer-0d6082063772">` (no question div), and an
  audio_map2 segment with `chapter_answer_ids` = `["answer-0d6082063772"]`, a
  `meta.lastPlayed` record and a non-null range
- WHEN the chapter is built
- THEN a `.qa-play` button with that segment's range SHALL appear inline
  immediately after that block's `<span class="answerer">`, and no button SHALL
  appear for any other block in that chapter

#### Scenario: Unreviewed questionless block stays buttonless
- GIVEN a questionless answer block whose only audio_map2 segment lacks
  `meta.lastPlayed`
- WHEN the chapter is built
- THEN no play button SHALL be emitted for that block

#### Scenario: Question-driven block is not double-injected
- GIVEN a chapter with both normal question+answer blocks and a questionless
  block, all of them listed in `chapter_answer_ids`
- WHEN the chapter is built
- THEN each block SHALL carry exactly one inline play button

### Requirement: Injection Is Idempotent And Non-Destructive
Injecting twice SHALL NOT duplicate buttons. An answer whose answerer name is
already followed by an inline play button SHALL NOT receive a second button.

#### Scenario: Re-run adds nothing
- GIVEN chapter content already processed by `inject_word_html_from_audio_map2`
- WHEN `inject_word_html_from_audio_map2` runs again on it
- THEN the output SHALL be byte-identical

### Requirement: No Interpolation For Word Chapters
Unlike the PDF maps, alignment SHALL NOT interpolate ranges for unmatched Word
questions. Segments without a confident match SHALL be `status: "missing"` and
SHALL produce no button. Machine-aligned segments (`status: "auto"` or
`status: "manual"`) SHALL produce no button until a human actually listens to
them (a `meta.lastPlayed` record is written by the review UI).

#### Scenario: Answer audio absent
- GIVEN a question whose answer session was never recorded
- WHEN alignment runs
- THEN that segment SHALL be `missing` and the built HTML SHALL show no play
  button for it

#### Scenario: Unlistened segment stays buttonless
- GIVEN a machine-aligned segment with a stored range but no `meta.lastPlayed`
- WHEN the chapter is built
- THEN no play button SHALL be emitted for it

### Requirement: Stable Question Identity Across Builds
Question ids used by maps and injector SHALL come from
`IDGenerator.generate_stable_qa_id` (hash of questioner + time + content
prefix) as embedded by `core/document_parser.py`, so maps survive full rebuilds
of the ebook.

#### Scenario: Full rebuild keeps buttons
- GIVEN a word map built against the current docx
- WHEN `gen_all.py` rebuilds the whole ebook
- THEN the same questions SHALL be matched by id and keep their play buttons

### Requirement: Fine Boundary Calibration
Alignment SHALL refine every mapped segment's start to the spoken onset with
**sub-second precision**, using SRT transition cues (e.g. 「下一個問題」/ questioner
name) or the answer's pinyin onset. The chronological aligner
(`tool/word_audio_map2/build_maps.py`) computes start/end, `status`
(`matched` / `pending` / `missing`), and `confidence` per segment and preserves
any existing human corrections in the raw SRT data.

#### Scenario: Start lands on the spoken transition
- GIVEN a segment whose start fell mid-cue
- WHEN alignment runs on the session
- THEN the new start SHALL sit at (or just before) the SRT onset and `end`
  SHALL equal the next segment's start
