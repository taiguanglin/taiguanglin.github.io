# books2ebook — `books/` 十本 PDF → `ebook/` 靜態電子書

與 `wenda2_ebook` 同款式（影印 `wenda2_ebook/assets`，並附 `books.css`）、
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
- 原經文用楷體（`KaiTi` / `HYKaiTiKW`）排，對應 `quote` 區塊（`.sutra-text`），與《圆觉经》
  一致；楷體大字的「品」名（如「断食肉品第八」）為 `h3` 導覽。
- 頁碼（字型 < 11.5 的純數字）與「时间：…／完整音频请关注…」metadata 行跳過；正文段落依
  首行縮排切分。

音檔綁定在 `audio_map.py` 的 `AUDIO_MAP`（`series → {N: NN_str}`）與 `AUDIO_BASE`；播放鈕
`data-audio` 指向 `../audio/jiangjing/<series>/<NN>.opus`，`data-end` 由 ffprobe 實測時長代入。

單本 PDF 的組裝（合併、補 TOC、docx→PDF）另見 `tool/build_jiangjing_pdfs.py`，音源轉檔
`tool/jiangjing2audio.py`、音量正規化 `tool/normalize_jiangjing_audio.py`。

## 一鍵重建

```bash
# 建議用系統 python（/usr/bin/python3 已含 pymupdf/opencc）
/usr/bin/python3 tool/books2ebook/gen_all.py
# 等價：
/usr/bin/python3 tool/books2ebook/main.py
# 其它路徑：
/usr/bin/python3 tool/books2ebook/main.py --books-dir books --out ebook
```

## 輸出

| 路徑 | 內容 |
|---|---|
| `ebook/index.html` / `index_trad.html` | 首頁目錄（搜尋入口→10 本書→各章小節） |
| `ebook/01.html` … `10.html`（各附 `_trad`）| 單書正文 |
| `ebook/assets/css/style.css` | 由 `wenda2_ebook/assets` 影印 |
| `ebook/assets/css/books.css` | 經文/標籤/插圖等附加樣式（本工具自有） |
| `ebook/assets/js/*` | 同上；`script.js` 的搜尋範圍過濾在複製後打一個 patch：`['question','answer']` → `['question','answer','content','heading']`，使散文段落也可被搜到 |
| `ebook/assets/img/bN/` | 書內插圖（以 xref 去重）|
| `ebook/search_index*.json` + `.hash` | 全量搜尋索引（與 wenda2_ebook 同格式） |

頁首導覽依頁面層級區分：總目錄頁顯示「網站首頁」（固定連到
`../index.html`）與「問答錄2」；單書內頁只顯示「坐禪系列總目錄」，
不連到另一本電子書，也不直接跳離電子書回網站。

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
