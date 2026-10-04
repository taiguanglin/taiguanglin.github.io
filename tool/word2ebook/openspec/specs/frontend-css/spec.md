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
| `00-base.css` | `:root` design tokens (colors, radii, shadows), `body`, headings `h1–h4` (em-based type scale), `p`, `img`, `a`, `hr`, `.toc`, `.question`, `.answer`, Q&A meta elements, dark-mode base. Also holds the long-text perf rule `.question, .answer, .para-block, article.qa-pair { content-visibility: auto; contain-intrinsic-size: auto 240px }` — ⚠️ `content-visibility: auto` implies **paint containment**, so any overlay positioned *outside* the block's box (`bottom: 100%`, negative `top`, …) is clipped away and can never be hovered or clicked; overlays on these blocks must stay inside the padding box. Its estimated heights also make the document height change during a scroll, so scroll targets computed once can land off-target (see the initial-anchor requirement in `frontend-js/spec.md`) |
| `01a-layout.css` | Reading toolbar, scrollbar, font/line-height controls, reading progress bar, action buttons, Q&A interaction overlays, toast notifications |
| `01b-floating-toc.css` | Floating TOC panel, TOC header, content area, items, tabs; dark-mode floating-TOC variants |
| `01c-bookmarks.css` | Bookmark list items, homepage bookmark groups, visual bookmark indicators, current-chapter info bar; dark-mode bookmark variants |
| `02-search-btn.css` | Search activation button styles (top and bottom) |
| `03-search.css` | Search panel, scope segmented control (`.search-scope` hidden by default; `.search-scope.is-visible` shows it), loading/progress/error/success states (incl. `.search-progress-bar.is-indeterminate` for unknown totals), search results, dark-mode search variants |
| `04a-toc-levels.css` | TOC level-display buttons, floating level panel, expand/collapse icons, TOC item hover, level-specific link colours, collapse animations |
| `04b-toc-dark.css` | Dark-mode overrides for all TOC, floating-TOC, and bookmark elements inside the TOC panel |
| `04c-qa-audio.css` | QA chapter styles: source banner, per-segment `qa-meta-bar` (number + speaker-icon-only `.qa-play` button — no visible time label, the range living only in the mini-player's progress row — + status badge), `qa-opening`, the bottom floating `qa-player` (seek row with `−5s`/progress/`+5s`, play/pause toggle, Bilibili-style volume control — a pink SVG speaker icon (~3/4 emoji size, `fill: var(--color-primary)`, sound waves hidden and a slash shown when muted) whose popup (numeric 0–100 readout + vertical rotated range slider filled up to `--qa-volume-pct` with the primary colour) appears on hover; a `::before` bridge spans the 10px gap above the button so hovering from button to slider stays continuous), loading states (`.qa-play.loading`, `.qa-play-icon--spinner`, `.qa-player.is-loading`, indeterminate progress pulse) with matching `body.dark-mode` overrides (icon uses `#ff91af` in dark mode); dark-mode variants. Ordered before `05-responsive.css` so its `@media` overrides win. Responsive rules for these live in `05-responsive.css`. Holds the ebook-only paragraph overlay contract (see the `books2ebook` copy of this module for the selectors themselves): the top-right `⋯` disclosure bubble and the bookmark mark sit **outside** the `.para-block` box (`bottom: 100%`), so they cover the tail of the *previous* paragraph rather than the paragraph under the cursor — and the text column is never narrowed to make room. Because `content-visibility: auto` on `.para-block` is paint containment (which would clip them away), `.para-block:hover, :focus-within, .bookmarked` set `content-visibility: visible` to lift it for that one block; a hovered block is necessarily already rendered, so `contain-intrinsic-size` never applies and the toggle cannot move the scroll position. The `.qa-actions::before` hit zone (44px left, 14px below the bubble) makes the 22px bubble forgiving to approach, and `.qa-btn { position: relative; z-index: 1 }` keeps the expanded buttons above it. Also hosts 講經段落跟播 styles: `.para-track-toggle` (per-lecture follow-play text checkbox inserted next to `.qa-play`, `on` state = gradient fill), `body.para-track-on` (pointer cursor on playable `.para-block[data-start]`, synced with the toggle), `.para-block.para-active` (warm-glow background + inset left accent via `box-shadow` + `font-weight: 600`; no `transform: scale()` — scaling would widen the block and clip on narrow screens); the previous paragraph gets no visual change (no dimming), each with `body.dark-mode` variants. Also hosts 經文置頂（sutra pin）styles: `.sutra-pin-toggle` (shares the `.para-track-toggle` pill look via grouped selectors), `.sutra-pin-group` (plain in-flow wrapper bounding each sutra's sticky range: sutra → next sutra / heading / image; no padding/border/overflow so margins collapse through), `.sutra-pin-host` (`position: sticky; top: 0` — the sutra itself holds at the viewport top at full size with no clone and no added chrome, so size and background are pixel-identical and there is no white edge), `position: static` overrides for `.sutra-pin-group.sutra-pin-tall` (sutra taller than 45% of the viewport never sticks), `body.sutra-pin-off` (toggle off) and `body.sutra-pin-suppress` (anchor-jump protection), plus `.sutra-pin-group { --w2e-pin-reserve: 0px }` with `.sutra-pin-group :is(.para-block, h1, h2, h3, h4, h5, h6, .label-heading) { scroll-margin-top: var(--w2e-pin-reserve) }` — 09c writes the pinned sutra's height + gap as an inline `--w2e-pin-reserve` per group, so every scroll that aligns a target to the viewport top (external `#fragment` navigation, in-page anchors, floating TOC, bookmarks, `.toc-count`) leaves the target below the pinned sutra; the value is 0 on pages without sutra pinning, so behaviour there is unchanged |
| `04d-image-lightbox.css` | Content-image `cursor: zoom-in`; full-screen `.img-lightbox` overlay (toolbar, stage, transform-based zoom/pan); mobile tap targets and safe-area padding; `body.dark-mode` variants. Ordered before `05-responsive.css` |
| `05-responsive.css` | All `@media` breakpoints: screen-height toolbar positioning, search/TOC tablet (≤768px), floating-controls wide (≥800px), mobile (≤600px incl. QA player full-width), small-phone (≤400px). Line-height and heading sizes are deliberately **not** overridden here — see "CSS Custom Properties" and "Type Scale Follows the Reading Font Size" |
| `06-ux-plus.css` | 2026-09 UX 改善元件（無 `@media`）：深色「墨夜」面板（`body.dark-neutral`，深灰＋暖金）、閱讀位置提示條、音檔續播膠囊、`.toc-count` 可點樣式、`.anchor-share` 錨點鈕、`mark.w2e-hl` 命中高亮、搜尋結果 `.kb-focus`、目錄 backdrop、目錄縮排導引線（`.toc ul ul` 虛線＋浮動目錄深層邊線）。**不含** `.w2e-backtop`（常駐回到頂端鈕已移除，只留功能選單內的 ↑）、**不含**任何 `.w2e-bm-*`（首頁總目錄底部的「我的書籤」管理區塊已移除） |

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

No `@media` block MAY re-declare `line-height` on `body` (or on any element whose
line-height comes from `--line-height`) with a literal value. A media query has
the same specificity as the base rule but wins on source order because
`05-responsive.css` is concatenated after `00-base.css`, so a literal there
silently overrides the value the reading settings write to `--line-height` and
the 緊密／正常／寬鬆 buttons stop working on that viewport.

#### Scenario: Line-height buttons on a tablet
- GIVEN a viewport of 700px and a `--line-height` written by the reading settings
- WHEN the user presses the 寬鬆 (2.0) button
- THEN the body line-height SHALL become 2.0
- AND it SHALL stay 2.0 at 400px-wide viewports as well

### Requirement: Type Scale Follows the Reading Font Size
`h1`–`h4`, `.questioner`, `.answerer`, `.question-time` and (for `ebook/`,
`books.css`) `.answer-time`, `.label-heading` SHALL be sized in `em` so they
scale with the body size the reading settings write to `body`. The heading
ratios SHALL be `1.6 / 1.3 / 1.15 / 1.0` — slightly tighter than the browser
defaults of `2 / 1.5 / 1.17 / 1`, because a 2em `h1` on a phone leaves barely
ten characters per line.

No `@media` block MAY re-declare a heading `font-size` in `px`. Pinning them
per breakpoint decouples the hierarchy from the reading size: with the default
body raised to 19px on tablets, a pinned 22px `h2` collapses the h2-to-body
ratio from 1.29 to 1.16 and the page loses its heading structure.

#### Scenario: Raising the font raises the headings with it
- GIVEN a tablet body font size of 19px
- WHEN the heading scale is computed
- THEN `h2` SHALL be `1.3em` (≈25px), not a fixed 22px

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

### Requirement: Body Font Size And Width Come From Pre-Paint Variables
`00-base.css`'s `body` rule SHALL take `font-size` and `max-width` from
`var(--w2e-font-size, 16px)` and `var(--w2e-content-width, 800px)`, written by
`reading-prepaint.js` on `<html>` before first paint; the fallbacks SHALL keep
the previous no-JS rendering. `body` SHALL NOT be sized via inline style,
because `<body>` does not exist yet when the pre-paint script runs.

### Requirement: Equal-Specificity Important Declarations Are Order-Sensitive
`04a-toc-levels.css` pins `.toc { line-height: 1.4 !important }` and
`.toc > ul > li { line-height: 1.4 !important }` (fixed leading, immune to
the global line-height control). `reading-prepaint.js` injects the same
selectors at `line-height: 1.6 !important` for the reading setting. These
have identical specificity, so **source order decides**. Any stylesheet or
`<style>` injected at the same level SHALL be inserted after `style.css`, or
the TOC row leading silently changes when the setting is re-applied.

### Requirement: TOC Item Layout Must Not Depend on JS
`.toc-item:not(.toc-expandable) { display: flex }` styles leaf TOC rows, so
`.toc-expandable` is load-bearing for layout, not decoration. The generators
SHALL emit it server-side on every `<li>` that has a child `<ul>` (see the
"Server-Rendered TOC Initial State" requirement in `html-generation/spec.md`).
`.toc-expandable` SHALL NOT be introduced or removed by JavaScript in a way that
changes an item's layout before first paint, and JS `initializeTocExpandableItems()`
only re-asserts the already-correct class.

