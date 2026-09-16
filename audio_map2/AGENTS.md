# audio_map2 — 時間序 Word 音檔 Mapping 審核 UI

> Repo-wide rules: [`../AGENTS.md`](../AGENTS.md)。
> 產生器／規則：[`../tool/word_audio_map2/README.md`](../tool/word_audio_map2/README.md)。

## 這是什麼

`index.html` 審核「**時間順序版 Word 彙總**」對音檔的 mapping 結果
（2024-02 … 2025-05，共 14 個月份 JSON 放在本資料夾）。

- **JSON 內所有文字（問題／回答／提問人／開收場）來自 Word 檔**；
  SRT 只用來取播放起訖與 `srt_preview` 對照 —— 不是校對稿。
- **已 review 的段**會以 `chapter_question_ids`（清單，見下）對應到
  `wenda2_ebook` 前 12 章；電子書前 12 章的播放鈕改由此注入（舊的
  `data/audio_map_word/word-*.json` 主題式地圖已移除）。對應**已固化**在
  月份 JSON 的段上（原本由已移除的 `link_chapters.py` 寫回，不再重新產生），
  欄位只在段上**新增**、不改文字／時間／status。

## 對應到電子書前 12 章（chapter_question_ids）

每個 segment 的欄位（已固化，不再重新產生）：

- `chapter_question_ids`：這個段對應的電子書 stable question id 清單
  （一個段可能對應多個主題子題，因彙總 docx 把 2–3 個子題併成一段）。
- `chapter_indexes`：對應的章節編號（1–12）。

**完成／review 判定以「最後播放」為準**：審核 UI 在實際播放某段時寫入
`meta.lastPlayed`（時間戳）。只有「有 `meta.lastPlayed` 記錄」且 `start != null`
的段，重建電子書後前 12 章對應段落才會出現播放鈕。align 器產出的 `status`
（`manual`/`reviewed`/`auto`/`missing`）**不再是注入閘門**——`status=manual`
但沒真正聽過的段一樣不亮鈕。

## 使用

本機需走 http server（fetch 相對路徑）：

```bash
python3 -m http.server -d /Users/paul/tai/taiguanglin.github.io 8000
# → http://localhost:8000/audio_map2/
```

操作：左側選月份 → session；卡片 ▶ 播放該段（`../audio/*.opus`）；
過濾器可只看 ⚠低信心／插補／待人工／缺時間。快捷鍵 `P` 播放暫停、`↑↓` 段落導覽、
`N` 定位到下一個未確認段落（`Shift`+`N` 下一個已確認；只捲動不播放、不寫 `lastPlayed`）。
topbar 左側的「跳瀏工具列」⤒/⤓ 按鈕同款功能：循環定位到下一個未確認／已確認段落，
右鍵／長按才定位並播放；徽章顯示本月份剩餘未確認段數（開場不計入、跳瀏也不會落在開場上，
與側邊欄 `mustCalibrateItems` 統計口徑一致）。

**完成＝實際聽過**：點 ▶／點文字播放該段後，會寫入「最後播放」記錄
（`meta.lastPlayed`），側邊欄 session 才會變綠色（完成）；只微調時間不算完成。
要持久化進度（寫回 GitHub JSON），按底部的「💾 儲存」或「存收聽進度」。

## 段落結構操作：合併／分拆／刪除

卡片右上角（手機在 ✎ 編輯模式內）提供四顆結構操作鈕——還原舊 `qa/` 校對編輯器
（已刪的 `assets/editor.word.js` 前身）的段操作，慣例對齊
`tool/word_audio_map2/apply_resplit.py` 與 SKILL.md：

- **⬆ 併上段／⬇ 併下段**：與前／後一個「問答段」合併（開場／收場不可合併）。
  問題與回答文字**逐字併接**（空行相接；同文只留一份）、提問人相同保留否則「、」並列；
  時間取兩段**包絡 [min start, max end]**（SKILL.md 規則：不內移已確認邊界，
  與前後段 `end[i]==start[i+1]` 銜接不變）；`chapter_question_ids`／`chapter_answer_ids`／
  `chapter_indexes` 取聯集（兩段原對應的電子書子題都改指向合併段）；信心度取兩段 min。
  **兩段都實際聽過才保留 `meta.lastPlayed`**，否則合併段視為未聽、需重聽。
- **✂ 分拆**：把一段拆成兩段。文字分界＝游標處（點擊「回答」文字即放置游標；
  沒有游標時退回第一個空行）；時間分界**優先＝播放器目前位置**（邊聽邊停在
  「唸回下一題題幹」處再按），否則＝本段目前結束時間（舊 qa 流程：先按「設結束」
  在拆分點）。前半 `[start, 分界]`、新段 `[分界, 原結束]`（用「設結束」先按過時
  新段為零寬，聽時再校）。**章節對應（chapter_question_ids）保留在前半**、新段不帶
  （無法自動判斷屬哪個子題；若新段才是電子書子題，請改 JSON 或重跑
  `link_chapters.py`）；新段 `q_text` 留空、`notes` 記 `ui-split from #N`，
  須實際聽過才會寫 `lastPlayed`。零長度段不可分拆。
- **🗑 刪除**：整段移除（confirm 會先警告，特別是帶章節對應的段——刪除即失去對應，
  重建電子書後該些問題不會有播放鈕）。後面段落自動重新編號；
  **前後段時間邊界不連動**（原段音檔範圍自所有段落下移除，鄰段請自行視需要調整）。

三種操作都會：依 `apply_resplit.py` 慣例重新產生 `index`（1..N 連續）、`stable_key`
（`session_id#N`）、`question_id`（sha1 公式與 `build_maps.py` 一致）、`q_preview`／
`answer_preview`；操作即存本機草稿、可 ↶ 復原（整份快照）。**結構變更後該 session 的
「↺ 回復原樣」停用**（段落已位移，單段對回原段會對錯），改用 ↶ 復原。載入時的本地
文字 overlay（`mergePdfTextFrom`）遇到結構與遠端／草稿不同的 session 會跳過，
不用舊結構文字蓋回合併／分拆後的段落。

## 卡片顏色

| 樣式 | 意義 |
|------|------|
| 紅框整卡 | confidence < 0.5，需特別仔細聽 |
| 徽章 高/中/⚠低信心 | ≥0.8 / 0.5–0.8 / <0.5 |
| notes: 待人工確認 | 找不到逐字音檔對應，時間為比例夾入 —— 用「待人工」過濾鍵集中審 |
| 雙檔合併時間軸 | 該日音檔分（上）（下）或文字檔未分段，UI 自動換檔播放 |
| 紅左框淡化卡 | 「零長度」段（師父未念）：卡片右上角 checkbox 勾選，起訖恆等、不可點播、自動算確認 |

## 特別注意的月份

- **2024-02 … 2024-08**：當期音檔是主題式講解（未逐題念問題），且 ASR 品質差，
  「待人工」比例高 —— 每段都要人工聽檔確認／修正。
- **2024-11 之後**：有逐題念名＋`师父说` 開收場標記，mapping 品質高，抽查即可；
  少數待人工段多半是問題以圖片提交或朗讀順序與 Word 不同。
- `2025-03-12`、`2024-12-09`：合併時間軸特例（見 tool README）。

**「零長度」標記（`"zero": true`，2026-09 新增，與 audio_map3 同步）**：卡片右上角
checkbox 勾選＝此段音檔長度為零（師父沒念）。行為：起訖強制相等（以原起始為錨點）、
時間欄唯讀、▶ 變「☐ 零長度（師父未念，無音可播）」、點文字不可播；調整前後段落時
其邊界自動吸附（可連續穿越多個零長度段，行為同 audio_map3）；勾選即寫入
`meta.lastPlayed`（自動確認）。注入器 `tool/word2ebook/core/audio_map_injector.py`
遇 `zero: true` 直接跳過（不產生播放鈕，等同零寬段）。

重新產生 JSON：`tool/word_audio_map2/build_maps.py --all --apply`
（會覆蓋本資料夾的月份 JSON；其章節子題拆分功能已隨舊 `data/audio_map_word/`
移除而凍結——重跑**不會**再拆被併的子題，手動修正請改在 UI 匯出或另存，
勿直接依賴重跑保留）。
