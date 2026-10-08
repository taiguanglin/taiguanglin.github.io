# books2ebook — `books/` 十本 PDF → `ebook/` 靜態電子書

與 `wenda2_ebook` 同款式：CSS/JS 不再各存一份，改以站點絕對路徑
`/wenda2_ebook/assets/...` 引用 `wenda2_ebook` 的建置產物（兩者同源
`tool/word2ebook/assets` 的 SoT），ebook 只保留自己專屬的 `books.css`、
`w2e-config.js` 與書內插圖。、
同一套簡/繁、全量搜尋、懸浮目錄、閱讀設定與深色模式。繁體版與
`word2ebook` 共用 `I18nProcessor`：以 OpenCC `s2twp` 產生台灣正體及台灣
慣用詞（例如「才、群、為、裡、軟體、滑鼠、資訊」），再套用一簡多繁的
語境修正，避免 `s2t` 產生「纔、羣、爲、裏」等少用異體字。

## 來源

| 編號 | `books/` PDF | 標題 | 解析器 |
|---|---|---|---|
| 01 | `01《坐禅》.pdf` (244pp) | 01《坐禅》 | `zuochan` |
| 02 | `02《坐禅之问答录》.pdf` (381pp) | 02《坐禅之问答录》 | `wendalu` |
| 03 | `03《坐禅2·次世代版终极佛法》.pdf` (352pp) | 03《坐禅2·次世代版终极佛法》 | `zuochan2` |
| 04 | `感恩与讲经（2024年4月14日）.pdf` | 感恩与讲经 | `ganen` |
| 05 | `04《次世代版终极佛法·TaiGuangLin禅师讲金刚经 心经》.pdf` (192pp) | 04《金刚经·心经讲记》 | `jingang` |
| 06 | `05 TaiGuangLin禅师讲《圆觉经》最终版.pdf` (211pp) | 05《圆觉经》讲记 | `yuanjue` |
| 07 | `06 Tai师父讲《四十二章经》.pdf` | 06 讲《四十二章经》 | `sishierzhang` |
| 08 | `07 Tai师父讲《楞伽经》.pdf` | 07 讲《楞伽经》 | `lengqie` |
| 09 | `08 Tai师父讲《六祖坛经》.pdf` | 08 讲《六祖坛经》 | `liuzutanjing` |
| 10 | `09 Tai师父讲《楞严经》(未完).pdf` | 09 讲《楞严经》(未完) | `lengyanjing` |

文字全數取自 PDF；TOC 僅擷取書內真實章節（不抄書前小目錄的殘頁標題）。

### 講經系列（04、07–10）

這五本以「講次（期）」為章節：每講是 `h2`（含該講音檔的播放鈕），如「楞伽经（1）」…
「楞伽经（42）」。共同解析器是 `parsers.py` 的 `_parse_jiangjing`（`sishierzhang` 額外指
派 `with_chapters=True` 以切出「第X章」等 `h3`）：

- 講次標題字型比正文大（≥15.5），匹配 `<經名>（N）`，支援字距拉開（「楞 伽 经（42）」）
  或拆成兩行（壇經「坛」＋「经（1）」）；編號可為中文數字（楞嚴 12–21）。
- 原經文用楷體（`KaiTi` / `HYKaiTiKW` / `PingFangSC-Semibold` / `STKaiti`）排，對應 `quote`
  區塊（`.sutra-text`），與《圆觉经》一致；楷體大字的「品」名（如「断食肉品第八」）為 `h3`
  導覽。楷/黑混排的一行（楞嚴 docx 轉 PDF 後經文結尾+解說開頭黏在同一視覺行）由
  `_split_mixed_line` 依字型 class 切開；康熙部首異體（⼆→二、⾳→音…）在 `_clean` 做 NFKC 正規化。
- 頁碼（字型 < 11.5 的純數字）與「时间：…／完整音频请关注…」metadata 行跳過；正文段落依
  首行縮排切分。

音檔綁定在 `audio_map.py` 的 `AUDIO_MAP`（`series → {N: 含日期的檔名}`）與 `AUDIO_BASE`。
音檔檔名含錄音日期（如「2025年7月7日Tai师父讲经·六祖坛经(1).opus」），全部平放在
`audio/jiangjing/` 下（不分系列子資料夾）。播放鈕 `data-audio` 指向 `../audio/jiangjing/<檔名>.opus`，
`data-end` 由 ffprobe 實測時長代入。

**講次編號 ≠ 檔名編號（容易搞混的偏移）**：`AUDIO_MAP` 的鍵是「該系列的**第 N 講**」
（播放器標題、跟播 checkbox 都用這個 N），而網頁檔名 `07.html`、`08.html`…是**書序**
（`config.BOOKS` 的 `number`）。兩者沒有換算關係——`04 讲《金刚经 心经》`（檔名
`05.html`）若無音檔映射就整本沒有播放鈕；四十二章經檔名 `07.html`，講次 N 從 1
重新數起。查播放鈕為何缺/多時，先對 `parsers` 切出的「（N）」編號，再對
`AUDIO_MAP[series][N]`，**不要**拿書序去對音檔。

單本 PDF 的組裝（合併、補 TOC、docx→PDF）另見 `tool/build_jiangjing_pdfs.py`，音源轉檔
`tool/jiangjing2audio.py`、音量正規化 `tool/normalize_jiangjing_audio.py`。

### 講經段落跟播（audio_map3 段落時間注入）

`para_audio_map.py` 在建置時讀取 **repo 根目錄**的 `audio_map3/<series>.json`
（由 `tool/jiangjing_para_map/` 對齊產生；格式為
`{"lectures": {"1": {"paragraphs": [{"pid", "start", "end", ...}]}}}`，pid 即段落
元素 id，`start`/`end` 為音檔秒數）。`html_generator.render_chapter` 對 `para` /
`strong` / `quote` 三種 `.para-block` 區塊，凡 pid 命中對齊表就附加
`data-start="%.3f" data-end="%.3f"` 屬性；**JSON 缺檔或 pid 未命中時靜默略過**
（不加屬性、不報錯、不打斷 build）。

前端行為由 `tool/word2ebook/assets/js/modules/09b-para-track.js` 提供（經
`StaticAssetsManager` 串接進 `ebook/assets/js/script.js`；樣式在 `04c-qa-audio.css`）。頁面上出現
帶 `data-start` 的段落時：

- 每個講次 h2 的播放鈕旁出現「段落跟播」文字 checkbox（localStorage `paraTrackEnabled`，
  預設 ON）。ON 時播放中即時高亮當前段落（`.para-active` 暖光暈＋加粗，上一段不變），
  並平滑捲動使當前段停在視窗上方且保留上一段底部可見。
- 跟播 ON 時點擊任一段落 → 直接從該段起點播放，之後一路順播到底，不在段末自停。
  拖選／反白選取文字、點擊段落內按鈕連結時不觸發；可點播段落顯示手形游標。

### 講經經文置頂（原經文原尺寸停留）

前端行為由 `tool/word2ebook/assets/js/modules/09c-sutra-pin.js` 提供（同一 bundle；
樣式主體在 `04c-qa-audio.css`，停留中的經文就是原版 `.sutra-text` 本身）。頁面出現
`.sutra-text` 時：向下捲動（不管有沒有跟播）會讓「即將捲出視窗頂」
的那段原經文以原生 `position: sticky` 停在視窗最上方（原尺寸、原樣式、無白邊；
Confluence 表格固定表頭概念），講解段落從其下方滑過。停留範圍由
`.sutra-pin-group` 限制在「該經文 → 下一邊界（下一段經文、h1–h6 章節名/品名、
圖片）」之間，因此天生不會蓋住經文、章節名或圖片——會遮住之前就先讓位歸位；
進入新章節自然失效。

**2026-10 長文載入效能：包層改於建置期輸出。** `html_generator.render_chapter`
對每個 `quote` 區塊直接輸出 `<div class="sutra-pin-group"><div class="sutra-pin-host">…</div>…</div>`
（其後的 para/strong/label/qa/hr 落在同一群內；遇到下一個邊界——下一段經文、
h2–h6 標題、實際輸出的 figure——先閉群，邊界留在群外；無 src 而未輸出的 img
不是邊界，與 09c 只認 DOM 中實際元素一致）。09c 偵測到既有包層即沿用、跳過
runtime DOM 手術——楞伽經 1482 群不再於啟動時插入/搬移近全頁節點；runtime
包法保留作為未包層頁面的後備。過長經文判定（> 55% 視窗高不停留）與錨點讓位高度
（`--w2e-pin-reserve`）的量測亦改為**接近視窗才量**：IntersectionObserver
（rootMargin 100px）進入前緣量一次，此時經文已被 `content-visibility` 真實
render，量到實際高度而非 240px 佔位值；resize／字級變化只重算已量過的群，
啟動不再全頁掃描（讀寫分批，避免 layout thrashing）。

過長經文不停留；且經文高度隨閱讀設定（字級／行距／版面寬）、視窗縮放或字型載入改變時會重新
量測（`ResizeObserver`／inline style 監看／`document.fonts.ready`），放大字級後接近滿版
的經文不會仍卡在置頂。段落跟播高亮（`.para-active`）在 `04c-qa-audio.css` 是半透明
暖色；經文若同時置頂，下方講解會透過半透明底色看見，故 `books.css` 針對
`.sutra-text.para-block.para-active` 改用等效的**不透明**暖色（深色模式亦然），
維持原視覺但不透光。講次 h2 旁有「經文置頂」
toggle（localStorage `sutraPinEnabled`，預設 ON）；錨點跳轉時短暫停停留避免蓋住
目標；段落跟播的自動捲動經 `W2E.sutraPin.reserveFor` 以「當前段頂 − 停留經文高 − 24px」為捲動上限，高亮段落永遠落在停留經文下方不被蓋住。

改前端行為 → 改 `tool/word2ebook/assets/` 模組後，**先重建 `wenda2_ebook/`**
（`tool/word2ebook/gen_all.py`）再重跑本工具的 `gen_all.py`：因為
`style.css`／`script.js`／`i18n-text.js`／`minisearch.min.js`／
`search-cache.js`／`jieba_rs_wasm.*` 這 7 個檔案與 `wenda2_ebook` 共用
（`config.SHARED_ASSET_FILES`），ebook 頁面直接引用
`/wenda2_ebook/assets/...`。`copy_assets()` 會比對 SoT 內容與共用產物，
若 `wenda2_ebook` 落後會印出警告（不中斷建置）。

## 一鍵重建

**用 `tool/word_audio_map2/.venv`（依賴已鎖版）**，不要用系統 python：

```bash
tool/word_audio_map2/.venv/bin/python tool/books2ebook/gen_all.py

# 等價寫法：
tool/word_audio_map2/.venv/bin/python tool/books2ebook/main.py --books-dir books --out ebook
```

### ⚠️ 為什麼指定這一個 python

**本工具的產出文字會隨 PyMuPDF 版本改變**。PDF 文字抽取在斷行處怎麼補空格
會隨版本不同而變，而 `parsers._join()` 正是靠「上一段結尾 + 下一段開頭」決定
要不要插空格——所以同一支 parser 換個 pymupdf 就可能產出不同的文字。

實測（2026-09）：在 PyMuPDF 1.28.2 下重建，8 個章節 HTML 有 72 段文字與版控
不同（`18 岁` → `18岁` 之類的數字空格差異），`search_index*.json` 的 MD5 跟著
變。也就是說**版控中的 `ebook/` 文字無法由任意環境重現**，且這種雜訊混進
功能提交會讓 diff 無法 review。

因此：

- 依賴版本鎖在 **`tool/word_audio_map2/requirements.txt`**（全部 `==`），
  理由與升版流程寫在該檔頭與 `tool/word_audio_map2/README.md`。
- 升版**必須與重建產物同一個提交**，且事先 review 文字 diff，
  確認是預期的內容差異而非抽取層雜訊。
- 純抽取雜訊（只有空格／全形半形之差）不要混進功能提交。

## 輸出

| 路徑 | 內容 |
|---|---|
| `ebook/index.html` / `index_trad.html` | 首頁目錄（搜尋入口→10 本書→各章小節） |
| `ebook/01.html` … `10.html`（各附 `_trad`）| 單書正文 |
| `ebook/assets/css/books.css` | 經文/標籤/插圖等附加樣式（本工具自有） |
| `ebook/assets/js/w2e-config.js` | ebook 專用搜尋範圍：`['question','answer','content','heading']`（01d-search-perform 讀取），取代舊的字串 patch |
| `ebook/assets/img/bN/` | 書內插圖（以 xref 去重）|
| `/wenda2_ebook/assets/css/style.css` | **共用**（不複製）：由 `StaticAssetsManager` 串接的 SoT 樣式，HTML 以站點絕對路徑引用 |
| `/wenda2_ebook/assets/js/script.js` | **共用**（不複製）：SoT 串接的 JS bundle |
| `/wenda2_ebook/assets/js/{i18n-text,minisearch.min,search-cache,jieba_rs_wasm,jieba_rs_wasm_bg}.{js,wasm}` | **共用**（不複製）：本地自架夥伴檔案 |
| `ebook/search_index*.json` + `.hash` | 全量搜尋索引（與 wenda2_ebook 同格式） |

頁首導覽依頁面層級區分：總目錄頁顯示「首頁」（固定連到
`../index.html`）與「問答錄2」；單書內頁只顯示「坐禪與講經總目錄」，
不連到另一本電子書，也不直接跳離電子書回網站。語言切換每頁只顯示
「切到另一語系」的單一按鈕：繁頁顯示「简体」、簡頁顯示「繁體」。

段落分段：依書本縮排（首行縮進 2 字元，對應 PDF 中 x₀ 偏移約 27–28 pt）還原；《坐禅之问答录》的問答以 `username：` 與 `Taiguanglin：` 搭配 x₀ 分辨，並保留編者補註（如「醫家正推法……——話頭禪」）。

### 《坐禅之问答录》師父貼文的切分

原書是論壇串的整理，師父常一次連發數則，每則各有發文時間。這些貼文在
`parse_wendalu` 中各自成為一個 `qa` 區塊（連續貼文的 `questioner`／`qtext`
為空，`html_generator` 會略過空的提問框），時間存進 `atime` 並以
`.answer-time` 顯示——否則 `_split_qa_time` 取出的時間會被丟掉。判斷貼文邊界
有兩個依據：

1. **署名行**。原書排版不一致，`_ANSWER_LEAD_RE` 一併吃下 `Taiguanglin：`、
   多空格的 `Taiguanglin ：`、誤植分號的 `Taiguanglin；`，以及回覆特定網友的
   `Taiguanglin@ 某某：`（後者只吃掉署名，`@某某：` 留在內文）。
2. **上一段以時間收尾**。少數長帖（如 2014-03-08 那篇談論疏的長文）接在前一
   則之後卻沒有再署名，此時以「前一段結尾即發文時間 + 本行為縮排新段」判定
   為新的一則。

### 《金刚经》解析中重引的原經文

第 04 本的「解析」會把原經文再引一次（如「3．须菩提，所言善法者，如来说即非善法，是名善法。」）。這些句子改以 `<strong>` 粗體輸出，與第 05 本《圆觉经》一致。判斷分兩關，都在 `parsers.py` 的 `parse_jingang`：

1. **字型分工**（`extract.py` 的 `Line.fonts` 保留整行各 span 的字型）。原書用 `FZHTJW` 黑體同時排「重引經文」與「名相注釋的詞頭」，兩者差別在於後者的詞頭之後會換回 `FZBYSK` 宋體：

   - `[FZHTJW]3．须菩提，所言善法者……` → 整段黑體 → 經文
   - `[FZHTJW]1．阿修罗： | [FZBYSK]我们可以理解为天界的畜生……` → 段內有宋體 → 注釋

   段落邊界沿用既有的縮排規則，所以像「2．卵生、胎生……／非有想非无想：〔宋體〕先看『四生』……」這種詞頭跨行的情況也會被歸成同一段而正確排除。

2. **與原經文語料比對**。第一關過後仍混有少量純黑體的白話講解（如「对于五眼有不同的解释。」、《心经》咒語的白話翻譯）。因此再把候選段落（去掉開頭編號）與全書 `FZSHJW` 經文語料做字元 4-gram 比對，重疊比例需 ≥ 0.6。用比例而非完全比對，是因為書中重引時偶有省字（原文「以音声求我」重引作「音声求我」）或異體字（著／着）。

此法不依賴編號，所以無編號的「如来不以具足相故，得阿耨多罗三藐三菩提。」與縮寫的「1．须菩提，汝若作是念……须菩提，莫作是念」同樣會轉粗體。目前共辨識出 134 段。另外，第 04 本少數頁面的「译文：」是用黑體而非 `FZLTHBJW` 排版，現在也一併歸為 `label`。

## 開發工具

```
cd tool/books2ebook
/usr/bin/python3 dev_peek.py [N]       # 看第 N 本書的標題階層
/usr/bin/python3 dev_peek.py 2 -v      # 連區塊 JSON 一併印出
```

## 與站點的連動

Github Pages 的首頁（`index.html`）在「學習資料」區塊收錄指向 `ebook/` 的卡片（與其它外掛工具的入口連動，對應於下方的樣式）。
