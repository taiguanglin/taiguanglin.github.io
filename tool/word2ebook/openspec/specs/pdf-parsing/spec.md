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
The parser SHALL remove page-number lines — both absolute counters (`N / M`) and
bare bottom-of-page counters that are only digits (`N`) — the repeated audio
footer (`完整音频请关注微信公众号：…`), and blank lines before reflow, so they
never appear in the output. Bare digit lines MUST be dropped so a word split
across a page break (e.g. `菩` | `萨`) is not corrupted into `菩39萨`.

#### Scenario: Bare page counter between wrapped lines
- GIVEN an answer whose last line on a page ends mid-word (`在菩`) and the next
  page starts with a bare page counter (`39`) then the rest of the word (`萨这里…`)
- WHEN parsed
- THEN the bare counter is removed and the answer reads `在菩萨这里…` with no
  embedded digits

#### Scenario: Absolute page counter stripped
- GIVEN a line `1409 / 2379` after body text
- WHEN parsed
- THEN that line does not appear in the chapter content

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
name `Taiguanglin`), matching the Word output markup. A timestamped questioner
line is `名字：YYYY-MM-DD HH:MM`. An answer marker is `Taiguanglin：`. Numbered
sub-questions (`N、`, `问题N、`, …) posted **consecutively** by the same questioner
(with no intervening answer, separator, or new questioner) SHALL be merged into a
**single** question card — one multi-part question — with each number rendered as
its own `question-text` paragraph. An intro/greeting before the first number stays
with the same card. A numbered question that appears **after an answer** is a new
turn and SHALL open a new question card (still reusing the same questioner's
name/time).

#### Scenario: Consecutive numbered questions merge
- GIVEN one questioner who asks `1、`, `2、`, `3、` consecutively before any answer
- WHEN parsed
- THEN a single question card SHALL be produced, carrying the questioner name/time
  once, with `1、`, `2、`, `3、` each as its own `question-text` paragraph

#### Scenario: Numbered question after an answer opens a new card
- GIVEN `1、` and `2、`, then `Taiguanglin：` answer, then `3、`
- WHEN parsed
- THEN two question cards SHALL be produced (`1、2、` merged; `3、` separate), both
  carrying the same questioner name/time

### Requirement: Questioners Without a Timestamp
Many 贴吧/微信公众号 comments carry only a name (`名字：`) with no timestamp on
its line. The parser SHALL still emit these as `<div class="question">` cards
(with an empty `question-time`) rather than stray paragraphs. A left-margin
`名字：` line (colon at end, no time) SHALL be treated as a new questioner **only
when** it opens a section — i.e. the current card is `None` (the line directly
follows a separator line, which always precedes a questioner) or the current card
is the `师父说` source-switch paragraph (the first commenter of a section). Such a
questioner's name/time SHALL be reused by any following numbered sub-questions.

A left-margin line that merely ends with `：` while a question or answer card is
open (e.g. a wrapped sentence like `…想请教三个问题：`) SHALL remain body text and
SHALL NOT be misread as a questioner.

#### Scenario: Comment after a separator has no time
- GIVEN a separator line followed by `无明萤火：` and then the comment body
- WHEN parsed
- THEN a question card with questioner `无明萤火` and no `question-time` SHALL be
  produced, and the body text SHALL belong to that card

#### Scenario: First section commenter after 师父说 has no time
- GIVEN a `师父说…回答微信公众号的问题` line immediately followed by `诚杨：`
- WHEN parsed
- THEN `诚杨` SHALL become a question card, not a paragraph

#### Scenario: Colon-ending continuation is not a questioner
- GIVEN an open question whose wrapped text ends a line with `…问题：`
- WHEN parsed
- THEN no questioner named `问题` SHALL be created; the text stays in the question

### Requirement: Wrapped-Separator Questioner
The parser SHALL handle a questioner whose name is glued to a leading separator
line (`———…———名字：`) followed by a bare time line, splitting the separator off
and merging the name with the time into a single questioner.

### Requirement: Wrapped (Line-Broken) Questioner Names
A questioner header pushed onto the trailing edge of a separator line can break
across two lines, leaving the **first part of the name** glued after the
separator and the **rest of the name (plus optional time)** on the next line
(e.g. `———…———白瀑` then `印龙：2025-08-05 10:34`, or `———…———西瓜` then `柿：`).
The parser SHALL rejoin the two halves into a single questioner header
(`白瀑印龙：2025-08-05 10:34`, `西瓜柿：`) so neither half leaks as a stray
paragraph or a separate questioner. A genuine short name that occupies its own
line after the separator (e.g. `西瓜：`) SHALL remain its own questioner and SHALL
NOT be merged.

#### Scenario: Name with time broken across the separator
- GIVEN `———…———白瀑` immediately followed by `印龙：2025-08-05 10:34`
- WHEN parsed
- THEN a single questioner `白瀑印龙` with time `2025-08-05 10:34` SHALL be
  produced, and neither `白瀑` nor `印龙` SHALL appear as its own questioner

#### Scenario: Name without time broken across the separator
- GIVEN `———…———西瓜` immediately followed by `柿：` (no time)
- WHEN parsed
- THEN a single questioner `西瓜柿` SHALL be produced

#### Scenario: Genuine short name is not over-merged
- GIVEN a clean separator line followed by `西瓜：` on its own line
- WHEN parsed
- THEN `西瓜` SHALL remain its own questioner

### Requirement: Split Name / Colon Rejoin
A short questioner line can be full-justified so its colon (and sometimes the
name itself) lands on its own line (e.g. `M` followed by a lone `：`, or
`奔跑吧兄弟` followed by a lone `：` far to the right). The parser SHALL rejoin a
plausible name line with an immediately-following lone-colon line into `名字：`
so the entry becomes a proper questioner instead of stray paragraphs (`M`, `：`).
When the name is lost entirely (a separator followed only by a bare `：` and then
the body), the parser SHALL still emit a question card (with an empty questioner
name) so the body never leaks as a `<p>：</p>` paragraph.

#### Scenario: Name and colon on separate lines
- GIVEN `M` on one line and `：` on the next, then the question body
- WHEN parsed
- THEN a questioner `M` SHALL be produced and neither `M` nor `：` SHALL appear
  as a stray paragraph

#### Scenario: Name entirely missing
- GIVEN a separator followed by a bare `：` and then the question body
- WHEN parsed
- THEN a question card (empty questioner name) SHALL hold the body, and no
  `<p>：</p>` paragraph SHALL be produced

### Requirement: In-Question Divider Lines
Real questioner-boundary separators sit at the left margin (x0 below the indent
threshold). A separator that is indented (x0 at/above the indent threshold) is a
divider the questioner drew inside their own post. The parser SHALL treat an
indented separator as a card boundary only when the following line is a new
questioner or structural marker; otherwise it SHALL drop the divider and keep the
surrounding text in the same question card, so a single question is not split and
its tail does not leak as stray paragraphs.

#### Scenario: Divider inside a question is dropped
- GIVEN an indented separator inside a question, followed by more question text
- WHEN parsed
- THEN the divider SHALL be dropped and the following text SHALL remain in the
  same question card (not leak as a `<p>` paragraph)

#### Scenario: Indented separator before a questioner still splits
- GIVEN an indented separator immediately followed by `随息居Lomi：`
- WHEN parsed
- THEN it SHALL act as a real boundary and `随息居Lomi` SHALL be a new questioner

### Requirement: Source Switching
A new day SHALL reset the current source to `贴吧`. A `师父说` line mentioning
`官网` or `官網` SHALL switch the current source to `官网`. A `师父说` line
mentioning `公众号` or `微信` SHALL switch the current source to `微信公众号`
(微信 takes precedence if both appear). Closing lines (`…回答到这里`) SHALL NOT
change the source. On the same day, `官网` / `贴吧` sections SHALL sort before
`微信公众号`.

#### Scenario: 官网 then 微信公众号
- GIVEN a day whose opening `师父说` mentions 官网, then a later `师父说` mentions
  微信公众号
- WHEN parsed
- THEN `toc_items` SHALL include `YYYY年M月D日 官网` then `YYYY年M月D日 微信公众号`

### Requirement: Cross-Year Month Chapters
When a PDF spans multiple calendar years (e.g. Nov 2025–Mar 2026), the parser
SHALL group sections by `(year, month)` so January 2026 becomes
`NN二〇二六年一月`, not `二〇二五年一月`.

### Requirement: Embedded Images
When an `ImageHandler` is supplied, the parser SHALL extract embedded PDF images
in reading order (by page y then x), skip images whose display width and height
are both below 80px, write each kept image under `assets/images/image_N.png`,
and insert `<img src="assets/images/…" alt="Image">` as an independent content
block (not inside Q/A meta). Unit tests MAY inject `__PDF_IMG__:…` markers into
`parse_lines` without PyMuPDF.

### Requirement: Shared Finalizer
The parser SHALL build each chapter via `core.chapter_finalizer.finalize_chapter`,
the same function used by `DocumentParser`, so back-to-top insertion, Q&A count
metadata, and the collapsible chapter TOC are produced identically.

## Technical Notes

- Public API: `PDFParser.parse(pdf_path, start_index=12)` and the pure,
  testable core `PDFParser.parse_lines(lines, start_index=12)` where `lines`
  is a list of `(x0, text)` tuples.
- PyMuPDF is imported lazily inside `_extract_lines` via the `_import_pymupdf()`
  helper, so unit tests can exercise `parse_lines` without PyMuPDF installed. The
  helper imports the canonical `pymupdf` module name first (PyMuPDF ≥ 1.23.0),
  falling back to `fitz`; this avoids the unrelated PyPI `fitz` package (which
  depends on `frontend`/`starlette` and raises `RuntimeError: Directory 'static/'
  does not exist` on import) shadowing the real module. A misimported `fitz`
  lacking `open()` raises a clear `ImportError` with remediation steps.
- Source labels `贴吧` / `微信公众号` are simplified; the traditional build
  converts them to `貼吧` / `微信公眾號` via OpenCC, matching the `qa/` folder
  naming used for future content.
- Helpers: `_year_to_cn` (Arabic year → circle-zero Chinese numerals),
  `_normalize_spaces` (strip CJK-adjacent spaces).
