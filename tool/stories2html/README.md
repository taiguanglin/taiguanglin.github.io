# stories2html

把 `stories/` 底下的實修故事原始檔（PDF / DOCX / DOC / TXT）轉成純 HTML 閱讀頁，
放在 `stories/<slug>.html`。原始檔保留在原地，每篇閱讀頁最末端會提供下載連結。

## 使用

```bash
python3 tool/stories2html/extract.py      # 原始檔 → 區塊 JSON + 內文圖片
python3 tool/stories2html/build.py        # 區塊 JSON → stories/<slug>.html
python3 tool/stories2html/build_index.py  # 更新 stories.html / index.html / sitemap.xml
python3 tool/stories2html/verify.py       # 逐字比對原始檔與產出，確認沒有漏字
```

三個腳本都可以加 slug 參數只處理單篇，例如：

```bash
python3 tool/stories2html/extract.py xiaoxi-shuangpan-riji
python3 tool/stories2html/build.py xiaoxi-shuangpan-riji
```

另外 `dump.py <slug>` 會把區塊 JSON 印成好讀的純文字，方便檢查版面判讀結果。

## 檔案

| 檔案 | 作用 |
| --- | --- |
| `docs.py` | 每篇的中介資料（標題、作者、分類、摘要）與 PDF 版面參數 |
| `extract.py` | 版面判讀：段落還原、標題／圖說／表格辨識、圖片輸出 |
| `fixups.py` | 逐篇收尾修正；只搬移或標記既有內容，不新增刪除原文 |
| `build.py` | 套用閱讀頁模板產生 HTML |
| `build_index.py` | 改寫故事清單頁、首頁卡片與 sitemap |
| `verify.py` | 把原始檔與產出的文字都去掉空白後逐字比對 |
| `build/` | 中間產物（區塊 JSON），可安全刪除後重跑 |

閱讀頁共用 `stories/assets/story.css` 與 `stories/assets/story.js`，
內文圖片放在 `stories/assets/img/<slug>/`。

### 圖片一律 WebP

內文圖片輸出為 `*.webp`（`extract.py::save_pixmap`）。MuPDF 的 `pix.save` 不支援
WebP，故先存無損 PNG 中間檔、再交給全站共用的
`tool/word2ebook/utils/image_markup.py::encode_webp`（q85，alpha/CMYK 自動處理），
轉完即刪中間檔。DOCX 內嵌若本來就是 WebP 則原樣落地，避免二次失真。

實測 189 張故事圖 10.42 MB → 6.75 MB（−35%；來源本已是 JPEG q76–85，
故壓縮空間比電子書的 PNG 少）。全站圖片格式策略以此模組為 SoT，
`word2ebook`／`books2ebook`／`stories2html` 三者共用。

## PDF 版面參數

`docs.py` 的 `layout` 用來告訴抽取器怎麼讀版面：

| 參數 | 意義 |
| --- | --- |
| `indent_x` | 段落首行的縮排位置；`None` 表示原檔不縮排，改用「上一行沒有到右界」判斷分段 |
| `body_x` | 段落續行的左界 |
| `right` | 版心右界 |
| `heading_min_size` | 字級大於此值視為標題 |
| `heading_re` / `heading3_re` | 以文字樣式辨識標題（例如 `一、工具篇`） |
| `skip_pages` | 略過的頁（封面目錄等，目錄改由程式重新產生） |
| `skip_re` | 略過的行（頁碼、書眉） |
| `quote_fonts` | 只用這些字體的段落視為引文（原檔常以楷體排引用） |
| `page_overrides` | 個別頁的版心覆寫（例如書名頁比正文窄） |
| `tables` | 是否偵測表格 |

## 加一篇新故事

1. 把原始檔放進 `stories/`。
2. 在 `docs.py` 的 `DOCS` 新增一筆設定。
3. 跑 `extract.py <slug>`，用 `dump.py <slug>` 檢查段落與標題判讀，必要時調整 `layout`。
4. 跑 `build.py <slug>` 與 `verify.py <slug>`，確認 `缺=0`。
5. 跑 `build_index.py` 更新清單頁與 sitemap。

## verify.py 的輸出怎麼看

- `缺=0` 表示原始檔的每一個字都出現在產出的 HTML 裡。
- 若有「⚠ 不論順序仍缺字」才是真的漏字；只有 `缺` 而沒有這行警告，
  代表內容都在、只是順序被刻意重排過（例如附錄的大表拆成每月一張）。
- `多` 是頁面自己加上的文字，例如圖說與章節標題。
