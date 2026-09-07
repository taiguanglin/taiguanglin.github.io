# tool/daily_quotes — 首頁「每日複習」精選語料管線

產出 repo 根目錄的 `daily_quotes.json`，由 `index.html` 前端依日期播種輪播展示。

## 流程

1. `build_quotes.py` — 從 `wenda2_ebook/search_index_trad.json`（answer）與
   `ebook/search_index_trad.json`（content + answer）做規則過濾
   （長度 60–400、黑名單、CJK 比例、去重）→ `candidates.json`。
2. 固定種子抽樣（`candidates_sample.json`）→ 分批 AI 評分（0–10，
   標準：文意自足、有啟發性、適合首頁）→ `scores/batch_*.json`。
3. `finalize.py` — 取 score ≥ 7、單一來源上限 70%，輸出
   `daily_quotes.json`（`{"quotes":[{text,url,title,source,score}]}`）。
   `url` 含頁內錨點（如 `ebook/03_trad.html#p-sc436a366`），已驗證與
   電子書 HTML 的 id 對應。

## 書籍更新後重建

`gen_all.py` 重建電子書後重跑 `build_quotes.py`；新增落進精選的候選需重新
AI 評分（人工或 subagent 批評，每批約 100 條），再跑 `finalize.py`。

## 擴充語料（361 → 730 / 1065 條）

`candidates.json`（16,382 條完整候選池）、`candidates_sample.json`（已評分的 2400 條）、
`scores/`（這 2400 條的 0–10 分數）**三者都納入版控**，供未來擴充重複使用：

1. 從 `candidates.json` 用不同/更大的固定種子額外抽樣（e.g. 再抽 1700 條），
   只對「新增」的條目做 AI 評分（沿用原兩來源比例原則）。
2. 把新分數與既有 `scores/` 合併，改 `finalize.py` 的 `TARGET` / `MIN_SCORE`
   再跑一次即可。**不需重評已評的 2400 條**，省下大規模評分成本。

## 前端（`index.html`）

- `fetch('daily_quotes.json')`，`idx = (dayNum * 2654435761 + 97) % len`
  （以**使用者本地時區**日播種——取 `new Date()` 的年月日再 `Date.UTC(...)/86400000`，
  每位訪客在各自午夜切換；同一時區同日一致，清單長度變動會重洗順序）。
- 預設 2 行截斷（`-webkit-line-clamp`），點文字或「展開全文」切換；
  「前往原文」以新分頁開啟錨點連結。
