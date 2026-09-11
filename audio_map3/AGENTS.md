# audio_map3 — 講經系列「段落 ↔ 音檔」毫秒級精準對齊 skill

> 這份文件是**給 agent / 未來校對者**的通用作業程序：如何把一個講經系列的
> `<series>.json` 對齊到「每段開頭第一個字毫秒級對齊音檔實際念出的第一個字」、
> 全段落高信心，並正確處理經文/偈語「念誦」與「不念」兩種情況。
>
> SoT JSON 位置：`audio_map3/<series>.json`（series ∈ `ganen / sishierzhang /
> lengqie / liuzutanjing / lengyanjing`）。產出由 `tool/jiangjing_para_map/`
> 的 DTW 對齊器產生；books2ebook 只注入 `reviewed=true` 講次的段落時間。

---

## 0. 核心心智模型（先讀這一段）

講經電子書每一段（`<p class="para-block">` 或 `<div class="sutra-text para-block">`）
分兩類，對齊策略完全不同：

| 類別 | 辨識 | 對齊策略 |
|------|------|---------|
| **講解段（commentary）** | `class` 無 `sutra-text` | 必須 DTW 錨定到音檔「實際念出的第一個字」，`conf` 反映字元級證據 |
| **經文/偈語段（sutra）** | `class` 含 `sutra-text` | 師父「可能念、也可能不念」，兩者都要處理（見 §4） |

**關鍵事實（用四十二章經第 1、2 講 golden sample 驗證過）：**

1. 經文/偈語段落絕大多數**不是逐字念誦**——師父是把經文「融入白話講解」，
   先引一句、再解釋。所以經文段的字元在 ASR 逐字稿裡通常**找不到逐字匹配**。
   實證：四十二章經 3–14 講 44 個 `skipped-sutra` 段落，**100% 逐字 0 命中**
   （即確實沒被逐字念出）。

2. 但也有例外：短經文／偈子（如「佛言：辞亲出家，识心达本…」）師父**會逐字念**，
   這種段要錨定成有實寬 `[start, end)` 的讀段（見 golden L2 p2：13.57→19.00）。

3. **毫秒級天花板由 ASR 決定**：只有當段落開頭 ~6–8 字**逐字**出現在 ASR 逐字稿時，
   才能做到「開頭第一個字 ≤50ms 對齊」。文言經文＋快速帶讀會產生大量同音錯字
   （「佛子住持」→「佛子助持」、「善超诸有」→「善超猪油」），這些段只能靠
   pinyin 模糊 DTW 逼近（約 ±0.5–3s），**不可能逐字毫秒級**。這是誠實的物理上限，
   不要為了「全高信心」去灌 conf。

4. golden（人工 confirmed）段落是**不可侵犯的鐵錨**：重跑對齊器時，其
   `start/end/conf/confirmed` 必須**完全不變**。這是最容易出 bug 的地方（見 §5 已修的 bug）。

---

## 1. 前置：確認輸入齊備

```bash
# 1) SRT/ASR 字幕（字元時間流來源；缺檔該講會被跳過）
ls /Users/paul/tai/audio/srt/jiangjing/   # <basename>.srt
# 2) FunASR 字元級 dump（毫秒級時間源；由 funasr_dump.py 產生）
ls /tmp/funasr_cache/<series>/             # <N>.json（N = 講次）
# 3) 電子書段落（段落 text/pid/class）
ls ebook/0X.html                          # sishierzhang=07, lengqie=08, liuzutanjing=09, lengyanjing=10, ganen=04
# 4) 系列↔講次↔basename 映射
python3 -c "import sys; sys.path.insert(0,'tool/books2ebook'); from audio_map import AUDIO_MAP; print(AUDIO_MAP['<series>'])"
```

**環境**：`realign_dtw.py` 與 `funasr_dump.py` 需要 `numpy / pypinyin / opencc / funasr`，
統一用 `tool/sense_voice/.venv/bin/python` 執行（別用裸 `python3`，會缺 numpy）。

---

## 2. 產生 FunASR 字元級 dump（若 `/tmp/funasr_cache/<series>/` 缺檔）

```bash
# 全系列（已存在的 dump 自動跳過；--force 強制重跑）
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/funasr_dump.py --series sishierzhang
# 或單講
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/funasr_dump.py --series sishierzhang --lecture 3
```

產出 `/tmp/funasr_cache/<series>/<N>.json`：
`{"basename", "duration", "text", "timestamp": [[ms_start, ms_end]…], "sentence_info"}`。
`timestamp` 每個元素是「一個字的 [開始毫秒, 結束毫秒]」——**這就是毫秒級時間源**。

> 用 paraformer-zh + fsmn-vad + ct-punc（CPU）。這是本 repo 唯一能輸出可靠
> 句級/字級 timestamp 的管線；SenseVoice-Small 更準但無 timestamp，不適用。

---

## 3. DTW 對齊（主流程）

```bash
# dry-run 先看每講報表
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/realign_dtw.py --series sishierzhang --dry-run
# 真正寫檔（保留 confirmed 段落與 reviewed 講次）
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/realign_dtw.py --series sishierzhang
# 只跑單講（快速迭代）
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/realign_dtw.py --series sishierzhang --lecture 5
```

`realign_dtw.py` 的對齊原理（DTW + 前後逼近，正是「來回檢驗」的實作）：

1. **錨定**：段頭 needle 在正規化 ASR 字元流（字元→拼音→拼音 4gram 種子投票）找候選，
   numpy 向量化 DTW 逐字打分，語速合理性（1–12 字/s）過濾幻影。
2. **經文處理**（§4）：lecture 頭整章塊、中段偈塊分別判斷「念 / 不念」。
3. **pass 2 收斂**：未錨定的講解段，在前後已錨定鄰居之間的 gap 內重新錨定。
4. **邊界串鏈**：`end[i] = start[i+1]`；末段 `end = duration`；`skipped-sutra` 取零寬。
5. **夾逼 evidence pass（`dtw-evid`）**：3 輪掃描，用「前後已驗證鄰居」夾住每段，
   在 [prev_end, next_start) 內重新驗證；verbatim 段頭直接 snap 到字時間戳。
6. **頭驗證修復**：DTW 自由 skip-in 把頭釘在窗頭（音節湯）的，若 12s+ 後有
   更強匹配則改釘到真正念出的位置。

輸出 `<series>.json`，每段：`{pid, text, start, end, conf, method, confirmed}`。
`method` 可信度由高到低：`dtw-evid`（夾逼驗證）> `dtw/dtw2/dtw-frag/dtw-scan`（DTW 錨定）
> `interp`（插值，無證據）> `skipped-sutra`（判定不念，零寬）。`conf` 是證據強度。

---

## 4. 經文/偈語：念 vs 不念（兩種情況都要判）

`realign_dtw.py` 用完整塊 DTW 覆蓋率（cov）判定：

| 情況 | 判定條件 | method | 結果 |
|------|---------|--------|------|
| **不念**（多數） | 全塊遍掃 cov < 0.45（文言被白話講解替代，逐字找不到） | `skipped-sutra` | `start == end`（零寬），conf = 不念證據強度 |
| **逐字念** | 塊頭連續 DTW 起始且語速合理，cov ≥ 0.5 | `dtw` / `dtw-evid` | 有實寬 `[start,end)` |
| **片段念**（偈子穿插講解中念） | 段頭 10 字 chunk DTW ≥ 0.8 | `dtw-frag` | 有實寬（只框「念出的那一段」） |
| **重複/合併** | 與前一段同源（電子書把同一引文拆兩筆） | `subsumed-dup` | 釘在前段讀段末邊界 |

**校對時務必用「逐字」而非「拼音模糊」驗證不念**：拼音模糊 probe 會把文言經文的
同音白話講解誤判成「有念」（文言與白話共享音節）。正確做法：把經文段正規化全文
（或頭 8 字）拿去 `stream.find()` 逐字找，**找不到 = 確實不念**。

```python
# 快速驗證某系列的 skipped-sutra 是否真的「逐字不念」
# （見 §6 的 verify_skips.py 片段）
```

---

## 5. golden sample 的正確用法 + 一個必修的 bug

**golden sample**（例：四十二章經第 1、2 講，`reviewed=True` 且每段 `confirmed=True`）是
人工對齊的鐵標竿。用法：

1. **不要對齊已 confirmed 的講次**——直接當基準，重跑時驗證其 `start/end/confirmed`
   完全不被改動（見下方「驗證 golden 未動」命令）。
2. **從 golden 學「段落開頭」的定義**：人工 start 通常落在「該段實際念出的第一個字」，
   容許前面 1–3 個語氣詞（「啊就」「有这是」）——這正是 DTW 的 `LEAD_BACK=0.15s` 要逼近的。
   不是把 start 釘在語氣詞前，而是釘在「內容開始」。
3. **從 golden 學經文兩種情況**：L2 p0（整章經文塊）`start==end`（不念）；
   L2 p2（短經文「佛言：辞亲出家…」）有實寬 13.57→19.00（逐字念）。

> **⚠ 必知的 bug（已修）**：`realign_dtw.py` 原本在 pinning 之後的最終單調 clamp
> （`for r in res: r["start"]=max(r["start"], last_t)`）會把 confirmed 段的 `start`
> 往前推（若前一段 `end` 越過它）。這會**污染 golden sample**。已在 pin 循環加
> `if i in pin_set: last_t=r["end"]; continue` 保護。**任何改動此邏輯的人，改完務必
> 重跑一次並驗證 golden 逐段 byte-level 不變**（下面命令）。另外：污染一旦寫進
> JSON，後續重跑會把「汙染值」當成 old 來源再回寫，所以修 bug 後要 `git checkout`
> 還原 JSON 再重跑。

```bash
# 驗證 golden 講次完全未動
python3 - <<'PY'
import json
old = json.load(open('audio_map3/sishierzhang.json'))  # 對齊前先備份 / 或 git HEAD
# 對齊後：
new = json.load(open('audio_map3/sishierzhang.json'))
for n in ('1','2'):  # golden 講次
    a,b = old['lectures'][n]['paragraphs'], new['lectures'][n]['paragraphs']
    ok = all(x['start']==y['start'] and x['end']==y['end'] and x['confirmed']==y['confirmed']
             for x,y in zip(a,b))
    print(f'L{n} golden intact:', ok)
PY
```

---

## 6. 客觀驗證（不要相信自報 conf）

`realign_dtw.py` 自報的 `conf` 會因結構性結論（interp 洞、skipped-sutra、in-bounds 命中）
而**下限抬高到 0.8+**，不足以代表「真的毫秒級」。務必用兩個客觀工具交叉驗證：

### 6a. span_audit.py（位置對不對）

```bash
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/span_audit.py --series sishierzhang
# 產出 reports/span_audit_<series>.json + console 摘要
```

| verdict | 意義 | 對策 |
|---------|------|------|
| `span_ok` | 頭在 start（±3s）＋塊在 span 內 → 位置可信 | 目標：越高越好 |
| `skip_ok` | 零寬＋全塊遍掃 cov<0.45 → 確實沒念 | 正確 |
| `span_bad` | 證據與記錄位置矛盾 → **真的錯** | 要修 |
| `unknown` | 位置可能對但字太弱（ASR 錯字） → 需人工眼 | 記錄 |

目標：`span_bad` 逼近 0；`unknown` 是 ASR 上限，接受並保留低 conf 供人工。

### 6b. pin_check.py（毫秒級 pin 對不對）

```bash
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/pin_check.py sishierzhang
```

檢驗「段落開頭 6 字逐字出現在 ASR、且 map start 釘在該字 ±0.05s」。輸出
`pinned<=0.05s` 比例。**關鍵**：`no-verbatim-hit` 越多 = ASR 越爛 = 越無法逐字毫秒級。

### 6c. 逐字驗證 skipped-sutra（§4 的「逐字不念」核對）

```bash
tool/sense_voice/.venv/bin/python - <<'PY'
import json, sys, numpy as np
sys.path.insert(0,'tool/jiangjing_para_map')
from realign_dtw import load_dump, norm_para, FILLER_RE, DUMP_DIR
doc = json.load(open('audio_map3/sishierzhang.json'))
tot = verb = 0
for n, lec in doc['lectures'].items():
    if int(n) <= 2: continue                      # 跳過 golden
    dump = load_dump(DUMP_DIR/'sishierzhang'/f'{n}.json')
    stream = norm_para(''.join(dump['chars']))
    for p in lec['paragraphs']:
        if p['method'] != 'skipped-sutra': continue
        tot += 1
        norm = norm_para(p['text'])
        if len(norm) >= 10 and norm in stream:    # 逐字全文在 ASR = 其實有念
            verb += 1
print(f'skipped-sutra 逐字誤判: {verb}/{tot}（應為 0，若 >0 表示有經文被誤判成不念）')
PY
```

---

## 7. 完整作業順序（照著走一遍）

```bash
cd /Users/paul/tai/taiguanglin.github.io

# 0) 備份 + 記下 golden 講次
cp audio_map3/<series>.json /tmp/<series>.json.bak

# 1) 確保 dump 齊全
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/funasr_dump.py --series <series>

# 2) dry-run 看報表
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/realign_dtw.py --series <series> --dry-run

# 3) 對齊（寫檔）
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/realign_dtw.py --series <series>

# 4) 驗證 golden 未動（§5 命令）

# 5) 客觀稽核 + 毫秒級 pin
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/span_audit.py --series <series>
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/pin_check.py <series>

# 6) 逐字核對 skipped-sutra（§6c）

# 7) 若 span_bad 過多 → 回 §3 用 --lecture 單講調，或提 ASR 品質（重新轉寫）
```

---

## 8. 迭代「前後逼近」的具體手法（當信心不足時）

當某段 `conf` 低或 `span_bad` 時，不要亂猜，用**前後逼近（夾逼）**來回收斂：

1. **看前後已錨定鄰居**：`realign_dtw.py` 的 evidence pass 已自動做
   「在 [prev_anchor_end, next_anchor_start) 內重新 DTW」。若還失敗，多半是
   該段開頭被 ASR 打成同音錯字 → **無法逐字錨定**。
2. **換錨點**：段頭太髒時，取段「後 1/4 或中段」的 14 字做 needle 再測
   （工具 `multi_head_confirm`/`needle_scan_anchor` 已做多 offset 掃描）。
3. **語速門檻**：任何 DTW 命中的「念出跨度」必須滿足 1–12 字/s，否則在縫同音字的幻影。
4. **earliest 偏好**：同一段文字可能被「先引一遍、後面討論時再提」；對齊時取
   **最早**那次（經文按順序，後面的重現是回音不是本段錨）。
5. **重複/回音陷阱**：短句（「佛言」「下一句」）在全經大量重複，若 gain 不到唯一
   位置，就**不硬錨**，標低 conf 讓人看。

**「全段落高信心」的誠實定義**：`conf ≥ 0.8` 且 `method ∈ {dtw-evid, dtw, dtw2, dtw-frag,
dtw-scan, skipped-sutra}`（有證據）；`interp` 是無證據插值，最多給 0.8 下限並標
`method=interp` 供人工。**不要**把 `interp`/`skipped-sutra` 的 conf 灌到跟 `dtw-evid`
一樣——那會騙過電子書的「高亮跟播」，卻未真正毫秒對齊。

---

## 9. 完成判定與注入

- 想要「跟播」生效：把該講 `reviewed` 設 `true`（可手改 JSON 或在 `audio_map3/index.html`
  的 UI 勾「本講校對完成」並用 PAT 存回）。
- 重新注入段落時間到電子書：

```bash
cd tool/books2ebook && python3 gen_all.py   # books2ebook 只注入 reviewed=true 講次
```

- 最終交付：`audio_map3/<series>.json`（UTF-8、`ensure_ascii=False`、按講次排序），
  保留了 golden 講次的 confirmed 段落、其餘講次 DTW 對齊結果。

---

## 10. 已知限制（寫進交付說明，別假裝做到）

1. **ASR 是毫秒級的天花板**：只有段落開頭逐字出現在 ASR 時才能 ≤50ms；文言經文＋
   快速帶讀的同音錯字使 ~80% 段落無法逐字錨定，只能 pinyin 模糊 DTW（±0.5–3s）。
2. **楞嚴咒等長咒語/快速咒念**：ASR 幾乎無有效輸出，該區段落只能插值（`interp`）。
3. 遇到這兩類，誠實標低 conf / `interp`，交付時說明，而非灌 conf 假裝「全高信心」。