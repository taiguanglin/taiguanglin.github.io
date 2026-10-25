# 章節拆頁設計筆記 — wenda2_ebook 大章分頁（配 13–21 章分類回建）

> **定位**：`tool/qa_curation/` 分類作業把第 13–21 章（3,453 則月度答疑）併入第
> 1–12 章後，章頁 HTML 會嚴重膨脹。本筆記是「拆頁」的設計決策紀錄（子頁命名、
> 轉址表、驗收清單）。**分類作業本身**（拆分準則、輸出 schema、音檔重跑）以
> `wenda2_split_classify_criteria.md` 為 SoT，本筆記不重複、只引用。
> **實作 SoT**：程式改動全部落在 `tool/word2ebook/`（規則：勿手改 `wenda2_ebook/`）；
> 落地後操作細節應回寫 `tool/word2ebook/AGENTS.md`。

---

## 1. 動機：分類併入後的膨脹實測（2026-10-21）

- 現況：第 1–12 章 **5,789 則**（Word 分類）；第 13–21 章 **3,453 則**未分類（PDF）。
  併入後總量 **≈9,242 則（+60%）**，且 13–21 章整章消失（電子書 21 章 → 12 章）。
- 單檔現況（簡體頁）：

| 章 | 則數 | 大小 | 併入後推估 |
|---|---:|---|---|
| 04 世界起源与轮转 | 1,328 | 2.3MB | ≈2,100 則 / **≈3.7MB** |
| 12 佛门修行 | 969 | 1.9MB | ≈1,550 則 / ≈2.9MB |
| 02 羯磨(业) | 789 | 1.5MB | ≈1,260 則 / ≈2.4MB |
| 10 双盘 | 688 | 1.2MB | ≈1,100 則 / ≈1.9MB |
| 11 禅定 | 608 | 1.1MB | ≈970 則 / ≈1.7MB |

- 04 章本體各 L2 節分佈（字符量）：起源 31K／創世 89K／設計 157K／眾生輪轉 294K／
  解脫與成佛 111K／傳法度人 200K／極樂世界 276K／娑婆世界 183K（另有「本章目录」
  佔位 h2 21K，非內容節）。**結論：L2 是天然拆分邊界**——拆 L2 後最大節
  （眾生輪轉）併入後約 0.8MB，仍在可接受範圍，**不需要拆到 L3**。
- 行動端一次 build 3.7MB 的 DOM（≈2,100 則 QA）載入與滾動都會明顯變痛；
  分類併入也會全檔重寫章 HTML，git diff 難以 review。

## 2. 方案：章頁＝章目錄；每個內容 L2 節各成一個靜態子頁

- **章頁 `04.html` 保留原 URL**，內容改為：h1（章名＋則數）＋完整章級 TOC
  （SSR 輸出，沿規則 12 全部要求：`.toc-expandable`、預設層級與 `▶` 按鈕預先輸出、
  層級解析兩邊一致）。不再含 QA 本體。
- 每個內容 L2 節輸出一個子頁：h1 章名（連回章頁）＋h2 節名＋該節全部 L3/L4 與
  QA 條目＋節間導航（上一節／下一節／回本章目錄）。
- **錨點 id 一律原樣保留**（`question-<id>`／`answer-<id>`／標題 slug），繁簡雙頁
  id 逐一相同（既有鐵律，lang-switch 與「前往原文」依賴它）。
- 首繪全部 SSR——與規則 12 相同的精神：爬蟲與無 JS 使用者直接可讀。

### 被否決的替代方案

| 方案 | 否決理由 |
|---|---|
| 內容抽 JSON、前端 fetch 載入 | 違反規則 12 SSR 鐵律：爬蟲／無 JS 得到空頁；「載入中」遮罩只是蓋住問題 |
| 只做客戶端分頁／摺疊 | 不減單檔大小，只改善渲染；下載與 DOM 成本照舊 |
| 子目錄式命名（`04/01.html`） | 頁面資產是**相對路徑**（`assets/css/style.css`…），進子目錄全部要改寫；`04.html` 與 `04/` 並存易誤導 |
| 拆到 L3 | 不必要：最大 L2 節併入後 ≈0.8MB；粒度太碎會傷閱讀連續性 |

## 3. 子頁命名

**`NNsXX.html`**（`NN`=章號、`s`=section、`XX`=章內內容 L2 的文件順序，兩位數，
01 起）。繁體頁 `NNsXX_trad.html`。例：04 章 → `04s01.html`…`04s08.html`＋繁體各一。

- 「本章目录」佔位 h2 **不編號、不生成子頁**；只數內容 L2。
- 選擇理由（皆有實測依據）：
  1. **扁平同層** → 相對資產路徑零改寫（實測 04.html 資產 href 皆為 `assets/...`，
     僅 `/lang-switch.js` 為絕對路徑，兩者皆不受影響）。
  2. **lang-switch 零改動**：`lang-switch.js` 以 `base + '_trad.html'` 機械對映並保留
     `location.hash`，`04s04.html` ↔ `04s04_trad.html` 天然成立。
  3. **sw.js 零改動**：`/wenda2_ebook\/.*\.html$/` 的 network-first regex 自動涵蓋
     子頁（SW 無硬編 precache 清單）。
  4. 檔名排序上子頁緊跟章頁，diff 與 `ls` 對人友善。
- 棄選：`04-01.html`（連字號未來易與其他編號檔混淆）；slug 式
  `04-zhongsheng-lunzhuan.html`（節名一改檔名就變，不利穩定外鏈）。

## 4. 轉址表（歷史深鏈相容）

章頁不再含內容後，**無法由重建自動修復的歷史外鏈**（論壇轉貼、舊書籤）指向
`04.html#answer-…` 會落空。`search_index`／`sitemap`／`daily_quotes.json` 會在重建
時自動改指子頁，不靠轉址。

- **每章輸出 `04-redirects.json`**：`{"answer-83a3ae693030": "04s04.html",
  "question-0e49c37e1a7e": "04s04.html", "<標題slug>": "04sXX.html"}`——
  id → 子頁**基底名**（不含 `_trad`）。涵蓋 answer、question 與標題 slug 三種 id。
- 章頁帶一小段內嵌 `<script>`（生成器輸出，約 10 行）：`location.hash` 非空才
  `fetch()` 本章 redirects.json，命中即 `location.replace()`（**保留 hash**）；
  繁體頁由 loader 把基底名補 `_trad`，使用者留在同語系。
- 無 JS → 停在章目錄頁，可閱讀可導航，屬可接受的漸進降級。這是深鏈補償、
  不是初始畫面，與規則 12 不衝突。
- 04 竮約 1,328×2 條 ≈ 數十 KB 的 JSON，只按需 fetch，不進章頁本體
  （章頁本體預估 ≈30KB）。

## 5. 受影響面（模組清單）

| 模組 | 影響 | 說明 |
|---|---|---|
| `generators/html_generator.py` | **主要** | 章頁渲染改 TOC-only；新增子頁渲染（節導航、h1/h2 層級、`_add_qa_counts_to_content_headings` 照用）；`_generate_chapters` 每章輸出 1＋N 檔＋redirects.json |
| `generators/toc_generator.py` | **主要** | TOC 節點 href 改指子頁；`.toc-expandable`／預設層級／`▶` SSR 規則不變（規則 12）；子頁 TOC 高亮當前節；章頁層級按鈕規則照舊 |
| `generators/search_generator.py` | 自動 | url 由章檔改指子頁錨點；id／slug 不變，內容鍵（pid 類比）不受影響 |
| 音檔注入（`core/audio_map_injector.py`、`inject_word_chapters`） | **零改動** | 注入發生在 `main.py` 的 chapters **模型層**、先於頁面寫出；條目 id 不變 → 搬到子頁不斷鏈 |
| `lang-switch.js` | 零改動 | 機械對映＋hash 保留已相容（§3） |
| `sw.js`（PWA） | 零改動 | network-first regex 已涵蓋（§3） |
| `sitemap.xml` | 更新 | 子頁列入（章頁保留）；`check_site.py` 驗一致性 |
| `tool/daily_quotes/` | **管線重跑** | url 變 → `refresh_sample.py` 對齊樣本 → `select_1095.py` 重出成品（pid 以文字重定位）→ `audit_quotes.py` 守門 |
| `tool/world_model/` | **必改** | 語料讀 `wenda2_ebook/*_trad.html` → glob 需加 `NNs*_trad.html`，否則拆頁後 04 章語料缺 8 節；改後 `verify.py` 逐行回比 |
| `tool/word2ebook/tests/` | 擴充 | 章頁／子頁兩模式的 `TestTOCInitialState`；轉址表生成；繁簡 id 逐一同；注入不因拆頁丟失；閾值行為 |
| `tool/books2ebook/` | 僅回歸 | 拆頁只動 word2ebook；共用資產（`reading-prepaint.js` 等）跑一次既有測試確認 |

## 6. 門檻制（建議）vs 全拆

- **建議採門檻制**：`tool/word2ebook/config.yaml` 新增 `chapter_split:` 區段
  （`threshold_mb: 1.2`）。章本體超過門檻才拆——現況拆 02／04／12；分類併入後
  10／11／01／07 陸續越線，**機制自動擴大適用，無需再動工程**。
- 全拆（12 章一律拆）模式單一，但小章（03=118 則）會變成近乎空殼的目錄頁＋零碎
  子頁，閱讀體驗變差。
- 兩種輸出只存在於 generator 內部；對消費端（TOC href 由章節模型帶出）兩模式同構，
  不增加分支。
- 03 章試拆一次作為對照，再最終定案門檻值。

## 7. 實施順序（拆頁與分類解耦）

1. **先拆頁機制**（用現行內容，02/04/12）＋測試＋轉址表 → `gen_all.py` →
   daily_quotes 對齊 → world_model glob 修正＋`verify.py` → commit。
2. **後分類併入**（準則 §6.4 作業、§6.5 回建：併入分類 Word 母檔、重跑
   `tool/pdf_audio_map/` 對位、`link_chapters.py` 重寫章節對應）→ `gen_all.py` →
   daily_quotes 對齊 → commit。

理由：分類併入會全檔重寫章 HTML；先拆頁，之後的內容 diff 分散在各子頁，review
與 `search_index`／每日精選對齊各自只做一次，不會兩次攪動。id 變動只會來自分類
（鐵律 4/10：原文不改寫→id 不變；拆分子問題→id 變、音檔管線重跑），拆頁本身
**不產生任何新 id**。

## 8. 驗收清單

### A. 拆頁機制（每步必須過）

1. `cd tool/word2ebook && ../../tool/word_audio_map2/.venv/bin/python -m pytest tests/`
2. `cd tool/books2ebook && ../../tool/word_audio_map2/.venv/bin/python -m pytest tests/`（共用資產回歸；缺產物會 skip）
3. 重建後**關 JS** 開 `04.html` 與 `04s04.html`：目錄排列正確、無橫向多欄、
   層級按鈕高亮不跳動、閱讀設定首繪即套用（規則 12）。
4. 深鏈實測：`04.html#answer-<實例id>` → 轉到正確子頁同名錨點；
   `04_trad.html#answer-<同id>` → 繁體子頁且語系不跳（id 兩頁相同）。
5. `node tool/site_chrome/lang_switch_harness.js`。
6. 播放鈕抽驗：02/04/12 各取一個已校對段，確認子頁上按鈕仍在、時間正確
   （注入在模型層，理論零差異，仍須實測）。
7. `search_index*.json` 不再有 `04.html#answer-` 形式的 04 章條目（全指向子頁）；
   搜尋 UI 實測命中可跳轉。
8. `python3 tool/site_chrome/sync.py --check && python3 tool/site_chrome/check_site.py`
   （sitemap、斷鏈、一致性）。
9. daily_quotes：`refresh_sample.py` → `select_1095.py` → `audit_quotes.py`
   （exit 0；成品 url 全部指向新子頁）。
10. `tool/world_model/`：glob 修正後 `verify.py` 逐行回比通過（拆頁前後語料零遺失）。
11. 尺寸檢查：所有子頁 <1MB；拆頁後章頁 <100KB。
12. 文件回寫：`tool/word2ebook/AGENTS.md` 增補拆頁慣例；本目錄
    `wenda2_split_classify_criteria.md` §6.5 補一句「章頁已拆頁，回建產物為多子頁」。

### B. 分類併入（後續）

依準則 §6.4 驗收清單＋§6.5 回建路徑（音檔對位重跑；`meta.lastPlayed` 段不可動），
本筆記不重複。

## 9. 不變式（拆頁必守）

1. `question-*`／`answer-*`／標題 slug 在拆頁前後**一字不改**；繁簡子頁 id 逐一相同。
2. 轉址只補歷史外鏈，重建產物（search_index、sitemap、daily_quotes）一律指向新 URL。
3. 初始畫面 SSR（規則 12）：章頁與子頁都不依賴 JS 才能閱讀；`reading-prepaint.js`
   仍排在最後一個 stylesheet 之後。
4. 拆頁不動音檔映射 JSON；音檔相關變動一律走準則 §6.5 的管線。
