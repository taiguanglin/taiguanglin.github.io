# 楞嚴經 L17 earcheck（毫秒級對齊）

- 講次：lengyanjing / lecture 17（《楞嚴經》第十七期：見性超勤）
- 音檔：lengyanjing-17.opus（duration=1911.96s）
- 依據：`audio_map3/skills/milli-align/SKILL.md`；FunASR 字級證據（`/tmp/funasr_cache/lengyanjing/17.json`）
- 結果：READ 72 / zero 84、鏈破口 0、no-evidence 1、defect 92

## 已套用 fix

| 檔 | 筆數 | 內容 |
|----|------|------|
| 機械鏈修 | 70 | 全 READ 段 end=下一 READ start（書序） |
| fix | 2 | [55][63] ASR 序列錨點（832.64→842.27） |
| fix | 6 | [55]-[61] 邊界（832.64/835.44/1013.40） |
| fix | 2 | [62][63] 邊界（1013.40/1016.68/1190.37） |

## 剩餘 defect（documented）

- [0]-[7] SUTRA 零寬（講首經文塊 chunks，0.63）— informational，經文塊由 chunks 呈現
- [13][14] SUTRA 零寬（146.18）— informational
- [16] no-evidence（185.91-186.65）— 過渡「他问的是，」
- [27] SUTRA 零寬（323.59）— informational
- [50] SUTRA 零寬（676.72）— informational
- [55] fat?（832.64-835.44，語速 0.02）— 過渡「下一句，」
- [56]-[61] zero 寬段（1013.40）— informational，未念引句
- [62] fat?（1013.40-1016.68，語速 0.03）— 過渡「然后再下一句，」
- [63] 經文讀（1016.68-1190.37）「是以汝今观见与尘」
- [64] zero 非 SUTRA 零寬且未標 zero — informational

## 邊界判讀備註

- L17 語序＝書序，無中斷插講
- [55] 過渡「下一句，」歸前段
- [63] 經文讀（1016.68-1190.37）「是以汝今观见与尘」
