---
name: audio-map2-align
description: >-
  Millisecond-precision alignment of a chronological Word↔audio mapping JSON
  (audio_map2/<month>.json). Learns boundary rules from already-confirmed
  "golden" segments (2025-05-16/17 are the canonical seed), one segment == one
  wenda2_ebook HTML question, snaps every segment start/end to the exact SRT cue
  edge, and regenerates a cleaner SRT via sense_voice when the existing ASR is too
  garbled to resolve a boundary. Use when asked to 對齊/校對/審核 a 月份 JSON.
---

# audio_map2 月份 JSON 校對（Word ↔ SRT 毫秒級時間對齊）

把某個 `audio_map2/<month>.json` 的每一段播放時間逐一、毫秒級地對齊到 SRT
實際念到的 cue 邊界。分段單位 = **一個 `wenda2_ebook` HTML 問題**（播放鈕注入處）。

## 鐵律（先讀）

1. **文字以 Word 為準，SRT 只取時間。** `q_text / answer_text / questioner / question_time /
   opening / closing / chapter_question_ids / chapter_indexes / index / question_id / stable_key`
   全部一字不動；只改 `start / end / start_label / end_label / confidence / notes / status`
   與 `segments[]` 陣列順序。
2. **分段 SoT 已改為 `wenda2_ebook` HTML**（`resplit_by_html.py` 的結果）：
   一段 = 一個 ebook 問題。Word 拆太細會**合併**（同 qid 多段），Word 拆太粗會**切分**
   （一段多 qid）。別再用 Word 段落數當對齊目標。
3. **毫秒級精準 = 貼齊 SRT cue 邊界。** SRT cue 本身帶毫秒（`00:00:19,680`）。
   段的 `start` 取「該段答案第一個字所在 cue 的 start」；`end` 取「該段答案最後一字
   所在 cue 的 end」。**不要**寫 `93.6`、`190.0` 這種把 cue 邊界四捨五入後的值 —
   直接抄 cue 原值（如 `19.680`）。
4. **誠實信心度。** ≥0.95 = cue 邊界直讀無歧義；0.85–0.9 = 內容實讀確認但 ASR 變形、
   cue 內含跨段過渡語；<0.5 只有在「按比例夾入、未經 SRT 實讀」時保留；空答案／音檔
   未讀 → `start/end = null`、`confidence = 0.0`、notes 寫原因。**不硬湊**。
5. **不要跑 `build_maps.py --all --apply`**（會覆蓋人工成果）；也不要 `resplit_by_html.py --apply`
   重複切分已對齊的檔案。修完直接覆寫 `<month>.json`（`indent=2` + 尾隨換行）。

## 環境與前置

```bash
cd /Users/paul/tai/taiguanglin.github.io/tool/word_audio_map2
# 唯一有 opencc/docx 的 venv；working dir 必須在此，helpers 才 import 得到 build_maps/common
.venv/bin/python ...
```

### 讀 SRT（毫秒 cue）

SRT 原始檔就帶毫秒，直接用 `parse_srt_raw` 讀原始 cue（不要 normalize 後丟掉毫秒）：

```python
from common import parse_srt_raw      # -> [(start_ms, end_ms, text), ...]
from pathlib import Path
cues = parse_srt_raw(Path(s['media_parts'][0]['srt_file']))
# cues[i] = (19.680, 23.160, '贴吧匿名一九六六嗯，')
```

SRT 路徑例：`~/Documents/backup_on_2026-07-16_13inch_macbook/2025答疑音頻/2025年5月17日Tai師父貼吧答疑.srt`
（`readspan.py` 的 `source` 參數用簡化字：`贴吧`、`微信公众号`。）

### 關鍵 helper（tools/）

| 檔案 | 用途 |
|------|------|
| `readspan.py` `<json> <date> <source> <t0> <t1>` | 印某時間窗的**原始 SRT 文字＋毫秒 cue**（收斂邊界的核心） |
| `xscan.py` `<json> <date> <source>` | 掃 `下一个问题/下一问` 過渡標記時刻（重排偵測） |
| `seqloc.py` `<json> <date> <source>` | 逐段 answer-head anchor 假說（僅供參考，MOVE≠必動） |
| `audit.py` / `audit_strict.py` | content-coverage 篩選錯位段 |
| `finalize.py` | notes 合併、stats 重算、結構校驗 |

## Golden sample 方法論（先挖已確認段學規則）

### 什麼是 golden sample

`confidence ≥ 0.8` 且 `status in (manual, reviewed)`（或該 session 的 `meta.lastPlayed`
有記錄）的段 = **已知正確的對齊**。`2025-05-16`、`2025-05-17` 兩天幾乎全數手動確認，
是標準種子。對齊任何新月份前，先從這兩天抽出 6–10 個 golden 段，歸納**這一台 ASR
（同一批音檔、同一模型）的變形規律**，再套用到待對齊段。

### 從 golden 學到的通用規則（可外推）

1. **段的起點 = 提問人名或「下一个问题」過渡語那個 cue 的 start。**
   師父幾乎固定以「下一个问题 / 下一个 / 还有 + 名字」開新段。段的 `start` 貼
   「名字（或其 ASR 變體）唸出」的那個 cue 起點，不是「下一个问题」那 cue 的起點
   （過渡語屬上一段的尾）。
2. **段的終點 = 下一段起點 cue 的 start（往前回推到上一個 cue 的 end）。**
   即 `end[i] == start[i+1]`；若兩者中間有 ASR 空窗（沉默），`end[i]` 取該段最後
   一個有字 cue 的 end，`start[i+1]` 取下一段第一個有字 cue 的 start，中間留空窗、
   **不要**把沉默硬塞進某段。
3. **多子題一段被切分時，邊界在「唸回下一題題幹」處。** 師父常把提問者的問題唸回去
   （answer_text 開頭 = 問題原文唸一遍）。切分點 = 下一子題題幹第一個字出現的 cue start。
   例如「…然后下一个问题，菩萨收徒没有标准…」→ 前一子題 end 在「下一个问题」前一個
   cue 的 end，後一子題 start 在「菩萨收徒」cue 的 start。
4. **ASR 變形速查**（這批音檔常見，見文末表）——用正字推測 ASR 串再反查 SRT，
   不要直接拿正字 grep SRT。
5. **合併段（同 qid）的時間 = 原多段時間取 [min start, max end]**，且合併後要保證
   與鄰段 `end[i]==start[i+1]` 不 overlap。合併不改變內部已確認的邊界，只取包絡。

## 標準流程（由粗到細、最終毫秒級收口）

### 第 0 步 — 確認分段 SoT 狀態

先確認該月 JSON 已用 `resplit_by_html.py` 切到「一段 = 一 ebook 問題」。
若尚未切（段數與 `wenda2_ebook` 問題數對不上），先跑 dry-run 對照，
再把「缺 qid / 多 qid」列清單。**不要盲目重切已對齊的月。**

### 第 1 步 — 全景盤點

```python
# 逐 session 列出：segment 數、null 數、conf<0.8 數、status=auto 數、待人工標記數
```

golden 段（已確認）不動；只處理 `conf<0.8` 或 `status=auto 且 conf<0.8` 的段。

### 第 2 步 — 找 reading-order 重排

跑 `xscan.py` 對照過渡語順序 vs `index` 順序。典型：同一提問人多題一起念、
或先念後題。重排後必須 `end[i]==start[i+1]`、無 overlap、無倒序。
記住 **`segments[]` 順序 = 播放順序**，`index` 是 Word 參照。

### 第 3 步 — 逐段收斂（毫秒級）

對每個 `conf<0.8` 的段：

1. `readspan.py <date> <source> <t0-60> <t1+60>` 印出含**毫秒 cue** 的原始 SRT。
2. 找該段 answer-head 的**獨特字串**（人名 / 主題詞 / 唸回的題幹），
   定位其**第一個字所在 cue 的 start**（就是段的精準 `start`）。
3. 找下一段的 answer-head（或過渡語），其 cue start = 本段的精準 `end`。
4. 回寫時把 ms 值**原樣抄進** `start/end`，同時 `start_label/end_label` 用
   `HH:MM:SS.mmm` 格式同步更新（label 由 ms 值算出，兩者必須一致）。
5. 若 ASR 太糊、連獨特字串都讀不出 → **進第 4 步 regenerate SRT**，別硬猜。

標籤格式 helper（會話內可直接複用）：

```python
def lbl(t):
    h=int(t//3600); m=int((t%3600)//60); s=t%60
    return f'{h:02d}:{m:02d}:{s:06.3f}'
```

### 第 4 步 — 需要時重新生成更精準的 SRT（millisecond 後盾）

當某段 AB SR 太糊、邊界 cue 無法從現有 `.srt` 讀出，用 `tool/sense_voice` 對該段
**音檔的該時間窗**重跑 ASR（Paraformer-zh + VAD，會輸出 sentence-level 毫秒 cue）：

```bash
cd /Users/paul/tai/taiguanglin.github.io/tool/sense_voice
# 單檔： whole opus → 新 srt（可先 ffmpeg 截出該窗口再轉，省時）
.venv/bin/python transcribe.py --input <opus> --output_dir /tmp/srt_refresh
```

- 只對**少數糊段**重跑；paraformer 逐字 timestamp 比舊 SRT 更細，可拿到準確 cue 邊界。
- 「重生成」產物是**參考**，最終仍以「該 cue 是否真的含答案頭／尾字」人工判定，
  再把 ms 值寫回 `start/end`。
- 若重跑仍無解、或該答案音檔**根本沒讀** → `null / 0.0` + note（誠實，不硬湊）。

### 第 5 步 — 信心度收口

- cue 邊界直讀無歧義（名字/題幹唸回清晰）→ **0.95**。
- 內容實讀確認、但 ASR 變形大或 cue 內含過渡語 → 0.85–0.9。
- 結構重排＋邊界確定、逐字 ASR 嚴重錯 → 0.8。
- 空答案／併入鄰段／音檔未讀 → `null / 0.0` + note。

### 第 6 步 — 收尾

```python
# (a) 誤加的單數 'note' 併回 'notes'
# (b) 清掉 '待人工確認'/'no-anchor:clamped'/'html-resplit:...待人工確認' 標記（已核實才算）
# (c) 重算 stats：missing=null數, matched=其餘, low_conf=matched 中 conf<0.5,
#     pending=notes 含 'no-anchor:clamped|待人工', interpolated=notes 含 'interpolated',
#     openings_ok/closings_ok = opening/closing.start is not None（0.0 是合法值）
# (d) 結構校驗：end[i]==start[i+1]、無 overlap、無倒序、openings/closings intact
```

跑 `validate_resplit.py`（`ALL HARD CHECKS PASSED`）。改前對 `<month>.json` 做
`git checkout` 後的 copy 到 `/tmp/<month>.backup.json`，收尾時 diff 驗證
**文字欄位 0 違反**。

## 已知 ASR 變形速查（貼吧/微信常見，先推正字再反查 SRT）

| 正字 | ASR 常誤為 |
|------|-----------|
| 师父 | 师傅 |
| 极乐世界 | 记了世界 |
| 业力 | 夜粒 / 衣粒 |
| 淫欲 | 盈民 / 溢欲 |
| 冤亲债主 | 年轻寨主 / 冤亲战士 |
| 习气 | 吸气 |
| 弥勒 | 弥若 |
| 须弥山 | 薛弥山 / 虚米三 |
| 慈航/搭档 | 刀板 / 炸弹 |
| 千湍盈泰 | 千州银泰 / 金瑞银泰 |
| 郑勇 | 郑雄 |
| 贴吧用户_QUDy8Na | QUD wifi / QUDYYN / qudyya |

技巧：英文用戶名唸成全形拼音＋英文字母混合；先讀正常文字推測 ASR 串，再反查 SRT。

## 誠實保留的空缺段（不可杜撰）

- `answer_text` 為空（佔位段）→ null/0.0。
- 內容已併入鄰段 → null/0.0，note 寫明併入哪段。
- 音檔沒讀該答案 → null/0.0。
- 提問人只被口頭確認樓層、沒念答案 → null/0.0（如 05-14 貼吧 1051樓）。

## 交付產出

- `<month>.json`（`ensure_ascii=False, indent=2` + 尾隨 `\n`）。
- 回報：重排了哪些 block、修正了哪些段（含 ms 值）、N 段誠實空缺理由、最終 stats。

詳細 helper 在 `tools/`（`readspan.py`、`xscan.py`、`seqloc.py`、`audit.py`、
`session_overview.py`、`finalize.py`）。