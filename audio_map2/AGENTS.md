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
右鍵／長按才定位並播放；徽章顯示本月份剩餘未確認段數。

**完成＝實際聽過**：點 ▶／點文字播放該段後，會寫入「最後播放」記錄
（`meta.lastPlayed`），側邊欄 session 才會變綠色（完成）；只微調時間不算完成。
要持久化進度（寫回 GitHub JSON），按底部的「💾 儲存」或「存收聽進度」。

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
