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

### 「圖片題」block（沒有題目段的答案）

前 12 章有 **16 個 block 沒有 `<div class="question">`**：提問以截圖送出（`<img alt="提問人：日期 …">`）
或題目被換成 `（此問題丟失或未收集到）`／`问题缺失`／`(TAI師父自白)` 之類佔位。這種 block 沒有 qid，
`link_chapters.py`／`audit_html_blocks.py` 只走 question block，比對不到，過去一律沒有播放鈕。

- 對應寫在 **`chapter_answer_ids`**（該 block 自己的 `answer-…` id）＋ `chapter_indexes`，
  **不放進 `chapter_question_ids`**。
- 產生方式：`tool/word_audio_map2/link_image_blocks.py`（dry-run 預設、`--apply` 才寫檔），
  以**答案文字**比對（OpenCC t2s ＋ 著/着 摺疊），只動上述兩欄與 `notes`。
- 注入：`tool/word2ebook/core/audio_map_injector.py` 的 `inject_word_html_from_audio_map2()`
  有第二個 pass 專門處理這種 block（走 `by_answer`）；審核 UI 的「HTML 對應」在
  `chapter_question_ids` 為空時也會渲染 `答` anchor。
- 合併段（一段連講多個 block）也會掛上多個 `answer-…` id，並在 `notes` 記
  `html-portion: …播放鈕共用本段時間`——該 block 的時間是整段範圍，不是精準切點。

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
- **月份 JSON 的來源隨網站位置切換**（`github.js` 的 `loadMapJson`）：在
  `taiguanglin.info`（任何非 localhost 主機）改讀
  `raw.githubusercontent.com/…/main/audio_map2/<month>.json`，commit 完**幾秒內**就看到新資料，
  不用等 Pages 建置（建置失敗時也不會卡住）。localhost／`file://` 一律讀本機檔案（預覽工作樹）。
  raw 讀不到（離線／被擋）會自動退回已部署檔案，並記住不再每次都等逾時。
  **topbar 常駐徽章 `#dataSourceBadge`** 會標「來源 GitHub raw · 10/1 22:42」（綠）或
  「來源 已部署檔案 · 10/1 22:42」（黃）；滑過有完整 URL、**該 JSON 在 main 最後一次 commit 的
  時間**（含「8 小時前」相對時間）與判讀說明——**看見舊資料先看這顆**。`#saveStatus` 是會被播放／
  校時／存檔洗掉的暫時訊息，不能拿它當來源依據。
  - 時間來源是 `getLastCommit()`（commits API）。raw **沒有** `Last-Modified`、contents API 也**沒有**
    日期欄，commits API 是唯一來源；`Promise.allSettled` 與既有的 `getFile` 並行，不拖慢載入。
  - 讀不到（離線／額度用完）顯示「時間未知」，**不猜**。存檔成功時 PUT 回應自帶新 commit 時間，
    徽章立刻更新——重新整理後時間對得上＝存檔確實落地。
- 快捷鍵：`P` 播放暫停、`↑↓` 段落導覽、`N` 定位下一個未確認段（`Shift`+`N` 下一個已確認；
  只捲動不播放、不寫 `lastPlayed`）。
- topbar「跳瀏工具列」⤒/⤓ 同款循環定位（右鍵／長按才定位並播放）；徽章顯示本月份剩餘未確認
  段數（開場不計入，與側邊欄 `mustCalibrateItems` 口徑一致）。
- **完成＝實際聽過**：播放該段才寫入 `meta.lastPlayed`、session 才變綠；只微調時間不算完成。
  要持久化（寫回 GitHub JSON）按底部「💾 儲存」或「存收聽進度」。
- **防遺失機制（不要改壞它）**：本機草稿是唯一能救回「按了儲存但沒存完就離開」的東西。
  - **草稿本體在 IndexedDB**（`assets/draft_store.js`；`/audio_map/`、`/audio_map3/` 各有一份**相同**
    的副本，共用同一個 database，key 帶 `audio_map2/…` 路徑所以三個 UI 不會互相覆蓋）。
    localStorage 只留每個草稿一筆 metadata 索引（`audioMapEditor:draft:<path>`，約 120 bytes），
    所以 `listDraftPaths()`／`hasDraft()`／草稿徽章仍是同步的。
    ⚠️ **不要**改回把文字塞 localStorage：一個月份 JSON 就是 1–3.4 MB，而 localStorage 額度約 5 MB
    且**三個 UI 共用**；寫滿時 `setItem` 丟 `QuotaExceededError`，而存檔流程在第一個 `await` 之前
    會先 `flushDraft()`，於是整個上傳被中止（2026-10 實際發生過）。舊版留在 localStorage 的草稿會由
    `initDraftStore()`（`bootstrap()` 開頭 await）自動搬進 IndexedDB 並縮小索引，順便把額度還回去。
  - `scheduleDraft()` 是 800ms debounce，但有 **2500ms 硬上限**（`DRAFT_MAX_DELAY_MS`）——
    連續校稿不會把本機副本無限期往後推。
  - `flushDraft()` **回傳 promise、而且永不 reject**（草稿只是保險，寫不進去只 warn，不擋存檔）。
    按「儲存到 GitHub」時 `saveCurrentMap()` 會 `await flushDraft()` 再上傳——上傳途中重整仍找得回草稿。
    `beforeunload`／`pagehide`／`visibilitychange:hidden`（手機切 app、下拉重整）也各自觸發；
    ⚠️ IDB 沒有同步 API，這些離頁點只能「啟動」寫入，真正有充分時間落地的是
    `visibilitychange:hidden`（還有 debounce 已經寫過的那份）。
  - `pendingSave` 標記（`storage.js`）記錄「上傳開始但沒完成」；存檔成功才清除。下次開頁看到草稿時，
    對話框會明說上次上傳未完成、遠端仍是存檔前版本。該 key 與 prefs／PAT 走 `safeSetItem()`：
    localStorage 滿時只 warn 不拋（拋出去同樣會中止存檔）。
  - 存檔**失敗不會丟任何東西**：草稿與標記都留著，可直接重試。

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
