# Static Assets Specification

## Purpose

The static-assets domain manages the discovery, concatenation, and delivery of
CSS and JavaScript source files. It abstracts the build step that transforms
modular source files into single deployable assets.

## Requirements

### Requirement: Module-First Resolution
`StaticAssetsManager` SHALL resolve CSS and JS content using the following
priority order:

**CSS:**
1. If `assets/css/modules/` exists → concatenate all `*.css` files sorted by filename
2. Else if `assets/css/style.css` exists → read that file directly
3. Else → return the `CSSAssets` inline stub

**JS:**
1. If `assets/js/modules/` exists → concatenate all `*.js` files sorted by filename,
   wrapped in a `DOMContentLoaded` listener
2. Else if `assets/js/script.js` exists → read that file directly
3. Else → return the `JSAssets` inline stub

#### Scenario: Modules directory present
- GIVEN `assets/js/modules/` contains `00-base.js` and `01-search.js`
- WHEN `StaticAssetsManager.get_full_js_content()` is called
- THEN the returned string SHALL start with `document.addEventListener('DOMContentLoaded'`
- AND contain the content of both files in order

#### Scenario: Fallback to single file
- GIVEN `assets/js/modules/` does not exist but `assets/js/script.js` does
- WHEN `get_full_js_content()` is called
- THEN the content of `script.js` SHALL be returned verbatim

### Requirement: Concatenation Ordering
When concatenating module files, files SHALL be sorted lexicographically by
filename. The numeric prefix (`00-`, `01-`, …) enforces the correct order.

### Requirement: JS Wrapper
When building JS from modules, the concatenated inner content SHALL be
wrapped exactly as:
```
document.addEventListener('DOMContentLoaded', function() {
<inner content>
});
```
The wrapper constants are `JS_WRAPPER_OPEN` and `JS_WRAPPER_CLOSE` defined in
`templates/static_assets.py`.

### Requirement: Auxiliary JS Files
In addition to `script.js` and `style.css`, the converter SHALL copy:
- `assets/js/i18n-text.js`
- `assets/js/search-cache.js`
- `assets/js/jieba_rs_wasm.js`
- `assets/js/jieba_rs_wasm_bg.wasm` (binary)

These files are copied verbatim from the source `assets/js/` directory.

### Requirement: Test Isolation
`StaticAssetsManager` SHALL expose an `_assets_base` attribute that tests can
override to point at a temporary directory, enabling module-concatenation
tests without modifying the real source tree.

## Technical Notes

- Implementation: `templates/static_assets.py::StaticAssetsManager`
- Source assets: `assets/css/modules/`, `assets/js/modules/`
- `_concat_files(directory, pattern)` is a static method that globs, sorts, reads, and joins
