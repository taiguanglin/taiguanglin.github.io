---
name: liuzutanjing-milli-align
description: >-
  《六祖壇經》專用「段落↔音檔」毫秒級對齊 skill。依 L2–L5 全人工 confirmed golden
  校准：先判內容轉場再選實體停頓，禁止疑難一律退 contact 或最近停頓吸附；
  own_first 對應本段語義開頭，有實念短經文一律 READ，不因下段重引而 zero。
---

# 六祖壇經專用毫秒級段落對齊

本 skill **優先於** `audio_map3/skills/milli-align/SKILL.md` 的通用寬鬆規則。通用工具仍可使用，但 own_first、zero、短收尾與人工 golden 的解釋以本檔為準。L2／L3 差異實證見 [`GOLDEN_ANALYSIS.md`](GOLDEN_ANALYSIS.md)；**L4／L5 新人工回歸與舊 contact 失敗量化**見 [`GOLDEN_L4_L5_ANALYSIS.md`](GOLDEN_L4_L5_ANALYSIS.md)。

## 1. 權威與不可侵犯事項

1. **先 pull／確認最新人工版**。golden 基準：L2 80/80、L3 89/89（commit `8872eda`）、L4 113/113（`9261ecd`）、L5 102/102（`c6eac18`）皆 confirmed；L2–L4 `reviewed=true`，L5 雖講層 `reviewed=false`，段級人工值仍全部不可改。若之後有更新，以新版為準。
2. `reviewed` 或 `confirmed` 的講次／段落，其 `start/end/conf/confirmed/zero/reviewed` 全部不可改；agent 永不代勾。
3. 只動目標講次；其他講次套用前後 canonical JSON **byte-identical**。pid、段落文字、音檔、duration 不改。
4. 不以 `method=ngram` 推斷演算法：人工 UI 存回會改成 ngram。看字級證據、start/end 與人工旗標。
5. 先快照 SoT 再施工；不得對整個 `liuzutanjing.json` 下 `git checkout`。本地 WIP 用 stash／`/tmp` 保存，pull 後不得把舊草案覆蓋人工版。
6. **鏈是草案預設，不是改寫人工值的理由**：新草案以 READ `end[i]=start[next READ]`、末 READ end=duration、start 單調、無負長度為目標；但 L5 人工 [69].end 比下一 READ start 晚 2.339s，[70] 又是未標 `zero` 的零寬段。此類交疊／零寬只能憑音訊另記例外，絕不可為了讓鏈轉綠而改 golden 或吞段。

## 2. 輸入與工具

- SoT：`audio_map3/liuzutanjing.json`；電子書：`ebook/09.html`。
- 字級毫秒源：`/tmp/funasr_cache/liuzutanjing/<N>.json`。缺失時以 `tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/funasr_dump.py --series liuzutanjing --lecture <N>` 重建。
- 通用證據器：`audio_map3/skills/milli-align/scripts/` 的 `boundary_walk.py`、`seq_align.py`、`milli_refine.py`、`milli_audit.py`、`batch_verify.py`、`clip_probe.py`。
- 專用保護稽核：`scripts/audit_alignment.py --baseline <施工前快照> --lectures <N或範圍>`；最後加 `--require-clean` 驗目標講次。音訊交疊例外在 table 用 `preserve_end:true`＋明示 end＋note，不能借它隱藏未解決鏈破口。
- 停頓：先 `volumedetect` 量底噪；本系列常用 **−28dB/0.20–0.30s strict** 與 **−22dB/0.20s soft**，高底噪檔不可只用 −38dB。V4 以 gap 與實體停頓 **重疊≥0.10s** 判讀。
- `span_audit` 的舊 regex 對巢狀 `.sutra-pin-host` 會漏段；須以 HTMLParser 適配器收齊全部 `.para-block`，不可把 63/80 之類漏讀當 pid 漂移。

## 3. own_first：先語義、後時間

### 3.1 必要條件

own_first 是「**本段語義開頭，在音檔中的第一次實際宣讀**」。必須同時有：
1. 本段印字開頭的 6–12 字上下文（文言同音錯字可用拼音，note 要標）；若取未逐字印出的解說引子，必須另證明前段印字已結束、引子已進入本段語義（L4[61]），不得只靠時間近；
2. 字級 onset／END 或實體停頓證據；
3. 與前段尾、下一段開頭不相混的雙向判讀。SUTRA 首次宣讀前的敘述轉場與 COMM 後方重述要分開（L5[18][52]）。

### 3.2 不得當 own_first 的材料

- 前段 SUTRA 殘頭、後半插引、前段白話收尾；
- 未印出的「這個／那麼／還有／我們／然後」等過場；
- 同字或同音在前段、第二遍重引、DTW j_first DEL 假命中；
- 僅因離舊 start 最近而選出的 ASR 字。

實證：L2[20] 不取「這個」而取印字「時」；L2[54] 不取前段「喂」而取「這是」；L3[47] 不取前段「房」而取「一宿」；L3[50] 不取前段「天明」而取「等天亮」。

### 3.3 SUTRA 與 COMM 分則

- **SUTRA**：取本段位置上的首次獨立宣讀；後面 COMM 重引不是它的起點。
- **COMM**：取本段白話開頭。若 COMM 印字本身以引文開始，可取該重引；若印字先講解，不得拿前段經文重引當 COMM 開頭。
- **語序前置**：只有確屬本段印字內容的提前講解才可提前；不能借語序之名吞前段。
- **插講**：依音訊順序切。若白話已先開始，後到的經文可由白話段攜帶，不可製造 start 倒序或負 span。

## 4. zero／READ：有 R 就 READ

1. 先量本段位置上的實際 vocalization R。**R 存在就 READ**，即使只有數字、短偈、殘頭，或下段會重念。
2. R 不存在才 `zero:true`；後段重引不溯歸本段，也不反過來抹掉本段已有的 R。
3. zero→READ 必須明確 `zero:false`，並用鏈推 end；只改 start 不算恢復。
4. zero 錨＝鏈後前個 READ end；head-zero（首個 READ 之前）＝**0.000**。`milli_refine` 重套 2、3 次不得漂移。人工 golden 若有未標旗零寬（L5[70]），只記例外，不擅自補旗。
5. confirmed zero 擋路時不可改它；先重審它是否真的 zero。人工實證 L2[21][53]、L3[14] 都是 zero→READ 後，COMM 才接在 R 後面，而非把 COMM 壓在 zero 同點；L5[20] 則是 READ→zero，因舊 R 其實屬 [18]。**zero 必須雙向驗且證據綁 pid/text，不得只沿用段號。**

## 5. 邊界：壇經從嚴否決吞段

依序執行每個邊界：

1. **前段尾**：找前段末句實際音訊與最後內容字精確 END。
2. **本段 own_first**：按 §3 確認，不得先套公式再找理由。
3. **先選內容轉場停頓，再取位**：own_first 前 10 秒的 dump gap 只是候選；須以 strict/soft 實體停頓及「前段尾在左、本段頭在右」選正確轉場。**不是永遠取最後一個 gap**（L4[47][61]），也不是把舊 start 吸附到最近停頓（L2–L5 回測 MAE 反而 0.702→0.914s）。
   - 已選定實體停頓後，L2–L5 人工取位中位數可按 `<0.5 / 0.5–1 / 1–1.5 / ≥1.5s` 暫用 `.458 / .554 / .804 / .804 × g`；這組係數**只用於實體停頓**，不可套 dump gap。
   - 舊 `.374 / .560 / .650 / .780` 是 dump gap 候選公式，不是內容選點依據，也不可混用。
4. **否決檢查＝淘汰該候選，不是自動退 contact**：
   - V1：gap 切在前段語義收尾或經文句中時列警示並重查雙側內容；長篇續講／切詞／切經文要淘汰，但 **1–3 字短收尾不是硬否決**（L4[107] 人工保留此型）。另找更早／更晚且雙向內容成立的實體停頓，不得自動吞，也不得自動退 contact。
   - V2：候選吞前段 ≥19 字或 ≥3.5s 材料，淘汰。
   - V4：strict/soft 皆無 ≥0.10s 重疊且吞 >3 字，淘汰。吞 ≤3 字也要查有沒有切詞或切經文。
   - 若被吞文字其實是本段自己的開頭，修正 own_first 到該開頭，不能把它誤記成前段。
   - **舊規則「V1/V2/V4 一律取前段末字 END」停用**：L4 contact 僅 14.3%、L5 僅 8.3% 落在人工值 ±0.3s，是主要微調來源。
5. **contact 是最後退路**：只有內容已正確切分、且 strict/soft 都證明兩側連讀沒有可停放的實體停頓時，才取**前段末內容字精確 END**（`t_end_of()`），不是本段 onset、onset−0.2 或插值。
6. **記錄**：note 必含前段尾、own_first 字@時間、所選實體停頓起訖／門檻、其他候選淘汰理由、取位公式或無停頓證據、舊值差、zero 判定。沒有這些證據就降 conf，不硬猜。

## 6. ASR 洞、切片與信心

- ≥2.5s dump 洞不直接套長洞 rel；以 strict/soft 實體停頓定界。
- 切片 ASR 原則上只信文字，不信時間戳；主 dump 找得到同字就回主 dump 精確值。多窗時基互斥時棄用切片時間。
- `volumedetect` 先分辨有聲掉字與真靜音；沒有 ASR 輸出不等於沒念。
- conf 建議：逐字長前綴 .85–.95；拼音／同音 .70–.85；實體停頓補救 .60–.80；弱證據或洞中估計 .50–.65。不得為了全綠灌 conf。

## 7. 施工與驗收

1. pull、快照、記錄 golden hash；建立 dump 與 strict/soft pauses。
2. 全講每個未 confirmed 邊界都走 §5；先盤點既有 rN，只寫下一個未用編號，只套用自己產生的表。
3. `milli_refine.py` dry-run→apply；第 2、3 次必須 **0 段變更**。head-zero 另查，不得只看 READ 鏈。
4. 驗證其他講次 byte-identical、所有 confirmed／reviewed 不變、pid/text 不變、無負長度／非單調／鏈破口、末段 end=duration；交疊例外只走 `preserve_end` 並在 earcheck 逐段列出。
5. 跑 `seq_align --mode metric`、`milli_audit`、`batch_verify`、完整 HTMLParser `span_audit`、`pin_check`。
6. **L4／L5 分開回歸**：任何新自動規則都要報各講 MAE、±0.3s／±0.5s 比例及 contact／hosting／zero 分組；禁止只報合計平均，禁止 nearest-pause snapping。strong head/final 可低優先複核，舊 contact／weak-nearest 必須重裁。
7. metric 未被覆蓋＝未判定，不是正確；所有 >0.7s 殘餘逐筆裁定。span unknown／bad 逐段解釋，不能為比例把 READ 改回 zero。
8. `sync_para_pids.py`→鎖版 venv `gen_all.py`→books2ebook／word2ebook pytest→`check_site.py`。人工未勾 reviewed 前，公開 ebook 不注入新講次是正常閘門，不可代勾。
9. 交付 SoT、rN 裁決表、耳機清單與實際驗收輸出；每個 conf≤0.65、掉字洞、zero→READ、V1/V2/V4、語序／插講都列入人工試聽。

## 8. 第 4 期特別守門

- 不把舊 agent 草案直接套回人工版；只借作候選證據，逐段依本 skill 重裁。
- [21]/[22] 要先量「童子曰…」自己的 R，不能仿舊③直接 zero；若 R 成立，[21] READ，[22] 接在 R 後。
- [0]–[15] head-zero=0.000；[33] 這類白話先起、經文後到的插講不可倒序；[68] 須證明有無獨立偈語，不可一概 zero。
- 舊零寬 [52][67][83][92][97] 必須各自以 R 證明 READ，不能只是沿舊表恢復。
- 對所有自動提案先做「前段插引 vs 本段印字開頭」檢查，特別是 [24][69][80][85][92][93][94][96][100][106][112]。

## 9. 完成定義

- [ ] 最新人工 golden 未變；其他講次 byte-identical。
- [ ] 每個邊界都有 §5 證據與 note；own_first 不是前段插引／過場。
- [ ] 每個 zero 都證明 R 不存在；每個短 R 都 READ 且 `zero:false`。
- [ ] 鏈、head-zero、幂等、pid、非目標講次全過；音訊證實的交疊／未標零寬例外有逐段記錄，且未為轉綠改寫人工值。
- [ ] metric／span／pin 殘餘逐項裁定，未把工具無輸出當正確。
- [ ] 人耳清單完成；agent 未代勾 confirmed／reviewed；ebook 重建與測試通過。
