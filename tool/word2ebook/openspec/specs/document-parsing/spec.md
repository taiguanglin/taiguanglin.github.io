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

### Requirement: Stable Element IDs
The system SHALL generate stable, deterministic IDs for each Q&A pair based on
`questioner_name + normalized_time + first_50_chars_of_content` hashed with MD5.

#### Scenario: Same content generates same ID
- GIVEN two runs of the parser against the same `.docx`
- WHEN the parser generates IDs
- THEN the IDs SHALL be identical across runs

### Requirement: Image Extraction
The system SHALL extract inline images from the `.docx` and save them as
`assets/images/image_N.png` in the output folder.

#### Scenario: Document with images
- GIVEN a `.docx` with embedded images
- WHEN the parser runs
- THEN each image SHALL be saved to `assets/images/` and referenced in HTML via relative path

### Requirement: TOC Metadata
For each chapter the system SHALL populate `Chapter.toc_items` with `TOCItem`
records for all Heading 2, 3, and 4 paragraphs found within that chapter.

## Technical Notes

- Implementation: `core/document_parser.py::DocumentParser`
- Uses: `python-docx` for DOCX reading
- ID generation: `utils/text_utils.py::IDGenerator.generate_stable_qa_id`
- Heading level mapping: DOCX `heading 1` → `<h1>`, `heading 2` → `<h2>`, etc.
