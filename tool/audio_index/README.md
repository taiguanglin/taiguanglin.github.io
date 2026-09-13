# audio_index — `audio/index.html` 產生器

掃描本機音檔庫 `/Users/paul/tai/audio/`（repo 內的 `audio` 是 symlink，未進 git），
產生該目錄的入口頁 `audio/index.html`：粉色系版面、置頂大悲咒播放器、類別／年份篩選。

## 版面（改樣板就好）

由上而下：

1. **黏頂標題列**：CSS 畫的蓮花印記、站名、音檔總數、回主站連結。
2. **大悲咒（置頂）**：西方三聖圖（**點圖即可播放／暫停**）＋ 一般版／快速版／兩版清單循環／停止，
   自訂進度條（已播比例填色、顯示 mm:ss）、音量（記住上次設定）、狀態列與提示。
3. **黏頂工具列**：類別下拉（原生 `<select>`，含 optgroup 分組與數量）＋ 關鍵字搜尋 ＋ 新→舊／舊→新。
4. **年份快篩**：`全部 426`、`2026（54）`… 一鍵縮小範圍；右側統計顯示 `顯示 N / 總數`。
5. **清單**：依「類別＋年月」分組，每列 ＝ 日期標籤 ＋ 標題（已去掉 `YYYY年M月D日` 前綴與 `.opus`）＋ 類別徽章 ＋ 原生播放器。
6. **底部正在播放條** 與右下「回大悲咒」快捷鈕（捲過大悲咒區塊才出現）。

篩選彼此可疊加；找不到結果時會顯示提示與「清除全部篩選」按鈕。
`prefers-reduced-motion` 會關閉過場動畫。

## 為什麼要產生

音檔庫會持續成長（答疑平放根目錄、講經放 `jiangjing/`、義理放 `yili/`），
手寫檔案清單一定會漏。本工具每次**遞迴掃描整個 `audio/`**，
任何 `*.opus` 都會自動出現在頁面上，不需要改 HTML。

## 檔案

| 檔案 | 角色 |
|------|------|
| `build_index.py` | 產生器：掃描 → 分類 → 渲染 → 寫回 `audio/index.html` |
| `index_template.html` | 樣板（版面、CSS、置頂大悲咒播放器與全部前端 JS） |

`build_index.py` 只覆寫樣板中的兩段程式碼（`const CATEGORIES = …` 與 `const FILES = […]`），
其餘 HTML/CSS/JS 原樣輸出；因此**版面要改就改樣板，不要改 `audio/index.html`**。
改樣板時必須保留：

- `const CATEGORIES = /*__CATEGORIES__*/…;` 與 `const FILES = [` … `\n];`（腳本的比對字串）。
- 播放器用到的 id：`dabeiAudio`、`dabeiAudioB`、`dabeiArtBtn`、`dabeiPlayBtn`、`dabeiSeek`、`dabeiTime`、
  `dabeiStatus`、`dabeiVolume`、`btnLoopNormal/Fast/Playlist`、`btnDabeiStop`、`totalCount`、`list`、`search`、
  `category`、`sortNewest/Oldest`、`stats`、`years`、`np`、`npTitle`、`npStop`、`jumpTop`。
- 大悲咒仍以「兩顆 `<audio>` 各載一首、關螢幕時切換播放」的方式接力，`DABEI` 的 `duration` 為檔案真實長度。

## 使用

```bash
python3 tool/audio_index/build_index.py            # 產生 audio/index.html
python3 tool/audio_index/build_index.py --dry-run  # 只印各類別數量與未分類檔案
```

新增音檔後（例如再轉一系列錄音）跑一次即可。

## 分類規則

| 類別 key | 顯示名稱 | 判斷方式 |
|----------|----------|----------|
| `dayi` / `tieba` / `weixin` / `guanwang` | 答疑 / 貼吧答疑 / 微信公眾號答疑 / 官網答疑 | 根目錄檔名關鍵字（`公眾號` 一律併入微信公眾號） |
| `lengqie`…`xinjing` | 楞伽經 / 六祖壇經 / 楞嚴經 / 四十二章經 / 感恩與講經 / 圓覺經 / 金剛經 / 心經 | `jiangjing/` 下檔名關鍵字（簡繁皆收） |
| `yili` | 義理 | `yili/` 目錄 |
| `other` | 其他 | 認不出來的檔案（會列在 stderr，請補規則） |

- 置頂大悲咒（`Tai師父大悲咒108遍.opus`、`Tai師父大悲咒快速版108遍.opus`）由頁面 featured 區塊處理，不列入清單。
- 新增類別時，同時改 `build_index.py` 的 `CATEGORIES`（含 `group`、`order`）與樣板的徽章樣式 `.badge.<cls>`。

## 部署注意

`audio/` 不在本 repo 的 git 內（見根 `AGENTS.md`），`audio/index.html` 屬於音檔庫那份 repo。
頁面上的音檔路徑一律相對 `audio/`（例如 `jiangjing/…opus`），
所以預覽時要從 `audio/` 目錄起服務：

```bash
cd ~/tai/audio && python3 serve.py --port 8080   # serve.py 支援 HTTP Range，拖曳進度條才正常
```
