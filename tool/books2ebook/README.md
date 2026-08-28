# books2ebook — `books/` 五本 PDF → `ebook/` 靜態電子書

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
| 04 | `04《次世代版终极佛法·TaiGuangLin禅师讲金刚经 心经》.pdf` (192pp) | 04《金刚经·心经讲记》 | `jingang` |
| 05 | `05 TaiGuangLin禅师讲《圆觉经》最终版.pdf` (211pp) | 05《圆觉经》讲记 | `yuanjue` |

文字全數取自 PDF；TOC 僅擷取書內真實章節（不抄書前小目錄的殘頁標題）。

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
| `ebook/index.html` / `index_trad.html` | 首頁目錄（搜尋入口→5 本書→各章小節） |
| `ebook/01.html` … `05.html`（各附 `_trad`）| 單書正文 |
| `ebook/assets/css/style.css` | 由 `wenda2_ebook/assets` 影印 |
| `ebook/assets/css/books.css` | 經文/標籤/插圖等附加樣式（本工具自有） |
| `ebook/assets/js/*` | 同上；`script.js` 的搜尋範圍過濾在複製後打一個 patch：`['question','answer']` → `['question','answer','content','heading']`，使散文段落也可被搜到 |
| `ebook/assets/img/bN/` | 書內插圖（以 xref 去重）|
| `ebook/search_index*.json` + `.hash` | 全量搜尋索引（與 wenda2_ebook 同格式） |

頁首導覽依頁面層級區分：總目錄頁顯示「網站首頁」（固定連到
`../index.html`）與「問答錄2」；單書內頁只顯示「坐禪系列總目錄」，
不連到另一本電子書，也不直接跳離電子書回網站。

段落分段：依書本縮排（首行縮進 2 字元，對應 PDF 中 x₀ 偏移約 27–28 pt）還原；《坐禅之问答录》的問答以 `username：` 與 `Taiguanglin：` 搭配 x₀ 分辨，並保留編者補註（如「醫家正推法……——話頭禪」）。

## 開發工具

```
cd tool/books2ebook
/usr/bin/python3 dev_peek.py [N]       # 看第 N 本書的標題階層
/usr/bin/python3 dev_peek.py 2 -v      # 連區塊 JSON 一併印出
```

## 與站點的連動

Github Pages 的首頁（`index.html`）在「學習資料」區塊收錄指向 `ebook/` 的卡片（與其它外掛工具的入口連動，對應於下方的樣式）。
