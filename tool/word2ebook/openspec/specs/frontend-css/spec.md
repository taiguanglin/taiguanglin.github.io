# Frontend CSS Specification

## Purpose

The frontend CSS defines the visual appearance of all ebook pages including
base typography, layout, Q&A blocks, dark mode overrides, reader UX elements,
search UI, and TOC level controls.

## Requirements

### Requirement: Module File Structure
Source CSS SHALL be split into ordered module files under `assets/css/modules/`.
Files SHALL be named with a two-digit numeric prefix so lexicographic sort equals
cascade order.

| File | Responsibility |
|---|---|
| `00-base.css` | `:root` design tokens (colors, radii, shadows), `body`, headings `h1–h4`, `p`, `img`, `a`, `hr`, `.toc`, `.question`, `.answer`, Q&A meta elements, dark-mode base |
| `01a-layout.css` | Reading toolbar, scrollbar, font/line-height controls, reading progress bar, action buttons, Q&A interaction overlays, toast notifications |
| `01b-floating-toc.css` | Floating TOC panel, TOC header, content area, items, tabs; dark-mode floating-TOC variants |
| `01c-bookmarks.css` | Bookmark list items, homepage bookmark groups, visual bookmark indicators, current-chapter info bar; dark-mode bookmark variants |
| `02-search-btn.css` | Search activation button styles (top and bottom) |
| `03-search.css` | Search panel, scope segmented control (`.search-scope` hidden by default; `.search-scope.is-visible` shows it), loading/progress/error/success states (incl. `.search-progress-bar.is-indeterminate` for unknown totals), search results, dark-mode search variants |
| `04a-toc-levels.css` | TOC level-display buttons, floating level panel, expand/collapse icons, TOC item hover, level-specific link colours, collapse animations |
| `04b-toc-dark.css` | Dark-mode overrides for all TOC, floating-TOC, and bookmark elements inside the TOC panel |
| `04c-qa-audio.css` | QA chapter styles: source banner, per-segment `qa-meta-bar` (number + `.qa-play` button + status badge), `qa-opening`, the bottom floating `qa-player` (seek row with `−5s`/progress/`+5s`, play/pause toggle, Bilibili-style volume control — speaker button that toggles a popup containing a vertical (rotated) range slider), loading states (`.qa-play.loading`, `.qa-play-icon--spinner`, `.qa-player.is-loading`, indeterminate progress pulse) with matching `body.dark-mode` overrides; dark-mode variants. Ordered before `05-responsive.css` so its `@media` overrides win. Responsive rules for these live in `05-responsive.css` |
| `04d-image-lightbox.css` | Content-image `cursor: zoom-in`; full-screen `.img-lightbox` overlay (toolbar, stage, transform-based zoom/pan); mobile tap targets and safe-area padding; `body.dark-mode` variants. Ordered before `05-responsive.css` |
| `05-responsive.css` | All `@media` breakpoints: screen-height toolbar positioning, search/TOC tablet (≤768px), floating-controls wide (≥800px), mobile (≤600px incl. QA player full-width), small-phone (≤400px) |

### Requirement: Single Output File
`StaticAssetsManager` SHALL concatenate all `modules/*.css` files (sorted by
name) to produce the single `style.css` copied to the ebook output.

#### Scenario: CSS concatenation
- GIVEN `assets/css/modules/` contains ordered `.css` module files
- WHEN `StaticAssetsManager.get_full_css_content()` is called
- THEN the returned string SHALL contain the content of every module file
  in ascending filename order

### Requirement: CSS Custom Properties
Base typography variables SHALL be defined in `:root` within `00-base.css`:
- `--line-height` (default `1.6`)

Components that use dynamic line-height MUST reference `var(--line-height)`.

### Requirement: Dark Mode
Dark mode overrides SHALL be implemented with the `body.dark-mode` selector.
Every component that has a light-mode appearance SHOULD have a corresponding
dark-mode override, avoiding the use of `!important` except where strictly
necessary for specificity.

### Requirement: Responsive Design
The CSS SHOULD define responsive breakpoints for at least `768px`, `600px`,
and `400px` viewport widths to support mobile reading.

## Technical Notes

- Source modules: `assets/css/modules/`
- Build step: `StaticAssetsManager.get_full_css_content()` in `templates/static_assets.py`
- Theme colours: primary pink `#e75480`, accent `#ff69b4`
- Design tokens are defined as CSS custom properties in `00-base.css` `:root` — always use `var(--color-primary)` etc. rather than raw hex values in new CSS
- All `@media` rules MUST live in `05-responsive.css`; component files contain no `@media` blocks
