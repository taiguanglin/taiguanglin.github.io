# Document Parsing Specification

## Purpose

The document-parsing domain is responsible for reading a `.docx` file and
producing an ordered list of `Chapter` objects, each containing structured
content (headings, Q&A pairs, paragraphs, images) and TOC metadata.

## Requirements

### Requirement: Chapter Detection
The system SHALL detect chapter boundaries by recognising Heading 1 (`<h1>`)
paragraphs as the start of a new chapter.

#### Scenario: Single-chapter document
- GIVEN a `.docx` with only one Heading 1 block
- WHEN `DocumentParser.parse_document` is called
- THEN the returned list SHALL contain exactly one `Chapter`

#### Scenario: Multi-chapter document
- GIVEN a `.docx` with N distinct Heading 1 blocks
- WHEN `DocumentParser.parse_document` is called
- THEN the returned list SHALL contain exactly N `Chapter` objects in document order

### Requirement: Q&A Pair Detection
The system SHALL identify Q&A pairs by detecting paragraphs that match the
questioner pattern (`Name：content`) and answerer pattern (`Taiguanglin：content`).

#### Scenario: Valid Q&A block
- GIVEN consecutive paragraphs where one is a questioner paragraph followed by an answerer paragraph
- WHEN the parser processes the block
- THEN a `QAPair` object SHALL be added to the corresponding `Chapter.qa_pairs`

#### Scenario: Space-separated question header
- GIVEN a question paragraph whose header is `Name<space>YYYY-MM-DD<space>HH:MM`
  (no colon after the name; e.g. `恒河沙丫 2025-05-14 19:28`, 2025-05-14 贴吧)
- WHEN the parser extracts the questioner
- THEN the system SHALL recognise the space-separated header BEFORE the
  colon split, so that the colon inside `HH:MM` is not treated as the
  name/content separator
- AND the questioner name SHALL be the single leading token
- AND the full timestamp SHALL be kept at the head of the remaining content so
  the standard time extraction yields the complete time (`YYYY-MM-DD HH:MM`)
  with the minutes (e.g. `28`) inside the `question-time` span, never leaked
  into the question text
- GIVEN a paragraph where the token before a date is not followed by a full
  `HH:MM` timestamp, the system SHALL NOT treat it as a questioner paragraph

#### Scenario: Misspelled answerer marker
- GIVEN the Word 彙總 contains an answerer marker that is a typo of
  `Taiguanglin` (e.g. `Taiguangli`, `Tiguanglin`, `_x0001_Taiguanglin`, or
  `Taiguanglin师父说`)
- WHEN the parser extracts the answerer
- THEN the system SHALL recognise it as an answerer, NOT as a questioner
- AND the rendered block SHALL be one `question` div followed by one `answer`
  div wrapped in a single `qa-pair` article, so the answer is never emitted as
  a second `question` div
- AND the system SHALL NOT treat ordinary questioner names (including ones that
  merely contain `Tai`/`师父`) as answerers
- NOTE: a marker embedded **mid-paragraph** (`…内容。Taiguanglin：回答`) is out
  of scope for this requirement; the marker regex stays anchored at line start.

### Requirement: Stable Element IDs
The system SHALL generate stable, deterministic IDs for each Q&A pair based on
`questioner_name + normalized_time + first_50_chars_of_content` hashed with MD5.

#### Scenario: Same content generates same ID
- GIVEN two runs of the parser against the same `.docx`
- WHEN the parser generates IDs
- THEN the IDs SHALL be identical across runs

#### Scenario: Duplicate base ID within one parser run
- GIVEN two Q&A blocks in the same run whose normalized components
  (questioner + time + content prefix) produce the same hash
- WHEN the parser generates their IDs
- THEN the first occurrence SHALL keep the base `question-<hash>` /
  `answer-<hash>` ID and every subsequent occurrence SHALL receive a
  `-2`, `-3`, … numeric suffix, so element IDs stay unique per page

### Requirement: Image Extraction
The system SHALL extract inline images from the `.docx`, transcode them to WebP,
and save them as `assets/images/image_N.webp` in the output folder.

#### Scenario: Document with images
- GIVEN a `.docx` with embedded images
- WHEN the parser runs
- THEN each image SHALL be saved to `assets/images/` and referenced in HTML via relative path

#### Scenario: Source image is PNG or JPEG
- GIVEN a `.docx` whose embedded images are PNG, JPEG, or GIF
- WHEN `ImageHandler.save_image_bytes` runs
- THEN the bytes SHALL be transcoded to WebP before being written
  (`utils/image_markup.py::encode_webp`, quality `WEBP_QUALITY` = 85, alpha preserved)
- AND only the WebP file SHALL be written — the source encoding SHALL NOT also be
  kept, so `assets/images/` ends up WebP-only

### Requirement: TOC Metadata
For each chapter the system SHALL populate `Chapter.toc_items` with `TOCItem`
records for all Heading 2, 3, and 4 paragraphs found within that chapter.

### Requirement: Shared Chapter Finalize
The parser SHALL finalize each chapter through
`core.chapter_finalizer.finalize_chapter` (QA-block merging, back-to-top
insertion, Q&A count metadata, and collapsible chapter TOC), which is the same
function used by `core/pdf_parser.py`. This keeps Word and PDF chapter output
byte-for-byte consistent in structure.

## Technical Notes

- Implementation: `core/document_parser.py::DocumentParser`
- Shared finalize: `core/chapter_finalizer.py` (`finalize_chapter`, `merge_qa_blocks`, `insert_back_to_top`)
- Uses: `python-docx` for DOCX reading
- ID generation: `utils/text_utils.py::IDGenerator.generate_stable_qa_id`
- Questioner/time extraction: `utils/text_utils.py::TextProcessor.extract_questioner_info`
  (space-separated `Name YYYY-MM-DD HH:MM` headers checked before the colon split)
- Heading level mapping: DOCX `heading 1` → `<h1>`, `heading 2` → `<h2>`, etc.

### Requirement: Image Markup
Paragraph-embedded images SHALL be rendered through
`utils/image_markup.py::render_img_tag` with `loading="lazy"`, `alt` taken from
the paragraph text (first 40 chars) or the `文章配圖` fallback, and
dimension-based `width`/`height` when the file parses.

#### Scenario: Paragraph contains both an image and text
- GIVEN a paragraph that holds both an embedded image and text (e.g. a question
  header `贴吧用户_QUDy8Na：2025-03-10 18:29` plus the question body)
- WHEN `DocumentParser._paragraph_to_html` runs
- THEN the paragraph SHALL be classified normally (question / answer / heading /
  regular paragraph) and the image SHALL be appended after that block
- AND the paragraph's text SHALL NOT be discarded

> Regression note (2026-10): the previous implementation returned `image_html`
> alone as soon as an image was found, discarding the whole paragraph's text.
> That silently dropped the questions for 2025-03-10 `贴吧用户_QUDy8Na`,
> 2025-05-15 `猫猫|` and 2025-03-12 `心的选择`, leaving orphaned answers in the
> published ebook.

#### Scenario: Paragraph is a pure image with no text
- GIVEN a paragraph that contains only an embedded image and no text
- WHEN `DocumentParser._paragraph_to_html` runs
- THEN the output SHALL be the image HTML alone
- AND no empty `<p>` or `<div>` wrapper SHALL be emitted

#### Scenario: Paragraph contains several images
- GIVEN a paragraph that embeds more than one image (e.g. a question that
  references 圖1／圖2／圖3, as 2025-03-10 `贴吧用户_QUDy8Na` does)
- WHEN `DocumentParser._extract_image_from_paragraph` runs
- THEN every image in the paragraph SHALL be emitted, in document order
- AND each emitted `<img>` SHALL reference its own distinct asset

> Regression note (2026-10): the previous implementation returned after the
> first image of a paragraph, so the remaining attachments were silently
> dropped — the source `.docx` holds 35 embedded images but only 28 were
> rendered.

### Requirement: Image Preservation Across the Three-Stage Rebuild
Every image emitted by the parser SHALL survive stage 2 and stage 3 and SHALL
appear in the published ebook. The parser's output is not the published
output: stage 2 (`tool/qa_split_ebook/extract.py`) reads the stage-1 draft's
HTML, and stage 3 (`tool/qa_split_ebook/gen_classified.py`) rebuilds the 12
thematic chapters from it.

Images live in three different places, and each stage must handle all three:

| Position | Produced by | Collected by | Re-inserted by |
|---|---|---|---|
| sibling of the `question`/`answer` div | `DocumentParser._append_image` (Word chapters) | `extract.sibling_imgs` | `gen_classified._attach_imgs` |
| child of the `question`/`answer` div, outside `question-text`/`answer-text` | `core/pdf_parser.py` (PDF chapters) | `extract.sibling_imgs` | `gen_classified._attach_imgs` |
| directly under `<main>`, between two `qa-pair` articles | `core/pdf_parser.py` (page-level PDF image) | `extract.py` (attached to the preceding answer) | `gen_classified._attach_imgs` |

#### Scenario: Image sits outside the question/answer div
- GIVEN a stage-1 draft whose `question` div is followed by one or more `<img>`
  siblings
- WHEN `gen_classified.extract_word_blocks` serialises the chapter
- THEN the images SHALL be carried into the serialised `question` block
- AND they SHALL NOT be dropped

#### Scenario: Image sits inside the div but outside question-text
- GIVEN a stage-1 draft whose `question` div contains `<img>` elements that are
  siblings of its `question-text` children (the PDF layout)
- WHEN `extract.sibling_imgs` runs
- THEN those images SHALL be returned alongside the div's trailing images

#### Scenario: Published ebook has no dangling or orphaned images
- GIVEN a built `wenda2_ebook/`
- WHEN the image references and the `assets/images/` directory are compared
- THEN every `<img src="assets/images/…">` SHALL point to an existing file
- AND every file in `assets/images/` SHALL be referenced by at least one
  chapter
- AND the published chapters SHALL contain images at all

> Regression note (2026-10-29): this chain was broken end to end — the
> published ebook had **0** `<img>` tags while all 64 WebP assets sat in
> `assets/images/` (35 from the Word source, 29 from the monthly PDFs).
> `tool/qa_split_ebook/tests/test_image_preservation.py` guards it, including a
> source-to-published reconciliation by WebP content hash.

