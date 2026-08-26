# audio_map2 — 時間序 Word 音檔 Mapping 審核 UI

> Repo-wide rules: [`../AGENTS.md`](../AGENTS.md)。
> 產生器／規則：[`../tool/word_audio_map2/README.md`](../tool/word_audio_map2/README.md)。

## 這是什麼

`index.html` 審核「**時間順序版 Word 彙總**」對音檔的 mapping 結果
（2024-02 … 2025-05，共 14 個月份 JSON 放在本資料夾）。

- **JSON 內所有文字（問題／回答／提問人／開收場）來自 Word 檔**；
  SRT 只用來取播放起訖與 `srt_preview` 對照 —— 不是校對稿。
- 完全不參考 `audio_map_word/word-*.json` 的時間。

## 使用

本機需走 http server（fetch 相對路徑）：

```bash
python3 -m http.server -d /Users/paul/tai/taiguanglin.github.io 8000
# → http://localhost:8000/audio_map2/
```

操作：左側選月份 → session；卡片 ▶ 播放該段（`../audio/*.opus`）；
過濾器可只看 ⚠低信心／插補／待人工／缺時間。快捷鍵 `P` 播放暫停、`↑↓` 段落導覽。

## 卡片顏色

| 樣式 | 意義 |
|------|------|
| 紅框整卡 | confidence < 0.5，需特別仔細聽 |
| 徽章 高/中/⚠低信心 | ≥0.8 / 0.5–0.8 / <0.5 |
| notes: 待人工確認 | 找不到逐字音檔對應，時間為比例夾入 —— 用「待人工」過濾鍵集中審 |
| 雙檔合併時間軸 | 該日音檔分（上）（下）或文字檔未分段，UI 自動換檔播放 |

## 特別注意的月份

- **2024-02 … 2024-08**：當期音檔是主題式講解（未逐題念問題），且 ASR 品質差，
  「待人工」比例高 —— 每段都要人工聽檔確認／修正。
- **2024-11 之後**：有逐題念名＋`师父说` 開收場標記，mapping 品質高，抽查即可；
  少數待人工段多半是問題以圖片提交或朗讀順序與 Word 不同。
- `2025-03-12`、`2024-12-09`：合併時間軸特例（見 tool README）。

重新產生 JSON：`tool/word_audio_map2/build_maps.py --all --apply`
（會覆蓋本資料夾的月份 JSON；手動修正請改在 UI 匯出或另存，勿直接依賴重跑保留）。
