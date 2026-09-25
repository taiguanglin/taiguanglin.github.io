# site_chrome

全站共用導覽、圖解頁 SEO 結構化資料的 **build-time 同步工具**，以及站台一致性檢查。

網站仍輸出完整 HTML，不靠 JavaScript 注入，所以無 JavaScript 使用者與搜尋引擎都能讀到導覽連結。

## 為什麼需要它

`「圖解」下拉選單` 原本逐頁手工複製，散落在 root 頁、`wenda2/` 章節頁、`stories/` 故事頁與多個生成器模板中；
改一次導覽要同步幾十處，很容易漂移成不一致。
現在選單只由 `sync.py` 定義一次，再由它寫回所有頁面。

## 指令

```bash
# 將共用導覽／SEO 結構化資料寫回所有頁面
python3 tool/site_chrome/sync.py

# 只驗證，不寫檔（CI 或提交前用）
python3 tool/site_chrome/sync.py --check

# 站台一致性總檢查（含上述 --check）
python3 tool/site_chrome/check_site.py

# 「圖解」下拉互動測試（滑鼠／鍵盤／點外關閉；不依賴 jsdom）
node tool/site_chrome/dropdown_harness.js
# 不帶參數測 4 個代表頁；帶參數可測任意頁面
node tool/site_chrome/dropdown_harness.js index.html wenda2/chapter-01.html
```

### dropdown_harness.js 在做什麼

它從**真實頁面**抽出 dropdown 的 HTML，用內建的極簡 DOM stub 解析成節點樹，再把 `shared.js`
裡那段 dropdown 程式碼**原封不動**抽出來執行，然後斷言：

- 初始 `aria-expanded="false"`、選單有 3 個入口
- 點 toggle 展開／再點收合，`aria-expanded` 同步
- `ArrowDown` 展開並把焦點移到第一個連結
- `Escape` 收合並把焦點交回 toggle
- 點擊選單外部會收合、點擊選單內部不會誤收

因為它吃的是實際輸出，所以生成器改版或手改頁面導致標記漂移時會直接失敗。

## 涵蓋頁面

`sync.py` 自動處理「含 `id="navbar"` 且載入 `shared.js`」的頁面：root `*.html`、`wenda2/*.html`、`stories/*.html`。

## 定義了什麼

| 內容 | 位置 |
|------|------|
| 「圖解」下拉 3 個入口（名詞圖解／坐禪與講經心智圖／問答錄2心智圖）、目前頁面高亮、相對路徑前綴 | `ITEMS` + `render()` |
| 圖解頁的 `WebPage`＋`BreadcrumbList` JSON-LD | `SEO_PAGES` + `sync_structured_data()` |
| 站台不變量（AI 免責聲明、canonical、連結與錨點、sitemap、圖片屬性、`b-truth` 三節點…） | `check_site.py` |

## 生成器整合

下列生成器寫檔後會自動呼叫 `sync.py`，重建後不必手動補導覽：

- `tool/session_knowledge/build.py`
- `tool/wenda2_curation/build/build_mm2.py`
- `tool/stories2html/build.py`（整批故事頁寫完後同步一次）

新增其他會產生「共用 chrome」頁面的生成器時，請比照辦理。

## 編輯慣例

- **不要手改頁面裡的導覽區塊**：會被 `sync.py` 覆蓋。要改選單就改 `ITEMS`，再重跑。
- SEO 結構化資料由 `<!-- STRUCTURED-DATA:START -->` / `:END -->` 標記包住，由 `sync.py` 冪等重建，可安全重複執行。
- 手機版滑入面板中，「圖解」toggle 只開合子選單、不收起整個面板（`shared.js` 的 `closeMenu` 迴圈排除 `.nav-dropdown-toggle`），桌機與手機行為一致。
- 舊的知識頁（`wenda2_knowledge*.html`、`books_knowledge*.html`）與其生成器、語料已於 2026-09 全數移除；「圖解」僅保留三個入口。
- `review.html`（名詞複習）已於 2026-09 移除，相關 CSS（`.rv-*`）與 `rv_harness.js` 一併刪除。
