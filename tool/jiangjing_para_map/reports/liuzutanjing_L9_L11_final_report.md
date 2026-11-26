# 《六祖壇經》L9–L11 音頻對齊交付報告

> 範圍：依使用者指示，**完成 L11 後停止；L12 以後不處理**。全程同一時間最多一個 sub-agent。已完成逐段音訊證據對齊、獨立高風險複核、SoT 寫入、sandbox／建置／網站驗收；**未代勾任何 confirmed／reviewed**，也不把低信心段宣稱為已完成人耳確認。

## 1. 完成結果

| 講次 | 裁決覆蓋 | start 改動 | 獨立複核 | 冪等／結構 | 主要指標（套用當時） |
|---|---:|---:|---|---|---|
| L9 | 108/108 | 108 | 29 accept／0 replace／5 note_fix | 3/3；零破口、倒序、負長度 | ±.3 **7/30→15/31**；±.7 **20/30→26/31**；span **103/113→104/113** |
| L10 | 107/107 | 107 | 57 accept／1 replace／4 note_fix | 3/3；零破口、倒序、負長度 | ±.3 **1/28→9/29**；±.7 **6/28→15/29**；span **103/116→106/116** |
| L11 | 87/87 | 86 | 84 accept／3 replace／12 note_fix | 3/3；零破口、倒序、負長度 | ±.3 **8/33→12/34**；±.7 **18/33→26/34**；span **86/99→87/99** |

最終 SoT：`audio_map3/liuzutanjing.json`，L11 三次套用雜湊均為
`a0fc3dcc7b4f4e9ac923962066c212aaeddb8664eeb2f261b216323a47950d6b`。
第 2、3 次套用皆 0 段變更；每次均以施工前快照驗證非目標講次不變。L6/L7 最新人工 golden 未改。

## 2. 本期關鍵修正

### L9

- 五個 ASR 洞恢復文字；[87]/[88] 分列 SUTRA 首次「離世覓菩提，恰如求兔角」與 COMM「如果你離開了這個人世間」，未犯 L7[76] 型合併。
- Reviewer 修正 5 筆證據記錄，包括片窗共同字時基差最大約 3.6s、接觸型停頓與首次白話末字。

### L10

- 26 段超過 2 秒、32 個 contact 全查；[13] −21.773s、[37]/[38] 整組重排經主 dump＋新切片支持。
- [87] strict 停頓 0.542s 屬 0.5–1s，公式由誤用 .458 改為 .554，start 1490.643→**1490.695**。
- [22]/[74] span 轉差經查為工具命中本段後字或前段文字，不誤改正確 start。

### L11

- **[20] 162.837→166.745**：初裁誤把前段 SUTRA 重念當本段白話開頭；標點校正後三窗一致，改以達後實停 166.540354–166.987208 取位。
- **[77] 1361.268→1361.066**、**[98] 1784.412→1784.185**：0.806792s／0.905438s 均屬 0.5–1s，應 ×.554 而非 ×.804。
- **clip_probe 標點／timestamp 根因修正**：舊版直接 `text[k]→ts[k]`，在標點後整串錯位，製造假時基漂移。新版 `aligned_clip_chars()` 先以 `PUNCT_RE` 對齊發音字；若模型 timestamp 含標點才接受 raw 對齊，數量仍不符就全部 `nan`／`invalid`，不再捏造毫秒值。四項回歸測試通過，校正切片見 `liuzutanjing_L11_hole_correct_r3.txt`。
- [26] 現值是 hosting 而非 contact；[51] 撤回「三窗一致」；[21][34][51][57][66][76][94][95] 的短收尾與 own_first 註記均按 reviewer 修正。

## 3. 寫入 skill 的持久規則

已更新 `audio_map3/skills/liuzutanjing-milli-align/SKILL.md` 與通用 `milli-align/SKILL.md`：

1. R 存在與 R 所有權分開（L6[48] READ→zero）。
2. SUTRA 首次宣讀與 COMM 白話開頭分列（L7[76]、L9[87]/[88]、L11[20]）。
3. 單窗時基吻合不是 golden；長洞需整組內容、實停與鄰段證據。
4. 標點／timestamp 先對齊，數量不符全部 nan，禁止直接索引配對製造假漂移。
5. 最新人工值永遠優先，舊表／舊建議值不得回套；L4–L7 回歸分開計算。
6. 初裁與 reviewer 不得並行超過一個 sub-agent；每批先落地再續裁。

分析文件：`audio_map3/skills/liuzutanjing-milli-align/GOLDEN_L6_L7_ANALYSIS.md`、`GOLDEN_L4_L5_ANALYSIS.md`。

## 4. 最終建置與測試（全部實際執行）

| 檢查 | 結果 |
|---|---|
| `sync_para_pids.py` | 五系列 pid 全部一致 |
| books2ebook 鎖版 venv `gen_all.py` | 完成；搜尋索引 19,424／19,424；sitemap 更新 |
| books2ebook pytest | **97 passed, 2 skipped** |
| word2ebook pytest | **686 passed**（5 個既存 deprecation warnings） |
| `check_site.py` | **SITE CHECK OK** |
| audio_map3 Node tests | **4 passed** |
| clip_probe／refine 自訂測試 | **7 passed** |
| `git diff --check` | 通過 |

最終全系列 span 執行時，L1–L7 dump 在 `/tmp` 已被清除而跳過，因此總結只使用可取得的 2,978 段，**不把缺 cache 當對齊缺陷，也不假稱全系列完成**。L11 本身 span=87/99。pin `bleed=2` 位於未處理的 L24／L27；L9–L11 無新增 bleed。

## 5. 交付索引

- SoT：`audio_map3/liuzutanjing.json`
- 總進度：`tool/jiangjing_para_map/reports/liuzutanjing_L9_onward_progress.json`
- L9：裁決、earcheck、獨立 review、structural、sandbox（同目錄 `liuzutanjing_L9_*_r3.*`）
- L10：裁決、earcheck、獨立 review、structural、sandbox（`liuzutanjing_L10_*_r3.*`）
- L11：裁決、earcheck、獨立 review、校正切片、structural、sandbox（`liuzutanjing_L11_*_r3.*`）
- 全系列 span：`tool/jiangjing_para_map/reports/span_audit_liuzutanjing.json`

未 commit／push。請使用者在 UI 優先試聽各期 conf≤0.75 與 ASR 洞段；這些保留人工裁決標記，沒有被當成高信心完成品。L12 以後依指示保持原狀。
