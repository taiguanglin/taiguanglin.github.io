# tool/daily_quotes — 首頁「每日精選」語料管線

產出 repo 根目錄的 `daily_quotes.json`，由 `index.html` 前端依日期播種輪播展示。

## 流程

1. `build_quotes.py` — 從 `wenda2_ebook/search_index_trad.json`（answer）與
   `ebook/search_index_trad.json`（content + answer）做規則過濾
   （長度 60–400、黑名單、CJK 比例、去重）→ `candidates.json`。
2. 固定種子抽樣（`candidates_sample.json`，2400 條）→ 分批 AI 評分（0–10，
   標準：文意自足、有啟發性、適合首頁）→ `scores/batch_*.json`。
3. `select_1095.py` — 產出 1095 條 `daily_quotes.json`：
   - **AI 骨架**：`scores/` 中 score ≥ 7 的 361 條（品質骨幹）。
   - **啟發式補充**：`candidates.json` 中尚未被評到的候選，以「可讀性啟發」
     （長度窗、結尾標點、教學詞、暱稱/時間戳/問號片段罰分、括號配對…）排序
     補足到 1095 條；單一來源（ebook）上限 70%。
   - `url` 含頁內錨點（如 `ebook/03_trad.html#p-sc436a366`），已驗證與電子書
     HTML 的 id 對應。

> `finalize.py`（早期 361 條版）已被 `select_1095.py` 取代。`score` 欄 = AI 分；
> `heuristic` 欄 = 啟發式分（無 AI 分的條目才帶）。

## 擴充 / 提升品質

- `candidates.json`（16,382 條完整候選池）、`candidates_sample.json`（已 AI 評的
  2400 條）、`scores/`（0–10 分數）皆納入版控。
- 日後有 AI 評分容量時，可對「啟發式補充」的 734 條再跑一次 AI 評分替換，
  或對 `candidates.json` 抽更多樣、評完後改 `select_1095.py` 的 `TARGET`。

## 前端（`index.html`）

- `fetch('daily_quotes.json')`，`idx = ((day * 2654435761 + 97) % len + len) % len`
  （以**使用者本地時區**日播種，午夜本地時間切換；負 offset 亦取正模）。
  同日同機一致，清單長度變動會重洗順序。
- **日切換**：header 列固定高度，含「◀ 前一天 / 今日 / 後一天 ▶」按鈕，
  點「今日」回到今日；按鈕位置不隨內容長度跳動（可連續點擊）。
- 預設 2 行截斷（`-webkit-line-clamp`）；內容 ≤2 行時自動隱藏「展開全文」。
- 「前往原文」以新分頁開啟錨點連結。
- **簡繁**：語料為繁體，靠全站 `lang-switch.js` 的 MutationObserver 對動態注入
  的文字即時轉換，載入與切日/切繁簡皆會正確轉換。