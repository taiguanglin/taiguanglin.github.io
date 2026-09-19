# 壇經 L19（宣詔品第九）人工試聽清單

套用 milli-align skill 後：READ 150 / zero 17、鏈破口 0、no-evidence 6。
請以 UI 逐段試聽——尤其 conf <0.8 者。

## 結構判定

```
書序：[0]-[9] 整章經文塊（zero@0.97，師父未在講首整讀）
     → [10] 導言（0.97-17.00）
     → [11] 經文讀（17.50-21.20）→ [12] 講解（22.09-24.35）
     → [13] 經文讀（25.51-29.73）→ [14] 講解（30.01-41.01）
     → [15] 經文讀（41.01-44.95）→ [16]-[165] 講解 READ（鏈 pass 修 end）
     → [166] 收尾（1701.88-1703.03）
```

- whole-lecture ASR 在 13.65-46.0 有 hole（32s）；[11]-[15] 以 slice ASR（ffmpeg -ss 擷 9-34s）補證據。
- whole-lecture ASR 在 179.5-206.3 有 hole（27s）；[21] 尾部以 slice ASR 輔證。

## 需人工試聽

| 段 | span | conf | 內容 | 疑點 |
|----|------|------|------|------|
| [11] | 17.50-21.20 | 0.8 | 行思禅师，生吉州安城刘氏（經文讀） | no-evidence（whole-ASR hole；slice ASR 16.19-21.18 行思成师商西周安成刘氏） |
| [13] | 25.51-29.73 | 0.8 | 闻曹溪法席盛化，径来参礼（經文讀） | no-evidence（whole-ASR hole；slice ASR 25.51-29.73） |
| [15] | 41.01-44.95 | 0.75 | 遂问曰："当何所务，即不落阶级？"（經文讀） | no-evidence（whole-ASR hole；slice ASR 41.01-44.03 遂问问当何所恶 既不落阶机） |
| [166] | 1701.88-1703.03 | 1.0 | 这期就讲到这里。 | no-evidence（ASR 尾部無字，收尾語流） |

## 修正紀錄

1. 判讀表 `liuzutanjing_L19_adjudication.json`（1 筆）：[10] 導言 READ run-onset=0.97。
2. 修正表 `liuzutanjing_L19_fix2.json`（5 筆）：[10] end=17.00、[11] 17.50-21.20、[12] 22.09-24.35、[13] 25.51-29.73、[14] 30.01-39.81。
3. 修正表 `liuzutanjing_L19_fix3.json`（31 筆）：[15]-[45] 全部從 zero 改 READ（ASR 序列錨點）。
4. 修正表 `liuzutanjing_L19_fix4.json`（2 筆）：[20] end=179.41、[21] 179.41-217.35。
5. 教訓：ASR hole（32s、27s）以 slice ASR 補證據；[10] baseline span（0.97-393.07）是 chain pass 把 end 錨到 393.07 的錯誤結果。
