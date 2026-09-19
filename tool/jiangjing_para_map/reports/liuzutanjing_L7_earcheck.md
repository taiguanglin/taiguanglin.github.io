# 壇經 L7（般若品第二·續）人工試聽清單

套用 milli-align skill 後：READ 68 / zero 29、鏈破口 0、no-evidence 1（[84]，ASR hole）。
請以 UI（audio_map3/index.html）逐段試聽以下段落——尤其 conf <0.8 者。

## 結構判定

```
書序：[0]-[10] 整章經文塊（zero@0.56，師父未在講首整讀）
     → [11] 導言（0.56-22.13）
     → [12] 經文引 zero → [13]-[14] 講解 READ
     → [15]-[18] zero（122.5-154.5 為音樂 ASR hole；176.3-178.3 行內念經歸 [19]）
     → [19]-[96] 講解 READ（鏈 pass 修 end）
```

- [15]-[18] 為零寬：122.48-154.46 經 ffmpeg volumedetect/silencedetect 確認為**音樂**（mean −10.7 dB、LRA 2.5 LU、無靜音段，FunASR 全段無回傳結果）——師父未口述。
- [18] 經文「世人愚迷，不見般若」在 176.3-178.3 行內念出，歸 [19] 語流（鏈 pass）。
- [84] 經文讀由 slice ASR 確認（whole-lecture ASR 在 1648.3-1654.0 有 hole）。

## 需人工試聽（conf <0.8）

| 段 | span | conf | 內容 | 疑點 |
|----|------|------|------|------|
| [20] | 221.09-227.19 | 0.8 | 般若无形相，智慧心即是…（經文讀） | 跨度 6s |
| [49] | 825.08-833.94 | 0.8 | 譬如大龙下雨于阎浮提…（經文讀） | |
| [84] | 1650.70-1658.50 | 0.85 | 善知识！一切修多罗及诸文字…（經文讀） | no-evidence（whole-ASR hole 1648.3-1654.0；slice ASR 確認 1650.72-1658.3） |
| [85] | 1658.50-1679.93 | 0.7 | "修多罗"是契经的意思… | ASR 嚴重亂碼（修道罗就是气经的 嗯 就是金啊 铂经契经@1658.5-1666.8）；weak-pinyin |

## 導言

[11] 0.56-22.13（ASR《坛经》第七期@0.56）。

## 修正紀錄

1. 判讀表 `liuzutanjing_L7_adjudication.json`（5 筆）：[11] READ、[15]-[18] zero（音樂 hole）。
2. 修正表 `liuzutanjing_L7_fix2.json`（2 筆）：[84] start=1650.70 READ（slice ASR 證據）、[85] start=1658.50 conf 0.7。
3. 教訓：whole-lecture ASR hole 可用 slice ASR（ffmpeg -ss 擷 40s → transcribe.py）補證據；音樂段以 LRA<3 LU + 無靜音 + FunASR 無回傳判定。
