# wenda2_ebook_classified → wenda2_ebook 遷移計劃

## 目標

`wenda2_ebook_classified/`（Word + PDF 全分類合併版）正式取代 `wenda2_ebook/` 成為對外公開的電子書。
`audio_map1_sep/`（分類版音頻校對 UI）正式取代 `audio_map/` 成為主要的音頻校對工具。

## 前置認知

- `gen_classified.py` 需要讀取原始 Word 章（01-12）作為來源 → 來源不能丟
- `tool/word2ebook/gen_all.py` 產出的未分類版本是 gen_classified.py 的上游 → 產出路徑要改名
- `daily_quotes` 管線讀 `wenda2_ebook/search_index_trad.json` → 分類版的 search_index 結構不同（12章 vs 21章），需要驗證
- `world_model` 工具讀 `wenda2_ebook/` 的 HTML → 分類版章節結構不同

---

## Phase 1：目錄重新命名

```bash
# 1. 原始未分類版 → 改名為內部建置來源
mv wenda2_ebook wenda2_ebook_word

# 2. 分類合併版 → 升級為正式 wenda2_ebook
cp -r wenda2_ebook_classified wenda2_ebook

# 3. 原始 audio_map → 保留為舊版參考（不刪，因為 tool/word2ebook 還需要 data/audio_map/）
# audio_map/ 不刪，但不再是主要校對工具

# 4. audio_map1_sep → 升級為主要校對工具（不刪原目錄，audio_map/ 保留但不更新）
# 實際做法：audio_map1_sep/ 改名為 audio_map_v2/，audio_map/ 保持現狀
# 或者：直接把 audio_map/ 的 index.html + assets/ 指向新版本
```

### 建議的目錄結構（遷移後）

| 目錄 | 角色 |
|---|---|
| `wenda2_ebook/` | **正式上線版**（= 原 wenda2_ebook_classified，12 章全分類） |
| `wenda2_ebook_word/` | 內部建置來源（= 原 wenda2_ebook，12 Word 章 + 9 月度章） |
| `wenda2_ebook_sep/` | PDF 分類預覽（僅 13-21 章的分類條目，01-12 主題樹） |
| `audio_map/` | **主要校對工具**（= 原 audio_map1_sep，分類版音頻對齊） |
| `audio_map1_sep/` | 改名為 audio_map/ 後不再存在 |
| `tool/word2ebook/data/audio_map/` | 音頻映射 JSON SoT（不變） |

---

## Phase 2：產生器路徑更新

### 2a. tool/word2ebook/gen_all.py
```python
# 輸出到 wenda2_ebook_word（不再直接輸出到 wenda2_ebook）
OUTPUT_FOLDER = REPO_ROOT / "wenda2_ebook_word"
```

### 2b. tool/qa_split_ebook/gen_classified.py
```python
# 來源：從 wenda2_ebook_word 讀取原始 Word 章
SRC = ROOT / "wenda2_ebook_word"
# 輸出：到 wenda2_ebook（正式版）
DST = ROOT / "wenda2_ebook"
```

### 2c. tool/qa_split_ebook/extract.py
```python
# 讀取來源改為 wenda2_ebook_word/13-21.html
SRC = ROOT / "wenda2_ebook_word"
```

### 2d. tool/qa_split_ebook/sync_audio_map.py
```python
DST = ROOT / "audio_map"  # 原本寫 audio_map1_sep，改回 audio_map
```

---

## Phase 3：全站參照更新

### 3a. 根目錄 HTML

| 檔案 | 修改 |
|---|---|
| `index.html` | `wenda2_ebook/index_trad.html` 連結不變（目錄名相同）|
| `wenda2.html` | 同上 |
| `sitemap.xml` | URL 結構不變（`/wenda2_ebook/01.html` 等），但章節數從 21 減為 12 → 需重新產生或手動移除 13-21 的 URL |
| `robots.txt` | `Disallow: /audio_map/` 保留（新版取代舊版後仍是內部工具）|
| `manifest.webmanifest` | `start_url` 不變 |
| `sw.js` | 快取路徑 `/(wenda2_ebook|ebook)` 不變 |
| `lang-switch.js` | `EBOOK_DIRS` 簡化為 `['/wenda2_ebook/', '/ebook/']`（wenda2_ebook_classified 不再存在）|

### 3b. wenda2/ 手工TOC頁

12 個 `wenda2/chapter-*.html` 檔案中的 `../wenda2_ebook/NN_trad.html` 連結：
- NN = 01-12 → **連結目標正確**（分類版也是 01-12 章）→ 不需改
- 但每章的內容含義變了（分類版 01 = Word 01 + PDF 分類到 01）→ 語意上仍然正確

### 3c. stories/*.html

`../wenda2_ebook/index_trad.html` 連結 → 目錄名不變，**不需改**。

### 3d. .gitignore

```
# 舊版
/wenda2_ebook_sep/
/wenda2_ebook_classified/

# 新版
/wenda2_ebook_sep/
/wenda2_ebook_word/    # 新增：內部建置來源
```

### 3e. audio_map 校對工具

| 項目 | 修改 |
|---|---|
| `audio_map1_sep/assets/editor.js` 行493 | `audio_map1_sep/${month}.json` → `audio_map/${month}.json` |
| `audio_map1_sep/index.html` | robots meta 已有 noindex ✓ |
| `audio_map1_sep/qid_to_sep_chapter.json` | 檔案跟著目錄改名，不需改內容 |

### 3f. tool/site_chrome/check_site.py

```python
# NOINDEX_PAGES: 改 audio_map1_sep → audio_map（目錄名回復）
"audio_map/index.html",
# ROBOTS_TXT_DISALLOW: 同上
"/audio_map/",
```

---

## Phase 4：下游工具更新

### 4a. tool/daily_quotes/

`build_quotes.py` 讀 `wenda2_ebook/search_index_trad.json`：
- 新版 wenda2_ebook 的 search_index 章節數不同（12 vs 21）
- **影響**：候選池的文字和 URL 會變（因為分類版把 PDF 條目分散到 01-12 章）
- **動作**：重跑 `build_quotes.py` → `select_1095.py` → `audit_quotes.py` 產生新的每日精選
- ⚠️ `candidates_sample.json` 的 idx 對應會失效 → 需要重新抽樣評分（或保持舊 candidates.json 不動，只在下次大改時重跑）

### 4b. tool/world_model/

`extract_corpus.py` 讀 `wenda2_ebook/[0-9][0-9]_trad.html`：
- 舊版有 01-21 章，新版只有 01-12 章
- **影響**：抽取的段落 ID 和 URL 會變
- **動作**：下次需要重建世界模型圖時重跑管線

### 4c. tool/audio_map/ 相關

`audio_map/assets/editor.js` 讀 `tool/word2ebook/data/audio_map/*.json`：
- 這是 JSON SoT，不隨目錄改名而變
- **不需修改**

---

## Phase 5：執行順序

```bash
# 1. 改名原始版
mv wenda2_ebook wenda2_ebook_word

# 2. 複製分類版為正式版
cp -r wenda2_ebook_classified wenda2_ebook

# 3. 更新產生器路徑（Phase 2）

# 4. 更新全站參照（Phase 3）

# 5. 舊的 audio_map/ 內容不刪（歷史校對資料），但主 index.html 加提示指向新版
#    或者：audio_map1_sep/ 直接改名為 audio_map/（覆蓋舊版）
#    → 建議：改名覆蓊，因為舊版 audio_map/ 的校對資料已全部完成（report 顯示 matched 333/333）

# 6. 驗證
tool/word_audio_map2/.venv/bin/python tool/site_chrome/check_site.py

# 7. Git commit
git add :/
git commit -m "Migrate: wenda2_ebook_classified → wenda2_ebook (all-classified), audio_map1_sep → audio_map"
```

---

## Phase 6：驗證清單

- [ ] `wenda2_ebook/` 有 12 章 × 2 語言 = 26 HTML + index × 2 + search_index × 2
- [ ] `wenda2_ebook/` 總問答數 = 9,242
- [ ] 所有 `../wenda2_ebook/` 連結可達
- [ ] sitemap.xml 只列 01-12 章
- [ ] robots.txt 正確 Disallow 內部工具
- [ ] check_site.py 全綠
- [ ] audio_map/ 校對工具可載入 JSON
- [ ] daily_quotes 管線可跑（或標記為需重跑）
- [ ] lang-switch.js 繁簡切換正常
- [ ] sw.js 快取正常

---

## 風險評估

| 風險 | 等級 | 緩解 |
|---|---|---|
| 外部已分享的 wenda2_ebook/13-21.html 連結失效 | 高 | 可加 301 redirect 或保留舊章節為空殼 |
| daily_quotes 候選池結構改變 | 中 | 保持舊 candidates.json，下次大改時重跑 |
| search_index 章節 ID 改變影響「每日精選」錨點 | 中 | audit_quotes.py 會抓到斷鏈 |
| gen_classified.py 讀不到 wenda2_ebook_word/ | 低 | 確認路徑改好後測試 |
| wenda2_ebook_sep/ 的 qid_to_sep_chapter.json 路徑失效 | 低 | gen_classified.py 會重建 |
