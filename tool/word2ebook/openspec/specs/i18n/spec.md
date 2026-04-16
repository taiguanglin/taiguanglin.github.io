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
