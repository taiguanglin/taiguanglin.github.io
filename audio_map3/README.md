# audio_map3 — 講經電子書「段落 ↔ 音檔時間」校對 UI

仿 audio_map / audio_map2 的人工校對工具，服務對象是 `ebook/` 講經系列
（感恩與講經、四十二章經、楞伽經、六祖壇經、楞嚴經）的「段落跟播」功能。

## 資料

- JSON SoT：`audio_map3/<series>.json`（series ∈ `ganen / sishierzhang / lengqie / liuzutanjing / lengyanjing`），
  由 `tool/jiangjing_para_map/build_maps.py` 產生（SRT ↔ 段落對齊；重跑保留 `confirmed` 段落與 `reviewed` 講次）。
- 結構：`lectures.{N}.paragraphs[] = {pid, text, start, end, conf, method, confirmed}`；講層 `reviewed`、`audio`、`duration`。
- 注入：`tool/books2ebook/para_audio_map.py` 在建置時把 start/end 寫進段落元素的 `data-start`/`data-end`，
  前端 `09b-para-track.js`（跟播 toggle / 高亮捲動 / 點段落即播 / 段末自停）依此運作。

## 使用

```bash
cd <repo root> && python3 -m http.server 8931   # 或 audio/serve.py（需 Range 支援以拖動音檔）
# 開 http://127.0.0.1:8931/audio_map3/
```

- 系列分頁 → 講次選擇（顯示確認進度）；段落卡片含信心著色（綠 ≥0.8 / 黃 0.5–0.8 / 紅 <0.5 或 miss）、
  start/end 可編輯（mm:ss.s）、▶ 播放該段、確認 checkbox，右上角另有「零長度」checkbox。
- 「設定」中可切換：手動輸入修改某段起訖時間時，是否自動同步上一段的結束／下一段的起始
  （預設開啟；關閉後手動輸入只改該段自己的時間，允許前後段重疊或留縫；同步時會自動穿越
  中間勾了「零長度」的段落，直接連到再上一段／下一段）。
- 段落卡片右上角的「零長度」checkbox：勾選＝此段音檔長度為零（師父沒念這段，多半是
  不念誦的經文段）。勾選後起訖時間強制相等（原起始值為錨點）、時間欄位鎖定唯讀、
  卡片淡化並禁止點播；調整前一段的結束或後一段的起始時，此段的邊界永遠自動吸附，
  且連續多個零長度段可一次穿越。資料寫回 JSON 段落的 `"zero": true` 欄位；電子書注入
  （`tool/books2ebook/para_audio_map.py`）遇到 `zero: true` 直接跳過，行為與零寬段相同
  （不可點播、不跟播）。
- 快捷鍵：空白播放暫停、`S`/`E` 把目前播放時間設為焦點段的 start/end、
  時間欄位聚焦時 ←/→ ±2s、↑/↓ 切換焦點段；一般非輸入狀態 ←/→ 快退/快進 5s。
- 跳瀏工具列（topbar 左側常駐，不佔段落欄位空間）：「⤒ 下一個未確認」「⤓ 下一個已確認」按鈕循環
  捲動定位到下一個未聽／已聽過的段落（只定位，不播放、不更新「最後播放」）；右鍵／長按＝定位並播放
  （會寫入「最後播放」）；快捷鍵 `N`＝定位下一個未確認、`Shift`+`N`＝定位下一個已確認；
  徽章顯示本講剩餘未確認段數（與側邊欄統計一致：開場不計入，只算正文段落＋收場，跳瀏掃描也不會落在開場上）。
- 講次層級「reviewed」勾選表示整講校對完成。
- 儲存：GitHub PAT（Contents: Read and write）存回 `audio_map3/<series>.json`；另有「下載 JSON」備援。
  未儲存的修改自動留在 localStorage 草稿，下次載入同一系列會套用。

## 校對完成後

```bash
cd tool/books2ebook && python3 gen_all.py   # 重新注入段落時間到 ebook/
```
