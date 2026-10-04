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
| **`batch_anchor.py --month M`** | **量測主力（2024-12 起）**：對每個邊界切 `[start−4, start+8]` 的 12s 短窗，opus+mp3 雙解碼器字級 onset，落盤 `/tmp/am2_<month>/<sid>__<label>.json`（**可續跑**，已存在就跳過）。全月 399 邊界約 4 分鐘 |
| **`propose_fixes.py --month M`** | 依快取產 `fixes.json` 候選：整詞/變形/長度≥3前綴比對 →（不中）**退級探針**（跳過首詞的答案前綴，3/5/8/12/16/20 字，`use_var=False`）→（不中）標 `weak` 交人工。含四條**信賴規則**：R1 首詞 ≤2 字需分數 ≥0.9（拼音全中）才採用；R2 分數 <0.75 交人工；R3 命中窗第一字是虛詞/語氣字而答案首詞不以它開頭 → 前移；R4 短詞（≤3 字）的 VAR 變形長度 > 首詞+2 時丟棄 |
| **`apply_alignment.py --month M [--overrides o.json] [--only-overrides] [--inplace]`** | 套用 `fixes.json`＋`overrides.json`，**由 `start` 鏈反推所有 `end`**、重算 `*_label`、單調性檢查、`--verify-text` 驗文字欄位 0 違改。`--only-overrides` = 第二輪只補新發現的錯 |
| **`post_align.py --month M --inplace`** | 收尾：修過期 `notes`（STALE 表）、標註已驗證、重算 `stats`、結構校驗（鏈／倒序／null label） |
| **`content_check.py --month M [--tol 3.5]`** | **內容定位（不可省）**：整場字級轉錄＋拼音模糊比對。0% 探針**跳過首詞**（人名被聽歪會讓探針滑到正文、量到假偏差），50/85% 探針驗內文確在窗內 |
| **`cross_check.py --month M --tol 3.5`** | 字級短窗錨點 ↔ 整場轉錄內容起點的**獨立互證**（兩種完全不同的量法）。`tol` 要吃進整場轉錄的局部 VAD 抖動（實測 ±5s） |
| **`listen_check.py --month M [--tol 0.55] [--win 6]`** | **播放端視角**：從 `start` 播下去 6s 內必須聽得到答案開頭（窗長要夠，2.5s 會因名字逐字母慢唸而誤判） |
| **`dup_scan.py --month M`** | 掃「首詞在視窗內被唸不只一次」，抓被跳過的第一次（±1.2s 聚類） |
| **`onset_at.py --month M --session S --at T`** | 在**任意**時刻量一次雙解碼器 onset（`batch_anchor` 的 ±9s 窗抓不到 20–60s 的整段錯位時用） |
| **`review_batch.py --month M [--pick prefix\|first_word] [--weak] [--dmin 0.5] [--session S --label #N]`** | **人工過目主工具（2024-11）**：一次印多個邊界的「新舊錨點之間字級時間軸」＋答案開頭 ＋匹配文字，`«起»`／`«新»` 標出兩個錨點各落在哪個字。`--pick` 過濾 basis、`--weak` 只看 weak、`--dmin` 只看 \|Δ\| 超過多少的 |
| **`review_fixes.py`／`inspect_span.py --session S --label N [--span B A]`** | 單邊界深看：新錨點前後字級時間軸 ＋ SRT cue ＋ Word 首詞 |
| **`reanchor.py --month M --session S --index N [--index …] [--near A B]`** | 用整場轉錄把**整段錯位／窗口太短**的段重新定位：0%（跳過首詞）/30/60/85% 四個探針在整場的佳命中時間，自動標「窗外」。`--near` 限絕對區間搜尋。⚠️ **探針也會失手**：0% 與 30% 探針**同時落到窗外且分數 <0.5** 時（2024-06 `06-17 #13`、`06-22 #11`），改用 `full/` 整場轉錄**以答案裡的關鍵字搜尋**定位時間，再用 `onset_at.py` 實測——不能因為探針失手就放棄。⚠️ **得到的是「首個實字」不是「首詞」**：之後要用 `first_word`／`prefix` 探針回頭確認首詞本身的位置（2024-06 `06-17 #4`、`06-21 #4`、`06-20 #17` 都因此晚了 3.6s）|
| **`onset_at.py --month M --session S --at T --span B A`** | 在**任意**時刻量雙解碼器字級 onset（`batch_anchor` 的固定窗抓不到時用；`--at 5.0 --span 1 8` = [4, 13]）。**窗寬會影響結果**：人名落在 VAD 空隙裡時，把窗收窄到 3–5s 才抓得到（2024-08 `08-16 #15`） |
| **`swap_order.py --month M {--swap\|--move} <sid>:<iA>:<iB> --inplace`** | **依音訊序重排 `segments[]`**（SKILL §1 鐵律允許改 `segments[]` 順序）：連帶重編 `index`／`stable_key`、兩段都加 `reordered:` note。`--swap A:B` 限**相鄰**兩段；`--move A:B` **不限相鄰**，處理 3 段以上的**循環錯位**（2024-07 `07-15 #44/#45/#46`：音檔序 #46→#44→#45，`--move 44:46 --move 45:46`）。⚠️ 守衛只認「後段 `start` 比前段早才算順序問題」，**必須先把正確時間寫進 JSON 再重排**，否則舊值本身遞增會被判「不是順序問題」而拒絕。⚠️ 重排後要**刪掉被重排段的舊快取重跑**，且 `apply_alignment.py --verify-text` 必須以 `question_id` 配對（已內建） |
| **`full_transcribe.py --month M`** | 整場字級轉錄（`/tmp/am2_<month>/full/<sid>.json`），**多段分檔自動接軌**（`2024-12-09-wechat` 上下檔 offset 2927.255） |
| **`drift_curve.py`／`driftmap.py`** | 整場轉錄的時間軸漂移校準。用 SRT cue 當參考點，**中位數分桶 ＋ 斜率上限的單調迴歸（PAVA）**——⚠️ 絕對不能用 running max，單一離群點會把整條曲線抬高後降不下來 |
| `funasr_anchor_verify.py --month M --date D [--source S] [--only ...]` | 單場互動式：批次印每個邊界的 SRT cue ＋ 雙解碼器字級時間軸 ＋ Δ 表（2024-12 已被上面的批次工具取代，單場除錯仍好用） |
| `readspan.py <json> <date> <source> <t0> <t1>` | 印時間窗原始 SRT 文字＋毫秒 cue（收斂邊界核心） |
| `first_char_audit.py --month M --date D --source S` | 逐段第一字稽核（`OK/EARLY/LATE/prev-tail/???`；**VAR 表權威**）。⚠️ **只驗「首詞所在 cue 是否與 start 重疊」，不驗 start 落在哪個 cue**，且**完全不檢查 opening/closing**——2025-01-17 有 31/31 個 `start` 全錯卻全報 `OK`；**2024-12 整月 `LATE 0` 而實際 310 個 `start` 錯**。只能當篩選器，不能當收案依據 |
| `funasr_ctx.py`／`funasr_onset_scan.py`／`funasr_verify.py` | 字流判讀／候選錨點掃描／複驗 |
| `funasr_char_onset.py <opus> <t0> <t1> 關鍵詞…` | 字級 onset（combined cue 才需；模型載入 ~40s，**多窗合併批次**） |
| `funasr_session_transcribe.py`／`funasr_dump.py` | 產生 `/tmp/funasr_cache/<sid>.json`（字級 cache；只處理單檔，分檔請用 `full_transcribe.py`） |
| `xscan.py` | 掃過渡標記（重排偵測） |
| `seqloc.py`／`audit.py`／`session_overview.py`／`finalize.py` | anchor 假說／錯位篩選／session 摘要／notes＋stats 收尾 |

**funasr 環境**：`tool/sense_voice/.venv`（python3.11＋`tool/sense_voice/requirements.txt`；
模型已在本機 `~/.cache/modelscope`，不必重下）。**絕對時間只信 10–25s 短窗 ＋ opus/mp3 雙解碼器
一致**；窗寬改變會讓同一個字級 onset 漂 1–2s（實測 `#17 Jhone` 在 14s 窗與 20s 窗差 1.66s），
跨窗不一致時取**較早**者並在 `notes` 記錄跨窗區間。
「一致」要理解成**至少一個聽到且兩個不衝突**，不是兩個都要聽到（實測 opus 會整段丟掉人名）。

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
3. **逐段收斂（批次管線，2024-12／2024-11 驗證）**：
   `batch_anchor.py --month M` → `propose_fixes.py --month M` → `review_fixes.py` 逐邊界過目 →
   人工判讀寫進 `overrides.json` → `apply_alignment.py --month M --overrides o.json --inplace`
   （**`end[i] := start[i+1]`，鏈由 start 反推**，label 以 `HH:MM:SS.mmm` 同步）。
   判讀時依 §2 判定過渡語歸屬，取**該詞第一個字**的字級 onset ＝ `start`；
   `weak` 與 `|Δ|>0.5s` 的邊界一律人工看 `inspect_span.py`。
   **兩輪收斂**：第 1 輪套用後**重跑 `batch_anchor.py`**（視窗跟著新 `start` 走）→
   `propose_fixes.py` 再跑一次 → 只把新發現的錯補進 `overrides.json` 並用 `--only-overrides` 套用。
   2024-12 實測第 2 輪又找出 13 個真錯，第 3 輪才收斂；2024-11 第 2 輪又找出 16 個（含 4 個
   9–59s 的整段錯位），第 3 輪才收斂；2024-09 做到第 4 輪才收斂（第 2 輪 16 個、第 3 輪 5 個、
   收尾前的「`#2` 手動實測」再補 6 個）。人工判讀用 `review_batch.py`（一次一批）最有效率。
   **雙解碼器對單字／字母名會差 0.9–1.1s**，「取較早者」的結果下一輪會翻回去——
   這類一律寫進 `overrides` 當保護值，否則每輪震盪（2024-09 有 8 筆是這種）。
   ⚠️ `find_word` 的命中窗可能**整體錯位一格**（人名「聖輝」落在「說盛」上得 0.588、
   落在「盛輝」上得 1.0）；所以必須「**先只留分數 ≥0.9 的窗，再在其中取最早**」，
   否則「取最早」會讓錯位窗勝出、把錨點釘在上一句尾巴上（2024-11 實測 −3.3s～−4.6s）。
4. **短窗重轉／字級**：cue 讀不出時用 `tool/sense_voice` 對時間窗重跑（sentence 級毫秒 cue）或字級
   onset。**絕對時間只信「10–25s 短窗 ＋ mp3/opus 雙解碼器一致」**（長窗／整檔會漂移、漏字）。仍無解
   或音檔沒讀 → `null/0.0`＋note。**例外：檔頭 0–5s 短窗的 VAD 會整段丟字，此時用整場轉錄取
   開場 onset**（整場轉錄在檔頭反而準，實測與 cue[0] 差 0.04–0.05s）。
5. **內容定位檢查（不可省，2025-01-17 實測抓到 56s 整段錯位）**：`full_transcribe.py --month M`
   → `content_check.py`（內含 `driftmap` 漂移校正）；用 `pypinyin`＋`difflib` 在**拼音音節級**模糊比對，
   把每段 `answer_text` 的內文片段定位回音檔，確認它落在自己的 `[start, end]` 內。
   - **0% 探針要跳過首詞**：人名被 ASR 聽歪（`恒河沙丫`→`红河沙洋`）時，含名字的探針會整段滑到正文，
     量到假的 +8s 偏差（2024-12-09-wechat #28 實測）。
   - 方向性：**內容必須不晚於 `start`**。`start > 內容起點 + tol` 才算整段錯位；反過來
     「內容比 start 晚」是正常情況（人名沒被唸出）。
   ⚠️ 整場轉錄**用來驗內容位置，不要取絕對時間**。2024-12 實測它與 SRT 全月偏差 ≤0.8s
   （`drift_curve.py` 量測），但**局部仍有 ±5s 的 VAD 抖動**（2024-12-13-tieba 1300s 處整場比
   短窗晚 5.8s）——絕對時間仍以短窗為準，抖動範圍靠 `cross_check.py --tol 3.5` 吸收。
   稽核＋Δ 表都抓不到的錯只有這一類能抓（`wechat #3` 錨到音檔裡重複出現兩次的同一句）。
6. **信心度收口**（依 §1.5）。
7. **收尾**：誤加單數 `note` 併回 `notes`；清掉已核實的 `待人工確認`／`no-anchor:clamped` 標記；重算
   stats；結構校驗（鏈、無 overlap/倒序、open/close 完整）；跑 `validate_resplit.py`
   （`ALL HARD CHECKS PASSED`）。改前備份 `/tmp/<month>.backup.json`，收尾 diff 驗**文字欄位 0 違反**。
8. **開場／收場一定要收尾**：`first_char_audit.py` 不檢查它們，而它們在 2025-01 的 12 場裡錯了 10 個
   （錨到第 2 個 cue、或跳過首字「好了」）。

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
**更嚴重的偽陰**：稽核拿「首詞所在 cue」判定，**不驗 `start` 落在哪個 cue**——若 `start` 整段落在
下一個 cue（例：2025-02-15 貼吧 #6 首詞 cue 574.54、`start` 誤取 577.242）仍會報 `OK`。
稽核只給 `OK/LATE/???` 不等於對齊正確；**收尾仍要逐段跑「從 `start` 剪 4s 首字複驗」**
（`start` 起第一個詞＝段落第一個詞才收案）。
**最嚴重的偽陰（2025-01-17 實測，31/31 個 `start` 全錯卻全報 `OK`）**：稽核只比對「首詞所在 cue」
的**文字**，而 `start` 可以整段落在同一個 cue 裡的任何位置——最常見就是落在「下一個問題 XXX」合併
cue 的**起點**（把過渡語算進本段、人名 onset 留在窗外 0.3–3s）。要抓這種錯必須看**字級時間軸**
（`funasr_anchor_verify.py` 的 Δ 表：`start` 之後的第一個字是過渡語＝錨錯了）＋**內容定位檢查**。
**自報 conf 不可信，以稽核為準。**

## 7. 逐月結論（可外推教訓；逐段明細見 git 歷史）

- **时间序月（2025-03、2024-05）**：套 golden 后每场 `LATE 0`、链 0 断点。2024-05（290 段）
  修正 187 段、`matched 280→288`。拆檔时间轴（09-wechat 上下檔）offset 2927.255，JSON `start` 一律 global。
  ⚠️ **2024-12 原以为已完成（`LATE 0`、`??? 123→64`），2026-10-02 用字级 onset 重校才发现
  `LATE 0` 是假阴性**：310 个 `start` 实际有误（>4s 10 个、2–4s 40 个、0.5–2s 78 个、
  <0.5s 182 个），并抓到 3 个整段错位（最大 `09-wechat #29` −58.56s）。
  **「cue 级稽核全绿」不等于对齐完成**，细节见 `AGENTS.md` 的「2024-12 毫秒级重校」。
- **2024-05 工具鏈教訓（勿用整檔重轉取代短窗）**：ASR 字級絕對時間隨 VAD 視窗漂移（16s／60s／整檔
  可差 2–5s）；長窗會漏字；窗尾字/秒 ≥7 代表 VAD 少配時間、值不可用。
  **2024-12 更正**：整檔轉錄的漂移其實很小（與 SRT 全月偏差 ≤0.8s），但**局部抖動可達 ±5s**；
  所以「整檔不能用」過於悲觀、「整檔可當絕對時間」則過於樂觀。正確口徑是
  **整檔用來驗內容位置、也用來量檔頭；中段絕對時間仍以 10–25s 短窗為準**。
- **`batch_anchor.py` 的兩個實作陷阱**（都踩過）：
  (1) 分檔（`media_parts` > 1）必須把 offset 加回時間戳，否則 part-1 的邊界全是本地時間；
  (2) `ffmpeg -ss` 給負值會被當 0，視窗起點要夾在 0 並把窗往後延，否則開場算出負數 start。
- **`VAR` 表對短詞會產生離譜變形**（2024-12 實測）：`variants('云')` 會生出 `下一个问题`（5 字），
  害人名以 1.0 分命中音檔裡的「下一個問」。短詞只接受長度 ≤ `len+2` 的變形；
  VAR 也不該套在任意「答案前綴」上（退級探針要 `use_var=False`）。
  VAR 變形還可能在首詞前塞助詞（`的啊第二个问`），命中窗第一字是虛詞時要前移到窗內第一個實字。
- **主題式月（2024-02…2024-08）**：音檔是主題式講解、ASR 差，每段都要判讀；Word 為改寫稿。SRT 常
  亂窗／空窗，第一詞只能靠 FunASR 字級 onset；名未轉出／SRT 亂窗屬**誠實極限**。
- **2024-03（已完成）**：FunASR VAD 空洞（整區無字級）以 ffmpeg 切片強轉補錨，並與主 cache 雙驗
  ±0.1s；問者名／首詞常被 ASR 打成同音（「果慧」→「我会」、「无为心内起悲心」→「我微信的起对信」、
  「Elaine」→「ELA」），用 homophone 假說定位後一律以字級窗口定案。**`segments[]` 是播放順序**：
  指數序≠時間序時按音訊序重排，並讓 `end[i]=start[i+1]` 連動。完成統計見 [`AGENTS.md`](AGENTS.md)。
- **2025-01-18（32 實段全對、要修的是開場／收場）**：`first_char_audit.py` 只檢查 `segments[]`，
  **完全不檢查 `opening`／`closing`**——兩場的 32 個實段 `start` 全部通過（雙解碼器字級複驗，
  提前量 0.00–0.11s），但 3 個開場／收場錨點全錯：`opening.start` 落在第 2 個 cue（漏掉「今」
  2.8–3.1s）、`closing.start` 落在「今天回答到…」而**跳過首字「好了」1.35s**。
  → **收尾必查開場／收場的第一字**（`fc_dump` 式印 `opening.start`／`closing.start` 前後 cue）。
- **開場 `start` 的正確值是 cue[0] 起或更早的字級 onset**，不是「第二句」的起點；
  `build_maps.py` 的開場錨點疑似抓錯 cue（2025-01 有 8/12 場晚 2.0–5.9s），值得回頭檢視。
- **字母人名要「寬窗」才抓得到首字母 onset**：`S N Z Y L G` 在 10s 窗裡 `S` 之後有 4s 空檔
  （paraformer 把整串併在首字母），窄窗會誤以為 `S` 後面沒東西；`[start-8, start+10]` 窗才完整。
- **`VAR` 超集陷阱實例**：`薛祖宜` 在檔內有 21 條同名條目，2024-05-25 那條只列 9 個變形，
  把含「謝謝主義」在內的 31 個**靜默丟掉**，於是稽核把已對齊的段報成 `???`。
  **加變形後務必跑「HEAD 的每個 key 的變形 ⊆ 新 key 的變形」回歸檢查**（同名 key 會覆蓋）。
- **null 佔位段不要留殘留 label**：`start/end=null` 時 `start_label`/`end_label` 一律 `''`
  （14 個月 178 個 null 段皆如此），否則審核 UI 會顯示不存在的時間。
- **2025-01-17（31/31 個 `start` 全錯、`first_char_audit.py` 全報 `OK`）**：
  - **`start` 落在「下一個問題＋人名」合併 cue 的起點**是最普遍的一類錯（11 段）：過渡語被算進本段。
    稽核抓不到，因為它只看「首詞所在 cue 的文字」與 `start` 是否重疊。**看字級時間軸才抓得到。**
  - **同一句話在音檔出現兩次 → 錨到錯的那次**（`wechat #3` 錯 56s：「也可以這麼說吧」81.31 是上一題
    收尾、150.55 才是本題答案頭）。**只有在「答案內文確實落在自己時間窗內」被驗證過時才算收案**。
  - **反向錯位**（`start` 在人名之後，把人名整段漏在窗外）同樣會被稽核報 `OK`（`wechat #20` −2.70s）。
  - **開場／收場這一場又錯 3 個**（2025-01-18 已修 3 個）：2025-01 的 12 場裡開場／收場共錯 13 個。
  - **短窗寬度本身會改變答案**：同一個字級 onset 在 14s 窗與 20s 窗可差 1.66s。跨窗不一致取較早者。
  - **整場轉錄只能驗內容、不能取絕對時間**（中段漂 2–3s）；但**檔頭 0–5s 反過來**——短窗 VAD 會丟掉
    檔頭，開場 onset 反而要靠整場轉錄。
  - **`end` 一律由 `start` 鏈反推**（`end[i] := start[i+1]`、`opening.end := 第一段 start`、
    `末段 end := closing.start`），不要各自估算。
  - **Word 可能把兩題寫在同一段答案裡**（`wechat #2` 的問答逐字收在 `#1.answer_text` 內）：該佔位段
    維持 `null` 並在 `notes` 寫明「內文已收在 #X 的 answer_text，另給時間會重疊」。
- **2025-01-16（45/48 個 `start` 錯，稽核一樣全報 `OK`）**——補上 2025-01-17 那一條的另一半：
  - **Δ 表只印「`start` 之後第一個字」會漏掉「`start` 晚到首字已念完 7 秒」**。
    `tieba #3 老奇了` 原值 157.030，但人名在 **149.25** 就念完了（149.25–149.9），正文 156.85 才開始，
    中間 7s 是 **SRT cue[57] 的假空窗**（cue 標 152.71-157.03 卻是靜默）。
    `wechat #3 正念` 同型（−6.91s，cue[108] 標 245.33-252.89 但實際只有 1.2s 內容）。
    → **判別法：把 `start` 前後各 3s 的 cue 與字級軸並印，看 `start` 之前那個字是「過渡語」還是上一段正文。**
  - **SRT cue 的長度不能當「這段有那麼長內容」的證據**；cue 邊界錯亂時以字級時間軸為準。
  - **兩個解碼器可能一個整段丟字**：`tieba #3` 的人名只有 mp3 聽到（opus 從 149.6 直接跳到 156.83）。
    「雙解碼器一致」要理解成**至少一個聽到且兩個不衝突**；一致取交集、衝突取較早者並記 `notes`。
  - **`closing.text` 開頭可能是 Word 的講者標記**（`师父：好了，今天的回答就到这里。` 的「师父：」），
    首字要取標記之後的「好」，別被 `first_word()` 抓成「师父」。
  - **重複出現的 `start` 早於cue[0]** 是開場錯位的可靠指標（2025-01-16 tieba `opening.start`
    比 cue[0] 晚 5.58s、wechat 晚 0.36s）；wechat 開場另有 `cue[0]` 是「啊，」的情況，
    首字要靠**整場轉錄**（短窗 VAD 會丟檔頭）。
  - **拼音模糊比對會有假陽性**：分數 <0.6 的命中要人工看原文（2025-01-16 `wechat #36`
    報「內容在 start 前 37.6s」，實際是 ASR 把「菩薩記錄眾生作的業」聽成
    「你不想進入眾生的業相伴起」導致匹配到別處）。
  - **`opening.text` 不一定以「今天」開頭**：2025-01-15-wechat 的開場詞是「2025年1月15號，回答…」
    ——沒有「今天」，音檔也沒有。開場錨點取**文字首詞**的 onset（「二零二五」＝1.70），
    不是 cue[0] 的「嗯」也不是第二句。
  - **人名／字母名被唸兩次時取第一次**（2025-01-15-wechat `#21 宇小白` 1452.84／1454.62、
    `#22 璽酉` 1481.17／1485.13；原值都落在第二次）。第一次是「叫名」，第二次是「叫名＋讀回題幹」。
  - **`notes` 可能是過期的，別照抄**：`2025-01-15-tieba #22` 仍帶著
    「空答案佔位段；回答已併入下一段」且 `conf=0`，但它有完整 `answer_text` 與 chapter 對應。
    **每段都要用整場字級轉錄確認內文真的被讀到，再決定 `conf`/`status`／清不清 `待人工確認`**。
  - **人名／字母名「唸兩次」取第一次，且要看清兩次的位置**（2025-01-14-tieba `#24 tzmzmr`：
    cue[1169]「TJMJEM」≈2592.01 首次錯聽、cue[1170]「TZNTZMZM」2597.31 重複乾淨，取**第一次**）。
    若兩次之間還有正文，用內容定位確認哪一次後面才接本題正文。
  - **`notes` 可能是過期或未閉合的**（`2025-01-14-tieba #23` 舊 note 寫「依前後段夾入（」但括號未閉合，
    本次已定位真實 onset 後改寫）。`html-resplit …待人工確認` 是**電子書分段邊界**問題、**不是**時間問題，
    時間校準後可 `conf/status` 升級但**保留**該 `待人工確認`。
  - **段與段時間重疊靠重推鏈修復**：`build_maps` 產物可能重疊（`2025-01-14-wechat #5` end 越過 `#6/#7`）；
    只要把每段 `start` 校準後由 `start` 鏈重推所有 `end`，重疊自動消失。
  - **`null` 佔位段可能帶「殘留 label」**（2025-01-13-tieba #6 `start/end=None` 但 label 殘留
    `00:19:17.809`）。**看到 `start=None` 就清掉 `start_label`/`end_label` 為 `''`**，否則審核 UI
    顯示不存在的時間。重推鏈時**必須排除 null 佔位段**。
  - **`index` 缺號是凍結的既有狀態**（2025-01-15-wechat 缺 5，已併入 #6，`notes` 有 `merged:` 標記）。
    `validate_resplit.py` 會報 non-contiguous ERROR；`index`／`stable_key`／`question_id` 屬文字欄位，
    **不要重編**。

## 8. 完成定義

- [ ] 每段從 `start` 播放，第一個聽到的詞＝段落文字第一個詞（允許 ASR 變形）
      → 工具化：`listen_check.py --month M --tol 0.55 --win 6`（2024-12 實測 389/399 通過，
      剩下 10 個逐個人工核為 ASR 變形／人名沒唸出，位置正確）
- [ ] `start` 絕不晚於第一詞 onset（`EARLY ≤1.5s` 合法）；鏈完整（`end[i] == start[i+1]`）
- [ ] **`start` 之前不含過渡語／上一段尾字／上一段正文**（過渡語歸屬依 §2，以字級 onset 切；
      印 `start` 前 3s 確認；`dup_scan.py` 檢查是否漏掉更早的同詞出現）
- [ ] **每段答案內文確實落在 `[start, end]` 內**（整場字級轉錄＋拼音模糊比對；抓整段錯位）
      → `content_check.py --month M --tol 3.5`
- [ ] **短窗錨點與整場轉錄互證**：`cross_check.py --month M --tol 3.5` 沒有未解的大偏差
- [ ] **`opening`／`closing` 的第一字也收尾**（稽核不檢查它們；`closing` 注意 Word 講者標記；
      `opening` 文字首詞可能不是「今天」，且**開場以整場轉錄的檔頭為準**——短窗 VAD 會整段丟掉 0–4s）
- [ ] **人名／字母名唸兩次時錨在第一次**（但若兩次之間講的是上一題內容則取第二次，
      見 `AGENTS.md` 2024-12 教訓 8）；`notes` 已過期者（`conf=0` 卻有完整 `answer_text`
      與 chapter 對應）要重估 `conf`/`status` 並在 `notes` 說明依據
- [ ] **跑過至少兩輪「重測 → 只補 overrides」**（2024-12 第 2 輪又找出 13 個真錯；
      2024-11 做到第 3 輪，第 2 輪又找出 16 個真錯、含 4 個 9–59s 的整段錯位）
- [ ] **`weak`（分數<0.62）超過 1/4 邊界時，不要把 `propose_fixes` 的 delta 當候選清單**（2024-06 是 51/214，第一輪只有 53/214 判 OK）：**每一個 weak 都改跑 `reanchor.py` 內容探針**
- [ ] **`start` 整段系統性漂移 >10s 時，`batch_anchor.py` 的 `[start±9s]` 窗會完全失效**
      （2024-03-05 從 #14 起累積偏移，到 #37 已差 109 秒）。此時改用
      `rebuild_anchors.py`（整場轉錄內容探針 + 單調約束）；輸出**必須先做單調性自我檢查**，
      出現逆序＝順序又錯了，該用 `swap_order.py --shift A:B` 搬位（不是 `--move` 對調）
    - [ ] **用整場轉錄重建錨點時，單調約束要「一律」套用**（不能只在 `st < prev` 時套），
      否則探針會命中前面出現過的同樣字串；且**命中時間是探針位置不是答案開頭**——
      只用 0% 探針當錨點，其餘探針僅作佐證
    - [ ] **ASR 差的月份（2024-02…08）錨點要「人名 onset ＋ 內容 onset 合流」**，
      單獨用哪一種都不夠：短窗 `first_word` 只認得人名（人名常沒被唸）；
      0% 內容探針認得正文但容易配到措辭雷同的別段。
      規則：**首詞 ≥2 字且 `sc ≥ 0.9` → 用人名字級 onset；否則用 0% 內容探針**
      （2024-03 實測：只用內容 330 例外、只用短窗 280、合流 **173**）
    - [ ] **`swap_order --shift A:B` 對「相鄰且 A 在前」是 no-op**（`target = ib−1 = ia`）。
      相鄰交換要用 **`--swap`**；`--shift` 只適合「把 A 搬到遠處」
    - [ ] **`--swap` 被守衛擋下時，先把實測到的正確時間寫進 JSON 再換位**
      （守衛只看 `start`）；換位後 `index` 全場重編，**`overrides` 的鍵要重新產生**
    - [ ] **null 佔位段的 `notes` 不是定案依據**：2024-02 有 **35%**（30/86）、
      2024-03 有 **24%**（24/101）的「音檔中找不到對應內容」其實有被唸出（多筆 sc=1.0）。
      主題式講解月份（2024-02…08）都要整批重掃 null 段
    - [ ] **`closing.text` 為空時，收場時間要對齊 `ffprobe` 檔長**（2024-02/03 全部如此）；
      無 `closing` block 的月份才把尾巴掛在末段 `end` 上，兩者不可混用
    - [ ] **`content_check.py` 沒有單調約束**，它報的「首內文早於 start」常是
      首探針撞到前面重複字串的假陽性（2024-03 的 42 個 BAD 加單調約束後真錯位為 0）；
      凡用整場轉錄定位都要自己加「從上一段 start 之後才找」的約束
    - [ ] **null 佔位段不可因為 `notes` 寫「音檔中找不到對應內容」就當定案**——
      那是當年某次比對的結論。2024-03 用區塊對齊重掃 101 個 null 段，**24% 翻案**
      （24 段其實有唸出，補回時間後 `matched 1122→1146`）。
      收尾時用當前最強的定位方法重新掃一次 null 段
    - [ ] **改完 `start` 一定要重跑 `batch_anchor` 再跑 `listen_check`**：
      `listen_check` 讀的是快取窗，`start` 移動超過窗邊界時窗不再覆蓋 `[start, start+6]`，
      會產生**假的例外**（2024-03 實測同一份檔案重測前 187／重測後 186）
    - [ ] **整場轉錄定位要用「拼音區塊對齊」，不要用「跳過人名的固定字數」或「答案前綴」**：
      人名常沒被唸（固定字數會切到正文中間）、老師常跳過開頭（前綴永遠對不上）。
      並且**必須限制最多提前 1.5s**——12s 窗的最前 4 秒是上一段的尾巴，
      實測 470 筆全被拉到 `start−3.49s`（窗邊界）
    - [ ] **字母／數字人名整類跳過內容探針**：`moonlight` 會被一個字母一個字母拼出來
      （佔 6 秒），內容探針會滑到拼完之後，正好跳過整個人名（2024-03 全月 91–94 段）
    - [ ] **驗「末段 `end` == 檔尾」用 `ffprobe`、不要信 `media_parts[].duration_est`**（2024-04 `04-22` 差 56.6s、`04-23` 差 23.6s；`duration_est` 是 SRT 最後一 cue 的結束時間）
    - [ ] **同一個人連問兩題時，答案首詞不是人名就錨在答案的首個實字**，不是最近一次叫名
    - [ ] **量錯位段時確認「量到的字串屬於哪一段」**：命中字串必須**同時符合本段 `answer_text` 的前綴**
      **且不在上一段的窗內**（2024-05 `05-24 #26` 第一輪量到的是上一題句尾的讀回句 `那個是不是`）
    - [ ] **重排 `segments[]` 後把被重排段的 overrides 重新對映到新 index**，否則會報「非嚴格遞增」
    - [ ] **`content_check` 報「後內文超出」時先確認首／中探針是否在窗內**——在窗內就是撞到別段的重複字串（2024-06 的 2 個 BAD 全是這類），當假陽性處理、**不要重排段落**
- [ ] **`segments[]` 指數序＝音訊序**（`apply_alignment.py` 會擋；用 `swap_order.py` 重排）。**判斷順序錯位類型**：先用 `reanchor.py` 的內容探針把相關各段**各自定位**，**看定位出來的先後順序**——相鄰對調用 `--swap`，**3 段以上循環錯位用 `--move` 兩次**。循環錯位在時間軸上長得像「每段都錯 100 多秒」（2024-07 `07-15 #44/#45/#46` 各錯 146–212s）
- [ ] **`#1` 是 null 佔位段的場，`#2.start` 與 `opening.end` 各自用 `onset_at.py` 量首字**
      （鏈接得起來不代表對；2024-09 六場全是這個形狀，兩場錯 15–24s）
- [ ] **`opening.text` 為空字串時開場錨點要手動量**（自動管線不產生候選）；
      **但要先確認音檔有沒有開場框語**：有（2024-09「今天是…」）→ 量首字；
      **無（2024-08 一開口就是第一題叫名）→ 留 `0.0` 讓給 `#1`**，否則開場變零長度並與 `#1` 相撞
- [ ] **沒有 `closing` block 的 session**（全庫 18 個）末段 `end` 維持原值（等於音檔長度）、
      不算結構問題
- [ ] **`apply_alignment.py` 報「非嚴格遞增」時往回追**：相鄰兩段 `start` 相同通常代表
      其中一段**整段錯位**（2024-08 `#44`/`#45` 同為 3232.2，往回追挖出 `#43` 錯 236 秒）
- [ ] **`closing`／`opening` 的 `text` 真的在它被錨的那個位置被唸出**
      （2024-11-11 的收場 block 其實是檔案中段的「貼吧→微信」問答，已在 `notes` 標 ⚠️）
- [ ] 文字欄位 0 違改（`apply_alignment.py --verify-text <backup>` 或 git diff 驗證）
- [ ] `post_align.py` 結構 issues 0、stats 已重算；`validate_resplit.py` 沒有**新增**錯誤
- [ ] 修正段 `notes` 記錄錨點證據（含跨窗／解碼器分歧）
- [ ] 交付：`<month>.json` ＋回報（重排 block、修正段含 ms、誠實空缺理由、stats）
