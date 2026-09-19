# 壇經 L8（般若品第二·續）人工試聽清單

套用 milli-align skill 後：READ 85 / zero 12、鏈破口 0、verbatim 22 / fuzzy 63 / no-evidence 0。
請以 UI 逐段試聽——尤其 conf <0.8 者。

## 結構判定

```
書序：[0]-[3] 整章經文塊（zero@0.71-0.86，師父未在講首整讀）
     → [4] 導言（0.86-7.81）
     → [5] 經文引 zero → [6]-[7] 講解 READ
     → [8] 經文讀 → [9]-[14] 講解 READ
     → [15] 經文引 zero → [16]-[18] 講解 READ
     → [19] 經文引 zero → [20]-[35] 講解 READ
     → [36]-[52] 經文讀＋講解交替 READ
     → [53] 經文引 zero → [54]-[96] 講解 READ（鏈 pass 修 end）
```

## 需人工試聽

[53] 1047.29 zero：講解頭（如果自己悟了就不用向外求@1047.3-1050）行內語流歸 [54]；
1050-1080 為音樂段（ffmpeg ebur128 LRA 1.8 LU、無 -25dB 靜音、FunASR 全段無回傳結果）。

## 修正紀錄

1. 判讀表 `liuzutanjing_L8_adjudication.json`（1 筆）：[53] zero（音樂段證據）。
2. 其餘由 chain pass 修 end（53 個鏈破口 → 0）。
