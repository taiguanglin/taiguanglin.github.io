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
| `04c-qa-audio.css` | QA chapter styles: source banner, per-segment `qa-meta-bar` (number + speaker-icon-only `.qa-play` button — no visible time label, the range living only in the mini-player's progress row — + status badge), `qa-opening`, the bottom floating `qa-player` (seek row with `−5s`/progress/`+5s`, play/pause toggle, Bilibili-style volume control — a pink SVG speaker icon (~3/4 emoji size, `fill: var(--color-primary)`, sound waves hidden and a slash shown when muted) whose popup (numeric 0–100 readout + vertical rotated range slider filled up to `--qa-volume-pct` with the primary colour) appears on hover; a `::before` bridge spans the 10px gap above the button so hovering from button to slider stays continuous), loading states (`.qa-play.loading`, `.qa-play-icon--spinner`, `.qa-player.is-loading`, indeterminate progress pulse) with matching `body.dark-mode` overrides (icon uses `#ff91af` in dark mode); dark-mode variants. Ordered before `05-responsive.css` so its `@media` overrides win. Responsive rules for these live in `05-responsive.css`. Also hosts 講經段落跟播 styles: `.para-track-toggle` (per-lecture follow-play text checkbox inserted next to `.qa-play`, `on` state = gradient fill), `body.para-track-on` (pointer cursor on playable `.para-block[data-start]`, synced with the toggle), `.para-block.para-active` (warm-glow background + inset left accent via `box-shadow` + `font-weight: 600`; no `transform: scale()` — scaling would widen the block and clip on narrow screens); the previous paragraph gets no visual change (no dimming), each with `body.dark-mode` variants. Also hosts 經文置頂（sutra pin）styles: `.sutra-pin-toggle` (shares the `.para-track-toggle` pill look via grouped selectors), `.sutra-pin-group` (plain in-flow wrapper bounding each sutra's sticky range: sutra → next sutra / heading / image; no padding/border/overflow so margins collapse through), `.sutra-pin-host` (`position: sticky; top: 0` — the sutra itself holds at the viewport top at full size with no clone and no added chrome, so size and background are pixel-identical and there is no white edge), `position: static` overrides for `.sutra-pin-group.sutra-pin-tall` (sutra taller than 45% of the viewport never sticks), `body.sutra-pin-off` (toggle off) and `body.sutra-pin-suppress` (anchor-jump protection) |
| `04d-image-lightbox.css` | Content-image `cursor: zoom-in`; full-screen `.img-lightbox` overlay (toolbar, stage, transform-based zoom/pan); mobile tap targets and safe-area padding; `body.dark-mode` variants. Ordered before `05-responsive.css` |
| `05-responsive.css` | All `@media` breakpoints: screen-height toolbar positioning, search/TOC tablet (≤768px), floating-controls wide (≥800px), mobile (≤600px incl. QA player full-width), small-phone (≤400px) |
| `06-ux-plus.css` | 2026-09 UX 改善元件（無 `@media`）：深色「墨夜」面板（`body.dark-neutral`，深灰＋暖金）、閱讀位置提示條、音檔續播膠囊、`.toc-count` 可點樣式、`.anchor-share` 錨點鈕、`mark.w2e-hl` 命中高亮、搜尋結果 `.kb-focus`、目錄 backdrop、`.no-audio-note`、目錄縮排導引線（`.toc ul ul` 虛線＋浮動目錄深層邊線）。**不含** `.w2e-backtop`（常駐回到頂端鈕已移除，只留功能選單內的 ↑）、**不含**任何 `.w2e-bm-*`（首頁總目錄底部的「我的書籤」管理區塊已移除） |

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

### Requirement: Initial Anchor Highlight
`.anchor-target-highlight` SHALL show a three-second red inset highlight that
remains visible over existing solid or gradient backgrounds, including
`.sutra-text`, and SHALL fade to transparent before it is removed.

### Requirement: Responsive Design
The CSS SHOULD define responsive breakpoints for at least `768px`, `600px`,
and `400px` viewport widths to support mobile reading.

## Technical Notes

- Source modules: `assets/css/modules/`
- Build step: `StaticAssetsManager.get_full_css_content()` in `templates/static_assets.py`
- Theme colours: primary pink `#e75480`, accent `#ff69b4`
- Design tokens are defined as CSS custom properties in `00-base.css` `:root` — always use `var(--color-primary)` etc. rather than raw hex values in new CSS
- All `@media` rules MUST live in `05-responsive.css`; component files contain no `@media` blocks

### Requirement: Print Styles
`05-responsive.css` SHALL include an `@media print` block that hides interactive
chrome (header/top nav, TOC controls, floating controls, toolbars, search UI,
QA audio UI, back-to-top, footers), forces `content-visibility: visible` on
content blocks (so long chapters print completely), uses physical white/black
for print, and adds `break-inside: avoid` on question/answer/qa-pair blocks.

### Requirement: Reduced Motion
`05-responsive.css` SHALL include an `@media (prefers-reduced-motion: reduce)`
block that reduces animation/transition durations to ~0 and disables smooth
scroll, while keeping state changes (theme, collapse) functional.

### Requirement: Content Visibility For Long Blocks
`00-base.css` SHALL apply `content-visibility: auto` with
`contain-intrinsic-size: auto 240px` to `.question`, `.answer`, `.para-block`,
and `article.qa-pair` so long chapters render without paying for offscreen
layout work; the print block MUST override it back to `visible`.

### Requirement: CJK Font Stack
`00-base.css` SHALL define `--font-sans` as a system CJK stack (PingFang TC /
Microsoft JhengHei / Noto Sans CJK with sensible fallbacks) for `body`;
no webfont fetch is introduced.

### Requirement: Dark Page Background Token
`00-base.css` SHALL define `--color-bg-page-dark` and apply it to both
`html.dark-mode` (set pre-paint by the inline head script) and `body.dark-mode`,
so the overscroll area matches the dark theme and the first paint is already
dark.

### Requirement: Nested TOC Visual Flatness
`04a-toc-levels.css` SHALL neutralize padding/margins on nested `#main-toc` /
`#chapter-toc` sub-lists (semantic nesting renders flat), and reset UA button
styling on `button.toc-expand-icon` (no background/border/padding, inherit font)
since the expand affordance changed from `<span>` to `<button>`.

