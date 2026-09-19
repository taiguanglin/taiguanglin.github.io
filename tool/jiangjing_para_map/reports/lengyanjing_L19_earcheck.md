# 楞嚴經 L19 earcheck（毫秒級對齊）

- 講次：lengyanjing / lecture 19（《楞嚴經》第十九期：別業妄見＋同分妄見）
- 音檔：lengyanjing-19.opus（duration=1925.06s）
- 依據：`audio_map3/skills/milli-align/SKILL.md`；FunASR 字級證據（`/tmp/funasr_cache/lengyanjing/19.json`）
- 結果：READ 44 / zero 146、鏈破口 2、no-evidence 3、defect 163

## 已套用 fix

| 檔 | 筆數 | 內容 |
|----|------|------|
| 機械鏈修 | 42 | 全 READ 段 end=下一 READ start（書序） |
| fix | 2 | [7][8] ASR 序列錨點（0.97→16.99） |

## 剩餘 defect（documented）

- [0] impossible（16.99-18.67）— 經文讀「阿难，吾今为汝以此二事进退合明」，位置以 ASR 序列錨點為準
- [1]-[6] SUTRA 零寬（18.67）— informational，講首經文塊 chunks
- [32] fat?（257.54-441.95，語速 0.29）— 講解「觉知道你的见生了病…」長段
- [33] fat?（441.95-579.71，語速 0.04）— 過渡「接着再下一句，」
- [39] fat?（579.71-831.99，語速 0.03）— 過渡「那么再看下一句，」
- [34][40][43] SUTRA 零寬 — informational
- [35]-[38][41][42] zero 非 SUTRA 零寬且未標 zero — informational

## 邊界判讀備註

- L19 語序＝書序，無中斷插講
- [7] 導言（0.97-14.95）「《楞严经》第十九期…」歸講首
- [8] 經文讀（14.95-16.99）「阿难，吾今为汝以此二事进退合明」
- [0] 經文讀（16.99-18.67）「阿难，吾今为汝以此二事进退合明。阿难，如彼众生别业妄见」
