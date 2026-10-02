# tool/daily_quotes — 首頁「每日精選」語料管線

產出 repo 根目錄的 `daily_quotes.json`，由 `index.html` 前端依日期播種輪播展示。

## 流程

1. `build_quotes.py` — 從 `wenda2_ebook/search_index_trad.json`（answer）與
   `ebook/search_index_trad.json`（content + answer）做規則過濾
   （長度 60–400、黑名單、CJK 比例、**排除經文**、去重）→ `candidates.json`。
2. 固定種子抽樣（`candidates_sample.json`，2400 條）→ 分批 AI 評分（0–10，
   標準：文意自足、有啟發性、適合首頁）→ `scores/batch_*.json`。
3. `select_1095.py` — 產出 1095 條 `daily_quotes.json`：
   - **AI 骨架**：`scores/` 中 score ≥ 7 的 341 條（品質骨幹；數字會隨過濾規則
     與電子書重建而變動，實測於現行 `daily_quotes.json`）。
   - **啟發式補充**：`candidates.json` 中尚未被評到的候選，以「可讀性啟發」
     （長度窗、結尾標點、教學詞、暱稱/時間戳/問號片段罰分、括號配對…）排序
     補足到 1095 條（實測 754 條）；單一來源（ebook）上限 70%（實測 ebook 766／wenda2 329）。
   - `url` 含頁內錨點（如 `ebook/03_trad.html#p-sc436a366`），已驗證與電子書
     HTML 的 id 對應。
4. `audit_quotes.py` — 稽核成品（見下）；有經文／斷鏈／重複就 `exit 1`。

> `score` 欄 = AI 分；`heuristic` 欄 = 啟發式分（無 AI 分的條目才帶）。

## 排除經文（`scripture_filter.py`）

每日精選只放 Tai 師父自己的話，**經文不該出現在首頁**。判定收斂在單一模組
`scripture_filter.py`，由 `build_quotes.py` 與 `select_1095.py` 共用（過去兩支腳本
各自帶一份弱規則、會各自漂移，於是經文漏進成品，例如六祖壇經「師示眾云：
善知識！本來正教，無有頓漸……」）。三道互相獨立的防線：

| | 規則 | 依據 | 現行命中 |
|---|------|------|---------|
| **A** | 結構錨點（權威） | ①講經系列以楷體排的**原經文** → `<div class="sutra-text para-block" id="p-x">`；②《金剛經 心經》《圓覺經》每章的**白話譯文** → 落在 `<div class="label-heading">譯文</div>` 與下一個 label 之間的段落（`解析`／`註解`／`本章大義` 才是老師的講解，保留）。這些 id 與 `search_index*.json` 的 url **一一對應**（實測 sutra-text 4,231/4,231 全中） | 候選池 991 條、成品 30 條 |
| **B** | 文言啟發式 | 命中古典對話／稱謂標記（`佛告`／`善知識`／`須菩提`／`云何`／`爾時`／`如是`…）**且**現代語助詞 ≤ 3 | 候選池 11 條、成品 0 條 |
| **C** | 人工複查清單 | `exclude.json`：講經書「解析」區段裡偶爾整段其實是經文白話譯文，A/B 分不出來 | 成品 2 條 |

B 補的是不在上述區塊裡的經文（例如書末附錄）。實測 B 的精確率 100%（11 條全是
真經文，零誤殺）。

⚠️ **刻意不做**「現代助詞密度低就排除」：講經系列的講解本身是端正的書面語
（《圓覺經》《楞伽經》尤甚），單看文白會誤殺師父的講解——一定要搭配古典
標記才安全。

### 「引用經文」不算經文段落

師父在講解時引一兩句經文是正常的，**只要師父自己的話是段落主體就保留**。
人工複查後刻意留下這三條（引用比例都低於一半，且老師都有詮釋）：

| url | 引用內容 | 占比 |
|-----|---------|------|
| `ebook/09_trad.html#p-sc9d0eb8a` | 六祖壇經神秀偈 | ≈19% |
| `ebook/08_trad.html#p-sbd299956` | 楞伽經四法 | ≈40% |
| `ebook/03_trad.html#p-se9561748` | 《地藏經》光目女願文 | ≈44% |

若要更嚴格（例如連 40% 的引用也不要），把 `scripture_filter.MODERN_MAX` 調低
並新增一條「引文佔比 > N% 即排除」的規則即可；目前刻意不这么做，因為會誤殺
師父講經時最自然的引用方式。

## 稽核成品

```bash
python3 tool/daily_quotes/audit_quotes.py            # 經文／斷鏈／重複／條數／來源配額
python3 tool/daily_quotes/audit_quotes.py --strict   # 放寬版文言掃描也視為失敗
```

除三道硬規則外，`audit_quotes.py` 還會跑一次**放寬版**掃描（門檻放寬到 8 個現代
助詞）並印出結果供人工複查；講解文字偏書面語會誤報，所以預設只警告。
重跑 `build_quotes.py` → `select_1095.py` 後務必跑一次稽核再提交。

⚠️ 規則只能涵蓋「結構上就是經文」的段落。講經書的「解析」區段偶爾整段其實是
經文白話譯文（C 規則即為此而生），**重建管線後仍應把成品重新送一次人工複查**
（本輪 1,095 條已逐條複查完畢）。

## 擴充 / 提升品質

- `candidates.json`（15,299 條完整候選池）、`candidates_sample.json`（已 AI 評的
  2400 條）、`scores/`（0–10 分數）皆納入版控。
- 日後有 AI 評分容量時，可對「啟發式補充」的 754 條再跑一次 AI 評分替換，
  或對 `candidates.json` 抽更多樣、評完後改 `select_1095.py` 的 `TARGET`。
- 電子書重建後 `search_index*.json` 會變，`candidates.json` 應重跑，否則會留下
  指向已不存在段落的**斷鏈**（稽核會擋下）。

## 前端（`index.html`）

- `fetch('daily_quotes.json')`，`idx = ((day * 2654435761 + 97) % len + len) % len`
  （以**使用者本地時區**日播種，午夜本地時間切換；負 offset 亦取正模）。
  同日同機一致，清單長度變動會重洗順序。
- **日切換**：header 列固定高度，含「◀◀ 前一個月 / ◀ 前一天 / 今日 / 後一天 ▶ / 後一個月 ▶▶」
  按鈕，點「今日」回到今日；按鈕位置不隨內容長度跳動（可連續點擊）。
  跳月時日期會夾到目標月份最後一天（如 1/31 → 2/28）。
- 預設 2 行截斷（`-webkit-line-clamp`）；內容 ≤2 行時自動隱藏「展開全文」。
- 「前往原文」以新分頁開啟錨點連結。
- **簡繁**：語料為繁體，靠全站 `lang-switch.js` 的 MutationObserver 對動態注入
  的文字即時轉換，載入與切日/切繁簡皆會正確轉換。
- **字型**：`tool/fonts/build_fonts.py` 會把整個 `daily_quotes.json` 納入子集語料
  （動態注入的文字也需自架字型覆蓋）；換過語料後請重跑字型建置。
