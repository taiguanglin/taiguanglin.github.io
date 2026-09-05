# TaiGuangLin Site Redesign —「絹本・粉韻」Design System v2.0

整站視覺系統規格。所有根目錄行銷頁（index、wenda2、stories、infographic、mindmap）與 `wenda2/` 十二章
必須以此為準。目標感受：高級、柔和、現代、有文化氣質的粉紅；不是廉價少女粉。

## 1. 色彩（CSS Custom Properties，style.css 已定義）

| Token | 值 | 用途 |
|---|---|---|
| `--rose-50` | #fbf2f5 | 最淡粉，區塊底 |
| `--rose-100` | #f8e7ec | 淡粉背景 |
| `--rose-200` | #f0d2dd | 淺粉容器、邊框 hover |
| `--rose-300` | #e5b3c5 | 裝飾線、淡強調 |
| `--rose-400` | #d689a6 | 強調粉 |
| `--rose-500` | #c45883 | **主粉紅**（CTA、重點） |
| `--rose-600` | #a63e6a | 深粉 hover、重點字 |
| `--rose-700` | #853058 | 深玫瑰文字 |
| `--rose-800` | #632445 | 暗玫瑰 |
| `--rose-900` | #43182f | 最深玫瑰墨 |
| `--paper` | #fcf8f7 | 全站底色（暖白帶粉） |
| `--porcelain` | #f6edec | 次級底（象牙粉，交替區塊） |
| `--surface` | #ffffff | 卡片面 |
| `--ink` | #36222c | 主文字（玫瑰墨） |
| `--ink-soft` | #5c4250 | 次級文字 |
| `--muted` | #967380 | 弱文字 |
| `--hairline` | #ecd9df | 細分線 |
| `--hairline-deep` | #dcc0cb | 稍深細線 |
| `--gold` | #b98c52 | 點綴金（少量！kicker 線、徽章、書籤帶） |
| `--gold-soft` | #d9b98a | 深底上的金字 |
| `--grad-rose` | linear-gradient(120deg,#e089ac,#c45883 55%,#a63e6a) | 主按鈕／強調漸層 |
| `--grad-petal` | linear-gradient(165deg,#fbf2f5,#f4dde5) | hero 淡底漸層 |
| `--grad-ink` | linear-gradient(160deg,#3c2433,#2a1522) | 深色區（quote band / footer） |
| `--shadow-xs/sm/md/lg` | 見 style.css | 玫瑰色調陰影 |
| `--r-sm/md/lg/pill` | 10/16/24/999px | 圓角（不要超過 24，禁止大圓球感） |

語感：paper 為底、白色卡片、hairline 細線分隔；深粉只用於文字與小面積強調；**大面積粉紅背景只允許淡階（rose-50~200）**；金色僅作為細節點綴（<5% 畫面）。

## 2. 字體
- 全文 `'Noto Serif TC'`（標題）與 `'Noto Sans TC'`（內文）。Google Fonts <link> 保留。
- Display：`.display`，serif 700，行高 1.22。其中用 `<em>` 或 `.accent` 可得到玫瑰漸層字。
- `.kicker`：12.5px、字距 .42em、大寫英文＋左側金線。每個 section 標頭模式：
```html
<div class="section-head">
  <span class="kicker">LOREM IPSUM</span>
  <h2>主標題 <em>漸層字</em></h2>
  <p>一行副標</p>
</div>
```
- 中文段章可用 `.zh-numeral`（壹、貳、參…）作裝飾編號。

## 3. 必用共用元件（style.css 已實作，勿重寫）
- `.container`（max 1160, padding 28）、`.container--narrow`
- `.section`、`.section--tint`、`.section-head`
- `.btn` + `.btn-primary` / `.btn-ghost` / `.btn-light`；按鈕結尾箭頭用 `<span class="arr">→</span>`
- `.card`、`.chip`
- `.quote-band > .inner > blockquote + cite`（深色法語帶；深色背景金色 cite）
- `.footer`（見下）
- `.reveal`（+`.reveal-d1/2/3` 延遲）— shared.js 的 IntersectionObserver 會加 `.in`

## 4. 導覽列與頁尾（所有頁面統一，逐字使用）

```html
<header class="navbar" id="navbar">
  <div class="nav-container">
    <a href="index.html" class="nav-logo"><!-- wenda2/*.html 用 ../index.html -->
      <span class="logo-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 4c2.2 2.2 3.2 4.6 3.2 6.8-2.1 1.3-4.3 1.3-6.4 0C8.8 8.6 9.8 6.2 12 4z"/>
          <path d="M4.5 12.5c1.8-.8 3.8-.7 5.2.6M19.5 12.5c-1.8-.8-3.8-.7-5.2.6"/>
          <path d="M5 16c1.8 1.6 4.2 2.4 7 2.4s5.2-.8 7-2.4"/>
        </svg>
      </span>
      <span class="logo-text">
        <span class="logo-name">TaiGuangLin</span>
        <span class="logo-sub">次世代終極佛法</span>
      </span>
    </a>
    <nav class="nav-menu" id="nav-menu" aria-label="主選單">
      <a class="nav-link" href="index.html">首頁</a>
      <a class="nav-link" href="wenda2.html">問答錄 2</a>
      <a class="nav-link" href="stories.html">實修故事</a>
      <a class="nav-link" href="infographic.html">名詞圖解</a>
      <a class="nav-link" href="mindmap.html">心智圖</a>
      <a class="nav-link nav-cta" href="#downloads" data-download-trigger>下載</a>
    </nav>
    <button class="hamburger" id="hamburger" aria-label="開啟選單"><span></span><span></span><span></span></button>
  </div>
</header>
```
- `wenda2/*.html`：所有相對路徑加 `../`；下載連結指向 `../index.html#downloads`。
- 目前在的頁面的對應 `.nav-link` 加 class `active`。

```html
<footer class="footer">
  <div class="container">
    <div class="footer-top">
      <div class="footer-brand">
        <div class="logo-name">TaiGuangLin</div>
        <span class="logo-sub">次世代終極佛法</span>
        <p>以現代淺白的語言，講解禪定實修與佛法深義。<br>願此妙法，利益一切尋求真理之人。</p>
      </div>
      <div class="footer-col">
        <h4>著作</h4>
        <ul>
          <li><a href="index.html#books">全部著作</a></li>
          <li><a href="wenda2.html">問答錄 2（十二主題）</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h4>資源</h4>
        <ul>
          <li><a href="stories.html">實修故事</a></li>
          <li><a href="infographic.html">名詞圖解</a></li>
          <li><a href="mindmap.html">名詞心智圖</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h4>下載</h4>
        <ul>
          <li><a href="index.html#downloads">電子書與語音</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <p>歡迎轉載流通，標明出處即可</p>
      <p>願一切眾生離苦得樂，早證菩提</p>
    </div>
  </div>
</footer>
<script src="shared.js" defer></script>  <!-- wenda2/ 用 ../shared.js -->
```

## 5. Hero / 頁首規範
- 全站頁首以 `.grad-petal` 淡粉為底，上方留白 >= nav-h；主標 `.display`、副標 `.lede`。
- index.html hero 右側放 `images/hero-lotus.svg`；`images/lotus-divider.svg` 可用於 section 分隔。
- 動效克制：僅 `.reveal` 淡入；禁止持續旋轉／漂浮的多餘動畫。

## 6. 內容守則
- 保留 SEO meta、canonical、og 標籤；title 可精修。
- 保留所有 functional 連結（電子書、stories/*.html、wenda2/chapter-*.html、微信、下載）。
- 文案可重寫，但資訊架構不變。
- 禁止 emoji-heavy 介面；圖示用簡潔 inline SVG（線條風、stroke 為主）。
