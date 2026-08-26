# word_audio_map2 — 時間序 Word → 音檔 mapping 產生器

依據**時間順序版** Word 彙總
`問答錄2/2024-2025 TAI师父答疑汇总 - 截止2025年7月12日.docx`
與 AI 轉出的 `.srt`，產出 `audio_map2/YYYY-MM.json`（2024-02 … 2025-05）
供 `/audio_map2/index.html` 審核播放段落。

## 原則

- **文字以 Word 為準**：`q_text` / `answer_text` / `questioner` / `question_time` /
  opening / closing 文字全部取自 docx。
- **SRT 只用於時間**：`start` / `end` / `srt_preview`（僅供對照，不是校對稿）。
- 不參考 `tool/word2ebook/data/audio_map_word/` 的既有時間（錯誤率高）。

## 指令

```bash
cd tool/word_audio_map2

# 全範圍產出並寫檔
.venv/bin/python build_maps.py --all --apply

# 單一月份 dry-run（只印報表）
.venv/bin/python build_maps.py --month 2024-12
```

首次安裝：`python3 -m venv .venv && .venv/bin/pip install opencc-python-reimplemented`
（OpenCC 做 繁↔簡 normalize，比對 SRT 用）。

## Word 解析規則

| 元素 | 判斷 |
|------|------|
| session 標題 | `Tai师父YYYY年M月D日答疑（文字版）`；`2024年2月16日…微信记录完整版` 無音檔，跳過 |
| 區塊起點 | 分隔線（`———`）、`师父说：` 標記、或嚴格的「短暱稱＋冒號」行 |
| 提問人列 | `Name：[時間戳]`；名稱 ≤15 字、非黑名單（Taiguanglin/师父说…）；含師父＋有內容 → 引語不拆塊 |
| 回答起點 | `Taiguanglin：` 行；**黏在問題段落尾端**（「…嗎？Taiguanglin：」）也會正確切開（全檔 126 處）；同答後再現 = 同人追問，各自成段 |
| 來源分段 | `师父说：…先回答贴吧的问题。` / `…回答微信公众号的问题。` 等 4 類標記 |

只有當天**實際存在多個音檔**（貼吧＋微信公眾號）才依標記拆 sub-session；
單音檔日（2024-02 … 2024-11）維持單一 session，`师父说` 變開場／收場文字。

特例：

- `2024-12-09` 公眾號音檔分（上）（下）→ 合併時間軸（下段時間 += 上段 SRT 末尾估計長度），
  JSON `media_kind:"split"`、`media_parts[]` 帶每檔資訊。
- Word 漏掉來源轉換標記但當天有雙音檔（如 `2025-03-12`）→ 自動以
  貼吧→微信 合併時間軸對齊，`resolved_source:"貼吧＋微信公眾號（文字檔未分段）"`。

## 對齊策略（沿用 tool/pdf_audio_map）

1. 提問人口語名變體命中（最強 anchor，如 掌南飛→张南飞、无为心内起悲心→微信内起背心）
2. 問題內文 needle（去頂禮等客套話）＋ **罕見 4/3-gram shingle 掃描**（對抗重 ASR 錯字）
3. 回答開頭 needle
4. 全域重新錨定 → 單調內插補洞

### 時長感知修復（duration-aware repair）

初步對齊後，比對每段「文字量 ÷ 語速」與實際分配到的音檔秒數：
明顯不足（<45% 預期時長）或信心 <0.5 的段落進入修復：

- **候選**：全 session 範圍內的名字命中／needle／shingle，加上
  bigram 模糊定位（容忍「往生極樂世界→出院往盛肌肉」級別的錯字）
- **共識**：多探針指向同一 ±45s 區域即可採信；精確候選需覆蓋率
  領先 60s 外亞軍 ≥0.08（或絕對值 ≥0.62）
- **順序寬容**：朗讀順序可能與 Word 排序不同（2025-05-17 即發生），
  修復後依時間重排播放順序
- **找不到逐字對應時**：依前後段比例夾入，標 `no-anchor:clamped`
  ＋「待人工確認」（黃色，UI 有「待人工」過濾鍵）——常見於主題式
  講解月份，或問題以圖片提交／隔日才回答者

段 end = 下一段 start；末段 end = 收場 start 或音檔結尾。
confidence < 0.5 → 低信心（審核 UI 紅卡提示）；stats 的 `pending`
即待人工確認段數。

## 各月品質概況

- **2025-01 … 2025-05、2024-11、2024-12**：結構化標記完整，低信心 0，
  僅少數「待人工」（3~11 段/月）需聽檔確認。
- **2024-02 … 2024-08**：音檔本身是**主題式講解**（未逐題念問題內容）且該時期
  ASR 品質差（禅→场/产、参→穿），大量段落僅能依名字錨定或比例夾入
  （pending 20~224/月）—— 需逐段聽檔確認，這正是本 review UI 的主要用途。

## 輸出 JSON schema

同 `tool/word2ebook/data/audio_map/*.json`（month/version/stats/sessions，
session 內 opening/segments/closing），另加：

- `docx_heading`：來源 Word 標題
- `media_kind`: `single` | `split` | `none`
- `media_parts[]`: `{stem, audio_file, srt_file, mp3_path, opus_path, duration_est}`

segment 欄位：`index / question_id / stable_key / questioner / question_time /
q_text / q_preview / answer_text / answer_preview / start / end / start_label /
end_label / confidence / status / locked / notes / srt_preview`。

## 審核 UI

`/audio_map2/index.html`：選月份 → session → 卡片式段落審核；
▶ 播放此段（串流 `../audio/*.opus`，支援 split 合併時間軸）、低信心紅框、
插補/缺時間過濾、SRT 對照摺疊區。鍵盤：`P` 播放/暫停、`↑↓` 上/下一段。
本機瀏覽需走 http server（fetch 相對路徑），例如：

```bash
python3 -m http.server -d /Users/paul/tai/taiguanglin.github.io 8000
# → http://localhost:8000/audio_map2/
```
