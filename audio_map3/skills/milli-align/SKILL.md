---
name: milli-align
description: 講經系列「段落 ↔ 音檔」毫秒級精準對齊 skill。以人工 golden 講次（如楞伽經 L1–4）為對齊要求範本，用 FunASR 字級 dump 對每段做逐字／拼音夾逼證據對齊，處理經文／偈語的各種念誦情況（全念、不念、唸到一半開始講解、中斷插講、後方重引），讓段落開頭第一個字毫秒級對齊音頻實際念出的第一個字，並誠實標記信心與待人工試聽清單。適用於校對 audio_map3/<series>.json 的任何講經系列（lengqie / liuzutanjing / lengyanjing / sishierzhang / ganen）。
---

# 毫秒級段落對齊（milli-align）

把一個講經系列的 `<series>.json` 對齊到「每段開頭第一個字 ＝ 音頻實際念出的第一個字」。
輸入：`audio_map3/<series>.json`（段落）、`/tmp/funasr_cache/<series>/<N>.json`（FunASR 字級 dump，
毫秒時間源）、`ebook/<K>.html`（SUTRA/COMM 分類）。背景知識見
[../../../audio_map3/AGENTS.md](../../AGENTS.md)（產線三階段、已知坑），細節數據與案例見
[reference.md](reference.md)。

## 0. 什麼時候用這個 skill

- 要把某講次（例：lengqie L5）對齊到毫秒級、全段落高信心。
- 要把人工 golden 的對齊慣例推廣到其他講次／系列。
- span_audit / pin_check 報出大量 span_bad，或段落播放起點明顯不對。

## 1. 鐵律（先讀，違反即返工）

1. **golden 不可侵犯**：`reviewed=true` 或 `confirmed=true` 的段落，start/end/conf/confirmed/zero
   重跑前後必須 byte-level 不變。寫檔前後都要跑校驗（§6）。
2. **證據先於位置**：每個位置必須有證據（逐字 hit、拼音 DTW、run-onset、鏈）。沒證據就用夾逼
   區間＋誠實低 conf，不要硬猜、不要灌 conf。
3. **conf 誠實階梯**：verbatim ≥0.9 ／ 近逐字 0.85 ／ 拼音 0.7–0.8 ／ 弱拼音 0.6（列人工）／
   夾逼插值 ≤0.75 ／ 不念證據 0.8–0.95。人耳（UI confirmed）永遠是最終裁判。
4. **寫回只動目標講次**：start/end/conf/method/zero；`confirmed` 鍵一律不碰。

## 2. golden 慣例（從楞伽 L1–4 人工對齊實測；換系列先重測 §5.1）

| 慣例 | 實測值 | 用法 |
|------|--------|------|
| 鏈 | golden.start == 前一個 READ 段的 end（median 誤差 0.000） | `end[i]=start[next READ]`；zero 段透明；末段 end=duration |
| 段首 lead-in | golden.start 落在第一個內容字**之前** 0～4s（median −0.84），絕不晚於內容字（max 0.00） | start = run-onset：從內容字往回走 ≤0.7s 停頓／語氣詞，且 ≥ prev_end |
| 講首導言 | intro.start = t(ASR 首字) − 0.2s（L1–4 實測 −0.35/−0.25/−0.20/−0.20） | 講首第一個 COMM 段就這樣釘 |
| 講首印刷塊 | 整章／長 passage 塊 = zero（書序參考文字），朗讀歸後方逐行引文段 | 見 reference.md §B |
| 搜尋窗 | 證據只在 [prev_end−0.3, next_start+0.3] 找；越窗的模糊命中是鄰段的回音 | 沒窗約束時 fuzzy 偏早 median −1.9s |
| 語速 | 朗讀 1–12 字/s；<0.8 字/s 的胖 span 多半吞了鄰段；>12 字/s 是幻影 | 胖／瘦 span 都要重切 |
| 經文不念 | 逐字遍掃找不到（拼音模糊會誤判，勿用） | zero + 誠實 conf |

## 3. 經文／偈語的五種情況（使用者明示「各種情況都有」）

| 情況 | 判定 | 產出 |
|------|------|------|
| **完全不念** | 逐字全文（或頭 8 字）在講內 ASR 找不到、且無局部 clean 命中 | `zero:true`，起訖＝鏈位置（prev READ end），conf 0.8–0.95 |
| **全念** | 塊頭逐字/拼音連續命中、語速合理 | READ span；start=run-onset |
| **唸到一半就講解** | 只命中頭 4–10 字，後續直接接講解語流 | READ span 只蓋「實際念出的那截」；conf 0.6–0.75 |
| **中斷插講** | 長 passage 朗讀中途插入白話（講完又續念） | 引文段與插講段各自成 span，按音訊順序切（書序≠語序） |
| **後方重引** | 同文出現兩次：第一次被書序在前的段認領，第二次（講解前重引）歸書序在後的獨立引文段 | 後段拿第二次 vocalization |

**行內引文歸屬**：短 vocalization 同時符合「獨立 SUTRA 段頭」與「後方 COMM 行內引文」時——
vocalization 前有 ≥0.6s 停頓或「啊/哈」結尾、或匹配到更完整的經文 → 歸 SUTRA；
與 COMM 語流同一口氣接連 → 歸 COMM（SUTRA 記 zero）。

## 4. 作業流程（照順序走）

### 4.1 備齊輸入
```bash
ls /tmp/funasr_cache/<series>/            # 缺就先跑 funasr_dump.py --series <series>
```
統一用 `tool/sense_voice/.venv/bin/python`（numpy/pypinyin/opencc）。
注意：`dump_window.py <series> <N>` 有 glob bug 會抓到 `15.json` 代替 `5.json`——
直接指定 `/tmp/funasr_cache/<series>/<N>.json`。

### 4.2 證據稽核（先看現況哪裡壞）
```bash
tool/sense_voice/.venv/bin/python audio_map3/skills/milli-align/scripts/milli_audit.py --series lengqie --lecture 5
```
逐段檢查：頭部逐字/拼音命中（窗內）、語速、zero 的逐字不念驗證、鏈完整性、COMM 零寬。
產出 defects 清單。**自報 conf 不可信，以這個稽核為準。**

### 4.3 逐段判讀（defect 才需要）
對每個 defect 開 ASR 視窗聽「字」：
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
判讀原則：同音錯字當逐字看（「凡诗四天」=梵釋四天）；對照段落全文找最長連續匹配；
用 §3 表決定 span；邊界用鏈＋run-onset。

### 4.4 套用修正
把判讀結果寫成 adjudication table（每段 `{i, start, end, conf, method, zero, note}`，
範例見 `tool/jiangjing_para_map/reports/lengqie_L5_adjudication.json`）：
```bash
tool/sense_voice/.venv/bin/python audio_map3/skills/milli-align/scripts/milli_refine.py \
  --series lengqie --lecture 5 --table tool/jiangjing_para_map/reports/lengqie_L5_adjudication.json --apply
```
（table 缺的段落用鏈＋現值保持不動；`--dry-run` 只印差異。）

### 4.5 回頭檢驗（十分逼近）
修完再跑 §4.2 稽核；conf <0.8 或 span_bad 的段落回到 §4.3 重判，直到：
- 全段 conf ≥0.8（少數證據天生弱的段落列入人工清單，conf 誠實保留）；
- 鏈完整（end[i]=start[next READ]、末段=duration、zero 起訖相等且錨在鏈上）；
- zero 段全部通過逐字不念驗證。

### 4.6 驗收寫檔
```bash
# golden 不動 + 目標講次旗標不動（milli_refine --apply 內建校驗，失敗即 abort 不寫檔）
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/span_audit.py --series lengqie
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/pin_check.py lengqie
```
交付物：更新的 `audio_map3/<series>.json`＋人工試聽清單（reports/）。需要跟播生效時，
使用者在 UI 勾「本講校對完成」（reviewed）——**agent 不代勾**。

## 5. 換新系列時的校正步驟

1. **重測 golden 慣例**：`scripts/golden_offsets.py --series <X> --golden 1-4`
   輸出鏈誤差、lead-in 分佈、講首導言 offset——如果與 §2 表差很多，以新實測為準。
2. **找該系列的講首結構慣例**：整章印刷塊 vs 導言 vs 重複引文的排法各系列不同
   （四十二章經見 AGENTS.md §0.5；楞伽長 passage 見 reference.md §B）。
3. 之後照 §4 走。SRT 重生成（`gen_srt.py`）只在 dump 品質不足時用——dump 已是毫秒源，
   SRT 只是粗字幕。

## 6. 完成定義

- [ ] 目標講次每段：conf 由證據支撐、start 落在「實際念出第一個字」的 run-onset（≤0.7s 停頓邊界，永不晚於內容字）
- [ ] 經文五情況各自正確歸位；zero 段逐字驗證通過
- [ ] 鏈完整；講首三段結構符合慣例
- [ ] golden 講次 byte-level 不變；confirmed/reviewed 旗標不變
- [ ] span_audit 對目標講次無 span_bad（unknown ≤ ASR 天花板）
- [ ] 人工試聽清單已寫入 reports/，弱證據段落如實標記
