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
| `00-base.css` | `:root` variables, `body`, headings `h1–h4`, `p`, `img`, `a`, `hr`, `.toc`, `.question`, `.answer`, Q&A meta elements, dark-mode base |
| `01-ux.css` | Reading toolbar, scrollbar, font/line-height controls, reading progress bar, floating TOC, chapter/homepage bookmarks, action buttons, Q&A interaction overlays, toast notifications |
| `02-search-btn.css` | Search activation button styles (top and bottom) |
| `03-search.css` | Search panel, loading/progress/error/success states, search results, dark-mode search variants |
| `04-toc-controls.css` | TOC level-display buttons, expand/collapse icons, TOC animations, dark-mode TOC variants, responsive breakpoints |
| `05-responsive.css` | Screen-height media queries, final overrides |

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
