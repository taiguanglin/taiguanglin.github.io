# 壇經 L20（護法品第九？）人工試聽清單

套用 milli-align skill 後：READ 138 / zero 19、鏈破口 0、no-evidence 0。
請以 UI 逐段試聽——尤其 conf <0.8 者。

## 結構判定

```
書序：[0]-[7] 整章經文塊（zero@28.46，師父未在講首整讀）
     → [8] 導言（1.39-14.35）
     → [9] 經文引 zero → [10]-[156] 經文讀／講解 READ（鏈 pass 修 end）
```

導言 [8] 重錨到 1.39-14.35（ASR《坛经》第二十期@1.39）。

## 需人工試聽

| 段 | span | conf | 內容 | 疑點 |
|----|------|------|------|------|
| [52] | 502.75-504.27 | 0.8 | 隍具述前缘。（經文讀） | no-evidence→0；ASR「防技术前人」＝隍具述前缘 同音錯字；baseline span 502.60-503.95 |

## 修正紀錄

1. 判讀表 `liuzutanjing_L20_adjudication.json`（1 筆）：[8] 導言 READ run-onset=1.39。
2. 修正表 `liuzutanjing_L20_fix2.json`（2 筆）：[52] start=502.75 end=504.27（經文讀重錨）、[53] start=504.27。
3. 其餘由 chain pass 修 end（65 個鏈破口 → 0）。
