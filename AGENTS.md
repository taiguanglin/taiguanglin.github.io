# taiguanglin.github.io — Agent / LLM Guide

> Read this first for **repo-wide** structure and conventions.  
> Tool-specific details live next to each tool (e.g. `tool/word2ebook/AGENTS.md`).  
> Prefer updating this file (or a tool’s `AGENTS.md`) over adding `.cursor/rules/*.mdc`.

---

## What this repo is

Static **GitHub Pages** site for TaiGuangLin (`taiguanglin.info` via `CNAME`).  
Deploy = push to `main` (no CI build step). Site chrome for marketing pages is Traditional Chinese (`zh-TW`).

---

## Golden rules

1. **Know source vs output** before editing. If a path is generated, change the generator / source, then rebuild.
2. **Never implement ebook features by editing `wenda2_ebook/`** — change `tool/word2ebook/`, then run the three-stage rebuild（`gen_all.py` → `tool/qa_split_ebook/extract.py` → `gen_classified.py`；一鍵版 `gen_all_and_push.py`，見「Main data flows」）. Same for play buttons: edit maps / injectors, not chapter HTML.
3. **`wenda2/` is not ebook output** — hand-maintained 12-chapter TOC pages; regenerating the ebook does **not** update `wenda2/`.
4. **`audio` is a local symlink** (`/Users/paul/tai/audio`), gitignored — never commit audio blobs here.
5. **Do not confuse site chrome with ebook assets** — root `shared.js` / `style.css` ≠ `wenda2_ebook/assets/` (built from `tool/word2ebook/assets/`). Root `script.js` was retired (superseded by `shared.js`); only the ebook bundles keep an `assets/js/script.js`.
6. **Internal editors** (`/audio_map/`, `/audio_map2/`) are editorial UIs.
7. **AI-generated content disclaimer** — `infographic.html`, `mindmap.html` and `wenda2_mindmap.html` must all display `本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。` Do not remove it when editing these pages.
8. **Shared chrome CSS lives in root `style.css`** — `index.html`'s embedded `<style>` is page-local. Any class reused by other root pages (nav `logo-name`/`logo-sub`, `footer-top`, `dharma-section`, …) must also have rules in `style.css`, or those pages break. Note `:not(.x)` cannot test for a *child* `.x` — use `:not(:has(.x))`.
9. **`mindmap.html`「三大初始設定」永遠只有三條** — 主幹 `b-truth` 固定為三個葉節點：`axiom-eternal`（自性恆常）、`axiom-firstthought`（初妄無因）、`axiom-onebody`（諸佛同體）。這是內容鐵律：**不可**在此主幹新增任何其他條目，也不可把其他節點移入。其他主題（如七處徵心、十番顯見等《楞嚴經》內容）一律屬「經典依據」主幹 `b-sutra`。若發現 `b-truth` 出現第 4 個葉節點，即為錯誤，必須移出。
10. **內部頁不得被索引** — `audio_map*/index.html`（含 GitHub PAT 輸入欄位的校稿工具）部署於公開 Pages，但一律不得被搜尋引擎索引。三條件缺一不可，由 `tool/site_chrome/check_site.py` 自動守門：
    - 頁面自帶 `<meta name="robots" content="noindex, nofollow, noarchive">`
    - **不得**出現在 `sitemap.xml`
    - `robots.txt` 對 `/audio_map/`、`/audio_map2/`、`/audio_map3/` 有 `Disallow`

    **`hidden/`（四本複習電子書＋入口頁）與其兩套產生器
    （`tool/wenda2_knowledge/`、`tool/ebook_knowledge/`）已於 2026-10-11 全數移除**
    （hidden/ 下線＝commit `15bbfd7`）：舊網址直接 404，`robots.txt` 的
    `Disallow: /hidden/` 與 `check_site.py` 的 hidden 相關登錄已同步清除。
    產生器連同內容 SoT（`src/*.py`）一併刪除——git 歷史（`3c40066` 及更早）可完整
    回溯。若要重新上線：先從歷史還原產生器與語料管線，重建後恢復 noindex／
    不列 sitemap／robots Disallow 三重守門，並維持「不掛全站導覽、
    `EBOOK_DIRS` 不含 `/hidden/`」的既有隔離。

    ⚠️ `session_knowledge.html`（查證工程紀錄）已於 2026-09 徹底移除，連同 `SESSION_KNOWLEDGE.md`、`tool/session_knowledge/`（含 `mm_harness.js`）與 `style.css` 的 `.sk-*` 區段；不要重新引入。
    ⚠️ `robots.txt` 不是存取控制，`audio_map*` 的 PAT 輸入仍無保護——真正的修法是把工具移出公開 repo。

11. **頁面顯示用圖片一律 WebP** — 全站圖片格式的 SoT 是 `tool/word2ebook/utils/image_markup.py`（`encode_webp` / `webp_dimensions`），`word2ebook`、`books2ebook`、`stories2html` 三個生成器皆引用它，品質一律 `WEBP_QUALITY`(85)。新增圖片產出時請走同一條路徑，不要再落地 PNG/JPEG。**兩個例外必須維持 PNG**：`images/taiguanglin.png`（`og:image`，社群 crawler 不支援 WebP）與 `images/buddha.png`（`manifest.webmanifest` 的 PWA icon）——`index.html` 的 `<img>` 改用另出的 `images/buddha.webp`，manifest 仍指 PNG。
12. **兩套電子書的初始畫面必須由伺服器端渲染完成（不得留給 JS）** — `wenda2_ebook/` 與 `ebook/` 的目錄（TOC）在 `script.js` 到位前就會被繪製，因此 HTML 必須自帶正確的初始狀態，否則使用者會先看到亂版畫面：
    - **`.toc-expandable` 是版面關鍵 class，不是裝飾** — `04a-toc-levels.css` 用 `.toc-item:not(.toc-expandable){display:flex}` 排葉節點。過去此 class 只由 JS 的 `initializeTocExpandableItems()` 補上，JS 未執行時全部 `<li>` 命中 `:not()`，巢狀 `<ul>` 被拉成 flex 兄弟而**橫向並排成多欄**——這就是「CSS/JS 沒載入完時目錄排列很怪」的真正根因（不是 CSS 慢）。故 `toc_generator.py` / `books2ebook/html_generator.py` 必須在有子 `<ul>` 時就輸出它。
    - **顯示層級與展開鈕也要預先輸出** — 依預設層級（首頁 2 層／章節頁 3 層）預先加上 `.hidden`、並把該層展開鈕輸出為 `▶`＋`aria-expanded="false"`，與 JS `setTocDisplayLevel()` 同規則。JS 之後只負責套用 `localStorage` 偏好。
    - **兩邊的層級解析必須一致** — `DEFAULT_TOC_LEVEL_INDEX`/`DEFAULT_TOC_LEVEL_CHAPTER`（`toc_generator.py`）、`resolve_display_level()` 與 JS 的 `defaultLevel` / `selectValidLevel()` 必須同規則（無該層時取**最近**層、同距離取較小者），章節頁 `.toc-level-btn.active` 也要標在解析後的層級（`I18nTemplateManager.build_level_buttons()`），否則 JS 啟動時按鈕高亮會跳動。
    - **不要用「載入中」轉圈圈蓋住這個問題** — 轉圈圈期間內容仍是亂的（只是被蓋住），還延後了可讀時間。改用漸進增强後關 JS 也能正常閱讀，爬蟲與無 JS 使用者一併受益。
    - **閱讀設定（字級／行距／內容寬度）同樣必須首繪前套用** — 過去由 `03d` 在 `DOMContentLoaded` 才寫 `body` 的 inline style，章節頁會先以 16px／800px 畫出來、再跳到 20px／834px（實測 CLS≈0.005、目錄縮排位移 17px）。引擎已搬到位於 `tool/word2ebook/assets/js/reading-prepaint.js` 的 **standalone** 檔（兩套電子書共用，暴露 `window.W2EReading`），模板以**同步 `<script src>`（不可 defer）** 引用。
    - ⚠️ **必須排在「最後一個 stylesheet 之後」** — 它注入的動態 TOC 樣式與 `04a-toc-levels.css` 的 `.toc > ul > li { line-height: 1.4 !important }` **權重相同且都帶 `!important`**（動態樣式給 1.6），勝負由**來源順序**決定。插在樣式表之前會讓 `03d` 重套時行距改變、整個目錄位移（li 30.8px→35.2px）。
    - 因為此時 `<body>` 還不存在，只能寫 `<html>` 的 CSS 自訂屬性（`--w2e-font-size` / `--w2e-content-width` / `--line-height`），由 `00-base.css` 的 `body` 規則消費。
    - 章節頁的層級按鈕只渲染「該章確實有標題」的層級（對應 JS `detectAndHideLevelButtons()`），否則控制列會在 JS 隱藏按鈕後縮短而位移。
    - 驗證方式：`tests/test_html_generator.py::TestTOCInitialState`（TOC 初始狀態）＋ `tests/test_static_assets.py` 的 `test_prepaint_js_*` / `test_03d_delegates_to_shared_reading_engine`（pre-paint 套用、樣式表順序、03d 不得留第二份引擎）。
13. **講經「段落跟播」是讀者便利功能，已校對講次必須真的出現在 `ebook/` 頁面上** — 整條鏈任一環壞掉都**不會報錯**，讀者只會看到「某幾段／某幾講沒有跟播」。三個必守的不變量（`tool/books2ebook/tests/test_follow_along_build.py` 逐條驗收）：
    - **pid 是段落文字雜湊**（`p-` + `md5(文字 + 段序)`，`html_generator.slug_id`）。改動段落文字的正規化（空白掃描、標點、繁簡…）→ pid 換掉 → 已校對的 `start/end` 掛到不存在的元素上，**該段靜默失去跟播**（注入器只是查不到、不報錯）。修：`python3 tool/books2ebook/sync_para_pids.py --apply`（只改 `pid`/`text`）→ 重建 `ebook/`。`2251ec4` 曾讓四十二章 10 個 confirmed 段失效。
    - **`reviewed=true` 是唯一開關**（`para_audio_map.py`；`end<=start` 或 `zero:true` 的段落依設計不注入）。所以「校稿 UI 勾完 → 必須重建 `ebook/` 才生效」；`audio_map3/*.json` 與 `ebook/*.html` 不得手改後直接 commit。
    - **前端要以文件順序收集段落**：`09b-para-track.js` 用 `createTreeWalker(document.body)`，因 09c 經文置頂的 `.sutra-pin-group` 讓經文之後的段落變成 h2 的**孫節點**；改回「h2 直接兄弟節點」會讓四十二章 L2 之後整講認不到。驗收指令：`cd tool/books2ebook && ../../tool/word_audio_map2/.venv/bin/python -m pytest tests/`（缺 `ebook/` 產物會 skip），配套 `cd tool/word2ebook && ../../tool/word_audio_map2/.venv/bin/python -m pytest tests/`。
14. **「經文」必須真的以經文區塊輸出（`.sutra-text`），且改經文判定盡量不要改動區塊切分** — 經文區塊承載三件事：講經書的「經文置頂」（`09c-sutra-pin.js` 的 sticky）、經文樣式（楷體／漸層背景）、搜尋錨點與每日精選的經文防線（`scripture_filter.py` 防線 A），全部只對 `.sutra-text` 生效。書裡的經文有兩種排法：**原經文**（楷體／宋體大字獨立成段）與**「解析」裡重引的經文條目**（**粗體**、**前面帶數字編號**，例：「3．闻是章句乃至一念生净信者…」「1. 一切障碍即究竟觉。」）。後者若留成一般粗體段落，以上三者對它**完全失效**。故 `tool/books2ebook/parsers.py` 必須把兩者都判為 `quote`（經文區塊）：
    - 講經系列（04 卷首／07 四十二章／08 楞伽／09 六祖壇經／10 楞嚴）＝**楷體字型**即經文。
    - 《金剛經 心經》（書 05）、《圓覺經》（書 06）＝**由成書 PDF 轉換而來**，除原經文外還有粗體／帶編號的重引條目；判準是「命中全書經文語料的 n-gram 重疊比 ≥ 0.7」（`parsers._SUTRA_MIN_RATIO`）——門檻 0.6 會把「引用經文 ＋ 老師自己的話」誤判成經文（例：圓覺經「即离，不作方便…佛已然答复，菩萨修行」）。《圓覺經》另有「編號（一般字型）＋經文（粗體）」的混排行，靠「**粗體位於行尾**」與名相注釋（「粗體詞頭 ＋ 一般字型說明」）區分開。
    - ⚠️ **成書 PDF 轉檔的兩本（金剛經 心經／圓覺經）不提供「經文置頂」**（`BookConfig(sutra_pin=False)`）：置頂是為「段落中有獨立經文區塊＋隨段跟播」的講經書設計的閱讀輔助，成書轉檔的排版不適用。這兩本書：建置期不輸出 `.sutra-pin-group`/`.sutra-pin-host` 包層、頁面 `<body>` 帶 `no-sutra-pin`（09c 見到即整頁跳過，**連 runtime 後備包法也不做**——否則省下的包層會在瀏覽器裡被補回來）、沒有「經文置頂」toggle。經文區塊本身照常輸出，id/pid 不變。
    - ⚠️ **盡量只改「區塊種類」，不要改「區塊數／區塊文字」**：pid 是 `md5(段落文字 + 段序)`（見規則 13），區塊數一變全書後續段落的 pid 全變 → 已校對的跟播段落靜默失效、`search_index` 與 `daily_quotes.json` 的連結全斷。真的必須改區塊切分時（如修訂原檔 PDF），改完務必重跑 `tool/daily_quotes/` 的三支管線並用 `refresh_sample.py` 對齊樣本。守門：`tool/books2ebook/tests/test_sutra_markup.py`。
    - ⚠️ **連續的經文段落必須共用同一個 `.sutra-pin-host`**（僅講經系列；成書轉檔兩書無包層）：原書常把一段經文縮排切成數段（《圓覺經》每章 2–12 段、《六祖壇經》最多 16 段）。若每段各開一個 host，sticky 的活動範圍只剩經文自身高度 → **等於沒有置頂效果**。故 `html_generator.render_chapter` 把連續經文收進同一個 host，`09c-sutra-pin.js` 的量測（過長判定＋`--w2e-pin-reserve`）也須量 **host 整體高度**並對 host 清單去重。
    - ⚠️ **例外：章首「全文經文」絕不置頂**（2026-12 修正）：《四十二章經》每章開頭先用楷體排一次該章**完整經文**（文字以章標題開頭，例：「第十五章请问力明」＋全章經文）。它是章首引文、不是正在講解的經文段——若依上面的「連續經文共用 host」規則與緊接的第一句重引經文併進同一 host（第 2/3/5/15/16/31 章），置頂時「全文＋第一句」會一起停在視窗頂；即使自成一 host，章首講解捲動時整段全文也會停留。故 `html_generator._is_chapter_full_text()`（文字以最近一個標題開頭）判定的章首全文經文**不包 host/group**、另加 `.sutra-full` 標記，`09c-sutra-pin.js` 的經文清單以 `:not(.sutra-full)` 排除（runtime 後備包法同樣不包它）。只有講解中逐句重引的經文段置頂。id/pid 不變（搜尋錨點、跟播、每日精選經文防線不受影響）。守門：`tool/books2ebook/tests/test_sutra_pin_wrappers.py`（合成渲染）＋ `test_sutra_markup.py`（建置產物）。
    - 《金剛經 心經》《圓覺經》的「解析」把經文條目排成「編號（一般字型）＋經文（粗體）」，會讓條目與後面的講解黏成同一段 → 該條沒有經文區塊（樣式／錨點／防線全失效）。2026-10 已用一次性工具（`fix_yuanjue_sutra_numbers.py`，工具本身已移除、git 歷史可回溯）**修訂原檔 PDF**（編號改成與經文同粗體；文字逐字不變）。 改動經文判定（或原檔）後，務必重跑 `tool/daily_quotes/` 的 `build_quotes.py` → `select_1095.py` → `audit_quotes.py`（經文錨點與 pid 變了，候選池與成品都會變；`candidates_sample.json` 的 url 也要用 `refresh_sample.py` 對齊）。

15. **搜尋引擎最佳化（SEO）的單一真相來源** — 電子書頁面「檔案很大」**不是**被索引的障礙（Google 未公布 HTML 大小上限；50 MB／50,000 URL 是 **sitemap** 的限制）。真正會讓公開搜尋結果停在舊版的，是下列四件事，都由產生器負責、不得手改產物：
    - **`sitemap.xml` 由 `tool/site_chrome/sitemap.py` 唯一產生**（`--check` 可驗證一致性）。`<lastmod>` 取 `git log -1 --format=%cs`（必須在版本控制下產物才準），**不輸出 `<priority>`／`<changefreq>`**（Google 明確忽略）。電子書重建後會自動重產（`tool/books2ebook/gen_all.py`、`tool/qa_split_ebook/gen_classified.py` 皆呼叫）。⚠️ **不要手改 `sitemap.xml`**——下次任何生成器執行都會覆蓋。
    - **跳轉頁（`wenda2_ebook/13–21*.html`）必須 `noindex, follow` ＋ canonical ＋ 唯一 title/description，且不得出現在 sitemap**（`tool/qa_split_ebook/gen_classified.py` 的 `_REDIRECT_TPL`）。`meta refresh` 只是臨時導向，Google 不視為 301。
    - **每個電子書頁面必須恰好一個 JSON-LD**（`Book`＋`Chapter`＋`WebPage`＋`BreadcrumbList`）與**動態描述**（問答數／段落數由建置期計算，**不得寫死**——舊版寫死「9,241 則問答」而實際 9,242，搜尋摘要因此與頁面矛盾）。⚠️ 繁體頁的 JSON-LD 必須在 `convert_html_to_trad()` **之後**注入（該轉換器不處理 `<script>` 內文）。
    - **站內搜尋索引 JSON（`search_index*.json` ＋ `.hash`，兩套合計約 47 MB）由 `robots.txt` `Disallow`**——crawler 抓它只浪費抓取資源；但**不可**連帶擋掉 `assets/` 的 CSS/JS（搜尋引擎仍需要它們渲染頁面）。
    - 守門：`tool/site_chrome/check_site.py`（產物層全項自動檢查）＋ `tool/word2ebook/tests/test_seo_jsonld.py`、`tool/books2ebook/tests/test_seo_jsonld.py`、`tool/site_chrome/tests/test_sitemap.py`。
    - **IndexNow**（`tool/site_chrome/indexnow.py`，金鑰在 repo 根 `indexnow-key.txt`）：推送後通知 Bing 等參與者立刻重抓；`gen_all_and_push.py --indexnow` 會自動送（URL 清單在 commit 前抓、通知在 push 成功後送）。

---

## Directory map

### Site pages (hand-edited unless noted)

| Path | Role |
|------|------|
| `index.html` | Landing page. Stories cards may be patched by `tool/stories2html/build_index.py`. 首頁「每日精選」（`daily_quotes.json` 依本地日期播種）另有 ◀◀ ◀ 今日 ▶ ▶▶ 鈕與**觸控左右滑動**（左滑＝後一天、右滑＝前一天）。⚠️ 觸控**必須走 Touch Events**（`touchmove` + `passive:false` + `preventDefault`）：Android Chrome 的 pointer 串流會被 compositor 以 `pointercancel` 中斷，用 Pointer Events 在手機上會完全滑不動；pen 才走 Pointer。改手勢／門檻／DOM id 後跑 `node tool/site_chrome/daily_quote_swipe_harness.js`。 |
| `wenda2.html` | Landing for the 12 thematic chapters under `wenda2/`. |
| `stories.html` | Stories list shell; list block updated by `build_index.py`. |
| `infographic.html` | Gallery: `infographic/thumbs/` WebP thumbnails in the grid, `infographic/webp/` full-size WebP in the lightbox (`data-src`). |
| `mindmap.html` | 坐禪與講經心智圖：自包含互動名詞心智圖（hand-edited）。 |
| `wenda2_mindmap.html` | 問答錄2心智圖：57 個高頻名詞／11 主幹；自包含單頁，**已凍結為手工維護**（產生器＋語料 `tool/wenda2_curation/` 已於 2026-09-28 移除，互動引擎原從 `mindmap.html` 拷貝）。 |
| `shared.js`, `style.css` | Shared nav / layout for root + `wenda2/` pages only. |
| `lang-switch.js` | Sitewide 繁/簡切換：一般頁面用 OpenCC-JS 即時轉換；電子書區（`EBOOK_DIRS`：`/wenda2_ebook/`、`/ebook/`）依偏好跳轉 `XX` ↔ `XX_trad` 雙頁。偏好存 `localStorage('tgl-lang')`，首次依 `navigator.languages` 判定。**含一對多誤轉修正層**（只/隻・發/髮・後/后・裡/里，字集與 `tool/word2ebook/utils/i18n_utils.py` 同源，兩份須同步維護）。**每頁都要含** `<script src="/lang-switch.js" defer></script>`（stories2html 與 word2ebook/books2ebook 範本皆已內建）；`audio_map*/` 刻意不加。⚠️ **跨語系轉址必須保留 `location.hash`**，且繁簡雙頁的段落 id（`p-*`／`answer-*`／`s*`）必須完全相同——首頁「每日精選」的「前往原文」靠這條才能落到引文段落。改 id 產生方式或轉址邏輯後跑 `node tool/site_chrome/lang_switch_harness.js`。 |
| `sitemap.xml` | SEO URLs — **由 `tool/site_chrome/sitemap.py` 產生**（勿手改；`--check` 可驗）。 |
| `robots.txt`, `CNAME` | Crawl / domain config. |
| `sw.js`, `manifest.webmanifest` | PWA（2026-09）：兩套電子書頁（`/wenda2_ebook/`、`/ebook/`）由 word2ebook `17-theme-pwa.js` 註冊根 SW；音檔永不快取；電子書頁面與搜尋索引採 **network-first**（2026-10-21，每次導覽以 ETag 重驗——部署後使用者打開即最新版，只有離線才吃快取；從前 stale-while-revalidate 會先回舊頁，是「要手動 Cmd+Shift+R」的根因）。manifest 被兩套電子書模板 `<head>` 引用。 |

### Content & media

| Path | Kind | Notes |
|------|------|--------|
| `問答錄2/` | **Source** | Word + monthly PDFs (and related) for 問答錄 2. Default inputs to `gen_all.py`. |
| `wenda2_ebook/` | **Generated** | Full bilingual searchable ebook. Rebuild from `tool/word2ebook/`. |
| `wenda2/` | **Hand content** | `chapter-01.html`…`chapter-12.html` site-themed TOC pages. Not produced by word2ebook. |
| `stories/` | **Hybrid** | Originals (PDF/DOCX/…) = source; `*.html` + many `assets/img/<slug>/*.webp` = generated by `stories2html`. Reader chrome: `stories/assets/story.{css,js}`. |
| `infographic/` | Assets | Concept images for `infographic.html` — WebP only: `webp/` (full size), `thumbs/` (640px). Regenerate with `tool/infographic2webp.sh`. |
| `images/` | Assets | Site-wide images (portrait, covers, favicons, social). Page-displayed images are WebP; `taiguanglin.png` (og:image) and `buddha.png` (manifest icon) stay PNG on purpose — see rule 11. |
| `fonts/` | Assets | 自架字型子集：Noto Serif/Sans TC 十字重 `*.woff2`＋`fonts.css`（SIL OFL 1.1，見 `fonts/OFL.txt`）。全站頁面以 `<link rel="stylesheet" href="/fonts/fonts.css">` 取代 Google Fonts 外鏈（大陸連不上）。新增頁面或新用字後跑 `tool/word_audio_map2/.venv/bin/python tool/fonts/build_fonts.py` 重建。 |
| `audio` | External (symlink) | Local `.opus` library; not in git. Play URLs assume same-origin `/audio/`. Its `index.html`（粉色串流頁、置頂大悲咒 player）**由 `tool/audio_index/index_template.html` 產生**：改樣板→跑 `python3 tool/audio_index/build_index.py`，不要手改 `audio/index.html`（該頁自帶 CSS/JS，不載入根 `style.css`）。 |
| `audio_map/` | Editorial UI **＋音頻映射 SoT** | `index.html` = 分類版音頻校對 UI（原 audio_map1_sep，2025-06 後月份）。**月份 JSON 的單一真相就在本目錄**（2026-10-26 起；`tool/word2ebook/data/audio_map/` 舊副本與 `qa_split_ebook/sync_audio_map.py` 已移除，產生器 `tool/pdf_audio_map/`、注入器 `tool/word2ebook`、`tool/qa_split_ebook` 皆直接讀寫這裡）。Alignment rules: **`audio_map/AGENTS.md`**. |
| `audio_map2/` | Editorial UI + data | 時間序 Word 彙總（2024-02…2025-05）的音檔 mapping 審核：月份 JSON + `index.html` review UI。文字以 Word 為準、SRT 只取時間；完成判定以「最後播放」(`meta.lastPlayed`) 為準。Rules: **`audio_map2/AGENTS.md`**. |
| `books/` | **Source** | 九本著作 PDF＋《感恩與講經》卷首一篇（坐禪系列 `01…05`＋講經系列 `06…09`，共 10 個 PDF；感恩與講經**不算一本書**）。 |
| `audio_map3/` | Editorial UI + data | 講經系列「段落 ↔ 音檔」對齊校對：`<series>.json` 由 `tool/jiangjing_para_map/build_maps.py` 產出（SRT ↔ 段落），`index.html` 審核；books2ebook 只注入 `reviewed=true` 講次的段落時間（跟播功能閘門）。pid 漂移用 `tool/books2ebook/sync_para_pids.py` 修（規則 13）。 |
| `ebook/` | **Generated** | 坐禪系列與講經系列**九本著作**＋卷首《感恩與講經》的合集靜態電子書（簡/繁、全量搜尋、每講播放鈕）。Rebuild from `tool/books2ebook/gen_all.py`。 |

### Tools (`tool/`)

工具清單、各自用途與依賴關係，見 **`tool/AGENTS.md`**（避免與各工具自己的 README 重複）。
簡表：

| Path | Purpose | Docs |
|------|---------|------|
| `tool/word2ebook/` | Word (+ PDF) → `wenda2_ebook/`（三段式就地重建：底稿 → qa_split extract → gen_classified 分類合併版） | **`AGENTS.md`**, `README.md`, `openspec/` |
| `tool/books2ebook/` | `books/` 九本著作＋感恩卷首 → `ebook/` 坐禅+講經系列电子书 | `README.md` |
| `tool/pdf_audio_map/` | Align PDF Q&A ↔ audio → `audio_map/*.json`（站台根目錄，單一 SoT） | `README.md` |
| `tool/word_audio_map2/` | Align 時間序 Word 彙總 ↔ SRT → `audio_map2/*.json` | `README.md` |
| `tool/sense_voice/` | Chinese ASR → `.srt`/`.txt` | `README.md` |
| `tool/audio_denoiser/` | Denoiser preprocessing before ASR | `README.md` |
| `tool/stories2html/` | Stories → HTML readers + index/sitemap patches | `README.md` |
| `tool/audio_index/` | 掃描 `audio/` → `audio/index.html`（置頂大悲咒播放器、類別／年份篩選） | `README.md` |
| `tool/site_chrome/` | 全站共用導覽 SoT → 「圖解」3 入口＋圖解頁 JSON-LD 寫回；`sync.py`（含 `--check`）、`check_site.py` 一致性檢查、`dropdown_harness.js` 下拉互動測試 | `README.md` |
| `tool/world_model/` | 兩套電子書產物 → 三千大千世界模型圖素材（16 主題章、逐字、帶錨點）；`build/` 已 gitignore | `README.md` |

---

## Main data flows

### 問答錄 2 ebook (canonical “進入電子書”)

三段式、單一目錄就地轉換（2026-10-26 起；`wenda2_ebook_word/` 中繼目錄已移除）：

```
問答錄2/*.docx + *.pdf
        │
        ▼
tool/word2ebook/gen_all.py  (+ audio_map/*.json inject)
        │   stage 1：就地重建 wenda2_ebook/ 為 21 章時間序底稿
        ▼
   wenda2_ebook/  ← 此時是底稿，還不是成品
        │
        ▼
tool/qa_split_ebook/extract.py      (stage 2：抽 13–21 → build/items.jsonl)
tool/qa_split_ebook/gen_classified.py (stage 3：就地轉 12 章分類合併版，13–21 換跳轉頁)
        │
        ▼
   wenda2_ebook/     ← published 成品；do not hand-edit for features
```

⚠️ 只跑 stage 1 就提交＝站上電子書變回未分類 21 章版。三段全跑可用
`tool/word2ebook/gen_all_and_push.py`（內建 pull → 三段重建 → commit → push）。

### 坐禅系列 + 講經系列电子书（books/ 九本著作＋感恩卷首）

```
books/*.pdf  (01《坐禅》…09《楞严经》 九本著作＋《感恩与讲经》卷首一篇)
        │
        ▼
tool/books2ebook/gen_all.py  （沿用 wenda2_ebook/assets 風格，含簡/繁與全量搜尋）
        │
        ▼
   ebook/      ← published; do not hand-edit; see tool/books2ebook/README.md
```

Audio-map pipeline (optional but used for play buttons):

```
SRT / opus  →  tool/pdf_audio_map/  →  audio_map/*.json（站台根目錄＝單一 SoT，
                                          由 /audio_map/index.html 校對 UI 直接讀寫）
                                          ▲
                                /audio_map/index.html (分類版校對) + gen_classified.py 注入播放鈕
              audio_map2/*.json  →  inject_word_chapters()  →  Word chapters 01–12 play buttons
              (audio_map2/index.html  review;  tool/word_audio_map2/  align)
```

### Homepage dual entry for 問答錄

| CTA on `index.html` | Target | Nature |
|---------------------|--------|--------|
| 查看目錄 | `wenda2.html` → `wenda2/chapter-*.html` | Hand TOC (12 themes) |
| 進入電子書 | `wenda2_ebook/index_trad.html` | Generated full ebook |

Do not assume these stay content-synced automatically.

### Stories

```
stories/<original>
   → tool/stories2html/extract.py  → build/<slug>.json  (gitignored)
   → build.py                      → stories/<slug>.html
   → build_index.py                → stories.html, index.html, sitemap.xml
```

Register new stories in `tool/stories2html/docs.py`. Prefer fixing extract/layout over long hand-edits of generated HTML.

### ASR / denoise (offline media; outside Pages content)

```
mp3  →  (optional) tool/audio_denoiser
     →  tool/sense_voice  →  .srt / .txt
     →  tool/pdf_audio_map  (補漏時 fill_misses.py 呼叫 sense_voice 重新轉寫)
```

---

## Where to edit (quick)

| Want to change… | Edit… | Then… |
|-----------------|-------|--------|
| Ebook UI / behaviour / search / i18n | `tool/word2ebook/` | 三段重建（`gen_all.py` → `tool/qa_split_ebook/extract.py` → `gen_classified.py`；一鍵版 `gen_all_and_push.py`） |
| 坐禅系列电子书 UI / 搜尋 / 簡繁 | `tool/books2ebook/` | `python3 gen_all.py`（同上；資產影印 wenda2_ebook 並附 books.css）|
| 段落跟播（校稿後要讀者真的用得到） | `audio_map3/*.json` ＋ `tool/books2ebook/` | `sync_para_pids.py --apply` → `gen_all.py` → `pytest tool/books2ebook/tests`（規則 13）|
| Ebook source text (Word/PDF months) | `問答錄2/` | `gen_all.py` |
| Play-button time ranges | `audio_map/*.json`（單一 SoT；經 `/audio_map/` UI 校對或 `pdf_audio_map` 產生） | Rebuild ebook |
| Site landing / nav / about | Root HTML + `shared.js` / `style.css` | Commit |
| 12-theme TOC pages | `wenda2.html`, `wenda2/` | Commit (no ebook rebuild) |
| Story reader text/layout | `stories2html` + originals / `docs.py` | extract → build → verify → build_index |
| Infographic / mindmap | `infographic/`, `infographic.html`, `mindmap.html` | Commit |
| 問答錄2心智圖內容 | `wenda2_mindmap.html`（**手工維護**；產生器已移除） | 直接改頁面 → `python3 tool/site_chrome/sync.py --check` → `check_site.py` → commit |

---

## Ambiguous / easy-to-misread paths

| Path | Clarification |
|------|----------------|
| `wenda2/` vs `wenda2_ebook/` | Different products. `wenda2/` = hand site TOC. `wenda2_ebook/` = generated ebook. |
| `問答錄2/` vs `wenda2_ebook/` | Source documents vs build output. |
| `audio_map/` 的 SoT | 2026-10-26 起 `audio_map/` 既是校對 UI 也是 JSON 唯一真相（產生器、注入器、抽取器直接讀寫同一份）；舊的 `tool/word2ebook/data/audio_map/` 副本已移除，不存在「兩份要同步」的問題。 |
| Root `script.js` vs ebook `script.js` | Root `script.js` 已移除（root chrome JS 是 `shared.js`）；ebook bundle 與其同名無關，由 `tool/word2ebook/assets/js/modules/` 串接而成。 |
| Production `/audio/` | Code expects same-origin audio; files are not in this git repo. Local preview needs the symlink. |
| `hidden/` | **已於 2026-10-11 從版控與部署移除**（commit `15bbfd7`）：目錄已不存在，舊網址 404。曾為四本複習電子書；產生器 `tool/wenda2_knowledge/`、`tool/ebook_knowledge/` 已同日整包刪除，僅 git 歷史可回溯。 |
| 「圖解」下拉選單 | 全站統一 3 個入口：名詞圖解（`infographic.html`）／坐禪與講經心智圖（`mindmap.html`）／問答錄2心智圖（`wenda2_mindmap.html`）。三頁皆為獨立終點頁，無「檢視切換」下一層。下拉單一真相來源為 `tool/site_chrome/sync.py`；生成或修改頁面後執行 `python3 tool/site_chrome/sync.py`，以 `--check` 驗證 root、`wenda2/`、`stories/` 的共用 chrome 頁。 |
| 導覽列頂層順序 | 全站統一：首頁／禪師／入門路徑／著作／問答錄 2／圖解 ▾／實修故事／下載資料——認識、兩大系列＋共用知識工具相連、延伸內容、行動（下載）最後。 |

---

## Agent doc layout

| Scope | File |
|-------|------|
| Whole repo | **`AGENTS.md`** (this file) |
| Tools directory | **`tool/AGENTS.md`** (清單 + 依賴關係) |
| Ebook converter | `tool/word2ebook/AGENTS.md` |
| Other tools | Their `README.md` (or script headers if no README) |

When a convention applies to more than one tool or to site layout, put it **here**. When it only concerns word2ebook internals (modules, OpenSpec, pytest), put it in `tool/word2ebook/AGENTS.md`.
