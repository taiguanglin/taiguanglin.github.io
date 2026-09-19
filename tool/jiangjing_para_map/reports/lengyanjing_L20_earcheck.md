# 楞嚴經 L20 earcheck（毫秒級對齊）

- 講次：lengyanjing / lecture 20（《楞嚴經》第二十期：五陰妄想）
- 音檔：lengyanjing-20.opus（duration=1820.57s）
- 依據：`audio_map3/skills/milli-align/SKILL.md`；FunASR 字級證據（`/tmp/funasr_cache/lengyanjing/20.json`）
- 結果：READ 50 / zero 119、鏈破口 0、no-evidence 3、defect 128

## 已套用 fix

| 檔 | 筆數 | 內容 |
|----|------|------|
| 機械鏈修 | 50 | 全 READ 段 end=下一 READ start（書序） |
| fix | 1 | [43] ASR 序列錨點（1078.94→1085.30） |
| fix | 1 | [44] 邊界（1085.30） |

## 剩餘 defect（documented）

- [0]-[4] SUTRA 零寬（講首經文塊 chunks，0.99）— informational，經文塊由 chunks 呈現
- [33] fat?（463.92-899.75，語速 0.07）— 講解「阿难，狂花，虚空中产生的这些个狂花…」長段
- [42] fat?（900.82-1078.94，語速 0.22）— 講解「就像你阿难的身体…」
- [43] impossible（1078.94-1085.30，語速 15.13）— 講解「那么在这里我们要知道…」，位置以 ASR 序列錨點為準
- [44] fat?（1085.30-1628.23，語速 0.01）— 講解「我们接着看下一句，」
- [35][37][39][41][45][48][50] SUTRA 零寬 — informational
- [36][38][40][46][49] zero 非 SUTRA 零寬且未標 zero — informational

## 邊界判讀備註

- L20 語序＝書序，無中斷插講
- [43] 講解（1078.94-1085.30）「那么在这里我们要知道…」
- [44] 講解（1085.30-1628.23）「我们接着看下一句，」
