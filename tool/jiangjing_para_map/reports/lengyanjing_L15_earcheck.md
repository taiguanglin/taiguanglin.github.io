# 楞嚴經 L15 earcheck（毫秒級對齊）

- 講次：lengyanjing / lecture 15（《楞嚴經》第十五期：見性無還＋阿那律）
- 音檔：lengyanjing-15.opus（duration=1703.96s）
- 依據：`audio_map3/skills/milli-align/SKILL.md`；FunASR 字級證據（`/tmp/funasr_cache/lengyanjing/15.json`）
- 結果：READ 34 / zero 70、鏈破口 2、no-evidence 3、defect 76

## 已套用 fix

| 檔 | 筆數 | 內容 |
|----|------|------|
| 機械鏈修 | 33 | 全 READ 段 end=下一 READ start（書序） |
| fix | 2 | [0][5] ASR 序列錨點（0.87→49.61） |

## 剩餘 defect（documented）

- [0] impossible（41.18-49.61，語速 19.15）— 經文讀「阿难言：我虽识此见性无还」，位置以 ASR 序列錨點為準
- [1]-[4] SUTRA 零寬（46.73）— informational，講首經文塊 chunks
- [19] fat?（336.39-979.93，語速 0.25）— 講解「这位阿那律听了这个话之后…」長段
- [22] fat?（983.74-1294.44，語速 0.28）— 講解「，前面阿那律是阿罗汉的境界…」
- [24] fat?（1294.44-1434.57，語速 0.04）— 講解「那么下一句，」
- [21][25][28][31][33][36] SUTRA 零寬 — informational
- [23][26][29][30][32][34][35][37] zero 非 SUTRA 零寬且未標 zero — informational

## 邊界判讀備註

- L15 語序＝書序，無中斷插講
- [5] 導言（0.87-33.84）「《楞严经》第十五期…」歸講首
- [0] 經文讀（41.18-49.61）「阿难言：我虽识此见性无还」
