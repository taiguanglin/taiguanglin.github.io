# 《六祖壇經》L6–L8 毫秒級音頻對齊交付報告

> 範圍：依使用者 2026-11-24 指示，**完成 L8 即停止；L9–L27 不再處理**。本輪完成逐段音訊證據對齊、獨立高風險複核、SoT 寫入、sandbox／建置／網站驗收；**未代勾任何 confirmed／reviewed**，也不把低信心段宣稱為已完成人耳確認。

## 1. 完成結果

| 講次 | 裁決覆蓋 | start 改動 | 獨立複核 | 冪等／結構 | 主要指標（套用當時） |
|---|---:|---:|---|---|---|
| L6 | 73/73 | 71 | 22 accept／0 replace；2 個 note END 修正 | 3/3；零破口、倒序、負長度 | metric ±.3 **12/40→20/40**；±.7 **29/40→31/40**；span **71/90→74/90** |
| L7 | 82/82 | 82 | 52 筆：43 accept／9 replace／26 note_fix；實際合併 5 個未 confirmed replace | 3/3；零破口、倒序、負長度 | metric ±.3 **6/21→8/21**；±.7 **12/21→15/21**；late>.7 **2→0**；span **75/97→78/97** |
| L8 | 92/92 | 91 | 48 accept／0 replace／3 note_fix；含全部大改動、低 conf、27 contact | 3/3；零破口、倒序、負長度 | metric ±.3 **11/41→19/42**；±.7 **21/41→32/42**；span **84/97→84/97**；pin 精確段 **0→5**、bleed 0 |

最終 SoT：`audio_map3/liuzutanjing.json`，L8 三次套用雜湊均為
`c393afc8c5d96a4e41b39944dbab2a280c3e0360a915583bb4185c9d3006a698`。
第 2、3 次套用皆 0 段變更；每次均以施工前快照驗證非目標講次不變。

**後續人工版本保護**：L6/L7 在初裁套用後，另有後續人工修改並變成 reviewed=true；L5 也改為 reviewed=true。最終 L8 套用只動 L8，未以早期快照覆寫這些新版人工值。最終重建使用當時最新 SoT。

## 2. 第 4／5 期人工差異如何改變流程

1. 舊 `contact`／V1 退前段末字 END 是主要微調來源：在人工版 L4、L5 分別只有 **14.3%／8.3%** 落在 ±0.3s。
2. `weak-nearest/cov=0.00` 共 34 筆，人工改 24 筆；不得自動落地。
3. 最近實體停頓吸附會退化；最佳自動 hybrid 的 LOO MAE 仍 **0.644s**，L4 **1.010s**，大誤差只由 118 降至 114，不具備直接套用資格。
4. 單次語義 agent 盲測在 L4 反而由 0.940s 惡化到 1.493s，故新流程強制「完整逐段表＋獨立高風險複核＋隔離 sandbox＋3 次冪等」。
5. 長 ASR 洞必須用切片恢復完整段首；片窗時基互斥時只信文字順序，回到主 dump 或實體停頓定界，不能偽裝成精確值。

詳細證據：`audio_map3/skills/liuzutanjing-milli-align/GOLDEN_L4_L5_ANALYSIS.md`。
現行規則：`audio_map3/skills/liuzutanjing-milli-align/SKILL.md`。

## 3. 工具修正與防錯

- `milli_refine.py`：修 READ→zero 鏈錯誤、防止新增 start 倒序、原子寫檔；音訊交疊例外只走有 note 的 `preserve_end`。3 項測試通過。
- `audit_alignment.py`：檢查 golden／confirmed／reviewed／pid/text／非目標講次與結構缺陷。
- `sandbox_episode.py`：隔離套用 3 次，跑結構、before/after metric、batch、milli_audit；未 PASS 不碰 SoT。
- `build_maps.parse_ebook`：以 HTMLParser 取代會被 `.sutra-pin-host` 截斷的 regex；全五系列 **11,772/11,772** 段 pid/text 一致。
- `span_audit`：只有 `end<=start` 才算 zero，短於 1 秒的實念不再誤報 `skip_ok`。parser／short-READ 共 4 項測試通過。

## 4. confirmed-zero 保護矛盾（未擅自修改）

- **L7 [15]–[18]**：切片找到實念，與 confirmed zero 矛盾；建議值分別為 **124.247／128.390／148.820／178.477**。原值保留，見 `liuzutanjing_L7_confirmed_zero_blocked_r3.json`。
- **L8 [53]**：切片找到「自己悟了…不用向外求…指月之手…溝通或者交流」實念，與 confirmed zero@1047.290 矛盾；所有欄位原樣保留，見 `liuzutanjing_L8_confirmed_zero_blocked_r3.json`。
- **L8 [54]**：start=1075.644 會帶入前段「交流」2 字短收尾，依新版 V1 保留，不描述成乾淨前尾，conf 維持 0.55。

這些是人工試聽項目，不是本輪可自動翻轉的段落。其他 conf≤0.65、片窗時基互斥、同音嚴重段也保留在各期 earcheck，未灌水成高信心。

## 5. 最終建置與測試（全部實際執行）

| 檢查 | 結果 |
|---|---|
| `sync_para_pids.py` | 五系列 pid 全部一致 |
| books2ebook 鎖版 venv `gen_all.py` | 完成；搜尋索引 19,424／19,424；sitemap 更新 |
| books2ebook pytest | **97 passed, 2 skipped** |
| word2ebook pytest | **686 passed**（5 個既存 deprecation warnings） |
| `check_site.py` | **SITE CHECK OK** |
| audio_map3 Node tests | **4 passed** |
| milli_refine unittest | **3 passed** |
| jiangjing_para_map unittest | **4 passed** |
| `git diff --check` | 通過 |

最終全系列 span：L1 無 dump，所以總數 3,549；pin `bleed=2` 位於未處理的 L24／L27，**L6–L8 沒有新增 bleed**。最終產物中的 L6/L7 已是後續人工更新版，其 span 也會與初裁報告不同；不以舊指標覆蓋或推翻人工版本。

## 6. 交付索引

- SoT：`audio_map3/liuzutanjing.json`
- 總進度：`tool/jiangjing_para_map/reports/liuzutanjing_r3_progress.json`
- L6：裁決、earcheck、獨立 review、structural、sandbox（同目錄 `liuzutanjing_L6_*_r3.*`）
- L7：裁決、earcheck、獨立 review、confirmed-zero blocked、structural、sandbox（`liuzutanjing_L7_*_r3.*`）
- L8：裁決、earcheck、獨立 review、confirmed-zero blocked、structural、sandbox（`liuzutanjing_L8_*_r3.*`）
- 全系列 span：`tool/jiangjing_para_map/reports/span_audit_liuzutanjing.json`

未 commit／push；使用者可在 UI 對弱證據與 confirmed-zero 矛盾做最終人耳裁決。L9–L27 依指示保持原狀，不在本次交付範圍。
