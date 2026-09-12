# audio_index — `audio/index.html` 產生器

掃描本機音檔庫 `/Users/paul/tai/audio/`（repo 內的 `audio` 是 symlink，未進 git），
產生該目錄的入口頁 `audio/index.html`：粉色系版面、置頂大悲咒播放器、類別下拉篩選。

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
