# 楞嚴經 L12 earcheck（毫秒級對齊）

- 講次：lengyanjing / lecture 12（《楞嚴經》第十二期：波斯匿王）
- 音檔：lengyanjing-12.opus（duration=1924.00s）
- 依據：`audio_map3/skills/milli-align/SKILL.md`；FunASR 字級證據（`/tmp/funasr_cache/lengyanjing/12.json`）
- 結果：READ 26 / zero 145、鏈破口 0、no-evidence 0、defect 147

## 已套用 fix

| 檔 | 筆數 | 內容 |
|----|------|------|
| 機械鏈修 | 24 | 全 READ 段 end=下一 READ start（書序） |
| fix | 2 | [16][17] ASR 序列錨點（372.91→376.98） |
| fix | 1 | [15] 邊界（372.91） |
| fix | 1 | [18] 邊界（376.98-1042.94） |

## 剩餘 defect（documented）

- [0][1] SUTRA 零寬（講首經文塊 chunks，0.82）— informational，經文塊由 chunks 呈現
- [16] fat?（372.91-374.44，語速 0.00）— 過渡「下一句，」
- [17] SUTRA 零寬（374.44）— informational，短經文引句「时波斯匿王起立白佛」
- [18]-[24] zero 寬段（1042.94）— informational
- [9] SUTRA 零寬（124.96）— informational
- [25] fat?（1042.94-1716.42，語速 0.01）— 講解「我们再往下看下一句，」
- [29]-[33] zero 寬段（1443.32）— informational
- [35]-[38] zero 寬段（1717.81）— informational

## 邊界判讀備註

- L12 語序＝書序，無中斷插講
- [16] 過渡「下一句，」歸前段，end＝下一 READ start
- [18] 講解（376.98-1042.94）「这个时候这位波斯匿王起来说话…」
