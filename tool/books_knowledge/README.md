# books_knowledge — 九書重點知識頁生成器

把 `mindmap.html` 內嵌、已逐點查證的名詞資料（`ROOT` / `BRANCHES` / `EBOOK_LINKS`）按「書」重新組織，
生成全靜態的 `books_knowledge.html`（比照 `wenda2_knowledge.html` 的定位，但對象是坐禪＋講經九書語料）。

## 資料流

```
mindmap.html（單一真相來源，hand-edited）
        │  build.js 抽取內嵌資料（slice + eval-IIFE，同 harness 手法）
        ▼
按書歸類（src 含書名標記即列入；一詞可跨多書）
        ▼
books_knowledge.html（生成物：9 個書區塊、名詞展開卡＝釋義／書中要點／原文摘句＋電子書深連結）
```

## 用法

在 repo 根目錄執行：

```sh
node tool/books_knowledge/build.js
```

## 維護規則

- **改名詞內容**：改 `mindmap.html`，重跑本腳本。`books_knowledge.html` 是生成物，勿手改後又重跑。
- **歸書標記**：`build.js` 內 `BOOKS[].marks`＝src 裡可辨認該書的字串（含講經系列完整書名變體，如《TaiGuangLin禪師講楞伽經》）。生成時若有任何名詞對不到書，build 直接失敗並列出節點——這是資料完整性檢查，不要放寬成 warning。
- **新增書**：在 `BOOKS` 加一列（`n` 電子書編號、`file`、`intro` 簡介、`marks`），重跑。注意 ebook/04《感恩與講經》不在查證語料內，不收。
- **頁面無 inline JS**：繁簡轉換由 `lang-switch.js` 全頁處理；樣式復用 `.mm-*`（詳情卡）＋ `.mm-ladder-step`（展開卡）＋ `.bk-*`（本頁專屬），都在根 `style.css`。
- **自檢**：腳本輸出前會檢查免責聲明、lang-switch、canonical、名詞卡數、深連結數、九個書區塊；任一失敗即 exit 1。

## 頁面導覽約定

「圖解」下拉選單在全站各頁為手工複製的 HTML；本工具生成的頁面、`mindmap.html` 與 `review.html`
已同步為相同七項順序（名詞圖解／名詞關聯心智圖／九書重點知識／名詞複習／問答錄2 重點知識／問答錄2 名詞心智圖／問答錄2 知識庫全檔）。其他舊頁的下拉若有差異，屬尚待同步的範圍。
