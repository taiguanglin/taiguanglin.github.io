# Internationalization (i18n) Specification

## Purpose

The i18n domain handles conversion between simplified and traditional Chinese,
variant-character normalisation, and localisation of all UI strings used in
generated HTML pages and the client-side JavaScript.

## Requirements

### Requirement: Simplified ↔ Traditional Conversion
The system SHALL support bidirectional conversion between simplified and
traditional Chinese using the `opencc-python-reimplemented` library.

#### Scenario: Simplified to traditional
- GIVEN a simplified Chinese string
- WHEN `I18nProcessor.to_traditional` is called
- THEN the returned string SHALL be valid traditional Chinese

#### Scenario: Empty string passthrough
- GIVEN an empty string is passed to any conversion method
- WHEN the method runs
- THEN it SHALL return an empty string without raising

### Requirement: Taiwan-Standard Traditional Output
`to_traditional` SHALL output Taiwan-standard traditional Chinese (台灣正體).
The source documents are simplified Chinese, so the method SHALL normalise the
input to simplified (`t2s`, which also flattens any stray Hong-Kong /
old-style glyphs), convert to Taiwan traditional with Taiwan
regional vocabulary (`s2twp`), then
repair the inherent one-to-many mis-conversions of OpenCC's `s2twp` dictionary
(see below), apply curated context fixes, and finally apply the
variant-character/word map. The one-to-many repairs are required because both
`opencc` and `opencc-python-reimplemented` greedily segment ambiguous
simplified characters (`只`, `发`, `后`, `里`, …) and pick the wrong traditional
glyph in certain contexts.

#### Scenario: Common Taiwan glyphs are selected
- GIVEN text containing `才`, `群`, or legacy variants `纔`, `羣`, `爲`, `裏`
- WHEN `I18nProcessor.to_traditional` is called
- THEN the output SHALL use the common Taiwan forms `才`, `群`, `為`, `裡`

#### Scenario: Taiwan regional vocabulary is selected
- GIVEN the simplified text `软件、鼠标、信息`
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL be `軟體、滑鼠、資訊`
- AND it SHALL NOT use Hong Kong or Mainland regional vocabulary

#### Scenario: Over-converted "only" is corrected
- GIVEN the text `隻能` (over-converted "only can")
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL be `只能`

#### Scenario: Over-converted "intervene" is corrected
- GIVEN the text `幹預`
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL be `干預`

#### Scenario: Taiwan glyph preference
- GIVEN the text `裏面`
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL be `裡面` (Taiwan uses `裡`, not `裏`)

#### Scenario: Legitimate measure word preserved
- GIVEN the text `一隻貓` (where `隻` is a valid measure word)
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL remain `一隻貓`

### Requirement: Correct s2twp "only" Over-Conversion
The bundled `opencc-python-reimplemented` `s2twp` dictionary over-converts the
adverb `只` (only) into the measure word `隻` after certain characters
(e.g. `是只能` → `是隻能`). After the `s2twp` step `to_traditional` SHALL repair
this: a `隻` whose following character is an adverb/verb/copula follower
(`能`, `要`, `是`, `有`, `會`, …) and whose preceding character is not a
number/quantifier SHALL be converted back to `只`. Fixed measure idioms such as
`隻字`, `隻身`, and `船隻` SHALL remain unchanged because their following
characters are not in the follower set.

#### Scenario: Adverb after copula repaired
- GIVEN the text `就是隻能治標`
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL be `就是只能治標`

#### Scenario: Measure idiom untouched
- GIVEN the text `隻字不提`
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL still contain `隻字不提`

#### Scenario: Manual context correction for ambiguous cases
- GIVEN a phrase the general heuristic cannot resolve, such as the Zen text
  `一歸何處，那一隻能回到自性` (where `一` is the pronoun "the One", so `隻能`
  should be `只能`, yet `一` is normally a measure-word prefix)
- WHEN `I18nProcessor.to_traditional` is called
- THEN a curated context-fix map SHALL correct it to `那一只能回到自性`,
  while genuine measure-word usage such as `這一隻能飛` SHALL remain unchanged

### Requirement: Correct s2twp "emit/hair" (發/髮) Over-Conversion
Simplified `发` maps to both `發` (emit/issue) and `髮` (hair). `s2twp`
over-converts `發` into `髮` after characters that collocate with hair
(e.g. `亂发愿` is read as `亂髮`+`願`; `眾生发願` as `生髮`+…). After `s2twp`,
`to_traditional` SHALL convert a `髮` back to `發` when its following character
is an emit/issue follower (`願`, `現`, `生`, `出`, `音`, `揮`, `作`, `展`, …),
OR when its preceding character is not a hair modifier (`頭`, `白`, `脫`, `長`,
`理`, `染`, …) and its following character is not a hair noun (`際`, `型`, `絲`,
…). Genuine hair words (`頭髮`, `白髮`, `髮際線`, `脫髮`, `理髮`) SHALL be kept.

#### Scenario: Emit over-converted to hair is repaired
- GIVEN the simplified text `不要乱发愿` (and `众生发愿`, `舌头发生`)
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL be `不要亂發願` (and `眾生發願`, `舌頭發生`)

#### Scenario: Genuine hair word preserved
- GIVEN the simplified text `头发的颜色` (and `白发变黑`, `发际线`)
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL be `頭髮的顏色` (and `白髮變黑`, `髮際線`)

### Requirement: Correct s2twp "after/queen" (後/后) Under-Conversion
Simplified `后` maps to both `後` (after) and `后` (queen/empress). `s2twp`
leaves `后` unconverted in `天后`, `東西后`, `父母后`, `聊天后` etc. where it
means "after". After `s2twp`, `to_traditional` SHALL convert `后` to `後` unless
its preceding character is a queen modifier (`皇`, `太`, `呂`, `武`, `蟻`, `王`,
…) or its following character is a queen noun (`宮`, `娘`, `妃`, `土`, …), so
that `皇后`, `太后`, `呂后`, `蟻后`, `天后宮`, `后土` are preserved.

#### Scenario: "after" under-conversion repaired
- GIVEN the simplified text `49天后再看看` (and `吃了东西后盘腿`)
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL be `49天後再看看` (and `吃了東西後盤腿`)

#### Scenario: Queen word preserved
- GIVEN the simplified text `慈禧太后` (and `娶一个皇后`)
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL contain `太后` (and `皇后`)

### Requirement: Correct s2twp "inside" (裡/里) Under-Conversion
Simplified `里` maps to both `裡` (inside) and `里` (li/mile/village/translit).
`s2twp` converts `這裡`/`心裡` correctly but leaves `里` after certain phrases
(`劇本里`, `知道里面`, `六道里`, `視角里`, `輪迴里`). After `s2twp`,
`to_traditional` SHALL convert `里` to `裡` when preceded by an inside-context
character (`本`, `道`, `會`, `角`, `方`, `場`, `子`, `迴`, `穴`, `識`, `經`,
`向`). Distance/transliteration words (`公里`, `千里`, `鄰里`, `斯里蘭卡`)
SHALL be preserved because their preceding character is not in that set.

#### Scenario: "inside" under-conversion repaired
- GIVEN the simplified text `剧本里写的` (and `六道里`, `我知道里面有鬼`)
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL be `劇本裡寫的` (and `六道裡`, `我知道裡面有鬼`)

#### Scenario: Distance/transliteration "li" preserved
- GIVEN the simplified text `公里` (and `斯里兰卡`, `邻里`)
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL be `公里` (and `斯里蘭卡`, `鄰里`)

### Requirement: Sleepy "睏" Context Correction
Simplified `困` covers both `困` (trapped/difficult) and `睏` (sleepy/drowsy).
`s2twp` always produces `困`. Where a curated phrase unambiguously means sleepy,
`to_traditional` SHALL correct it via the context-fix map, while genuine
"trapped/difficult" usage (`困難`, `被困`) SHALL remain `困`.

#### Scenario: Sleepy 困 corrected to 睏
- GIVEN the simplified text `反而你现在困才是更大的问题`
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL contain `現在睏才是`

#### Scenario: Trapped 困 preserved
- GIVEN the simplified text `遇到困难`
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL contain `困難`

### Requirement: Variant Character Normalisation
Before and after OpenCC conversion the system SHALL apply a variant-character
map to standardise uncommon glyphs (e.g. `衆 → 眾`, `喫 → 吃`). The same map
SHALL also correct unambiguous word-level mis-conversions where the traditional
form has only one correct spelling but `s2twp` picks the wrong one:
`制造 → 製造`, `制作 → 製作`, `製度 → 制度`, `分鍾 → 分鐘`.

#### Scenario: Variant character replaced
- GIVEN text containing the character `衆`
- WHEN `I18nProcessor.standardize_variant_chars` is called
- THEN the returned string SHALL contain `眾` instead

#### Scenario: Word-level mis-conversion corrected
- GIVEN the simplified text `少和人制造矛盾` (and `十几分钟`)
- WHEN `I18nProcessor.to_traditional` is called
- THEN the result SHALL be `少和人製造矛盾` (and `十幾分鐘`)

### Requirement: OOXML Control-Character Escape Removal
Word escapes characters that are invalid in XML — the C0 control range
(`0x00`–`0x1F`) and DEL (`0x7F`) — into literal strings of the form `_xHHHH_`
(e.g. `_x0001_`, `_x000B_`), which `python-docx` returns verbatim. These are
meaningless noise. `standardize_variant_chars` SHALL strip every such
control-character escape (replacing it with the empty string) so it appears in
neither the simplified nor traditional output. Because this runs inside
`standardize_variant_chars`, both `to_traditional` and `ensure_simplified`
inherit the behaviour. Escapes for printable characters (e.g. `_x005F_` for the
underscore itself, `_x0041_` for `A`) are outside the control range and SHALL be
preserved so genuine body text is never deleted.

#### Scenario: Control-character escape stripped
- GIVEN the text `真實不虛的希望_x0001_` (and `一行_x000B_文字`)
- WHEN `I18nProcessor.standardize_variant_chars` (or `to_traditional` /
  `ensure_simplified`) is called
- THEN the result SHALL be `真實不虛的希望` (and `一行文字`), with no `_xHHHH_`
  control-character escape remaining

#### Scenario: Printable-character escape preserved
- GIVEN the text `保留_x005F_底線`
- WHEN `I18nProcessor.standardize_variant_chars` is called
- THEN the result SHALL still contain `_x005F_`

### Requirement: Filename Conventions
Traditional Chinese variants of HTML files SHALL use the `_trad.html` suffix.
- `I18nProcessor.get_traditional_filename("01.html")` → `"01_trad.html"`
- `I18nProcessor.get_simplified_filename("01_trad.html")` → `"01.html"`

### Requirement: UI String Localisation
All user-visible UI strings SHALL be defined in `config.yaml` under the `i18n`
key, with `simplified` and `traditional` sub-keys for each string.
Header navigation labels SHALL use `navigation.ebook_toc`,
`navigation.site_home`, and `navigation.cross_ebook` so the ebook total,
site-home, and sibling-ebook destinations remain unambiguous in both variants.

#### Scenario: i18n text retrieval
- GIVEN `config.yaml` defines `i18n.navigation.home.simplified = "首页"`
- WHEN `get_i18n_text("navigation.home", is_traditional=False)` is called
- THEN `"首页"` SHALL be returned

#### Scenario: Missing key returns default
- GIVEN a key path that does not exist in `config.yaml`
- WHEN `get_i18n_text` is called with a `default` argument
- THEN the `default` value SHALL be returned

### Requirement: Client-Side i18n
The JavaScript file `assets/js/i18n-text.js` SHALL export or define a mapping
of UI string keys to their simplified and traditional values, mirroring
`config.yaml`. The helper `getI18nText(key, isTraditional, fallback, params)`
SHALL resolve strings from this mapping. Search scope labels
(`search.scope_label`, `search.scope_question`, `search.scope_answer`,
`search.scope_both`) SHALL appear in both `config.yaml` and `i18n-text.js`,
and the index template SHALL inject them into the scope control buttons.

### Requirement: Ensure Simplified Content in Search Index
Before writing simplified search index entries, the system SHALL call
`I18nProcessor.ensure_simplified` on each item's `title`, `content`, and
`context` to guarantee that search index content is purely simplified Chinese
regardless of the source document's original character set. To preserve the
existing simplified edition's wording, `資訊` SHALL be normalized to `信息` only
on the simplified-output path; this replacement SHALL NOT affect Taiwan
traditional output.

## Technical Notes

- Server-side: `utils/i18n_utils.py::I18nProcessor`
- Config-based strings: `utils/config_utils.py::ConfigManager.get_i18n_text`
- Client-side strings: `assets/js/i18n-text.js`
- OpenCC converters are lazy-loaded on first use to avoid startup overhead
