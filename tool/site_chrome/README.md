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

# lang-switch.js 跨語系轉址（含首頁「前往原文」的錨點保留；不依賴 jsdom）
node tool/site_chrome/lang_switch_harness.js
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

### lang_switch_harness.js 在做什麼

用 Node 的 `vm` 跑**真正的 `lang-switch.js`**，只替掉它會碰到的少數全域
（`location` / `localStorage` / `sessionStorage` / `navigator` / `document`），斷言
跨語系轉址的行為。守住一條重要不變量：

> **繁簡雙頁的段落 id 必須完全相同**，且跨語系轉址時**必須把 `location.hash`
> 一起帶過去**。

首頁「每日精選」的「前往原文」永遠連到 `ebook/…_trad.html#p-xxx`（語料是繁體）。
偏好簡體的讀者會被轉到簡體頁；舊版轉址只帶 `location.search`、漏掉 hash，再加上
`lang-switch.js` 是 `defer`、執行時瀏覽器通常還沒套用片段捲動（`scrollY` 仍是 0），
算出的「最近標題」會是整本書的目錄 —— 於是「跳到該段」變成「跳到書的開頭」。

改 `books2ebook`／`word2ebook` 的 id 產生方式時（例如改成用轉換後文字做雜湊），
這個 harness 與下面 `audit_quotes.py` 的連結檢查都會失效：
`wenda2_ebook` 已經有 `content-*` 這類「隨繁簡文字變動」的 id，
`daily_quotes.json` 引用的 `p-*`／`answer-*` 則必須跨語系穩定。

## 涵蓋頁面

`sync.py` 自動處理「含 `id="navbar"` 且載入 `shared.js`」的頁面：root `*.html`、`wenda2/*.html`、`stories/*.html`。

## 定義了什麼

| 內容 | 位置 |
|------|------|
| 「圖解」下拉 3 個入口（名詞圖解／坐禪與講經心智圖／問答錄2心智圖）、目前頁面高亮、相對路徑前綴 | `ITEMS` + `render()` |
| 圖解頁的 `WebPage`＋`BreadcrumbList` JSON-LD | `SEO_PAGES` + `sync_structured_data()` |
| **`sitemap.xml` 全文（唯一 SoT）** | `sitemap.py`（見下） |
| **IndexNow 變更通知** | `indexnow.py`（見下） |
| 站台不變量（AI 免責聲明、canonical、連結與錨點、sitemap、圖片屬性、`b-truth` 三節點…） | `check_site.py` |

## `sitemap.py` — sitemap.xml 的唯一產生器（2026-10-28）

`sitemap.xml` 過去由 `tool/stories2html/build_index.py` 局部補丁拼湊，`lastmod`
停在 2026-10-10（內容卻在 10-27／10-28 更新過）。Google 官方說明 `<lastmod>`
**只有在持續且準確時才會被採用**，過期的 lastmod 反而會讓爬蟲降低重抓頻率。

現在 `sitemap.py` 是唯一 SoT：

```sh
python3 tool/site_chrome/sitemap.py            # 產生（寫回 repo 根 sitemap.xml）
python3 tool/site_chrome/sitemap.py --check    # 只檢查是否與產生器一致
```

- URL 來源：主要頁面（root `*.html`）＋ `wenda2/` 章節＋ 兩套電子書的**實質頁**
  （`wenda2_ebook/`、`ebook/`）。
- **帶 `noindex` 或 `meta refresh` 的頁面一律不收錄**（13–21 章跳轉頁因此不會
  出現在 sitemap）。
- `<lastmod>` 取 `git log -1 --format=%cs`（無 git 紀錄時退回檔案 mtime）——
  必須在版本控制下產物才準。
- **不輸出 `<priority>`／`<changefreq>`**：Google 明確忽略這兩個欄位，留著只會
  誤導人。
- 電子書重建後會自動重產 sitemap（`tool/books2ebook/gen_all.py` 與
  `tool/qa_split_ebook/gen_classified.py` 都會呼叫它）。

⚠️ **不要手改 `sitemap.xml`**——下次任何生成器執行都會覆蓋。要改收錄範圍請改
`sitemap.py`。

## `indexnow.py` — 變更通知（2026-10-28）

```sh
python3 tool/site_chrome/indexnow.py --changed   # 通知本次變更的 URL
python3 tool/site_chrome/indexnow.py --all       # 通知 sitemap 全部 URL
```

- 金鑰：環境變數 `INDEXNOW_KEY`，或 repo 根目錄 `indexnow-key.txt`（部署後即
  `https://taiguanglin.info/indexnow-key.txt`，符合 IndexNow 的驗證要求）。
- 每次最多 10,000 個 URL（協定上限）；送出失敗只回報、**不中斷建置流程**。
- `tool/word2ebook/gen_all_and_push.py` 與 `tool/books2ebook/gen_all_and_push.py`
  支援 `--indexnow`：URL 清單在 commit **前**抓（commit 後工作樹就乾淨了），
  通知在 push 成功後才送。

## 生成器整合

下列生成器寫檔後會自動呼叫 `sync.py`，重建後不必手動補導覽：

- `tool/stories2html/build.py`（整批故事頁寫完後同步一次）

新增其他會產生「共用 chrome」頁面的生成器時，請比照辦理。

## 編輯慣例

- **不要手改頁面裡的導覽區塊**：會被 `sync.py` 覆蓋。要改選單就改 `ITEMS`，再重跑。
- SEO 結構化資料由 `<!-- STRUCTURED-DATA:START -->` / `:END -->` 標記包住，由 `sync.py` 冪等重建，可安全重複執行。
- 手機版滑入面板中，「圖解」toggle 只開合子選單、不收起整個面板（`shared.js` 的 `closeMenu` 迴圈排除 `.nav-dropdown-toggle`），桌機與手機行為一致。
- `session_knowledge.html`（查證工程紀錄）連同 `SESSION_KNOWLEDGE.md`、`tool/session_knowledge/`（含 `mm_harness.js`）與 `.sk-*` CSS 已於 2026-09 徹底移除；`robots.txt`／`check_site.py` 的相關條目同步清掉。
- `review.html`（名詞複習）已於 2026-09 移除，相關 CSS（`.rv-*`）與 `rv_harness.js` 一併刪除。
