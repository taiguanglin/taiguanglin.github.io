# qa_split_ebook — 問答錄2「拆分＋分類」管線（與 word2ebook 共用 `wenda2_ebook/`）

把 `wenda2_ebook/` 第 13–21 章（**stage 1 底稿**：2025年6月起的未分類月度答疑，
3,452 則）依 `tool/qa_curation/` 準則拆分子問題、分類到既有 12 章主題樹，重組成
**線上電子書 `wenda2_ebook/`（全分類合併版）**。2026-10-26 起為**就地轉換**：
`wenda2_ebook_word/` 中繼目錄已移除，stage 1（`tool/word2ebook/gen_all.py`）
直接重建 `wenda2_ebook/`，本管線接手就地轉成成品（見根 `AGENTS.md`「Main data
flows」）；音檔映射讀 `audio_map/`（站台根目錄單一 SoT）。

⚠️ 實驗性質：分類由 LLM 依準則產出（低信心條目在書中標「⚑復查」、
未歸類條目集中於 99 章），內容以原書為準。

## 管線（全部用鎖版 venv 執行）

> 音頻映射直接讀寫站台根目錄 `audio_map/*.json`（單一 SoT，2026-10-26 起）；
> 舊的步驟 0 `sync_audio_map.py`（把 `tool/word2ebook/data/audio_map/` 抄到
> `audio_map/`）已隨該副本一併移除。

| 步 | 指令 | 說明 |
|---|---|---|
| 1 | `venv/bin/python extract.py` | 解析 `wenda2_ebook/13–21.html`（stage 1 底稿） → `build/items.jsonl`（含音檔對位；多段 answer-text、`-N` 後綴 id 都處理） |
| 1b | `venv/bin/python extract_tree.py` | 自 `wenda2_ebook/01–12.html` 章內 TOC 抽 12 章主題樹（533 節點，L4 含 `hidden`）→ `build/section_tree.json`；分類 path 編號以此為準（L3 序號在 L2 內、L4 在 L3 內） |
| 2 | `venv/bin/python distill.py` | 準則蒸餾：主指南＋逐章 digest（定位/R/N 樹）＋逐節準則 → `build/classify_guide.md`、`build/criteria_digest/` |
| 3 | `venv/bin/python make_self_batches.py` | 產 47 批精簡輸入（q 全文＋a 前 250 字；sc=true 拆分候選留全文）→ `build/self_batches/batch_NNN.slim.jsonl`＋`tree_compact.txt` |
| 4 | **自制作業**（LLM 逐批） | 讀 `batch_NNN.slim.jsonl` → 逐則依準則判定 → 寫 `build/self_classified/batch_NNN.compact`（格式 `i\|ch-L2-L3(-L4)\|conf\|依據[\|flags]`，flags：nr／d／ru=path；拆分項另寫 `batch_NNN.splits.jsonl`，每子題一行含 path/conf/q/a 切分文，sub 連續） |
| 5 | `venv/bin/python expand_classified.py NNN …`（或 `--all`） | compact＋splits → 完整 `build/classified/batch_NNN.jsonl`；驗證批次守恆、path 命中樹；更新 `build/self_classified/progress.json` |
| 6 | `venv/bin/python gen_all.py` | 組裝**實驗分離版** `wenda2_ebook_sep/`（gitignore，舊實驗輸出）：12 章主題樹×簡繁、章目錄頁、index、全量搜尋索引（含 .hash）、播放鈕（拆分子題共用母條目音段）、99 未歸類收容章、`build/report.md`。**線上發布版不走這步**——改由 `gen_classified.py` 就地把 `wenda2_ebook/` 轉成分類合併版（stage 3） |

## 分類判定要點（詳讀 `../qa_curation/wenda2_split_classify_criteria.md`）

- 先負規則（各章 N 條）再正規則；12 是 fallback、優先序最低。
- 看「問句主軸＋師父答案主軸」，不看開頭情境、不按字面關鍵詞；
  多義詞（念佛／消業／夢／超度／回向／淫欲／疾病／劇本…）先查 §3.2 表。
- 拆分：編號子問題一律拆（「N、」「问题N：」「第N问」「①」），答案按師父
  作答順序對位切分；師父合併回答→保持一則、rule 註明 merged_answer；
  師父答「以後再講」→ conf 照常、加 d flag；源檔殘缺／答案未回應的
  孤兒片段→ nr。
- 節內排序＝時間升冪（由早到晚，gen 自動處理）；原文逐字不改寫。
  - **排序鍵＝最終顯示的 `question-time`**：先套用日期補全（`_INFERRED_DATES`
    推斷日期、日期正規化），再排序；補日期若排在排序之後，該則會被當成
    「無時間」而跳到小節最前面（2026-11 修正：01 章「修行翻出情緒/習氣」
    首則 2025-12-09 曾排在 2024-09-09 之前）。
  - 時間解析支援 `YYYY-M-D`、`YYYY/M/D`、`DD-MM-YYYY`、`MM-DD-YYYY`，
    以及 `HH:MM` / `HH:MM:SS`（微信後端時間戳帶秒，舊版整串落空而被
    誤判為無日期）；無法解析日期者排在小節最後。
  - 守門測試：`tests/test_date_ordering.py`（單元＋端到端排序＋發布版
    12 章逐小節稽核）。
- **段落還原（2026-10-27 起）**：PDF 條目的多段 Q/A 逐段包 `<p>`
  （`gen_classified._parts_to_html`；全站 CSS `p { margin: 15px 0 }` 提供段距）。
  舊版 `"".join(parts)` 把段落無縫黏成文字牆（1,358 問、2,759 答受害）。
  div id／錨點不變；`search_index` 內容在段落邊界多出一個空格
  （`get_text()` 行為），屬預期差異——下次重跑 `tool/daily_quotes/`
  管線時 `candidates.json` 會自然吸收。Word 條目沿用 docx 的 `<br/>` 軟換行，不受影響。

## 補充條目（`supplemental_items.json`，版控 SoT）

收錄 **PDF 有收錄、但 stage 1 渲染為小節尾 `<p>`、`extract.py` 只抽
`article.qa-pair` 而帶不進分類版**的內容——例如月度章「师父说」的結尾開示
（開場/結尾語在底稿是 h2 小節尾的 `.qa-opening`/`.qa-closing` 帶 play bar，
不是 Q&A 卡片）。`gen_classified.py`（stage 3）讀本檔，把每條 `items` 以
與 PDF 分類條目同一套包裝/排序/播放鈕注入路徑併入指定樹路徑（`path`）；
`audio` 欄位以合成 qid 註冊播放鈕（不寫回 `audio_map/*.json`）。
文字一律取自 **stage 1 底稿的解析原文**（與 PDF SoT 一致），只加段落分隔。
新增條目後重跑 stage 2＋3 即生效（例：2025-11-13 微信結尾開示 → `12-01-13`
正視神通）。

## 圖片保留（stage 2／stage 3）

發布版電子書的插圖有三種擺放位置，**stage 2 取 inner HTML、stage 3 只序列化
`question`／`answer` div 本體**，兩種做法都看不到圖：

| 來源 | 位置 | 誰收 |
|---|---|---|
| Word 章 | `question`/`answer` div 的**兄弟節點**（word2ebook 的 `_append_image` 接在區塊之後） | `extract.sibling_imgs` → `gen_classified._attach_imgs` |
| PDF 章 | div **內部**、但在 `question-text`/`answer-text` 之外（pdf_parser 的排版） | 同上 |
| PDF 章 | 夾在兩個 `qa-pair` 之間的**頁面層級配圖** | `extract.py` 附到前一則答案 |

> 2026-10-29 修：這條鏈路斷掉時，發布版的 `<img>` 數量是 **0**，而
> `assets/images/` 裡的 64 個 WebP 都在——讀者只看到「如下面兩張圖」卻沒有圖。
> 現已全數補回（Word 35 張 + PDF 29 張 = 64）。

守門測試：

```bash
cd tool/qa_split_ebook && ../../tool/word_audio_map2/.venv/bin/python -m pytest tests/
```

`tests/test_image_preservation.py` 涵蓋三層：
1. **單元**——`sibling_imgs` 三種位置都收得到、`_attach_imgs` 插回區塊內；
2. **產物**——發布版每個 `<img>` 都指向存在的檔案、每個資產檔都被引用、
   發布版確實有圖；
3. **來源對帳**——Word 與 PDF 原始檔的每一張圖（依 WebP 內容雜湊比對）
   都真的出現在發布版裡。改了 stage 2／3 的圖片處理後必須跑一次。

## 狀態與恢復

- **跨 session 續跑必讀：[`RESUME.md`](RESUME.md)** ——進度判定、每批流程、
  緊湊/splits 格式、實戰歸類慣例、筆誤自檢、啟動檢查表。
- 進度：`build/self_classified/progress.json`（done/failed 批號，expand 自動更新）。
- 已分類資料：`build/classified/batch_NNN.jsonl`（gen 前會歸檔到
  `tool/qa_split_ebook/classified/`，可進版控供複查）。
- 尚未分類的批次會被 gen_all 放進 99 章（不丟失，條目守恆）。
- 重新組裝：步驟 6 重跑即可（`wenda2_ebook/`（全分類合併版） 會整個重建）。
