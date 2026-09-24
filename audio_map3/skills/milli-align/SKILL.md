---
name: milli-align
description: >-
  講經系列「段落 ↔ 音檔」毫秒級精準對齊 skill。以人工 golden 講次（楞伽經 L1–6）為範本，
  用 FunASR 字級 dump 對每段做逐字／拼音夾逼證據對齊，處理經文／偈語各種念誦情況（全念＝非零
  實寬、不念＝zero、半念＋下段重複＝zero 且講解段攜帶念誦(2.a)、半念無重複＝span 恰蓋實念那截
  (2.b)、中斷插講、後方重引），讓段首第一字毫秒級對齊實際念出的第一字，並誠實標記信心與人工
  試聽清單。適用 audio_map3/<series>.json 全系列。
---

# 毫秒級段落對齊（milli-align）

把 `<series>.json` 對齊到「每段開頭第一個字 ＝ 音頻實際念出的第一個字」。
輸入：`audio_map3/<series>.json`、`/tmp/funasr_cache/<series>/<N>.json`（字級 dump，毫秒源）、
`ebook/<K>.html`（SUTRA/COMM 分類）。產線、資料模型、注入、已知限制見
[`../../AGENTS.md`](../../AGENTS.md)。

量測腳本（`scripts/`）：`golden_offsets.py`（golden 慣例）、`milli_audit.py`（證據稽核）、
`milli_refine.py`（套用，正典在此勿在 /tmp 重建）、`zero_audit.py`／`zero_probe.py`、`clip_probe.py`、
`batch_verify.py`、`win.py`、`series_cls.py`。

## 0. 什麼時候用

某講次要對到毫秒級／把 golden 慣例推廣到其他講次／`span_audit`、`pin_check` 報大量 span_bad
或播放起點明顯不對時。

## 1. 鐵律

1. **golden 不可侵犯**：`reviewed`／`confirmed` 段重跑前後 `start/end/conf/confirmed/zero` 必須
   byte-level 不變（寫檔前後都驗）。
2. **證據先於位置**：每個位置要有證據（逐字 hit、拼音 DTW、run-onset、鏈）。沒證據就用夾逼區間
   ＋誠實低 conf，不硬猜不灌 conf。
3. **conf 誠實階梯**：verbatim ≥0.9／近逐字 0.85／拼音 0.7–0.8／弱拼音 0.6（列人工）／夾逼插值
   ≤0.75／不念證據 0.8–0.95。人耳（UI confirmed）是最終裁判。
4. **只動目標講次**的 start/end/conf/method/zero，`confirmed` 鍵一律不碰。
5. **「head OK ≠ 邊界對」**：段首單向驗證抓不到吞尾，每個邊界要**雙向**驗（見 §4.1）。
6. **驗證宣稱不可繼承**：每輪 adjudication 後都要對**全部 READ 段首**重掃。

## 2. golden 慣例（楞伽 L1–4 實測；換系列先重測 §8）

| 慣例 | 實測 | 用法 |
|------|------|------|
| 鏈 | `golden.start == 前一個 READ 段的 end`（median **0.000**；299 對僅 <5% 刻意留白） | `end[i]=start[next READ]`；zero 段透明；末段=duration |
| 段首 lead-in | 落在第一個逐字內容字**之前** 0–4s（median −0.84），**絕不晚於內容字**（max 0.00） | start＝run-onset（內容字往回 ≤0.7s 停頓／語氣詞，且 ≥prev_end）；**不是** `t(內容字)−0.15` |
| 講首導言 | `intro.start = t(ASR 首字) − 0.2s`（L1–4：−0.35/−0.25/−0.20/−0.20） | 講首第一個 COMM 段 |
| 搜尋窗 | 證據只在 `[prev_end−0.3, next_start+0.3]` 找 | 越窗模糊命中是鄰段回音（無窗約束時偏早 median −1.9s） |
| 語速 | 朗讀 1–12 字/s；<0.8 胖 span 吞鄰段；>12 是幻影 | 胖／瘦 span 都要重切 |
| zero 錨點 | 統一用 prev READ end（鏈位置） | 值不影響注入（`zero` 被跳過） |
| 邊界精度 | golden 實測 ±0.5s（僅 22% 精確落字尾） | **\|Δ\|≥0.7s 必修；0.3–0.7s 須有切片／目視證據才修** |
| conf | 證據強度，非人工滿意度（golden L4 有 6 段 conf≤0.6 但 confirmed） | 不灌 conf |

## 3. 經文／偈語五種情況（**判定順序由上而下**）

**第一步：量出實際念誦範圍 R**（字級 dump 逐字對照，同音錯字當逐字看）＝該段開頭實際被念出的
最長連續字串（用語速 1–12 字/s 自檢）。然後按序判：

| 情況 | 判定 | 產出 |
|------|------|------|
| **①完全不念** | R 不存在（逐字／近逐字在講內 ASR 找不到、無局部 clean 命中） | `zero:true`，起訖＝鏈位置，conf 0.8–0.95 |
| **②全念（rule 1）** | R ≈ 全段（≥~90% 字數，語速自洽） | **不可為零**。span＝`[run-onset(R首字), R末字 end-time]`；即使下段重複引文也照給實寬（L6 [49]/[158]，優先於 2.a） |
| **③半念＋下段開頭重複（2.a）** | R 只是段頭一小截（≤~10 字），且下一講解段開頭 verbatim 重複 **≥~80% 的 R** | **`zero:true`**（錨在鏈位置）；**講解段 start＝R 的 run-onset**（念誦音頻由講解段攜帶）。L5 [27]/[56]、L6 [34]/[52]/[79]/[81]、L2 [79]/[81]/[83] |
| **④半念＋下段無重複（2.b）** | R 只是段頭一小截，下段開頭**沒有** verbatim 重複（直接講解／只子片段／改述） | span＝`[run-onset(R首字), R末字 end-time]`，**恰停在念誦結束處**；講解段緊接其後。L5 [18]/[22]/[50]、L6 [24]、L2 [52]/[77] |
| **⑤中斷插講／後方重引** | 長 passage 朗讀中途插白話（講完續念）；同文兩次 vocalization | 引文段與插講段各自成 span，按**音訊順序**切；後段拿第二次 vocalization。變體見 §4.6 |

**邊界慣例（②④）**：READ end＝R 末字 end-time（毫秒）；下一講解段 start＝同一邊界（停頓 ≤~2s
歸講解段 lead-in；≥2s 純靜音才留白不鏈，L6 [9]）。**③的講解段 start**＝R 的 run-onset（內容字
往回 ≤0.7s）。判 ③④以**音頻實際念誦**為準，別被印刷文字騙（L5 [20] 音頻只念頭 8 字、[21] 開頭
重引 → ③）。

**②全念後的同氣流重引**：SUTRA 全念後師父常在同一口氣重引末句片段再接講解——下一段 COMM
開頭 verbatim 含該重引時，**重引歸該 COMM 的 start**，SUTRA 保有 rule 1 實寬、不 zero（②優先；
L7 [30]→[31]／[35]→[36]／[87]尾→[88]／[92]→[93]）。拆分念誦（⑤短距版）同理：SUTRA 拿頭部
span，**尾段念誦留在下一 COMM 的 span 內**（L7 [67]/[74]）。

**行內引文歸屬（③特例）**：短 vocalization 同時像「獨立 SUTRA 段頭」與「後方 COMM 行內引文」時
——**COMM 開頭 verbatim 含它 → 一律歸 COMM**（③，SUTRA 記 zero），**即使前面有 ≥0.6s 停頓**
（L6 [34]：0.95s 停頓仍被人工翻成 zero）；COMM 開頭不含（只子片段／改述）→ 歸 SUTRA（④）。
**停頓非判準，以 COMM 是否 verbatim 重引為主。**

**通則（L10 r4 定稿）**：**每段 span 必須覆蓋「它自己的 text 被說出的全部音訊」**；別人引用它的
句子、或夾在它中間的念誦，都不改變它自己的範圍。兩段互爭同一音訊時按**音訊順序**切，且不得讓
任何段吞掉鄰段文字。

## 4. 結構錯誤型態速查

1. **吞尾（最常見最隱蔽）**：前段尾巴整句被下段 `start` 吞掉，段首單向驗證抓不到。**邊界雙向
   驗**：下段 head needle 命中在邊界後之外，**前段末句 needle 也須命中在邊界前且緊鄰**；邊界值
   ＝前段末字的 **END-time**（不是字首 onset，字首會剪尾音）。L8 r4 66/67（最大 11.6s）、
   L9 r2 83 段、L12 [38]/[68]/[71]/[91]。
2. **胖／瘦 span（rate 鐵證）**：胖（<0.8 字/s）吞鄰段（L4 [41] 103.6s→40.1s；L37 [52] 332s、
   L41 [21] 242s——**全系列不得有 >120s 的 READ span**）；瘦（>12 字/s）念誦尾被下段吞（L12 [68]
   26.2、[71] 16.9；L13 [109] 13.3）。半念段 rate 以**全文**算會虛高（假警報），要以 vocalized
   字數看（L7 [87] 清單 710 字只念 ~110 → 實際 3.1 字/s，非 17.5）。
3. **COMM 永不 zero**：講解段被壓零寬是缺陷，重錨在真位置（L4 [19]/[43]；L10 [120]；L11 [76]）。
4. **假 zero（ASR 掉字）**：字級流在「同音錯字密集區」會大段掉字且音檔連續有聲（`silencedetect` 無
   ≥0.6s 靜音）——**不可因字級稀疏判 zero**。**判 zero 前必抽 40s 切片重跑 ASR**（40s 可靠；
   <30s 常失敗）。L14 抓到 5 假 zero、L15 抓到 8（投報率最高的一步）。
5. **③ vs ④（最常錯）**：③＝下段開頭重複 **≥~80% 的 R**；④＝只重複子片段／改述。**必須算 R 的
   覆蓋率**，別看到引號就當③（L15 [31] 只引 9/46 字、[90] 只引 5/30 字 → ④）。②優先於 2.a。
6. **⑤ 交錯／書序≠語序變體**：(a) 講首長 passage 書序≠語序（L5 [3]–[13]：全 passage 塊＝zero，
   朗讀由書序在後的 [14]/[16] 認領；[15] 是中斷插講）；(b) 講解先唸、經文 R 才插入 → 經文段維持
   zero；(c) COMM 零寬但講解確實存在 → 真缺陷改 READ；(d) **念誦夾在同一它段的兩截註解中間** →
   念誦段 zero、音頻由夾住它的 COMM 攜帶（L10 [44]/[45]）；鏡像＝**註解打斷誦文** → 誦文段 span
   止於打斷點（L10 [118]/[119]）。講首三段（四十二章 L2 鐵律）：整章經文塊 → 導言白話段 → 經文
   重複段；正確＝i0 零寬、i1 導言 real span、i2 逐字念的經文 real span（`realign_dtw` 會把 i0
   誤判成有念而吞掉 i1；受害 L10/L12/L13/L14）。
7. **zero 段 `confirmed:true` 是 UI 自動寫入的**（零長度即視為已確認，AGENTS §0a），**不是人耳
   golden**；要改這類段先移除自動 confirmed，別被 milli_refine 護欄卡住（L11 [76]/[93]/[55]）。
   **confirmed zero 釘死相鄰邊界**（鏈必須穿過 zero），理想值只記 earcheck。
8. **`milli_audit` 已知假陽性（別追）**：(a) `early`——verbatim 抓到後段回音；(b) `impossible rate`
   ——④半念 span 用全段字數算虛高（L13 [36] 12.2、[53] 13.4），只豁免 ≤3.5s；自行補跑「rate>10」
   全段掃描，別只信 SUTRA；(c) `span_bad` ≠ 位置錯（半念短經文段、⑤交錯、ASR 掉字都會報）。
9. **判 start 前先看上一段 R 末字的字級 end**（吞頭型）；段界緊接（≤0.7s）的語氣詞（啊／嗯／了／
   嘛／吧）收前段。

## 5. 工具與陷阱

- **⚠ 長音檔 `sentence_info`／SRT 時間是壓縮的，全域 `timestamp` 才是對的**：L11–L14 實測線性
  +6.6%（t=500s +35s、1500s +100s、2008s +127s）。`tool/sense_voice` SRT 與 `funasr_dump.py` 的
  `sentence_info` 同源受影響；`realign_dtw` 用的全域 `timestamp` 正確。**驗證新講次前先用 40s
  切片對一個已知點「對錶」。**
- **⚠ 切片 ASR 靜默丟字**：`vad_kwargs={"max_single_segment_time":30000}` 跑 40s 切片時，若被
  VAD 判成單一長段，paraformer **只吐尾部 ~10s、其餘靜默丟棄**（`silencedetect`／RMS 證明有聲）。
  L16 [29]：mst 30000→48 字、15000→133、10000→213、5000→225。**切片 ASR「沒有輸出」≠「沒念」**；
  `clip_probe.py` 預設 `--vad-ms 10000`。
- **char 時間層會局部掉字**：整區掉字並把後續字元時移 1–3s（L10 [37] 掉 ~10 字→後移 2.5s；
  L10 尾區 1919.5–1940 全掉）。**仲裁**：`ffmpeg -i x.opus -af silencedetect=noise=-32dB:d=2.0` 取
  真靜音與 char 層缺口比對；有疑慮的邊界用 VAD 切片重聽（切片法時基須先驗：切含已知靜音區間，
  量到的 `silence_start` 須等於「全檔值 − T」）。
- `dump_window.py` 的 glob（`*{N}.json`）會把 `15.json` 排在 `5.json` 前——直接餵
  `/tmp/funasr_cache/<series>/<N>.json` 給 `load_dump`。
- `FILLER_RE` 只列單字語氣詞；lead-in 實詞（那么／我们看／后边呢）不在其中——**run-onset 走
  「停頓」而非「詞性」**。`norm_para()` 會 t2s＋去標點＋去語氣詞。
- **`milli_refine.py` 正典在 `scripts/`**——別在 /tmp 重建（L8 版因 /tmp 清空遺失）。保護＝
  「table 不得觸及 confirmed 段＋寫檔後 confirmed byte-identical 斷言」。
- 段首批量驗證：needle 6 字同音、score≥0.55、通過線 `d∈[−0.35,+2.0]`（向前窗
  `[start−0.6,start+3.0]`）；防 sliding window 越界（`n=min(6,len(needle),len(win))`）。**寧可
  NO-CONFIRM，不可放寬到誤通過**；改述式段首（「如果這樣看」→「不过这样看」）是最大盲區。

## 6. ASR 同音錯字對照（楞伽 L5–L15 累積；全庫唯一副本）

> 文言經文的同音／近音錯讀。用法：同音錯字當逐字看，對照段落全文找最長連續匹配。
> 英文字母人名：paraformer 把整串字母時間合併在第一個字母，取該字母 onset。

| 正字 | ASR 常誤為 | 正字 | ASR 常誤為 |
|------|-----------|------|-----------|
| 梵釋四天 | 凡诗四天 | 大观行师 | 大观行诗 |
| 遍一切处 | 便于制作 | 证真实 | 保证真实 |
| 远离二乘三昧过失 | 等于二乘三位过失 | 毛轮住非净智境 | 茅伦助飞静 |
| 超诸应化所应作事 | 操作硬化所做所应做事 | 我今愿得重见如来大神通力 | 古今炼的充电如来大神动力 |
| 时虚空中 | 持续控制中／自悉檀 | 修習 | 休(息) |
| 楞伽王 | 任亲王／矿(楞伽王) | 况法与非法 | 旷法理非凡／局外 |
| 楞伽经 | 用结经／梦结晶／文基经 | 大慧 | 大会／博言(佛言) |
| 尔时 | 而是时／凡是大慧 | 瓶等诸物 | 平等诸务 |
| 自共相 | 自贡向／自向共享 | 若相续／若蕴 | 弱相信／我运(蕴) |
| 复有沙门 | 富复有三门 | 悉檀 | 诗塘／自西谈 |
| 戏论习气 | 细润吸气 | 识虚妄 | 市希网 |
| 是名相灭 | 是民项命 | 彼诸外道 | 比之外导 |
| 相续 | 相序／聚 | 三乘句 | 三层句 |
| 摽相句 | 飘像剧／雕像剧 | 演说句 | 演说剧 |
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

## 7. 作業流程

**7.1 備齊輸入**：`ls /tmp/funasr_cache/<series>/`（缺先跑 `funasr_dump.py --series <s>`）；統一用
`tool/sense_voice/.venv/bin/python`。

**7.2 證據稽核**：
```bash
tool/sense_voice/.venv/bin/python audio_map3/skills/milli-align/scripts/milli_audit.py --series lengqie --lecture 5
```
逐段檢查頭部逐字／拼音命中（窗內）、語速、zero 逐字不念驗證、鏈完整性、COMM 零寬。
**自報 conf 不可信，以此稽核為準。**

**7.3 逐段判讀**（defect 才需要）：開 ASR 視窗聽「字」（`scripts/win.py` 或）：
```bash
tool/sense_voice/.venv/bin/python - <<'PY'
import sys; sys.path.insert(0,'tool/jiangjing_para_map')
from realign_dtw import load_dump, _t_of
from pathlib import Path
d = load_dump(Path('/tmp/funasr_cache/lengqie/5.json'))
buf=[(t,c) for k,c in enumerate(d['chars']) if (t:=_t_of(d['times'],k))==t and 690<=t<=700]
for i in range(0,len(buf),14):
    ch=buf[i:i+14]; print(f"[{ch[0][0]:8.2f}] {''.join(c for _,c in ch)}")
PY
```
同音錯字當逐字看；對照全文找最長連續匹配；用 §3 決定 span；邊界用鏈＋run-onset。

**7.4 套用修正**：寫 adjudication table（`{i, start, end, conf, method, zero, note}`，範例
`tool/jiangjing_para_map/reports/lengqie_L5_adjudication.json`）：
```bash
tool/sense_voice/.venv/bin/python audio_map3/skills/milli-align/scripts/milli_refine.py \
  --series lengqie --lecture 5 --table tool/jiangjing_para_map/reports/lengqie_L5_adjudication.json --apply
```
（缺的段落用鏈＋現值不動；`--dry-run` 只印差異。）**confirmed zero 釘死相鄰邊界**。印刷行（C 標籤、
無引號）被分段引用時該行改 **zero**、片段歸引述段（L9 [82]）。

**7.5 回頭檢驗**：重跑 §7.2，直到①全段 conf ≥0.8（天生弱者列人工清單）②鏈完整
（`end[i]=start[next READ]`、末段=duration、zero 起訖相等錨在鏈上）③zero 段全通過逐字不念驗證
④段首重掃 LATE=0、**邊界雙向抽驗**無吞尾。

**7.6 驗收寫檔**：
```bash
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/span_audit.py --series lengqie
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/pin_check.py lengqie
```
（`milli_refine --apply` 內建 golden／旗標校驗，失敗即 abort 不寫檔。）交付：更新的
`audio_map3/<series>.json`＋人工試聽清單（`reports/`）。要跟播生效時由使用者在 UI 勾「本講校對
完成」（reviewed）——**agent 不代勾**。

## 8. 換新系列

1. `scripts/golden_offsets.py --series <X> --golden 1-4` 重測 golden 慣例（與 §2 差很多以新實測為準）。
2. 找該系列講首結構慣例（整章印刷塊 vs 導言 vs 重複引文排法各系列不同，見 §4.6）。
3. 照 §7 走。SRT 重生成（`gen_srt.py`）只在 dump 品質不足時用——dump 已是毫秒源。

## 9. 完成定義

- [ ] 每段 conf 由證據支撐、start 落在「實際念出第一字」的 run-onset（永不晚於內容字）
- [ ] 每個 SUTRA 段量過 R 並按 §3 判型（全念＝實寬；半念→2.a zero＋講解段攜帶／2.b span 恰蓋 R；不念＝zero）
- [ ] zero 段逐字驗證通過；2.a 的講解段 start 釘在引文 run-onset
- [ ] 鏈完整（停頓 ≤2s 歸下段 lead-in；末段=duration）；講首三段結構符合慣例
- [ ] golden byte-level 不變、confirmed/reviewed 旗標不變
- [ ] 段首重掃 LATE=0、邊界雙向抽驗無吞尾；span_audit 無「真」span_bad
- [ ] 人工試聽清單已寫入 `reports/`，弱證據段落如實標記

## 10. 逐講驗收（楞伽 L5–L42；span_audit 口徑）

L5 124 段（ok90/skip13/unk20/bad1）、L6 91.7%、L7 94.7%、L8 **100%**（r4 重掃 66/67、吞尾
11.6s）、L9 88%、L10 91.1%、L11 92.4%、L12 86.3%、L13 88.5%、L14 81.1%（假 zero 5）、
L15 78.4%（推翻 8 假 zero）；L16–L42 批次 526 筆修正、鏈破口 0、>120s span 0。
bad+unknown 多為 ASR 天花板／假警報，逐一查明後列人工清單。各講 earcheck 與 adjudication table
在 `tool/jiangjing_para_map/reports/`。
