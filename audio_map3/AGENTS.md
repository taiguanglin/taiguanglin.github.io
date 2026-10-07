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

**別再踩的十條教訓：**（第 8 條含 zero 錨點陷阱；第 10 條是做表前的檔案盤點）

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
4a. **相鄰的「經文段／講解段」可能被整組對調**（L25 [103]/[104] 差 **21.4 秒**）。
   判別：DTW 最佳命中落在**鄰段**而非本段，且**兩段的命中互相交換**。
   `span_audit` 與首字指標都可能看不出來 → 逐段 DTW 搜尋時要順帶比對鄰段命中。
   ⚠️ **`--mode metric` 的 `t_first` 會系統性誤命中「上一段經文」的同一個字**（L30）：
   楞伽經是「經文段 → 白話講解段」，師父講解時幾乎逐句重念經文，同一串字在音檔出現 2–3 次。
   L30 的 6 個 metric 離群值中 **5 個是這個假象**（[42] +3.24→實為 [41] 經文、[54] +2.50→[53] 經文、
   [74] +2.13→[73] 經文、[82] +2.08→[81] 的「財利」、[39] −1.58→第二個「世」）。
   **動任何段之前，必須用 `--mode chars` 確認 metric 命中間的是「本段」的字**——
   L30 一度照 metric 把 [42] 移了 3.3s，反而把 [41] 夾成 1.34s／52 字（同輪回退）。
   ⚠️ **更危險的反面：工具「沒有意見」不等於「沒問題」**（L31）：[71] 原值晚 **24.85 秒**，
   而 `--mode metric` 的證據表裡**根本沒有 [71]**（20 字前綴比不中 → 靜默跳過），
   `--mode final` 對它的判定是 **`why:"keep"`**（`sum` 0.275＝信心極低）。本講 80 個 READ 段中
   `metric` 只覆蓋 36 段；**未被覆蓋＝未判定**。→ 全講一次 dump 的逐字流
   （`--mode chars --lo 0 --hi <dur> --width 34`）＋以現值為中心的 ±5s 分段視窗，
   是 L31 找出這個錯位（並在兩輪內判完 80 段）的主力工法；逐段工具一律降級為線索。
   ⚠️⚠️ **量化版：`--mode metric` 有「窗盲點」——搜尋窗只有 `[start−3.0, start+7.0]`，
   偏離真值超過約 7 秒的段在報表裡「根本不會有那一行」**（L32）。
   「metric 表上沒有這一段」＝**未判定**，不是「正確」。L32 六個實例：
   [68] 1237.40→**1220.88**（−16.52s）、[58] 970.03→**985.59**（+15.56s）、
   [69] 1258.82→**1245.26**（−13.56s）、[71] 1294.464→**1286.05**（−8.41s）、
   [32] 455.31→**447.85**（−7.46s）、[90] 1591.98→**1587.08**（−4.90s）——**六筆全部無 metric 列**。
   L31 的 [71]（−24.85s）與 L32 的 [68]（−16.52s）**兩講的最大錯位都落在窗外**。
   → **驗收紀律**：完成後必須用 `--mode chars --lo/--hi` 對**每一段**首字獨立確認一遍
   （L32 做了 88/88），不可只看 metric 有覆蓋的段。修正後覆蓋段會長出來
   （L32：28 → 31，新增 [56]/[71]/[90]），可拿這個差值當「本輪修到幾筆窗外錯位」的量化證據。
4b. **「吞尾」（start 早於首字）是比例最高的缺陷型態，且 `span_audit` 完全看不到**：
   L24 有 **56%** 的段早於首字（median −0.99s，十二講最差），而 `span_audit` 全程 90.0% 不動。
   每講都要看 `seq_align.py --mode metric` 的 **early / late 兩個方向**，不能只看 late。
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
   ⚠️ **切片時基的精度不是全域一致**（L21 實測）：非掉字區差 0.3–1.0s；掉字區邊界附近（主 dump
   剛恢復處）吻合到 0.01s；但**掉字區內部差 1.2–1.85s、音檔尾端差 1.8–2.6s**。
   ⚠️ **時基驗證必須多窗，且任一窗失敗即棄用切片**（L26 實測：同一講 1000–1012 窗差 0.2s、
   **700–712 窗卻差 4.1s**，結論互相矛盾）。L20 只驗兩窗就採信，本講證明那不夠。
   → 掉字區裡定段界，**能在主 dump 找到對應字就用主 dump 精確值**；只能靠切片的取 ±1s
   合理值並在裁決表 note 標明精度。
   ⚠️ **切片的「時間戳」不可信，但切片的「文字」完全可信**（L30 新招）：把切片拿去重新轉寫，
   文字會直接告訴你「**這 14 秒念的是哪一段**」。L30 在時基三窗互相矛盾、時間戳全部棄用的情況下，
   靠切片文字在 **61.7s 掉字區**（1589.0–1650.7）訂出 `[89]→[91]→[92]→[93]` 的內容順序
   （1590–1604 窗＝「法律啊什麼是法律呢？為療法實行見愛無我」＝[91]；1626–1636 窗＝「你要滅掉…
   一切諸佛所供灌頂具諸受行」＝[92]），且三者合計 4.28 字/s 佐證正確。
   ⚠️ **判「師父停頓」之前先量音量**：`ffmpeg -ss X -t Y -i FILE -af volumedetect -f null -`
   （**不要加 `-v error`**，會把報告一起吃掉）。L30 掉字區 `mean_volume -11.6 dB` ＝ 有聲，
   是 ASR 失效而非靜音。
7. **`win.py` 的行內插值不能拿來定段界**（誤差可達 2s，L16 實測兩次踩到，其中一次把
   本來精確的值改壞）。插值只用來定位「要看哪一段」，最終取值用
   **`seq_align.py --mode chars --seg N`**（逐字＋精確秒數）。
8. **`milli_refine` 的 READ 身分＝「有無實寬 span」（`end != start`），且必須「變更前」記錄**：
   - **不可用 `zero` 標記判定**：L22 [84] 同時 `confirmed` + `zero:true` 卻有 3.85s 實寬
     （pre-existing 資料不一致）。舊判準因此把它踢出 READ 集合，鏈 pass 把 `[83].end`
     直接接到 `[85].start` → **3.85s overlap 鏈破口**（L22 r2 實測）。現已修：依實寬判定，
     並對 `zero`+實寬的段印明確警告交人耳裁決。
   - **必須變更前記錄**：裁決表同時改相鄰兩段且後段 start 後移時，事後判定會把先套的
     那段誤判掉 → 產生**負長度 span 並靜靜寫進 SoT**（L18 r2 [48]/[49] 實測）。
   - 鏈 pass 後若仍有負長度／破口 → **abort 不寫檔**。
   - ⚠️ **驗收要比對「目標講次自身的鏈破口數量是否新增」**——只驗非目標講次會漏掉這類
     自身造成的破口（L22 靠這一步才抓到）。
   - **畸形 span（<1.5s 裝 20+ 字）是「待查線索」不是「缺陷結論」**。兩種成因：
     ① **相鄰段造成（三個方向都會）**：下一段**太早**（L23 [32]/[33]、[85]/[86]）、
        下一段被**前移**（L26 [122]：83 字/s）、下一段被**後移**（L29 [81]：62.8 字/s），
        三者都會夾短本段 end → **相鄰兩段必須一起定**；
        **每筆改動後都要回頭檢查前一段的畸形 span 旗標，三個方向都要查**；
     ② **⑤ 交錯 + 半讀**：經文後半落在下一段 COMM 的 span 內，首字其實對上了
        （L27 [65] 1.32s／53 字、[102] 0.7s／31 字）。
     → **判別順序：先看首字有沒有對上。對上了就是半讀／交錯，不是錯位；沒對上才去查相鄰段。**
     ⚠️ **修正過程中自己製造的問題要在同一輪修完**（L29：22 筆套用後驗收抓到 [81]/[91] 被自己
     後移夾短，當場補 2 筆重跑，表 22→24 筆，畸形 span 歸零）——不要因為「已經套過了」而放著。
   - ⚠️ **confirmed 的 zero 段會擋住下一段前移**：zero 錨點＝前一 READ 的 end 不可動，
     把下一段 start 前移到錨點之前會造成 **`[zero].start > [next].start` 破壞 start 單調**。
     證據充分也要放棄（L23 [30]），記入 earcheck 交人耳裁決。
   - ⚠️ **驗收三項缺一不可**：① 非目標講次 byte-identical ② 目標講次**鏈破口數量不可新增**
     ③ **start 單調**（L22 靠 ②、L23 靠 ③ 各自抓到一個只有套用後才顯現的問題）。
     ⚠️ **HEAD 既有資料可能本來就單調性違反**，且 **confirmed zero 的錨點可以錯 20 秒甚至 61 秒**：
     - L26 `[60]` confirmed zero 錨 716.98 > `[61]` 716.50（偏 0.48s）→ 把 [61] 設為 716.98
       且符合字級證據即可恢復單調（[60] 成為孤兒 zero，交人耳裁決）。
     - L28 `[10]` confirmed zero 錨 86.30，而正確的 `[9].end = [11].start = 66.31`（**偏 20s**）
       → **不能修**：[10] 是 confirmed 不可動；把 [11] 推到 86.30 會製造 20 秒的**已知錯誤**，
       那比留下單調性違反更糟。
     - L30 `[90]` confirmed zero 錨 1651.91，正確值 **1590.60**（**偏 61.3s**）→ 同理**不套用**，
       改寫成 `lengqie_L30_adjudication_r4_blocked.json`（可直接套用的完整表＋指令）並列 earcheck
       最高優先。目前 [91]/[92] 仍呈 0.07s／155 字、0.26s／102 字（物理不可能）＝**已知且已交人耳**，
       不是漏修。
     → **「單調性無法修復」可以是合格結論**，前提：① 逐字證明該段值正確 ② 指出阻擋者是 confirmed
     ③ 寫進 earcheck 最高優先項。**不要為了讓檢查變綠而製造已知的錯誤。**
   **相鄰兩段都改時，table 裡兩邊都要列**（只改一段會留下舊 `end`）。
   附帶：`zero: true` 的 `start` 必須寫「**鏈後的值**（＝下一 READ 段的 start）**，
   不能寫原 span 的任意值**——寫錯 `milli_refine --apply` 會變成非 idempotent
   （每次都被鏈 pass 覆寫）。**驗收連跑 2–3 次 `--apply`，第 2、3 次必須是「0 段變更」。**
9. **永不對整個 `<series>.json` 下 `git checkout`**：L17 輪為測試「裁決表單次套用可重現」
   而 `git checkout`，把已套用的 L13／L14／L16 修正**全部沖掉**（靠四張裁決表重套才救回）。
   - `milli_refine --apply` 本身 **idempotent**（第二次跑＝0 段變更）——在同一份工作樹上直接
     跑第二次就能證明可重現，**不需要**還原 git。
   - 每次套用後的驗證**必須涵蓋先前所有講次**（非目標講次 byte-identical），不能只看目標講次。
10. **做表前先盤點 `reports/`：rN 檔可能已存在於 HEAD，直接覆寫就是資料損失**（L31 實例）。
   - 一定要先 `git ls-files tool/jiangjing_para_map/reports/ | grep <series>_L<N>`；
     成果寫 **`…_r2.json`**（或下一個未用的 rN），**既有 r1 原檔不動**。
     L31 第一輪把成果寫進同名 `lengqie_L31_adjudication.json`，覆寫了受版控的 r1（靠
     `git checkout -- <該檔>` 還原；**該指令只准用在 reports/ 的 rN 檔，永不對 `<series>.json`**）。
   - **r1 幾乎都是「未套用」的確認表**：L30／L31 的 SoT 區段都**找不到 `method:"span"`**
     （L30：`ngram 82 / dtw-evid 18 / miss 2`），而 r1 表是 zero_audit 期的產物，
     其 `start` 值與 builder 產出相同，差別只在 `end`／`conf`／`method` 的鏈同步。
     → **只套用自己產出的 rN**；把 r1 一起套會多出「移除 `confirmed: False`」等中繼資料變動，
     與 L30 的既有狀態不一致。判準：套完後目標講次的 `method` 分佈應與前一講同型
     （L31 只套 r2 → `dtw-evid 57 / ngram 33 / miss 1`）。
   - r1 與 r2 對同一段的 `start` 不同時，**r2 是最後套用的贏**；單獨重跑 r1 會把 r2 的
     幾何修正還原（L31：r1 單跑＝20 段變更、再跑 r2＝16 段變更，序列終態不變）。
     **驗收要驗「r1→r2→r1→r2 的序列終態穩定」，不能只驗單表冪等。**
   - **L32 已照此紀律執行，結果再次印證「只套 r2」**：L32 在 HEAD 有 tracked r1（18 筆：
     6 筆 zero→READ ＋ 12 筆「鏈邊界同步」）＋ r1 earcheck。r1 的 zero→READ 判定與 r2 一致，
     但**六個起點全都不是首字 onset**（86.52／332.50／442.39／534.41／924.68／1580.85），
     r2 逐段回正為 86.52（不變）／334.74／443.47／534.23／925.02／1581.67；
     r1 的 12 筆「鏈邊界同步」在 r2 全部被真值取代。只套 r2 → `dtw-evid 75 / ngram 19`，
     與 L30／L31 同型（r1 的 `method:"span"` 在 SoT 區段找不到痕跡＝r1 未落地）。
     **序列終態實測（在 `/tmp/pre32.json` 的沙箱副本上跑 `r1→r2→r1→r2` 兩輪，SoT 全程不動）**：
     兩輪終態 sha 相同（**穩定**）、且**幾何（start/end/zero）與 r2-only 完全相同**；
     唯一差異是 **[11] 的 `method`**（r1 標 `"span"` vs r2-only 的 `"ngram"`，因 [11] 首字本來就對，
     r2 未列它）。依本條紀律取 **r2-only** ✓。→ **沙箱副本是好工具**：要驗「舊表再套會不會污染」
     時，把 `cp <pre-state>.json audio_map3/<series>_test.json` 後對它跑，驗完刪除，
     比對真正的 `<series>.json` 下 `git checkout` 安全得多（後者永遠禁止）。
   - ⚠️ **`batch_verify` 的嫌疑筆數是「起點缺陷嚴重度」的領先指標**：L31 5 筆嫌疑只有 1 筆真錯位，
     **L32 5 筆嫌疑全部是真錯位**（[12] −5.00s、[26] −7.66s、[56] −7.01s、[58] −7.87s、[69] −16.49s，
     且 [58]/[69] 還低估幅度，真值為 +15.56s／−13.56s）——最後 L32 的變更段數 75 筆 vs L31 57 筆。
     → 嫌疑筆數多、或 z 值超過 ±7s 時，直接進「全講逐字 dump 逐段判」流程，不要逐段探測。
   - ⚠️ **`milli_refine` 的鏈 pass 只在 `--apply` 時跑，dry-run 顯示的是「鏈前」狀態**（L33 實測）：
     裁決表只給 `start` 時，dry-run 看起來每段 `end` 都還是舊值（滿屏重疊），
     但 `--apply` 會把每個 READ 的 `end` 接到下一 READ 的 `start`（L33 同步 80 段），
     並對負長度／破口 abort。→ **dry-run 不能拿來檢查單調性／鏈破口**，只能看表筆數與 `start`；
     鏈與單調的驗收一律在 `--apply` 之後做。
   - **L33 已照此紀律執行（r2-only、80 筆）**，並新增一條掉字區工法：
     **切片重跑 ASR 只信文字、不信時間戳時，凡主 dump 同區有字就回歸主 dump 精確值**。
     L33 三大掉字區（790–810／1385–1400／1643.9–1661.9s）全靠切片文字定「哪段在哪」，
     但同一段音訊用 `1430–1441` 與 `1432–1442` 兩窗得到 色@1433.81 vs 色@1433.27（差 0.54s）、
     `1240–1250` 窗對主 dump 系統性 +0.68s、`1750–1762` 窗內兩處錨點自相矛盾（−0.75／+0.38）
     → **切片時間戳只到 ±0.6s**：能在主 dump 找到對應字者（[78][79][94][96]）一律用主 dump，
     主 dump 全無字者（[45][46][76][90]）才用切片值並標 `conf=0.7` 寫進 earcheck。
     成果：`早<−0.7s` **44% → 2%**、`±0.7s 內 51% → 96%`、覆蓋段 45 → 51，殘餘 2 筆 `|d|>0.7`
     已逐字證明是工具假象（[11] 命中上一段經文、[17] 命中本段第二個字）。
   - **L34 再證此紀律（r2-only、74 筆），並確立「經文逐句插講」型**：本講經文段是
     「念一句經文 → 講一段白話 → 再念下一句」，因此**經文段的 span 可以只有 2 秒**（[66]：
     只朗讀首句 `始造即舍无常者` 1360.22，其餘各句分別落在 [67]/[68]/[70] 的 span 內）。
     處置原則：**前段（經文段）保留自己的朗讀起點；後段（講解段）取「朗讀結束後、屬於自己的
     第一個內容」**（L34 [72]→1470.04、[67]→1362.20、[74]→1494.50）。若讓後段取自己的導言
     （如 [72] 的「下面讲第二种外道」1456.97 在經文朗讀**之前**）就會 `start[後] < start[前]`
     → 鏈 pass 產生負 span → 工具 abort，**所以交錯時不能無腦取首字**。
   - **L34 另證：`clip_probe` 能救回主 dump「整段」遺失的內容**。本講主 dump 在 **2009.31 之後
     全無時間戳**（[96] 65 字＋[97] 12 字沒有時間）；五個切片窗（`1970–1992`／`1990–2010`／
     `2006–2029`／`2014–2022`／`2021–2029`）不只補回文字，還原了 [78] 被誤轉的
     「大家想想看」（主 dump 讀成「这里选两个」）。**但切片跨窗時基會漂移 ~1.1s**，
     故尾段用**全片長度**交叉檢核（`[96] 65 字 ÷ 3.9 字/s + [97] 2.3s + 2009.78 ≈ 2028.5` ✓）
     並標 `conf=0.8` 列入人耳清單。
   - ⚠️ **`metric` 的 `t_first` 也會命中「老師的過場語」**（L34 新發現）：[95] 的 `t_first`=1976.62
     是老師唸偈語前的「下面是一段偈语」——**這句話不在任何段落的印出文字裡**；[86] 的
     `t_first`=1780.35 則是 [85] 經文內的「我说」。殘餘 4 筆離群（[48]／[67]／[86]／[95]）
     全部屬「上一段經文／過場語／本段第二個同音字」三類假象，逐字駁倒後即 45/45。
     成果：`早<−0.7s` **53% → 2%**、`±0.7s 內 40% → 91%`、median −0.74 → **+0.00**；
     `span_audit` 83/98 = 84.7%（唯一 2 筆 span_bad 亦為上面兩類假象）。
   - **L35 再證此紀律（r2 53 筆 ＋ r3 3 筆），並新增「重引陷阱」與「切片時基吻合」兩條**：
     ① **段頭落在重引上**——本講開頭是「整段經文先念（18.40–32.26）→ **再重引一次**（32.54–39.14）
     → 講解（40.52）」，[6] 的殘值 32.54 是重引，印出文字的首次宣讀在 **18.40**（−14.14s）。
     通則：**經文段取「首次宣讀」，COMM 段才取「重引」**（與 SKILL §3 ⑤ 相反），
     判別法＝用 `--mode chars` 看前段 `end` 之後、現值之前有沒有本段印出文字的逐字串。
     ② **切片時基這次與主 dump 吻合到 0.02–0.03s**——兩處 27.1s／31.7s 連續掉字
     （629.28–656.40、809.59–841.27）由 `clip_probe` 兩窗各半還原，邊界 大@657.58（主 dump）
     vs 657.56（切片）、842.47 vs 842.44。⚠️ 這**不推翻** L34 的「跨窗漂 1.1s」；
     判準不變：**主 dump 找得到就用主 dump**，切片只補主 dump 沒有的字。
     ③ **metric 會命中「順序吻合的第二次重念」**：[33] 音訊是「**群讀**三句引文（695.78–700.54）
     → **再**逐句重念講解（若生若滅@700.96）」，metric 因順序相同而取 700.96（d=−5.18）。
     通則：**命中本段第二個同名引文時，先看第一個引文是不是就等於現值**；是則維持不動。
     本講 3 筆 `|d|>0.7` 殘餘（[33] −5.18／[35] +2.18／[73] +3.60）全屬此類假象。
     ④ **r3 再校的時機**：metric 命中的是**段落印出的首字**且音近（里／離、非、為）時，
     即使與現值差 1.8–2.2s 也應採用；純過場語（「然後呢」「那什麼是…」）則不採用。
     成果：`早<−0.7s` **51% → 3%**、`±0.7s 內 38% → 92%`、median −0.90 → **+0.00**；
     `span_audit` 65/77 = 84.4%、`pin_check` `pinned 73/78 = 94%、bleed 0`。

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
