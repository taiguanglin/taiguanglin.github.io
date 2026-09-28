# tool/ — 工具與產生器目錄指南

> 每個工具的詳細規則、指令與資料流，以**該工具自己的 README / AGENTS.md** 為準（見下方表格「Docs」欄）。
> 這份文件只記錄「還有哪些工具、各自做什麼、誰依賴誰」，避免與各工具文件重複。

---

## 目錄總覽

| 工具 | 做什麼 | 輸入 → 輸出 | Docs |
|------|--------|-------------|------|
| `tool/word2ebook/` | 問答錄 2 電子書產生器（Word + 月 PDF）。前 12 章（Word 分類）播放鈕由 `audio_map2/*.json` 注入；13–21 章（PDF）播放鈕由 `data/audio_map/*.json` 注入。 | `問答錄2/*.docx` + `*.pdf` → `wenda2_ebook/` | **`AGENTS.md`**, `README.md`, `openspec/` |
| `tool/site_chrome/` | 全站共用導覽的單一真相來源：把「圖解」下拉 3 入口（名詞圖解／坐禪與講經心智圖／問答錄2心智圖）、圖解頁 JSON-LD 寫回所有共用 chrome 頁；並附站台一致性檢查（AI 免責聲明、canonical、連結／錨點、sitemap、圖片屬性、`b-truth` 三節點）＋免 jsdom 的下拉互動測試。 | `sync.py` 定義 → root／`wenda2/`／`stories/` HTML；`dropdown_harness.js` 驗互動 | `README.md` |
| `tool/wenda2_knowledge/` | 問答錄 2 的兩本「複習用」電子書產生器：`hidden/wenda2_keypoints/`（重點知識，18 章主題章節＋自測）＋`hidden/wenda2_lens/`（另類閱讀視角，第二人稱敘事）（已部署但不索引；`hidden/` 已進版控）。SoT 是 `src/*.py`；`data/corpus.json` 為生成物。引文逐字對照 `wenda2_ebook/`，驗證不過就 exit 1。 | `wenda2_ebook/*.html` → `extract_corpus.py` → `data/corpus.json`；＋`src/*.py` → `build_all.py` → `hidden/wenda2_keypoints/`、`hidden/wenda2_lens/`（不索引） | `README.md` |
| `tool/books2ebook/` | 坐禅系列 + 講經系列共十本原書 → 靜態電子書（簡/繁、全量搜尋、每講播放鈕）。 | `books/*.pdf` → `ebook/` | `README.md` |
| `tool/ebook_knowledge/` | `ebook/` 十本書的兩本「複習用」電子書產生器：`hidden/ebook_keypoints/`（重點知識，主題重組＋逐字引文＋自測）＋`hidden/ebook_lens/`（另一個讀法，十本書走成一條十年的參學路，第二人稱敘事）（已部署但不索引；`hidden/` 已進版控）。SoT 是 `src/*.py`；`data/corpus.json` 為生成物。引文逐字對照 `ebook/`，驗證不過就 exit 1。 | `ebook/*.html` → `extract_corpus.py` → `data/corpus.json`；＋`src/*.py` → `build_all.py` → `hidden/ebook_keypoints/`、`hidden/ebook_lens/`（不索引） | `README.md` |
| `tool/pdf_audio_map/` | 對齊 PDF 章節（13–21）↔ 音檔時間 → 音訊映射 JSON（SoT：`tool/word2ebook/data/audio_map/`）。 | SRT/opus → `data/audio_map/*.json` | `README.md` |
| `tool/word_audio_map2/` | 對齊**時間序** Word 彙總（2024-02…2025-05）↔ SRT → `audio_map2/*.json`（`build_maps.py`）。段上的 `chapter_question_ids` 供前 12 章注入；**分段會隨 `build_maps.py` 的 Q&A 偵測調整**，重分段後以 `link_chapters.py` 重新寫回章節對應（詳見「分段與章節對應」）。 | docx + SRT → `audio_map2/*.json` | `README.md` |
| `tool/sense_voice/` | FunASR 中文 ASR → `.srt`/`.txt`（被 `pdf_audio_map/fill_misses.py` 呼叫做補漏）。 | mp3/wav → srt/txt | `README.md` |
| `tool/audio_denoiser/` | Facebook Denoiser 語音去雜音（ASR 前處理）。 | mp3/wav → mp3/wav | `README.md` |
| `tool/stories2html/` | 實修故事原始檔 → HTML 閱讀頁 + index/sitemap 補丁。 | `stories/<原始檔>` → `stories/<slug>.html` | `README.md`（metadata SoT：`docs.py`） |
| `tool/fonts/` | 全站字型自架子集管線：掃站用頁面語料（含 OpenCC 簡體聯集）→ pyftsubset 產十字重 woff2＋`fonts.css`，取代 Google Fonts 外鏈（大陸連不上）。 | root/`wenda2/`/`stories/` 頁面語料 → `fonts/` | `README.md`（執行用 word_audio_map2 的 venv；fonttools 在 `.pylibs`） |
| `tool/daily_quotes/` | 首頁「每日精選」語料管線：從兩套電子書索引抽候選（長度 60–400、黑名單、CJK 比例 ≥60%、排除純文言經文、md5 去重）→ `candidates.json`（16,382 條）；固定種子抽 2,400 條交 AI 評分（0–10）→ `select_1095.py` 以 score≥7 為骨架、其餘按可讀性啟發式補足→ repo 根目錄 `daily_quotes.json`（1,095 條，單一來源 ≤70%），由 `index.html` 依日期播種輪播。 | `{wenda2_ebook,ebook}/search_index_trad.json` → `build_quotes.py` → `candidates.json`；＋`candidates_sample.json`／`scores/batch_*.json` → `select_1095.py` → `daily_quotes.json` | **`README.md`** |
| `tool/jiangjing_para_map/` | 講經系列「段落 ↔ SRT 字元時間流」對齊 → `audio_map3/<series>.json`；重跑保留已 confirmed 段落與 reviewed 講次。books2ebook 只注入 reviewed 講次的段落時間。 | ebook HTML 段落 + `audio/srt/jiangjing/*.srt` → `audio_map3/*.json` | `README.md` |
| `tool/build_jiangjing_pdfs.py` | 【一次性已完成】組裝講經系列 PDF：合併（六祖壇經 2 PDF、楞嚴 docx→PDF）、四十二章/楞伽直接複製原檔（已含目錄）、其餘補檔首可點擊 TOC（含頁數）。**講經 5 本 PDF 已產出且驗證無誤，若未來不再新增/修改講經 PDF，此工具與下方兩個音檔工具可一併刪除。** | 來源 PDF/docx → `books/06…09*.pdf` + 感恩 | 檔首 docstring |
| `tool/series2audio.py` | 新錄音系列（義理／圓覺經／心經／金剛經）mp3·m4a → **去雜音（DNS64）+ 音量正規化** → opus（16kbps / mono / 48kHz / voip），輸出 `audio/yili/` 與 `audio/jiangjing/`。等於把 `jiangjing2audio.py` + `audio_denoiser/denoise_jiangjing.py` + `normalize_jiangjing_audio.py` 三步併成一步（模型每個 worker 只載入一次）。 | `~/Downloads/Tai师父*/音頻/*.mp3`／`*.m4a` → `audio/{yili,jiangjing}/*.opus` | 檔首 docstring |
| `tool/audio_index/` | 掃描整個 `audio/` 目錄產生入口頁 `audio/index.html`（粉色系、置頂大悲咒、類別下拉篩選）；新增任何 `*.opus` 都會自動進清單。 | `audio/**/*.opus` → `audio/index.html` | **`README.md`** + `index_template.html` |
| `tool/jiangjing2audio.py` | 【一次性已完成】講經系列 mp3 → opus（16kbps / mono / 48kHz / voip），檔名含錄音日期，輸出到 `audio/jiangjing/<日期>Tai师父讲经·<系列>(<N>).opus`（平放）。**105 支 opus 已轉檔、正規化完畢；若講經音檔不再新增，可刪除。** | mp3 → `audio/jiangjing/*.opus` | 檔首 docstring |
| `tool/normalize_jiangjing_audio.py` | 【一次性已完成】對齊既有答疑 opus 的平均音量（mean_volume ≈ -11 dB）：`volumedetect` 量平均音量 → `volume` + `alimiter` 補增益並重新編碼 opus。**原地更新** `audio/jiangjing/`。**已完成；若講經音檔不再新增，可刪除。** | `audio/jiangjing/*.opus`（原位） | 檔首 docstring |

### 已移除（不再保留）

以下工具為**一次性／已完成**流程，輸入或產生器已移除，故整包刪除（git 歷史仍可回溯）：

- ~~`tool/qa_resplit/`~~ — 對 `qa/*.txt`（校對轉錄稿，2025-11~2026-03）做 resplit/realign/TW-normalize；`qa/` 已刪，不再使用。
- ~~`tool/wenda2_curation/`~~ — 問答錄 2 心智圖的資料 SoT（57 名詞結構、逐字引句、名詞統計）與產生器（`build_mm.py`／`build_mm2.py`、`data/*.json`、`mm_data.js`）。發布頁 `wenda2_mindmap.html` **自包含且保持不動**，往後不再重新生成，來源與產生器已於 2026-09-28 整包移除（更早的知識頁部分已於 2026-09 移除）。
- ~~`tool/word_audio_map/`~~ — 主題式對齊器（舊 `data/audio_map_word/` 流程），源碼已刪。其 `.venv` 已搬至 `tool/word_audio_map2/`（供 `build_maps.py` 與 word2ebook 生成使用）。
- ~~`tool/video_creator/`~~ — 離線 ffmpeg（聲音 + `animation.mp4` → 影片），站外獨立用途，已移除。
- ~~`tool/session_knowledge/`~~ — 查證工程 session 紀錄生成器（`SESSION_KNOWLEDGE.md` → `session_knowledge.html`，內部 noindex 頁）。連同 `SESSION_KNOWLEDGE.md`、生成物、`.sk-*` CSS、`mm_harness.js` 於 2026-09 徹底移除，git 歷史可回溯。

---

## 依賴關係（誰讀誰）

```
問答錄2/*.docx + *.pdf
        │
        ▼
tool/word2ebook/  (gen_all.py)
   ├─ inject_chapters():           讀 tool/word2ebook/data/audio_map/*.json  (← tool/pdf_audio_map/)
   └─ inject_word_chapters():      讀 audio_map2/*.json 的 chapter_question_ids
        │                            (由 link_chapters.py 寫回；分段調整後需重跑)
        ▼
wenda2_ebook/  ← 建構產物，勿手改

books/*.pdf ── tool/books2ebook/gen_all.py ──► ebook/

講經系列（工具鏈，皆為**一次性組裝流程，已完成**）：
來源 PDF / docx ── tool/build_jiangjing_pdfs.py ──► books/06…09*.pdf（+ 感恩）【可刪除】
mp3 ── tool/jiangjing2audio.py ──► audio/jiangjing/<日期>Tai师父讲经·<系列>(<N>).opus（平放）【可刪除】
                                        │
                                        ▼ tool/normalize_jiangjing_audio.py（對齊答疑響度）【可刪除】
                                （原地更新 audio/jiangjing/）

新錄音（後續新增系列，取代上面兩支）：
~/Downloads/Tai师父*/音頻/*.mp3|m4a
        │
        ▼ tool/series2audio.py（DNS64 去雜音 + 音量對齊 -11 dB + opus 16kbps）
   audio/yili/*.opus（義理系列）、audio/jiangjing/*.opus（圓覺經／心經／金剛經…）
        │
        ▼ tool/audio_index/build_index.py（掃描全部 *.opus）
   audio/index.html（入口頁；audio/ 本身不在本 repo git 內）

SRT / opus ── tool/pdf_audio_map/ ──► tool/word2ebook/data/audio_map/*.json
                                        (補漏時經 tool/sense_voice/ 重新轉寫)

audio_map2/*.json 的產生：問答錄2 docx + SRT ── tool/word_audio_map2/build_maps.py ──► audio_map2/*.json
                                       └── 重分段後：link_chapters.py ──► 寫回 chapter_question_ids / chapter_indexes
```

### 首頁「每日精選」（tool/daily_quotes）

```
wenda2_ebook/search_index_trad.json（只取 answer 條目）┐
ebook/search_index_trad.json（content + answer 條目）  ┘
        │ tool/daily_quotes/build_quotes.py
        │   規則過濾：長度 60–400、黑名單（敷衍回答／亂碼問號／URL／時間戳行…）、
        │   CJK 比例 ≥60%、排除純文言經文（古典對話標記＋現代語助詞 ≤2）、md5 去重；
        │   clean() 會去掉開頭署名「Taiguanglin」與前導時間段
        ▼
   tool/daily_quotes/candidates.json            16,382 條（完整候選池，已進版控）
        │ 固定種子抽樣 2,400 條 → candidates_sample.json → 分批交 AI 評分 0–10
        ▼
   tool/daily_quotes/scores/batch_00..23.json   2,400 筆
        │   ⚠️ 每筆的 `idx` 是**索引進 candidates_sample.json 的位置**，不是 candidates.json
        ▼
   tool/daily_quotes/select_1095.py
        │   骨架：score ≥ 7（353 條，按分數降冪）
        │   補足：candidates.json 中未被評分過的候選，按 heuristic() 可讀性啟發排序（742 條）
        │          （長度窗、結尾標點、教學詞加分；前導時間戳／暱稱／英文代號、連續問號、
        │            括號不配對、數字比例過高、提問句罰分）
        │   來源上限：單一來源（ebook）≤ 70%（其餘靠 wenda2 平衡）
        ▼
   daily_quotes.json（repo 根目錄，1,095 條）
        ├─ index.html：fetch 後以本地日期播種（day*2654435761+97 取正模）輪播；
        │  同日同機一致，清單長度變動會重洗順序；附前一天／後一天／前後一個月跳轉
        └─ tool/fonts/build_fonts.py：把整個 daily_quotes.json 納入字型子集語料
           （動態注入的文字也必須有自架字型覆蓋）
```

> 註：`candidates.json`、`candidates_sample.json`、`scores/` **皆納入版控**（可重用的候選池與既有 AI 分數）；只有 `batches/`（評分前的暫存分批）在 `tool/daily_quotes/.gitignore` 內被忽略。
> 註：`candidates_sample.json` 沒有產生腳本（當初以固定種子人工抽樣）。要提升品質時：從 `candidates.json` 抽更多樣本評分 → 擴充／覆蓋 `scores/` → 調整 `select_1095.py` 的 `TARGET`（目前 1095＝三年份）後重跑；分數與啟發式比例可能隨過濾規則微調而變動，重跑後請更新 README 的數字。

### 分段與章節對應（word_audio_map2）

`build_maps.py` 把 Word 彙總切成「問答段」時，段數會隨 Q&A／後續題偵測邏輯調整；例如跨多個 `Taiguanglin：` 標記的同一作者貼文，可能被拆成多個子問答段。**過去假設「`audio_map2/*.json` 的分段不會再調整、`chapter_question_ids` 一次凍結即可」已不成立** —— 拆分邏輯會持續修正，所以：

- 重分段（`build_maps.py` 調整後）應以 `link_chapters.py` **為主**重新寫回每段的 `chapter_question_ids` / `chapter_indexes`（內容比對 `build/questions.json`）。預設 `--apply` 為 **fill-empty-only**——只補「缺章節」的段、絕不改已有人工校對連結的段、且只補尚未被任何段認領的 qid；`--apply --overwrite` 才整份重導（會丟掉未重新比到的既有 qid，慎用）。
- `link_chapters.py` 因過去假定「分段不再變」而被移除，現已**自 git 歷史恢復**（`tool/word_audio_map2/link_chapters.py`），供未來重跑。

`tool/word_audio_map2/` 內的腳本分工（詳見該目錄 `README.md`）：

| 腳本 | 用途 |
|------|------|
| `build_maps.py` | 主產生器：時間序 Word 彙總 → `audio_map2/*.json`（問答分段）。 |
| `link_chapters.py` | 章節對應之主：以內容比對把 `chapter_question_ids`/`chapter_indexes` 寫回；預設 fill-empty-only。 |
| `apply_resplit.py` | 用改過的分段邏輯重跑 parser，並按內容比對搬移舊段 `start/end`、`meta.lastPlayed` 等已校對欄位。 |
| `validate_resplit.py` | 結構驗證：index 連續、`stable_key`/`question_id` 唯一、章節覆蓋、時間單調。 |
| `validate_relink.py` | 對帳驗證：比對 git `HEAD`，強制「凍結 qid 零遺失」+「無新增 spurious 跨 session qid」+「`meta.lastPlayed` 不變」。 |
| `fill_orphan_chapters.py` / `redistribute_chapters.py` / `reconcile_qids.py` | 重分段與重對應之間的墊補（補孤兒章節 / 重分配多 qid 清單 / 掛回遺失 qid）。 |
| `fill_resolvable.py` | 為「有實質問答卻未對應」的段，以 q_text（include/ratio，並有最短字數護欄）補上分類題；列印每筆待人工複核。 |

> 有「最後播放」(`meta.lastPlayed`) 紀錄的段**任何腳本都不應改動**——人工校對音檔時間的完成判定以此為準。

> 註：若未來不再新增/修改講經 PDF 或音檔，**上述標記【可刪除】的三個講經工具（`build_jiangjing_pdfs.py`、`jiangjing2audio.py`、`normalize_jiangjing_audio.py`）可整包移除**；`gen_all.py` 重建電子書時只需：讀 `books/*.pdf` → 解析/分段 → 產生 HTML → 依 `audio_map.py` 映射插入播放鈕，不再涉及 PDF 組裝與音檔轉檔。

> 註：`.venv`（`tool/word_audio_map2/.venv`）是唯一裝有 docx / opencc / slugify /
> yaml / jieba / pymupdf 的環境，`gen_all.py`（word2ebook）與 `build_maps.py`、
> `audio_map2/tools/*.py` 都以它為 python。

---

## 概略原則

1. **Generated 目錄勿手改**：`wenda2_ebook/`、`ebook/` 皆為建構產物；改產生器或來源後重跑對應 `gen_all.py`。
2. **音訊播放鈕只在注入器產生**：`tool/word2ebook/core/audio_map_injector.py`（PDF 13–21）與 `inject_word_chapters()`（Word 01–12）。別手改章節 HTML。
3. **離線媒體工具（sense_voice / audio_denoiser）為輔助流程**，不參與 Pages 佈署；只有在新音檔需要 ASR 時才用。
4. 每個工具的尖細規則放它自己的 README/AGENTS.md；跨工具／站台級慣例放根 `AGENTS.md`。
