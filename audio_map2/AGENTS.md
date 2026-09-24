# audio_map2 — 時間序 Word 音檔 Mapping 審核 UI 與進度

> Repo-wide rules: [`../AGENTS.md`](../AGENTS.md)。
> **對齊校對 skill（月份 JSON、第一字錨定、工具、ASR 速查）**：[`SKILL.md`](SKILL.md)。
> 產生器／規則：[`../tool/word_audio_map2/README.md`](../tool/word_audio_map2/README.md)。

## 這是什麼

`index.html` 審核「**時間順序版 Word 彙總**」對音檔的 mapping 結果
（2024-02 … 2025-05，共 14 個月份 JSON 放在本資料夾）。

- **JSON 內所有文字（問題／回答／提問人／開收場）來自 Word 檔**；SRT 只用來取播放起訖與
  `srt_preview` 對照——不是校對稿。
- **已 review 的段**以 `chapter_question_ids`／`chapter_indexes`（電子書 stable qid 清單／章節編號
  1–12）對應到 `wenda2_ebook` 前 12 章；電子書播放鈕由此注入（舊 `data/audio_map_word/word-*.json`
  已移除）。對應由 `tool/word_audio_map2/link_chapters.py` 內容比對寫回（分段調整時需重跑），欄位
  只在段上新增、不改文字／時間／status。

**完成／review 判定以「最後播放」為準**：UI 實際播放某段時寫入 `meta.lastPlayed`。只有
「有 `meta.lastPlayed`」且 `start != null` 的段，重建電子書後前 12 章才會出現播放鈕。
唯一例外：`zero: true`（零長度）段即使無 `lastPlayed`／`lastEdited` 也一律視為已確認。
align 器產出的 `status`（`manual/reviewed/auto/missing`）**不再是注入閘門**。

## 使用

本機需走 http server（fetch 相對路徑）：

```bash
python3 -m http.server -d /Users/paul/tai/taiguanglin.github.io 8000
# → http://localhost:8000/audio_map2/
```

- 左側選月份 → session；卡片 ▶ 播放該段（`../audio/*.opus`）；過濾器可只看
  ⚠低信心／插補／待人工／缺時間。
- 快捷鍵：`P` 播放暫停、`↑↓` 段落導覽、`N` 定位下一個未確認段（`Shift`+`N` 下一個已確認；
  只捲動不播放、不寫 `lastPlayed`）。
- topbar「跳瀏工具列」⤒/⤓ 同款循環定位（右鍵／長按才定位並播放）；徽章顯示本月份剩餘未確認
  段數（開場不計入，與側邊欄 `mustCalibrateItems` 口徑一致）。
- **完成＝實際聽過**：播放該段才寫入 `meta.lastPlayed`、session 才變綠；只微調時間不算完成。
  要持久化（寫回 GitHub JSON）按底部「💾 儲存」或「存收聽進度」。

### 卡片顏色

| 樣式 | 意義 |
|------|------|
| 紅框整卡 | confidence < 0.5，需特別仔細聽 |
| 徽章 高/中/⚠低信心 | ≥0.8 / 0.5–0.8 / <0.5 |
| notes: 待人工確認 | 找不到逐字對應、時間為比例夾入（用「待人工」過濾鍵集中審） |
| 雙檔合併時間軸 | 該日音檔分（上）（下）或文字檔未分段，UI 自動換檔播放 |
| 紅左框淡化卡 | 「零長度」段（師父未念）：起訖恆等、不可點播、自動算確認 |

## 段落結構操作：合併／分拆／刪除

卡片右上角（手機在 ✎ 編輯模式）提供結構鈕，慣例對齊 `tool/word_audio_map2/apply_resplit.py`；
三種操作都會重產 `index`／`stable_key`（`session_id#N`）／`question_id`／預覽欄位，即存本機草稿、
可 ↶ 復原。**結構變更後該 session 的「↺ 回復原樣」停用**。

- **⬆ 併上段／⬇ 併下段**（開場／收場不可併）：問答逐字併接、提問人相同保留否則「、」並列；時間取
  包絡 `[min start, max end]`（不內移已確認邊界）；章節取聯集、信心度取 min。**兩段都聽過才保留
  `meta.lastPlayed`**。
- **✂ 分拆**：文字分界＝游標處（無游標退第一個空行）；時間分界優先＝播放位置，否則＝本段結束時間。
  前半 `[start,分界]`、新段 `[分界,原結束]`；章節對應留前半、新段不帶、`q_text` 留空、`notes` 記
  `ui-split from #N`，須聽過才寫 `lastPlayed`。**零長度段不可分拆。**
- **🗑 刪除**：整段移除（帶章節對應會警告）；後面重新編號；**前後段時間邊界不連動**。

## 特別注意

- **2024-02…08**：主題式講解（未逐題念問題）且 ASR 差，「待人工」比例高，每段都要人工聽檔。
  **2024-11 之後**：逐題念名＋`师父说` 開收場，品質高、抽查即可。
- `2025-03-12`、`2024-12-09`：合併時間軸特例（見 tool README）。
- **零長度 `"zero": true`**：師父沒念。起訖強制相等（原起始為錨點）、時間欄唯讀、▶ 變「☐ 零長度
  （無音可播）」、點文字不可播；調整前後段時邊界自動吸附（可穿越多個零段）。注入器
  `tool/word2ebook/core/audio_map_injector.py` 遇 `zero` 直接跳過。
- 重新產生 JSON：`tool/word_audio_map2/build_maps.py --all --apply`（會覆蓋月份 JSON；章節子題拆分
  已凍結，重跑**不會**再拆被併的子題）。

## 校對進度（2026-09）

第一字錨定已完成**全部 14 個月**（2024-02 … 2025-05），最後完成的 `2024-03` 收尾如下；
逐段明細與各 session 教訓見 git 歷史（不再保存在本檔）。

- **2024-03**：25 sessions／1223 段；`status` = manual 1195／auto 26／missing 2；`openings_ok` 25、
  `closings_ok` 25；stats 已重算（`matched 1108`／`pending 17`／`low_conf 1`／`interpolated 0`）。
- null（conf 0）101 段＝音檔未讀／純文字答覆，依慣例標 `missing` 並在 `notes` 記原因（含
  `文字稿含時間戳之書面答覆，音檔未讀`、`音檔中找不到對應內容`）。
- 文字欄位與 `opening`/`closing` 逐值比對 `HEAD` **0 違改**；鏈完整；`validate_resplit.py` 硬檢查
  通過。
- **注入／跟播閘門仍是各段的 `meta.lastPlayed`**（UI 實際播放才寫入）——工程對齊完成後仍需人工在
  UI 逐段試聽確認；`zero: true` 段例外，直接視為已確認。
