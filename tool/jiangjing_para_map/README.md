# jiangjing_para_map — 講經電子書段落 ↔ 音檔時間軸對齊

把講經系列電子書（`ebook/04、07、08、09、10.html`）每一個段落
（`<p class="para-block" id="p-sXXXXXXXX">` 與 `<div class="sutra-text para-block">`）
對齊到該講音檔的時間軸，輸出 JSON（`audio_map3/<series>.json`），
供人工校對 UI 與電子書播放鈕注入使用。

## 輸入

| 來源 | 路徑 |
|------|------|
| 電子書 | `ebook/04|07|08|09|10.html`（h2 播放鈕 `data-audio` 對應音檔 basename） |
| 音檔 | `/Users/paul/tai/audio/jiangjing/<basename>.opus`（ffprobe 讀時長，可缺） |
| 字幕 | `/Users/paul/tai/audio/srt/jiangjing/<basename>.srt`（**缺檔直接跳過該講**，可重跑補） |
| 系列↔講次↔basename | `tool/books2ebook/audio_map.py` 的 `AUDIO_MAP` |

五系列：`ganen`(1講） / `sishierzhang`(14) / `lengqie`(42) / `liuzutanjing`(27) / `lengyanjing`(21，含楞严咒長咒語段落）。

## 對齊原理

1. 解析 SRT cues → `(start, end, text)`。
2. 正規化：去標點/空白，繁→簡（可選 `opencc`，`OpenCC('t2s')`；缺套件自動略過，
   不硬依賴）；雙邊再去口語助詞（啊呀吧嗯呃…）以抵擋 ASR 灌水。
3. 把 cues 正規化文字串成「字元時間流」，cue 內每個字元線性插值出時間戳。
4. 每個段落（依序）取正規化文本的 0/¼/½/¾ 處各 20 字作 needle（取最佳），
   以 2/3-gram 索引在「前一段對齊位置之後」的字元流蒐候選位置，
   另加游標後 1200 字的密集掃描補漏；評分取
   `max(difflib 字元比率, bigram Dice)`（Dice 對 ASR 同音錯字抗性較強），
   method=`ngram`，conf=分數，門檻 0.5。
5. 單調約束：段落 start 非遞減。匹配失敗 → method=`miss`（conf=0）；
   <4 正規化字 → method=`short`（conf=0.15）。miss/short 段落不硬塞時間，
   而是在前後錨點之間按正規化字數比例**插值**（錨點段落先保留自己的字數份額，
   避免零寬度時間區間）。
6. `start = 匹配時間 − 0.3s`（不為負）；`end = 下一段 start`；
   末段 `end = 音檔時長`（ffprobe → h2 鈕 `data-end` → SRT 末 cue +1s）。

## 用法

```bash
cd tool/jiangjing_para_map
python3 build_maps.py                          # 全部五系列
python3 build_maps.py --series lengqie          # 單一系列
python3 build_maps.py --series lengqie --lecture 15
python3 build_maps.py --dry-run                 # 只印報表不寫檔
python3 build_maps.py --series ganen -v         # 另印前 20 段書↔SRT 對照
python3 build_maps.py --srt-dir /path/to/srt    # 改用其他 SRT 目錄
```

每講印出 `paras / avg_conf / high / mid / low` 統計。

只需 Python 3 標準庫（opencc 可選）。

## 輸出格式（`audio_map3/<series>.json`，UTF-8，`ensure_ascii=False`）

```json
{
  "series": "lengqie",
  "book_number": 8,
  "generated_at": "<iso8601>",
  "lectures": {
    "15": {
      "audio": "2025年1月15日Tai师父讲经·楞伽经(15).opus",
      "title": "楞伽经（15）",
      "duration": 4800.1,
      "reviewed": false,
      "paragraphs": [
        {"pid": "p-s30de4342", "text": "…", "start": 0.0, "end": 25.3,
         "conf": 0.91, "method": "ngram", "confirmed": false}
      ]
    }
  }
}
```

- `conf ≥ 0.8` 視為高可信，`0.5–0.8` 中，`< 0.5`（含 `miss`/`short`）需人工校對。
- **重跑安全**：已存在 JSON 中 `confirmed=true` 的段落保留其 `start/end`
  （人工校對結果不被覆寫）；講層級 `reviewed` 亦保留。
- SRT 缺檔的講次整講跳過：報表列出 skipped 清單；若舊 JSON 已有該講資料則保留不動。

## 驗證記錄（105 講全量跑完）

| 系列 | 講數 | 段數 | 高(≥0.8) | 中 | 低(<0.5) |
|------|-----|------|------|----|------|
| ganen | 1 | 81 | 95% | 2% | 2% |
| sishierzhang | 14 | 1006 | 46% | 17% | 37% |
| lengqie | 42 | 4265 | 6% | 11% | 84%（見下） |
| liuzutanjing | 27 | 3636 | 4% | 8% | 88% |
| lengyanjing | 21 | 2784 | 7% | 5% | 88% |

- ganen 逐段抽查：前 10 段 start/end 與 SRT cue 內容一致（書↔音逐句對得上），
  avg_conf 0.89；時間軸單調、無零寬、末段 end == 音檔時長。
- sishierzhang / lengqie#1 抽查同樣成立（書面語句 conf 常 ≥0.85）。
- **品質上限由 ASR 決定**：楞伽/壇經/楞嚴的 SRT 對經文朗誦產生大量同音錯字
  （如「楞伽」→「浪桀」、「世尊于七日住摩竭海中」→「之以七日作摩羯海中」），
  文言經文與快速帶讀段落無法穩定對齊（整段全檔掃描 bigram-Dice 也僅 0.2–0.3）。
  這些講次的低 conf 段落已按正規化字數在錨點間插值、標低 conf 供人工校對；
  根本改善需以 `tool/sense_voice/` 重新轉寫後重跑本工具。
