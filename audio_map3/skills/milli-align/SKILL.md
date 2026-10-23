---
name: milli-align
description: >-
  講經系列「段落 ↔ 音檔」毫秒級對齊 skill（L21 r3 定稿）。主力工法＝全講逐邊界走查
  （boundary_walk）：每個邊界取「前段末內容字 END-time」為準，語氣詞／過場歸前段、
  停頓歸下段緩衝、逐句插講與語序型各依專規；時基爭議以 silencedetect 物理停頓為唯一
  仲裁者；掉字區只信切片文字；尾部壞區用音量＋語速反推。metric/final 提案只是線索
  （±3/+7s 窗盲點）。戰史（L5–L42 逐講紀錄）在同目錄 HISTORY.md。
---

# 毫秒級段落對齊（milli-align，r3 版）

把 `<series>.json` 對齊到「每段 span 恰覆蓋它自己的文字被說出的全部音訊」、
且「段首第一字毫秒級對齊實際念出的第一字」。輸入：`audio_map3/<series>.json`、
`/tmp/funasr_cache/<series>/<N>.json`（字級 dump，毫秒源）、`ebook/<K>.html`（SUTRA/COMM
分類）。產線／資料模型／注入見 [`../../AGENTS.md`](../../AGENTS.md)。

腳本（`scripts/`，全部用 `tool/sense_voice/.venv/bin/python`）：**`boundary_walk.py`
（邊界走查證據器，主力）**、`seq_align.py`（metric/final 提案＝線索；chars 模式輔助）、
`clip_probe.py`（掉字區切片）、`milli_refine.py`（套用正典，勿在 /tmp 重建）、
`milli_audit.py`、`zero_audit.py`、`batch_verify.py`、`win.py`、`golden_offsets.py`。

逐講實戰紀錄（L5–L42 舊方法時代的全部數據與案例）→ [`HISTORY.md`](HISTORY.md)。

## 0. 什麼時候用

任何講次要達毫秒級、或已完成的講次要做 r3 級複核時。**r2 時代「metric 85%、晚 0%」的講
仍可能藏著 >8 秒的整段錯位**（L21 r3 實證：[81] 偏 29.05s、[82] 10.81s、[79] 9.51s、
[68] 8.91s，全部落在 metric 搜尋窗外）——所以新講次必須全程走查，不得只看指標。

## 1. 鐵律

1. **golden 不可侵犯**：`reviewed`／`confirmed` 段的 `start/end/conf/confirmed/zero` 套用
   前後必須 byte-identical（寫檔前後都驗）。**agent 永不代勾 `confirmed`／`reviewed`**。
2. **證據先於位置**：每個值要有字級證據（逐字／拼音 END／物理停頓／音量）。沒證據就低 conf
   ＋列人工，不硬猜不灌 conf。
3. **conf 誠實階梯**：逐字 END ≥0.85／拼音 0.7–0.8／切片 ±0.6s 0.6–0.7／尾部反推 0.5／
   掉字區 0.6／弱證據 ≤0.6 列人工。人耳（UI）是最終裁判。
4. **只動目標講次**；非目標講次套用後必須 byte-identical。
5. **head OK ≠ 邊界對**：每個邊界雙向驗（前段末句 needle 命中在邊界前、後段頭 needle 命中
   在邊界後且緊鄰）。
6. **驗證宣稱不可繼承**：每輪後對全部 READ 段首重掃；「工具沒意見」＝未判定，不是正確。
7. **報表紀律**：寫表前先 `git ls-files tool/jiangjing_para_map/reports/ | grep <series>_L<N>`；
   已有 rN 就寫下一個 rN，舊檔不動；**只套用自己產出的表**；**永不對 `<series>.json` 下
   `git checkout`**（L17 事故）。驗收連跑 `--apply` 2–3 次，第 2、3 次必須「0 段變更」。
8. **裁決對象是音檔裡實際存在的話語**；印字只是找尋的線索（L37/L38 語序型通則）。
9. **鏈不可破**：`end[i]=start[next READ]`、末 READ end=duration、start 單調、無負長度。
   confirmed zero 擋路時「不修」也是合格結論（L28/L30 型，逐字證明＋列 earcheck）。
10. **start 落在偵測音節上**是比相似度更強的結構驗證（每個 start 距最近 ASR 字元 ≤0.3s，
    lead-in 例外逐一裁決；L36 網）。

## 2. golden 慣例（楞伽 L1–4 實測；換系列先重測 §12）

| 慣例 | 實測 | 用法 |
|------|------|------|
| 鏈 | `golden.start == 前一個 READ 段的 end`（median 0.000） | `end[i]=start[next READ]`；zero 透明；末段=duration |
| 段首 lead-in | 落在首個逐字內容字前 0–4s（median −0.84），絕不晚於內容字 | 講首導言＝`t(ASR首字)−0.2s`（L40 回歸檢查） |
| 搜尋窗 | 證據只在 `[prev_end−0.3, next_start+0.3]` 找 | 越窗命中是鄰段回音 |
| 語速 | 朗讀 1–12 字/s；講解 1.3–5；<0.8 吞鄰段；>12 幻影（半讀除外） | 胖／瘦 span 都要重切；物理不可能＝時基壞 |
| zero 錨點 | 統一用 prev READ end（**鏈後的值**，L19 陷阱） | 值無功能影響但寫錯會破冪等 |
| 邊界精度 | golden ±0.5s；**系統性 +0.15s（落在前一字音節內）也是缺陷**（L32） | 毫秒級＝回到字 END/onset 原值 |
| conf | 證據強度非滿意度 | 不灌 conf |

## 3. 經文／偈語五種情況（判定順序由上而下）

先量實際念誦範圍 R（同音錯字當逐字看、語速自檢），然後按序判：

| 情況 | 判定 | 產出 |
|------|------|------|
| ①完全不念 | R 不存在 | `zero:true` 錨鏈位置，conf 0.8–0.95 |
| ②全念 | R ≈ 全段 | 實寬 `[run-onset(R首字), R末字END]`；即使下段重引也照給（優先於③） |
| ③半念＋下段開頭 verbatim 重複 ≥~80% R | R 只是頭一小截 | SUTRA `zero:true`；**講解段 start＝R 的 run-onset**（念誦由講解段攜帶） |
| ④半念＋無重複 | 只子片段／改述 | span 恰蓋 R：`[run-onset, R末字END]` |
| ⑤中斷插講／後方重引／逐句插講 | 同文多次 vocalization | 引文段與插講段各自成 span 按音訊順序切；細則見 §4.3 |

行內引文歸屬：短 vocalization 同時像獨立 SUTRA 頭又像後方 COMM 行內引文時——COMM 開頭
verbatim 含它 → 一律歸 COMM（③），**停頓非判準**；不含 → 歸 SUTRA（④）。
**通則**：每段 span 必須覆蓋它自己的 text 被說出的全部音訊；別人引用它的句子、或夾在它
中間的念誦，都不改變它自己的範圍；兩段互爭同一音訊按音訊順序切，不得吞鄰段文字。

## 4. 邊界裁決規則（**停頓轉場制**；2026-10 使用者 L21 全講 89 段人工確認後定稿＝現行 golden）

> 舊版以「前段末字 END」為通則——L21 r3 的 46 個提案被使用者**系統性提前
> （中位 −2.2s，42/46 段）**，經物理 silencedetect 逐樣本驗證後由使用者定案新通則：
> **下段首字前的最後一個停頓＝轉場點**。L1–L4 golden 之所以「末字 END 吻合」，
> 是因為那些邊界恰好都是接觸式。

**4.1 停頓轉場制（主規則）**，邊界依音檔結構分流：
1. **找下段首字** own_first（本段印字頭／首個內容詞的實際 vocalization；§5 走查定）。
2. 在 `[own_first−10s, own_first]` 找**最後一個** ≥0.3s 停頓（dump 字 END→下字 onset 間隙；
   掉字區用 silencedetect 物理驗證，L21-final 實證 dump 洞後字元可晚 0.5–1.7s）。
3. **有停頓 → 邊界＝停頓區內的轉場點**（運算取**停頌中點**；<0.5s 停頌取停頌末−0.1）。
   **停頓＋停頓後到 own_first 之間的所有話語——即使印字屬於前段——一律歸下段**：
   - 前段**收尾句**（L21-final：「都学好了，就可以了」→[73]、「（一百零六）页」→[62]、
     「好好学语|言」→[64]——前段 span 止於它與主體**連讀**的最後語句，可能很短）；
   - **下段主題的插講經文句**（「如衢巷中…」→解釋「衢巷」的 [70]＝插講句歸「解釋它的段落」）；
   - 引導語／重引（「（就是）为非色四…」→[71]、「（什么样的问题）不是正问呢」→[80]）。
4. **接觸邊界（無 ≥0.3s 停頓）→ 前段末字 END-time（毫秒原值）**：L21-final 使用者原值
   保留的 [39][55][59][63] 全屬此類。不是字首 onset（剪尾音）、不是「字首−0.15」。

**4.2 語氣詞／過場／打結**：接觸邊界下仍歸前段（呢/啊/嗯/哈/好、「下一段」「他下面说的」
——L40 r1 慣把過場當下段起點，錯）；停頓轉場制下它們落在停頓之後、自然歸下段。
講岔打結取**完整的那一遍**（L31 [67]）；第一遍本身完整則取第一遍，無論後方重念多逐字（L42 [64]）。
**插講型（⑤）**：經文段保留頭句朗讀起點；其餘句朗讀歸「解釋它的」講解段（＝4.1 第 3 條）；
span 只有 2 秒（L34 [66] 型）＝合格，不是缺陷。

**4.3 語序型**：音檔順序 ≠ 印字順序（先釋義後念標題、先講例後念經文）→ 錨**第一個實際
宣讀的本段內容**（L21 [40] 先釋義 740.95、印字標題在 746.30 晚 5.25s；L38 六段群、L39 [58]）。

**4.4 首次宣讀 vs 重引**：段頭同時存在兩者時——**SUTRA 段取首次宣讀**（L35 [6] −14.14s）、
**COMM 段取重引**（L33 [20]）；判別：看前段 end 之後、現值之前有沒有本段印字的逐字串。

**4.5 自晚型（L37）**：舊 start 落在**自己段的身體裡**（pre 視窗內容＝本段印字後半）→
立即沿時間軸向前開寬視窗找「本段印字開頭的逐字串」。

**4.6 整組對調（L25 型）**：相鄰 SUTRA/COMM 的 DTW 最佳命中互相落在對方身上 →
兩段一起重定。**相鄰兩段都改時，table 兩邊都要列**（漏一邊會留舊 end）。

**4.7 畸形 span（<1.5s 裝 20+ 字）是待查線索**：三個方向（下段太早 L23／下段被前移 L26／
下段被後移 L29）都會夾短本段；另一種是 ⑤ 半讀（首字有對上就合格）。**先看首字對不對，
沒對上才查相鄰段；每筆改動後回頭查前一段旗標；自己製造的問題同一輪修完（L29）。**

## 5. 主力工法：全講邊界走查（停頓轉場制實作）

**每一個邊界都要走**——未走查的段＝未判定（L31 [71] 偏 24.85s、L37 [39] 偏 32.86s、
L21 [81] 偏 29.05s，全都在 metric 窗外、全靠走查抓出）。

### 5.1 證據工具

**`boundary_walk.py`**（常設腳本；L21 r3 的 walk.py 正典化，講次參數化）：
```bash
# 段號模式：印每段現值、頭部 needle 候選（拼音+覆蓋率）、前段尾 needle 命中
V=tool/sense_voice/.venv/bin/python
$V audio_map3/skills/milli-align/scripts/boundary_walk.py --series lengqie --lecture 22 --lo 40 --hi 44
# 秒數模式：字級原始流（字@start-end，10 字/行）——lo/hi 是「秒」，整數
$V audio_map3/skills/milli-align/scripts/boundary_walk.py --series lengqie --lecture 22 --raw --lo 1230 --hi 1265
```
**精確 END 查詢**（邊界取值一律用這個，不用行內插值）：
```bash
$V - <<'PY'
import sys; sys.path.insert(0,'audio_map3/skills/milli-align/scripts')
sys.path.insert(0,'tool/jiangjing_para_map')
from seq_align import Stream, load_dump
from pathlib import Path
st = Stream(load_dump(Path('/tmp/funasr_cache/lengqie/22.json')))
for c,t in [('的',1372.57),('段',1598.79)]:   # (字, 該字的 onset 秒)
    for q in range(len(st.norm)):
        tt = st.t_of(q)
        if tt is not None and st.norm[q]==c and abs(tt-t)<0.14:
            print(f"{c}@{tt:.2f} end={st.t_end_of(q):.3f}"); break
PY
```

### 5.2 逐邊界判讀四步（對每個邊界 B＝[i].start 執行）

1. **前段尾**：找 [i-1] 印字末句在 dump 的逐字串 → 最後內容字的精確 END（含歸前段的
   語氣詞／過場）；
2. **本段頭**：找 [i] 的 **own_first**（第一個實際宣讀內容：印字頭逐字／重引／語序前置／
   插講句皆可能），取其 onset。
3. **停頓轉場裁決（§4.1）**：在 `[own_first−10s, own_first]` 找最後一個 ≥0.3s 停頓
   （dump 字 END→下字 onset 間隙；洞區或語氣可疑 → silencedetect 物理驗證）——
   **有 → 邊界＝停頌中點（停頓後的一切歸下段）；無 → 邊界＝前段末字 END**。
   語速（span 字數÷秒）／起訖單調自檢後定值。
4. **記錄**：note 必須含 own_first 字元時間、停頓起訖、所套規則編號（4.1-3／4.1-4／4.3…）。

### 5.3 工具提案只是線索

- `seq_align --mode metric` 搜尋窗只有 `[start−3, start+7]`：**偏離 >7s 的段在報表裡
  根本不會有那一行**（L32 六例、L21 r3 四例）。修正後覆蓋段會長出來（也可減少＝共用引文
  假象被消除，L39 (c)）——覆蓋差可當量化證據，但**覆蓋不等於判定**。
- `metric` 的 `t_first` 五種誤命中（動段前必駁）：上一段經文同一字（L30）、老師過場語
  「下面是一段偈语」（L34）、本段第二個同音字（L34/L36）、第二次重念（L35）、DTW j_first
  DEL（§8）。**殘餘離群要逐筆查，假象與真修混在同一份報表**（L41 (d)）；也要查自己剛寫的
  表有沒有筆誤（L42 [15]）。
- `span_audit` 量不到邊界品質（L13 全程 88.5% 不動而首字 65→80%）；兩者都要看。

## 6. 時基爭議與掉字區：物理錨裁決（L21 r3 新定稿）

**6.1 時基優先序**：主 dump 全域 `timestamp` ＞ 切片。但主 dump 也會在同音錯字密集區
整段掉字、尾段 nan——此時用物理工具仲裁，不是「多窗切片互相比對」（L26 的失敗方法）。

**6.2 silencedetect 物理停頓＝時基爭議的唯一仲裁者**（L21 r3 實證）：
主 dump 與切片時間戳衝突時，取實測停頓比對兩邊的字間隙——**字 END 對齊 silence_start、
下一字 onset 對齊 silence_end 的那個時基為真**；把音節放進真實靜音內的那個是壞時基
（L21：主 dump 字間隙 1329.86→1330.53、1331.92→1332.49 與實測靜音 1330.04–1330.52、
1331.95–1332.50 完全重合 → 切片在該區早 1.1s 判定為假）。
```bash
ffmpeg -hide_banner -ss START -t LEN -i <opus> -af silencedetect=noise=-38dB:d=0.30 -f null - 2>&1 | grep silence_
# 輸出的 offset 相對 -ss START，要加回絕對時間
```

**6.3 切片紀律**（`clip_probe.py --chars --times --vad-ms 10000`，~40s 窗）：
- **只信文字，不信時間戳**——文字直接告訴你「這幾秒念的是哪一段」（L30 61.7s 掉字區
  就這樣訂出內容順序）；
- 主 dump 同區找得到對應字 → **一律用主 dump 精確值**（L33/L39/L41 三驗）；
- 主 dump 全無字才用切片值：先多窗驗時基（任一窗失敗即棄用時間戳，L26），或做
  **頭尾雙向校正**（兩窗各以「接觸主 dump 端」校正，L42），conf ≤0.7；
- 切片 ASR「沒有輸出」≠「沒念」（VAD 靜默丟字；L16 mst 30000 只吐尾 10s）。

**6.4 volumedetect 分辨「真靜音」與「ASR 失效」**（判停頓前必量）：
`ffmpeg -ss X -t Y -i FILE -af volumedetect -f null -`（**不要加 `-v error`**）。
mean ≈ −60dB＝真靜音；−11dB 左右＝有聲（ASR 掉字）。

**6.5 尾部壞區協議**（dump 尾字全 nan、clip 也失位時；L21 [88]）：
1. 確認檔案真實長度（`ffprobe -show_entries format=duration`）與 JSON duration 一致；
2. silencedetect 掃尾 10s 找最後停頓；volumedetect 分段量「停頓是否真靜音」；
3. SRT 尾部 cue 的**文字**旁證最後一句內容（SRT 時間軸壓縮不可用，純文字可用）；
4. 停頓後的剩餘秒數 ÷ 收尾語速（5–6.5 字/s）反推「好了…」類收尾句 onset；
5. conf 0.5、note 記 ±0.3s、列 earcheck 人耳清單。

## 7. 缺陷型態速查

| 型態 | 特徵 | 處置 | 戰史 |
|------|------|------|------|
| 吞尾 | 下段 start 切進前段末字音節（系統性 +0.15s 也是） | 邊界移到前段末字 END | L8/L9/L24/L32 |
| 搶過場 | start 落在「下一段/下一句」上 | 過場歸前段 | L40 28 段 |
| 自晚 | start 落在自己段身體裡 | 向前開寬窗找印字開頭 | L37 [39][69]、L21 [81][82] |
| 整組對調 | 相鄰兩段 DTW 命中互換 | 兩段一起重定 | L25 [103]、L38 [76][77] |
| 假 zero | 字級流掉字、音檔有聲 | 切片複驗文字 | L14/L15/L20/L41 [77] |
| COMM 被壓零寬 | 講解段 zero | 重錨真位置 | L4/L10/L11/L38 [75] |
| confirmed zero 擋路 | 前移會破單調 | 不修＋逐字證明＋列人耳 | L23/L28/L30/L36 |
| r1 假 zero→READ | 起點＝前段 end 鏈值，非首字 onset | 逐段回正首字 | L32/L37/L40 |
| 講岔打結 | 同句兩遍 | 取完整遍 | L31/L38/L39/L42 |
| 語序型 | 音檔順序≠印字 | 錨首個實際宣讀 | L21 [40]、L37 [45]、L38 |

## 8. 工具與陷阱

- **長音檔 `sentence_info`／SRT 時間是壓縮的（線性 +6.6%）**，全域 `timestamp` 才對；
  SRT 的**文字**可作內容旁證（尾部壞區用），時間不可用。
- **切片 ASR 靜默丟字**：VAD `max_single_segment_time` 太大只吐尾部 ~10s（L16）；
  `clip_probe.py` 預設 `--vad-ms 10000`；「沒有輸出」≠「沒念」。
- **char 時間層會局部掉字**並把後續字元時移 1–3s（L10 [37]、L21 掉字區）→ §6 物理錨仲裁。
- **行內插值不可取值**（L16 兩事故）：插值只定位「要看哪段」，取值一律精確字元 END/onset。
- **`milli_refine` 正典在 `scripts/`**：READ 身分＝「有無實寬 span（`end != start`）」且必須
  **變更前**記錄（L18 bug）；`zero` 標記＋實寬的 inconsistent 記錄以實寬為準（L22 r2 bug）；
  鏈 pass 後負長度／破口 abort 不寫檔；**dry-run 顯示的是鏈前狀態**，鏈／單調驗收在
  `--apply` 後做（L33）；zero 的 start 寫「鏈後的值」否則破冪等（L19）。
- **`dump_window.py` glob 陷阱**（`*{N}.json` 把 15 排在 5 前）：直接餵
  `/tmp/funasr_cache/<series>/<N>.json` 給 `load_dump`。
- **`FILLER_RE` 只列單字語氣詞**：lead-in 走「停頓」不走「詞性」。
- **批次輸出中段截斷**：落地檔 ≤40 行分次讀（L32 誤判過「無證據」）。
- **`batch_verify` 嫌疑筆數是領先指標**：嫌疑多或 |z|>±7s → 直接進全講走查，不逐段探測。

## 9. ASR 同音錯字對照（楞伽累積；全庫唯一副本）

> 文言經文的同音／近音錯讀。同音錯字當逐字看，對照段落全文找最長連續匹配。
> 英文字母人名：時間合併在第一個字母，取該字母 onset。

| 正字 | ASR 常誤為 | 正字 | ASR 常誤為 |
|------|-----------|------|-----------|
| 梵釋四天 | 凡诗四天 | 大观行师 | 大观行诗 |
| 遍一切处 | 便于制作 | 证真实 | 保证真实 |
| 远离二乘三昧过失 | 等于二乘三位过失 | 毛轮住非净智境 | 茅伦助飞静 |
| 超诸应化所应作事 | 操作硬化所做所应做事 | 我今愿得重见如来大神通力 | 古今炼的充电如来大神动力 |
| 时虚空中 | 持续控制中／自悉檀 | 修習 | 休(息) |
| 楞伽王 | 任亲王／矿(楞伽王) | 况法与非法 | 旷法理非凡／局外 |
| 楞伽经 | 用结经／梦结晶／文基经 | 大慧 | 大会／博言(佛言) |
| 尔时 | 而是时／凡是大慧／而是(真) | 瓶等诸物 | 平等诸务 |
| 自共相 | 自贡向／自向共享 | 若相续／若蕴 | 弱相信／我运(蕴) |
| 复有沙门 | 富复有三门 | 悉檀 | 诗塘／自西谈 |
| 戏论习气 | 细润吸气 | 识虚妄 | 市希网 |
| 是名相灭 | 是民项命 | 彼诸外道 | 比之外导 |
| 相续 | 相序／聚 | 三乘句 | 三层句 |
| 標相句 | 飘像剧／雕像剧 | 演说句 | 演说剧 |
| 名相灭 | 民项命 | 自性 | 自信 |
| 阿赖耶识 | 阿拉利／阿拉耶序 | 世间恒如梦 | 世间红楼(梦) |
| 断见常见 | 断剑常剑 | 承佛神力 | 成佛神力 |
| 说颂言 | 说顺言 | 摩帝菩萨 | 摩地菩萨 |
| 是故大慧 | 事会／下在 | 但住心量 | 赞助心量 |
| 观察三有无始时来 | 山有三有五尺以来 | 生死涅槃二种平等 | 三十年前暗动平凡 |
| 住灭法 | 猪病房 | 力通自在 | 绿通自在 |
| 阿罗汉 | 二百万 | 俱时而起无差别相各了自境 | 聚势而起无差别向过流之尽 |
| 众生识所现 | 众城学所县 | 圣智 | 自动／圣只 |
| 习气种 | 其气准 | 幻境 | 望境 |
| 以习力 | 以席例 | 不觉／是念／我灭／三昧 | 不决／是内／我便／三味 |
| 不取诸／以彼／五法 | 不辨始／以里／无(五)法 | 诸修行者／微 | 中(诸)书／锲 |

**L21 r3 補充（名句文身章實測）**：复次→这次／副词｜名身者→民生的／铃声的｜句身者→
俱身者｜文身者→纹身者／为成长(长短)高下｜汝应修学→五音书写｜此名句文身相→此名字纹身
上｜非色四蕴→黑色四运｜未来世中→未来势中｜邪智→协助｜愚夫→一副／逾期发复(愚痴凡夫)｜
涅槃诸行→和工程色／涅槃足形｜相所相→项所向一｜造所造→照所照｜地与微尘→至于微臣｜
究竟→究竟(詞中可被 2s 停頓切開)｜衢巷→趋向｜计著→记住｜颂言→从善顺言。

## 10. 作業流程

**10.1 備齊輸入**：`ls /tmp/funasr_cache/<series>/`（缺先跑
`funasr_dump.py --series <s> --lecture <N>`，單講 60–70s CPU）；全部用
`tool/sense_voice/.venv/bin/python`。

**10.2 盤點**：`git ls-files reports/ | grep <series>_L<N>`（rN 紀律，§1.7）；
從 JSON 列出 confirmed／reviewed／zero 段清單（不可動的邊界先標出來——
confirmed zero 會釘死相鄰邊界）。

**10.3 掃描定優先序**：掉字空窗（≥3s gap 清單）→ 決定哪些區要 clip；畸形 span 清單
（§4.8）→ 這些邊界優先走。

**10.4 全講邊界走查**：對每個未 confirmed 的 READ 段執行 §5.2 四步；邊界值取精確 END。
走查以「段號批次」進行（boundary_walk --lo/--hi，每批 3–6 段），疑難處切 --raw 秒數窗。

**10.5 寫 rN 表**：`{i, start, conf, method, note}`（note＝逐字證據＋舊值差）；
相鄰兩段都改務必兩邊都列；zero 段 start 寫鏈後值。

**10.6 套用**：`milli_refine.py --series <S> --lecture <N> --table <rN.json>` 先 dry-run
（只看筆數與 start，不看鏈）→ `--apply`。

**10.7 驗收組合**（§11）→ earcheck（`reports/<series>_L<N>_earcheck_rN.md`）＋
人耳清單 → `verify-artifact.py`。

## 11. 驗收組合（每次套用後必跑，全綠才算完）

```bash
V=tool/sense_voice/.venv/bin/python
$V audio_map3/skills/milli-align/scripts/seq_align.py --series <S> --lecture <N> --mode metric --json /tmp/m.json
$V tool/jiangjing_para_map/span_audit.py --series <S>
$V tool/jiangjing_para_map/pin_check.py <S>
```
1. 鏈完整（末 READ end=duration、負長度 0、破口數不新增）＋ start 單調（與修正前比較，
   既有違反要說明處置）；
2. 非目標講次 **byte-identical（全部，不只抽驗）**＋ confirmed 零變動＋ reviewed 未動；
3. `--apply` 第 2、3 次＝0 段變更（冪等）；
4. metric 覆蓋差（量化窗外錯位修正）＋ 殘餘 |d|>0.7 逐筆裁定（§5.3 五種假象）；
5. 每 start 距最近 ASR 字元 ≤0.3s（lead-in 例外逐一裁決）；
6. 弱證據段落如實列 earcheck 人耳清單（conf ≤0.6 務必試聽）。

## 12. 換新系列

1. `golden_offsets.py --series <X> --golden 1-4` 重測 §2 慣例；
2. 找講首結構慣例（整章印刷塊 vs 導言 vs 重複引文各系列不同）；
3. 照 §10 走；SRT 重生成只在 dump 品質不足時用。

## 13. 完成定義

- [ ] 每個未 confirmed 邊界都走過 §5.2 四步，值取精確字元 END/onset（毫秒原值）
- [ ] 首 6 筆：鏈／單調／byte-identical／冪等／覆蓋差／殘餘裁定 全數記錄
- [ ] 掉字區＝clip 文字定歸屬＋主 dump/物理錨取值；尾部壞區按 §6.5 協議
- [ ] zero 段逐字驗證通過；③ 的講解段 start 釘在 R run-onset
- [ ] 人耳清單已寫 earcheck；agent 未代勾任何 confirmed／reviewed
