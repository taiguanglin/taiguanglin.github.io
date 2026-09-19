# 楞嚴經 L9 earcheck（毫秒級對齊）

- 講次：lengyanjing / lecture 9（《楞嚴經》第九期：奢摩他路＋光明拳）
- 音檔：lengyanjing-09.opus（duration=2018.44s）
- 依據：`audio_map3/skills/milli-align/SKILL.md`；FunASR 字級證據（`/tmp/funasr_cache/lengyanjing/9.json`）
- 結果：READ 124 / zero 8、鏈破口 0、no-evidence 1、defect 10

## 已套用 fix

| 檔 | 筆數 | 內容 |
|----|------|------|
| 機械鏈修 | 112 | 全 READ 段 end=下一 READ start（書序） |
| fix | 16 | [12]-[26] ASR 序列錨點（148.56→291.95） |
| fix | 2 | [14][15] 邊界（164.01/165.00/166.57） |
| fix | 2 | [15][27] 邊界（164.01/291.95-321.76） |

## 剩餘 defect（documented）

- [0]-[2] SUTRA 零寬（講首經文塊 chunks，1.05/1.20）— informational，經文塊由 chunks 呈現
- [37] SUTRA 零寬（507.84）— informational，短經文引句「惑汝真性」
- [45] no-evidence（532.62-533.41）— 經文讀「故受轮转」
- [66] SUTRA 零寬（804.57）— informational，短經文引句
- [72] SUTRA 零寬（894.39）— informational，短經文引句
- [85] fat?（1168.98-1201.40，語速 0.49）— 經文讀「如汝今者，承听我法」，位置以 ASR 序列錨點為準
- [86][87] zero 非 SUTRA 零寬且未標 zero（1180.56）— informational

## 邊界判讀備註

- L9 語序＝書序，無中斷插講
- [12] 講解（148.56-158.27）「阿难说，我与大众…」
- [14] 經文讀（164.01-165.00）「佛告阿难：汝今答我，」歸導言之後第一段
- [15] 講解（165.00-166.57）「你现在回答我」
- [16] 經文讀（166.57-174.35）「如来屈指为光明拳」
