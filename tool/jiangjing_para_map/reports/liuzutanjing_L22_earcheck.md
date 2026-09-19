# 壇經 L22（頓漸品第八·志徹行昌刺師）人工試聽清單

套用 milli-align skill 後：READ 140 / zero 21、鏈破口 0、no-evidence 0。
請以 UI 逐段試聽——尤其 conf <0.8 者。本講 baseline 有 115 個 zero 寬段（講解塊全零寬），
已以 ASR 序列錨點全部改 READ。

## 結構判定

```
書序：[0]-[9] 整章經文塊（zero@0.81，師父未在講首整讀）
     → [10] 導言（0.81-20.43）
     → [11]-[23] 經文讀／講解 READ
     → [24] 經文讀（207.84-209.62）→ [25] 講解（209.62-294.31）
     → [26] 過渡 zero → [27]-[33] 經文讀／講解 READ
     → [34]-[43] 講解 READ → [44] 過渡（425.78）
     → [45] 經文讀（428.10）→ [46]-[160] 講解 READ（鏈 pass 修 end）
```

## 修正紀錄

1. 判讀表 `liuzutanjing_L22_adjudication.json`（1 筆）：[10] 導言 READ run-onset=0.81。
2. 修正表 `liuzutanjing_L22_fix2.json`（14 筆）：[24]-[42] 經文讀／講解 READ（ASR 錨點）。
3. 修正表 `liuzutanjing_L22_fix3.json`（2 筆）：[25] end=294.31、[26] zero@294.31。
4. 修正表 `liuzutanjing_L22_fix4.json`（40 筆）：[44]-[83] 全部從 zero 改 READ（ASR 錨點）。
5. 修正表 `liuzutanjing_L22_fix5.json`（53 筆）：[84]-[136] 全部從 zero 改 READ（ASR 錨點）。
6. 修正表 `liuzutanjing_L22_fix6.json`（10 筆）：[97][100][110]-[112][121]-[123][129][131] early/fat/impossible 重錨。
7. 修正表 `liuzutanjing_L22_fix7.json`（3 筆）：[99] zero、[131] 1537.72-1567.83、[132] 1567.83。
8. 修正表 `liuzutanjing_L22_fix8.json`（1 筆）：[99] zero@952.97。
