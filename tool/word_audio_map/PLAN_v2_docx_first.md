# 計劃 v2：docx 為真相源的全量音頻定位與直接覆寫（supersedes PLAN_mono_realignment.md）

> 執行者：AI agent。先讀 repo `AGENTS.md`、`audio_map/AGENTS.md`（對齊語意規範）。
> 本計劃取代 v1：v1 的中間產物（chrono_sessions / session_assignment / mono_probe /
> qid_bridge 等）**可復用**，但寫回策略與品質模型依本文件為準。
> 觸發原因：v1 結果經人工檢視仍差（保守 conf 模型造成 UI 大片黃紅、部分邊界不準）。

## 0. 使用者指令（原文要點）
1. 用 backup 目錄的 SRT × 時間序 docx 重新配對：找出**每一個** docx 答疑段落對應的音頻位置。
2. docx 段落 ↔ json 段落匹配；符合者**直接把該段時間覆寫**進 json。
3. 現有 audio_map/index.html 所用的 json 時間對齊資料**可以整批屏棄**。

## 1. 目標 / 非目標
**目標**
- D1（第一交付物）：`build/docx_audio_map.json` —— 時間序 docx 全部 ≈6,370 問答塊的
  `{session_id, start, end, labels, score, method}` 完整映射；無錨點者明確標 `unanchored`。
- D2：word-01~12.json 的時間欄位全部以此映射**直接覆寫**；舊時間值一律作廢。
- D3：全量機器驗收報告（覆蓋率/單調/邊界合規），以及新版人工抽聽清單。

**非目標**
- 不改電子書章節結構、不動 PDF 月地圖（13–21 章）、不改 question_id/q_text/a_text；
- 不做需要耳朵的判斷（聽檔仍是人類關卡）；
- 不再維護 v1 的保守 lcb→conf 映射作為 UI 主要訊號。

## 2. 核心方法變更（相對 v1）
| 面向 | v1 | v2 |
|---|---|---|
| 主產物 | 更新既有 json 的中間過程 | **docx→音頻完整映射**獨立成檔、可獨立審查 |
| 寫回策略 | 只改橋接成功且高分的段，其餘留舊值 | **先清空全部舊時間**，橋接成功才填新值；無對應者明確 `missing` |
| 品質訊號 | lcb 線性 conf（保守→一片紅） | **窗口覆蓋率**（塊文字在自身音區內的字元命中比例）＋邊界規則合規 |
| 邊界精修 | calibrate 事後 ±30s | 對齊當下就按 AGENTS 規則：口頭「下一个问题」字內插＞姓名錨點＞答案起點，自適應 lead-in；calibrate 最後僅做冪等拋光 |

## 3. 階段

### R0 — 重置與快照（半小時）
1. branch 已在 `mono-realign`，續用。
2. 快照現況到 `build/pre_v2_snapshot/`（12 個 word-*.json 原樣拷貝；僅供事後 diff 對照，不作為資料來源）。
3. 驗收閘：快照存在；`git status` 乾淨。

### R1 — docx→音頻全量定位（核心，1–1.5 天）
輸入：`build/chrono_sessions.json`（P1）、SRT 庫。
1. **日期綁定（吸收 v1 rebind 教訓）**：每章候選＝標註日 ±(14/21) 天內所有 sessions；
   內容投票決定 1..N 個按時序排列的 runs（允許一章跨多日，如 2024-02 早期章節），
   同日多源（公眾號/貼吧/上下集）沿用 P2 切分。產出 `build/session_assignment_v2.json`。
2. **逐塊定位**：DP 單調（`locate_dp`，原始 LCB≥12 才可指派）→ 字元位置。
3. **onset 精修（對齊當下完成）**：
   - 區塊間過渡：搜尋前後塊之間 SRT 的「下一个问题／下个问题」cue，字內插取「下」時間
     （`find_xia_time_in_cue`），作為**後塊 start**；否則姓名錨點；否則答案頭 LCB 起；
   - 自適應 lead-in（`adaptive_lead`，不切前句）；`end_i=start_{i+1}`；
   - 收場「…就到这里」偵測：末塊 end=收場起點，否則音檔尾；
   - 同場內建去重疊（鏈式天然保證，違例即 bug 直接 fail）。
4. **品質分（替代 v1 conf）**：
   `coverage`＝[start,end] 窗口內實際命中的塊拼音字元數 ÷ 塊總拼音字元數；
   `named`＝姓名是否在窗口開頭附近命中。
   status：`auto`（coverage≥0.60 且 (named 或 coverage≥0.75)）／`weak`（coverage≥0.40）／`review`（其他或未錨定）。
5. 產出 **D1：`build/docx_audio_map.json`**＋`build/docx_audio_report.md`
   （各章錨定率、auto/weak/review 分佈、未錨定清單）。
6. **閘門**：錨定率 ≥90%；同場重疊=0；runs 日期亂序=0。

### R2 — docx ↔ json 段落匹配（0.5 天）
沿用 `qid_bridge.py` 多輪指派（94.6%），再加兩個回收器：
1. 以 R1 的 `named`+coverage 提升同名候選信度（原 0.7/1.25 門檻微調）；
2. q_text 相似度為主的后備（a_text 被 docx 編輯過的題）。
產出 `build/qid_bridge_v2.json`＋衝突報告。**閘門：橋接 ≥93%。**

### R3 — 直接覆寫 word-*.json（0.5 天）
新腳本 `apply_docx_map.py`：
1. **第一步清空**：所有段的 `start/end/start_label/end_label/confidence/status/notes/
   srt_preview/session_id/audio_file/srt_file` 重置為 empty_range_fields()（status=`missing`）。
   ——兌現「屏棄舊對齊」。受保護狀態（locked/manual/none/meta.confirmed）不存在，若出現則跳過並記錄。
2. 第二步填充：橋接成功者寫入 D1 的時間與欄位；status 依 R1（auto/weak→`review` 弱者、
   review→`review`）；notes=`docx1(seq,score,cov,named)`。
   `weak` 是否給鈕：仍遵守注入門禁（未 confirmed 不出鈕），僅影響 UI 顏色。
3. 無 docx 對應的 json 段：保持 `missing`＋note=`no-docx-counterpart`（≈300–500 題，
   多為純文字開示/未答題——這是真相，不是錯誤）。
4. `version+=1`；stats 重算；`build/v2_diff_report.md`（與 R0 快照比對，透明化）。
5. **閘門**：schema 欄位集合不變；被覆寫段數＝橋接∩錨定數；protected 改動=0。

### R4 — 全量機器驗收＋重建（0.5 天）
1. 校驗：同場單調/零重疊/end 鏈/audio_file 存在於 `~/tai/audio/`；
2. `calibrate.py --apply` 冪等拋光至 dry-run≈0 → 再跑一次第 1 步校驗；
3. `gen_all.py` → `verify_build.py`（PDF 零回歸）；
4. 產出 `build/v2_acceptance.md`：D1 覆蓋率、json 填充率（auto/weak/review/missing）、
   與 v1 對照表；新版 `build/v2_spot_check.md`（45 筆分層抽樣：大位移/低覆盖/隨機）。
   **閘門**：verify_build PASS、json 填充率 ≥88%（橋接×錨定的自然積）。

### R5 — 人類抽聽（停點，同 v1）
人類依 `v2_spot_check.md` 聽檔；在 `/audio_map/` 修正＋確認。Phase 8 合併另行人類指示。

## 4. 不變式（沿 v1 §5，新增一條）
1. schema 欄位集合不變；question_id 永不改。
2. locked/manual/none/meta.confirmed 永不自動改寫（本期為 0）。
3. 電子書文字只來自主題版 docx。
4. 不編輯 wenda2_ebook/（一切經 gen_all）；不動 PDF 地圖。
5. 破壞性寫入先有 dry-run/快照。
6. **舊時間資料視為廢棄：任何階段不得拿 v1 後的 json 時間當輸入或比較基準**
   （R0 快照僅供事後人審 diff）。

## 5. 風險與緩解
| 風險 | 緩解 |
|---|---|
| 清空後橋接失敗的題失去任何線索 | missing 段保留 q_text/a_text 於 UI；diff 報告可回查舊值 |
| 二月型跨日章節誤綁 | R1 步驟1 投票+時序 runs；閘門含亂序=0 |
| coverage 高但位置錯（模板句撞詞） | named 共識＋DP 全局最優（非貪婪）＋人類抽聽把關 |
| 「下一个问题」缺失場次 | 落回姓名/答案頭 onset（AGENTS §Alignment 2）|
| weak/review 太多造成 UI 又一片黃紅 | 顏色語意已重定義：auto=雙證據、weak=單證據；真實呈現待校量 |

## 6. 交付物清單
D1 `build/docx_audio_map.json` ／ D2 覆寫後 `tool/word2ebook/data/audio_map_word/word-*.json`
／ D3 `build/docx_audio_report.md`、`build/v2_acceptance.md`、`build/v2_spot_check.md`。
