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
- 節內排序＝時間升冪（gen 自動處理）；原文逐字不改寫。

## 狀態與恢復

- **跨 session 續跑必讀：[`RESUME.md`](RESUME.md)** ——進度判定、每批流程、
  緊湊/splits 格式、實戰歸類慣例、筆誤自檢、啟動檢查表。
- 進度：`build/self_classified/progress.json`（done/failed 批號，expand 自動更新）。
- 已分類資料：`build/classified/batch_NNN.jsonl`（gen 前會歸檔到
  `tool/qa_split_ebook/classified/`，可進版控供複查）。
- 尚未分類的批次會被 gen_all 放進 99 章（不丟失，條目守恆）。
- 重新組裝：步驟 6 重跑即可（`wenda2_ebook/`（全分類合併版） 會整個重建）。
