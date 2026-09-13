# TaiGuangLin Site Redesign —「素瓷緋櫻」Design System v3.0

整站視覺系統規格。所有**非電子書**頁面（根目錄 `index.html`、`wenda2.html`、`stories.html`、
`infographic.html`、`mindmap.html`、`wenda2/chapter-*.html`、`stories/*.html`）共用
根目錄 `style.css`；故事閱讀頁再加 `stories/assets/story.css`。

> `ebook/` 與 `wenda2_ebook/` 各自使用 `assets/css/style.css`，**與本系統無關，不要動**。

目標感受：素瓷紙底、緋櫻為色、深梅為墨——安靜、克制、有文化氣質的粉，而不是甜膩少女粉。

---

## 1. 色彩（`style.css` `:root` 已定義）

| Token | 值 | 用途 |
|---|---|---|
| `--sakura-50` | #fdf6f9 | 最淡粉，區塊底 |
| `--sakura-100` | #fbeaf2 | 淡粉背景、chip 底 |
| `--sakura-200` | #f7d8e5 | 邊框、淡強調 |
| `--sakura-300` | #efbcd2 | 裝飾、指示點 |
| `--sakura-400` | #e79dbe | 中間粉、細線 |
| `--sakura-500` | #cf6b96 | **主粉紅** |
| `--sakura-600` | #b54d78 | 深粉、hover |
| `--sakura-700` | #953a60 | 深玫瑰文字 |
| `--sakura-800` | #732b49 | 標題強調 |
| `--sakura-900` | #541d35 | 深底上的粉字 |
| `--sakura-950` | #37121f | 最深 |
| `--paper` | #fdfafb | 全站底色（暖瓷白）；body 另加兩層極淡紙紋 |
| `--paper-tint` / `--paper-deep` | #f8eef2 / #f3e4ea | 淡底區塊 |
| `--surface` | #ffffff | 卡片面 |
| `--ink` | #33202a | 主文字（玫瑰墨） |
| `--ink-soft` | #5a414c | 次級文字 |
| `--ink-mute` | #8d7180 | 弱文字 |
| `--line` / `--line-deep` | #f0dde5 / #e3c4d3 | 細線 |
| `--gold` / `--gold-soft` | #b58a56 / #dcc39b | 點綴金（kicker 線、問答「答」、深底 cite，<5% 畫面） |
| `--grad-rose` | linear-gradient(120deg,#e79dbe,#cf6b96 55%,#a8406a) | 主按鈕／強調 |
| `--grad-petal` | linear-gradient(168deg,#fdf6f9,#f7e3ec,#f5dce7) | page-hero 淡底 |
| `--grad-ink` | linear-gradient(155deg,#3d1e2f,#24121c) | 法語帶（深梅墨） |
| `--sh-1/2/3` | 玫瑰調柔陰影 | 卡片／彈窗 |
| `--r-xs…xl` / `--r-pill` | 8/12/16/22/30/999px | 圓角（勿超過 30） |

**舊命名別名**：`--rose-*`、`--pink-*`、`--spacing-*`、`--radius-*`、`--shadow-*`、
`--primary-pink`、`--light-pink`、`--soft-pink`、`--pale-pink`、`--deep-pink`、
`--primary-color`、`--accent-color`、`--text-muted`、`--pink-gradient`、`--soft-gradient`
全部保留下來（指向新值），所以各頁行內樣式與舊元件不必改動。

語感：paper 為底、白卡、hairline 細線；深粉只用在文字與小面積強調；
**大面積粉紅只允許淡階（sakura-50~200）**；金色僅作細節。

## 2. 字體與排版
- 標題 `'Noto Serif TC'`（`--font-serif`）、內文 `'Noto Sans TC'`（`--font-sans` / `--font-primary`）。Google Fonts `<link>` 保留。
- `.display`（內頁大標）、`.hero-title`（首頁）、`.section-title`（區塊標題，置中，下緣 74px 漸層細線）、`.lede`、`.lead`、`.section-desc`。
- `.kicker` / `.section-kicker`：11.5px、字距 .38em、大寫英文＋左側金線（`.section-kicker::before` 已關閉）。
- 漸層字：`<span class="grad">…</span>`（套在 `.section-title` / `.display` / `.hero-title` 內）。
- `<div class="section-head">` = kicker + h2.section-title + p.section-desc（置中）。

## 3. 共用元件（style.css 已實作，勿重寫）
`.container`（1160）/`.container--narrow`、`.section`、`.section--tint`（＝`.section.alt`＝`.section.bg-light`，
上緣有花瓣波浪）、`.card`、`.chip`、`.pill-nav-wrap > .pill-nav > .chip`、`.crumbs`、
`.btn` + `.btn-primary` / `.btn-ghost` / `.btn-outline` / `.btn-light` / `.btn-sm`（結尾箭頭用 `<span class="arr">→</span>`）、
`.dharma-section > .dharma-content > blockquote.dharma-quote + cite.dharma-author`（深梅墨帶，上下花瓣邊；
同帶有第二段法語時，第二段加 `.dharma-verse`＝上方置中金線分隔、字距略放；`wenda2/chapter-*.html`
的 `.qa-quote` 同理用 `.q-verse`）、
`.footer`、`.reveal` / `.reveal-d1..d3`（`shared.js` 的 IntersectionObserver 會加 `.in`，尊重 `prefers-reduced-motion`）、
`.modal-overlay` / `.modal` / `.download-option`（首頁下載彈窗）、`.lightbox`（圖解頁）。

## 4. 導覽列與頁尾（所有頁面統一；`wenda2/`、`stories/` 內頁加 `../`）

```html
<nav class="navbar" id="navbar">
  <div class="nav-container">
    <a href="index.html" class="nav-logo">
      <span class="logo-name">TaiGuangLin</span>
      <span class="logo-sub">次世代終極佛法</span>
    </a>
    <div class="nav-menu" id="nav-menu">
      <a href="index.html" class="nav-link">首頁</a>              <!-- 目前頁加 class active -->
      <a href="index.html#about" class="nav-link">禪師</a>
      <a href="index.html#start" class="nav-link">入門路徑</a>
      <a href="index.html#books" class="nav-link">著作</a>
      <a href="wenda2.html" class="nav-link">問答錄 2</a>
      <a href="stories.html" class="nav-link">實修故事</a>
      <div class="nav-dropdown" id="nav-dropdown">
        <a href="#" class="nav-link nav-dropdown-toggle" id="dropdown-toggle">圖解 ▾</a>
        <div class="nav-dropdown-menu">
          <a href="infographic.html" class="nav-dropdown-item">名詞圖解</a>
          <a href="mindmap.html" class="nav-dropdown-item">名詞關聯心智圖</a>
        </div>
      </div>
      <a href="index.html#downloads" class="nav-link nav-cta" data-download-trigger>下載資料</a>
    </div>
    <button class="hamburger" id="hamburger" aria-label="開啟選單" aria-expanded="false">
      <span></span><span></span><span></span>
    </button>
  </div>
</nav>
<div class="site-menu-veil" id="site-menu-veil"></div>  <!-- shared.js 會在缺少時自動補上 -->
```

- 導覽列是**浮動膠囊**（`.nav-container` 圓角＋毛玻璃）；`.navbar.scrolled` 加深。
- 蓮花印記由 `.nav-logo::before` 以 CSS 繪製 → 所有頁面一致，**不必在 HTML 放 logo SVG**。
- 最後一個指向 `#downloads` 的連結會自動得到 CTA 樣式（`.nav-link.nav-cta` 或 `a[href$="#downloads"]`）。
- 舊頁面留著的 `<div class="nav-logo">`、`下載`（無 `nav-cta`）也能正確顯示，不必逐頁改。

```html
<footer class="footer">
  <div class="container">
    <div class="footer-top">
      <div class="footer-brand"><div class="logo-name">TaiGuangLin</div><p>次世代終極版佛法</p><p>用現代通俗易懂的語言，傳承純正佛法智慧。</p></div>
      <div class="footer-col"><h4>著作與電子書</h4><ul>…</ul></div>
      <div class="footer-col"><h4>問答錄 2</h4><ul>…</ul></div>
      <div class="footer-col"><h4>更多資源</h4><ul>…</ul></div>
    </div>
    <div class="footer-bottom"><p>歡迎分享給更多人結法緣</p><p>願一切眾生離苦得樂，早證菩提</p></div>
  </div>
</footer>
<script src="shared.js" defer></script>
```

- 頁尾為**淺瓷底**（不是深色）；深色只留給法語帶。舊的 `footer-content` / `footer-section`
  結構（`tool/stories2html` 產出的故事頁）亦有對應樣式。

## 5. 頁首與動效
- 內頁：`section.page-hero`（淡粉漸層＋圓相水印）＋ `.crumbs` ＋ `.kicker` ＋ `h1.display` ＋ `p.lede`。
- 首頁：`.hero`（`hero-copy` / `hero-art`）＋ `images/hero-lotus.svg`（圓相中的禪坐身影與蓮花）。
  「每日精選」卡片（`.daily-quote`）以負 margin 疊在 hero 下緣。
- 頁首裝飾細線用 `images/lotus-divider.svg`（`divider-mark`）。
- 著作／電子書卡片封面用 `images/合集.svg`（九本並列的書脊＋蓮花印記）。
- **動效**：網頁層只保留 `.reveal` 淡入與 :hover 微抬（禁止版面層的持續動畫）。
  唯一例外是 hero 插圖本身：`images/hero-lotus.svg` 在檔案內用 CSS `@keyframes` 做極輕微的
  動畫（圓相一筆畫出、蓮座綻放、身姿微浮、光暈呼吸、花瓣慢落、細點環極慢旋轉）。
  該檔以 `<img>` 載入，動畫必須**自成一體**（只准用檔內 `<style>`，不得依賴外部 CSS/JS），
  且務必在檔內以 `@media (prefers-reduced-motion: reduce)` 全部停用，並讓「基線狀態」
  就是完整靜態畫面（動畫只是加分，關掉也完全不缺角）。
  撰寫時注意：CSS transform 會蓋掉 `transform` 屬性，被定位的元素要先 `translate(...)` 到外層 `<g>`，
  要動的 `<g>` 自己不要帶 `transform` 屬性。

## 5b. 音檔串流頁（`/audio/`，獨立部署，不在本 repo）

`audio/` 是連到音檔庫的 symlink（未進 git），該頁自帶一整套行內 CSS/JS，**不載入本 repo 的
`style.css` / `shared.js`**，但色票與版面語彙刻意沿用本系統（同 `--sakura-*`、同紙底與浮動膠囊感）。

- 產生器：`tool/audio_index/build_index.py`（掃描 `*.opus` → 填 `CATEGORIES` / `FILES` → 寫出
  `audio/index.html`）。**改版面一律改樣板 `tool/audio_index/index_template.html`，不要改產物。**
- 版面順序：置頂**大悲咒播放器**（西方三聖圖可點擊播放／暫停、模式分段鈕、進度與音量）→
  黏頂工具列（類別＋搜尋＋新舊排序）→ 年份快篩＋統計 → 依類別／年月分組的清單 → 底部「正在播放」條。
- UX 重點：檔名拆成「日期標籤＋標題」（去掉 `YYYY年M月D日` 與 `.opus`）、426 筆可用年份快篩、
  空結果提供「清除全部篩選」、捲過大悲咒後右下出現回頂快捷鈕、`prefers-reduced-motion` 一併關閉過場。
- 播放器行為（關螢幕循環、Media Session、Opus 尾端 duration 膨脹）都在樣板內的 `dabeiPlayer`，
  修改時請保留既有 id 與「雙 `audio` 元素接力」的作法。

## 6. 內容與流程守則
- 保留 SEO meta、canonical、og 標籤；保留所有功能連結（電子書、`stories/*.html`、
  `wenda2/chapter-*.html`、語音、下載網盤）。
- `infographic.html` 與 `mindmap.html` 必顯示
  `本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。`（樣式用 `.note-ai`）。
- 文案可重寫，資訊架構不變；圖示用簡潔 inline SVG（線條風），**不用 emoji**。
- `stories.html` 的清單區塊由 `tool/stories2html/build_index.py` 產生（保留
  `<!-- STORIES-LIST:BEGIN/END -->` 標記與 `st-*` class）；故事閱讀頁（`stories/*.html`）
  由 `tool/stories2html/build.py` 產生（`stories/assets/story.css` + `story.js`）。
