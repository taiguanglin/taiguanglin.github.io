# 音頻對位全量複掃報告（2026-10-26 第三輪）

> 【2026-10-26 同日註記】本輪完成後，audio_map 的 SoT 已收斂為站台根目錄 `audio_map/`
> 單一副本（`tool/word2ebook/data/audio_map/` 舊副本與 `qa_split_ebook/sync_audio_map.py`
> 已移除，產生器／注入器／抽取器直接讀寫 `audio_map/`；`audio_map/AGENTS.md` 已自
> git 歷史恢復並更新）。下文「UI↔SoT」的區分自此不存在。
> 電子書為 9,241 則（本報告 31 行的 9,242 為刪卡前的即時數字，正文其後的重建
> 已以 9,241 為準）。

範圍：`audio_map/` 9 個月份（2025-06…2026-03）、108 個 session、3,457 段、108 個 closing。
審計工具：`tool/qa_split_ebook/build/audit_all.py`、`audit_boundary.py`、`audit_answer_where.py`。

## 一、本輪完成的三項工作

### 1. 2025-07-07 貼吧 #38「一千萬彩票」交錯作答 → 兩段式播放 ✓
師父先答 #38 前半（4406.59–4451.31），中間先答 #39（盤古／女媧，4451.31–4469.53），
再回頭補完 #38（「再呃再回到這個一萬…一千萬的問題啊…」4473.110–4530.760）。
處理比照 `audio_map2/2024-03-26` 唐偉 `two_part_group` 先例：
- 映射段 #38 加 `parts: [[4406.59,4451.31],[4473.11,4530.76]]`；
- 注入器（`audio_map_injector.py` 新增 `_seg_parts()`、`gen_classified.py` 支援
  `data-segments`）→ 播放鈕兩段式連播，`08-qa-audio.js` 既有邏輯即可依序播放；
- #38/#39 notes 均註記特殊情況（`two-part-playback` / `interleaved-answer`），方便未來辨識；
- #39 範圍刻意不切開（4451.31–4530.76），維持「本段 end＝下段 start」鏈連續。
驗證：`wenda2_ebook/02.html` 已輸出
`data-segments="[[4406.59,4451.31],[4473.11,4530.76]]"`；03.html 唐偉先例不受影響。
新增測試 `test_two_part_playback_carries_data_segments`（33 passed）。

### 2. 2025-07-12 貼吧 #10「苏小雅Helen」師父跳過 → 徹底刪除 ✓
PDF 標「无回答」；音檔僅提示語「下一个问题，苏小雅Helen啊，」（506.63–510.44），
師父直接回答下一題（510.460「你可以那么理解啊」）。依指示「沒回答就不出現在問答錄」：
- PDF：`tool/fix_20250712_suxiaoya_remove.py` 整卡塗銷（第 638 頁 10 行，鄰卡完好）；
- 映射：刪段＋重編號（30 段）；#9.end 507.25→510.44（吸收提示語）、#10.start
  509.785→510.44，鏈連續；`qid_to_sep_chapter.json`、`audio_dates_supplement.json`
  移除該 qid（`tool/pdf_audio_map/apply_20261026_fixes.py`，可重跑＋`--check`）；
- 分類資料：刪卡使 `extract.py` 的 seq 全體後移 → `tool/qa_split_ebook/realign_classified_seq.py`
  以 qid 重對位全部 3,458 行（丟 1 行、改 i 2,752 行；`build/batches/` 暫存亦同步，
  並清掉 09-01 合併遺留的過期行）。
驗證：電子書 9,242→9,241 則；全書無「苏小雅Helen」；3,458 行逐行比對
qid↔章節 0 不符；#9/#10 邊界 510.44 已入 HTML。

### 3. 全量「逐一」複掃 ✓
- `audit_all.py`：**0 error**、29 warns（見下表）；上輪 35→29（#38 交錯作答、
  #15 zero 段誤判、蘇小雅段已消除；審計器並新增 parts 聯集視窗與 zero:true 豁免）。
- `audit_boundary.py`：3,457 段全掃，起點分佈無 ±8 秒外離群。
- `audit_answer_where.py`：16 筆候選（#38 已退出清單），均為「師父重唸自己先前講過
  的句子」型 n-gram 誤報或已知低覆蓋段，非錯位。
- `pytest tool/word2ebook`：645 passed、1 failed（既有 `test_gen_all_repo_layout`，
  與本輪無關）。
- `daily_quotes` 三步管線：**零 diff**、稽核通過（該卡答案「无回答」本非候選）。
- UI↔SoT：9 個月份 JSON `audio_map/` 與 `tool/word2ebook/data/audio_map/` 逐月 byte-identical。

## 二、目前剩下的問題（全部為 warn 級，0 error）

### A. 單一源頭、無法在映射層修復（需原音/SRT 補件）
| # | 位置 | 問題 |
|---|------|------|
| 1 | 2026-02-04-wechat #18 ＋ closing | SRT 比音檔短 80.2 秒（字幕止於 1317.265s，段窗到 1394.59s）→ 覆蓋率 0.00、closing 無法驗證。需重新轉寫補 SRT。 |

### B. 已人工核可為誤報／語義學正常（不建議再動）
| # | 位置 | 問題 |
|---|------|------|
| 2 | 2025-06-13-wechat #21 | 提示語後 6 秒語音偏下題——孤兒提示語，已人工確認邊界無誤 |
| 3 | 17×answer-coverage-low | 答案覆蓋率 0.14–0.54：師父以口語重述、省略原句、穿插寒暄所致（如 2025-07-12-tieba #3 師父答「心诚则灵」類意譯；2026-02-02-guanwang #43 師父僅簡短回應），人工複聽無錯位 |
| 4 | 8×question-not-addressed | 前 15 秒與提問相似度低：師父先閒聊再切入、或先覆誦樓層號（2025-11-11-guanwang #14 同類 late-boundary），已抽樣核可 |
| 5 | 3×late-boundary | 提示語後仍有 5–6 秒語音偏下題：師父自問自答式過場，已核可 |
| 6 | 16×answer-where 候選 | 師父重唸先前講過的片語（如 2025-12-11 #23「问腿疼有关节」）被 n-gram 命中在舊時間點，非映射錯位 |

### C. 環境／工程債（與對位無關但如實列出）
| # | 項目 | 說明 |
|---|------|------|
| 7 | closing.end vs ffprobe | 各月 closing 尾端比實際音檔長 1–4.4 秒尾靜音（播放器停 1–4 秒），屬 benign，修齊需逐檔重測尾靜音 |
| 8 | `test_gen_all_repo_layout` | 既有失敗：測試期望 OUTPUT_FOLDER=`wenda2_ebook`，實際為 `wenda2_ebook_word`（測試過時，非本輪造成） |
| 9 | `tool/qa_split_ebook/build/batches/` | LLM 分批暫存為 gitignored 暫存資料，本輪已順手同步，但未來任何刪卡/合併後需留意它不會自動重生成 |

**結論**：3,457 段結構 0 錯誤；唯一實質待辦是 #1（2026-02-04 SRT 補轉寫），
其餘為誤報或已知良性，無需再改映射。

## 三、本輪修訂檔案
- 資料：`audio_map/2025-07.json`＋SoT 副本、`qid_to_sep_chapter.json`、
  `audio_dates_supplement.json`、`classified/batch_010–045*.jsonl`（i 重對位）
- 程式：`tool/word2ebook/core/audio_map_injector.py`、`tool/qa_split_ebook/gen_classified.py`
- PDF：`問答錄2/2025年6月-9月答疑合并（未分类）.pdf`（蘇小雅卡塗銷，增量存檔）
- 重建：`wenda2_ebook/` 24 檔（含搜尋索引）
- 新腳本：`tool/fix_20250712_suxiaoya_remove.py`、`tool/pdf_audio_map/apply_20261026_fixes.py`、
  `tool/qa_split_ebook/realign_classified_seq.py`
- 規格/測試：`openspec/specs/pdf-audio-map/spec.md`（兩段式情境）、`test_audio_map_injector.py`
