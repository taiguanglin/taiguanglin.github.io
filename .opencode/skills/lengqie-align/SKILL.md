---
name: lengqie-align
description: Use when aligning 楞伽經 lecture paragraphs to audio in audio_map3/lengqie.json, fixing skipped-sutra/read-zero errors, rescuing swallowed intros, or auditing alignment quality with tune/span_audit. Covers the engine+SKILL pipeline (realign_dtw + align_lengqie.py) and the manual-review workflow.
---

# 楞伽經段落 ↔ 音檔精準對齊（lengqie-align）

> 經驗來源：`audio_map3/lengqie.json` L1–3 人工 golden（2026-09，UI 逐段試聽＋0.1s
> 微調＋`confirmed/reviewed`），以 SRT／FunASR 字級時間流逐段實證。
> 執行器：`tool/jiangjing_para_map/align_lengqie.py`（engine＋結構修正層）。
> 只做音檔對齊：永不觸碰 `confirmed`／`reviewed`／L1–3。

## 1. 對齊對象的結構（先看懂再動手）

每講電子書（`ebook/08.html`）段落分兩類（`cls`：`SUTRA`＝含 `sutra-text`，否則 `COMM`）：

| 類別 | 位置 | 師父行為 | 對齊 |
|------|------|---------|------|
| 首 SUTRA run（每講第一個連續 SUTRA 區，如 L4 p0、L2 p37–40、L3 p0–6） | 講首 | 印刷參考塊，**不念** | ZERO（`start==end`，`zero:true`） |
| 短引文（SUTRA，norm ≤ 60 字） | 引文＋講解交替 | **念出**（逐字／片段／微讀）或**跳過**直講 | READ 實寬／SKIP 零寬 |
| 長 SUTRA（norm ≥ 100 字，中段） | 中段 | 可能整塊念（如 L3#81，3.5 字/s）或只念頭＋改述（如 L2#58） | 證據仲裁 |
| COMM 講解段 | 全講 | **恆念出**（golden：COMM 零寬＝0 段） | 恆 READ，找不到錨只許插值＋標記，不許判 zero |

關鍵實證（皆有 ASR 對照，不可憑空想像）：

1. **書序≠語序**：導言 COMM（「《楞伽經》第X期…」）在書中排在首經文塊**之後**，
   但音檔裡**先念**（L4：1.5s 先念導言，經文引用 11s 才出現）。解法不是重排，
   而是首塊判 ZERO＋導言從講首錨（R1/R3）。
2. **subsumed-dup**：長塊頭部被後方短引文覆蓋（如 L4 p0 頭＝p2 全文）→
   vocalization 歸短引文，長塊 ZERO。只看頭部命中會誤判長塊為 READ（§0.5 系統性錯誤）。
3. **位置消歧靠順序，不靠全域搜尋**：同一經文會在講中重現（L2#38 全文在 #58 重念）。
   全文覆蓋測試必須用**局部窗**（前一錨後＋約 175s），否則遠方重讀造成誤判 READ。
4. **回音陷阱**：師父講解時會重提引文（如 L3#50 重提 #49 前 5 字），engine 偶爾把
   後段的 quote-mention 算到引文頭上（L4 p2 錨到 p3 改述區，晚 5s）。殘差交人工，
   不要用 naive earliest-snap 硬拉（已實證在 golden 製造回歸，見 §5）。
5. **人類自己也不完美**：golden 有 5 處 gap/overlap（L3#26  overlap 9s）、微讀段
   （16 字給 0.2s）、shortcut（念出的偈子併入講解段 L3#49）。自動對齊以**證據**為準，
   不以 100% 複刻人類為準；`span_audit` 對 golden 微讀段也會報 `span_bad`／`unknown`
   ——那是 ASR 可驗證性下限，不是錯誤。

## 2. 管線：engine（DTW）＋ SKILL 修正層

```
FunASR 字級 dump (/tmp/funasr_cache/lengqie/<N>.json，缺檔跑 funasr_dump.py)
        │
        ▼
realign_dtw.align_lecture（字級 DTW：verbatim→pinyin→4gram 投票→DTW 驗證→
        語速門檻→evidence 夾逼；sutra 延遲到 pass 1.5 防級聯污染）
        │
        ▼
align_lengqie.py skill_correct（R1–R8 結構修正＋鏈化＋人工清單）
        │
        ▼
audio_map3/lengqie.json（只寫 L4–42 的 start/end/conf/method/zero）
```

R 規則（`skill_correct` 內按 R1→R4→R8→R6'→R7→R5 順序執行）：

- **R1/R2 首 run 長塊仲裁**：首 SUTRA run 中 norm≥100 且 engine 給實寬者，
  以 engine span 為中心做局部全文貪婪覆蓋；`cov < 0.60` 或頭部被後方 10 段內短引文
  覆蓋 → `block-zero`。L4 p0 實測 `cov=0.06, subsumed=True` → 正確歸零。
- **R3 被吞導言救援**：首 run 後 6 段內零寬 COMM → 在 `[0, 下一實寬]` 內逐字
  （off 0/8/¼）＋拼音 fuzzy（≥0.60）重錨。L4 p1 從 14.90 零寬救回 1.54s（真值 1.5s）。
  （頭部 ASR 髒是常態：「楞伽經」→「孟奇經」，純逐字必敗。）
- **R4 誤判 skip 救援**：零寬短引文在局部間隙依序試 頭逐字→體逐字（off 4/8，
  治口吃重複頭）→拼音 DTW（≥0.55，**禁區**：路徑起點限窗內，防 pad 區回音劫持；
  另有 1–12 字/s 語速門）。只救「清楚念出」；微讀（2–6 字帶過）證據不足不硬救。
- **R8 過胖引文拆分**：SUTRA 實寬語速 `< 2.5 字/s`＋緊鄰零寬 COMM → 前段按
  4.5 字/s 切給引文，後段還給講解（`split-give`）。L3#25/#26 實測切出 240.7s，
  人工值 241.99s（Δ1.3s）。
- **R6' 回音誤讀修正（安全網）**：READ 短引文語速 `< 3.0 字/s`＋自身 10 字頭無證據
  （逐字＋fuzzy<0.5）＋後兩段內有 10 字頭逐字回音 → `echo-zero`，後段起點前移。
  真讀有口吃也可能慢，故三閘門缺一不可。
- **R7 COMM 永不零寬**：零寬 COMM 按字數加權拆分包夾間隙；間隙 > 60s 者
  `NEEDS-HUMAN`（如 L4 p41 104s 大洞——engine 留白比亂填誠實）。
- **R5 鏈**：`end[i]=start[i+1]`（尊重 `end_fixed`），zero 重壓零寬，講首零錨首讀，
  單調夾逼。與人類 L1（0 breaks）同式。
- **已刪除 R9（early-snap）**：最早模糊命中多為口吃預演，硬拉在 golden 製造
  4–9s 回歸。教訓：**不要跟 engine 的 evidence 仲裁對著幹**；殘差走人工 UI。

`rescue-blocked`：有證據但鏈位置被鄰段佔據 → 如實標記進人工清單，不靜默吞掉。

## 3. 參數（tune 鎖定，改前重跑 `--tune`）

`HEAD_N=14`、`LEAD_BACK=0.15`、`FULL_T=0.60`、`SHORT_Q=60`、`LONG_B=100`、
R4 fuzzy≥0.55、R3 fuzzy≥0.60、R8 `<2.5字/s`＋切分語速 4.5 字/s、R6' `<3.0字/s`。

## 4. 標準作業

```bash
# 0) 備份
cp audio_map3/lengqie.json /tmp/lengqie.json.bak
# 1) 補 dump（缺哪講補哪講；CPU 約 1–2 分鐘/講）
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/funasr_dump.py --series lengqie
# 2) 調參驗證（唯讀；人类 golden L1–3 為錨，見 §5 水位）
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/align_lengqie.py --tune
# 3) 單講試跑 → 看 skill reason 是否合理
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/align_lengqie.py --dry-run --lecture 4
# 4) 全量試跑（只印報表）
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/align_lengqie.py --dry-run
# 5) 寫檔（內建三重鎖：拒寫 L1–3／拒改 reviewed／confirmed 全系列比對；違者 assert 中斷）
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/align_lengqie.py --apply
# 6) 客觀稽核
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/span_audit.py --series lengqie
tool/sense_voice/.venv/bin/python tool/jiangjing_para_map/pin_check.py lengqie
```

人工清單：`tool/jiangjing_para_map/reports/lengqie_manual_review.json`
（`skip-quote:verify-by-ear`／`low-conf`／`rescue-blocked`／大間隙 `comm-split`），
在 `audio_map3/index.html` 逐段試聽後寫回（此時才動 `confirmed`——那是人工 pass，
本管線永不代勞）。

## 5. 精度水位與誠實殘差（tune 實測，改動規則後必須達到）

| 講 | engine mean\|Δ\| | skill 後 | P≤1s | zero-P/R | skill 零回歸 |
|----|---------------|---------|------|----------|-------------|
| L1 | 1.79s | 1.79s（0 改動） | 50.9% | — | ✓ |
| L2 | 2.90s | 2.90s | ~30% | 78%/100% | ✓（REGRESS 行必須為空） |
| L3 | 2.49s | 2.17s | ~48% | 54%/88% | ✓ |

殘差三類，皆為 ASR 可驗證性下限（`span_audit` 對 golden 同樣報 bad/unknown），
**不許灌 conf 假裝解決**：① 微讀（2–6 字帶過，如 L2#52「諸識無我」→「初始无我」）；
② 無 vocalization 的 content-split（如 L3#39，6s 是人工耳切）；③ 口吃預演回音。
另有一類反向：engine 對但 golden shortcut（如 L3#49 偈子確有念出）——以證據為準保留。

## 6. 禁區

1. `confirmed`／`reviewed`／L1–3 數值：讀可以，寫不行（`--apply` 內建 assert）。
2. `method` 標籤只供稽核，不代表演算法血統；`conf` 是證據強度，不許為「全高信心」灌水。
3. 缺 dump 不許用 SRT 線性插值冒充毫秒級（鏈上可差數秒）；先跑 `funasr_dump.py`。
4. 任何改動先過 `--tune`：`skl-mean` 不得劣於 `eng-mean` 超 0.2s、REGRESS 必須為空。
