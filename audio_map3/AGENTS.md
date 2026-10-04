# audio_map3 — 講經系列「段落 ↔ 音檔」對齊（作業總覽＋UI）

> 校對程序、五種念誦情況、結構錯誤型態、ASR 同音對照、逐講驗收 →
> [`skills/milli-align/SKILL.md`](skills/milli-align/SKILL.md)。
> 本檔＝資料模型、產線、UI 操作、已知限制。SoT JSON：`audio_map3/<series>.json`
> （`ganen / sishierzhang / lengqie / liuzutanjing / lengyanjing`）。

## 資料與注入

- SoT 由 `tool/jiangjing_para_map/build_maps.py` 產生（SRT ↔ 段落；重跑保留 `confirmed` 段與
  `reviewed` 講次）。結構：`lectures.{N}.paragraphs[] = {pid, text, start, end, conf, method,
  confirmed}`，講層 `reviewed`／`audio`／`duration`；「零長度」段另有 `"zero": true`。
- 注入：`tool/books2ebook/para_audio_map.py` 把 start/end 寫進段落元素 `data-start`／`data-end`，
  前端 `09b-para-track.js`（跟播 toggle／高亮捲動／點段落即播／段末自停）依此運作。
- **注入器只讀 `reviewed` + `start`/`end`**，不讀 `method`/`conf`/`confirmed`；跟播閘門＝講層
  `reviewed=true`；`end <= start`（零寬／不念的經文段）跳過、不注入。`method`/`conf` 純屬校對
  與稽核 metadata。想生效：UI 勾「本講校對完成」並存回（**agent 不代勾**）。
- 重新注入：`cd tool/books2ebook && python3 gen_all.py`。
- 交付：`audio_map3/<series>.json`（UTF-8、`ensure_ascii=False`、按講次排序；保留 golden 講次
  的 confirmed 段）＋人工試聽清單（`tool/jiangjing_para_map/reports/`）。

## 使用（校對 UI）

```bash
cd <repo root> && python3 -m http.server 8931   # 或 audio/serve.py（需 Range 支援以拖動音檔）
# 開 http://127.0.0.1:8931/audio_map3/
```

- 系列分頁 → 講次（顯示確認進度）；段落卡片信心著色（綠 ≥0.8／黃 0.5–0.8／紅 <0.5 或 miss）、
  start/end 可編輯（mm:ss.s）、▶ 播放、確認 checkbox，右上角另有「零長度」checkbox。
- 「設定」可切換：手動輸入起訖時是否自動同步上一段結束／下一段起始（預設開；關閉後只改本段、
  允許重疊或留縫；同步時自動穿越中間的「零長度」段）。
- 快捷鍵：空白播放暫停、`S`/`E` 設目前播放時間為焦點段 start/end、時間欄聚焦時 ←/→ ±2s、
  ↑/↓ 切換焦點段；一般非輸入狀態 ←/→ 快退／快進 5s。
- **跳瀏工具列**（topbar 左側常駐）：「⤒ 下一個未確認」「⤓ 下一個已確認」循環定位，只捲動不播放、
  不寫 `lastPlayed`；右鍵／長按＝定位並播放；快捷鍵 `N`／`Shift`+`N`；徽章顯示本講剩餘未確認
  段數（確認＝`meta.lastPlayed` 有值**或 `zero: true`**；開場不計入，與側邊欄統計一致）。
- 儲存：GitHub PAT（Contents: Read and write）存回 `<series>.json`；「下載 JSON」備援；未存修改
  留在 localStorage 草稿。
- **`<series>.json` 只讀同源檔案**（與 `/audio_map/` 相同，`loadMonth()` 裡直接 `fetch`）：
  localhost／本機預覽讀工作樹，線上讀 Pages 部署副本，**不再**繞去
  `raw.githubusercontent.com`（2026-10 移除：那個讀法在部分網路下不穩，8 秒逾時＋退回同一個
  已部署檔案，實際只是多一個失敗點）。代價：commit 後要等 Pages 建置才看得到新資料；要立刻確認
  遠端版本用衝突對話框的「重新載入遠端」（走 contents API）。
  **topbar 常駐徽章 `#dataSourceBadge`** 標「來源 本站檔案 · 9/8 15:57」，滑過有完整 URL、
  **該 JSON 在 main 最後一次 commit 的時間**（含「24 天前」相對時間）與判讀說明——**看見舊資料先看
  這顆**。`#saveStatus` 是會被播放／校時／存檔洗掉的暫時訊息，不能拿它當來源依據。
  - 時間來源是 `getLastCommit()`（commits API）：同源檔案**沒有** `Last-Modified`、contents API 也
    **沒有**日期欄。以 `Promise.allSettled` 與既有的 `getFile` 並行，不拖慢載入。
  - 讀不到（離線／額度用完）顯示「時間未知」並把徽章轉成虛線灰（`data-unknown="true"`），**不猜**。
    存檔成功時 PUT 回應自帶新 commit 時間，徽章立刻更新——重新整理後時間對得上＝存檔確實落地。
- **防遺失機制（不要改壞它）**（與 audio_map2 同款）：本機草稿是唯一能救回「按了儲存但沒存完就
  離開」的東西。
  - **草稿本體在 IndexedDB**（`assets/draft_store.js`，三個審核 UI 共用同一份模組與 database，
    key 帶 `audio_map3/…` 路徑所以不會互相覆蓋），localStorage 只留 metadata 索引（約 120 bytes），
    `listDraftPaths()`／`hasDraft()` 仍同步。⚠️ 別改回 localStorage 存文字：一個系列 JSON 就是
    0.5–1.9 MB，額度約 5 MB 且三個 UI 共用，寫滿時 `setItem` 丟 `QuotaExceededError`，而存檔流程
    會先 `flushDraft()` 再上傳，於是整個上傳被中止（2026-10 實際發生過）。舊草稿由
    `initDraftStore()` 自動搬進 IndexedDB，順便把額度還回去。
  - `scheduleDraft()` 800ms debounce 有 **2500ms 硬上限**（`DRAFT_MAX_DELAY_MS`）；
    `flushDraft()` 回傳 promise 且**永不 reject**，`saveCurrentMap()` 會 `await` 它再上傳；
    `beforeunload`／`pagehide`／`visibilitychange:hidden`（手機切 app、下拉重整）也各自觸發。
    IDB 沒有同步 API，離頁點只能啟動寫入，真正有時間落地的是 `visibilitychange:hidden`。
  - `pendingSave` 標記（`storage.js`，經 `safeSetItem()` 不會拋 quota 例外）記錄「上傳開始但沒完成」，
    成功才清除，下次看到草稿時對話框會明說上次上傳未完成。存檔失敗不會丟任何東西。

### 「零長度」標記（`"zero": true`，2026-09 新增，與 audio_map2 同步）

勾選＝此段音檔長度為零（師父沒念，多半是不念的經文段）。行為：起訖強制相等（原起始為錨點）、
時間欄唯讀、卡片淡化禁播；調整前後段時邊界自動吸附（可連續穿越多個零段）。管線保護：
`build_maps.py` 的 `merge_existing` 保留 `zero` 並把起訖壓回相等；`realign_dtw.py` 把 zero 段與
confirmed 鐵錨同等 pin 住。人工校正「誤留極短長度的沒念段」就用這個勾選修復。

## 0a. 產線現實（2026-09 定稿，最優先讀）

**「毫秒級對齊」是四種東西疊出來的，不是單一對齊器：**

| 階段 | 工具 | 角色 |
|------|------|------|
| ① 粗對 | `tool/jiangjing_para_map/build_maps.py`（`method=ngram`，SRT 字元流 + difflib/bigram） | SoT 產出器、唯一寫入 `reviewed`/`confirmed` 標籤者；品質不均（硬講次 avg_conf≈0.3） |
| ② 精修 | `realign_dtw.py`（FunASR 字級 dump + DTW） | 高訊號對齊器（`dtw-evid`／`interp`／…），**歷史路線**，已被 milli-align 取代 |
| ③ 序列重錨 | **`skills/milli-align/scripts/seq_align.py`**（雙向邊界最佳化 → 短前綴滑動 DTW → run-onset） | **現行匹配器**：逐段產出 start 提案（`--mode final/bopt`）；`--mode metric` 是「首字有沒有對到」的**唯一客觀指標** |
| ④ 人工確認 | `index.html`（試聽＋段尾自停＋`lastPlayed`→`confirmed`＋講層 `reviewed`） | **毫秒級最終裁判** |

**別再踩的九條教訓：**（第 8 條含 zero 錨點陷阱）

1. **`method` 標籤 ≠ 實際演算法**（已確認的 sishierzhang 1–8 期 JSON 一律標 `ngram`，但硬經文段
   位置實際來自 DTW）——**看 `conf` ＋客觀稽核，不看 method 字串**。
2. **「經文不念」沒有 persisted 的 `skipped-sutra` method**：它表現為 `start == end`（零寬），仍標
   `method=ngram`。判斷「不念 vs 沒對到」用逐字比對，不看 method。
3. **重跑安全靠 `confirmed` 旗標，不靠 method**：`build_maps.py` 的 `merge_existing` 與
   `realign_dtw.py` 的 pin 都會在原樣保留 `confirmed` 段的 `start/end`。已確認講次是**鐵錨**，
   任何重跑前後都要驗證 byte-level 不變。
4. **`span_audit` 的 ok-rate 量不到邊界品質**：L13 r2→r3 它一直是 88.5%，但「每段首字對到音檔
   首字」的指標從 65% 拉到 80%（詳見 `reports/lengqie_L13_earcheck.md`）。**驗收要跑
   `seq_align.py --mode metric`**，兩者都要看。
5. **ASR 掉字會讓「結構」錯掉，不只是精度變差**：L20 主 dump 有 **32.7s 完全無字**
   （783.7–816.4），r1 依它定的段界把 **[47]–[51] 整區錯置約 30 秒**，而 `span_audit`
   完全看不出來（同樣靠主 dump 比對）——**只有 `seq_align --mode metric` 暴露出來**
   （±0.7s 內只有 46%）。掉字區的處置見下一條。
6. **ASR 會在同音錯字密集區整段掉字**：L14 有 **30.3s** 空窗（2039.8–2070.1）、
   另有 5 處 8–13s 空窗，音檔其實連續有聲。這些區域的 `span_audit` span_bad／d_head 低是
   **量測假象**，判段界必須用 `skills/milli-align/scripts/clip_probe.py --chars` 切片複驗，
   且**切片時基要先驗**（L14 r2 因此把 [106]/[107] 定錯 1.5–2.4s）。見 SKILL §6b。
   **複驗順序**：① 掃 ≥3s 空窗找掉字區 → ② **先驗時基**（挑兩個非掉字區，切片與主 dump
   逐字比對，差 <1s 才可信）→ ③ 驗過才用切片字級時間定段界。定段界用
   `clip_probe.py --chars --times`（逐字「字+精確秒數」），**不要**用只有行首時間的 `--chars`。
7. **`win.py` 的行內插值不能拿來定段界**（誤差可達 2s，L16 實測兩次踩到，其中一次把
   本來精確的值改壞）。插值只用來定位「要看哪一段」，最終取值用
   **`seq_align.py --mode chars --seg N`**（逐字＋精確秒數）。
8. **`milli_refine` 的 READ 身分必須「變更前」記錄**：裁決表同時改相鄰兩段且後段 start
   後移時，事後用 `end > start` 判定會把先套的那段踢出 READ 集合 → 產生**負長度 span 並靜靜
   寫進 SoT**（L18 r2 [48]/[49] 實測）。已修（`reads_before` + 鏈後 abort 安全網）。
   **相鄰兩段都改時，table 裡兩邊都要列**（只改一段會留下舊 `end`）。
   附帶：`zero: true` 的 `start` 必須寫「**鏈後的值**（＝下一 READ 段的 start）**，
   不能寫原 span 的任意值**——寫錯 `milli_refine --apply` 會變成非 idempotent
   （每次都被鏈 pass 覆寫）。**驗收連跑 2–3 次 `--apply`，第 2、3 次必須是「0 段變更」。**
9. **永不對整個 `<series>.json` 下 `git checkout`**：L17 輪為測試「裁決表單次套用可重現」
   而 `git checkout`，把已套用的 L13／L14／L16 修正**全部沖掉**（靠四張裁決表重套才救回）。
   - `milli_refine --apply` 本身 **idempotent**（第二次跑＝0 段變更）——在同一份工作樹上直接
     跑第二次就能證明可重現，**不需要**還原 git。
   - 每次套用後的驗證**必須涵蓋先前所有講次**（非目標講次 byte-identical），不能只看目標講次。

> 對齊**新講次**請走 [`skills/milli-align/SKILL.md`](skills/milli-align/SKILL.md) §7 流程
> （首字指標 → 提案 → 逐段判讀 → refine → 回頭檢驗 → 驗收），**不要**只重跑 `realign_dtw.py`。
> golden 慣例（鏈、段首 lead-in、講首導言、搜尋窗、語速）見該 SKILL §2，序列對齊器見 §6a。

## 1. 核心心智模型

| 類別 | 辨識 | 策略 |
|------|------|------|
| **講解段（COMM）** | `class` 不含 `sutra-text` | 必須錨到「實際念出的第一個字」；`conf` 反映字元級證據 |
| **經文／偈語段（sutra）** | `class` 含 `sutra-text` | 師父可能念、也可能不念，兩種都要判（SKILL §3 五情況） |

1. 經文段**多數不是逐字念誦**——師父把經文融入白話講解。實證：四十二章 3–14 講 44 個 skipped
   段 **100% 逐字 0 命中**；例外是短經文／偈子會逐字念，要錨成實寬讀段。
2. **毫秒級天花板由 ASR 決定**：只有段落開頭 ~6–8 字逐字出現在 ASR 才能 ≤50ms；文言＋快速帶讀
   的同音錯字只能 pinyin 模糊逼近（±0.5–3s）。誠實標低 conf。
3. **golden（人工 confirmed）段是不可侵犯的鐵錨**：重跑其 `start/end/conf/confirmed` 必須不變。
4. **講首結構慣例**（四十二章 L2 鐵律）：整章經文塊 → 導言白話段 → 經文重複段；正確＝i0 零寬、
   i1 導言 real span、i2 讀出的經文 real span（`realign_dtw` 會把 i0 誤判成有念而吞掉 i1；
   受害 L10/L12/L13/L14）。

## 2. DTW 精修路線（歷史；救 low-conf 段時仍可用）

需 `numpy / pypinyin / opencc / funasr`，統一用 `tool/sense_voice/.venv/bin/python`：

```bash
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/funasr_dump.py --series <series>
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/realign_dtw.py --series <series> [--dry-run] [--lecture N]
```

字元→拼音→4gram 種子投票＋DTW 逐字打分＋語速過濾 → 念／不念判斷（全塊 cov<0.45 不念零寬；
塊頭 cov≥0.5 逐字念實寬；段頭 10 字 chunk DTW≥0.8 片段念；與前段同源 `subsumed-dup`）→ pass2
在已錨定鄰居 gap 內收斂 → 鏈（`end[i]=start[i+1]`，末段 `=duration`，skipped 零寬）→ 夾逼驗證。
`method` 可信度：`dtw-evid` > `dtw*` > `interp` > `skipped-sutra`。
**驗證「不念」必用逐字**（`stream.find()`），拼音模糊會把文言同音白話誤判成有念。

- **客觀驗證（不信自報 conf）**：`span_audit.py --series <X>`（`span_ok`／`skip_ok`（零寬＋逐字
  遍掃無命中）／`span_bad`／`unknown`；零寬段用 char-exact 判定）；`pin_check.py <series>`
  （段頭 6 字逐字出現且 start 釘在該字 ±0.05s；`no-verbatim-hit` 越多＝ASR 越爛）。
- **必修過的 bug**：pinning 後的最終單調 clamp 曾把 confirmed 段 `start` 往前推、污染 golden，
  已在 pin 循環加保護。改動此邏輯必重跑並驗證 golden byte-level 不變；污染寫進 JSON 要
  `git checkout` 還原再重跑。`sim_char`：1.0 逐字／0.9 同拼音（zh/ch/sh 已摺疊 z/c/s）／0.8 同聲母
  韻母僅鼻韻尾或 n/l、f/h 相混；**不要加「同聲母／同韻母」弱分級**（會製造回音假錨點）。
- **誠實信心定義**：`conf ≥ 0.8` 且 `method ∈ {dtw-evid, dtw, dtw2, dtw-frag, dtw-scan,
  skipped-sutra}`；`interp` 最多 0.8 並標 `method=interp` 供人工。**不許**把 `interp`／
  `skipped-sutra` 灌成 `dtw-evid` 等級——那是騙過跟播。

## 3. 已知限制（寫進交付說明，別假裝做到）

1. **ASR 是毫秒級天花板**：只有段落開頭逐字出現在 ASR 才能 ≤50ms；文言＋快速帶讀的同音錯字使
   ~80% 段落無法逐字錨定，只能 pinyin 模糊（±0.5–3s）。
2. **楞嚴咒等長咒／快速咒念**：ASR 幾乎無有效輸出，該區段落只能插值（`interp`）。
3. 遇這兩類誠實標低 conf／`interp`，交付時說明，不灌 conf。

### 3a. 「換更好的 ASR」不能突破天花板（已實證，別再花重工）

Qwen3-ASR-0.6B + ForcedAligner 對 4 講 A/B：段落頭 6 字逐字命中率講解段 paraformer 22–44% vs
Qwen 10–41%；經文段 6–13% vs 4–9%。**換 LLM-ASR 反而更差**——它把語音「整理成流暢文字」、改寫掉
段落那 6–8 字精確字串，而 realign 靠逐字精確的段頭錨定。方向應是**改匹配器**。

### 3b. 三硬系列的誠實底線（楞伽/壇經/楞嚴）

長篇文言義疏 + 楞嚴咒密集朗誦，ASR 同音錯字灌爆段頭，`span_audit bad+unknown` 高但誠實、重跑
不會變好（deterministic）：

| 系列 | 段數 | span_bad | unknown | bad+unknown | 主導殘餘 |
|------|------|----------|---------|-------------|---------|
| lengqie | 4265 | 151 | 306 | 10.72% | 零寬 commentary（段頭同音錯字） |
| liuzutanjing | 3636 | 256 | 319 | 15.81% | 零寬 commentary（L6 最差 40%） |
| lengyanjing | 2784 | 578 | 360 | 33.69% | 525 段零寬 commentary（楞嚴咒區最重） |

主導殘餘＝ASR 天花板具體化，不是可修結構 bug。唯一可靠出路是人工在 UI 試聽後寫回 `confirmed`，
**不要**逐段手灌時間硬湊。對齊前先補齊 `/tmp/funasr_cache/<series>/` 的 dump（每講 CPU ASR 約
1–2 分鐘；`/tmp` 會清空）。

### 3c. 換新系列 SOP

1. `skills/milli-align/scripts/golden_offsets.py --series <X> --golden 1-4` 重測 golden 慣例。
2. 找該系列講首結構慣例（整章印刷塊 vs 導言 vs 重複引文排法各系列不同）。
3. 照 [`skills/milli-align/SKILL.md`](skills/milli-align/SKILL.md) §7 走；SRT 重生成
   （`gen_srt.py`）只在 dump 品質不足時用——dump 已是毫秒源，SRT 只是粗字幕。
