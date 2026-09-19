# 壇經 L24（付囑品第十·三十六對）人工試聽清單

套用 milli-align skill 後：READ 140 / zero 50、鏈破口 0、no-evidence 0。
請以 UI 逐段試聽——尤其 conf <0.8 者。本講 baseline 有 131 個 zero 寬段（講解塊全零寬），
已以 ASR 序列錨點全部改 READ。

## 結構判定

```
書序：[0]-[9] 整章經文塊（zero@30.59-51.54，師父未在講首整讀）
     → [10] 導言（0.51-19.72）
     → [11]-[12] 經文讀／講解 READ
     → [13]-[15] 經文讀／講解 READ（ASR 錨點）→ [16]-[30] READ
     → [31] 經文讀 zero → [32]-[51] READ → [52]-[63] 經文讀／講解 READ
     → [64] 經文讀 zero → [65]-[86] READ → [87]-[179] READ
     → [180] 經文讀（1753.25-1761.17）→ [181]-[189] READ（鏈 pass 修 end）
```

導言 [10]（ASR《坛经》第二十四期@0.51-19.72）。

## 修正紀錄

1. 判讀表 `liuzutanjing_L24_adjudication.json`（3 筆）：[10]-[12] 導言／經文讀／講解（ASR 錨點）。
2. 修正表 `liuzutanjing_L24_fix2.json`（14 筆）：[50]-[64]（ASR 錨點）。
3. 修正表 `liuzutanjing_L24_fix3.json`（2 筆）：[50] end=366.80、[51] zero@366.80（INVERTED）。
4. 修正表 `liuzutanjing_L24_fix4.json`（19 筆）：[66]-[86]（ASR 錨點）。
5. 修正表 `liuzutanjing_L24_fix5.json`（3 筆）：[79] end=745.28、[80] 745.28-750.04、[86] 834.26-836。
6. 修正表 `liuzutanjing_L24_fix6.json`（91 筆）：[89]-[179]（ASR 錨點）。
7. 修正表 `liuzutanjing_L24_fix7.json`（5 筆）：[72][74][84][143][179] early/fat 重錨。
8. 修正表 `liuzutanjing_L24_fix8.json`（4 筆）：[142] end、[178] end、[179] 1709.71-1753.25、[180] 1753.25-1761.17。
9. 修正表 `liuzutanjing_L24_fix9.json`+`fix10.json`+`fix11.json`（7 筆）：[142]-[144] 鏈修正。
