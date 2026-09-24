---
name: audio-map2-align
description: >-
  時間序 Word↔音檔 mapping JSON（audio_map2/<month>.json）的毫秒級對齊校對 skill：文字以 Word
  為準、SRT 只取時間，分段單位＝一個 wenda2_ebook HTML 問題；每段 start 對齊「段落文字第一個詞
  開口唸出的時刻」（第一字錨定），end 嚴格銜接下一段。以人工 golden 學邊界規則，用 SRT cue 邊界
  與 FunASR 字級 timestamp（tool/sense_voice）定位。Use when 對齊／校對／審核 audio_map2 月份 JSON。
---

# audio_map2 月份 JSON 校對（Word ↔ 音檔，第一字錨定）

把 `audio_map2/<month>.json` 每段的播放時間毫米級對齊到實際念到的字／cue。分段單位＝**一個
`wenda2_ebook` HTML 問題**（播放鈕注入處）。

- UI 操作、資料模型、章節對應、目前進度 → [`AGENTS.md`](AGENTS.md)。
- 產生器與上游 → `tool/word_audio_map2/README.md`。

## 1. 鐵律

1. **文字以 Word 為準，SRT 只取時間。** `q_text / answer_text / questioner / question_time /
   opening / closing / chapter_question_ids / chapter_indexes / index / question_id / stable_key`
   一字不動；只改 `start / end / start_label / end_label / confidence / notes / status` 與
   `segments[]` 順序。
2. **分段 SoT＝`wenda2_ebook` HTML**（`resplit_by_html.py` 結果）：一段＝一 ebook 問題。Word 拆太細
   要合併、太粗要切分；別用 Word 段數當目標。
3. **第一字錨定**：`start` ＝段落文字第一個詞**開口唸出**的時刻，**絕不晚於第一詞 onset**（允許
   提前 0–1.5s 落在靜音／過渡語）；`end[i]==start[i+1]`、`opening.end==第一段 start`、
   末段 `end==closing.start`（或音檔尾）。
4. **毫秒級＝貼齊 SRT cue 邊界**：`start`＝第一字所在 cue 的 start，**直接抄原值**（如 `19.680`），
   不要四捨五入。cue 粒度不足時用 **FunASR 字級 timestamp**，不要按比例硬猜。
5. **誠實信心度**：≥0.95 cue 直讀無歧義；0.85–0.9 內容實讀確認但 ASR 變形／cue 含過渡語；<0.5 只有
   「按比例夾入、未實讀」才保留；空答案／音檔未讀 → `start/end=null`、`confidence=0.0`＋notes。
6. **零長度**（`"zero": true`）：師父沒念 → 起訖嚴格相等、不可點播、勾選即視為已確認；「誤留極短
   長度的沒念段」用此標記修復，不要手改成完全相等。
7. **不要跑 `build_maps.py --all --apply`**（覆蓋人工成果）；也不要對已對齊月份重跑
   `resplit_by_html.py --apply`。修完直接覆寫 `<month>.json`（`ensure_ascii=False, indent=2`＋尾隨 `\n`）。

## 2. 過渡語歸屬（第一字錨定核心；判斷看**文字**）

- `answer_text` 以「**下一个问题／第 N 個問題**」開頭（文字含過渡語）→ 過渡語**屬本段**：`start`
  ＝過渡語 cue 起；cue 前有上一段尾字時＝cue 內過渡語實際 onset（字級）。
- `answer_text` 以**人名／唸回題幹**開頭（文字不含）→ 過渡語**屬上一段尾**：`start`＝人名 cue 起；
  過渡語與人名同 cue 時＝cue 內人名 onset（字級）。

| 情況 | 判定 | `start` 錨點 |
|------|------|--------------|
| 人名獨立成 cue | cue 只含人名（±語氣詞） | `cue.start` |
| 文字含過渡語 | answer_text 以「下一个问题」開頭 | 過渡語 cue 起；前有尾字 → cue 內 onset |
| 過渡語＋人名同 cue | cue＝「下一个问题 XXX」且 answer 以人名開頭 | cue 內人名 onset（字級） |
| 唸回題幹 | answer_text 以題幹原文開頭（多子題第 2 題起） | 題幹 `cue.start`（read-back 屬本段） |
| 靜音提前 | start 落在第一詞 cue 前靜音 | 保持不動（≤1.5s 合法） |

（2025-03-15 微信公众号 25 段 golden 實測；**字母人名**取該字母 onset，paraformer 把整串合併在首字母。）

## 3. 環境與工具

```bash
cd /Users/paul/tai/taiguanglin.github.io/tool/word_audio_map2
# 唯一有 opencc/docx 的 venv；working dir 必須在此，helpers 才 import 得到 build_maps/common
.venv/bin/python ...
```

SRT 原始檔就帶毫秒，直接讀原始 cue：`from common import parse_srt_raw` → `[(start_ms, end_ms, text)]`。
`audio_map2/tools/`（`readspan.py` 的 `source` 用簡化字 `贴吧`、`微信公众号`）：

| 檔案 | 用途 |
|------|------|
| `readspan.py <json> <date> <source> <t0> <t1>` | 印時間窗原始 SRT 文字＋毫秒 cue（收斂邊界核心） |
| `first_char_audit.py --month M --date D --source S` | 逐段第一字稽核（`OK/EARLY/LATE/prev-tail/???`；**VAR 表權威**） |
| `funasr_ctx.py`／`funasr_onset_scan.py`／`funasr_verify.py` | 字流判讀／候選錨點掃描／複驗 |
| `funasr_char_onset.py <opus> <t0> <t1> 關鍵詞…` | 字級 onset（combined cue 才需；模型載入 ~40s，**多窗合併批次**） |
| `funasr_session_transcribe.py`／`funasr_dump.py` | 產生 `/tmp/funasr_cache/<sid>.json`（字級 cache） |
| `xscan.py` | 掃過渡標記（重排偵測） |
| `seqloc.py`／`audit.py`／`session_overview.py`／`finalize.py` | anchor 假說／錯位篩選／session 摘要／notes＋stats 收尾 |

## 4. golden 方法論與通用規則

**golden** ＝ `confidence ≥ 0.8` 且 `status in (manual, reviewed)`（或該 session 有 `meta.lastPlayed`）。
種子：`2025-05-16/17`（邊界）、`2025-03-15 微信公众号`（第一字）。對齊新月份前先抽 6–10 段歸納**同一
批音檔、同一 ASR** 的規律再外推。

1. 起點＝段落文字第一個詞的開口時刻（§2）；終點＝下一段起點 cue start 往前回推到上一個 cue 的 end；
   沉默留空窗，不硬塞。
2. 多子題一段被切分 → 邊界在「唸回下一題題幹」處；合併段時間＝原多段 `[min start, max end]` 包絡，
   不內移已確認邊界、不 overlap。
3. **ASR 變形先推正字對應的 ASR 串再反查 SRT**，不要直接拿正字 grep。

## 5. 標準流程

0. **確認分段 SoT 狀態**：段數須對得上 `wenda2_ebook` 問題數；缺 qid／多 qid 先列清單，**不要盲目
   重切已對齊的月**。
1. **全景盤點**：逐 session 列段數、null、`conf<0.8`、`status=auto`、待人工數；golden 不動。
2. **找 reading-order 重排**：`xscan.py` 對照過渡語順序 vs `index` 順序；重排後必須
   `end[i]==start[i+1]`、無 overlap、無倒序（`segments[]` 是播放順序）。
3. **逐段收斂**：對 `conf<0.8` 段 `readspan.py` 印毫秒 cue → 找 answer-head 獨特字串（人名／主題詞／
   唸回題幹）→ 該字所在 cue start ＝ `start`；下一段 head／過渡語 cue start ＝本段 `end`。回寫 ms
   原值、label 以 `HH:MM:SS.mmm` 同步。
4. **短窗重轉／字級**：cue 讀不出時用 `tool/sense_voice` 對時間窗重跑（sentence 級毫秒 cue）或字級
   onset。**絕對時間只信「10–25s 短窗 ＋ mp3/opus 雙解碼器一致」**（長窗／整檔會漂移、漏字）。仍無解
   或音檔沒讀 → `null/0.0`＋note。
5. **信心度收口**（依 §1.5）。
6. **收尾**：誤加單數 `note` 併回 `notes`；清掉已核實的 `待人工確認`／`no-anchor:clamped` 標記；重算
   stats；結構校驗（鏈、無 overlap/倒序、open/close 完整）；跑 `validate_resplit.py`
   （`ALL HARD CHECKS PASSED`）。改前備份 `/tmp/<month>.backup.json`，收尾 diff 驗**文字欄位 0 違反**。

## 6. ASR 變形速查（**權威 VAR 表在 `tools/first_char_audit.py`**）

> 同名 key「後者覆蓋前者」——增補必須列**超集**，否則前面變形被靜默丟掉。
> 逐月完整變形（2024-02／05／08／12、2025-03…）見該腳本與 git 歷史。**先推正字的 ASR 串再反查。**

| 正字 | ASR 常誤為 |
|------|-----------|
| 师父 | 师傅 |
| 极乐世界／极乐是我家 | 记了世界／幸运；其实是我家 |
| 业力／淫欲／习气 | 夜粒·衣粒／盈民·溢欲／吸气 |
| 冤亲债主／须弥山 | 年轻寨主／薛弥山·虚米三 |
| 千湍盈泰 | 千州银泰·金瑞银泰·迁入银泰·千入银泰·青收银台 |
| 释慈伟／苏七念1 | 是思维·诗词伟／七年一·十七年·书期呢一 |
| 薛祖宜 | 需谢注意·学习主义·缺主医·薛主仪 |
| 无为心内起悲心 | 微信练起背心／微信的取背心 |
| 观照0620／偶米大 | 关照零六二零·关掉零六二零／欧米伽·欧密达 |
| 勤心莫退／印光／打坐 | 请先默退·请先目对／应光／打造·打错 |
| 字母名（HFFHI/FLPHM/…） | 字母保留並合併在首字母 |
| 貼吧/微信用戶名 | 擬全形拼音＋字母混合（QUDy8Na → QUD wifi）；先讀正常文字推 ASR 串 |

**工具陷阱**：`transcribe.py` 是 positional；SRT 只有 sentence 級 cue，字級 timestamp 要從
`model.generate()` 的 `item['timestamp']` 取（`funasr_char_onset.py` 已封裝）。`AutoModel` 的 punc
模型用全名 `iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch`（`"ct-punc"` 此 venv 不註冊）。
稽核對「長 cue 含前段尾＋首詞」可能給 **OK 偽陰**；`EARLY ≤1.5s` 合法，只修 `LATE`／`prev-tail`。
**自報 conf 不可信，以稽核為準。**

## 7. 逐月結論（可外推教訓；逐段明細見 git 歷史）

- **时间序月（2025-03、2024-12、2024-05）**：套 golden 後每場 `LATE 0`、鏈 0 斷點。2024-12（376 段）
  `LATE 47→0`、`??? 123→64`；2024-05（290 段）修正 187 段、`matched 280→288`。拆檔時間軸
  （09-wechat 上下檔）offset 2927.255，JSON `start` 一律 global。
- **2024-05 工具鏈教訓（勿用整檔重轉取代短窗）**：ASR 字級絕對時間隨 VAD 視窗漂移（16s／60s／整檔
  可差 2–5s）；長窗會漏字；窗尾字/秒 ≥7 代表 VAD 少配時間、值不可用。
- **主題式月（2024-02…2024-08）**：音檔是主題式講解、ASR 差，每段都要判讀；Word 為改寫稿。SRT 常
  亂窗／空窗，第一詞只能靠 FunASR 字級 onset；名未轉出／SRT 亂窗屬**誠實極限**。
- **2024-03（已完成）**：FunASR VAD 空洞（整區無字級）以 ffmpeg 切片強轉補錨，並與主 cache 雙驗
  ±0.1s；問者名／首詞常被 ASR 打成同音（「果慧」→「我会」、「无为心内起悲心」→「我微信的起对信」、
  「Elaine」→「ELA」），用 homophone 假說定位後一律以字級窗口定案。**`segments[]` 是播放順序**：
  指數序≠時間序時按音訊序重排，並讓 `end[i]=start[i+1]` 連動。完成統計見 [`AGENTS.md`](AGENTS.md)。

## 8. 完成定義

- [ ] 每段從 `start` 播放，第一個聽到的詞＝段落文字第一個詞（允許 ASR 變形）
- [ ] `start` 絕不晚於第一詞 onset（`EARLY ≤1.5s` 合法）；鏈完整
- [ ] 文字欄位 0 違改（git diff 驗證）；修正段 `notes` 記錄錨點證據
- [ ] 交付：`<month>.json` ＋回報（重排 block、修正段含 ms、誠實空缺理由、stats）
