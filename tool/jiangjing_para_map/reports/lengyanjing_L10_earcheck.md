# 楞嚴經 L10 earcheck（毫秒級對齊）

- 講次：lengyanjing / lecture 10（《楞嚴經》第十期：十番顯見前段）
- 音檔：lengyanjing-10.opus（duration=1800.48s）
- 依據：`audio_map3/skills/milli-align/SKILL.md`；FunASR 字級證據（`/tmp/funasr_cache/lengyanjing/10.json`）
- 結果：READ 28 / zero 99、鏈破口 0、no-evidence 3、defect 111

## 已套用 fix

| 檔 | 筆數 | 內容 |
|----|------|------|
| 機械鏈修 | 28 | 全 READ 段 end=下一 READ start（書序） |
| fix | 10 | [0]-[9] ASR 序列錨點（12.94→670.73） |
| fix | 8 | [7]-[9] 邊界（54.85/73.24/644.89/669.00） |

## 剩餘 defect（documented）

- [0][3] SUTRA 零寬（12.94/19.58）— informational，講首經文塊 chunks
- [7] fat?（54.85-644.89，語速 0.13）— 講解「三昧——禅的意思…」長段
- [8] fat?（644.89-669.00，語速 0.21）— 講解「然后下一句…」
- [9]-[13] zero 寬段（913.85/1005.07）— informational，未念引句
- [10][22][27][28] ⚠ 頭 8 字逐字出現過（可能其實有念）— informational

## 邊界判讀備註

- L10 語序＝書序，無中斷插講
- [2] 導言（15.40-19.58）「《楞严经》第十期…」歸講首
- [5] 經文讀（27.21-33.75）「而白佛言：自我从佛发心出家」
- [7] 講解（54.85-73.24）「三昧——禅的意思…」
- [8] 講解（73.24-644.89）「然后下一句…」
