# 壇經 L13（坐禪品第五）人工試聽清單

套用 milli-align skill 後：READ 81 / zero 30、鏈破口 0、no-evidence 0。
請以 UI 逐段試聽——尤其 conf <0.8 者。

## 結構判定

```
書序：[0]-[4] 整章經文塊（zero@1.21，師父未在講首整讀）
     → [5] 導言（1.21-14.56）
     → [6] 經文引 zero → [7]-[110] 經文讀／講解 READ（鏈 pass 修 end）
```

## 需人工試聽

| 段 | span | conf | 內容 | 疑點 |
|----|------|------|------|------|
| [65] | 979.49-985.40 | 0.8 | 三慧香，自心无碍…（經文讀） | baseline span 僅 1.25s（978.35-979.60），重錨後 5.9s；前有 1.7s 停頓 |

## 修正紀錄

1. 修正表 `liuzutanjing_L13_fix2.json`（2 筆）：[65] start=979.49 end=985.40（經文讀重錨）、[66] start=985.40。
2. 判讀表 `liuzutanjing_L13_adjudication.json`（1 筆）：[5] 導言 READ run-onset=1.21。
3. 其餘由 chain pass 修 end（37 個鏈破口 → 0）。
