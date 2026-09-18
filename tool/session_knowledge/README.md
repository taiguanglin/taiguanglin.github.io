# session_knowledge — Session 知識庫生成器

把 repo 根目錄的 `SESSION_KNOWLEDGE.md`（2026-09-16~17 名詞查證與圖解工程 session 的完整知識萃取）
轉成全靜態的 `session_knowledge.html`（站台 chrome、目錄、表格／code 樣式齊備）。

## 資料流

```
SESSION_KNOWLEDGE.md（單一真相來源，hand-edited）
        │  build.py：受限 md 子集 → HTML（先轉義，再粗體／code／連結）
        ▼
session_knowledge.html（生成物：11 節、13 表、TOC 錨點；無 inline JS，繁簡交 lang-switch.js）
```

## 用法

在 repo 根目錄執行：

```sh
python3 tool/session_knowledge/build.py
```

## 維護規則

- **改內容**：改 `SESSION_KNOWLEDGE.md`，重跑本腳本。生成頁勿手改後又重跑。
- **md 子集刻意受限**：`#`/`##`/`###`/`####`、`|` 表格（第二行須為 `|---|`）、`-`／`1.` 單層清單、`>` 引用、``` 圍欄、`---`、行內 `**粗體**`／`` `code` ``／`[文字](連結)`。表格 cell 內不得再放 `|`；不支援巢狀清單與圖片。要擴充先改 build.py 的 parse()。
- **自檢**：生成後檢查免責聲明、lang-switch、canonical、TOC 與 h2 數量一致（11 節）、13 張表、無殘留 md 標記；任一失敗即 exit 1。改 md 的章節／表格數後，同步更新 build.py 的自檢數字。
- 本目錄另存兩個**自抽取版** harness（見 `mm_harness.js`／`rv_harness.js` 檔首說明）：直接從 repo 的 mindmap.html／review.html 抽內嵌腳本 eval 跑煙霧測試，不需 /tmp 快取——`SESSION_KNOWLEDGE.md` 第 6.3、9 節有完整用法與斷言盤點。

## 相關頁面

- `review.html`（間隔重複閃卡＋測驗）— 手編，inline 資料；本知識庫記錄其查證依據
- `books_knowledge.html`（九書重點知識）— 由 `tool/books_knowledge/build.js` 從 mindmap.html 生成
- `mindmap.html`（名詞關聯心智圖＋修行次第線）— 73 節點資料的 SoT
