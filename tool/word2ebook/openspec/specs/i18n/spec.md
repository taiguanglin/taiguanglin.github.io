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
`to_traditional` SHALL output Taiwan-standard traditional Chinese (台灣正體),
regardless of whether the source text is simplified or Hong-Kong/old-style
traditional. Because the source documents are already traditional with
Hong-Kong / semantically over-converted glyphs (e.g. `隻能`, `幹預`, `裏面`,
`沖突`), the method SHALL first normalise the input to simplified (`t2s`) so the
phrase dictionary can resolve semantic ambiguity, then convert to Taiwan
traditional (`s2tw`), then apply the variant-character map.

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

### Requirement: Correct s2tw "only" Over-Conversion
The bundled `opencc-python-reimplemented` `s2tw` dictionary over-converts the
adverb `只` (only) into the measure word `隻` after certain characters
(e.g. `是只能` → `是隻能`). After the `s2tw` step `to_traditional` SHALL repair
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

### Requirement: Variant Character Normalisation
Before and after OpenCC conversion the system SHALL apply a variant-character
map to standardise uncommon glyphs (e.g. `衆 → 眾`, `喫 → 吃`).

#### Scenario: Variant character replaced
- GIVEN text containing the character `衆`
- WHEN `I18nProcessor.standardize_variant_chars` is called
- THEN the returned string SHALL contain `眾` instead

### Requirement: Filename Conventions
Traditional Chinese variants of HTML files SHALL use the `_trad.html` suffix.
- `I18nProcessor.get_traditional_filename("01.html")` → `"01_trad.html"`
- `I18nProcessor.get_simplified_filename("01_trad.html")` → `"01.html"`

### Requirement: UI String Localisation
All user-visible UI strings SHALL be defined in `config.yaml` under the `i18n`
key, with `simplified` and `traditional` sub-keys for each string.

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
in `01-search.js` SHALL resolve strings from this mapping.

### Requirement: Ensure Simplified Content in Search Index
Before writing simplified search index entries, the system SHALL call
`I18nProcessor.ensure_simplified` on each item's `title`, `content`, and
`context` to guarantee that search index content is purely simplified Chinese
regardless of the source document's original character set.

## Technical Notes

- Server-side: `utils/i18n_utils.py::I18nProcessor`
- Config-based strings: `utils/config_utils.py::ConfigManager.get_i18n_text`
- Client-side strings: `assets/js/i18n-text.js`
- OpenCC converters are lazy-loaded on first use to avoid startup overhead
