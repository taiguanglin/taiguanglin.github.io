# tool/fonts — 全站字型自架子集管線

把 Noto Serif TC / Noto Sans TC 依「實際用字語料」做成 woff2 子集，輸出到
`fonts/`，取代全站的 Google Fonts 外鏈（`fonts.googleapis.com` 在中國大陸時常
連不上，而本站明確服務簡體讀者）。

## 產出（要 commit）

| 檔案 | 內容 |
|------|------|
| `../../fonts/NotoSerifTC-{400,500,600,700,900}.woff2` | 標題襯線字重 |
| `../../fonts/NotoSansTC-{300,400,500,600,700}.woff2` | 內文黑體字重 |
| `../../fonts/fonts.css` | `@font-face`（絕對路徑 `/fonts/...`，root／`wenda2/`／`stories/`／404 皆可直接引用） |
| `../../fonts/OFL.txt` | Noto 字型授權（SIL OFL 1.1） |

## 重建流程

1. **源字型**放 `src/`（gitignore，不進版控）：
   - `notofonts/noto-cjk` 的 `Sans/SubsetOTF/TC/` 與 `Serif/SubsetOTF/TC/`：
     `NotoSansTC-{Light,Regular,Medium,Bold}.otf`、`NotoSerifTC-{Regular,Medium,SemiBold,Bold,Black}.otf`
   - `NotoSansTC-SemiBold.ttf`：CJK 靜態版沒有 Sans SemiBold，從 google/fonts 的
     `NotoSansTC[wght].ttf` 實例化：
     `pip3 install --target .pylibs fonttools brotli`
     `python3 -m fontTools.varLib.instancer NotoSansTC-VF.ttf wght=600 -o NotoSansTC-SemiBold.ttf`
2. **執行**（需要 opencc → 用 word_audio_map2 的 venv；fonttools 走 `.pylibs`）：

   ```bash
   tool/word_audio_map2/.venv/bin/python tool/fonts/build_fonts.py
   ```

3. 語料自動重掃：root `*.html`＋`wenda2/*.html`＋`stories/*.html`＋
   `stories/assets/story.js`＋`daily_quotes.json`，並把 OpenCC t2s 轉換後的
   簡體字併入聯集（`lang-switch.js` 在繁頁即時轉簡，缺字會退回系統字型）。

## 何時要重跑

- **新增頁面／新增動態注入文字**（尤其新故事、每日精選語料更新）之後。
- 子集只覆蓋語料用字；新增頁面若出現語料外的新字，該字會以系統字型顯示
  （不會破版，但建議重跑保持一致）。

## 頁面接入方式

所有載入站用字型的頁面，head 放：

```html
<link rel="stylesheet" href="/fonts/fonts.css">
```

（root 頁面亦可用 `fonts/fonts.css`，但為了 404／子目錄一致，統一用絕對路徑。）
`style.css` 的 `--font-serif`／`--font-sans` 名稱不變（`'Noto Serif TC'`／
`'Noto Sans TC'`），不需改任何 CSS。
