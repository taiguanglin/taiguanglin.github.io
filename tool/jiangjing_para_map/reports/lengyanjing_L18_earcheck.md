# 楞嚴經 L18 earcheck（毫秒級對齊）

- 講次：lengyanjing / lecture 18（《楞嚴經》第十八期：別業妄見＋同分妄見）
- 音檔：lengyanjing-18.opus（duration=1836.17s）
- 依據：`audio_map3/skills/milli-align/SKILL.md`；FunASR 字級證據（`/tmp/funasr_cache/lengyanjing/18.json`）
- 結果：READ 171 / zero 15、鏈破口 0、no-evidence 1、defect 17

## 已套用 fix

| 檔 | 筆數 | 內容 |
|----|------|------|
| 機械鏈修 | 166 | 全 READ 段 end=下一 READ start（書序） |
| fix | 6 | [8]-[13] ASR 序列錨點（0.43→111.19） |
| fix | 4 | [9]-[12] 邊界（27.51/40.36/55.64/72.13/93.94） |
| fix | 1 | [0] 導言（0.43-18.43） |
| fix | 3 | [161]-[163] 邊界（1572.04/1576.78/1580.12） |

## 剩餘 defect（documented）

- [1]-[7] SUTRA 零寬（講首經文塊 chunks，111.19）— informational，經文塊由 chunks 呈現
- [42] no-evidence（514.76-515.01）— 過渡「那么，」
- [53][61][81][111][140] SUTRA 零寬 — informational，短經文引句
- [60][150] zero 非 SUTRA 零寬且未標 zero — informational

## 邊界判讀備註

- L18 語序＝書序，無中斷插講
- [8] 導言（0.43-18.43）「《楞严经》第十八期…」歸講首
- [13] 經文讀（97.22-111.19）「阿难白佛言：世尊，必妙觉性非因非缘」
- [162] 講解（1572.04-1580.12）「其余小洲都分布在海上…」
