# 楞嚴經 L16 earcheck（毫秒級對齊）

- 講次：lengyanjing / lecture 16（《楞嚴經》第十六期：見性無外＋方器圓器）
- 音檔：lengyanjing-16.opus（duration=1873.51s）
- 依據：`audio_map3/skills/milli-align/SKILL.md`；FunASR 字級證據（`/tmp/funasr_cache/lengyanjing/16.json`）
- 結果：READ 17 / zero 116、鏈破口 2、no-evidence 3、defect 124

## 已套用 fix

| 檔 | 筆數 | 內容 |
|----|------|------|
| 機械鏈修 | 15 | 全 READ 段 end=下一 READ start（書序） |
| fix | 3 | [0][7][8] ASR 序列錨點（0.59→74.01） |

## 剩餘 defect（documented）

- [0] impossible（46.54-74.01，語速 29.05）— 經文讀「佛告阿难：一切世间大小、内外」，位置以 ASR 序列錨點為準
- [1]-[6] SUTRA 零寬（50.00）— informational，講首經文塊 chunks
- [10] fat?（74.01-601.25，語速 0.14）— 講解「佛告诉阿难，世间大小内外…」長段
- [11] fat?（601.25-1079.35，語速 0.01）— 講解「接着佛说，」
- [14] fat?（1079.35-1466.54，語速 0.02）— 講解「接着看下一句，」
- [19] fat?（1466.54-1533.61，語速 0.07）— 講解「那么下一句，」
- [12][15][17][20][23] SUTRA 零寬 — informational
- [7][8][13][16][18][21][24] zero 非 SUTRA 零寬且未標 zero — informational

## 邊界判讀備註

- L16 語序＝書序，無中斷插講
- [7] 導言（0.59-43.24）「《楞严经》第十六期…」歸講首
- [8] 講解（44.04-46.54）「那么我们接着看七十一页的答案部分，原文，」
- [0] 經文讀（46.54-74.01）「佛告阿难：一切世间大小、内外」
