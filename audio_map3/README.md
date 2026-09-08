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
  start/end 可編輯（mm:ss.s）、▶ 播放該段、確認 checkbox。
- 快捷鍵：空白播放暫停、`S`/`E` 把目前播放時間設為焦點段的 start/end、
  時間欄位聚焦時 ←/→ ±2s、↑/↓ 切換焦點段；一般非輸入狀態 ←/→ 快退/快進 5s。
- 講次層級「reviewed」勾選表示整講校對完成。
- 儲存：GitHub PAT（Contents: Read and write）存回 `audio_map3/<series>.json`；另有「下載 JSON」備援。
  未儲存的修改自動留在 localStorage 草稿，下次載入同一系列會套用。

## 校對完成後

```bash
cd tool/books2ebook && python3 gen_all.py   # 重新注入段落時間到 ebook/
```
