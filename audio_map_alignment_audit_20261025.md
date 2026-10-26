# 音檔對齊全量稽核報告（2026-10-25）

> 【2026-10-26 註記】audio_map 的 SoT 已收斂為站台根目錄 `audio_map/` 單一副本
> （`tool/word2ebook/data/audio_map/` 舊副本與 `qa_split_ebook/sync_audio_map.py`
> 已移除）。本報告為當時雙副本狀態下的歷史紀錄，文中「UI／SoT」的區分已不存在。
>
> 範圍：`audio_map/`（校稿 UI）與 `tool/word2ebook/data/audio_map/`（canonical SoT）9 個月全量
> 108 場、3,458 段、108 個收場。目標：逐段確認邊界／答案落點，修正有 SRT 證據的問題，
> 並列出仍需人工決定的項目。

---

## 一、稽核方法（全部逐段執行）

| 檢查 | 內容 |
|---|---|
| 結構鏈 | `opening.end == 段1.start`、段 i `end == 段 i+1.start`（±0.001）、`段末.end == closing.start`、`closing.end ≤ ffprobe 音檔長度` |
| 完整性 | 缺值／零長／負長區間、`meta.lastPlayed`、SoT↔UI 一致性、`stats` 計數 |
| 語意對位 | 每段 SRT 視窗 vs `q_text`／`answer_text`（字元 bigram Dice、答案覆蓋率、NextScore、提示語邊界） |
| 答案落點 | 把 PDF 答案切成 6 字 n-gram，在整場 SRT（含逐字時間索引）搜尋 → 判斷答案語句「落在本段窗口內／窗口外／整場未出現」 |
| 起點-onset | 每段起點對到師父「下一個問題／下一位／X 樓」提示 cue 的時刻，統計偏移分佈 |
| 收場 | `closing.py` 的收場語偵測（`回答到這／就說到這／回答到這裡`…）＋SRT 尾段 |
| 字幕完整性 | 每場 SRT 最後一條字幕 vs 音檔長度（找 ASR 截斷） |

稽核腳本（皆在 `tool/qa_split_ebook/build/`，gitignored）：
`audit_all.py`（結構＋語意）、`audit_boundary.py`（起點-onset 分佈）、
`audit_answer_where.py`（答案落點）、`inspect_seg.py`（單段人工複聽）。

---

## 二、本次已修正（11 類，全部有 SRT 證據）

| # | 位置 | 問題 | 修正 |
|---|---|---|---|
| 1 | canonical SoT（6 個月） | `tool/word2ebook/data/audio_map/` 落後 UI（仍含零長段、4 個缺值段、6 個缺 `lastPlayed`、舊 `stats`） | 以 UI（使用者最新校對結果）回寫 SoT；**9 個月現已 byte-identical** |
| 2 | `2025-06-09-wechat` #18 | 回答尾聲 12.705s 落在兩段之間無人負責（SRT 1776.399–1789.4「但他就是該有的樣子了 哈啊」，正是 `answer_text` 末句「那就是它該有的樣子」） | #18.end → `1789.104`（＝#19.start） |
| 3 | `2025-06-10-tieba` #27/#28 | 0.171s 重疊（#27.end 2954.86 vs #28.start 2954.689；下一題 cue 起點 2954.93） | #28.start → `2954.86` |
| 4 | `2025-06-13-tieba` #15/#16 | #15 本身無回答（PDF 答案＝「上一回答里。」），其範圍卻含第 6 題提示「然後嗯第六個問題…」 | #15 標記 `zero: true`（師父未念）；#16.start → `1580.485` |
| 5 | `2025-12-09-guanwang` #31/#32 | #31 的補充回答（3381–3440s「功德不是人家要的…」）被算進 #32 窗口 | #31.end / #32.start → `3442.09`（＝第 32 題真正起點） |
| 6 | `2026-01-07-guanwang` 收場 | 收場語「這個問題你的問題就回答到這裡吧」被算在最後一段，closing 零長 | 切出 closing `[4761.4, 4763.685]`，最後一段 end → `4761.4` |
| 7 | `2026-02-05-guanwang` 收場 | closing 缺值，但 SRT 有收場語「好了啊／你的事就先說到這裡吧哈」 | 補 closing `[2617.54, 2619.995]`，最後一段 end → `2617.54` |
| 8 | `2025-07-09-wechat` 收場 | 零長 closing，且 `srt_preview` 誤抓上一題答案 | 明確標記 `zero: true` + `no-spoken-session-close` |
| 9 | `2026-02-07-guanwang` 收場 | closing `start/end` 為 null（`status: missing`） | 明確標記 `zero: true`（確實無收場語） |
| 10 | 5 個月的 `stats` | `matched` / `closing_ok` 過時（2025-06 333→338、2025-07 400→401、2025-11 464→468、2026-02 closing_ok 10→12、2026-03 333→334） | 重算 |
| 11 | 注入器 | `zero: true`（師父未念）在 PDF 章與分類電子書仍被注入播放鈕（點下去只有空白） | `tool/word2ebook/core/audio_map_injector.py` 新增 `_is_audio_map_reviewed()`；`tool/qa_split_ebook/gen_classified.py` 略過 zero 段；OpenSpec＋單元測試同步更新 |

---

## 三、仍存在的問題（需人工決定，共 5 項）

### ① 2025-07-07-tieba #38 / #39 交錯作答（唯一需要決策的實質問題）
- #38＝「1、我想多做功德，然後求中一張一千萬的彩票，這種方式是否如法？會實現嗎？」
  音檔首段 4406.59–4451.15。
- 師父接著先回答 #39（「2、盤古開天闢地…」）4451.31–4469.53，
  **再回頭補完 #38**（4473.11–4530.76，「再呃再回到這一千萬的問題啊…」）。
- 現況：#38 播放到 4451.31 就停（答案缺尾），#39 的播放含 #38 的補答。
- 純時間區間無法拆開這兩題（兩段音檔交錯）。建議二選一：
  1. 比照 2025-09-01 合併成一張卡（兩個問、一次回答）；
  2. 允許 #38 的播放延伸到 4530.76（與 #39 重疊），並在 `notes` 註明。

### ② 2026-02-04-wechat 的 SRT 檔尾缺 80.2 秒字幕
- SRT 最後一條字幕停在 1317.265s，音檔長 1397.498s（其餘 107 場的 SRT 皆完整）。
- 受影響：#18 `[1341.74, 1394.59]`（讀《妙法蓮華經》成佛）與該場收場**無法用 SRT 驗證**。
- 需重跑 ASR（`tool/sense_voice`）或人工複聽確認；目前該段時間是使用者校對值，未更動。

### ③ 2025-07-12-tieba #10「師父跳過」
- PDF 答案標「無回答」；音檔只有「下一個問題，蘇小雅…」（507.25–509.8）。
- 對齊無誤，但建議在書面標註「師父未答」，以免讀者以為漏音。

### ④ 2025-06-13-wechat #21 尾端有孤兒提問提示
- 2065.37–2070.885「那下一個問題我有啊，這個上面呃上面已經問過了哈」——該問未建檔，
  提示語落在 #21 的尾巴（不影響 #21 答案：#21 回答在 2064.2 已結束）。
- 若要補建該問，需另外新增一張「師父說已回答過」的卡。

### ⑤ 收場尾端與 ffprobe 長度差 1–4.4 秒（約 35 場）
- 例：2025-06-09-tieba closing end 4988.505 vs 音檔 4990.374。
- 判定為尾端靜音／編碼填充（SRT 最後一條字幕即在此之前結束），**非錯誤**，不建議改。

---

## 四、逐一確認的量化結果

| 指標 | 結果 |
|---|---|
| 結構性錯誤（缺值／零長／重疊／缺口／收場斷鏈／SoT 不一致） | 修正前 11 → **修正後 0** |
| 可比對「下一題提示點」的段落 | 2,849／3,458（609 段該場無提示語可比） |
| 段落起點 vs 提示點偏移 | min −2.94s、max +4.98s、**中位 −0.17s**；>8s 者 **0**、<−4s 者 **0** |
| 答案落點（n-gram 落在本段窗口外 ≥50% 者） | **0** |
| 殘留警訊 | 35 筆（答案覆蓋率低 20／提問未回應 10／邊界偏晚 3／下一題內容滲入 1／SRT 截斷 1）——逐筆複聽後皆屬：師父明說「已回答過／不回答」、PDF 標「無回答／上一回答裡」、或 ASR 字幕缺口，非對齊錯誤 |

---

## 五、本次檔案異動

**資料（校稿 UI ＋ canonical SoT，9 個月現已一致）**
`audio_map/2025-{06,07,09,11,12}.json`、`audio_map/2026-{01,02,03}.json`、
`tool/word2ebook/data/audio_map/` 同名 8 檔、`audio_map/qid_to_sep_chapter.json`、
`tool/qa_split_ebook/classified/batch_015.jsonl`

**工具**
`tool/pdf_audio_map/apply_audit_fixes_20261025.py`（本次修正，可重跑、冪等）、
`tool/pdf_audio_map/merge_20250901_sunhong.py`（2025-09-01 合併資料腳本）、
`tool/word2ebook/core/audio_map_injector.py`（zero 段不注入播放鈕）、
`tool/qa_split_ebook/gen_classified.py`（同上）、
`tool/word2ebook/openspec/specs/pdf-audio-map/spec.md`、`tool/word2ebook/tests/test_audio_map_injector.py`

**產物**
`wenda2_ebook/01–12(.html/_trad.html)`、`wenda2_ebook/search_index*.json(+hash)`（22 檔、64 行新增／54 行刪除）
`wenda2_ebook_word/`（內部建置來源，gitignored）

**未改動但值得一提**
`tool/daily_quotes/` 三支管線已重跑（build_quotes → select_1095 → audit_quotes）：
`audit_quotes` 通過（經文命中 0），`candidates.json`／`daily_quotes.json` 與版控**零差異**。
