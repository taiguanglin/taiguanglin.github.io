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

#### Scenario: Next-day opening without a standalone Tai header
- GIVEN a `2月6日 官网` session whose closing is followed by a bare
  `今天是2026年2月7号…先回答官网的问题` (no new `Tai师父…日答疑` line before it)
- WHEN parsed
- THEN a new `2026年2月7日 官网` `<h2>` SHALL be emitted; the following questions
  SHALL NOT remain under `2026年2月6日 官网`

#### Scenario: OCR year in Tai header still starts the new day
- GIVEN a closing paragraph that glues `Tai师父202六年2月7日答疑` onto the
  previous day's wrap-up, then `今天是202六年2月7号…回答微信公众号的问题`
- WHEN parsed
- THEN `202六年` SHALL be read as 2026 and a `2026年2月7日 微信公众号` section
  SHALL be created (not left inside the previous day)

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
line is either `名字：YYYY-MM-DD HH:MM` (typical 贴吧) or `名字：HH:MM:SS` /
`名字：HH:MM` (WeChat official-account backend timestamps, e.g. 2025-11-10).
An answer marker is `Taiguanglin：`. Numbered sub-questions (`N、`, `问题N、`, …)
posted **consecutively** by the same questioner (with no intervening answer,
separator, or new questioner) SHALL be merged into a **single** question card —
one multi-part question — with each number rendered as its own `question-text`
paragraph. An intro/greeting before the first number stays with the same card. A
numbered question that appears **after an answer** is a new turn and SHALL open a
new question card (still reusing the same questioner's name/time). Numbered
openers include Arabic `N、` / `问题N、`, Chinese `一、` / `二、` and
`问题二、` (顿号/dot only),
and a dumped restatement `第二个问题是，…` (distinct from the answerer saying
`第二个问题，…` as the **first** paragraph of a new answer, or listing points as
`第一，` / `第二，`). When a later question body is dumped into the previous
answer without `是，` — `第二个问题，…吗？`, `第二个问题 家族…`, `二是关于…`,
or a circled `②…` — and the next structural line is `Taiguanglin：`, that body
SHALL become its own question card. The same patterns SHALL stay inside the
answer when they are the answerer's own listing (①②③ in one reply) or a
continuation that is not followed by a new `Taiguanglin：`. An unnumbered
question body dumped into the previous answer — `最后一个不是问题…`,
`第二件事情…`, `另外想请教师父…`, `还有我现在…` — SHALL likewise become its
own question card when the current answer already has body and the next
structural line is `Taiguanglin：` (following paragraphs until that marker stay
on the new question). These SHALL remain in the answer when the next opener is
a new questioner rather than `Taiguanglin：`.

A **nameless** question body (no nickname line) that is dumped into the previous
answer (2025-07: 腹股沟/李光耀/中东核战/恶念/隔阴… ) SHALL become its own
question card when the joined paragraph ends with `？`/`?`, the current card is an
answer with body, the answer contains no circled `①②③` listing, and the next
paragraph (skipping wrapped continuation lines) is a `Taiguanglin：` answer. The
`？` may fall on a wrapped line, so the paragraph is joined before checking.
Questioner is recovered from a `下一个问题，名字` cue in the following answer,
else left empty. Mid-answer rhetoric ending in `？` (followed by more answer
paragraphs or a dumped-marker line such as `最后一个不是问题…`) SHALL stay in
the answer. The same applies to question bodies that are preceded by a
`名字 时间` line (space-separated, no colon, e.g. `贴吧用户_58NtK16
2025-07-07 19:48`) — such a line SHALL be read as the questioner + timestamp.
Numbered openers additionally include `第N、` (e.g. `第二、`), `问题N：`
(colons after the numeral), and `第N个问题、` (dumped with 顿号).

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

#### Scenario: Chinese numbered question after an answer opens a new card
- GIVEN `一、` then `Taiguanglin：` answer, then `二、`
- WHEN parsed
- THEN two question cards SHALL be produced, both carrying the same questioner

#### Scenario: 问题二、 after an answer opens a new card
- GIVEN an answer, then a body paragraph `问题二、临终之时…`, then another
  `Taiguanglin：` answer
- WHEN parsed
- THEN a second question card SHALL be produced for `问题二、`, and it SHALL
  NOT remain inside the previous answer

#### Scenario: 第二个问题是 restatement after an answer opens a new card
- GIVEN an answer, then a body paragraph `第二个问题是，腰容易塌…`, then another
  `Taiguanglin：` answer
- WHEN parsed
- THEN a second question card SHALL be produced for the restatement, and it SHALL
  NOT remain inside the previous answer

#### Scenario: 第二个问题， dumped question after an answer opens a new card
- GIVEN an answer, then `第二个问题，看了您的书后…算邪淫吗？`, then another
  `Taiguanglin：` that starts `第二个问题淫欲的问题…`
- WHEN parsed
- THEN a second question card SHALL be produced for `看了您的书后`, and the
  following `第二个问题淫欲的问题` SHALL remain in the new answer

#### Scenario: 第二个问题 plus space after an answer opens a new card
- GIVEN an answer, then `第二个问题 家族里面兄弟相争…存在吗？`, then another
  `Taiguanglin：`
- WHEN parsed
- THEN a second question card SHALL be produced for that body

#### Scenario: 二是关于 after an answer opens a new card
- GIVEN a question that includes `一是关于腹式呼吸…`, an answer, then
  `二是关于锻炼…想请您开示。`, then another `Taiguanglin：`
- WHEN parsed
- THEN two question cards SHALL be produced for that questioner

#### Scenario: circled ② after an answer opens a new card
- GIVEN an answer, then `②能否先度跟我有缘的人…吗？`, then another
  `Taiguanglin：`
- WHEN parsed
- THEN a second question card SHALL be produced for `②能否先度`

#### Scenario: 最后一个不是问题 dumped after an answer opens a new card
- GIVEN an answer, then `最后一个不是问题，…佛菩萨的加持力太强大了…`, then
  another `Taiguanglin：`
- WHEN parsed
- THEN a second question card SHALL be produced for that body, and it SHALL
  NOT remain inside the previous answer

#### Scenario: nameless ？-ending question after an answer opens a new card
- GIVEN an answer with body, then a nameless paragraph ending in `？` (the `？`
  may fall on a wrapped line), then another `Taiguanglin：` answer
- WHEN parsed
- THEN a second question card SHALL be produced for the paragraph,
  and it SHALL NOT remain inside the previous answer
- AND a `名字 时间` line (space-separated, no colon) directly before such a
  paragraph SHALL be read as the questioner + timestamp
- AND when the split question has no nickname line, its `questioner` SHALL
  trace up to the previous named questioner (the split body is that person's
  follow-up), rather than a topic phrase recovered from the next answer

#### Scenario: 昨天还有人问 restated question answered without a new Taiguanglin
- GIVEN an answer ending a wrap-up (`这个问题就说到这里。`), then an indented
  `昨天还有人问，…？` (or `昨天就有人问`), then its answer paragraphs with no
  intervening `Taiguanglin：`
- WHEN parsed
- THEN a new question card SHALL be produced for the restated question (named
  by tracing up to the previous questioner), followed by an answer card for the
  unmarked answer paragraphs

#### Scenario: （贴下回复） marker stays in the answer, glued name follows
- GIVEN an answer, then a left-margin `（贴下回复）`, then an indented glued
  `净红：还是希望…`
- WHEN parsed
- THEN `（贴下回复）` SHALL be appended to the previous answer and SHALL NOT
  become a questioner
- AND a new question card SHALL be produced with questioner `净红` (the glued
  name prefix stripped from the body)

#### Scenario: X、Y数量 continuation is not a numbered sub-question
- GIVEN an answer whose wrapped continuation begins `六、七秒` / `七、八成`
  (a number range) mid-sentence
- WHEN parsed
- THEN that line SHALL remain in the answer and SHALL NOT open a new question
  card (unlike a genuine indented `六、` sub-question opener)

#### Scenario: wrapped nickname fragment is dropped
- GIVEN a bare questioner name `言午` followed by an indented `(十念)：` fragment
- WHEN parsed
- THEN the fragment SHALL be dropped and SHALL NOT be glued into the question
  text

#### Scenario: ？-ending rhetoric stays in the answer
- GIVEN an answer whose own paragraph ends in `？` followed by more answer
  paragraphs (no new `Taiguanglin：`), or by a dumped-marker line such as
  `最后一个不是问题…`
- WHEN parsed
- THEN no new question card SHALL be produced; the paragraph SHALL remain
  inside the answer

#### Scenario: 第二件事情 dumped after an answer opens a new card
- GIVEN an answer, then `第二件事情，就是我之前做事情的时候…被人打断…`, then
  `我想请问Tai师父的是…`, then another `Taiguanglin：`
- WHEN parsed
- THEN a second question card SHALL be produced containing both dumped
  paragraphs, and they SHALL NOT remain inside the previous answer

#### Scenario: 另外想请教师父 dumped after an answer opens a new card
- GIVEN an answer, then `另外想请教师父，闭关有什么需要注意的事项…`, then
  another `Taiguanglin：`
- WHEN parsed
- THEN a second question card SHALL be produced for the 闭关 body

#### Scenario: 还有我现在 dumped after an answer opens a new card
- GIVEN an answer, then `还有我现在刚开始练盘腿…`, then another
  `Taiguanglin：`
- WHEN parsed
- THEN a second question card SHALL be produced for the 盘腿 body

#### Scenario: dumped follow-up without a following Taiguanglin stays in the answer
- GIVEN an answer ending `最后一个不是问题，加持力很大。`, then a new
  questioner `乙：` (no intervening `Taiguanglin：`)
- WHEN parsed
- THEN that paragraph SHALL remain in the answer and SHALL NOT open a new
  question card

#### Scenario: circled ①②③ listing in an answer is not a new card
- GIVEN an answer that lists `①见啥是啥` / `②见啥不是啥` / `③见啥还是啥`
  with no new `Taiguanglin：` between them
- WHEN parsed
- THEN those lines SHALL remain in the same answer card

#### Scenario: 第一， in an answer is not a new card
- GIVEN an answer paragraph `第一，你不需要向他解释…`
- WHEN parsed
- THEN that paragraph SHALL remain in the answer card and SHALL NOT open a
  new question (unlike PDF `一、` / `二、` with a 顿号)

#### Scenario: WeChat HH:MM:SS questioner is not swallowed by opening
- GIVEN a WeChat section whose first commenters are `亻田：10:38:28` and
  `素山Celine ：10:42:42` (time-only stamps) with answers between them
- WHEN parsed
- THEN each SHALL become its own question card with `question-time`, and the
  opening paragraph SHALL contain only the `师父说` intro — not the comment bodies

### Requirement: Questioners Without a Timestamp
Many 贴吧/微信公众号 comments carry only a name (`名字：`) with no timestamp on
its line. The parser SHALL still emit these as `<div class="question">` cards
(with an empty `question-time`) rather than stray paragraphs. A left-margin
questioner label SHALL be treated as a new questioner **only when** it opens a
section — i.e. the current card is `None` (the line directly follows a separator
line, which always precedes a questioner), the current card is a source-opening
paragraph (`师父说…` **or** a bare `今天是…` intro without the `师父说` prefix, as
on 2025-11-15 官网), **or** the current card is an answer (WeChat transcripts
often omit the separator between answers and the next nickname). Accepted labels:
`名字：`, `名字：，` (colon plus leftover comma when the timestamp is missing,
e.g. `莲舟曲：，`), a bang-suffixed nickname (`咩咩!` / `咩咩！`), or a bare short nickname
(`咩咩`) that is a plausible display name. Such a questioner's name/time SHALL be
reused by any following numbered sub-questions.

When a bare display name is immediately followed by an emoji/symbol + timestamp
line (e.g. `咩咩` then `🐏：14:20:56`), the parser SHALL keep the display name as
`questioner` and attach the timestamp, rather than using the emoji as the name.

Most questioner labels are left-margin, but a rare PDF layout may also indent the
label itself (e.g. `薛祖宜：` after a separator). When the current card is `None`
and an indented `名字：` is a plausible display name, the parser SHALL still start
a question card rather than a stray paragraph.

A left-margin line that merely ends with `：` while a question or answer card is
open (e.g. a wrapped sentence like `…想请教三个问题：`) SHALL remain body text and
SHALL NOT be misread as a questioner. PDF glyph-junk lines of punctuation-only
symbols (e.g. `"`, `#`, `$`, `%`, `&`, `+：`) SHALL be dropped and SHALL NOT
become questioner names or body paragraphs. A body line that begins with such
leftover symbols glued onto CJK text (e.g. `+，请问一下读《地藏经》…`) SHALL have
the leading junk stripped so only the real sentence remains. An exception: a nickname that is only
periods (`。：` / `。。：`) or only digits (`57：` / `13020466664：`) SHALL still
become a question card.

A left-margin bang line that continues an **unfinished** answer sentence
(e.g. closing wrap `祝大家一路顺风，回` then `家过年开心！`) SHALL stay in that
answer and SHALL NOT become a questioner.

#### Scenario: Comment after a separator has no time
- GIVEN a separator line followed by `无明萤火：` and then the comment body
- WHEN parsed
- THEN a question card with questioner `无明萤火` and no `question-time` SHALL be
  produced, and the body text SHALL belong to that card

#### Scenario: Indented questioner label after a separator
- GIVEN a separator line followed by an indented `薛祖宜：`, then the question body
- WHEN parsed
- THEN a question card with questioner `薛祖宜` SHALL be produced, and the body
  SHALL NOT appear as stray `<p>` paragraphs

#### Scenario: First section commenter after 师父说 has no time
- GIVEN a `师父说…回答微信公众号的问题` line immediately followed by `诚杨：`
- WHEN parsed
- THEN `诚杨` SHALL become a question card, not a paragraph

#### Scenario: First commenter after bare 今天是 opening has no time
- GIVEN a bare `今天是…先回答官网的问题。` opening (no `师父说` prefix) followed by
  `winnie：` and the comment body
- WHEN parsed
- THEN `winnie` SHALL become a question card, and the opening paragraph SHALL
  contain only the intro — not the comment body

#### Scenario: Colon-ending continuation is not a questioner
- GIVEN an open question whose wrapped text ends a line with `…问题：`
- WHEN parsed
- THEN no questioner named `问题` SHALL be created; the text stays in the question

#### Scenario: Name with trailing comma after colon
- GIVEN a separator followed by `莲舟曲：，` then the comment body
- WHEN parsed
- THEN a question card with questioner `莲舟曲` SHALL hold the body, and
  `莲舟曲：，` SHALL NOT appear as a stray paragraph

#### Scenario: Wrapped closing bang is not a questioner
- GIVEN an answer whose last wrap is `祝大家一路顺风，回` then a left-margin
  `家过年开心！`
- WHEN parsed
- THEN `家过年开心` SHALL NOT become a questioner, and the closing SHALL read
  `祝大家一路顺风，回家过年开心！`

#### Scenario: Bang-suffixed nickname after an answer
- GIVEN an answer card followed by `咩咩!` (and optional junk symbol lines) then
  the question body
- WHEN parsed
- THEN a question card with questioner `咩咩` SHALL be produced; `咩咩!` SHALL
  NOT remain a stray paragraph, and junk symbols SHALL NOT appear as paragraphs

#### Scenario: Bare nickname then emoji timestamp
- GIVEN an answer card followed by `咩咩` then `🐏：14:20:56` then the body
- WHEN parsed
- THEN a question card with questioner `咩咩` and time `14:20:56` SHALL be
  produced (not questioner `🐏`)

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

When a separator is followed by question body with **no** nickname line at all
(`顶礼…` / `师父好…` / `请问…`, or `：` glued onto that body), the parser SHALL
open a question card rather than a stray `<p>`. If the following `Taiguanglin：`
answer begins with `下一个问题` / `还有下一个问题` plus a nickname (before `，`
or `这位` / `这个是`), that nickname SHALL be used as `questioner`. Otherwise the
questioner name MAY be empty. The parser SHALL NOT read audio-map JSON.

A left-margin `名字：正文` glued on one line after a separator SHALL split into
questioner + body (e.g. `我空法空空亦空：感觉就是自己没了一会`). Greeting-shaped
prefixes (`顶礼Tai师父：…`) SHALL remain question body, not a nickname.

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

#### Scenario: Nameless 顶礼 body after a separator recovers the nickname
- GIVEN a separator, then indented `顶礼Tai师，为什么出家的是男众…`, then
  `Taiguanglin：还有下一个问题，Ｃｑｙ，为什么出家的是男众…`
- WHEN parsed
- THEN a question card with questioner `Ｃｑｙ` SHALL hold the 顶礼 body, and
  the body SHALL NOT leak as a `<p>` paragraph

#### Scenario: Colon glued to 师父好 body recovers 月亮
- GIVEN a separator, then `：师父好 我是一名同性恋…`, then
  `Taiguanglin：下一个问题，月亮这个是个月亮图标，…`
- WHEN parsed
- THEN a question card with questioner `月亮` SHALL hold the body, and no
  `<p>：</p>` SHALL be produced

#### Scenario: Name and body glued on one line
- GIVEN a separator followed by `我空法空空亦空：感觉就是自己没了一会` then
  more question body
- WHEN parsed
- THEN a question card with questioner `我空法空空亦空` SHALL hold the body, and
  `我空法空空亦空：感觉…` SHALL NOT appear as a stray paragraph

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
and insert `<img src="assets/images/…" alt="Image">` into the surrounding
content flow. When a Q/A card is open, the image SHALL stay inside that card
(between preceding and following body text) rather than closing the card.
Adjacent body fragments split by an image (including one-character-per-line
PDF glyph runs) SHALL be coalesced back into continuous paragraphs where the
sentence was mid-flow. Unit tests MAY inject `__PDF_IMG__:…` markers into
`parse_lines` without PyMuPDF.

#### Scenario: Image mid-question stays in the card
- GIVEN a question whose body is split by an embedded image marker
- WHEN parsed
- THEN the `<img>` SHALL appear inside the question card between the split
  body parts, and the split sentence SHALL be coalesced when mid-flow

#### Scenario: Vertical glyph run after an image merges
- GIVEN an image followed by successive single-character indented lines
- WHEN parsed
- THEN those glyphs SHALL merge into one continuous paragraph, not one `<p>`
  per character

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
