# 楞嚴經 L21 earcheck（毫秒級對齊）

- 講次：lengyanjing / lecture 21（《楞嚴經》第二十一期：六入本如來藏）
- 音檔：lengyanjing-21.opus（duration=2033.26s）
- 依據：`audio_map3/skills/milli-align/SKILL.md`；FunASR 字級證據（`/tmp/funasr_cache/lengyanjing/21.json`）
- 結果：READ 45 / zero 165、鏈破口 0、no-evidence 1、defect 175

## 已套用 fix

| 檔 | 筆數 | 內容 |
|----|------|------|
| 機械鏈修 | 45 | 全 READ 段 end=下一 READ start（書序） |
| fix | 1 | [45] ASR 序列錨點（1443.50→1449.08） |

## 剩餘 defect（documented）

- [0]-[5] SUTRA 零寬（講首經文塊 chunks，0.97）— informational，經文塊由 chunks 呈現
- [20] fat?（306.37-559.91，語速 0.01）— 過渡「下一句，」
- [26] fat?（570.92-829.76，語速 0.08）— 經文讀「如是，阿难，当知是见非明、暗来」
- [28] SUTRA 零寬（806.72）— informational
- [31] SUTRA 零寬（873.90）— informational
- [32] fat?（873.90-1007.96，語速 0.19）— 講解「如果从暗相当中来…」
- [38] fat?（1067.87-1084.46，語速 0.18）— 過渡「下一句，」
- [43] fat?（1280.57-1436.55，語速 0.02）— 過渡「下一句，」
- [45] impossible（1443.50-1449.08，語速 25.53）— 講解「所以你应该知道眼入是虚妄的…」，位置以 ASR 序列錨點為準
- [48] SUTRA 零寬（1452.31）— informational
- [49] fat?（1452.31-1719.97，語速 0.38）— 講解「这个和前面的眼根是一样的逻辑…」

## 邊界判讀備註

- L21 語序＝書序，無中斷插講
- [45] 講解（1443.50-1449.08）「所以你应该知道眼入是虚妄的…」
